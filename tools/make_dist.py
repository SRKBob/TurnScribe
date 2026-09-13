"""打源码发行包：zip + 对方拿到后的三步安装指引。

排除一切本机私有/可再生内容（.venv、temp、模型、输出、本地配置），
包含 assets/fonts（界面字体，5.8MB）。产物落在 dist/（已 gitignore）。

用法：
    .venv\\Scripts\\python.exe tools\\make_dist.py
"""

from __future__ import annotations

import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 打进包里的顶层内容；目录整体包含，文件白名单精确到名
INCLUDE_DIRS = ["assets", "core", "docs", "tools", "ui_theme.py"]
INCLUDE_FILES = [
    "app.py", "config.py", "local_config.example.py",
    "install.bat", "run.bat", "clean.bat",
    "requirements.txt", "README.md", "LICENSE", ".gitignore", ".gitattributes",
]

EXCLUDE_PARTS = {"__pycache__", ".venv", "temp", "output", "models",
                 ".workbuddy", "dist", ".git"}


def _included_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_DIRS:
        p = ROOT / name
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (set(f.parts) & EXCLUDE_PARTS):
                    files.append(f)
        elif p.is_file():
            files.append(p)
    for name in INCLUDE_FILES:
        p = ROOT / name
        if p.is_file():
            files.append(p)
        else:
            print(f"[跳过] {name}（不存在）")
    return files


def main() -> int:
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    out = dist_dir / f"TurnScribe-src-{date.today():%Y%m%d}.zip"

    files = _included_files()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            zf.write(f, Path("TurnScribe") / f.relative_to(ROOT))

    size_mb = out.stat().st_size / 1024**2
    print(f"打包完成：{out}")
    print(f"共 {len(files)} 个文件，{size_mb:.1f}MB")
    print()
    print("对方拿到 zip 后的三步：")
    print("  1. 解压到任意目录")
    print("  2. 双击 install.bat（需要 Python 3.10+ 和网络，全程自动，约 20-40 分钟）")
    print("  3. 双击 run.bat 启动，首屏引导卡会提示还缺什么（如 ffmpeg 的放置位置）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
