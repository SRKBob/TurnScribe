@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 把 Python 字节码缓存也收进 temp，避免项目目录里散落 __pycache__
set PYTHONPYCACHEPREFIX=%~dp0temp\pycache

rem 解释器可用环境变量 PYTHON_BIN 指定，未设置时用 PATH 里的 python
rem 不要写死本机绝对路径——个人目录路径不应进版本库
set "PY=python"
if defined PYTHON_BIN set "PY=%PYTHON_BIN%"

where "%PY%" >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 解释器。
    echo        请安装 Python 3.10+ 并勾选 "Add to PATH"，或设置环境变量 PYTHON_BIN 指向 python.exe
    echo        下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo === 1/5 创建虚拟环境 ===
if not exist ".venv\Scripts\python.exe" "%PY%" -m venv .venv

echo === 2/5 升级 pip ===
".venv\Scripts\python.exe" -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo === 3/5 安装 torch（CUDA 12.6，约 2.5GB，走国内镜像） ===
rem 官方源 download.pytorch.org 在国内基本拉不动，改用阿里云镜像
".venv\Scripts\python.exe" -m pip install "torch==2.8.0+cu126" "torchaudio==2.8.0+cu126" ^
    -f https://mirrors.aliyun.com/pytorch-wheels/cu126/ ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [提示] torch 安装失败多为网络中断，重新运行本脚本即可续传。
    pause
    exit /b 1
)

echo === 4/5 安装其余依赖 ===
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [提示] 依赖安装失败，重新运行本脚本即可续传。
    pause
    exit /b 1
)

echo === 5/5 预下载模型权重（约 1GB，只下一次，中断可重跑续传） ===
".venv\Scripts\python.exe" tools\check_env.py --download

echo.
echo === 环境自检 ===
".venv\Scripts\python.exe" tools\check_env.py

echo.
rem ffmpeg 不在 pip 里装：给用户明确的放文件指引，run.bat 启动后首屏引导卡也会再提示
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, '.'); from config import find_ffmpeg; print('[OK] ffmpeg', find_ffmpeg())" 2>nul
if errorlevel 1 (
    echo [待办] 还差 ffmpeg（处理视频必需）：
    echo        1. 打开 https://www.gyan.dev/ffmpeg/builds/ 下载 "release essentials" 解压版
    echo        2. 解压后把 bin\ffmpeg.exe 复制到本项目 bin\ 目录下（没有 bin 文件夹就新建一个）
    echo        放好后双击 run.bat 即可使用。
) else (
    echo 全部就绪。双击 run.bat 启动。
)
pause
