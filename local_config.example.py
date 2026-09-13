"""本机私有配置模板。

用法：把本文件复制为 local_config.py，按需填入自己机器上的路径。
local_config.py 已在 .gitignore 中，不会被提交到版本库。

项目里凡与「我这台机器」强相关、不适合公开的内容（个人目录下的工具路径、
私有解析服务地址、凭据等）都放这里，不要写进 config.py。
"""

# ffmpeg 副本路径，PATH 里找不到时依次尝试。不需要就留空元组。
FFMPEG_CANDIDATES: tuple[str, ...] = (
    # r"C:\tools\ffmpeg\bin\ffmpeg.exe",
)

# B站登录态（SESSDATA Cookie 值）：配置后 B站 AI 字幕（ai-zh）也能直读，
# 不配置则只能读到 UP 主手传的 CC 字幕，读不到时自动降级为语音识别。
# 获取方式：Edge 登录 B站 -> F12 -> Application -> Cookies -> 复制 SESSDATA 的值。
# BILIBILI_SESSDATA = "粘贴到这里"
