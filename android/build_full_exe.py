# -*- coding: utf-8 -*-
"""
把**整个主程序**（Streamlit 全套：首页 / 曲库 / 街机厅 / VIP / 小游戏 / 档案 / 设置 / 信件）
打成一个 exe。用法：

    python package/build_full_exe.py          # onedir：一个文件夹，启动快
    python package/build_full_exe.py onefile  # 单文件：一个 exe，但每次要解压，启动慢

注意：这会带上 Streamlit 和 pandas / numpy 那一堆依赖，体积是几百 MB 的量级，
启动也要等几秒 —— 只想要「打歌 + 小游戏」的话，用轻量版 package/build_exe.py 就够了。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "package"
MODE = sys.argv[1] if len(sys.argv) > 1 else "onedir"
NAME = "舞萌DX完整版"
OUT = PKG / ("dist_full" if MODE == "onedir" else "dist_full_onefile")

ICON = next((p for p in (
    ROOT / "app-icon.ico",
    Path(__file__).resolve().parents[1] / "app-icon.ico",
) if p.exists()), None)

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onedir" if MODE == "onedir" else "--onefile",
    "--windowed",
    "--name", NAME,
    "--distpath", str(OUT),
    "--workpath", str(PKG / "build_full"),
    "--specpath", str(PKG),
    # Streamlit 的前端资源、altair 的 schema 都是散在包里的文件，必须整包收集
    "--collect-all", "streamlit",
    "--collect-all", "altair",
    # 项目本身
    "--add-data", f"{ROOT / 'app.py'}{os.pathsep}.",
    "--add-data", f"{ROOT / 'config.py'}{os.pathsep}.",
    "--add-data", f"{ROOT / 'modules'}{os.pathsep}modules",
    "--add-data", f"{ROOT / 'data'}{os.pathsep}data",
]
for mod in ("pandas", "numpy", "pyarrow", "protobuf", "tornado", "PIL", "requests"):
    cmd += ["--collect-all", mod]
# 包的元数据（importlib.metadata.version）在冻结环境下不一定跟得过去，
# 打包机上取不到的包名会让 PyInstaller 直接失败，所以这里不逐个 --copy-metadata，
# 改由 full_launcher.py 在运行时兜底（见 patch_metadata()）。
if ICON:
    cmd += ["--icon", str(ICON)]
cmd += ["--hidden-import", "streamlit.web.cli", "--hidden-import", "streamlit.runtime.scriptrunner.magic_funcs"]
cmd.append(str(PKG / "full_launcher.py"))

print(" ".join(str(c) for c in cmd))
r = subprocess.run(cmd, cwd=str(PKG))
if r.returncode != 0:
    sys.exit(r.returncode)

exe = OUT / NAME / f"{NAME}.exe" if MODE == "onedir" else OUT / f"{NAME}.exe"
print()
print("完成：", exe, f"({exe.stat().st_size / 1024 / 1024:.0f} MB)" if exe.exists() else "(没找到)")
