"""生成带项目图标的快捷方式（.bat 文件本身无法设置图标）。

在项目根目录和桌面各创建一个「话轮 TurnScribe.lnk」，
双击即启动 run.bat，图标显示为 assets/icon.ico。

用法：
    .venv\\Scripts\\python.exe tools\\make_shortcut.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "icon.ico"
RUN_BAT = ROOT / "run.bat"


def make_shortcut(dest: Path) -> None:
    """用 WScript.Shell COM 创建 .lnk（系统自带能力，无需额外依赖）。"""
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"'{dest}'); "
        f"$s.TargetPath = '{RUN_BAT}'; "
        f"$s.WorkingDirectory = '{ROOT}'; "
        f"$s.IconLocation = '{ICON},0'; "
        "$s.Description = '话轮 TurnScribe · 视频转文字'; "
        "$s.Save()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0 or not dest.exists():
        raise RuntimeError(f"创建快捷方式失败：{dest}\n{result.stderr.strip()}")


def main() -> int:
    if not RUN_BAT.is_file():
        print(f"[错误] 找不到 {RUN_BAT}")
        return 1
    if not ICON.is_file():
        print(f"[错误] 找不到图标 {ICON}")
        return 1

    targets = [ROOT / "话轮 TurnScribe.lnk"]
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        targets.append(desktop / "话轮 TurnScribe.lnk")

    for dest in targets:
        make_shortcut(dest)
        print(f"[OK] {dest}")
    print("\n双击快捷方式即可启动，效果与 run.bat 相同，但带项目图标。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
