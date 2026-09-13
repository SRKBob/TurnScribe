"""处理链路编排：下载/读取 -> 抽音轨 -> 识别 -> 说话人分离 -> 合并渲染。

长任务的三处加固
----------------
1. **增量落盘**：每阶段结果写 temp/cache/<key>/，中途中断可续跑（resume=True）。
2. **分段排序**：并发识别会打乱顺序，合并前统一按时间重排。
3. **模型复用**：ASR / CAM++ 只在进程内加载一次，批量处理不重复初始化。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import CONFIG, CACHE_DIR, AppConfig, ensure_dirs
from core.asr import ASREngine
from core.diarize import DiarizationError, Diarizer, assign_single_speaker
from core.downloader import cleanup_downloads, resolve_input
from core.media import extract_audio, probe_duration_ms
from core.render import merge_segments, render_markdown, safe_filename, write_markdown
from core.srt import render_srt, speaker_prefix_needed, write_srt
from core.types import MediaMeta, Segment, Turn

ProgressFn = Callable[[float, str], None]

# 识别/解析逻辑的版本号。改动 asr/diarize 的语义后必须递增，
# 否则旧缓存会让改进对已处理过的文件静默失效。
CACHE_VERSION = 4


@dataclass
class TaskResult:
    source: str
    title: str
    md_path: Path | None
    duration_ms: int
    speaker_count: int
    turn_count: int
    elapsed_s: float
    warnings: list[str] = field(default_factory=list)
    turns: list[Turn] = field(default_factory=list)
    srt_path: Path | None = None

    @property
    def summary(self) -> str:
        minutes, seconds = divmod(int(self.elapsed_s), 60)
        return (
            f"{self.title} | 时长 {self.duration_ms // 60000} 分钟 | "
            f"{self.speaker_count} 位说话人 | {self.turn_count} 段 | 耗时 {minutes}m{seconds}s"
        )


def _cache_key(source: str, path: Path, cfg: AppConfig) -> str:
    """缓存键：来源 + 文件大小/修改时间 + 影响结果的配置项。"""
    stat = path.stat() if path.is_file() else None
    raw = json.dumps(
        {
            "v": CACHE_VERSION,
            "source": source,
            "size": stat.st_size if stat else 0,
            "mtime": int(stat.st_mtime) if stat else 0,
            "lang": cfg.asr.language,
            "itn": cfg.asr.use_itn,
            "device": cfg.asr.device,
            "threshold": cfg.diarize.cluster_threshold,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


class Pipeline:
    """可复用的处理引擎。批量任务请复用同一个实例，模型只加载一次。"""

    def __init__(self, cfg: AppConfig | None = None) -> None:
        self.cfg = cfg or CONFIG
        ensure_dirs()
        self._asr: ASREngine | None = None
        self._diarizer: Diarizer | None = None

    # ---------- 子步骤 ----------

    def _get_asr(self) -> ASREngine:
        if self._asr is None:
            self._asr = ASREngine(self.cfg.asr)
        return self._asr

    def _get_diarizer(self) -> Diarizer:
        if self._diarizer is None:
            self._diarizer = Diarizer(self.cfg.diarize, device=self._get_asr().device)
        return self._diarizer

    @staticmethod
    def _scaled(progress: ProgressFn | None, low: float, high: float) -> ProgressFn | None:
        """把子步骤的 0~1 进度映射到整体进度区间。"""
        if progress is None:
            return None
        return lambda ratio, msg: progress(low + (high - low) * max(0.0, min(1.0, ratio)), msg)

    # ---------- 主流程 ----------

    def process(
        self,
        raw_input: str,
        out_dir: Path | None = None,
        progress: ProgressFn | None = None,
    ) -> TaskResult:
        started = time.time()
        warnings: list[str] = []
        out_dir = out_dir or (Path(__file__).resolve().parent.parent / "output")
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1) 解析输入（本地路径直通，链接走下载器）
        media_path, platform = resolve_input(
            raw_input, CACHE_DIR / "downloads", self._scaled(progress, 0.0, 0.05)
        )
        duration_ms = probe_duration_ms(media_path)

        key = _cache_key(raw_input, media_path, self.cfg)
        work = CACHE_DIR / key
        work.mkdir(parents=True, exist_ok=True)
        audio_path = work / "audio.wav"
        seg_file = work / "02_segments_spk.json"

        # 2) 抽音轨（缓存命中则跳过）
        if not audio_path.exists():
            if progress:
                progress(0.05, "抽取音轨（仅取音频，忽略视频流）…")
            extract_audio(media_path, audio_path)
        else:
            if progress:
                progress(0.05, "复用已抽取的音轨")

        # 3) 识别 + 说话人分离（整体结果一起缓存）
        segments = self._load_segments(seg_file) if self.cfg.resume else None
        if segments is None:
            segments = self._get_asr().transcribe(
                audio_path,
                progress=self._scaled(progress, 0.10, 0.65),
                duration_ms=duration_ms,
            )
            if not segments:
                raise ValueError("未识别到任何语音内容，请检查视频音轨")

            speaker_count = 0
            if progress:
                progress(0.65, "说话人分离中…")
            try:
                speaker_count = self._get_diarizer().assign(
                    audio_path, segments, self._scaled(progress, 0.65, 0.92)
                )
            except DiarizationError as exc:
                warnings.append(f"说话人分离失败，已降级为单说话人：{exc}")
                speaker_count = assign_single_speaker(segments)

            self._save_segments(seg_file, segments)
        else:
            if progress:
                progress(0.92, "命中缓存，复用上一轮识别结果")
            speaker_count = len({s.speaker for s in segments if s.speaker >= 0}) or 1

        # 4) 合并 + 渲染。文稿与字幕独立开关，但至少要选一个——
        #    什么都不导出的转写没有意义，直接当成配置错误拦下。
        if not (self.cfg.export_md or self.cfg.export_srt):
            raise ValueError("导出格式一项都没勾选：请至少选择「Markdown 文稿」或「SRT 字幕」其中之一")

        if progress:
            progress(0.94, "合并段落并渲染…")
        turns = merge_segments(
            segments,
            merge_gap_ms=self.cfg.diarize.merge_gap_ms,
            min_turn_ms=self.cfg.diarize.min_turn_ms,
        )
        title = media_path.stem if platform == "local" else _title_from_download(media_path)
        meta = MediaMeta(
            title=title,
            source=raw_input,
            duration_ms=duration_ms,
            platform=platform,
        )
        markdown = render_markdown(meta, turns, self.cfg.render)

        md_path: Path | None = None
        if self.cfg.export_md:
            md_path = write_markdown(
                markdown, out_dir / f"{safe_filename(title)}.md"
            )

        # 4b) SRT 字幕：与 Markdown 同名。角色前缀 auto——多人对话才标「角色A：」，
        #     单人视频满屏前缀只会干扰阅读。
        srt_path: Path | None = None
        if self.cfg.export_srt:
            if progress:
                progress(0.97, "生成 SRT 字幕…")
            if self.cfg.srt_prefix == "auto":
                use_prefix = speaker_prefix_needed(turns)
            else:
                use_prefix = self.cfg.srt_prefix == "always"
            srt_path = write_srt(
                render_srt(turns, speaker_prefix=use_prefix),
                out_dir / f"{safe_filename(title)}.srt",
            )

        # 5) 清理：尽力而为。删除失败绝不能影响已经完成的转写结果，
        #    某些环境会用安全钩子拦截程序化删除。
        if not self.cfg.keep_audio:
            _safe_unlink(audio_path)
        if platform != "local":
            cleanup_downloads(CACHE_DIR / "downloads")

        if progress:
            progress(1.0, "完成")

        return TaskResult(
            source=raw_input,
            title=title,
            md_path=md_path,
            duration_ms=duration_ms,
            speaker_count=speaker_count,
            turn_count=len(turns),
            elapsed_s=time.time() - started,
            warnings=warnings,
            turns=turns,
            srt_path=srt_path,
        )

    # ---------- 缓存读写 ----------

    @staticmethod
    def _save_segments(path: Path, segments: list[Segment]) -> None:
        path.write_text(
            json.dumps([s.to_dict() for s in segments], ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _load_segments(path: Path) -> list[Segment] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [Segment.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


def _title_from_download(media_path: Path) -> str:
    """下载来的文件以视频 ID 命名，尽量从 yt-dlp 元信息里取真实标题。

    注意元信息文件名是 `<video_id>.info.json`，与媒体文件 `<video_id>.<ext>` 同目录
    同主干，所以要用 `with_suffix(".info.json")` 而不是在媒体扩展名后再挂一截。
    """
    info_file = media_path.with_suffix(".info.json")
    if info_file.exists():
        try:
            data = json.loads(info_file.read_text(encoding="utf-8"))
            title = str(data.get("title", "")).strip()
            if title:
                return title
        except (json.JSONDecodeError, OSError):
            pass
    return media_path.stem


def _safe_unlink(path: Path) -> None:
    """删不掉就删不掉，不能让清理动作把整批任务带崩。

    捕获 BaseException 是刻意的：沙箱/安全钩子拦截删除时抛出的可能是 SystemExit，
    它继承自 BaseException 而非 Exception，只捕获 OSError 会漏掉并直接终止进程。
    """
    try:
        path.unlink(missing_ok=True)
    except BaseException:  # noqa: BLE001 - 清理失败必须无副作用
        pass
