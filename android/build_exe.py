# -*- coding: utf-8 -*-
"""用 PyInstaller 把机台打成一个 exe。用法：python package/build_exe.py"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "package"
OUT = PKG / "dist"
# 默认打「整合大厅」（机台 + 小游戏 + 曲库 + 成绩）；
# 想要纯机台版就：python package/build_exe.py cabinet
MODE = sys.argv[1] if len(sys.argv) > 1 else "hub"
HTML = ROOT / "standalone" / ("maimai-dx.html" if MODE == "cabinet" else "maimai-hub.html")
NAME = "舞萌DX机台" if MODE == "cabinet" else "舞萌DX大厅"
# 图标：优先用工程里自带的 app-icon.ico，找不到再退回外部那一份
ICON = next((p for p in (
    ROOT / "app-icon.ico",
    PKG / "app-icon.ico",
    Path(__file__).resolve().parents[1] / "app-icon.ico",
) if p.exists()), None)

if not HTML.exists():
    sys.exit("先跑 work/build_standalone.py 生成 standalone/maimai-dx.html")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", NAME,
    "--distpath", str(OUT),
    "--workpath", str(PKG / "build"),
    "--specpath", str(PKG),
    "--add-data", f"{HTML}{os.pathsep}.",
]
if ICON is not None and ICON.exists():
    cmd += ["--icon", str(ICON)]
cmd.append(str(PKG / "desktop_launcher.py"))

print(" ".join(str(c) for c in cmd))
r = subprocess.run(cmd, cwd=str(PKG))
if r.returncode != 0:
    sys.exit(r.returncode)
exe = OUT / f"{NAME}.exe"
print()
print("完成：", exe, f"({exe.stat().st_size / 1024 / 1024:.1f} MB)" if exe.exists() else "(没找到)")
