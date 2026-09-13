"""命令行批量转写入口。与 GUI 共用同一条 pipeline。

用法：
    .venv\\Scripts\\python.exe tools\\run.py <本地文件或链接> [更多来源...] [-o 输出目录]

示例：
    python tools\\run.py "D:\\v\\a.mp4" https://www.bilibili.com/video/BV191GR6VE1i/
    python tools\\run.py "D:\\v\\a.mp4" -o "D:\\我的文稿" --style block --speaker-stats
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import CONFIG, OUTPUT_DIR  # noqa: E402
from core.media import ffmpeg_available  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="视频语音转文字 → Markdown（带说话人区分）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("sources", nargs="+", help="本地媒体路径或视频链接，可多个")
    p.add_argument(
        "-o", "--out",
        default=str(OUTPUT_DIR),
        help=f"输出目录（默认 {OUTPUT_DIR}）",
    )
    p.add_argument("--device", default="auto", choices=["auto", "cuda:0", "cpu"])
    p.add_argument("--language", default="auto", choices=["auto", "zh", "yue", "en", "ja", "ko"])
    p.add_argument("--style", default="inline", choices=["inline", "block"],
                   help="inline=「角色A：内容」；block=角色名独立成行")
    p.add_argument("--no-timestamp", action="store_true", help="不输出每段时间戳")
    p.add_argument("--speaker-stats", action="store_true", help="附各角色发言时长统计")
    p.add_argument("--threshold", type=float, default=0.55,
                   help="说话人聚类阈值，越小越倾向合并为同一人")
    p.add_argument("--no-resume", action="store_true", help="忽略缓存，强制重新识别")
    p.add_argument("--keep-audio", action="store_true", help="保留抽取的音轨")
    return p


def main() -> int:
    args = build_parser().parse_args()

    ok, detail = ffmpeg_available()
    if not ok:
        print(f"[警告] {detail}")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = replace(
        CONFIG,
        asr=replace(CONFIG.asr, device=args.device, language=args.language),
        diarize=replace(CONFIG.diarize, cluster_threshold=args.threshold),
        render=replace(
            CONFIG.render,
            style=args.style,
            with_timestamp=not args.no_timestamp,
            include_speaker_stats=args.speaker_stats,
        ),
        resume=not args.no_resume,
        keep_audio=args.keep_audio,
    )

    pipeline = Pipeline(cfg)  # 模型只加载一次，批量复用
    print(f"输出目录：{out_dir}")
    print(f"共 {len(args.sources)} 个来源\n")

    done: list[Path] = []
    failed: list[tuple[str, str]] = []

    for index, source in enumerate(args.sources, start=1):
        shown = Path(source).name if not source.lower().startswith("http") else source
        print(f"[{index}/{len(args.sources)}] {shown}")

        def progress(ratio: float, message: str) -> None:
            print(f"    {ratio * 100:5.1f}%  {message}", flush=True)

        try:
            result = pipeline.process(source, out_dir=out_dir, progress=progress)
            done.append(result.md_path)
            print(f"    -> {result.md_path}")
            print(f"       {result.summary}")
            for warning in result.warnings:
                print(f"       注意：{warning}")
        except Exception as exc:  # 单个失败不中断整批
            failed.append((source, str(exc)))
            print(f"    !! 失败：{exc}")
        print()

    print(f"完成 {len(done)} 个，失败 {len(failed)} 个")
    for path in done:
        print(f"  OK  {path}")
    for source, err in failed:
        print(f"  NG  {source}  ->  {err}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
