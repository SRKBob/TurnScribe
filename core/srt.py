"""SRT 字幕渲染。把合并后的 Turn 列表转成标准 SubRip 字幕文件。

格式约定（SubRip）：
    序号
    HH:MM:SS,mmm --> HH:MM:SS,mmm
    字幕文本（可多行）
    <空行>

时间轴策略：复用 Markdown 渲染的「长发言按句切分 + 字符占比插值」逻辑，
保证同一个视频里 Markdown 的时间戳与字幕的时间轴一致。估算值不精确，
但足以拖动进度条对到「大概哪句话」。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.render import _chunk_starts, _split_long_text
from core.types import Turn, speaker_label

# 单条字幕的舒适上限：超过就按句切分。SRT 常见实践是每条不超过 ~20 字（中文），
# 但切太碎会闪屏，取一个折中值。
MAX_CUE_CHARS = 42

# 一条字幕的最短停留时间（毫秒），防止切块过密时字幕闪烁
MIN_CUE_MS = 600


def fmt_srt_ts(ms: int) -> str:
    """毫秒 -> SRT 时间戳 HH:MM:SS,mmm（注意是逗号，SubRip 规范如此）。"""
    total = max(0, ms)
    return f"{total // 3600000:02d}:{total % 3600000 // 60000:02d}:{total % 60000 // 1000:02d},{total % 1000:03d}"


@dataclass
class Cue:
    """一条字幕：起止毫秒 + 文本（可含角色前缀）。"""

    start_ms: int
    end_ms: int
    text: str


def build_cues(
    turns: list[Turn],
    *,
    speaker_prefix: bool = True,
    max_chars: int = MAX_CUE_CHARS,
) -> list[Cue]:
    """把发言段落切分成字幕条。

    切分规则与 Markdown 渲染一致（按句号/问号/叹号断句，超长再兜底），
    时间用字符占比线性插值估算；相邻字幕的结束时间顶到下一条开始，
    避免两条字幕之间出现无意义的空窗。
    """
    cues: list[Cue] = []
    for turn in turns:
        text = turn.text.strip()
        if not text:
            continue
        chunks = _split_long_text(text, max_chars)
        starts = _chunk_starts(chunks, turn.start_ms, turn.end_ms)
        for i, (chunk, start_ms) in enumerate(zip(chunks, starts)):
            end_ms = starts[i + 1] if i + 1 < len(starts) else turn.end_ms
            end_ms = max(end_ms, start_ms + MIN_CUE_MS)
            label = f"{speaker_label(turn.speaker)}：" if speaker_prefix else ""
            cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=label + chunk))
    return cues


def render_srt(
    turns: list[Turn],
    *,
    speaker_prefix: bool = True,
    max_chars: int = MAX_CUE_CHARS,
) -> str:
    """渲染完整 SRT 文本（UTF-8，无 BOM；播放器普遍兼容）。"""
    cues = build_cues(turns, speaker_prefix=speaker_prefix, max_chars=max_chars)
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{fmt_srt_ts(cue.start_ms)} --> {fmt_srt_ts(cue.end_ms)}\n"
            f"{cue.text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def speaker_prefix_needed(turns: list[Turn]) -> bool:
    """「auto」策略：多位说话人时才加角色前缀，单人视频不加。"""
    return len({t.speaker for t in turns}) > 1


def write_srt(content: str, out_path: Path) -> Path:
    # utf-8-sig（带 BOM）：VLC/PotPlayer/mpv 都认，老播放器也不会把中文猜成 GBK；
    # CRLF 是 SubRip 的传统换行，Notepad 直接打开不挤成一行。
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8-sig", newline="\r\n")
    return out_path
