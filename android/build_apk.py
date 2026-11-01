# -*- coding: utf-8 -*-
"""
直接编 APK —— 不装 Android Studio、不用 Gradle、不联网。

原理：APK 本质上就是一个 zip。官方工具链里真正必需的只有四样东西，
我们从 Google / Microsoft 的官方分发包里直接取出来用：

    aapt2.exe     Android SDK build-tools  → 编译资源、生成二进制 manifest
    android.jar   Android SDK platform     → 编译 Java 时的 android 类库
    d8.jar        build-tools              → class → dex
    zipalign.exe  build-tools              → 4 字节对齐
    apksigner.jar build-tools              → v1+v2+v3 签名
    javac/java    JDK 17                   → 编译 Java、跑上面这些 jar

流程：aapt2 compile → aapt2 link → javac → d8 → 塞 dex → zipalign → apksigner。
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

APP_LABEL = "舞萌 DX 大厅"
PKG_NAME = "com.maimai.hub"
VERSION_CODE = "5"
VERSION_NAME = "3.2.0"
MIN_SDK = "23"
TARGET_SDK = "35"


def die(msg: str) -> "None":
    print("\n[失败] " + msg)
    sys.exit(1)


# ---------------------------------------------------------------- 工具链定位

def _find(root: Path, name: str, max_depth: int = 4):
    """在 root 下找名字为 name 的文件，返回第一个命中的路径。"""
    if not root.exists():
        return None
    for p in root.rglob(name):
        if len(p.relative_to(root).parts) <= max_depth:
            return p
    return None


def locate_toolchain() -> dict:
    """找齐 javac / aapt2 / android.jar / zipalign / d8.jar / apksigner.jar。"""
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

    tc = {}
    base = None
    for c in cands:
        if c and c.exists():
            base = c
            break
    if base is None:
        die("没找到工具链。先跑 package\\fetch_toolchain.py 把 JDK 和 build-tools 拉下来。")

    # JDK：优先 JAVA_HOME，其次工具链里的 jdk 目录
    jdk = None
    for jh in (os.environ.get("JAVA_HOME"), base / "jdk", base):
        if not jh:
            continue
        p = Path(jh)
        for sub in (p, *([d for d in p.iterdir() if d.is_dir()] if p.is_dir() else [])):
            if (sub / "bin" / "javac.exe").exists():
                jdk = sub
                break
        if jdk:
            break
    if jdk is None:
        jdk = (_find(base, "javac.exe", 5) or None)
        if jdk:
            jdk = jdk.parent.parent
    if jdk is None:
        die(f"工具链里没有 javac.exe（{base}）。跑 package\\fetch_toolchain.py 补一个 JDK。")

    aapt2 = _find(base, "aapt2.exe", 5)
    zipalign = _find(base, "zipalign.exe", 5)
    jar = _find(base, "android.jar", 4)
    d8 = _find(base, "d8.jar", 5)
    signer = _find(base, "apksigner.jar", 5)

    missing = [n for n, v in (("aapt2.exe", aapt2), ("zipalign.exe", zipalign),
                              ("android.jar", jar), ("d8.jar", d8),
                              ("apksigner.jar", signer)) if not v]
    if missing:
        die("工具链缺：" + "、".join(missing) + f"（在 {base} 下没找到）")

    tc.update(base=base, jdk=jdk, java=jdk / "bin" / "java.exe",
              javac=jdk / "bin" / "javac.exe", keytool=jdk / "bin" / "keytool.exe",
              aapt2=aapt2, zipalign=zipalign, android_jar=jar, d8=d8, apksigner=signer)
    for k in ("java", "javac", "keytool"):
        if not tc[k].exists():
            die(f"JDK 不完整：{tc[k]} 不存在")
    return tc


# ---------------------------------------------------------------- 源码素材

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{pkg}"
    android:versionCode="{code}"
    android:versionName="{name}">

    <uses-sdk android:minSdkVersion="{min}" android:targetSdkVersion="{target}" />
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
        android:hardwareAccelerated="true">
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
    </application>
</manifest>
"""

STRINGS = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{label}</string>
</resources>
"""

MAIN_JAVA = r"""package com.maimai.hub;

import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView webView;

    private void immersive() {
        View d = getWindow().getDecorView();
        int f = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
        d.setSystemUiVisibility(f);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window w = getWindow();
        w.setStatusBarColor(Color.rgb(7, 16, 21));
        w.setNavigationBarColor(Color.rgb(7, 16, 21));
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        w.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(7, 16, 21));
        setContentView(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        s.setLayoutAlgorithm(WebSettings.LayoutAlgorithm.NORMAL);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            s.setSafeBrowsingEnabled(false);
        }

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient());

        immersive();
        webView.loadUrl("file:///android_asset/www/index.html");
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) immersive();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webView != null) webView.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.setWebViewClient(null);
            webView.setWebChromeClient(null);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView != null && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
"""


def make_icon(path: Path, size: int = 192) -> None:
    """画个和机台同色的图标：深色圆盘 + 金色五角星。"""
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


# ---------------------------------------------------------------- 主流程

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
    """aapt2 是原生程序，路径里有非 ASCII 字符会打不开目录 —— 必须落在纯 ASCII 目录里。
    这台机器用户名是中文，Temp 默认路径就带中文，所以要专门挑一个。"""
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


def pick_html() -> Path:
    """纯前端版：把整个 maimai-web 目录（index.html + 4 个 js）塞进 assets/www。"""
    d = ROOT / "standalone" / "maimai-web"
    if d.is_dir():
        return d
    die("standalone/maimai-web 目录不存在，先准备好纯前端工程（index.html/data.js/dxsrc.js/chart.js/app.js）")


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else APP_LABEL
    tc = locate_toolchain()
    html = pick_html()

    print("工具链：", tc["base"])
    print("JDK    ：", tc["jdk"])
    print("原料   ：", html.name, "（%.0f KB）" % (html.stat().st_size / 1024))
    print()

    work = ascii_tmpdir()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # --- 1. 铺源码树 -------------------------------------------------------
    (work / "res" / "values").mkdir(parents=True, exist_ok=True)
    (work / "res" / "mipmap-xxhdpi").mkdir(parents=True, exist_ok=True)
    (work / "assets" / "www").mkdir(parents=True, exist_ok=True)
    (work / "src" / "com" / "maimai" / "hub").mkdir(parents=True, exist_ok=True)

    (work / "AndroidManifest.xml").write_text(
        MANIFEST.format(pkg=PKG_NAME, code=VERSION_CODE, name=VERSION_NAME,
                        min=MIN_SDK, target=TARGET_SDK), encoding="utf-8")
    (work / "res" / "values" / "strings.xml").write_text(
        STRINGS.format(label=label), encoding="utf-8")
    (work / "src" / "com" / "maimai" / "hub" / "MainActivity.java").write_text(
        MAIN_JAVA, encoding="utf-8")
    make_icon(work / "res" / "mipmap-xxhdpi" / "ic_launcher.png")
    # 纯前端：把整个 maimai-web 目录拷进 assets/www（index.html + data.js/dxsrc.js/chart.js/app.js）
    shutil.copytree(str(html), str(work / "assets" / "www"), dirs_exist_ok=True)
    print("[1/7] 源码树铺好了：%s" % work)

    env = dict(os.environ)
    env["JAVA_HOME"] = str(tc["jdk"])
    env["PATH"] = str(tc["jdk"] / "bin") + os.pathsep + env.get("PATH", "")

    # --- 2. aapt2 compile --------------------------------------------------
    run([tc["aapt2"], "compile", "--dir", work / "res", "-o", work / "compiled.zip"])
    print("[2/7] 资源编译完成")

    # --- 3. aapt2 link -----------------------------------------------------
    base_apk = work / "base.apk"
    run([tc["aapt2"], "link",
         "-I", tc["android_jar"],
         "--auto-add-overlay",
         "--manifest", work / "AndroidManifest.xml",
         "--min-sdk-version", MIN_SDK,
         "--target-sdk-version", TARGET_SDK,
         "--version-code", VERSION_CODE,
         "--version-name", VERSION_NAME,
         "-A", work / "assets",
         "-0", "html",                      # html 不压缩，避免 AssetManager 的解压缩上限
         "-o", base_apk,
         work / "compiled.zip"])
    print("[3/7] 资源链接完成 → base.apk")

    # --- 4. javac ----------------------------------------------------------
    obj = work / "obj"
    obj.mkdir()
    run([tc["javac"], "-encoding", "UTF-8", "-nowarn",
         "-source", "8", "-target", "8",
         "-bootclasspath", tc["android_jar"],
         "-d", obj,
         work / "src" / "com" / "maimai" / "hub" / "MainActivity.java"])
    print("[4/7] Java 编译完成")

    # --- 5. d8 → dex -------------------------------------------------------
    dexdir = work / "dex"
    dexdir.mkdir()
    classes = [str(p) for p in obj.rglob("*.class")]
    run([tc["java"], "-cp", tc["d8"], "com.android.tools.r8.D8",
         "--lib", tc["android_jar"], "--min-api", MIN_SDK,
         "--output", dexdir] + classes)
    dex = dexdir / "classes.dex"
    if not dex.exists():
        die("d8 没产出 classes.dex")
    # dex 用 STORED 写进去（Android 可以直接 mmap，装起来也快）
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

    # 签名产物先落在 ASCII 目录（aapt2 校验要用），最后再拷回工程目录
    final_name = "%s-%s.apk" % (label.replace(" ", ""), VERSION_NAME)
    out_apk = work / final_name
    if out_apk.exists():
        out_apk.unlink()
    run([tc["java"], "-cp", tc["apksigner"], "com.android.apksigner.ApkSignerTool",
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
               "verify", "--print-certs", "--verbose", out_apk]).strip()[-1200:])
    print()
    badge = run([tc["aapt2"], "dump", "badging", out_apk])
    for line in badge.splitlines():
        if line.startswith(("package:", "application-label:", "sdkVersion:",
                            "targetSdkVersion:", "launchable-activity:")):
            print("  " + line)

    with zipfile.ZipFile(out_apk) as z:
        names = z.namelist()
    need = ["AndroidManifest.xml", "classes.dex", "resources.arsc",
            "assets/www/index.html", "META-INF/MANIFEST.MF"]
    for n in need:
        print(("  ✓ " if n in names else "  ✗ ") + n)

    dest = OUTDIR / final_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out_apk, dest)
    print()
    print("=" * 62)
    print("APK 出来了：%s" % dest)
    print("大小：%.1f MB" % (dest.stat().st_size / 1048576))
    print("=" * 62)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
