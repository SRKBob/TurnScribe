"""说话人分离：CAM++ 声纹嵌入 + 全局层次聚类。

为什么不用 funasr 内置的 spk_model 组合
--------------------------------------
1. 官方 README 明确说明该组合「未验证分离准确率」；
2. 它在长音频上做滑窗聚类，簇编号会漂移 —— 3 小时素材容易出现同一人被拆成多个角色。

本模块的做法：对每个 VAD 片段单独提声纹，再做一次**全局**层次聚类。
声纹向量总量极小（几千条 × 192 维），不存在漂移问题，且超长片段会自动取子窗口平均。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from config import DiarizeConfig
from core.types import Segment

ProgressFn = Callable[[float, str], None]

# 超过该时长的片段按子窗口切分后取平均，避免一个片段里混入两个人导致声纹失真
LONG_SEGMENT_MS = 8_000
SUB_WINDOW_MS = 3_000


class DiarizationError(RuntimeError):
    pass


class Diarizer:
    def __init__(self, cfg: DiarizeConfig | None = None, device: str = "cpu") -> None:
        self.cfg = cfg or DiarizeConfig()
        self.device = device
        self._model = None

    def load(self, progress: ProgressFn | None = None) -> None:
        if self._model is not None:
            return
        if progress:
            progress(0.0, "加载 CAM++ 声纹模型…")
        from funasr import AutoModel

        self._model = AutoModel(
            model="cam++",
            device=self.device,
            disable_update=True,
            disable_pbar=True,  # 逐段调用 generate 时每段会新建一条 tqdm 蓝条，在控制台堆成刷屏
        )

    # ---------- 声纹提取 ----------

    def _embed_slice(self, audio: np.ndarray, start_ms: int, end_ms: int) -> np.ndarray | None:
        """对一段音频提声纹；超长片段取多子窗平均。"""
        assert self._model is not None
        sr = 16_000
        start = max(0, int(start_ms / 1000 * sr))
        end = min(len(audio), int(end_ms / 1000 * sr))
        if end - start < int(self.cfg.min_segment_ms / 1000 * sr):
            return None

        span = end - start
        sub_len = int(SUB_WINDOW_MS / 1000 * sr)
        if span <= int(LONG_SEGMENT_MS / 1000 * sr):
            windows = [(start, end)]
        else:
            windows = [
                (offset, min(offset + sub_len, end))
                for offset in range(start, end, sub_len)
                if min(offset + sub_len, end) - offset >= int(1_000 / 1000 * sr)
            ]
            if not windows:
                windows = [(start, end)]

        vectors: list[np.ndarray] = []
        for w_start, w_end in windows:
            try:
                result = self._model.generate(input=audio[w_start:w_end], fs=sr)
            except Exception:
                continue
            vector = self._extract_vector(result)
            if vector is not None:
                vectors.append(vector)
        if not vectors:
            return None
        mean = np.mean(vectors, axis=0)
        norm = float(np.linalg.norm(mean))
        return mean / norm if norm > 0 else None

    @staticmethod
    def _extract_vector(result: Any) -> np.ndarray | None:
        """funasr 的 CAM++ 输出键名在不同版本间略有差异，这里逐个尝试。"""
        if not result:
            return None
        payload = result[0] if isinstance(result, list) else result
        if not isinstance(payload, dict):
            return None
        for key in ("spk_embedding", "embedding", "spk_emb"):
            value = payload.get(key)
            if value is None:
                continue
            array = value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)
            array = np.asarray(array, dtype=np.float32).reshape(-1)
            if array.size:
                norm = float(np.linalg.norm(array))
                return array / norm if norm > 0 else None
        return None

    # ---------- 聚类 ----------

    def _cluster(self, embeddings: np.ndarray) -> np.ndarray:
        """层次聚类（平均连接 + 余弦距离）。簇数超上限时逐步放宽阈值合并。"""
        from scipy.cluster.hierarchy import fcluster, linkage

        if len(embeddings) == 1:
            return np.array([0])

        tree = linkage(embeddings, method="average", metric="cosine")
        threshold = self.cfg.cluster_threshold
        labels = fcluster(tree, t=threshold, criterion="distance")

        # 簇数超上限：抬高阈值强制合并（阈值越大越倾向合并）
        guard = 0
        while len(set(labels)) > self.cfg.max_speakers and guard < 20:
            threshold += 0.02
            labels = fcluster(tree, t=threshold, criterion="distance")
            guard += 1
        return labels - 1  # 归一到 0 起

    def _absorb_small_clusters(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
        durations_ms: list[int],
    ) -> np.ndarray:
        """把「噪声簇」按声纹相似度并入最近的大簇，返回 0 起的连续编号。

        为什么需要这一步：说话人嵌入在短促、低能量的片段上极不可靠，
        「对不对？」「嗯」「好」这类插入语经常被判成一个独立角色。实测一段
        13 分钟的独白会被拆成 10 个角色，其中 9 个簇合计不到 10 秒。

        判据（满足其一即视为噪声簇）：
          1. 簇内总发言时长低于 min_cluster_ms；
          2. 簇内总发言时长低于「最大簇 × min_cluster_ratio」。
        第 2 条让阈值随素材长度自适应 —— 13 秒的短音频和 3 小时的会议
        可以用同一套参数，不会因为绝对时长差异而失效。
        """
        unique = sorted({int(v) for v in labels})
        if len(unique) <= 1:
            return np.zeros(len(labels), dtype=int)

        weights = np.asarray(durations_ms, dtype=np.float64)
        totals = {c: float(weights[labels == c].sum()) for c in unique}
        biggest = max(totals.values()) or 1.0

        centroids: dict[int, np.ndarray] = {}
        for c in unique:
            vec = embeddings[labels == c].mean(axis=0)
            norm = float(np.linalg.norm(vec))
            centroids[c] = vec / norm if norm > 0 else vec

        floor = max(float(self.cfg.min_cluster_ms), biggest * self.cfg.min_cluster_ratio)
        large = [c for c in unique if totals[c] >= floor]
        if not large:  # 极端情况：全是小簇，至少保住时长最长的那个
            large = [max(unique, key=lambda c: totals[c])]

        mapping: dict[int, int] = {}
        for c in unique:
            if c in large:
                continue
            mapping[c] = max(large, key=lambda other: float(centroids[c] @ centroids[other]))

        resolved = [mapping.get(int(v), int(v)) for v in labels]
        order = {c: i for i, c in enumerate(sorted(set(resolved)))}
        return np.array([order[c] for c in resolved], dtype=int)

    def _reassign_short(self, segments: list[Segment]) -> None:
        """未参与聚类的短片段，按时间就近归给已识别的说话人。"""
        known = [(s.start_ms, s.end_ms, s.speaker) for s in segments if s.speaker >= 0]
        if not known:
            return
        for seg in segments:
            if seg.speaker >= 0:
                continue
            mid = (seg.start_ms + seg.end_ms) / 2
            seg.speaker = min(
                known,
                key=lambda item: abs(mid - (item[0] + item[1]) / 2),
            )[2]

    def assign(
        self,
        wav_path: str | Path,
        segments: list[Segment],
        progress: ProgressFn | None = None,
    ) -> int:
        """给每个 Segment 打上 speaker 编号，返回识别出的说话人数量。

        失败时抛 DiarizationError，由调用方决定是否降级为单说话人。
        """
        if not segments:
            return 0

        self.load(progress)
        assert self._model is not None

        try:
            import soundfile as sf

            audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != 16_000:
                raise DiarizationError(f"采样率应为 16000，实际 {sr}")
        except ImportError as exc:
            raise DiarizationError("缺少 soundfile，请执行 pip install soundfile") from exc

        total = len(segments)
        vectors: list[np.ndarray] = []
        indexes: list[int] = []
        for index, seg in enumerate(segments):
            vector = self._embed_slice(audio, seg.start_ms, seg.end_ms)
            if vector is not None:
                vectors.append(vector)
                indexes.append(index)
            if progress and index % 20 == 0:
                progress(index / max(1, total), f"提取声纹 {index}/{total}")

        if len(vectors) < 1:
            raise DiarizationError("未能提取到任何声纹，可能是音频全为静音或过短")

        matrix = np.vstack(vectors)
        labels = self._cluster(matrix)
        labels = self._absorb_small_clusters(
            matrix, labels, [segments[i].duration_ms for i in indexes]
        )
        for position, seg_index in enumerate(indexes):
            segments[seg_index].speaker = int(labels[position])

        self._reassign_short(segments)
        speaker_count = len({int(v) for v in labels})
        if progress:
            progress(1.0, f"说话人分离完成，共 {speaker_count} 位")
        return speaker_count


def assign_single_speaker(segments: list[Segment]) -> int:
    """降级路径：全部归为角色A。"""
    for seg in segments:
        seg.speaker = 0
    return 1
