"""端到端集成测试：用真实音频跑完整链路。

构造方式：取一段公开的中文测试音频，用 ffmpeg 升调生成「第二个人的声音」，
拼成 A-B-A 两说话人对话，包成 MP4（顺带验证视频抽音轨），再跑完整 Pipeline。

用法：.venv\\Scripts\\python.exe tools\\e2e_test.py
"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import CONFIG, LOG_DIR, SCRATCH_DIR, find_ffmpeg  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402
from core.render import fmt_ts  # noqa: E402

WORK = SCRATCH_DIR / "_e2e"
# 测试必须每次真跑：关闭断点续传，否则会命中旧缓存而测不出改动效果
TEST_CONFIG = replace(CONFIG, resume=False, keep_audio=False)
SAMPLE_URLS = (
    "https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav",
    "https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/example/zh.mp3",
)

lines: list[str] = []


def write_report() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "_e2e.log").write_text("\n".join(lines), encoding="utf-8")


def log(text: str) -> None:
    lines.append(text)
    print(text, flush=True)
    # 实时落盘，便于后台运行时观察进度
    write_report()


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore")[-800:])


def fetch_sample() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    target = WORK / "sample.wav"
    if target.exists():
        return target
    for url in SAMPLE_URLS:
        try:
            log(f"下载测试音频：{url}")
            with urllib.request.urlopen(url, timeout=60) as resp:
                target.write_bytes(resp.read())
            return target
        except Exception as exc:
            log(f"  失败：{exc}")
    raise RuntimeError("测试音频全部下载失败，请检查网络")


def build_two_speaker_mp4(sample: Path) -> Path:
    """A（原声）- B（升调）- A（原声），包成 MP4。"""
    ffmpeg = find_ffmpeg()
    voice_b = WORK / "voice_b.wav"
    merged = WORK / "merged.wav"
    video = WORK / "two_speakers.mp4"
    if video.exists():
        return video

    # 升调 18% 造出第二个音色，保持时长不变
    run([ffmpeg, "-y", "-loglevel", "error", "-i", str(sample), "-af",
         "asetrate=16000*1.18,aresample=16000,atempo=1/1.18", str(voice_b)])

    listing = WORK / "concat.txt"
    listing.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in (sample, voice_b, sample)),
        encoding="utf-8",
    )
    run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(merged)])

    # 加一条黑色视频轨，验证「MP4 抽音轨」这条路径
    run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "color=c=black:s=320x240:r=10", "-i", str(merged),
         "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "aac", str(video)])
    return video


def main() -> int:
    try:
        sample = fetch_sample()
        mp4 = build_two_speaker_mp4(sample)
        log(f"测试素材：{mp4}（{mp4.stat().st_size / 1024:.0f} KB）")
    except Exception as exc:
        log(f"[FAIL] 素材准备失败：{exc}")
        write_report()
        return 1

    log("\n=== 开始跑完整链路（首次运行需下载模型，约 1GB）===")
    pipeline = Pipeline(TEST_CONFIG)
    try:
        result = pipeline.process(
            str(mp4),
            out_dir=LOG_DIR,
            progress=lambda ratio, msg: log(f"  {ratio * 100:5.1f}%  {msg}"),
        )
    except Exception as exc:
        import traceback

        log(f"[FAIL] 链路异常：{exc}")
        log(traceback.format_exc())
        write_report()
        return 1

    log("\n=== 结果 ===")
    log(f"文件：{result.md_path}")
    log(f"时长：{fmt_ts(result.duration_ms)}")
    log(f"说话人数：{result.speaker_count}")
    log(f"段落数：{result.turn_count}")
    log(f"耗时：{result.elapsed_s:.1f}s")
    for warning in result.warnings:
        log(f"警告：{warning}")

    log("\n=== 段落明细 ===")
    for turn in result.turns:
        log(f"[角色{turn.speaker}] {fmt_ts(turn.start_ms)}-{fmt_ts(turn.end_ms)}  {turn.text[:60]}")

    ok = result.speaker_count == 2 and result.turn_count >= 2
    log("\n端到端测试" + ("通过：成功分出 2 位说话人" if ok else "未达预期（期望 2 位说话人）"))
    write_report()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
