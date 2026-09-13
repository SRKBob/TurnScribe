"""音频抽取与探测。只依赖 ffmpeg，不依赖任何模型。"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from config import find_ffmpeg

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def probe_duration_ms(path: str | Path) -> int:
    """用 `ffmpeg -i` 的 stderr 解析时长。本机没有独立的 ffprobe，故不依赖它。"""
    result = _run([find_ffmpeg(), "-hide_banner", "-i", str(path)])
    text = result.stderr.decode("utf-8", errors="ignore")
    match = _DURATION_RE.search(text)
    if not match:
        raise ValueError(f"无法解析媒体时长：{path}")
    hours, minutes, seconds, frac = match.groups()
    frac_ms = int(frac.ljust(3, "0"))
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + frac_ms


def extract_audio(
    src: str | Path,
    dst: str | Path,
    *,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    """抽出 16kHz 单声道 wav —— SenseVoice / VAD / CAM++ 的统一输入格式。

    只取音轨（-vn），3 小时视频从几百 MB 降到几十 MB。
    """
    src_path, dst_path = Path(src), Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src_path),
        "-vn",
        "-ac", "1" if mono else "2",
        "-ar", str(sample_rate),
        "-acodec", "pcm_s16le",
        "-f", "wav",
        str(dst_path),
    ]
    result = _run(cmd)
    if result.returncode != 0 or not dst_path.exists():
        detail = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"音频抽取失败：{detail or '未知错误'}")
    return dst_path


def ffmpeg_available() -> tuple[bool, str]:
    """给 GUI 做启动自检用。"""
    try:
        path = find_ffmpeg()
    except FileNotFoundError as exc:
        return False, str(exc)
    result = _run([path, "-version"])
    if result.returncode != 0:
        return False, f"ffmpeg 无法执行：{path}"
    first_line = result.stdout.decode("utf-8", errors="ignore").splitlines()
    return True, first_line[0] if first_line else path


def dump_json(path: str | Path, data: object) -> Path:
    """统一用 UTF-8 无 BOM 落盘，避免中文在 Windows 下乱码。"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))
