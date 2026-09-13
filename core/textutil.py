"""文本清洗工具。ASR 分段与 Markdown 渲染共用同一套规则，避免两处不一致。

为什么需要独立的清洗层
----------------------
VAD 会从句中、词间断开音频，SenseVoice 随后给每个新段落补上标点。结果是：

- 段首多出孤立标点：`"，对不对？"`、`"。 好，"` —— 拼接后变成 `"。，对不对？"`
- 段尾多出标点串：`"假装看不到。，"` —— 拼接后变成 `"…看不到。，会先修一些别的"`
- 出现只含标点的 60ms 噪声段：`"。，"`、`"。"`

这些既污染转写稿，也污染声纹聚类（短噪声段会被判成独立说话人）。
所以统一在 `normalize_segment_text()` 里处理，渲染前再用 `join_text()` 兜一层。
"""

from __future__ import annotations

import re

# 句末/停顿标点
_PUNC_CLASS = "。！？，、；：,.!?;:…"
# 连续标点：出现两个以上基本都来自「VAD 切断 + 模型补标点」
_PUNC_RUN_RE = re.compile(f"[{_PUNC_CLASS}]{{2,}}")
# 收敛时保留哪一个：按表意强度排序
_PUNC_PRIORITY = "。！？…，、；：,.!?;:"
# 段落前导的孤立标点（只剥前导，尾随标点是正常句读）
_LEADING_PUNC = _PUNC_CLASS + "· \u3000\t\r\n"
# 是否含真实内容：至少一个字母/数字/汉字/假名/谚文
_CONTENT_RE = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")

# rich_transcription_postprocess 产出的情感/事件标签，以及 SenseVoice 特殊 token
_TAG_RE = re.compile(r"<\|[^|>]*\|>")
_SPECIAL_RE = re.compile(r"<(?:\|[^>]*\|)?(?:s|e|o|nospeech|/s|/e|/o)[^>]*>")


def has_content(text: str) -> bool:
    """是否含真实内容。纯标点段是 VAD 切分噪声，应直接丢弃。"""
    return bool(_CONTENT_RE.search(text))


def collapse_punctuation(text: str) -> str:
    """把连续标点收敛成一个，优先保留表意最强的那个（。 > ！ > ？ > 其他）。"""
    def pick(match: re.Match[str]) -> str:
        run = match.group(0)
        for char in _PUNC_PRIORITY:
            if char in run:
                return char
        return run[0]

    return _PUNC_RUN_RE.sub(pick, text)


def strip_tags(text: str) -> str:
    """剥掉 <|HAPPY|>、<|Applause|>、<|zh|> 等全部特殊标签。"""
    return _TAG_RE.sub("", _SPECIAL_RE.sub("", text))


def normalize_segment_text(text: str) -> str:
    """段落文本规范化：剥标签 -> 收敛连续标点 -> 去掉前导孤立标点。"""
    cleaned = collapse_punctuation(strip_tags(text))
    return cleaned.lstrip(_LEADING_PUNC).strip()


def join_text(head: str, tail: str) -> str:
    """拼接两段文本，收敛交界处的重复标点。"""
    if not head:
        return tail
    if not tail:
        return head
    return collapse_punctuation(f"{head}{tail}")
