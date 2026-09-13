"""环境自检：安装依赖后跑一次，确认模型与 GPU 都就绪。

用法：
    .venv\\Scripts\\python.exe tools\\check_env.py            # 只检查
    .venv\\Scripts\\python.exe tools\\check_env.py --download # 顺便预下载模型
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MODEL_DIR, find_ffmpeg, ensure_dirs  # noqa: E402


def check_ffmpeg() -> bool:
    try:
        print(f"[OK] ffmpeg      {find_ffmpeg()}")
        return True
    except FileNotFoundError as exc:
        print(f"[FAIL] ffmpeg    {exc}")
        return False


def check_imports() -> bool:
    ok = True
    for module in ("torch", "torchaudio", "funasr", "gradio", "yt_dlp"):
        try:
            mod = __import__(module)
            print(f"[OK] {module:<11} {getattr(mod, '__version__', 'unknown')}")
        except ImportError:
            print(f"[FAIL] {module:<11} 未安装")
            ok = False
    return ok


def check_cuda() -> bool:
    try:
        import torch
    except ImportError:
        return False
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[OK] CUDA        {name} / {total:.1f}GB")
        return True
    print("[FAIL] CUDA      不可用，将退回 CPU（3 小时视频约需 40-90 分钟）")
    return False


def download_models() -> None:
    """预下载全部权重，之后即可离线运行。"""
    from funasr import AutoModel

    ensure_dirs()
    for label, kwargs in (
        ("SenseVoiceSmall", {"model": "iic/SenseVoiceSmall", "trust_remote_code": True}),
        ("FSMN-VAD", {"model": "fsmn-vad"}),
        ("CT-Punc", {"model": "ct-punc"}),
        ("CAM++", {"model": "cam++"}),
    ):
        print(f"[..] 下载 {label} ...", flush=True)
        AutoModel(**kwargs)
        print(f"[OK] {label}")
    print(f"\n模型缓存目录：{MODEL_DIR}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="预下载模型")
    args = parser.parse_args()

    results = [check_ffmpeg(), check_imports(), check_cuda()]
    if args.download and all(results[:2]):
        download_models()

    healthy = results[0] and results[1]
    print("\n环境检查" + ("通过" if healthy else "未通过"))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
