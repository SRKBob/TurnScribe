"""Markdown 渲染。把合并后的 Turn 列表转成可读、可存档的文档。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config import RenderConfig
from core.textutil import join_text
from core.types import MediaMeta, Segment, Turn, speaker_label


def fmt_ts(ms: int) -> str:
    """毫秒 -> HH:MM:SS（超过一小时保留小时位，方便对着视频拖进度条）。"""
    total = max(0, ms) // 1000
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def merge_segments(
    segments: list[Segment],
    *,
    merge_gap_ms: int = 1200,
    min_turn_ms: int = 800,
) -> list[Turn]:
    """把碎片段合并成发言段落。

    规则：
    1. 按时间排序（并发识别的输出顺序不可信，必须重排）。
    2. 相邻同说话人、且间隔小于 merge_gap_ms 的片段合并。
    3. 合并后短于 min_turn_ms 的段落并入前一段，避免"嗯""对"刷屏。
    4. 空文本直接丢弃。
    """
    ordered = sorted(
        (s for s in segments if s.text and s.text.strip()),
        key=lambda s: (s.start_ms, s.end_ms),
    )

    turns: list[Turn] = []
    for seg in ordered:
        text = seg.text.strip()
        if turns:
            prev = turns[-1]
            same_speaker = prev.speaker == seg.speaker
            close_enough = seg.start_ms - prev.end_ms <= merge_gap_ms
            if same_speaker and close_enough:
                prev.text = join_text(prev.text, text)
                prev.end_ms = max(prev.end_ms, seg.end_ms)
                continue
        turns.append(Turn(speaker=seg.speaker, start_ms=seg.start_ms, end_ms=seg.end_ms, text=text))

    # 短插话并入上一段（同说话人才并，否则会污染角色归属）
    merged: list[Turn] = []
    for turn in turns:
        if (
            merged
            and turn.speaker == merged[-1].speaker
            and turn.duration_ms < min_turn_ms
        ):
            merged[-1].text = join_text(merged[-1].text, turn.text)
            merged[-1].end_ms = max(merged[-1].end_ms, turn.end_ms)
            continue
        merged.append(turn)
    return merged


def _split_long_text(text: str, limit: int) -> list[str]:
    """超长发言按句号切段，避免出现整屏文字墙。"""
    if limit <= 0 or len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buffer = ""
    for piece in text.replace("！", "！\n").replace("？", "？\n").replace("。", "。\n").split("\n"):
        if not piece:
            continue
        if buffer and len(buffer) + len(piece) > limit:
            chunks.append(buffer)
            buffer = piece
        else:
            buffer += piece
    if buffer:
        chunks.append(buffer)
    return chunks


def _chunk_starts(chunks: list[str], start_ms: int, end_ms: int) -> list[int]:
    """给超长发言的各个分块估算起始时间，按字符占比线性插值。

    单说话人长视频几乎整段都会被合并成一段，切块后若不带时间戳就没法对着
    视频回查。估算值不精确，但足以定位到「大概哪一分钟」。
    """
    if not chunks:
        return []
    total = sum(len(c) for c in chunks) or 1
    span = max(0, end_ms - start_ms)
    starts: list[int] = []
    offset = 0
    for chunk in chunks:
        starts.append(start_ms + int(span * offset / total))
        offset += len(chunk)
    return starts


def render_markdown(
    meta: MediaMeta,
    turns: list[Turn],
    cfg: RenderConfig | None = None,
) -> str:
    cfg = cfg or RenderConfig()
    lines: list[str] = []

    lines.append(f"# {meta.title or '转写结果'}")
    lines.append("")

    if cfg.include_meta:
        speakers = sorted({t.speaker for t in turns})
        lines.append(f"> 来源：{meta.source or '本地文件'}")
        lines.append(f"> 时长：{fmt_ts(meta.duration_ms)}")
        lines.append(f"> 说话人：{len(speakers)} 位")
        if meta.extra.get("transcript_source") == "cc":
            lines.append("> 说明：本稿直接取自视频自带 CC 字幕，字幕不含说话人信息，全文统一显示为「角色A」。")
        lines.append(f"> 转写时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("> 由 SenseVoice 自动转写，可能存在识别误差，重要内容请对照原视频核对。")
        lines.append("")

    lines.append("---")
    lines.append("")

    if cfg.include_speaker_stats:
        stats: dict[int, int] = defaultdict(int)
        for turn in turns:
            stats[turn.speaker] += turn.duration_ms
        lines.append("## 发言时长统计")
        lines.append("")
        lines.append("| 角色 | 发言时长 | 占比 |")
        lines.append("| --- | --- | --- |")
        total = sum(stats.values()) or 1
        for speaker, ms in sorted(stats.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {speaker_label(speaker)} | {fmt_ts(ms)} | {ms / total:.1%} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    for turn in turns:
        name = speaker_label(turn.speaker)
        chunks = _split_long_text(turn.text, cfg.paragraph_chars)
        starts = _chunk_starts(chunks, turn.start_ms, turn.end_ms)

        if cfg.style == "block":
            for chunk, chunk_start in zip(chunks, starts):
                stamp = f"`{fmt_ts(chunk_start)}` " if cfg.with_timestamp else ""
                lines.append(f"**{name}** {stamp}".rstrip())
                lines.append("")
                lines.append(chunk)
                lines.append("")
        else:
            for chunk, chunk_start in zip(chunks, starts):
                stamp = f"`{fmt_ts(chunk_start)}` " if cfg.with_timestamp else ""
                prefix = f"**{name}** {stamp}".rstrip()
                lines.append(f"{prefix}：{chunk}")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def safe_filename(name: str, fallback: str = "transcript") -> str:
    """去掉 Windows 文件名非法字符。"""
    cleaned = "".join(ch for ch in name if ch not in '<>:"/\\|?*').strip().strip(".")
    return (cleaned or fallback)[:120]


def write_markdown(content: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
