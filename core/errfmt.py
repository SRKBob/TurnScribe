"""错误翻译层：把管线异常转成用户能看懂的人话 + 可操作的建议。

原则：
- 界面日志只出现「发生了什么 + 怎么办」；技术细节压成一行括注。
- 完整堆栈仍打到控制台（stderr），用户反馈问题时可粘贴。
- 匹配规则按「最具体优先」排列；没命中就走兜底模板，不空转。
"""

from __future__ import annotations

import re
import sys
import traceback

# 规则表：(匹配正则, 人话标题, 行动建议)。按顺序匹配，先命中先用。
_RULES: list[tuple[str, str, str]] = [
    # ---- 下载 / 链接 ----
    (
        r"未安装 yt-dlp",
        "缺少下载组件 yt-dlp",
        "在项目目录执行 `.venv\\Scripts\\pip install yt-dlp` 后重试；或直接上传本地视频文件",
    ),
    # 模型加载失败放在网络规则之前——「下载模型超时」比「下载超时」更具体
    (
        r"modelscope|funasr|下载模型|snapshot|checkpoint|权重|\.pt\b|\.bin\b",
        "模型文件缺失或下载失败",
        "首次运行需要联网下载模型（约 1GB，存于用户缓存目录）；确认网络可用后重试，中断过的缓存会自动续传",
    ),
    (
        r"没有可用的解析器",
        "这个链接暂时无法识别",
        "检查链接是否完整；该平台可能暂不支持，可先下载到本机再上传文件",
    ),
    (
        r"登录|sign in|cookies|账号|login",
        "平台要求登录才能下载",
        "这类链接（抖音/快手/小红书等）常需要浏览器登录态，工具无法代替登录——建议把视频保存到手机/电脑后直接上传文件",
    ),
    (
        r"文件不存在|No such file|cannot find|找不到.{0,12}文件",
        "找不到文件",
        "文件可能被移动或删除，重新上传一次",
    ),
    (
        r"视频不可|unavailable|removed|private|已删除|404|not exist",
        "视频不存在或已被删除",
        "确认链接在浏览器里能正常打开；私密/已下架的视频无法下载",
    ),
    (
        r"age.?restrict|年龄限制",
        "视频有年龄限制",
        "带年龄限制的视频需要账号登录，工具无法下载；请改用本地文件",
    ),
    (
        r"timed? ?out|timeout|超时",
        "下载超时",
        "检查网络后重试；如果是长视频，网络不稳定时多试几次",
    ),
    (
        r"getaddrinfo|name or service|resolve|域名|DNS",
        "网络连接失败",
        "检查网络是否可用；链接域名可能被网络环境屏蔽，换网络或改用本地文件",
    ),
    (
        r"connection|SSL|reset|refused|断网|连接",
        "网络连接不稳定",
        "检查网络后重试；反复失败可改用本地文件（先把视频下载下来）",
    ),
    # ---- 媒体处理 ----
    (
        r"音频抽取失败|ffmpeg",
        "音频抽取失败（ffmpeg 问题）",
        "确认电脑上装有 ffmpeg 且在 PATH 中；视频文件本身损坏也会导致此错误，可先用播放器验证文件能正常播放",
    ),
    (
        r"无法解析媒体时长|invalid data|moov atom|损坏",
        "视频文件无法读取",
        "文件可能不完整或格式异常，先用播放器确认能正常播放；仍不行就转成 mp4 再试",
    ),
    # ---- 模型 / 显存 ----
    (
        r"out of memory|显存|CUDA error|OutOfMemory",
        "显存不够（GPU 内存不足）",
        "关闭其他占用显卡的程序后重试；或在「推理设备」里改选 `cpu`（会慢但稳定）；更短的音频也更省显存",
    ),
    (
        r"未识别到任何语音内容|静音|过短",
        "没有识别到语音",
        "视频可能全是背景音乐或音量过低；换个有声段的视频试试，或检查是否选错了语言",
    ),
    (
        r"Permission denied|拒绝访问|权限",
        "没有读写权限",
        "输出目录可能受系统保护（如 C:\\Windows），把输出目录改成 D 盘等普通文件夹",
    ),
    (
        r"磁盘|space|space不足|No space",
        "磁盘空间不足",
        "清理系统盘或更换输出目录后重试",
    ),
]

# 兜底：识别不出的错误给通用模板，不带堆栈


def friendly_error(exc: BaseException, source: str = "") -> str:
    """把异常翻译成用户可读的两行：发生了什么 + 怎么办。

    返回多行字符串（不带前缀缩进，由调用方控制排版）。
    同时把完整堆栈打到 stderr，方便反馈问题时取证。
    """
    print(f"[TurnScribe] 处理失败：{source or '（未指明来源）'}", file=sys.stderr)
    traceback.print_exc()

    text = f"{type(exc).__name__}: {exc}"
    title, tip = _match(text)

    detail = str(exc).strip().splitlines()[0][:120] if str(exc).strip() else type(exc).__name__
    lines = [f"❌ {title}"]
    if source:
        lines.append(f"　出错环节：{source}")
    lines.append(f"👉 {tip}")
    lines.append(f"　（技术细节：{detail}）")
    return "\n".join(lines)


def _match(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for pattern, title, tip in _RULES:
        if re.search(pattern, text) or re.search(pattern, lowered, re.IGNORECASE):
            return title, tip
    return "处理失败", "把日志里的「技术细节」截图反馈，或换一个文件/链接再试"
