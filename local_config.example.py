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
