"""话轮 TurnScribe · 界面设计规范生成器。

从 `ui_theme.py` 的 PALETTES 与 `_variables()` 导出 `docs/THEMES.md`，
保证「文档里的色值」与「界面实际用的色值」永远一致。

改过配色后重跑：
    .venv\\Scripts\\python.exe tools\\gen_theme_doc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui_theme import DEFAULT_THEME, PALETTES, _variables  # noqa: E402

OUT = ROOT / "docs" / "THEMES.md"

BASE_KEYS = [
    ("primary", "强调色", "按钮底、选中态、滑块"),
    ("primary_deep", "强调色 · 深", "按钮 hover / 按下"),
    ("soft", "强调浅底", "选中背景、focus 光晕"),
    ("on_primary", "强调底上的字", "主按钮文字，需 >= 4.5:1"),
    ("swatch", "色点", "保留字段（调色盘图标直接用强调色，本键暂未使用）"),
    ("bg", "页面底", "最底层背景"),
    ("surface", "卡片底", "卡片、预览框"),
    ("surface2", "次级底", "代码块、面板"),
    ("surface3", "三级底 / 悬停", "hover 态"),
    ("field", "字段底", "输入框、下拉（需与卡片底可分辨）"),
    ("text", "正文", "需 >= 7:1"),
    ("muted", "次要文字", "需 >= 4.5:1"),
    ("muted2", "三级文字", "占位、标签，需 >= 3:1"),
    ("border", "描边", "卡片、分隔线"),
]

DERIVED_KEYS = [
    ("ts-field", "字段底（实际生效值）"),
    ("ts-border-strong", "描边 · 强"),
    ("primary-300", "色阶 300"),
    ("primary-700", "色阶 700"),
    ("neutral-300", "中性阶 300"),
    ("neutral-600", "中性阶 600"),
    ("ts-scroll", "滚动条"),
]


# ---- 对比度工具（与 tools/themecheck.py 同一套算法） ----
def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(value: str) -> float:
    r, g, b = _rgb(value)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def delta(a: str, b: str) -> float:
    ca, cb = _rgb(a), _rgb(b)
    return sum(abs(ca[i] - cb[i]) for i in range(3)) / 3.0


def table(rows, header) -> str:
    out = [f"| {header[0]} | {header[1]} | {header[2]} |", "|---|---|---|"]
    for a, b, c in rows:
        out.append(f"| {a} | `{b}` | {c} |")
    return "\n".join(out)


def main() -> int:
    L: list[str] = []
    add = L.append

    add("# 界面设计规范 · THEMES")
    add("")
    add(
        "> 本文由 `tools/gen_theme_doc.py` 从 `ui_theme.py` 自动导出，色值即界面实际使用的值。"
    )
    add("> 改色后请重跑：`.venv\\Scripts\\python.exe tools\\gen_theme_doc.py`")
    add("")
    add(f"共 **{len(PALETTES)} 套主题**，默认 `{DEFAULT_THEME}`（{PALETTES[DEFAULT_THEME]['label']}）。")
    add("")

    # ---------- 1 设计原则 ----------
    add("## 1. 设计原则")
    add("")
    add(
        "1. **单一强调色。** 每套主题只有一个强调色，只出现在主按钮、选中态、滑块、"
        "链接与焦点环上；其余全部交给中性灰阶——这是「干净」的来源。"
    )
    add(
        "2. **填充式字段，而非描边框。** 输入框 / 下拉用比卡片暗（浅色主题）或亮"
        "（暗色主题）一档的底色来区分，描边只作辅助。Gradio 的控件容器默认就靠底色"
        "区分，若字段底与卡片底同色，下拉框会直接「消失」。"
    )
    add(
        "3. **极轻阴影。** 浅色主题用 `rgb(24 32 32 / 3%)` 加一层大范围低透明投影；"
        "暗色主题换纯黑阴影，不靠发光。"
    )
    add("4. **统一圆角。** 卡片 16px、字段 10px、按钮 12/10/8px、调色盘按钮 10px。")
    add(
        "5. **零网络字体。** 只用系统字体栈，断网也是这个样子。"
    )
    add(
        "6. **对比度是硬约束。** 每套主题必须通过 `tools/themecheck.py`："
        "正文 / 底 ≥ 7:1、次要文字 ≥ 4.5:1、三级文字 ≥ 3:1、按钮文字 ≥ 4.5:1。"
    )
    add("")

    # ---------- 2 总览 ----------
    add("## 2. 主题总览")
    add("")
    add("| 键 | 名称 | 模式 | 提取来源 | 强调色 | 主按钮对比度 |")
    add("|---|---|---|---|---|---|")
    for key, p in PALETTES.items():
        v = _variables(key)
        c = ratio(v["ts-on-primary"], v["ts-primary"])
        add(
            f"| `{key}` | **{p['label']}** | {p['mode']} | {p['note']} | "
            f"`{p['primary']}` | `{v['ts-on-primary']}` on `{p['primary']}` = {c:.2f}:1 |"
        )
    add("")
    add("主按钮文字色各主题不同：`amber`（桂黄暖）用深色字，其余用白字。这是对比度决定的，不要改。")
    add("")

    # ---------- 3 色板 ----------
    add("## 3. 主题色板")
    add("")
    for i, (key, p) in enumerate(PALETTES.items(), start=1):
        v = _variables(key)
        add(f"### 3.{i} {p['label']}（`{key}`，{p['mode']}）")
        add("")
        add(f"来源：{p['note']}")
        add("")
        rows = []
        for k, label, use in BASE_KEYS:
            if k in p:
                value, note = p[k], use
            elif k == "field":
                # field 是可选键：未显式声明时由 _variables() 按明暗模式推导
                value, note = v["ts-field"], use + "（未显式声明，按模式推导）"
            else:
                value, note = "—", use
            rows.append((f"{label} `{k}`", value, note))
        if "accent" in p:
            rows.append(("链接 / 焦点环 `accent`", p["accent"], "主题自带（不等同强调色）"))
        else:
            rows.append(("链接 / 焦点环 `accent`", p["primary"], "沿用强调色"))
        add(table(rows, ("角色", "色值", "用途")))
        add("")
        add(table([(f"{lab} `--{k}`", v[k], "") for k, lab in DERIVED_KEYS], ("派生变量", "实际色值", "")))
        add("")
        add(
            f"实测：正文 / 页面底 {ratio(v['ts-text'], v['body-background-fill']):.2f}:1，"
            f"正文 / 卡片底 {ratio(v['ts-text'], v['ts-surface']):.2f}:1，"
            f"次要文字 / 卡片底 {ratio(v['ts-muted'], v['ts-surface']):.2f}:1，"
            f"三级文字 / 卡片底 {ratio(v['ts-muted-2'], v['ts-surface']):.2f}:1，"
            f"字段底与卡片底 Δ{delta(v['ts-field'], v['ts-surface']):.1f}。"
        )
        add("")

    # ---------- 4 组件规范 ----------
    add("## 4. 组件样式规范")
    add("")
    add("### 4.1 圆角")
    add("")
    add("| 对象 | 值 |")
    add("|---|---|")
    add("| 卡片 / 区块容器 | 16px |")
    add("| 输入框 / 下拉 | 10px |")
    add("| 主按钮 | 12px |")
    add("| 次级按钮 | 10px |")
    add("| 小按钮 | 8px |")
    add("| 调色盘按钮 | 10px |")
    add("")
    add("### 4.2 主按钮")
    add("")
    add(
        "高度 48px、字号 15px、字重 600、字距 0.03em。底色 `primary`，hover `primary_deep`，"
        "无边框，阴影从 `0 1px 2px` 抬到 `0 2px 8~10px`。点按时阴影归零，靠位移反馈。"
    )
    add("")
    add("### 4.3 输入字段 / 下拉")
    add("")
    add(
        "底色 `field`，描边 `field_border`（字段底再深 / 亮一档），focus 时描边换成强调色，"
        "外加 3px 半透明光晕（浅色 16%、暗色 24% 不透明度）。圆角 10px，无内阴影。"
    )
    add("")
    add("| 主题 | 字段底 | 卡片底 | 通道平均差 |")
    add("|---|---|---|---|")
    for key, p in PALETTES.items():
        v = _variables(key)
        add(f"| {p['label']} | `{v['ts-field']}` | `{v['ts-surface']}` | Δ{delta(v['ts-field'], v['ts-surface']):.1f} |")
    add("")
    add("### 4.4 卡片")
    add("")
    add(
        "圆角 16px，1px 描边用 `border`，底色 `surface`，阴影 `ts-shadow-card`。"
        "卡片内部不再套第二层框，字段直接浮在卡片底上。"
    )
    add("")
    add("### 4.5 主题选择器（调色盘下拉）")
    add("")
    add(
        "页头右侧一个 44×38px 的调色盘图标按钮（`gr.Dropdown` 伪装：选中值文字隐藏，"
        "Gradio 自带箭头换成 SVG 调色盘图标，用 CSS `mask` 上色，颜色取当前主题的强调色——"
        "换主题时图标颜色跟着变）。点击弹出下拉列表：面板圆角 12px、卡片底 + 描边 + 卡片阴影，"
        "选中项用 `soft` 底加粗高亮。选择结果写入项目根目录 `.ui_theme.json`（已 gitignore），"
        "**重启 / 刷新后自动恢复**。切换本身由 Python 回调替换 `gr.HTML` 里的 `<style>` 完成，"
        "**不依赖任何前端 JS**。"
    )
    add("")
    add("### 4.6 字体")
    add("")
    add("| 用途 | 字体栈 |")
    add("|---|---|")
    add("| 正文 | `system-ui` → `PingFang SC` → `Microsoft YaHei UI` → `sans-serif` |")
    add("| 日志 / 代码 | `Cascadia Mono` → `JetBrains Mono` → `Consolas` → `monospace` |")
    add("")
    add("### 4.7 滚动条")
    add("")
    add("宽 8px，滑块用 `ts-scroll`（浅色主题黑 14%、暗色主题白 16%），悬停加深，轨道透明。")
    add("")

    # ---------- 5 派生规则 ----------
    add("## 5. 派生规则")
    add("")
    add("每套主题只声明约 13 个基准色，其余 100 多个 Gradio 语义变量由 `_variables()` 推导：")
    add("")
    add("| 变量 | 浅色主题 | 暗色主题 |")
    add("|---|---|---|")
    add("| `primary-50` | `soft` 向白外推 55% | `soft` 向页底外推 55% |")
    add("| `primary-200 / 300 / 400` | `soft` → `primary` 插值 24% / 48% / 74% | 同左 |")
    add("| `primary-700 ~ 950` | `primary_deep` 向黑外推 14/28/44/60% | 向白外推 |")
    add("| `neutral-50 → 950` | 最浅 → 最深 | 最暗 → 最亮 |")
    add("| `field` | 页底压暗 3% | 页底提亮 14%，或用主题自带的 `field` |")
    add("| `input-border-color` | 字段底压暗 7% | 字段底提亮 12% |")
    add("| 卡片阴影 | `rgb(24 32 32 / 3%)` | `rgb(0 0 0 / 55%)` |")
    add("")

    # ---------- 6 新增主题 ----------
    add("## 6. 如何新增一套主题")
    add("")
    add("1. 在 `ui_theme.py` 的 `PALETTES` 里加一项，填全 13 个基准色（`mode` 必填）。")
    add("2. 跑 `.venv\\Scripts\\python.exe tools\\themecheck.py`，把不达标的色改到达标为止。")
    add("3. 跑 `.venv\\Scripts\\python.exe tools\\uicheck.py` 确认界面能正常构建。")
    add("4. 跑 `.venv\\Scripts\\python.exe tools\\gen_theme_doc.py` 刷新本文。")
    add("5. 下拉列表会自动多出一项，`app.py` 不用改。")
    add("")

    text = "\n".join(L) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"written {OUT} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
