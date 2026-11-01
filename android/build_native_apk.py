# -*- coding: utf-8 -*-
"""
打「真原生」APK —— Java 引擎 + SurfaceView + AudioTrack，不套 WebView。

流程跟 build_apk.py 一样：aapt2 compile → aapt2 link → javac → d8 → 塞 dex
→ zipalign → apksigner。只是这次编的是 package/native/src 下面那一整套
游戏代码，不是一份 HTML。

用法：
    python package/build_native_apk.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "package"
NATIVE = PKG / "native"
OUTDIR = PKG / "apk"

APP_LABEL = "舞萌 DX"
PKG_NAME = "com.maimai.dx"
MIN_SDK = "23"

sys.path.insert(0, str(PKG))
from build_apk import ascii_tmpdir, locate_toolchain, make_icon, run  # noqa: E402


def main() -> None:
    tc = locate_toolchain()
    print("工具链：", tc["base"])
    print("JDK    ：", tc["jdk"])
    print()

    work = ascii_tmpdir()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    src = work / "src"
    shutil.copytree(NATIVE / "src", src)
    shutil.copyfile(NATIVE / "AndroidManifest.xml", work / "AndroidManifest.xml")
    (work / "res" / "values").mkdir(parents=True, exist_ok=True)
    (work / "res" / "mipmap-xxhdpi").mkdir(parents=True, exist_ok=True)
    (work / "res" / "values" / "strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n    <string name="app_name">%s</string>\n</resources>\n' % APP_LABEL,
        encoding="utf-8")
    make_icon(work / "res" / "mipmap-xxhdpi" / "ic_launcher.png", 192)

    n_java = len(list((src).rglob("*.java")))
    print("[1/7] 源码就位：%d 个 java 文件" % n_java)

    env = dict(__import__("os").environ)
    env["JAVA_HOME"] = str(tc["jdk"])
    env["PATH"] = str(tc["jdk"] / "bin") + __import__("os").pathsep + env.get("PATH", "")

    run([tc["aapt2"], "compile", "--dir", work / "res", "-o", work / "compiled.zip"])
    print("[2/7] 资源编译完成")

    base_apk = work / "base.apk"
    run([tc["aapt2"], "link",
         "-I", tc["android_jar"],
         "--auto-add-overlay",
         "--manifest", work / "AndroidManifest.xml",
         "--min-sdk-version", MIN_SDK,
         "--target-sdk-version", "35",
         "-o", base_apk,
         work / "compiled.zip"])
    print("[3/7] 资源链接完成")

    obj = work / "obj"
    obj.mkdir()
    files = [str(p) for p in sorted(src.rglob("*.java"))]
    run([tc["javac"], "-encoding", "UTF-8", "-nowarn",
         "-source", "8", "-target", "8",
         "-bootclasspath", tc["android_jar"],
         "-d", obj] + files)
    print("[4/7] Java 编译完成（%d 个源文件）" % len(files))

    dexdir = work / "dex"
    dexdir.mkdir()
    classes = [str(p) for p in obj.rglob("*.class")]
    run([tc["java"], "-cp", tc["d8"], "com.android.tools.r8.D8",
         "--lib", tc["android_jar"], "--min-api", MIN_SDK,
         "--output", dexdir] + classes)
    dex = dexdir / "classes.dex"
    if not dex.exists():
        print("[失败] d8 没产出 classes.dex")
        sys.exit(1)
    with zipfile.ZipFile(base_apk, "a", zipfile.ZIP_DEFLATED) as z:
        if "classes.dex" not in z.namelist():
            z.writestr(zipfile.ZipInfo("classes.dex", (2026, 1, 1, 0, 0, 0)),
                       dex.read_bytes(), zipfile.ZIP_STORED)
    print("[5/7] dex：%d 字节 / %d 个 class" % (dex.stat().st_size, len(classes)))

    aligned = work / "aligned.apk"
    run([tc["zipalign"], "-f", "-p", "4", base_apk, aligned])
    print("[6/7] 对齐完成")

    ks = OUTDIR / "debug.keystore"
    if not ks.exists():
        run([tc["keytool"], "-genkeypair", "-v",
             "-keystore", ks, "-storetype", "PKCS12",
             "-storepass", "android", "-alias", "androiddebugkey",
             "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "10950",
             "-dname", "CN=Android Debug, OU=Maimai, O=Android, L=CN, ST=CN, C=CN"])

    final_name = "舞萌DX-原生版.apk"
    out_apk = work / final_name
    run([tc["java"], "-cp", tc["apksigner"], "com.android.apksigner.ApkSignerTool",
         "sign", "--ks", ks, "--ks-type", "PKCS12",
         "--ks-pass", "pass:android", "--key-pass", "pass:android",
         "--v1-signing-enabled", "true",
         "--v2-signing-enabled", "true",
         "--v3-signing-enabled", "true",
         "--out", out_apk, "--in", aligned])
    print("[7/7] 签名完成")

    print()
    print(run([tc["java"], "-cp", tc["apksigner"], "com.android.apksigner.ApkSignerTool",
               "verify", "--print-certs", out_apk]).strip())
    for line in run([tc["aapt2"], "dump", "badging", out_apk]).splitlines():
        if line.startswith(("package:", "application-label:", "sdkVersion:",
                            "targetSdkVersion:", "launchable-activity:",
                            "uses-feature:", "supports-screens:")):
            print("  " + line)

    with zipfile.ZipFile(out_apk) as z:
        names = z.namelist()
    for n in ("AndroidManifest.xml", "classes.dex", "resources.arsc",
              "META-INF/MANIFEST.MF"):
        print(("  ✓ " if n in names else "  ✗ ") + n)

    dest = OUTDIR / final_name
    shutil.copyfile(out_apk, dest)
    print()
    print("=" * 62)
    print("原生 APK：%s" % dest)
    print("大小：%.2f MB" % (dest.stat().st_size / 1048576))
    print("=" * 62)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
