@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 入党积极分子刷题库（关闭本窗口即停止）

rem 优先用 Python，其次用 Node.js
where py >nul 2>nul
if %errorlevel%==0 (
  py server.py --open
  goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
  python server.py --open
  goto :done
)

where node >nul 2>nul
if %errorlevel%==0 (
  node server.js --open
  goto :done
)

echo.
echo [错误] 没有检测到 Python 或 Node.js。
echo 请先安装 Python 3（https://www.python.org/），再双击本文件。
pause
goto :eof

:done
if errorlevel 1 (
  echo.
  echo 服务已异常退出，请查看上方提示。
  pause
)
