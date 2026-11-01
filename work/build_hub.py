# -*- coding: utf-8 -*-
"""
把整个应用整合进一个**单文件 HTML 大厅**：
    🕹 机台（全屏，带声音、星星 SLIDE、Simai 导入）
    🎮 20 个小游戏（全部离线自包含）
    🎼 曲库（400 首，能搜、能直接开打）
    🏆 成绩 / ⚙ 设置 / 🎴 今日运势 / ❓ 说明

产出 standalone/maimai-hub.html —— 双击就能玩，离线、零外部请求。
电脑用它打 exe，手机用它打 APK（也可以直接加到主屏幕当 app）。
"""
from __future__ import annotations

import base64
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules import arcade, songs  # noqa: E402

OUT_DIR = ROOT / "standalone"
OUT_DIR.mkdir(exist_ok=True)
LIB_LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 400

# ---------------------------------------------------------------- 内置曲库
snap = songs.load_snapshot()
rec = songs.flatten(snap) if snap else []
bucket: dict[str, dict] = {}
_rng = random.Random("hub-lib")
for r in rec:
    t = (r.get("title") or "").strip()
    if not t or not r.get("bpm"):
        continue
    try:
        ds = float(r.get("ds") or 0)
    except (TypeError, ValueError):
        continue
    if ds <= 0:
        continue
    item = {"title": t, "artist": (r.get("artist") or "")[:40],
            "bpm": int(r.get("bpm") or 0), "ds": round(ds, 1),
            "genre": (r.get("genre") or "")[:16]}
    old = bucket.get(t)
    if old is None or ds > old["ds"]:
        bucket[t] = item
lib = sorted(bucket.values(), key=lambda x: (-x["ds"], x["title"]))[:LIB_LIMIT]

titles = [x["title"] for x in lib]


def _w(html: str, default: int = 900) -> int:
    """
    游戏的「设计宽度」。大部分小游戏的 canvas 是固定像素、居中显示的
    （比如 360×440），所以视口只要比 canvas 稍宽一点就够；拿这个当基准，
    手机窄屏按它等比缩小，整个游戏都能完整看到。
    """
    m = re.search(r"<canvas[^>]*?width=[\"']?(\d+)", html)
    cw = int(m.group(1)) if m else 640
    return max(360, min(900, cw + 48))


GAMES: list[dict] = []


def add(gid: str, name: str, cat: str, html: str, h: int) -> None:
    GAMES.append({"id": gid, "name": name, "cat": cat, "html": html,
                  "w": _w(html), "h": h})


# ---------------------------------------------------------------- 20 个小游戏
add("rhythm", "🎵 节奏判定", "🎵 节奏手感", arcade.rhythm_html(), 640)
add("tap", "⚡ 打 NOTE", "🎵 节奏手感", arcade.tap_html(), 580)
add("offset", "🎚 判定偏移校准", "🎵 节奏手感", arcade.offset_html(), 560)

add("judge", "🎚 判定偏移挑战", "🎚 判定与手感", arcade.judge_html(), 660)
add("chord", "🤝 双押拆解", "🎚 判定与手感", arcade.chord_html(), 680)
add("survive", "💥 连击生存", "🎚 判定与手感", arcade.survive_html(), 700)

add("simon", "🧠 音符记忆", "🧠 记忆脑力", arcade.simon_html(), 600)
add("memory", "🃏 曲名翻牌", "🧠 记忆脑力",
    arcade.memory_html(_rng.sample(titles, min(8, len(titles)))), 640)
add("echo", "🔁 谱面记忆复述", "🧠 记忆脑力", arcade.echo_html(), 620)

add("type", "⌨️ 曲名打字", "🎯 曲库知识",
    arcade.type_html(_rng.sample(titles, min(60, len(titles)))), 560)

add("merge", "🔢 2048", "🕹 消磨时间", arcade.merge_html(), 720)
add("drop", "🟦 NOTE 落块", "🕹 消磨时间", arcade.drop_html(), 640)
add("snake", "🐍 音符蛇", "🕹 消磨时间", arcade.snake_html(), 600)

# 需要素材的两个：插画拼图内联一张原创插画，回忆回廊取几句主线台词
_miku = sorted((ROOT / "data" / "miku").glob("*.jpg"))[:1]
if _miku:
    b64 = base64.b64encode(_miku[0].read_bytes()).decode("ascii")
    add("puzzle", "🧩 插画拼图", "🕹 消磨时间", arcade.puzzle_html(b64, 3), 620)
try:
    from modules import galgame  # noqa: E402
    _lines = galgame.mainline_lines(8)
    if _lines:
        add("recall", "📖 回忆回廊", "🕹 消磨时间", arcade.recall_html(_lines), 620)
except Exception as _e:                                        # noqa: BLE001
    print("（跳过回忆回廊：", _e, "）")

add("steady", "🥁 节奏稳定性", "📖 读谱与手速", arcade.steady_html(), 600)
add("stamina", "🔥 连打耐力", "📖 读谱与手速", arcade.stamina_html(), 600)
add("score", "📊 成绩可视化", "📖 读谱与手速", arcade.score_html([]), 640)

_card = arcade.bingo_cards(lib, "hub-card")
if _card:
    add("bingo", "🎱 曲库宾果", "🎱 曲库宾果", arcade.bingo_html(_card), 700)

add("ambience", "🎧 氛围音", "🎴 今日运势", arcade.ambience_html(), 200)

# ---------------------------------------------------------------- 机台引擎
js = (ROOT / "modules" / "dx_cabinet.js").read_text(encoding="utf-8")


def jdump(obj) -> str:
    """注入用的 JSON。'</' 必须转义，否则会把外层的 <script> 提前关掉。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


SHELL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#05080c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>舞萌 DX 大厅</title>
<link rel="icon" href="data:,">
<link rel="manifest" href="data:application/manifest+json,%7B%22name%22%3A%22%E8%88%9E%E8%90%8C%20DX%20%E5%A4%A7%E5%8E%85%22%2C%22short_name%22%3A%22DX%E5%A4%A7%E5%8E%85%22%2C%22start_url%22%3A%22.%22%2C%22display%22%3A%22fullscreen%22%2C%22orientation%22%3A%22any%22%2C%22background_color%22%3A%22%2305080c%22%2C%22theme_color%22%3A%22%2305080c%22%2C%22icons%22%3A%5B%5D%7D">
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;overflow:hidden;background:#05080c;color:#dff0ef;
  font-family:'Segoe UI','Microsoft YaHei',system-ui,sans-serif;
  overscroll-behavior:none;user-select:none;-webkit-user-select:none}
:root{--cy:#39C5BB;--star:#F5D442;--line:rgba(57,197,187,.22)}
#bar{position:fixed;left:0;right:0;top:0;z-index:30;display:flex;align-items:center;gap:8px;
  padding:8px 10px;background:rgba(6,12,17,.94);border-bottom:1px solid var(--line);
  backdrop-filter:blur(6px)}
#brand{font-weight:700;font-size:14px;color:var(--cy);white-space:nowrap}
#tabs{display:flex;gap:6px;overflow-x:auto;flex:1;scrollbar-width:none}
#tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;border:1px solid var(--line);background:rgba(57,197,187,.06);
  color:#a9c4c8;border-radius:999px;padding:5px 12px;font-size:12px;cursor:pointer}
.tab.on{background:var(--cy);color:#04252a;border-color:var(--cy);font-weight:700}
#main{position:absolute;left:0;right:0;bottom:0;top:47px;overflow:hidden}
.pane{position:absolute;inset:0;display:none;overflow:auto;-webkit-overflow-scrolling:touch}
.pane.on{display:block}
body.cab #bar{display:none}
body.cab #main{top:0}
.pane::-webkit-scrollbar{width:6px}
.pane::-webkit-scrollbar-thumb{background:rgba(57,197,187,.3);border-radius:3px}

/* ---- 机台 ---- */
#p-cab{overflow:hidden;background:#05080c}
#cvwrap{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
#dxcv{display:block;background:#05080c;touch-action:none}
#backhome{position:fixed;left:10px;top:10px;z-index:40;display:none;
  border:1px solid var(--line);background:rgba(6,12,17,.8);color:#9fe8e2;
  border-radius:999px;padding:6px 14px;font-size:12px;cursor:pointer}
body.cab #backhome{display:block}

/* ---- 小游戏 ---- */
#gamebar{display:flex;gap:6px;overflow-x:auto;padding:8px 10px;scrollbar-width:none;
  border-bottom:1px solid var(--line);background:rgba(8,14,19,.9);
  position:sticky;top:0;z-index:5}
#gamebar::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;border:1px solid var(--line);background:rgba(57,197,187,.05);
  color:#a9c4c8;border-radius:999px;padding:5px 11px;font-size:12px;cursor:pointer;white-space:nowrap}
.chip.on{background:var(--cy);color:#04252a;border-color:var(--cy);font-weight:700}
#gamebox{position:relative;width:100%;height:calc(100% - 43px);overflow:hidden}
#gframe{position:absolute;left:50%;top:0;transform-origin:top center;
  border:0;background:#070d12;width:900px;height:600px}

/* ---- 通用内容 ---- */
.wrap{padding:12px 14px 40px;max-width:980px;margin:0 auto}
h2{font-size:15px;color:var(--cy);margin:14px 0 8px}
.note{background:rgba(57,197,187,.07);border:1px solid var(--line);border-radius:10px;
  padding:10px 12px;font-size:12px;line-height:1.75;color:#bcd6d9}
.note b{color:#9fe8e2}
input[type=text],select{background:#0b141a;border:1px solid var(--line);color:#dff0ef;
  border-radius:8px;padding:8px 10px;font-size:13px;width:100%}
input[type=range]{width:100%;accent-color:#39C5BB}
.btn{border:1px solid var(--line);background:rgba(57,197,187,.1);color:#9fe8e2;
  border-radius:8px;padding:7px 14px;font-size:12px;cursor:pointer}
.btn.pri{background:var(--cy);color:#04252a;font-weight:700;border-color:var(--cy)}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:6px 8px;border-bottom:1px solid rgba(57,197,187,.12);text-align:left}
th{color:#7f9aa0;font-weight:600}
.song{display:flex;align-items:center;gap:8px;padding:8px 10px;
  border-bottom:1px solid rgba(57,197,187,.10)}
.song .t{flex:1;min-width:0;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.song .m{font-size:11px;color:#7f9aa0;white-space:nowrap}
.ds{color:var(--star);font-weight:700}
.play{border:1px solid var(--cy);background:rgba(57,197,187,.14);color:#9fe8e2;
  border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.card{border:1px solid var(--line);border-radius:10px;padding:10px;background:rgba(57,197,187,.05);
  cursor:pointer;font-size:12px}
.card:hover{background:rgba(57,197,187,.14)}
.card .c{font-size:11px;color:#7f9aa0;margin-top:3px}
#hint{position:fixed;left:0;right:0;bottom:0;z-index:20;padding:5px 10px;font-size:11px;
  color:#6f858c;text-align:center;background:rgba(4,8,12,.8);pointer-events:none;display:none}
body.cab #hint{display:block}
.lucky{font-size:22px;text-align:center;padding:18px 0;color:var(--star);font-weight:700}
@media (max-width:560px){#brand{display:none}.wrap{padding:10px 10px 40px}}
</style>
</head>
<body>
<div id="bar">
  <div id="brand">舞萌 DX 大厅</div>
  <div id="tabs"></div>
</div>
<button id="backhome">← 回大厅</button>

<div id="main">
  <section class="pane" id="p-cab"><div id="cvwrap"><canvas id="dxcv" width="960" height="560"></canvas></div></section>

  <section class="pane" id="p-game">
    <div id="gamebar"></div>
    <div id="gamebox"><iframe id="gframe" title="game"
      sandbox="allow-scripts allow-same-origin allow-modals"></iframe></div>
  </section>

  <section class="pane" id="p-lib">
    <div class="wrap">
      <div class="note">内置 <b>__N__</b> 首真实曲目（定数取每首歌最高的那条）。
        搜到哪首就点「开打」，直接按难度生成谱面进机台 —— 同一首同一个难度<b>永远同一张谱</b>，能刷分。</div>
      <div class="row" style="margin-top:10px">
        <input type="text" id="q" placeholder="🔍 搜曲名或艺人" style="flex:2;min-width:160px">
        <select id="dsf" style="flex:1;min-width:120px">
          <option value="0">全部定数</option>
          <option value="1">≤ 9（新手）</option>
          <option value="2">9 ~ 12</option>
          <option value="3">12 ~ 13.5</option>
          <option value="4">≥ 13.5（高手）</option>
        </select>
      </div>
      <div id="list" style="margin-top:10px"></div>
      <div style="text-align:center;margin-top:12px"><button class="btn" id="more">再往下翻 100 首</button></div>
    </div>
  </section>

  <section class="pane" id="p-score">
    <div class="wrap">
      <div class="note">这里读的是<b>本机浏览器里存的个人最佳</b>（按 曲+难度 记），
        打完一局机台就会写进来。换浏览器/清缓存会没有，这是纯离线版的边界。</div>
      <h2>🏆 我的最佳</h2>
      <div id="best"></div>
      <div style="margin-top:14px"><button class="btn" id="clr">清空全部成绩</button></div>
    </div>
  </section>

  <section class="pane" id="p-set">
    <div class="wrap">
      <h2>⚙ 机台设置</h2>
      <div class="note">改完立刻生效，和机台里的设置是同一份（存在本机浏览器里）。</div>
      <div style="margin-top:12px">
        <div>音符速度 <span id="v_speed" class="ds"></span></div>
        <input type="range" id="s_speed" min="60" max="200" step="5">
        <div style="margin-top:12px">判定偏移 <span id="v_off" class="ds"></span> ms（总觉得自己偏早就调负）</div>
        <input type="range" id="s_off" min="-150" max="150" step="1">
        <div style="margin-top:12px">伴奏音量 <span id="v_vol" class="ds"></span></div>
        <input type="range" id="s_vol" min="0" max="100" step="1">
        <div style="margin-top:12px">判定音量 <span id="v_se" class="ds"></span></div>
        <input type="range" id="s_se" min="0" max="100" step="1">
        <div class="row" style="margin-top:14px">
          <button class="btn" id="t_se">音效：开</button>
          <button class="btn" id="t_bgm">伴奏：开</button>
          <button class="btn" id="clr_imp">清掉导入过的谱面</button>
        </div>
      </div>
      <h2>🎧 氛围音</h2>
      <div id="amb"></div>
    </div>
  </section>

  <section class="pane" id="p-lucky">
    <div class="wrap">
      <div class="lucky" id="lk">—</div>
      <div class="note" id="lkb"></div>
      <div style="text-align:center;margin-top:14px"><button class="btn pri" id="lkgo">再抽一次</button></div>
    </div>
  </section>

  <section class="pane" id="p-help">
    <div class="wrap">
      <h2>🕹 机台怎么玩</h2>
      <div class="note">
        键盘 <b>A S D F J K L ;</b> = 圆环八分区（左上开始顺时针），<b>空格</b> = TOUCH，<b>Shift</b> = EX；<br>
        手机/触屏：<b>点圆环方位</b>敲，<b>按住划到另一个方位</b>送 SLIDE，<b>点中央屏</b> = TOUCH/EX。<br>
        选曲画面 <b>↑↓</b> 选曲、<b>←→</b> 选难度、<b>Enter</b> 开打；<b>I</b> 导入谱面、<b>H</b> 键位说明、<b>Esc</b> 放弃。<br>
        金色五角星是 <b>BREAK</b>：头判按 BREAK 算，CRITICAL PERFECT 有加成，全谱加成封顶 +1%，所以理论上限 <b>101.0000%</b>。
      </div>
      <h2>📄 导入谱面</h2>
      <div class="note">
        机台里按 <b>I</b> 打开导入框，粘社区通用的 <b>Simai</b> 文本（astroDX / Majdata 那套）：
        <code>&amp;bpm= &amp;offset= &amp;title=</code> 开头，<code>#Master</code> 难度块，
        <code>1b</code> 星星、<code>1h[4:1]</code> HOLD、<code>1^3</code> 弧线 SLIDE、<code>1-2-3</code> 链滑、
        <code>A1</code>~<code>C</code> TOUCH、<code>E</code> EX。手机上长按粘贴即可。
      </div>
      <h2>📱 手机上怎么用</h2>
      <div class="note">
        这个页面<b>不联网</b>也能跑。iPhone：Safari 分享 → 添加到主屏幕；
        Android：菜单 → 添加到主屏幕 / 或装编出来的 APK。横过来判定环更大。
      </div>
      <h2>🔒 真实边界</h2>
      <div class="note">
        曲库是真实曲库快照，但<b>没有音频授权</b>，所以伴奏是用 Web Audio 现场合成的（鼓 + 贝斯 + 和弦 + 旋律，跟着 BPM 走），
        不是原曲。成绩只存在你这台设备上。
      </div>
    </div>
  </section>
</div>

<div id="hint"><b>↑↓</b> 选曲　<b>←→</b> 难度　<b>Enter</b> 开打　<b>I</b> 导入　<b>H</b> 说明　·　手机：点方位敲，划过去送 SLIDE</div>

<script>
var HUB_LIB   = __LIB__;
var HUB_GAMES = __GAMES__;
</script>
<script>
__JS__
</script>
<script>
/* ============================================================ 大厅外壳 */
var TABS = [
  { id: 'cab',   name: '🕹 机台' },
  { id: 'game',  name: '🎮 小游戏' },
  { id: 'lib',   name: '🎼 曲库' },
  { id: 'score', name: '🏆 成绩' },
  { id: 'set',   name: '⚙ 设置' },
  { id: 'lucky', name: '🎴 运势' },
  { id: 'help',  name: '❓ 说明' }
];
var DXHUB = { idle: true };
window.DXHUB = DXHUB;
var $ = function (s) { return document.querySelector(s); };
var cur = 'cab', curGame = -1;

function el(tag, cls, txt) {
  var e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

/* ---- 导航 ---- */
var tabsBox = $('#tabs');
TABS.forEach(function (t) {
  var b = el('div', 'tab', t.name);
  b.onclick = function () { go(t.id); };
  b.dataset.id = t.id;
  tabsBox.appendChild(b);
});

function go(id) {
  if (cur === 'cab' && id !== 'cab') {
    // 正在打歌就切走：先收尾，免得回来时间跳一大截全变 MISS
    try { if (window.DX && window.DX.S && window.DX.S.running) window.DX.endPlay(); } catch (e) { }
  }
  cur = id;
  DXHUB.idle = (id !== 'cab');
  document.body.classList.toggle('cab', id === 'cab');
  ['cab', 'game', 'lib', 'score', 'set', 'lucky', 'help'].forEach(function (p) {
    $('#p-' + p).classList.toggle('on', p === id);
  });
  Array.prototype.forEach.call(tabsBox.children, function (b) {
    b.classList.toggle('on', b.dataset.id === id);
  });
  if (id === 'cab') {
    try { if (window.DX && window.DX.relayout) window.DX.relayout(); } catch (e) { }
    try { if (window.DX) window.DX.AU.resume(); } catch (e) { }
  }
  if (id === 'game' && curGame < 0) showGame(0);
  if (id === 'score') drawBest();
  if (id === 'set') syncSettings();
  if (id === 'lucky') lucky();
}
$('#backhome').onclick = function () { go('lib'); };

/* ---- 小游戏 ---- */
var gbar = $('#gamebar'), gframe = $('#gframe'), gbox = $('#gamebox');
var cats = [];
HUB_GAMES.forEach(function (g) { if (cats.indexOf(g.cat) < 0) cats.push(g.cat); });
HUB_GAMES.forEach(function (g, i) {
  var c = el('div', 'chip', g.name);
  c.dataset.cat = g.cat; c.dataset.i = i;
  c.onclick = function () { showGame(i); };
  gbar.appendChild(c);
});
function fit() {
  if (curGame < 0) return;
  var g = HUB_GAMES[curGame];
  var cw = gbox.clientWidth || g.w, ch = gbox.clientHeight || g.h;
  var k = Math.min(1, cw / g.w, ch / g.h);      // 只缩不放：canvas 放大会糊
  gframe.style.width = g.w + 'px';
  gframe.style.height = g.h + 'px';
  gframe.style.transform = 'translateX(-50%) scale(' + k + ')';
}
function showGame(i) {
  curGame = i;
  Array.prototype.forEach.call(gbar.children, function (c) {
    c.classList.toggle('on', +c.dataset.i === i);
  });
  gframe.srcdoc = HUB_GAMES[i].html;
  fit();
}
window.addEventListener('resize', fit);
window.addEventListener('orientationchange', function () { setTimeout(fit, 200); });

/* ---- 曲库 ---- */
var shown = 100;
var DIFFS = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'Re:MASTER'];
var DS_ADJ = [-6, -4, -2, -0.7, 0];
function filtered() {
  var q = ($('#q').value || '').trim().toLowerCase();
  var f = +$('#dsf').value;
  return HUB_LIB.filter(function (s) {
    if (q && (s.title + ' ' + s.artist).toLowerCase().indexOf(q) < 0) return false;
    if (f === 1 && s.ds > 9) return false;
    if (f === 2 && (s.ds < 9 || s.ds >= 12)) return false;
    if (f === 3 && (s.ds < 12 || s.ds >= 13.5)) return false;
    if (f === 4 && s.ds < 13.5) return false;
    return true;
  });
}
function drawList() {
  var box = $('#list'); box.innerHTML = '';
  var rows = filtered().slice(0, shown);
  if (!rows.length) { box.appendChild(el('div', 'note', '没搜到，换个词试试。')); return; }
  rows.forEach(function (s) {
    var d = el('div', 'song');
    var t = el('div', 't', s.title + (s.artist ? '　— ' + s.artist : ''));
    var m = el('div', 'm', 'BPM ' + s.bpm + '　定数 ');
    var b = el('span', 'ds', s.ds.toFixed(1));
    m.appendChild(b);
    var p = el('div', 'play', '开打 ▸');
    p.onclick = function () { playSong(s, 3); };
    d.appendChild(t); d.appendChild(m); d.appendChild(p);
    box.appendChild(d);
  });
  $('#more').style.display = (filtered().length > shown) ? '' : 'none';
}
function playSong(s, di) {
  if (!window.DX) return;
  var ds = Math.max(1, Math.round((s.ds + DS_ADJ[di]) * 10) / 10);
  var c = window.DX.buildChart({ title: s.title, artist: s.artist, bpm: s.bpm, ds: ds }, di);
  if (!c) return;
  window.DX.loadChart(c);
  go('cab');
  try { window.DX.AU.resume(); } catch (e) { }
  window.DX.startPlay();
}
$('#q').oninput = function () { shown = 100; drawList(); };
$('#dsf').onchange = function () { shown = 100; drawList(); };
$('#more').onclick = function () { shown += 100; drawList(); };
drawList();

/* ---- 成绩 ---- */
function drawBest() {
  var rows = [];
  for (var i = 0; i < localStorage.length; i++) {
    var k = localStorage.key(i);
    if (k && k.indexOf('dx_best_') === 0) {
      var v = parseFloat(localStorage.getItem(k)) || 0;
      var rest = k.slice(8), j = rest.lastIndexOf('_');
      rows.push({ t: rest.slice(0, j), d: rest.slice(j + 1), ach: v,
                  rk: (window.DX && window.DX.rankOf) ? window.DX.rankOf(v) : '' });
    }
  }
  rows.sort(function (a, b) { return b.ach - a.ach; });
  var box = $('#best'); box.innerHTML = '';
  if (!rows.length) { box.appendChild(el('div', 'note', '还没有记录 —— 去机台打一局就有了。')); return; }
  var tb = el('table'), hd = el('tr');
  ['曲名', '难度', '达成率', '评级'].forEach(function (h) { hd.appendChild(el('th', '', h)); });
  tb.appendChild(hd);
  rows.slice(0, 200).forEach(function (r) {
    var tr = el('tr');
    tr.appendChild(el('td', '', r.t));
    tr.appendChild(el('td', '', r.d));
    tr.appendChild(el('td', 'ds', r.ach.toFixed(4) + '%'));
    tr.appendChild(el('td', '', r.rk));
    tb.appendChild(tr);
  });
  box.appendChild(tb);
}
$('#clr').onclick = function () {
  var ks = [];
  for (var i = 0; i < localStorage.length; i++) {
    var k = localStorage.key(i);
    if (k && k.indexOf('dx_best_') === 0) ks.push(k);
  }
  ks.forEach(function (k) { localStorage.removeItem(k); });
  drawBest();
};

/* ---- 设置 ---- */
function loadSettings() {
  try { return JSON.parse(localStorage.getItem('dx_settings')) || {}; } catch (e) { return {}; }
}
function saveSettings(s) { localStorage.setItem('dx_settings', JSON.stringify(s)); }
function apply(s) {
  if (!window.DX) return;
  window.DX.S.speed = s.speed; window.DX.S.offset = s.offset;
  window.DX.AU.on = s.se; window.DX.AU.bgmOn = s.bgm;
  window.DX.AU.setVol(s.vol); window.DX.AU.setSe(s.seVol);
}
function syncSettings() {
  var s = loadSettings();
  s.speed = s.speed || 1.0; s.offset = s.offset || 0; s.se = s.se !== false;
  s.bgm = s.bgm !== false; s.vol = s.vol === undefined ? 0.7 : s.vol;
  s.seVol = s.seVol === undefined ? 0.55 : s.seVol;
  $('#s_speed').value = Math.round(s.speed * 100); $('#v_speed').textContent = s.speed.toFixed(2) + '×';
  $('#s_off').value = s.offset; $('#v_off').textContent = (s.offset > 0 ? '+' : '') + s.offset;
  $('#s_vol').value = Math.round(s.vol * 100); $('#v_vol').textContent = Math.round(s.vol * 100) + '%';
  $('#s_se').value = Math.round(s.seVol * 100); $('#v_se').textContent = Math.round(s.seVol * 100) + '%';
  $('#t_se').textContent = '音效：' + (s.se ? '开' : '关');
  $('#t_bgm').textContent = '伴奏：' + (s.bgm ? '开' : '关');
  apply(s);
}
[['s_speed', 'speed', 100], ['s_off', 'offset', 1], ['s_vol', 'vol', 100], ['s_se', 'seVol', 100]].forEach(function (p) {
  $('#' + p[0]).oninput = function () {
    var s = loadSettings();
    s[p[1]] = (+this.value) / p[2];
    saveSettings(s); syncSettings();
  };
});
$('#t_se').onclick = function () { var s = loadSettings(); s.se = !s.se; saveSettings(s); syncSettings(); };
$('#t_bgm').onclick = function () { var s = loadSettings(); s.bgm = !s.bgm; saveSettings(s); syncSettings(); };
$('#clr_imp').onclick = function () { localStorage.removeItem('dx_custom_charts'); this.textContent = '已清掉 ✓'; };

/* ---- 氛围音 ---- */
var ambGame = HUB_GAMES.filter(function (g) { return g.id === 'ambience'; })[0];
if (ambGame) {
  var f = document.createElement('iframe');
  f.style.cssText = 'width:100%;height:150px;border:0;background:#070d12';
  f.setAttribute('sandbox', 'allow-scripts allow-same-origin');
  f.srcdoc = ambGame.html;
  $('#amb').appendChild(f);
}

/* ---- 今日运势 ---- */
var LUCKY = [['大吉', '今天手顺得离谱，去冲个新纪录'], ['中吉', '稳，适合刷达成率'],
             ['小吉', '打打低难度找找手感'], ['吉', '可以试试高一个等级'],
             ['半吉', '先校准一下判定偏移'], ['末吉', '别硬撑，打两局歇歇']];
function lucky() {
  var i = Math.floor(Math.random() * LUCKY.length);
  var s = HUB_LIB[Math.floor(Math.random() * Math.min(120, HUB_LIB.length))];
  $('#lk').textContent = LUCKY[i][0];
  $('#lkb').innerHTML = '<b>' + LUCKY[i][1] + '</b><br>今日一曲：' + s.title +
    '　BPM ' + s.bpm + '　定数 <span class="ds">' + s.ds.toFixed(1) + '</span>' +
    '<br><span style="color:#7f9aa0">（纯属好玩，不算命 —— 曲是随机从本地曲库里抽的）</span>';
  $('#lkb').dataset.title = s.title;
}
$('#lkgo').onclick = lucky;

/* ---- 启动 ---- */
go('cab');
</script>
</body>
</html>
"""

html = (SHELL.replace("__LIB__", jdump(lib))
             .replace("__GAMES__", jdump(GAMES))
             .replace("__JS__", js)
             .replace("__N__", str(len(lib))))

out = OUT_DIR / "maimai-hub.html"
out.write_text(html, encoding="utf-8")

print(f"曲库内置 {len(lib)} 首　小游戏 {len(GAMES)} 个")
for g in GAMES:
    print(f"  · {g['cat']}　{g['name']}　{g['w']}×{g['h']}　{g['html'].__len__() // 1024} KB")
print(f"\n单文件大厅：{out}  →  {out.stat().st_size / 1024:.0f} KB")
ext = re.findall(r"(?:src|href)\s*=\s*[\"'](https?:)?//", html)
print("外部链接：", len(ext))
