"""话轮 TurnScribe · 主题对比度自检（离线，无依赖）。

校验每套主题的关键色彩组合是否满足 WCAG 2.1：
  - 按钮文字 / 按钮底色      >= 4.5  (AA 正文)
  - 正文 / 页面底色          >= 7.0  (AAA 正文，长文阅读)
  - 正文 / 卡片底色          >= 7.0
  - 次要文字 / 卡片底色      >= 4.5
  - 三级文字 / 卡片底色      >= 3.0  (占位、标签)
  - 字段底 / 卡片底         需可分辨（RGB 平均差 >= 4）
  - 描边 / 卡片底           需可分辨（RGB 平均差 >= 6）

用法：
    .venv\\Scripts\\python.exe tools\\themecheck.py
退出码 0 = 全部通过，1 = 有项不达标。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui_theme import PALETTES, _variables  # noqa: E402


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(value: str) -> float:
    r, g, b = _rgb(value)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def delta(a: str, b: str) -> float:
    """平均通道差，判断「两种颜色能否看出区别」。"""
    ca, cb = _rgb(a), _rgb(b)
    return sum(abs(ca[i] - cb[i]) for i in range(3)) / 3.0


def main() -> int:
    failures: list[str] = []
    print(f"主题对比度自检 · 共 {len(PALETTES)} 套\n")

    for key, p in PALETTES.items():
        v = _variables(key)
        surface = v["ts-surface"]
        bg = v["body-background-fill"]
        text = v["ts-text"]
        muted = v["ts-muted"]
        muted2 = v["ts-muted-2"]
        field = v["ts-field"]
        border = v["ts-border"]
        primary = v["ts-primary"]
        on_primary = v["ts-on-primary"]

        checks = [
            ("按钮文字 / 按钮底", on_primary, primary, 4.5),
            ("正文 / 页面底", text, bg, 7.0),
            ("正文 / 卡片底", text, surface, 7.0),
            ("次要文字 / 卡片底", muted, surface, 4.5),
            ("三级文字 / 卡片底", muted2, surface, 3.0),
            ("字段底 / 卡片底(可分辨)", field, surface, 4.0),
            ("描边 / 卡片底(可分辨)", border, surface, 6.0),
            ("按钮底 / 页面底(可分辨)", primary, bg, 12.0),
        ]

        print(f"[{key}] {p['label']}  ·  {p['mode']}  ·  {p['note']}")
        for label, a, b, need in checks:
            if label.endswith("(可分辨)"):
                got = delta(a, b)
                ok = got >= need
                print(f"   {'PASS' if ok else 'FAIL'}  {label:26s} Δ{got:6.1f} (需 >= {need})")
            else:
                got = contrast(a, b)
                ok = got >= need
                print(f"   {'PASS' if ok else 'FAIL'}  {label:26s} {got:5.2f}:1 (需 >= {need})")
            if not ok:
                failures.append(f"{key} · {label} = {got:.2f} (需 {need})")
        print()

    if failures:
        print(f"不达标 {len(failures)} 项：")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
