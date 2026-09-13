@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem 把 Python 字节码缓存也收进 temp，避免项目目录里散落 __pycache__
set PYTHONPYCACHEPREFIX=%~dp0temp\pycache

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先执行：install.bat
    pause
    exit /b 1
)

if "%~1"=="" (
    echo 用法：
    echo   run_cli.bat "视频文件路径" [更多文件或链接...] [-o 输出目录]
    echo.
    echo 示例：
    echo   run_cli.bat "D:\videos\a.mp4"
    echo   run_cli.bat "D:\videos\a.mp4" https://www.bilibili.com/video/BV191GR6VE1i/ -o "D:\我的文稿"
    echo   run_cli.bat "D:\videos\a.mp4" --style block --speaker-stats
    pause
    exit /b 0
)

".venv\Scripts\python.exe" tools\run.py %*
echo.
pause
