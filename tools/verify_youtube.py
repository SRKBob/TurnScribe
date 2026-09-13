"""YouTube 链路验证：分层探测，定位问题卡在哪一层。

用法（先确保代理可用并设置了 YTDLP_PROXY，见下）：
    set YTDLP_PROXY=http://127.0.0.1:7890
    .venv\\Scripts\\python.exe tools\\verify_youtube.py            # 第 1 层：元数据（秒级）
    .venv\\Scripts\\python.exe tools\\verify_youtube.py --full      # 第 2 层：完整转写（19 秒测试视频）

测试视频用 YouTube 史上第一条视频「Me at the zoo」（19 秒、公开、无年龄限制）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def layer1_metadata() -> bool:
    """第 1 层：网络 + yt-dlp 解析。不下视频，秒级。"""
    import os

    import yt_dlp

    proxy = os.environ.get("YTDLP_PROXY", "").strip()
    print(f"[1] 代理：{proxy or '（未设置 YTDLP_PROXY —— 国内网络大概率超时）'}")
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "socket_timeout": 15,
    }
    if proxy:
        opts["proxy"] = proxy
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(TEST_URL, download=False)
        print(f"[1] 通过：解析到「{info['title']}」（{info.get('duration')}s，"
              f"音轨格式 {len(info.get('formats', []))} 种可选）")
        return True
    except Exception as exc:
        text = str(exc)[:200]
        if "timed out" in text or "getaddrinfo" in text or "Connection" in text:
            print(f"[1] 失败（网络层）：{text}")
            print("    👉 代理没通：确认代理软件在跑、YTDLP_PROXY 端口写对后重试")
        else:
            print(f"[1] 失败（解析层）：{text}")
            print("    👉 网络通了但 yt-dlp 解析被拒：升级 yt-dlp 后重试"
                  "（.venv\\Scripts\\pip install -U yt-dlp）")
        return False


def layer2_pipeline() -> bool:
    """第 2 层：真实管线（下载音轨 -> 识别 -> 出 Markdown）。"""
    from config import CONFIG
    from core.pipeline import Pipeline

    print("[2] 跑完整管线：下载 19 秒测试视频音轨并转写…")
    try:
        result = Pipeline(CONFIG).process(TEST_URL)
    except Exception as exc:
        print(f"[2] 失败：{exc}")
        return False
    print(f"[2] 通过：{result.summary}")
    print(f"    文稿：{result.md_path}")
    print(f"    预览：{result.md_path.read_text(encoding='utf-8')[:120]}…")
    return True


def main() -> int:
    ok = layer1_metadata()
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        ok = layer2_pipeline() and ok
    else:
        print("\n（第 1 层通过后，加 --full 验证端到端转写）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
