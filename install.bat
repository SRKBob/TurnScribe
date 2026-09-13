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
    echo        请安装 Python 并加入 PATH，或设置环境变量 PYTHON_BIN 指向 python.exe
    pause
    exit /b 1
)

echo === 1/4 创建虚拟环境 ===
if not exist ".venv\Scripts\python.exe" "%PY%" -m venv .venv

echo === 2/4 升级 pip ===
".venv\Scripts\python.exe" -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo === 3/4 安装 torch（CUDA 12.6，约 2.5GB，走国内镜像） ===
rem 官方源 download.pytorch.org 在国内基本拉不动，改用阿里云镜像
".venv\Scripts\python.exe" -m pip install "torch==2.8.0+cu126" "torchaudio==2.8.0+cu126" ^
    -f https://mirrors.aliyun.com/pytorch-wheels/cu126/ ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple

echo === 4/4 安装其余依赖 ===
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo === 环境自检 ===
".venv\Scripts\python.exe" tools\check_env.py

echo.
echo 安装完成。双击 run.bat 启动。
pause
