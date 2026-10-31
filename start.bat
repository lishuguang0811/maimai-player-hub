@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   舞萌助手 · MAIMAI PLAYER HUB
echo ============================================

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] 首次运行，正在创建虚拟环境...
  python -m venv .venv
  if errorlevel 1 (
    echo [!] 没找到 python，请先安装 Python 3.10+ 并勾选 Add to PATH。
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [2/2] 启动中，浏览器将打开 http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause
