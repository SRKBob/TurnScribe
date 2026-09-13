"""离线自检：不加载任何模型，验证合并与渲染逻辑是否正确。

用法：.venv\\Scripts\\python.exe tools\\selftest.py
报告中同时写入 temp/logs/_selftest.log（UTF-8），避免 Windows 控制台编码干扰。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LOG_DIR, SCRATCH_DIR, RenderConfig  # noqa: E402
from core.render import fmt_ts, merge_segments, render_markdown, safe_filename  # noqa: E402
from core.types import MediaMeta, Segment, Turn, speaker_label  # noqa: E402

lines: list[str] = []
failures: list[str] = []


def log(text: str) -> None:
    lines.append(text)
    print(text, flush=True)


def check(label: str, actual: object, expected: object) -> None:
    if actual == expected:
        log(f"[OK] {label}")
    else:
        log(f"[FAIL] {label}\n      期望: {expected!r}\n      实际: {actual!r}")
        failures.append(label)


# --- 基础工具函数 ---
check("fmt_ts 秒级", fmt_ts(65_000), "00:01:05")
check("fmt_ts 跨小时", fmt_ts(3_725_000), "01:02:05")
check("角色命名", speaker_label(0), "角色A")
check("角色命名越界", speaker_label(26), "角色27")
check("文件名清洗", safe_filename('a<b>c:d"e/f'), "abcdef")

# --- 合并规则 ---
# 输入故意乱序，且覆盖三种情况：同人相邻要合并、短插话要并入、跨人要切断。
segments = [
    Segment(start_ms=60_000, end_ms=63_000, text="第二句。", speaker=0),
    Segment(start_ms=0, end_ms=5_000, text="大家好，", speaker=0),
    Segment(start_ms=5_200, end_ms=9_000, text="今天讲三件事。", speaker=0),
    Segment(start_ms=14_000, end_ms=14_500, text="对。", speaker=0),
    Segment(start_ms=20_000, end_ms=23_000, text="第一件事。", speaker=1),
    Segment(start_ms=62_500, end_ms=64_000, text="嗯。", speaker=0),
]

turns = merge_segments(segments, merge_gap_ms=1200, min_turn_ms=800)
check("合并后段落数", len(turns), 3)
check("按时间重排", turns[0].start_ms, 0)
check("同人合并 + 短插话并入", turns[0].text, "大家好，今天讲三件事。对。")
check("合并后结束时间延伸", turns[0].end_ms, 14_500)
check("跨说话人切断", [t.speaker for t in turns], [0, 1, 0])
check("同人相邻片段再合并", turns[2].text, "第二句。嗯。")

# --- 说话人聚类（用合成向量，不加载模型）---
import numpy as np  # noqa: E402

from config import DiarizeConfig  # noqa: E402
from core.diarize import Diarizer  # noqa: E402

rng = np.random.default_rng(20260913)


def unit(vec: np.ndarray) -> np.ndarray:
    return vec / np.linalg.norm(vec)


base_a, base_b = unit(rng.normal(size=192)), unit(rng.normal(size=192))
noisy = [unit(base_a + 0.05 * rng.normal(size=192)) for _ in range(6)]
noisy += [unit(base_b + 0.05 * rng.normal(size=192)) for _ in range(5)]
labels = Diarizer(DiarizeConfig())._cluster(np.vstack(noisy))
check("聚类分出 2 簇", len(set(labels.tolist())), 2)
check("同一声纹归为同簇", len(set(labels[:6].tolist())) == 1 and len(set(labels[6:].tolist())) == 1, True)
check("两簇标号不同", labels[0] != labels[-1], True)

# 相似度极高时应合并为一簇（验证阈值下限方向正确）
same = [unit(base_a + 0.01 * rng.normal(size=192)) for _ in range(8)]
check("同源声纹聚合为 1 簇", len(set(Diarizer(DiarizeConfig())._cluster(np.vstack(same)).tolist())), 1)

# --- 小簇吸收（过分割修复）---
# 背景：独白视频里「对不对？」这类短插入语会被判成独立角色。实测 13 分钟素材
# 被拆成 10 个角色，其中 9 个簇合计不到 10 秒。下面的合成向量复现这个场景。
diar = Diarizer(DiarizeConfig())
rng2 = np.random.default_rng(7)
vec_a, vec_b, vec_c = (unit(rng2.normal(size=192)) for _ in range(3))
main_vecs = [unit(vec_a + 0.05 * rng2.normal(size=192)) for _ in range(10)]
small_b = [unit(vec_b + 0.05 * rng2.normal(size=192)) for _ in range(2)]
small_c = [unit(vec_c + 0.05 * rng2.normal(size=192)) for _ in range(2)]

noise_matrix = np.vstack(main_vecs + small_b + small_c)
noise_durations = [8_000] * 10 + [300, 300] + [250, 250]
raw_labels = diar._cluster(noise_matrix)
check("吸收前确实过分割成 3 簇", len(set(raw_labels.tolist())), 3)
absorbed = diar._absorb_small_clusters(noise_matrix, raw_labels, noise_durations)
check("小簇被吸收，收敛为 1 位说话人", len(set(absorbed.tolist())), 1)
check("吸收后编号从 0 起连续", sorted(set(absorbed.tolist())), [0])

# 反例：第二说话人有足够发言时长时必须保留，不能被误吞
keep_matrix = np.vstack(main_vecs + small_b)
keep_durations = [8_000] * 10 + [7_000, 7_000]
kept = diar._absorb_small_clusters(keep_matrix, diar._cluster(keep_matrix), keep_durations)
check("占比足够的第二说话人保留", len(set(kept.tolist())), 2)

# --- 文本规范化（标点与噪声段修复）---
from core.render import join_text  # noqa: E402
from core.textutil import collapse_punctuation, has_content  # noqa: E402
from core.textutil import normalize_segment_text as normalize_text  # noqa: E402

check("剥掉前导孤立标点", normalize_text("。 好，"), "好，")
check("剥掉问号前缀", normalize_text("？ 是靠钱吗？"), "是靠钱吗？")
check("压掉重复标点", normalize_text("真的。。"), "真的。")
check("收敛尾随标点串", normalize_text("假装看不到。，"), "假装看不到。")
check("收敛重复逗号", normalize_text("别的。，"), "别的。")
check("标点串优先保留句末标点", collapse_punctuation("好的，。"), "好的。")
check("标点串优先保留问号", collapse_punctuation("是这样吗？，"), "是这样吗？")
check("纯标点段判为无内容", has_content("。，"), False)
check("空白段判为无内容", has_content("   "), False)
check("中文判为有内容", has_content("大家好"), True)
check("英文数字判为有内容", has_content("ok 123"), True)
check("拼接压掉交界重复标点", join_text("反感。", "。之前网上"), "反感。之前网上")
check("拼接压掉交界标点串", join_text("看不到。", "，会先修"), "看不到。会先修")
check("正常拼接不受影响", join_text("大家好，", "我是老林"), "大家好，我是老林")

# --- 超长发言分块的时间戳估算 ---
from core.render import _chunk_starts  # noqa: E402

check("单块时间戳不偏移", _chunk_starts(["abcdef"], 7_000, 9_000), [7_000])
check("分块时间戳按字符占比推进", _chunk_starts(["ab", "cd"], 0, 4_000), [0, 2_000])
check("分块时间戳不等分而是按长度", _chunk_starts(["a", "aaa"], 0, 4_000), [0, 1_000])
check("空分块返回空", _chunk_starts([], 0, 1_000), [])

# --- 下载文件标题解析 ---
# 元信息文件是 <video_id>.info.json，与媒体文件 <video_id>.<ext> 同主干。
# 曾经写成「在媒体扩展名后再挂 .info.json」，导致 B 站文稿永远以视频 ID 命名。
import json  # noqa: E402

from core.pipeline import _title_from_download  # noqa: E402

fixture = SCRATCH_DIR / "_selftest_title"
fixture.mkdir(parents=True, exist_ok=True)
media = fixture / "BV123.m4a"
media.write_bytes(b"x")
(media.with_suffix(".info.json")).write_text(
    json.dumps({"title": "真实标题"}, ensure_ascii=False), encoding="utf-8"
)
check("标题取自 info.json", _title_from_download(media), "真实标题")

lonely = fixture / "BV999.m4a"
lonely.write_bytes(b"x")
check("无元信息时回落到视频 ID", _title_from_download(lonely), "BV999")

# --- Markdown 渲染 ---
md = render_markdown(
    MediaMeta(title="测试视频", source="test.mp4", duration_ms=3_725_000),
    turns,
    RenderConfig(style="inline", include_speaker_stats=True),
)
for token in ("# 测试视频", "01:02:05", "**角色A**", "**角色B**", "发言时长统计"):
    check(f"Markdown 含 {token}", token in md, True)

out_dir = LOG_DIR
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "_selftest.md").write_text(md, encoding="utf-8")
log(f"\n样例 Markdown：{out_dir / '_selftest.md'}")

# --- SRT 字幕渲染 ---
from core.srt import build_cues, fmt_srt_ts, render_srt, speaker_prefix_needed, write_srt  # noqa: E402

check("SRT 毫秒时间戳", fmt_srt_ts(3_725_123), "01:02:05,123")
check("SRT 零点时间戳", fmt_srt_ts(0), "00:00:00,000")

srt_turns = [
    Turn(speaker=0, start_ms=0, end_ms=5_000, text="大家好，今天讲三件事。"),
    Turn(speaker=1, start_ms=20_000, end_ms=23_000, text="第一件事是什么？"),
]
srt_multi = render_srt(srt_turns, speaker_prefix=True)
check("SRT 序号从 1 开始", srt_multi.startswith("1\n"), True)
check("SRT 时间轴格式", "00:00:00,000 --> 00:00:05,000" in srt_multi, True)
check("SRT 多人带角色前缀", "角色A：大家好" in srt_multi and "角色B：第一件事是什么？" in srt_multi, True)
check("SRT 结尾换行收束", srt_multi.endswith("\n"), True)

# auto 策略：单人视频不加前缀，多人视频加
check("auto 前缀-多人加", speaker_prefix_needed(srt_turns), True)
check("auto 前缀-单人不加", speaker_prefix_needed(srt_turns[:1]), False)
srt_single = render_srt(srt_turns[:1], speaker_prefix=speaker_prefix_needed(srt_turns[:1]))
check("单人字幕无前缀", "角色A：" not in srt_single and "大家好" in srt_single, True)

# 长句切分：每条字幕的结束时间应顶到下一条开始（或段尾），且不早于开始时间
long_turn = Turn(speaker=0, start_ms=10_000, end_ms=30_000,
                 text="第一句话。" * 12)  # 72 字，必然切多条
cues = build_cues([long_turn], speaker_prefix=False)
check("长句切成多条字幕", len(cues) > 1, True)
check("字幕时间单调递增",
      all(cues[i].start_ms < cues[i + 1].start_ms for i in range(len(cues) - 1)), True)
check("末条字幕结束于段尾", cues[-1].end_ms, 30_000)
check("字幕时长不低于下限", all(c.end_ms - c.start_ms >= 600 for c in cues), True)

srt_text = render_srt([long_turn], speaker_prefix=False)
(out_dir / "_selftest.srt").write_text(srt_text, encoding="utf-8-sig", newline="\r\n")
log(f"样例 SRT：{out_dir / '_selftest.srt'}")

summary = "自检通过" if not failures else f"自检未通过（{len(failures)} 项失败）"
log(summary)
lines.append(f"exit={1 if failures else 0}")
(out_dir / "_selftest.log").write_text("\n".join(lines) + "\n", encoding="utf-8")

raise SystemExit(1 if failures else 0)
