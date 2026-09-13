"""首启体检：检测 ffmpeg / torch+CUDA / 模型缓存，给用户能看懂的引导。

设计约束：
- 全部只读检测，不触发下载；下载仍由 check_env --download 或首次转写兜底完成。
- 模型缓存检测扫「候选缓存根」里的目录名（funasr/modelscope 的落盘布局），
  目录存在且非空才算就绪——下载中断留下的空壳不算。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from config import MODEL_DIR, find_ffmpeg

# 模型别名 -> 缓存目录名特征（funasr 解析别名后的真实落盘名，见 ~/.cache/modelscope/models/）
_MODEL_PATTERNS: list[tuple[str, str, tuple[str, ...]]] = [
    ("SenseVoice 识别", "iic--SenseVoiceSmall", ("SenseVoiceSmall",)),
    ("FSMN-VAD 切分", "speech_fsmn_vad", ("fsmn_vad",)),
    ("CT-Punc 标点", "punc_ct-transformer", ("punc_ct-transformer",)),
    ("CAM++ 声纹", "speech_campplus", ("campplus",)),
]


def _cache_roots() -> list[Path]:
    """模型权重可能出现的目录：环境变量覆盖 > 项目 models/ > 用户级缓存。"""
    roots: list[Path] = [MODEL_DIR]
    env = os.environ.get("MODELSCOPE_CACHE")
    if env:
        roots.append(Path(env))
    roots.append(Path.home() / ".cache" / "modelscope" / "models")
    return roots


def _model_ready(patterns: tuple[str, ...]) -> bool:
    for root in _cache_roots():
        if not root.is_dir():
            continue
        try:
            for entry in root.iterdir():
                name = entry.name.lower()
                if any(p.lower() in name for p in patterns) and any(entry.iterdir()):
                    return True
        except OSError:
            continue
    return False


@dataclass
class Check:
    name: str
    ok: bool
    detail: str        # 现状一句话
    howto: str = ""    # 未就绪时的指引


def models_missing() -> list[str]:
    """轻量查询：还缺哪些模型权重（只扫目录，不碰 torch）。"""
    return [label for label, _, patterns in _MODEL_PATTERNS if not _model_ready(patterns)]


def run_checks() -> list[Check]:
    checks: list[Check] = []

    # 1) ffmpeg
    try:
        checks.append(Check("ffmpeg", True, "已就绪 — " + find_ffmpeg()))
    except FileNotFoundError:
        checks.append(Check(
            "ffmpeg", False,
            "未找到（处理视频必需）",
            "下载 ffmpeg（https://www.gyan.dev/ffmpeg/builds/ 的 release essentials 解压版），"
            "把 ffmpeg.exe 放进项目 `bin\\` 目录即可，无需安装",
        ))

    # 2) torch / GPU
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            gib = torch.cuda.get_device_properties(0).total_memory / 1024**3
            checks.append(Check("推理设备", True, f"{name}（显存 {gib:.1f}GB，转写走 GPU）"))
        else:
            checks.append(Check(
                "推理设备", False,
                "GPU 不可用，将用 CPU 转写（3 小时素材约需 40-90 分钟）",
                "装有 NVIDIA 显卡时：确认 install.bat 的 torch 安装步骤成功（CUDA 版），重新运行 install.bat 可修复",
            ))
    except ImportError:
        checks.append(Check(
            "推理设备", False, "未安装 torch",
            "重新运行 install.bat 完成依赖安装",
        ))

    # 3) 模型权重（首次运行需联网下载约 1GB）
    missing = models_missing()
    if not missing:
        size_ok = "4 个模型权重全部就绪"
        try:
            total = sum(
                f.stat().st_size
                for root in _cache_roots() if root.is_dir()
                for f in root.rglob("*") if f.is_file()
            )
            size_ok += f"（{total / 1024**3:.1f}GB）"
        except OSError:
            pass
        checks.append(Check("模型权重", True, size_ok))
    else:
        checks.append(Check(
            "模型权重", False,
            f"尚未下载：{'、'.join(missing)}",
            "点击「开始转写」会自动联网下载（约 1GB，下载一次永久使用，中断可续传）；"
            "也可在命令行执行 `.venv\\Scripts\\python.exe tools\\check_env.py --download` 提前拉取",
        ))

    return checks


def status_markdown() -> str:
    """渲染成 UI 首屏引导卡。全部就绪时收成一行，避免常年占地方。"""
    checks = run_checks()
    if all(c.ok for c in checks):
        detail = next(c.detail for c in checks if c.name == "推理设备")
        return f"✅ 环境就绪 — {detail}，模型权重与 ffmpeg 均可用\n"

    lines = ["### ⚠️ 首次使用，还有几件事没就绪\n"]
    for c in checks:
        mark = "✅" if c.ok else "❌"
        lines.append(f"- {mark} **{c.name}** — {c.detail}")
        if not c.ok and c.howto:
            lines.append(f"  - 👉 {c.howto}")
    lines.append("\n就绪项不用管；未就绪项处理完刷新本页即可。")
    return "\n".join(lines)
