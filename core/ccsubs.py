"""B站 CC 字幕直读：命中则完全跳过下载、抽音轨、ASR 与说话人分离。

链路（三个官方接口，均为 GET）：
    1. /x/web-interface/view?bvid=..        -> 标题、时长、cid
    2. /x/player/v2?bvid=..&cid=..          -> subtitle.subtitles[] 字幕轨列表
    3. <subtitle_url>（aisubtitle.hdslb.com）-> {"body": [{"from","to","content"}]}

访问限制：
    - 匿名只能看到 UP 主手传的 CC 字幕；
    - AI 字幕（lan=ai-zh）需要登录态，通过 SESSDATA（local_config.py 或环境变量
      BILIBILI_SESSDATA）提供。拿不到字幕轨时返回 None，由主流程降级走 ASR。
    - 请求必须带 Referer: https://www.bilibili.com/，否则 412。
"""

from __future__ import annotations

import json
import re
import urllib.request
import uuid
from typing import Any, Callable

from core.types import Segment

ProgressFn = Callable[[float, str], None]

# 字幕轨语言优先级：AI 中文字幕 > 简中 > 其他
LANG_PRIORITY = ("ai-zh", "zh-Hans", "zh-CN", "zh")

BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
AV_RE = re.compile(r"av(\d+)", re.IGNORECASE)

_UA = "Mozilla/5.0"
# 注意：UA 不能伪装成完整 Chrome 串——B站风控会核对 UA 与 TLS 指纹，
# 「声称是浏览器但指纹是 Python」直接 412；诚实的短 UA 反而放行。


# B站是国内站点：强制直连。若环境里设了 HTTP_PROXY（常见于为了 YouTube 挂代理），
# urllib 会默认走代理出口，数据中心 IP 会被 B站风控直接 412。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_json(url: str, sessdata: str = "") -> dict[str, Any]:
    # B站风控要求请求携带 buvid3，纯裸请求会吃 412。规范做法是先访问主站
    # 领取 buvid3，但实测一个随机 UUID 同样放行，省掉一次往返。
    buvid = f"buvid3={uuid.uuid4().hex}infoc"
    cookie = buvid + (f"; SESSDATA={sessdata}" if sessdata else "")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie,
        },
    )
    with _OPENER.open(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _video_id(url: str) -> str:
    """从链接里抠出 BV 号；b23.tv 短链先跟随跳转。"""
    if "b23.tv" in url:
        req = urllib.request.Request(
            url, headers={"User-Agent": _UA}, method="HEAD"
        )
        with _OPENER.open(req, timeout=20) as resp:
            url = resp.geturl()
    match = BV_RE.search(url)
    if match:
        return match.group(0)
    av = AV_RE.search(url)
    if av:
        return f"av{av.group(1)}"
    raise ValueError(f"链接里没有找到 BV/av 号：{url}")


def _pick_subtitle_track(tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_lan = {t.get("lan"): t for t in tracks}
    for lan in LANG_PRIORITY:
        if lan in by_lan:
            return by_lan[lan]
    return tracks[0] if tracks else None


def parse_body_entries(entries: list[dict[str, Any]]) -> list[Segment]:
    """把 B站字幕 JSON 的 body 数组转成 Segment 列表（说话人固定为 0）。"""
    segments: list[Segment] = []
    for item in entries:
        text = str(item.get("content", "")).strip()
        if not text:
            continue
        segments.append(
            Segment(
                start_ms=int(float(item["from"]) * 1000),
                end_ms=int(float(item["to"]) * 1000),
                text=text,
                speaker=0,  # 字幕无说话人信息，统一挂到单角色上
            )
        )
    return segments


def fetch_cc_subtitles(
    url: str,
    sessdata: str = "",
    progress: ProgressFn | None = None,
) -> dict[str, Any] | None:
    """尝试拉取 B站视频自带 CC 字幕。

    返回 {"segments", "title", "duration_s", "lang"}；没有字幕轨时返回 None
    （调用方应降级为 ASR）。接口/网络异常向上抛，由主流程统一兜住。
    """
    vid = _video_id(url)
    if progress:
        progress(0.10, "读取视频信息…")
    view = _get_json(
        f"https://api.bilibili.com/x/web-interface/view?bvid={vid}" if vid.startswith("BV")
        else f"https://api.bilibili.com/x/web-interface/view?aid={vid[2:]}",
        sessdata,
    )
    if view.get("code") != 0:
        raise RuntimeError(f"B站接口返回异常：{view.get('message', '未知错误')}")
    data = view["data"]
    title = str(data.get("title", "")).strip()
    duration_s = float(data.get("duration", 0))
    cid = data.get("cid")

    if progress:
        progress(0.40, "查询字幕轨…")
    player = _get_json(
        f"https://api.bilibili.com/x/player/v2?bvid={vid}&cid={cid}"
        if vid.startswith("BV")
        else f"https://api.bilibili.com/x/player/v2?aid={vid[2:]}&cid={cid}",
        sessdata,
    )
    tracks = ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
    track = _pick_subtitle_track(tracks)
    if track is None:
        return None

    if progress:
        progress(0.70, f"下载字幕（{track.get('lan_doc') or track.get('lan')}）…")
    sub_url = str(track.get("subtitle_url", ""))
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    body = _get_json(sub_url, sessdata).get("body") or []
    segments = parse_body_entries(body)
    if not segments:
        return None

    if progress:
        progress(0.95, f"取到 {len(segments)} 条 CC 字幕")
    return {
        "segments": segments,
        "title": title,
        "duration_s": duration_s,
        "lang": str(track.get("lan", "")),
    }
