"""链接解析层（可插拔）。

设计目标：平台反爬随时会变，所以把「拿到本地媒体文件」这件事抽象成 Resolver。
默认用 yt-dlp；某个平台失效时，注册一个新的 Resolver 即可，主流程不动。
"""

from __future__ import annotations

import glob
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

ProgressFn = Callable[[float, str], None]

# 各平台特征。用于 GUI 提示稳定性，也用于决定是否重试带 Cookie。
PLATFORM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"bilibili\.com|b23\.tv", "bilibili"),
    (r"douyin\.com", "douyin"),
    (r"iesdouyin\.com", "douyin"),
    (r"kuaishou\.com|v\.kuaishou\.com", "kuaishou"),
    (r"xiaohongshu\.com|xhslink\.com", "xiaohongshu"),
    (r"channels\.weixin\.qq\.com|weixin\.qq\.com", "wechat_channels"),
    (r"youtube\.com|youtu\.be", "youtube"),
)

# 已知需要登录态才稳的平台：先匿名试，失败再带浏览器 Cookie 重试
NEEDS_COOKIES = {"douyin", "kuaishou", "xiaohongshu", "wechat_channels"}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def detect_platform(url: str) -> str:
    for pattern, name in PLATFORM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return "unknown"


def is_url(text: str) -> bool:
    return bool(URL_RE.match(text.strip()))


class ResolverError(RuntimeError):
    pass


class Resolver(ABC):
    """解析器接口：给一个链接，还一个本地媒体文件路径。"""

    name = "base"

    @abstractmethod
    def can_handle(self, url: str) -> bool: ...

    @abstractmethod
    def resolve(self, url: str, workdir: Path, progress: ProgressFn | None = None) -> Path: ...


class YtDlpResolver(Resolver):
    """默认解析器。只取音轨，不拉视频流 —— 3 小时视频从几百 MB 降到几十 MB。"""

    name = "yt-dlp"

    def can_handle(self, url: str) -> bool:
        return is_url(url)

    def resolve(self, url: str, workdir: Path, progress: ProgressFn | None = None) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover
            raise ResolverError("未安装 yt-dlp，请先执行 pip install yt-dlp") from exc

        workdir.mkdir(parents=True, exist_ok=True)
        platform = detect_platform(url)

        def hook(status: dict) -> None:
            if progress is None:
                return
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
                done = status.get("downloaded_bytes") or 0
                ratio = (done / total) if total else 0.0
                progress(ratio, f"下载中 {done / 1048576:.1f}MB / {total / 1048576:.1f}MB")
            elif status.get("status") == "finished":
                progress(1.0, "下载完成，抽取音轨…")

        def build_opts(use_cookies: bool) -> dict:
            opts: dict = {
                "format": "ba/bestaudio/best",
                "outtmpl": str(workdir / "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "retries": 3,
                "writeinfojson": True,   # 供 pipeline 取原始标题，用于 Markdown 文件名
                "progress_hooks": [hook],
            }
            if use_cookies:
                # 抖音等平台需要登录态，从本机 Edge 读取 Cookie。
                # Cookie 仅在本机内存中交给 yt-dlp，不落盘、不进版本库。
                opts["cookiesfrombrowser"] = ("edge",)
            return opts

        attempts = [False, True] if platform in NEEDS_COOKIES else [False]
        last_error = ""
        for use_cookies in attempts:
            try:
                if progress:
                    label = "带浏览器 Cookie 重试" if use_cookies else f"解析 {platform} 链接"
                    progress(0.0, label)
                with yt_dlp.YoutubeDL(build_opts(use_cookies)) as ydl:
                    info = ydl.extract_info(url, download=True)
                video_id = info.get("id", "")
                matches = [
                    p for p in glob.glob(str(workdir / f"{video_id}.*"))
                    if not p.endswith((".part", ".ytdl"))
                ]
                if matches:
                    return Path(max(matches, key=lambda p: Path(p).stat().st_size))
                last_error = "下载完成但未找到媒体文件"
            except Exception as exc:  # yt-dlp 抛的异常类型繁杂，统一兜住
                last_error = str(exc)

        hint = ""
        if platform in NEEDS_COOKIES:
            hint = "（该平台需要登录态：请在 Edge 中登录后重试，或改用本地文件上传）"
        raise ResolverError(f"链接解析失败：{last_error}{hint}")


class ResolverRegistry:
    """解析器注册表。新增平台只需 registry.register(MyResolver())。"""

    def __init__(self) -> None:
        self._resolvers: list[Resolver] = [YtDlpResolver()]

    def register(self, resolver: Resolver, *, priority: int = 0) -> None:
        self._resolvers.insert(max(0, priority), resolver)

    def pick(self, url: str) -> Resolver:
        for resolver in self._resolvers:
            if resolver.can_handle(url):
                return resolver
        raise ResolverError(f"没有可用的解析器处理该链接：{url}")


REGISTRY = ResolverRegistry()


def resolve_input(
    raw: str,
    workdir: Path,
    progress: ProgressFn | None = None,
) -> tuple[Path, str]:
    """统一入口：本地路径原样返回，URL 交给解析器。返回 (文件路径, 平台名)。"""
    raw = raw.strip().strip('"')
    if is_url(raw):
        resolver = REGISTRY.pick(raw)
        return resolver.resolve(raw, workdir, progress), detect_platform(raw)

    path = Path(raw)
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在：{raw}")
    return path, "local"


def cleanup_downloads(workdir: Path) -> None:
    """清掉下载缓存中残留的分片文件。失败不影响主流程。"""
    try:
        for pattern in ("*.part", "*.ytdl", "*.temp"):
            for leftover in workdir.glob(pattern):
                try:
                    leftover.unlink()
                except BaseException:  # noqa: BLE001
                    pass
        if workdir.exists() and not any(workdir.iterdir()):
            shutil.rmtree(workdir, ignore_errors=True)
    except BaseException:  # noqa: BLE001
        pass
