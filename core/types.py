"""核心数据结构。所有中间产物都通过这里定义的 dataclass 流转，便于落盘与续跑。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Word:
    """词级时间戳，单位毫秒。"""

    text: str
    start_ms: int
    end_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Word":
        return cls(text=d["text"], start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]))


@dataclass
class Segment:
    """一个 VAD 切分出的语音片段，附带识别文本与说话人编号。"""

    start_ms: int
    end_ms: int
    text: str
    speaker: int = -1                     # -1 表示尚未分配
    words: list[Word] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "speaker": self.speaker,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Segment":
        return cls(
            start_ms=int(d["start_ms"]),
            end_ms=int(d["end_ms"]),
            text=d.get("text", ""),
            speaker=int(d.get("speaker", -1)),
            words=[Word.from_dict(w) for w in d.get("words", [])],
        )


@dataclass
class Turn:
    """合并后的发言段落：同一说话人连续内容已拼接，供渲染直接消费。"""

    speaker: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass
class MediaMeta:
    """输入素材的元信息，写入 Markdown 文件头。"""

    title: str
    source: str = ""
    duration_ms: int = 0
    platform: str = "local"
    extra: dict[str, Any] = field(default_factory=dict)


def speaker_label(index: int) -> str:
    """说话人编号 -> 展示用角色名。只用匿名角色，不做身份识别。"""
    if index < 0:
        return "未识别"
    if index < 26:
        return f"角色{chr(ord('A') + index)}"
    return f"角色{index + 1}"
