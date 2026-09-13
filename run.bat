@echo off
chcp 65001 >nul
title 话轮 TurnScribe
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem 把 Python 字节码缓存也收进 temp，避免项目目录里散落 __pycache__
set PYTHONPYCACHEPREFIX=%~dp0temp\pycache

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先执行：install.bat
    pause
    exit /b 1
)

echo 正在启动话轮 TurnScribe...
echo 服务地址 http://127.0.0.1:7860  （关闭本窗口即停止服务）
echo.

".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请查看上方日志。
    pause
)
