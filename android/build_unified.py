# -*- coding: utf-8 -*-
"""
合一版 APK 构建 —— 大厅（WebView）+ 原版 AstroDX 安装包，装一个 App 全都有。

和 build_apk.py 的区别：
  1. assets 里多塞一个 astrodx.apk（原版 AstroDX，Unity 原生，约 85MB）
  2. Java 层多一个 ApkProvider（把内置包以 content:// 交给系统安装器）
  3. MainActivity 多一个 window.DXBridge 桥：检测 / 解包 / 拉起安装器 / 一键启动
  4. Manifest 声明 REQUEST_INSTALL_PACKAGES

用法：
    python build_unified.py                # 合一版（默认）
    python build_unified.py --no-dx        # 只有大厅，不带 AstroDX
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "package"
OUTDIR = PKG / "apk"
SRC_JAVA = PKG / "android_src"
DX_APK = PKG / "apk" / "astrodx.apk"

APP_LABEL = "舞萌DX合一版"
PKG_NAME = "com.maimai.hub"
VERSION_CODE = "8"
VERSION_NAME = "4.1.1"
MIN_SDK = "23"
TARGET_SDK = "35"


def die(msg: str) -> "None":
    print("\n[失败] " + msg)
    sys.exit(1)


# ---------------------------------------------------------------- 工具链

def _find(root: Path, name: str, max_depth: int = 4):
    if not root.exists():
        return None
    for p in root.rglob(name):
        if len(p.relative_to(root).parts) <= max_depth:
            return p
    return None


def locate_toolchain() -> dict:
    cands = []
    env = os.environ.get("APK_TOOLCHAIN")
    if env:
        cands.append(Path(env))
    cands += [
        ROOT / ".toolchain",
        ROOT.parent / ".toolchain",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk",
        Path(os.environ.get("ANDROID_HOME", "")),
        Path(os.environ.get("ANDROID_SDK_ROOT", "")),
    ]

    base = None
    for c in cands:
        if c and c.exists():
            base = c
            break
    if base is None:
        die("没找到工具链。先跑 package\\fetch_toolchain.py。")

    jdk = None
    for jh in (os.environ.get("JAVA_HOME"), base / "jdk", base):
        if not jh:
            continue
        p = Path(jh)
        subs = [p] + ([d for d in p.iterdir() if d.is_dir()] if p.is_dir() else [])
        for sub in subs:
            if (sub / "bin" / "javac.exe").exists():
                jdk = sub
                break
        if jdk:
            break
    if jdk is None:
        jc = _find(base, "javac.exe", 5)
        if jc:
            jdk = jc.parent.parent
    if jdk is None:
        die(f"工具链里没有 javac.exe（{base}）")

    aapt2 = _find(base, "aapt2.exe", 5)
    zipalign = _find(base, "zipalign.exe", 5)
    jar = _find(base, "android.jar", 4)
    d8 = _find(base, "d8.jar", 5)
    signer = _find(base, "apksigner.jar", 5)

    missing = [n for n, v in (("aapt2.exe", aapt2), ("zipalign.exe", zipalign),
                              ("android.jar", jar), ("d8.jar", d8),
                              ("apksigner.jar", signer)) if not v]
    if missing:
        die("工具链缺：" + "、".join(missing))

    tc = dict(base=base, jdk=jdk, java=jdk / "bin" / "java.exe",
              javac=jdk / "bin" / "javac.exe", keytool=jdk / "bin" / "keytool.exe",
              aapt2=aapt2, zipalign=zipalign, android_jar=jar, d8=d8, apksigner=signer)
    for k in ("java", "javac", "keytool"):
        if not tc[k].exists():
            die(f"JDK 不完整：{tc[k]}")
    return tc


# ---------------------------------------------------------------- 资源模板

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{pkg}"
    android:versionCode="{code}"
    android:versionName="{name}">

    <uses-sdk android:minSdkVersion="{min}" android:targetSdkVersion="{target}" />

    <!-- 用来拉起系统安装器安装内置的 AstroDX -->
    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />

    <supports-screens
        android:anyDensity="true"
        android:largeScreens="true"
        android:normalScreens="true"
        android:smallScreens="false"
        android:xlargeScreens="true" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:usesCleartextTraffic="false"
        android:theme="@android:style/Theme.Material.NoActionBar"
        android:hardwareAccelerated="true"
        android:largeHeap="true">

        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|screenSize|keyboardHidden|screenLayout|smallestScreenSize|density|fontScale"
            android:exported="true"
            android:launchMode="singleTask"
            android:screenOrientation="sensor"
            android:keepScreenOn="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- 把 filesDir 里的安装包以 content:// 暴露给系统安装器（仅本次授权可读） -->
        <provider
            android:name=".ApkProvider"
            android:authorities="{pkg}.apk"
            android:exported="false"
            android:grantUriPermissions="true" />
    </application>
</manifest>
"""

STRINGS = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{label}</string>
</resources>
"""


def make_icon(path: Path, size: int = 192) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size * 0.04
    d.ellipse([m, m, size - m, size - m], fill=(7, 16, 21, 255))
    d.ellipse([m, m, size - m, size - m], outline=(57, 197, 187, 255), width=max(2, size // 32))

    cx = cy = size / 2
    r_out, r_in = size * 0.34, size * 0.145
    pts = []
    for i in range(10):
        ang = -90 + i * 36
        r = r_out if i % 2 == 0 else r_in
        a = ang * math.pi / 180.0
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=(245, 212, 66, 255))
    img.save(path, "PNG")


# ---------------------------------------------------------------- 执行

def run(cmd, cwd=None, env=None) -> str:
    print("  $", " ".join(str(c) for c in cmd)[:300])
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                       env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stdout[-3000:] if p.stdout else "")
        print(p.stderr[-3000:] if p.stderr else "")
        die("命令失败（exit %d）：%s" % (p.returncode, cmd[0]))
    return p.stdout or ""


def ascii_tmpdir() -> Path:
    def short(p: str) -> str:
        try:
            import ctypes
            f = ctypes.windll.kernel32.GetShortPathNameW
            n = f(p, None, 0)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                if f(p, buf, n + 1):
                    return buf.value
        except Exception:
            pass
        return p

    for cand in (os.environ.get("TMP"), os.environ.get("TEMP"),
                 "C:/Windows/Temp", "C:/Temp"):
        if cand and str(cand).isascii() and Path(cand).is_dir():
            try:
                return Path(tempfile.mkdtemp(prefix="apkbuild_", dir=str(cand)))
            except Exception:
                pass
    d = Path(tempfile.mkdtemp(prefix="apkbuild_"))
    s = short(str(d))
    return Path(s) if str(s).isascii() else d


def pick_web() -> Path:
    d = ROOT / "standalone" / "maimai-web"
    if d.is_dir():
        return d
    die("standalone/maimai-web 不存在")


def main() -> None:
    with_dx = "--no-dx" not in sys.argv
    label = APP_LABEL if with_dx else "舞萌DX大厅"

    if with_dx:
        if not DX_APK.exists():
            die("缺少 %s —— 先下载原版 AstroDX 安装包放到 package/apk/astrodx.apk" % DX_APK)
        # 完整性粗检：zip 结尾必须有 EOCD
        with open(DX_APK, "rb") as fh:
            head = fh.read(4)
            fh.seek(-22, os.SEEK_END)
            tail = fh.read(2)
        if head[:2] != b"PK" or tail != b"PK":
            die("astrodx.apk 不是完整的 zip/APK，可能没下完")

    tc = locate_toolchain()
    web = pick_web()

    print("工具链：", tc["base"])
    print("JDK    ：", tc["jdk"])
    print("大厅   ：", web.name)
    if with_dx:
        print("AstroDX：%s（%.1f MB）" % (DX_APK.name, DX_APK.stat().st_size / 1048576))
    print()

    work = ascii_tmpdir()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # --- 1. 铺源码树 -------------------------------------------------------
    (work / "res" / "values").mkdir(parents=True, exist_ok=True)
    (work / "res" / "mipmap-xxhdpi").mkdir(parents=True, exist_ok=True)
    (work / "assets" / "www").mkdir(parents=True, exist_ok=True)
    java_out = work / "src" / "com" / "maimai" / "hub"
    java_out.mkdir(parents=True, exist_ok=True)

    (work / "AndroidManifest.xml").write_text(
        MANIFEST.format(pkg=PKG_NAME, code=VERSION_CODE, name=VERSION_NAME,
                        min=MIN_SDK, target=TARGET_SDK), encoding="utf-8")
    (work / "res" / "values" / "strings.xml").write_text(
        STRINGS.format(label=label), encoding="utf-8")
    make_icon(work / "res" / "mipmap-xxhdpi" / "ic_launcher.png")

    shutil.copytree(str(web), str(work / "assets" / "www"), dirs_exist_ok=True)

    if with_dx:
        shutil.copyfile(DX_APK, work / "assets" / "astrodx.apk")

    java_files = []
    for jf in SRC_JAVA.rglob("*.java"):
        dst = java_out / jf.name
        shutil.copyfile(jf, dst)
        java_files.append(dst)
    if not java_files:
        die("android_src 下没有 .java")

    print("[1/7] 源码树铺好了：%d 个 Java 文件" % len(java_files))

    env = dict(os.environ)
    env["JAVA_HOME"] = str(tc["jdk"])
    env["PATH"] = str(tc["jdk"] / "bin") + os.pathsep + env.get("PATH", "")

    # --- 2. aapt2 compile --------------------------------------------------
    run([tc["aapt2"], "compile", "--dir", work / "res", "-o", work / "compiled.zip"])
    print("[2/7] 资源编译完成")

    # --- 3. aapt2 link -----------------------------------------------------
    # .apk 必须以 STORED 存进 assets：系统安装器要能直接 seek/mmap，
    # 而且 88MB 走解压流容易在老机器上 OOM。
    zero_compress = ["-0", "html", "-0", "apk"] if with_dx else ["-0", "html"]
    base_apk = work / "base.apk"
    link = [tc["aapt2"], "link",
            "-I", tc["android_jar"],
            "--auto-add-overlay",
            "--manifest", work / "AndroidManifest.xml",
            "--min-sdk-version", MIN_SDK,
            "--target-sdk-version", TARGET_SDK,
            "--version-code", VERSION_CODE,
            "--version-name", VERSION_NAME,
            "-A", work / "assets"] + zero_compress + [
            "-o", base_apk,
            work / "compiled.zip"]
    run(link)
    print("[3/7] 资源链接完成 → base.apk")

    # --- 4. javac ----------------------------------------------------------
    obj = work / "obj"
    obj.mkdir()
    run([tc["javac"], "-encoding", "UTF-8", "-nowarn",
         "-source", "8", "-target", "8",
         "-bootclasspath", tc["android_jar"],
         "-d", obj] + java_files)
    print("[4/7] Java 编译完成")

    # --- 5. d8 → dex -------------------------------------------------------
    dexdir = work / "dex"
    dexdir.mkdir()
    classes = [str(p) for p in obj.rglob("*.class")]
    run([tc["java"], "-Xmx2g", "-cp", tc["d8"], "com.android.tools.r8.D8",
         "--lib", tc["android_jar"], "--min-api", MIN_SDK,
         "--output", dexdir] + classes)
    dex = dexdir / "classes.dex"
    if not dex.exists():
        die("d8 没产出 classes.dex")
    with zipfile.ZipFile(base_apk, "a", zipfile.ZIP_DEFLATED) as z:
        if "classes.dex" not in z.namelist():
            z.writestr(zipfile.ZipInfo("classes.dex", (2026, 1, 1, 0, 0, 0)),
                       dex.read_bytes(), zipfile.ZIP_STORED)
    print("[5/7] dex 生成完成（%d 字节）" % dex.stat().st_size)

    # --- 6. zipalign -------------------------------------------------------
    aligned = work / "aligned.apk"
    run([tc["zipalign"], "-f", "-p", "4", base_apk, aligned])
    print("[6/7] 对齐完成")

    # --- 7. 签名 -----------------------------------------------------------
    ks = OUTDIR / "debug.keystore"
    if not ks.exists():
        run([tc["keytool"], "-genkeypair", "-v",
             "-keystore", ks, "-storetype", "PKCS12",
             "-storepass", "android", "-alias", "androiddebugkey",
             "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "10950",
             "-dname", "CN=Android Debug, OU=Maimai, O=Android, L=CN, ST=CN, C=CN"])

    final_name = "%s-%s.apk" % (label.replace(" ", ""), VERSION_NAME)
    out_apk = work / final_name
    if out_apk.exists():
        out_apk.unlink()
    run([tc["java"], "-Xmx3g", "-cp", tc["apksigner"], "com.android.apksigner.ApkSignerTool",
         "sign",
         "--ks", ks, "--ks-type", "PKCS12",
         "--ks-pass", "pass:android", "--key-pass", "pass:android",
         "--v1-signing-enabled", "true",
         "--v2-signing-enabled", "true",
         "--v3-signing-enabled", "true",
         "--out", out_apk,
         "--in", aligned])
    print("[7/7] 签名完成")

    # --- 校验 --------------------------------------------------------------
    print()
    print(run([tc["java"], "-cp", tc["apksigner"], "com.android.apksigner.ApkSignerTool",
               "verify", "--print-certs", "--verbose", out_apk]).strip()[-900:])
    print()
    badge = run([tc["aapt2"], "dump", "badging", out_apk])
    for line in badge.splitlines():
        if line.startswith(("package:", "application-label:", "sdkVersion:",
                            "targetSdkVersion:", "launchable-activity:",
                            "uses-permission")):
            print("  " + line)

    with zipfile.ZipFile(out_apk) as z:
        infos = {i.filename: i for i in z.infolist()}
    need = ["AndroidManifest.xml", "classes.dex", "resources.arsc",
            "assets/www/index.html", "assets/www/app.js", "assets/www/dxsrc.js",
            "assets/www/chart.js", "assets/www/data.js", "META-INF/MANIFEST.MF"]
    if with_dx:
        need.append("assets/astrodx.apk")
    for n in need:
        ok = n in infos
        print(("  ✓ " if ok else "  ✗ ") + n)
    if with_dx and "assets/astrodx.apk" in infos:
        i = infos["assets/astrodx.apk"]
        stored = (i.compress_type == zipfile.ZIP_STORED)
        print("    内置包 %.1f MB，存储方式：%s" % (i.file_size / 1048576,
                                              "STORED(可直接 mmap)" if stored else "DEFLATED"))

    dest = OUTDIR / final_name
    shutil.copyfile(out_apk, dest)
    print()
    print("=" * 62)
    print("APK 出来了：%s" % dest)
    print("大小：%.1f MB" % (dest.stat().st_size / 1048576))
    print("=" * 62)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
