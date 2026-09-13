"""语音识别：SenseVoiceSmall + FSMN-VAD + CT-Punc。

时间戳约定（已对照 funasr 1.4.15 源码 `auto/auto_model.py` 确认）
------------------------------------------------------------
- `timestamp` 是 **毫秒整数** 二元组列表：[[start_ms, end_ms], ...]。
  源码在拼接 VAD 偏移时用的是 `t[0] = int(t[0]) + vadsegment_ms`，故单位是毫秒。
- `sentence_info` 只在配置了 `spk_model` 或显式传 `sentence_timestamp=True` 时才产出。
  本工具自己做说话人分离（不用内置 spk_model），因此必须显式打开 `sentence_timestamp`，
  否则拿不到分段结果，整个 3 小时视频会退化成单个 Segment。
- SenseVoice 是 NAR 模型，可能不返回词级时间戳；此时候选时间轴来自 VAD 切分边界。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from config import ASRConfig
from core.textutil import has_content, normalize_segment_text as normalize_text
from core.types import Segment, Word

ProgressFn = Callable[[float, str], None]

# 词级时间戳不可用时的兜底：按静音间隔切句
FALLBACK_GAP_MS = 800
FALLBACK_MAX_MS = 30_000


def resolve_device(preference: str = "auto") -> str:
    if preference != "auto":
        return preference
    try:
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _as_ms(value: Any) -> int:
    """funasr 的时间戳已是毫秒整数；兼容浮点毫秒。"""
    return int(round(float(value)))


def _parse_words(raw: Any, tokens: list[str] | None = None) -> list[Word]:
    """归一化词级时间戳。兼容两种历史格式：
    - 新版 [[start_ms, end_ms], ...]，token 从 words 字段取
    - 旧版 [[token, start_s, end_s], ...]（秒）
    """
    words: list[Word] = []
    if not raw:
        return words
    for index, item in enumerate(raw):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        if isinstance(item[0], str):
            # 旧版三元组：时间单位是秒
            try:
                start, end = int(float(item[1]) * 1000), int(float(item[2]) * 1000)
            except (TypeError, ValueError):
                continue
            text = item[0]
        else:
            start, end = _as_ms(item[0]), _as_ms(item[1])
            text = tokens[index] if tokens and index < len(tokens) else ""
        words.append(Word(text=text, start_ms=start, end_ms=max(end, start)))
    return words


def _split_words_by_silence(words: list[Word]) -> list[Segment]:
    """词级时间戳可用、但没有 sentence_info 时的兜底：按静音间隔切句。"""
    segments: list[Segment] = []
    bucket: list[Word] = []

    def flush() -> None:
        if not bucket:
            return
        text = normalize_text("".join(w.text for w in bucket))
        if has_content(text):
            segments.append(
                Segment(
                    start_ms=bucket[0].start_ms,
                    end_ms=bucket[-1].end_ms,
                    text=text,
                    words=list(bucket),
                )
            )
        bucket.clear()

    for word in words:
        if bucket:
            gap = word.start_ms - bucket[-1].end_ms
            span = word.end_ms - bucket[0].start_ms
            if gap > FALLBACK_GAP_MS or span > FALLBACK_MAX_MS:
                flush()
        bucket.append(word)
    flush()
    return segments


class ASREngine:
    """一次性加载模型，可重复处理多个文件（批量时不要每文件重建）。"""

    def __init__(self, cfg: ASRConfig | None = None) -> None:
        self.cfg = cfg or ASRConfig()
        self.device = resolve_device(self.cfg.device)
        self._model = None

    def load(self, progress: ProgressFn | None = None) -> None:
        if self._model is not None:
            return
        if progress:
            progress(0.0, f"加载 SenseVoice 模型（{self.device}），首次运行需下载权重…")

        from funasr import AutoModel

        kwargs: dict[str, Any] = {
            "model": self.cfg.asr_model,
            "trust_remote_code": True,
            "vad_model": self.cfg.vad_model,
            "vad_kwargs": {"max_single_segment_time": self.cfg.max_single_segment_ms},
            "device": self.device,
            "disable_update": True,
            "disable_pbar": True,
        }
        if self.cfg.request_punc:
            kwargs["punc_model"] = self.cfg.punc_model

        self._model = AutoModel(**kwargs)
        if progress:
            progress(1.0, "模型就绪")

    def transcribe(
        self,
        wav_path: str | Path,
        progress: ProgressFn | None = None,
        duration_ms: int = 0,
    ) -> list[Segment]:
        """整段音频识别，返回按时间排序的 Segment 列表（此阶段 speaker 均为 -1）。"""
        self.load(progress)
        assert self._model is not None

        if progress:
            progress(0.1, "语音识别中…")

        result = self._model.generate(
            input=str(wav_path),
            cache={},
            language=self.cfg.language,
            use_itn=self.cfg.use_itn,
            batch_size_s=self.cfg.batch_size_s,
            merge_vad=self.cfg.merge_vad,
            merge_length_s=self.cfg.merge_length_s,
            output_timestamp=True,
            sentence_timestamp=True,  # 关键：否则不返回 sentence_info
            disable_pbar=True,        # 进度条会污染服务端日志
        )

        segments = self._parse_result(result)
        if progress:
            progress(1.0, f"识别完成，共 {len(segments)} 段")
        return segments

    def _parse_result(self, result: Any) -> list[Segment]:
        if not result:
            return []
        payload = result[0] if isinstance(result, list) else result
        if not isinstance(payload, dict):
            return []

        segments = self._from_sentence_info(payload)
        if segments:
            return segments

        # 兜底：只有整段文本 + 词级时间戳
        text = normalize_text(str(payload.get("text", "")))
        words = _parse_words(payload.get("timestamp"), payload.get("words"))
        if words:
            segments = _split_words_by_silence(words)
            if segments:
                return segments
        if not has_content(text):
            return []
        return [Segment(start_ms=0, end_ms=0, text=text)]

    @staticmethod
    def _from_sentence_info(payload: dict[str, Any]) -> list[Segment]:
        info = payload.get("sentence_info")
        if not isinstance(info, list) or not info:
            return []
        segments: list[Segment] = []
        for item in info:
            if not isinstance(item, dict):
                continue
            text = normalize_text(str(item.get("text", "") or item.get("sentence", "")))
            if not has_content(text):
                continue
            start = _as_ms(item.get("start", 0))
            end = _as_ms(item.get("end", start))
            words = _parse_words(item.get("timestamp"), item.get("words"))
            segments.append(
                Segment(start_ms=start, end_ms=max(end, start), text=text, words=words)
            )
        return sorted(segments, key=lambda s: s.start_ms)
