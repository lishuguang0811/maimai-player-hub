# -*- coding: utf-8 -*-
"""
把机台打成一个**单文件 HTML**：双击就能玩、离线可用、手机上全屏。

这个文件同时是三件事的原料：
  · 直接双击打开（浏览器里跑，不需要 Python / Streamlit）
  · exe 打包时塞进去，用 WebView 或浏览器打开
  · APK 里 WebView 加载的 assets/www/index.html

做法很简单：把 modules/dx_cabinet.js 原样内联，再把曲库裁一份内置进去，
外面套一层全屏壳。零外部请求 —— 断网、拷 U 盘、发给别人都能跑。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules import songs  # noqa: E402

OUT_DIR = ROOT / "standalone"
OUT_DIR.mkdir(exist_ok=True)
LIB_LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 400

# ---------------------------------------------------------------- 内置曲库
snap = songs.load_snapshot()
rec = songs.flatten(snap) if snap else []
bucket: dict[str, dict] = {}
for r in rec:
    t = (r.get("title") or "").strip()
    if not t or not r.get("bpm"):
        continue
    try:
        ds = float(r.get("ds") or 0)
    except (TypeError, ValueError):
        ds = 0.0
    if ds <= 0:
        continue
    item = {
        "title": t,
        "artist": (r.get("artist") or "")[:40],
        "bpm": int(r.get("bpm") or 0),
        "ds": round(ds, 1),
    }
    # 一首歌在曲库里有多条（每个难度一条）—— 留定数最高的那条，
    # 这样独立版的曲库才收得进高难度的曲子。
    old = bucket.get(t)
    if old is None or ds > old["ds"]:
        bucket[t] = item
lib = sorted(bucket.values(), key=lambda x: (-x["ds"], x["title"]))[:LIB_LIMIT]

js = (ROOT / "modules" / "dx_cabinet.js").read_text(encoding="utf-8")
lib_json = json.dumps(lib, ensure_ascii=False, separators=(",", ":"))

SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#05080c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>舞萌 DX 机台</title>
<link rel="icon" href="data:,">
<link rel="manifest" href="data:application/manifest+json,%7B%22name%22%3A%22%E8%88%9E%E8%90%8C%20DX%20%E6%9C%BA%E5%8F%B0%22%2C%22short_name%22%3A%22DX%E6%9C%BA%E5%8F%B0%22%2C%22start_url%22%3A%22.%22%2C%22display%22%3A%22fullscreen%22%2C%22orientation%22%3A%22landscape%22%2C%22background_color%22%3A%22%2305080c%22%2C%22theme_color%22%3A%22%2305080c%22%2C%22icons%22%3A%5B%5D%7D">
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;overflow:hidden;background:#05080c;
  font-family:'Segoe UI','Microsoft YaHei',system-ui,sans-serif;color:#dff0ef;
  overscroll-behavior:none;touch-action:none;user-select:none;-webkit-user-select:none}
#wrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
canvas{display:block;background:#05080c;touch-action:none}
#hint{position:fixed;left:0;right:0;bottom:0;padding:6px 10px;font-size:11px;
  color:#6f858c;text-align:center;background:rgba(4,8,12,.72);line-height:1.6;
  pointer-events:none;z-index:5}
#hint b{color:#9fe8e2}
kbd{background:rgba(57,197,187,.16);border:1px solid rgba(57,197,187,.4);border-radius:4px;
  padding:0 4px;font-family:Consolas,monospace;font-size:10px;color:#9fe8e2}
@media (orientation:portrait){#hint{font-size:10px}}
</style>
</head>
<body>
<div id="wrap"><canvas id="dxcv" width="960" height="560"></canvas></div>
<div id="hint">
  <b>↑↓</b> 选曲　<b>←→</b> 选难度　<b>Enter</b> 开打　<b>I</b> 导入谱面　<b>H</b> 键位说明　·
  手机：点圆环方位敲，按住划过去送 SLIDE，点中央屏 = TOUCH
</div>
<script>
var DXLIB = __LIB__;
</script>
<script>
__JS__
</script>
</body>
</html>
"""

html = SHELL.replace("__LIB__", lib_json).replace("__JS__", js)

out = OUT_DIR / "maimai-dx.html"
out.write_text(html, encoding="utf-8")

# 顺手给 APK / exe 一份可直接用的副本
print(f"曲库内置 {len(lib)} 首（定数从高到低）")
print(f"单文件 HTML：{out}  →  {out.stat().st_size / 1024:.0f} KB")
if lib:
    hi = max(lib, key=lambda x: x["ds"])
    print(f"最难的一首：{hi['title']}  ds {hi['ds']}  BPM {hi['bpm']}")
