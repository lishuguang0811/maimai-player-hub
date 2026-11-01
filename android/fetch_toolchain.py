# -*- coding: utf-8 -*-
"""
把编 APK 需要的工具链拉下来 —— 只要 JDK + build-tools + platform，不装 Android Studio。

三样东西都来自官方分发包，直接解压就能用：
    JDK 17          华为镜像的 OpenJDK（国内快）
    build-tools 35  dl.google.com 官方分发包（aapt2 / zipalign / d8 / apksigner）
    platform 35     dl.google.com 官方分发包（android.jar）

默认落在 <项目>\\.toolchain 或 <项目上级>\\.toolchain（后者不污染工程目录）。
"""

import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = [
    # (文件名, [候选下载地址，按顺序试])
    ("jdk17.zip", [
        "https://mirrors.huaweicloud.com/openjdk/17.0.1/openjdk-17.0.1_windows-x64_bin.zip",
        "https://aka.ms/download-jdk/microsoft-jdk-17.0.13-windows-x64.zip",
    ]),
    ("build-tools.zip", [
        "https://dl.google.com/android/repository/build-tools_r35.0.1_windows.zip",
        "https://dl.google.com/android/repository/build-tools_r34-windows.zip",
    ]),
    ("platform.zip", [
        "https://dl.google.com/android/repository/platform-35_r02.zip",
        "https://dl.google.com/android/repository/platform-34-ext12_r01.zip",
    ]),
]


def download(name: str, urls, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1024 * 1024:
        print("  已有 %s（%.0f MB），跳过" % (name, dest.stat().st_size / 1048576))
        return True
    for url in urls:
        print("  试 %s" % url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    buf = r.read(1 << 20)
                    if not buf:
                        break
                    f.write(buf)
                    got += len(buf)
                    if total:
                        print("\r     %.1f / %.1f MB" % (got / 1048576, total / 1048576),
                              end="", flush=True)
            print()
            if dest.stat().st_size > 1024 * 1024:
                return True
        except Exception as e:
            print("    失败：%s" % e)
            dest.unlink(missing_ok=True)
    return False


def unzip(zp: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp) as z:
        z.extractall(dest)
    print("  解压 → %s" % dest)


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / ".toolchain"
    base.mkdir(parents=True, exist_ok=True)
    print("工具链目录：%s\n" % base)

    for name, urls in SOURCES:
        zp = base / name
        print("[下载] %s" % name)
        if not download(name, urls, zp):
            print("\n[失败] %s 没下下来" % name)
            sys.exit(1)
        print("[解压] %s" % name)
        unzip(zp, base / ("jdk" if name == "jdk17.zip" else name.replace(".zip", "")))

    print("\n工具链就绪。接下来：")
    print("  python package\\build_apk.py")


if __name__ == "__main__":
    main()
