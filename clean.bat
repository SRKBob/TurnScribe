@echo off
chcp 65001 >nul
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo   磁盘清理 - 话轮 TurnScribe
echo ============================================================
echo.
echo   [1] 项目临时文件     temp\logs + pycache*        很小
echo   [2] 下载缓存         temp\cache\downloads       ~12 MB
echo   [3] pip 下载缓存     全局，重装依赖需重下        ~3.3 GB
echo   [4] Windows 临时目录 全局，占用中的会跳过        ~2.9 GB
echo   [5] 模型权重缓存     ~\.cache\modelscope        ~2.0 GB
echo   [6] 虚拟环境 .venv   删后必须重跑 install.bat    ~7.3 GB
echo   [0] 退出
echo.
echo   [1][2] 安全：[1] 随时可删，[2] 下次处理链接会重新下载
echo   [3][4] 安全：纯缓存，系统会自动重建
echo   [5][6] 慎用：删了要重新下载 / 重装环境
echo.
set /p ch=请输入编号后回车: 

if "%ch%"=="1" goto clean_temp
if "%ch%"=="2" goto clean_downloads
if "%ch%"=="3" goto clean_pip
if "%ch%"=="4" goto clean_wintemp
if "%ch%"=="5" goto clean_models
if "%ch%"=="6" goto clean_venv
if "%ch%"=="0" goto end
goto menu

:confirm
echo.
set /p sure=%~1 输入 Y 确认，其他键取消: 
if /i "%sure%"=="Y" exit /b 0
exit /b 1

:clean_temp
call :confirm "将删除 temp\logs 与 temp\pycache*（不影响转写稿件）"
if errorlevel 1 goto menu
echo 清理中...
rd /s /q "temp\logs" >nul 2>&1
rd /s /q "temp\pycache" >nul 2>&1
rd /s /q "temp\pycache_stale" >nul 2>&1
echo 完成。temp\cache（断点续传缓存）与 temp\scratch 已保留。
echo.
pause
goto menu

:clean_downloads
call :confirm "将删除 temp\cache\downloads（下次处理链接视频会重新下载）"
if errorlevel 1 goto menu
echo 清理中...
rd /s /q "temp\cache\downloads" >nul 2>&1
echo 完成。
echo.
pause
goto menu

:clean_pip
call :confirm "将清空 pip 下载缓存（约 3.3 GB，以后装包需重新下载）"
if errorlevel 1 goto menu
echo 清理中...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip cache purge
) else (
    python -m pip cache purge
)
echo.
pause
goto menu

:clean_wintemp
call :confirm "将清理 Windows 临时目录（正在被占用的文件会自动跳过）"
if errorlevel 1 goto menu
echo 清理中...
del /f /s /q "%TEMP%\*.*" >nul 2>&1
for /d %%d in ("%TEMP%\*") do rd /s /q "%%d" >nul 2>&1
echo 完成。部分正在使用的文件未能删除，属正常。
echo.
pause
goto menu

:clean_models
call :confirm "将删除模型权重缓存（约 2 GB，下次运行需重新下载，约 10 分钟）"
if errorlevel 1 goto menu
echo 清理中...
rd /s /q "%USERPROFILE%\.cache\modelscope" >nul 2>&1
echo 完成。下次运行 run.bat 时会自动重新下载模型。
echo.
pause
goto menu

:clean_venv
echo.
echo   ！！警告：删除 .venv 后本工具将无法启动！
echo   恢复方式：重新双击 install.bat，需重新下载约 2.5 GB 依赖。
echo.
call :confirm "确认删除整个虚拟环境？"
if errorlevel 1 goto menu
echo 清理中...
rd /s /q ".venv" >nul 2>&1
echo 完成。如需恢复，双击 install.bat。
echo.
pause
goto menu

:end
endlocal
