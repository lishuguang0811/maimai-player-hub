#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[1/2] 创建虚拟环境..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

echo "[2/2] 启动中，浏览器将打开 http://localhost:8501"
exec .venv/bin/python -m streamlit run app.py
