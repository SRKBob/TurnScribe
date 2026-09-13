"""话轮 TurnScribe · 界面主题与样式。

设计目标
--------
简洁、干净、克制的「高级感」——浅色底 / 深色底、克制的强调色、大量留白、
卡片式分区、统一圆角、极轻阴影。不做渐变堆砌，不加载任何网络字体。

主题构成
--------
共 5 套，分两组：

* **素材色组（3 套，浅色）**——取自项目附带的中国传统色卡素材：
  - `qiubo`  秋波蓝：冷蓝，干净利落
  - `bamboo` 竹月青：青绿，清爽
  - `amber`  桂黄暖：暖米底 + 琥珀强调，唯一使用「深色字按钮」的主题
* **WorkBuddy 组（2 套，明暗成对）**——对齐 WorkBuddy 客户端设计语言：
  - `wb_light` / `wb_dark`：近乎无彩色的中性灰阶，品牌色在亮色下为近黑、
    暗色下为近白，唯一功能色是蓝色焦点环 / 链接。这套配色是「干净」的来源。

换肤机制
--------
Gradio 6 把整主题渲染成一堆 CSS 变量，定义在 `:root` 上（见
`gradio/themes/base.py::_get_theme_css`，它同时输出 `:root {}` 与
`:root.dark, :root .dark {}` 两段）。本模块的做法：

1. `theme_css(name)` 生成一段 `<style>:root:root, ... { --xxx: ...; }</style>`，
   用双 `:root` 提高特异性，保证压过 Gradio 自己的定义（不依赖注入顺序）。
2. 这段样式塞进一个 `gr.HTML` 组件；主题选择器变化时由 Python 回调替换其内容，
   浏览器重算变量 → 全界面即时换色。**不需要任何前端 JS。**
3. 明色主题与暗色主题**都写在同一条规则里**，并同时覆盖 `.dark`——这样
   Gradio 自带的深色开关与系统 `prefers-color-scheme` 都不会把调色板改掉。
   `color-scheme` 也由这里下发，让原生控件（下拉、滚动条）跟随主题。

因此 `gradio_theme()` 只负责字体 / 圆角 / 中性色相的兜底，真正的配色全部由
变量块接管。

色值约束
--------
所有色值都过 `tools/themecheck.py` 的 WCAG 校验（离线、秒级）：
按钮文字 / 按钮底 >= 4.5，正文 / 底 >= 7.0，次要文字 >= 4.5，三级文字 >= 3.0，
且字段底与卡片底、描边与卡片底必须「可分辨」（避免输入框在卡片上消失）。
"""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr

DEFAULT_THEME = "qiubo"

ROOT = Path(__file__).resolve().parent
# 主题偏好持久化文件（gitignore）：记录用户上次选的主题，重启 / 刷新后仍生效
PREF_FILE = ROOT / ".ui_theme.json"

# 内置字体目录：MiSans（本地分片 woff2，随用随取，不依赖网络）
FONTS_DIR = ROOT / "assets" / "fonts" / "misans"

# --------------------------------------------------------------------------
# 调色板
# --------------------------------------------------------------------------
# 每套主题只声明约 13 个基准色，其余 100 多个 Gradio 语义变量由 _variables() 推导。
#
#   mode        : "light" | "dark" —— 决定底色/文字的明暗方向与色阶走向
#   primary     : 强调色（按钮底、选中态、滑块）
#   primary_deep: 强调色 hover / 按下态
#   soft        : 强调色的浅色底（选中背景、focus 光晕）
#   on_primary  : 压在 primary 上的文字色（需保证对比度 >= 4.5）
#   accent      : 链接 / 焦点环颜色（默认同 primary）
#   swatch      : 主题选择器上的小色点（不代表 primary，只用来「一眼可辨」）
#   bg          : 页面底色
#   surface     : 卡片底色
#   surface2    : 次级面板（预览框、代码块）
#   surface3    : 三级 / 悬停底
#   field       : 输入字段底（可选；不写则按模式推导，必须与 surface 可分辨）
#   text        : 正文
#   muted       : 次要文字
#   muted2      : 三级文字（占位、标签）
#   border      : 描边
PALETTES: dict[str, dict[str, str]] = {
    # ---------------- 素材色组：秋波蓝 ----------------
    # 素材原色 秋波藍 #8ABCD1 太浅（白字仅 2.06:1），无法直接做按钮底，
    # 故主色压深到 #4A7A96（白字 4.65:1 达标），原色转作色点，浅调气质靠 soft 保留。
    "qiubo": {
        "label": "秋波蓝",
        "mode": "light",
        "note": "秋波藍 #8ABCD1 · 太平洋海岸 #5B84B1",
        "primary": "#4A7A96",
        "primary_deep": "#3A647C",
        "soft": "#E6F0F6",
        "on_primary": "#FFFFFF",
        "swatch": "#8ABCD1",
        "bg": "#F5F9FC",
        "surface": "#FFFFFF",
        "surface2": "#FAFCFE",
        "surface3": "#EEF5FA",
        "text": "#1D2D37",
        "muted": "#5E7886",
        "muted2": "#7A909B",
        "border": "#DCE8EF",
    },
    # ---------------- 素材色组：竹月青 ----------------
    # 素材原色 竹色 #1BA784 白字仅 3.04:1（仅够大字），压深到 #157A63 后达标。
    "bamboo": {
        "label": "竹月青",
        "mode": "light",
        "note": "竹色 #1BA784 压深 · 若竹 #6CA984 · 淺松綠 #84C0BE",
        "primary": "#157A63",
        "primary_deep": "#0E6350",
        "soft": "#E3F3EC",
        "on_primary": "#FFFFFF",
        "swatch": "#1BA784",
        "bg": "#F5FAF8",
        "surface": "#FFFFFF",
        "surface2": "#FAFDFB",
        "surface3": "#EEF7F3",
        "text": "#14302A",
        "muted": "#587C71",
        "muted2": "#6E9385",
        "border": "#D8EAE2",
    },
    # ---------------- 素材色组：桂黄暖 ----------------
    # 全部素材里最「暖」的一支。琥珀底配深色字（黑字 7.2:1），
    # 底色取自 雪柳 #FFFBF8 / 血牙 #E9D1B5 / 米色 #DBCCB1 的暖米层次。
    "amber": {
        "label": "桂黄暖",
        "mode": "light",
        "note": "桂黄 #EDA01F · 血牙 #E9D1B5 · 雪柳 #FFFBF8",
        "primary": "#E5A21E",
        "primary_deep": "#C6860C",
        "soft": "#FBF0D9",
        "on_primary": "#2A2114",
        "swatch": "#EDA01F",
        "bg": "#FBF7F0",
        "surface": "#FFFDFA",
        "surface2": "#FAF6EE",
        "surface3": "#F6EFE3",
        "text": "#33291B",
        "muted": "#7D6C54",
        "muted2": "#8A7B63",
        "border": "#EBDFCC",
    },
    # ---------------- WorkBuddy 组：亮 ----------------
    # 取自 WorkBuddy 客户端 CSS 变量（--color-* 系列）的亮色取值，逐一照搬：
    # bg #FEFEFE / card #FFFFFF / secondary #F5F5F7 / tertiary #F3F3F3 /
    # text #1A1A1A / secondary #5C5C5C / tertiary #7C7C82 / border #DCDEE3 /
    # input-border #E5E7EB / focus & link #1677FF
    "wb_light": {
        "label": "WorkBuddy 亮",
        "mode": "light",
        "note": "WorkBuddy 客户端亮色 token",
        "primary": "#1A1A1A",
        "primary_deep": "#000000",
        "soft": "#F0F0F2",
        "on_primary": "#FFFFFF",
        "accent": "#1677FF",
        "swatch": "#1A1A1A",
        "bg": "#FEFEFE",
        "surface": "#FFFFFF",
        "surface2": "#F5F5F7",
        "surface3": "#F3F3F3",
        "field": "#F5F5F7",
        "text": "#1A1A1A",
        "muted": "#5C5C5C",
        "muted2": "#7C7C82",
        "border": "#DCDEE3",
    },
    # ---------------- WorkBuddy 组：暗 ----------------
    # bg #000000 / card #1A1A1A / secondary #1C1C1E / tertiary #242424 /
    # hover #2A2A2A / text #E5E5E5 / secondary #A3A3A3 / tertiary #8E8E93 /
    # border #2E2E33 / focus #60A5FA。品牌色翻转为近白，按钮为「白底黑字」。
    # 注意：字段底必须比卡片亮一档，否则输入框会「消失」（与浅色主题同理）。
    "wb_dark": {
        "label": "WorkBuddy 暗",
        "mode": "dark",
        "note": "WorkBuddy 客户端暗色 token",
        "primary": "#E5E5E5",
        "primary_deep": "#FFFFFF",
        "soft": "#262628",
        "on_primary": "#1A1A1A",
        "accent": "#60A5FA",
        "swatch": "#E5E5E5",
        "bg": "#000000",
        "surface": "#1A1A1A",
        "surface2": "#1C1C1E",
        "surface3": "#2A2A2A",
        "field": "#242424",
        "text": "#E5E5E5",
        "muted": "#A3A3A3",
        "muted2": "#8E8E93",
        "border": "#2E2E33",
    },
}

FONT_STACK = (
    '"MiSans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", '
    '"PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif'
)
FONT_MONO = '"Cascadia Mono", "JetBrains Mono", Consolas, "Courier New", ui-monospace, monospace'

# MiSans 官方权值 -> 界面使用的 CSS 权值（仅内置这三个，覆盖 400/500/600）
_MISANS_WEIGHTS = {"Regular": 400, "Medium": 500, "Demibold": 600}


def font_face_css() -> str:
    """生成 MiSans 的 @font-face（分片 + unicode-range，浏览器只取用到的分片）。

    字体目录缺失（如未随仓库分发）时返回空串，整体优雅回退到系统字体栈。
    """
    if not FONTS_DIR.is_dir():
        return ""
    base = "/gradio_api/file=" + FONTS_DIR.as_posix()
    blocks: list[str] = []
    for weight_name, css_weight in _MISANS_WEIGHTS.items():
        css_file = FONTS_DIR / f"MiSans-{weight_name}.min.css"
        if not css_file.is_file():
            continue
        try:
            text = css_file.read_text(encoding="utf-8")
        except BaseException:
            continue
        # MiSans 自带权值号(330/380/450)归一到常用 400/500/600
        text = text.replace("font-weight:330", f"font-weight:{css_weight}")
        text = text.replace("font-weight:380", f"font-weight:{css_weight}")
        text = text.replace("font-weight:450", f"font-weight:{css_weight}")
        text = text.replace("url('", f"url('{base}/")
        blocks.append(text)
    return "\n".join(blocks)


def theme_choices() -> list[tuple[str, str]]:
    """给 gr.Dropdown / gr.Radio 用的 [(显示名, 键)]。"""
    return [(p["label"], key) for key, p in PALETTES.items()]


# --------------------------------------------------------------------------
# 主题偏好持久化：写入项目根目录 .ui_theme.json（已 gitignore）
# 读写均为尽力而为——偏好文件坏了绝不能拖垮界面启动
# --------------------------------------------------------------------------
def load_theme() -> str:
    """读取上次保存的主题键；无效 / 缺失 / 损坏一律回退默认主题。"""
    try:
        data = json.loads(PREF_FILE.read_text(encoding="utf-8"))
        name = data.get("theme")
        if isinstance(name, str) and name in PALETTES:
            return name
    except BaseException:  # 文件不存在 / JSON 损坏 / 沙箱拦截，全部兜住
        pass
    return DEFAULT_THEME


def save_theme(name: str) -> None:
    """保存主题键；失败静默（丢失偏好只影响下次启动的默认值）。"""
    if name not in PALETTES:
        return
    try:
        PREF_FILE.write_text(
            json.dumps({"theme": name}, ensure_ascii=False), encoding="utf-8"
        )
    except BaseException:
        pass


def theme_label(name: str) -> str:
    return PALETTES.get(name, PALETTES[DEFAULT_THEME])["label"]


def theme_mode(name: str) -> str:
    return PALETTES.get(name, PALETTES[DEFAULT_THEME])["mode"]


# --------------------------------------------------------------------------
# 颜色工具
# --------------------------------------------------------------------------
def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(channels) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in channels)


def _mix(a: str, b: str, ratio: float) -> str:
    """ratio=0 → a，ratio=1 → b。"""
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(ca[i] + (cb[i] - ca[i]) * ratio for i in range(3)))


def _rgba(color: str, alpha: float) -> str:
    """给阴影 / 焦点环用的 `rgb(r g b / a)`。"""
    r, g, b = _rgb(color)
    return f"rgb({r} {g} {b} / {alpha})"


# --------------------------------------------------------------------------
# 由基准色推导 Gradio 需要的全部语义变量
# --------------------------------------------------------------------------
def _variables(name: str) -> dict[str, str]:
    p = PALETTES[name]
    dark = p["mode"] == "dark"

    primary, deep, soft = p["primary"], p["primary_deep"], p["soft"]
    bg, surface, surface2, surface3 = p["bg"], p["surface"], p["surface2"], p["surface3"]
    text, muted, muted2, border = p["text"], p["muted"], p["muted2"], p["border"]
    on_primary = p.get("on_primary", "#FFFFFF")
    accent = p.get("accent", primary)

    # 色阶两端：浅色主题「低序号=最浅」，暗色主题「低序号=最暗」，方向相反
    lo_anchor = bg if dark else "#FFFFFF"           # 色阶 50 一侧的外推方向
    hi_anchor = "#FFFFFF" if dark else "#000000"    # 色阶 900 一侧的外推方向

    # 字段底色。Gradio 的输入控件容器（.block）靠底色而非描边区分，
    # 若与卡片同色就会「消失」。浅色主题取比页底暗一档，暗色主题取比页底亮一档。
    # 可用 field 显式指定（WorkBuddy 两套直接用它自己的 tertiary 灰）。
    field = p.get("field") or (
        _mix(bg, "#FFFFFF", 0.14) if dark else _mix(bg, "#000000", 0.03)
    )
    field_border = _mix(field, "#FFFFFF", 0.12) if dark else _mix(field, "#000000", 0.07)

    card_shadow = (
        "0 1px 2px rgb(0 0 0 / 0.55), 0 14px 34px -22px rgb(0 0 0 / 0.85)"
        if dark
        else "0 1px 2px rgb(24 32 32 / 0.03), 0 12px 32px -20px rgb(24 32 32 / 0.16)"
    )
    soft_shadow = "0 1px 2px rgb(0 0 0 / 0.45)" if dark else "0 1px 2px rgb(24 32 32 / 0.05)"
    lift_shadow = (
        "0 2px 10px -2px rgb(0 0 0 / 0.60)" if dark else "0 2px 8px -2px rgb(24 32 32 / 0.12)"
    )

    def scale_hue(base_soft: str, base: str, base_deep: str) -> dict[str, str]:
        return {
            "50": _mix(base_soft, lo_anchor, 0.55),
            "100": base_soft,
            "200": _mix(base_soft, base, 0.24),
            "300": _mix(base_soft, base, 0.48),
            "400": _mix(base_soft, base, 0.74),
            "500": base,
            "600": base_deep,
            "700": _mix(base_deep, hi_anchor, 0.14),
            "800": _mix(base_deep, hi_anchor, 0.28),
            "900": _mix(base_deep, hi_anchor, 0.44),
            "950": _mix(base_deep, hi_anchor, 0.60),
        }

    hue = scale_hue(soft, primary, deep)
    neutral = {
        # 浅色：50 最浅 → 950 最深；暗色：50 最暗 → 950 最亮
        "50": bg,
        "100": surface2,
        "200": border,
        "300": _mix(border, muted2, 0.50 if dark else 0.38),
        "400": muted2,
        "500": muted,
        "600": _mix(muted, text, 0.60 if dark else 0.72),
        "700": text,
        "800": _mix(text, hi_anchor, 0.02 if dark else 0.25),
        "900": _mix(text, hi_anchor, 0.30),
        "950": "#FFFFFF" if dark else _mix(text, "#000000", 0.50),
    }

    vars_: dict[str, str] = {}
    for step, value in hue.items():
        vars_[f"primary-{step}"] = value
        vars_[f"secondary-{step}"] = value
    for step, value in neutral.items():
        vars_[f"neutral-{step}"] = value

    vars_.update(
        {
            # ---- 字体 ----
            "font": FONT_STACK,
            "font-mono": FONT_MONO,
            # ---- 页面 / 面板 ----
            "body-background-fill": bg,
            "body-text-color": text,
            "body-text-color-subdued": muted,
            "background-fill-primary": surface,
            "background-fill-secondary": surface2,
            "border-color-primary": border,
            "border-color-accent": _mix(primary, lo_anchor, 0.35),
            "border-color-accent-subdued": soft,
            "color-accent": primary,
            "color-accent-soft": soft,
            "panel-background-fill": surface2,
            "panel-border-color": border,
            "container-radius": "16px",
            # ---- 链接 / 焦点 ----
            "link-text-color": accent,
            "link-text-color-hover": _mix(accent, hi_anchor, 0.18),
            "link-text-color-active": _mix(accent, hi_anchor, 0.28),
            "link-text-color-visited": accent,
            # ---- 区块：卡片 + 填充式字段 ----
            "block-background-fill": field,
            "block-border-color": field_border,
            "block-radius": "16px",
            "block-shadow": card_shadow,
            "block-title-text-color": text,
            "block-label-background-fill": "transparent",
            "block-label-border-color": "transparent",
            "block-label-shadow": "none",
            "block-label-text-color": muted,
            "block-label-radius": "8px",
            "block-info-text-color": muted2,
            "block-title-background-fill": "transparent",
            "block-title-border-color": "transparent",
            "block-title-radius": "8px",
            # ---- 输入控件 ----
            "input-background-fill": field,
            "input-background-fill-focus": _mix(field, "#FFFFFF", 0.05) if dark else surface,
            "input-background-fill-hover": _mix(field, "#FFFFFF", 0.03) if dark else _mix(field, "#000000", 0.02),
            "input-border-color": field_border,
            "input-border-color-hover": _mix(field, "#FFFFFF", 0.20) if dark else _mix(field, "#000000", 0.13),
            "input-border-color-focus": accent,
            "input-radius": "10px",
            "input-shadow": "none",
            "input-shadow-focus": f"0 0 0 3px {_rgba(accent, 0.24 if dark else 0.16)}",
            "input-placeholder-color": _mix(muted2, bg, 0.35) if dark else _mix(muted2, "#FFFFFF", 0.28),
            "input-text-size": "14px",
            "stat-background-fill": surface2,
            # ---- 勾选 / 单选 ----
            "checkbox-background-color": _mix(field, "#FFFFFF", 0.06) if dark else surface,
            "checkbox-background-color-hover": _mix(field, "#FFFFFF", 0.09) if dark else _mix(surface, soft, 0.35),
            "checkbox-background-color-focus": _mix(field, "#FFFFFF", 0.09) if dark else surface,
            "checkbox-background-color-selected": primary,
            "checkbox-border-color": field_border,
            "checkbox-border-color-hover": _mix(border, muted2, 0.45),
            "checkbox-border-color-focus": accent,
            "checkbox-border-color-selected": primary,
            "checkbox-check": on_primary,
            "checkbox-shadow": "none",
            "checkbox-label-background-fill": _mix(field, "#FFFFFF", 0.03) if dark else surface,
            "checkbox-label-background-fill-hover": _mix(field, soft, 0.55 if dark else 0.30),
            "checkbox-label-background-fill-selected": soft,
            "checkbox-label-border-color": field_border,
            "checkbox-label-border-color-hover": _mix(border, muted2, 0.45),
            "checkbox-label-border-color-selected": _mix(soft, primary, 0.45),
            "checkbox-label-text-color": _mix(text, muted, 0.55),
            "checkbox-label-text-color-selected": _mix(text, primary, 0.35 if dark else 0.20),
            "checkbox-label-shadow": "none",
            "checkbox-label-shadow-hover": "none",
            "checkbox-label-shadow-active": "none",
            "checkbox-label-padding": "6px 12px",
            "checkbox-label-gap": "6px",
            "checkbox-label-text-size": "13px",
            "checkbox-label-text-weight": "500",
            "checkbox-label-border-width": "1px",
            "checkbox-label-border-radius": "10px",
            # ---- 滑块 ----
            "slider-color": primary,
            # ---- 按钮 ----
            "button-primary-background-fill": primary,
            "button-primary-background-fill-hover": deep,
            "button-primary-border-color": primary,
            "button-primary-border-color-hover": deep,
            "button-primary-text-color": on_primary,
            "button-primary-text-color-hover": on_primary,
            "button-primary-shadow": soft_shadow,
            "button-primary-shadow-hover": lift_shadow,
            "button-primary-shadow-active": "none",
            "button-secondary-background-fill": _mix(surface, "#FFFFFF", 0.04) if dark else surface,
            "button-secondary-background-fill-hover": surface3 if dark else surface2,
            "button-secondary-border-color": field_border,
            "button-secondary-border-color-hover": _mix(border, muted2, 0.45),
            "button-secondary-text-color": _mix(text, muted, 0.30),
            "button-secondary-text-color-hover": text,
            # Gradio 的次级按钮靠 box-shadow 而非 border 画外框，给 0 宽阴影就会消失
            "button-secondary-shadow": f"0 0 0 1px {field_border}",
            "button-secondary-shadow-hover": (
                f"0 0 0 1px {_mix(border, muted2, 0.45)}, {lift_shadow}"
            ),
            "button-secondary-shadow-active": f"0 0 0 1px {_mix(border, muted2, 0.45)}",
            "button-cancel-background-fill": surface2,
            "button-cancel-background-fill-hover": _mix(surface2, muted, 0.18),
            "button-cancel-border-color": field_border,
            "button-cancel-border-color-hover": _mix(border, muted2, 0.45),
            "button-cancel-text-color": muted,
            "button-cancel-text-color-hover": text,
            "button-large-radius": "12px",
            "button-medium-radius": "10px",
            "button-small-radius": "8px",
            # ---- 表格 ----
            "table-border-color": border,
            "table-even-background-fill": field,
            "table-odd-background-fill": surface,
            "table-text-color": text,
            "table-row-focus": soft,
            # ---- 其它 ----
            "accordion-text-color": text,
            "shadow-drop": soft_shadow,
            "shadow-drop-lg": lift_shadow,
        }
    )

    # ---- 本模块自用（base_css 里直接引用） ----
    vars_.update(
        {
            "ts-mode": p["mode"],
            "ts-shadow-card": card_shadow,
            "ts-border": border,
            "ts-border-strong": _mix(border, muted2, 0.45),
            "ts-primary": primary,
            "ts-primary-soft": soft,
            "ts-on-primary": on_primary,
            "ts-field": field,
            "ts-surface": surface,
            "ts-surface-2": surface2,
            "ts-surface-3": surface3,
            "ts-text": text,
            "ts-muted": muted,
            "ts-muted-2": muted2,
            "ts-accent": accent,
            "ts-ring": _rgba(accent, 0.24 if dark else 0.16),
            "ts-scroll": "rgb(255 255 255 / 0.16)" if dark else "rgb(0 0 0 / 0.14)",
            "ts-scroll-hover": "rgb(255 255 255 / 0.26)" if dark else "rgb(0 0 0 / 0.24)",
        }
    )
    return vars_


def theme_css(name: str) -> str:
    """生成换肤用的 <style> 片段（含 color-scheme，让原生控件跟随明暗）。"""
    if name not in PALETTES:
        name = DEFAULT_THEME
    mode = PALETTES[name]["mode"]
    body = "\n".join(f"  --{k}: {v};" for k, v in _variables(name).items())
    # 双 :root 提特异性；同时覆盖 .dark，避免 Gradio 深色开关 / 系统偏好改写调色板
    return (
        "<style>\n"
        ":root:root, :root:root.dark, :root .dark {\n"
        f"  color-scheme: {mode};\n"
        f"{body}\n"
        "}\n"
        "</style>"
    )


# --------------------------------------------------------------------------
# 静态结构样式（与配色无关：排版、留白、卡片、页脚）
# --------------------------------------------------------------------------
def base_css() -> str:
    palette_icon = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' "
        "stroke-linecap='round' stroke-linejoin='round'%3E"
        "%3Cpath d='M12 21a9 9 0 1 1 9-9c0 1.66-1.34 3-3 3h-1.6a1.9 1.9 0 0 0-1.35 3.24"
        "c.36.36.47.9.28 1.37-.29.75-1.06 1.39-3.33 1.39Z'/%3E"
        "%3Ccircle cx='7.5' cy='10.5' r='1'/%3E"
        "%3Ccircle cx='12' cy='7.5' r='1'/%3E"
        "%3Ccircle cx='16.5' cy='10.5' r='1'/%3E%3C/svg%3E"
    )
    return f"""{font_face_css()}
/* ---------- 页面骨架 ---------- */
.gradio-container {{
  max-width: 1060px !important;
  margin: 0 auto !important;
  padding: 30px 22px 26px !important;
  background: var(--body-background-fill) !important;
  font-family: var(--font) !important;
  color: var(--body-text-color);
}}
.gradio-container .prose {{ max-width: none; }}
footer, .gradio-container footer {{ display: none !important; }}

/* 换肤变量槽：不可见，但其中的 <style> 规则照常生效 */
.ts-theme-vars {{ display: none !important; }}

/* ---------- 页头 ---------- */
.ts-hero {{ padding: 2px 2px 0; }}
.ts-hero h1 {{
  margin: 0;
  font-size: 29px;
  line-height: 1.25;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--body-text-color);
}}
.ts-hero h1 .ts-en {{
  font-weight: 300;
  color: var(--body-text-color-subdued);
  letter-spacing: 0.01em;
  margin-left: 8px;
  font-size: 26px;
}}
.ts-hero p {{
  margin: 7px 0 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--body-text-color-subdued);
}}
.ts-hero .ts-dot {{ color: var(--ts-primary); margin: 0 6px; }}
.ts-head {{ align-items: center !important; gap: 12px !important; }}

/* ---------- 主题选择器：调色盘图标 + 下拉 ---------- */
/* 图标按钮是页头行里一个 44px 的小方块，其余宽度全让给标题 */
.ts-head > .form:has(> .ts-theme-dd) {{
  flex: 0 0 auto !important;
  min-width: 0 !important;
  width: 44px !important;
  overflow: hidden !important;   /* 44px 容器出滚动条极难看，直接禁掉（下拉面板是 fixed 不受影响） */
}}
.ts-theme-dd {{
  min-width: 0 !important;
  width: 44px !important;
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 0 !important;
  overflow: visible !important;   /* 块默认 overflow:hidden，会把下拉面板裁掉 */
}}
/* Gradio 内部的多层容器全部剥底，只留按钮本身 */
.ts-theme-dd .container,
.ts-theme-dd .wrap,
.ts-theme-dd .wrap-inner {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  gap: 0 !important;
}}
/* 输入框本体：伪装成调色盘按钮 */
.ts-theme-dd .secondary-wrap {{
  position: relative !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  overflow: visible !important;
  background: var(--ts-surface) !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
  box-shadow: none !important;
  height: 38px !important;
  min-height: 38px !important;
  padding: 0 !important;
  gap: 0 !important;
  cursor: pointer;
}}
.ts-theme-dd .secondary-wrap:hover {{ border-color: var(--ts-border-strong) !important; }}
/* 选中值文字隐藏（当前主题由图标颜色体现）；输入层铺满按钮、保证可点可聚焦 */
.ts-theme-dd .secondary-wrap input {{
  position: absolute !important;
  inset: 0 !important;
  margin: 0 !important;   /* Gradio 默认 margin:4px 会把铺满的输入层顶出按钮 4px，撑出横向滚动条 */
  width: 100% !important;
  color: transparent !important;
  caret-color: transparent !important;
  font-size: 0 !important;
  padding: 0 !important;
  min-width: 0 !important;
  height: 100% !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}}
/* Gradio 自带的小箭头换成调色盘图标（mask 上色，自动跟随主题强调色） */
.ts-theme-dd .icon-wrap {{ display: none !important; }}
.ts-theme-dd .secondary-wrap::after {{
  content: "";
  position: absolute !important;
  inset: 0 !important;
  margin: auto !important;
  width: 18px;
  height: 18px;
  pointer-events: none;
  background-color: var(--ts-primary);
  -webkit-mask: url("{palette_icon}") no-repeat center / contain;
  mask: url("{palette_icon}") no-repeat center / contain;
}}
/* 下拉选项面板（Gradio 6 真实结构：.options > ul.option-list > li.item，
   position:fixed 渲染，宽度自适应，不会被 44px 按钮裁剪） */
.options.svelte-1ou0lab {{
  min-width: 178px !important;
  max-width: 230px !important;
  background: var(--ts-surface) !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 12px !important;
  box-shadow: var(--ts-shadow-card) !important;
  padding: 4px !important;
}}
.options.svelte-1ou0lab ul.option-list {{ padding: 0 !important; }}
.options.svelte-1ou0lab li.item {{
  width: auto !important;   /* Gradio 会把面板宽度内联成输入框宽度(42px)，项宽必须放开，否则文字逐字竖排 */
  padding: 7px 12px !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  color: var(--ts-text) !important;
}}
.options.svelte-1ou0lab li.item:hover,
.options.svelte-1ou0lab li.item.active {{
  background: var(--ts-primary-soft) !important;
  font-weight: 600 !important;
}}

/* ---------- 卡片 ---------- */
.ts-card {{
  background: var(--background-fill-primary);
  border: 1px solid var(--ts-border);
  border-radius: 16px;
  padding: 20px 20px 8px;
  box-shadow: var(--ts-shadow-card);
  gap: 12px !important;
}}
.ts-card > .form, .ts-card .form {{ border: none !important; background: transparent !important; }}

/* ---------- 主按钮 ---------- */
.ts-run {{ margin-top: 4px; }}
.ts-run button, button.ts-run {{
  height: 48px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  letter-spacing: 0.03em;
  border-radius: 12px !important;
  border: none !important;
}}
.ts-run button:focus-visible {{ box-shadow: 0 0 0 3px var(--ts-ring) !important; }}

/* ---------- 结果区 ---------- */
.ts-log textarea {{
  font-family: var(--font-mono) !important;
  font-size: 12px !important;
  line-height: 1.75 !important;
  color: var(--body-text-color-subdued) !important;
}}
.ts-preview {{
  background: var(--ts-surface) !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 12px !important;
  padding: 4px 16px !important;
  min-height: 300px;
  max-height: 460px;
  overflow-y: auto;
}}
.ts-download {{ min-height: 0 !important; }}
.ts-download .wrap {{ min-height: 0 !important; }}
.ts-preview .prose {{ font-size: 14px; line-height: 1.8; }}
.ts-status .prose h3 {{ margin: 0; font-size: 15px; font-weight: 600; }}
.ts-status {{ min-height: 26px; }}

/* ---------- 折叠面板 ---------- */
.gradio-container .label-wrap span {{ font-size: 13px !important; font-weight: 500 !important; }}
.gradio-container .label-wrap {{ color: var(--body-text-color-subdued) !important; }}

/* ---------- 页脚说明 ---------- */
.ts-foot {{
  text-align: center;
  font-size: 12px;
  line-height: 1.7;
  color: var(--body-text-color-subdued);
  opacity: .9;
  padding: 6px 0 0;
}}
.ts-foot code {{
  background: var(--ts-surface-2);
  border: 1px solid var(--ts-border);
  border-radius: 5px;
  padding: 1px 6px;
  font-size: 11.5px;
}}

/* ---------- 滚动条 ---------- */
.ts-preview::-webkit-scrollbar, .ts-log textarea::-webkit-scrollbar {{ width: 8px; height: 8px; }}
.ts-preview::-webkit-scrollbar-thumb, .ts-log textarea::-webkit-scrollbar-thumb {{
  background: var(--ts-scroll);
  border-radius: 4px;
}}
.ts-preview::-webkit-scrollbar-thumb:hover, .ts-log textarea::-webkit-scrollbar-thumb:hover {{
  background: var(--ts-scroll-hover);
}}
.ts-preview::-webkit-scrollbar-track, .ts-log textarea::-webkit-scrollbar-track {{ background: transparent; }}
"""


def gradio_theme() -> gr.themes.Base:
    """Gradio 基础主题：只定字体兜底、中性色相与圆角；配色由变量块接管。"""
    return gr.themes.Base(
        primary_hue="neutral",
        secondary_hue="neutral",
        neutral_hue="neutral",
        radius_size="lg",
    )
