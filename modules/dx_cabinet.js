/*
 * 舞萌 DX 机台 —— 演奏引擎（自包含，零外部资源）
 *
 * 一个文件里装了：谱面生成器、Simai 导入、合成伴奏、判定音、圆环判定区渲染、
 * 判定与结算、成绩码。Streamlit 里用 iframe 嵌，独立版里直接跑全屏。
 *
 * 外部只依赖两个可选全局变量：
 *   window.CHART  一张谱面（Streamlit 侧生成好注进来）
 *   window.DXLIB  曲库 [{title,artist,bpm,ds,diff}]（独立版内置）
 */
(function () {
'use strict';

var CHART = window.CHART || null;
var LIB = window.DXLIB || [];

// ============================================================ 常量
var W_CP = 33, W_P = 67, W_GR = 100, W_GD = 150, W_MISS = 200;   // 判定窗口(ms)，真机值
var NOTE_POINTS = 500, BREAK_BONUS = 100, BREAK_CAP = 1.0;
var VAL = { cp: 1.0, p: 0.98, gr: 0.88, gd: 0.65, miss: 0.0 };
var RANKS = [
  [101.0, 'SSS+'], [100.0, 'SSS'], [99.5, 'SS+'], [99.0, 'SS'], [98.5, 'S+'],
  [98.0, 'S'], [97.0, 'AAA'], [94.0, 'AA'], [90.0, 'A'], [80.0, 'BBB'],
  [75.0, 'B'], [70.0, 'C'], [0, 'D']
];
var KEYS = ['a', 's', 'd', 'f', 'j', 'k', 'l', ';'];
var KEY_ALIAS = { w: ';', o: ';' };
// 8 个分区的角度（弧度，屏幕坐标系 y 向下）
var POS_A = [];
(function () {
  // 0=左上 1=左 2=左下 3=下 4=右下 5=右 6=右上 7=上
  var deg = [225, 180, 135, 90, 45, 0, 315, 270];
  for (var i = 0; i < 8; i++) POS_A.push(deg[i] * Math.PI / 180);
})();
var POS_CN = ['左上', '左', '左下', '下', '右下', '右', '右上', '上'];
var C_TAP = '#39C5BB', C_STAR = '#F5D442', C_HOLD = '#7FD1FF',
    C_SLIDE = '#B07CFF', C_TOUCH = '#FF8FD1', C_EX = '#FFB020',
    C_MISS = '#E5484D';
var SHAPE_CN = { line: '直线', arc: '圆弧', arc_l: '左弧', arc_r: '右弧', v: 'V字',
                 wifi: 'Wifi', s_cur: 'S形', z_cur: 'Z形', fan: '扇形' };

function rankOf(a) { for (var i = 0; i < RANKS.length; i++) if (a >= RANKS[i][0]) return RANKS[i][1]; return 'D'; }
function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }
function lerp(a, b, t) { return a + (b - a) * t; }

// ============================================================ 音频：合成伴奏 + 判定音
var AU = {
  ctx: null, master: null, bgmGain: null, seGain: null,
  on: true, bgmOn: true, vol: 0.7, seVol: 0.55,
  timer: null, nextBeat: 0, beatIdx: 0, beatMs: 500, stopAt: 0,

  init: function () {
    if (this.ctx) return this.ctx;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    try { this.ctx = new AC(); } catch (e) { return null; }
    this.master = this.ctx.createGain(); this.master.gain.value = this.vol;
    this.master.connect(this.ctx.destination);
    this.bgmGain = this.ctx.createGain(); this.bgmGain.gain.value = 0.30;
    this.bgmGain.connect(this.master);
    this.seGain = this.ctx.createGain(); this.seGain.gain.value = this.seVol;
    this.seGain.connect(this.master);
    return this.ctx;
  },
  resume: function () {
    var c = this.init();
    if (c && c.state === 'suspended' && c.resume) c.resume();
  },
  setVol: function (v) { this.vol = v; if (this.master) this.master.gain.value = v; },
  setSe: function (v) { this.seVol = v; if (this.seGain) this.seGain.gain.value = v; },

  // ---- 单个音 ----
  blip: function (freq, dur, type, peak, dest, detune) {
    var c = this.ctx; if (!c) return;
    var o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine';
    o.frequency.value = freq;
    if (detune) o.detune.value = detune;
    var t = c.currentTime;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(peak, t + 0.004);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest || this.seGain);
    o.start(t); o.stop(t + dur + 0.02);
  },
  noise: function (dur, peak, hp, dest) {
    var c = this.ctx; if (!c) return;
    var n = Math.floor(c.sampleRate * dur);
    var buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0);
    for (var i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n);
    var src = c.createBufferSource(); src.buffer = buf;
    var f = c.createBiquadFilter(); f.type = 'highpass'; f.frequency.value = hp || 1200;
    var g = c.createGain(); g.gain.value = peak;
    src.connect(f); f.connect(g); g.connect(dest || this.seGain);
    src.start();
  },

  // ---- 判定音：每种音符一个音色 ----
  se: function (kind, star) {
    if (!this.on) return;
    var c = this.init(); if (!c) return;
    if (kind === 'tap')      this.blip(1760, 0.045, 'triangle', 0.16);
    else if (kind === 'break') { this.blip(2637, 0.12, 'sine', 0.20); this.blip(3520, 0.10, 'sine', 0.11); }
    else if (kind === 'hold')  this.blip(1320, 0.09, 'sine', 0.14);
    else if (kind === 'slide') this.noise(0.13, 0.13, 2400);
    else if (kind === 'touch') this.blip(880, 0.11, 'sine', 0.14);
    else if (kind === 'ex')  { this.blip(1046, 0.10, 'triangle', 0.12); this.blip(1568, 0.10, 'sine', 0.09); }
    else if (kind === 'miss')  this.blip(130, 0.13, 'square', 0.10);
    else if (kind === 'coin') { this.blip(988, 0.07, 'square', 0.14); var self = this;
                                setTimeout(function () { self.blip(1319, 0.10, 'square', 0.13); }, 70); }
    else if (kind === 'clear') { var self2 = this, notes = [523, 659, 784, 1046];
                                notes.forEach(function (f, i) {
                                  setTimeout(function () { self2.blip(f, 0.22, 'sine', 0.15); }, i * 110); }); }
  },

  // ---- 伴奏：跟着 BPM 现场合成，鼓 + 贝斯 + 和弦 ----
  startBGM: function (bpm, durMs) {
    var c = this.init(); if (!c) return;
    this.stopBGM();
    this.beatMs = 60000 / clamp(bpm || 120, 40, 300);
    this.beatIdx = 0;
    this.nextBeat = c.currentTime + 0.12;
    this.stopAt = c.currentTime + durMs / 1000 + 0.2;
    var self = this;
    this.timer = setInterval(function () { self._sched(); }, 30);
    this._sched();
  },
  stopBGM: function () { if (this.timer) { clearInterval(this.timer); this.timer = null; } },
  _sched: function () {
    var c = this.ctx; if (!c) return;
    var horizon = c.currentTime + 0.35;
    var guard = 0;
    while (this.nextBeat < horizon && this.nextBeat < this.stopAt && guard++ < 64) {
      this._beat(this.nextBeat, this.beatIdx);
      this.beatIdx++;
      this.nextBeat += (this.beatMs / 1000) / 2;      // 以 8 分音符为步进
    }
  },
  _beat: function (t, i) {
    if (!this.bgmOn) return;
    var c = this.ctx, g = this.bgmGain;
    var bar = Math.floor(i / 8), inBar = i % 8;
    // 鼓
    if (inBar === 0 || inBar === 4 || (inBar === 6 && bar % 2 === 1)) {
      var o = c.createOscillator(), gg = c.createGain();
      o.type = 'sine';
      o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.11);
      gg.gain.setValueAtTime(0.9, t); gg.gain.exponentialRampToValueAtTime(0.001, t + 0.16);
      o.connect(gg); gg.connect(g); o.start(t); o.stop(t + 0.18);
    }
    if (inBar === 2 || inBar === 6) {                  // 军鼓
      var n = Math.floor(c.sampleRate * 0.13);
      var b = c.createBuffer(1, n, c.sampleRate), d = b.getChannelData(0);
      for (var k = 0; k < n; k++) d[k] = (Math.random() * 2 - 1) * (1 - k / n);
      var s = c.createBufferSource(); s.buffer = b;
      var f = c.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 1900;
      var vg = c.createGain(); vg.gain.value = 0.35;
      s.connect(f); f.connect(vg); vg.connect(g); s.start(t);
    }
    if (i % 2 === 0) {                                  // 踩镲
      var n2 = Math.floor(c.sampleRate * 0.04);
      var b2 = c.createBuffer(1, n2, c.sampleRate), d2 = b2.getChannelData(0);
      for (var k2 = 0; k2 < n2; k2++) d2[k2] = (Math.random() * 2 - 1) * (1 - k2 / n2);
      var s2 = c.createBufferSource(); s2.buffer = b2;
      var f2 = c.createBiquadFilter(); f2.type = 'highpass'; f2.frequency.value = 7000;
      var v2 = c.createGain(); v2.gain.value = 0.10;
      s2.connect(f2); f2.connect(v2); v2.connect(g); s2.start(t);
    }
    // 贝斯（每小节换根音，i-VI-IV-V 的走向）
    var roots = [55, 65.4, 49, 58.3];
    if (inBar === 0 || inBar === 3 || inBar === 6) {
      var fr = roots[bar % 4] * 2;
      var ob = c.createOscillator(), gb = c.createGain();
      ob.type = 'sawtooth'; ob.frequency.value = fr;
      var lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 420;
      gb.gain.setValueAtTime(0.0001, t);
      gb.gain.linearRampToValueAtTime(0.16, t + 0.02);
      gb.gain.exponentialRampToValueAtTime(0.001, t + (this.beatMs / 1000) * 0.45);
      ob.connect(lp); lp.connect(gb); gb.connect(g);
      ob.start(t); ob.stop(t + (this.beatMs / 1000) * 0.5 + 0.02);
    }
    // 和弦垫（每小节头）
    // 注意：本文件是 'use strict'，forEach 回调里的 this 是 undefined，
    // 必须先把 this 存进 self，否则每小节都会抛 TypeError（伴奏和弦/贝斯失效）。
    if (inBar === 0) {
      var base = roots[bar % 4] * 4;
      var selfBeat = this.beatMs / 1000;
      [1, 1.26, 1.5].forEach(function (m) {
        var oc = c.createOscillator(), gc = c.createGain();
        oc.type = 'triangle'; oc.frequency.value = base * m;
        gc.gain.setValueAtTime(0.0001, t);
        gc.gain.linearRampToValueAtTime(0.055, t + 0.06);
        gc.gain.exponentialRampToValueAtTime(0.0008, t + selfBeat * 3.4);
        oc.connect(gc); gc.connect(g); oc.start(t); oc.stop(t + selfBeat * 3.6);
      });
    }
    // 旋律（八分音符，五声音阶）
    var scale = [0, 2, 4, 7, 9, 12, 14, 16];
    var mel = scale[(bar * 3 + i) % 8] + (bar % 2 ? 12 : 0);
    var om = c.createOscillator(), gm = c.createGain();
    om.type = 'square'; om.frequency.value = 440 * Math.pow(2, mel / 12);
    gm.gain.setValueAtTime(0.0001, t);
    gm.gain.linearRampToValueAtTime(0.030, t + 0.01);
    gm.gain.exponentialRampToValueAtTime(0.0008, t + (this.beatMs / 1000) * 0.32);
    om.connect(gm); gm.connect(g); om.start(t); om.stop(t + (this.beatMs / 1000) * 0.4);
  }
};

// ============================================================ Simai 解析（JS 版，规则同 Python）
var SHAPE_OF = { '-': 'line', '—': 'line', '^': 'arc', '~': 'arc', '<': 'arc_l',
                 '>': 'arc_r', 'v': 'v', 'V': 'v', 'w': 'wifi', 'W': 'wifi',
                 's': 's_cur', 'S': 's_cur', 'z': 'z_cur', 'Z': 'z_cur',
                 'p': 'p_cur', 'q': 'q_cur', '$': 'fan' };
var SHAPE_CHARS = '-—^~<>vVwWsSzZpq$';
var DIFF_ALIAS = { BASIC: 'BASIC', BAS: 'BASIC', ADVANCED: 'ADVANCED', ADV: 'ADVANCED',
                   EXPERT: 'EXPERT', EXP: 'EXPERT', MASTER: 'MASTER', MAS: 'MASTER',
                   'RE:MASTER': 'RE:MASTER', REMASTER: 'RE:MASTER', REM: 'RE:MASTER' };

function simaiSplitTop(text, sep) {
  var out = [], buf = '', depth = 0;
  for (var i = 0; i < text.length; i++) {
    var ch = text[i];
    if ('{[('.indexOf(ch) >= 0) depth++;
    else if ('}])'.indexOf(ch) >= 0) depth--;
    if (ch === sep && depth <= 0) { out.push(buf); buf = ''; }
    else buf += ch;
  }
  out.push(buf);
  return out;
}
function simaiDur(tok, beatMs, defBeats) {
  if (!tok) return [defBeats, false];
  var inner = tok.replace(/^\[/, '').replace(/\]$/, '').trim();
  if (!inner) return [defBeats, false];
  if (inner.indexOf(':') >= 0) {
    var p = inner.split(':');
    var x = parseFloat(p[0]), y = parseFloat(p[1] || '1');
    if (isNaN(x) || isNaN(y) || y === 0) return [defBeats, false];
    return [x / y, true];
  }
  var v = parseFloat(inner);
  return isNaN(v) ? [defBeats, false] : [v, true];
}
function simaiNote(tok, t, beatMs, defBeats) {
  var s = String(tok || '').trim();
  if (!s) return [[], defBeats, false];
  var out = [], m;
  // SLIDE: 1-2 / 1b^3 / 1-2-3
  m = s.match(/^([1-8])(b?)([-—^~<>vVwWsSzZpq$]+)([1-8])(b?)/);
  if (m) {
    var star = (m[2] || m[5]) ? 1 : 0;
    var a = parseInt(m[1], 10) - 1, b = parseInt(m[4], 10) - 1;
    var shape = SHAPE_OF[m[3].charAt(m[3].length - 1)] || 'line';
    var rest = s.slice(m[0].length);
    var dm = rest.match(/^(\[[^\]]*\])/);
    var durTok = dm ? dm[1] : '';
    if (dm) rest = rest.slice(dm[0].length);
    var d = simaiDur(durTok, beatMs, defBeats);
    var slideMs = clamp(d[0] * beatMs, 120, beatMs * 4);
    out.push({ t: t, k: 'slide', p: a, q: b, d: slideMs, s: shape, star: star });
    var more;
    while ((more = rest.trim().match(/^([-—^~<>vVwWsSzZpq$]+)([1-8])(b?)/))) {
      var nb = parseInt(more[2], 10) - 1;
      out.push({ t: t, k: 'slide', p: b, q: nb, d: slideMs,
                 s: SHAPE_OF[more[1].charAt(more[1].length - 1)] || 'line',
                 star: more[3] ? 1 : star });
      b = nb;
      rest = rest.slice(rest.indexOf(more[0]) + more[0].length);
      var d2 = rest.trim().match(/^(\[[^\]]*\])/);
      if (d2) rest = rest.slice(rest.indexOf(d2[0]) + d2[0].length);
    }
    return [out, d[1] ? d[0] : defBeats, d[1]];
  }
  // TOUCH / EX / TOUCH HOLD
  m = s.match(/^([A-Ea-e])([1-8]?)(b?)(h?)(\[[^\]]*\])?/);
  if (m && 'ABCDEabcde'.indexOf(m[1]) >= 0) {
    var z = m[1].toUpperCase();
    var pos = m[2] ? parseInt(m[2], 10) - 1 : 0;
    var star2 = m[3] ? 1 : 0;
    var dd = simaiDur(m[5] || '', beatMs, defBeats);
    if (z === 'E') out.push({ t: t, k: 'ex', z: 'E', p: pos, star: 0 });
    else if (m[4]) out.push({ t: t, k: 'thold', z: z, p: pos, star: star2,
                              d: Math.max(120, dd[0] * beatMs) });
    else out.push({ t: t, k: 'touch', z: z, p: pos, star: star2 });
    return [out, dd[1] ? dd[0] : defBeats, dd[1]];
  }
  // TAP / BREAK / HOLD
  m = s.match(/^([1-8])(b?)(h?)(\[[^\]]*\])?/);
  if (m) {
    var p2 = parseInt(m[1], 10) - 1;
    var star3 = m[2] ? 1 : 0;
    var dd2 = simaiDur(m[4] || '', beatMs, defBeats);
    if (m[3]) out.push({ t: t, k: 'hold', p: p2, star: star3, d: Math.max(120, dd2[0] * beatMs) });
    else out.push({ t: t, k: 'tap', p: p2, star: star3 });
    return [out, dd2[1] ? dd2[0] : defBeats, dd2[1]];
  }
  return [[], defBeats, false];
}
function parseSimai(text, defaultDiv) {
  text = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  defaultDiv = defaultDiv || 4;
  var defBeats = 1 / defaultDiv;
  var meta = { bpm: 120, offset: 0, title: '', artist: '', ds: 0 };
  var blocks = [], curName = null, curBuf = [], warns = [];
  var lines = text.split('\n');
  for (var li = 0; li < lines.length; li++) {
    var line = lines[li].trim();
    if (!line) continue;
    if (line.charAt(0) === '&') {
      var mm = line.match(/^&(\w+)\s*=\s*(.*)$/);
      if (mm) {
        var key = mm[1].toLowerCase(), val = mm[2];
        if (key === 'bpm') meta.bpm = parseFloat((val.match(/[\d.]+/) || ['120'])[0]) || 120;
        else if (key === 'offset') meta.offset = parseFloat((val.match(/[\d.\-]+/) || ['0'])[0]) * 1000 || 0;
        else if (key === 'title') meta.title = val;
        else if (key === 'artist') meta.artist = val;
        else if (key === 'lv' || key === 'ds') meta.ds = parseFloat((val.match(/[\d.]+/) || ['0'])[0]) || 0;
      }
      continue;
    }
    if (line.charAt(0) === '#' || line.charAt(0) === '＃') {
      if (curName !== null) blocks.push([curName, curBuf.join('\n')]);
      curBuf = [];
      var head = line.slice(1).trim().toUpperCase();
      var name = null;
      var parts = head.split(/[:：\s]+/);
      for (var pi = 0; pi < parts.length; pi++) if (DIFF_ALIAS[parts[pi]]) { name = DIFF_ALIAS[parts[pi]]; break; }
      if (!name) {
        for (var kk in DIFF_ALIAS) if (head.indexOf(kk) === 0) { name = DIFF_ALIAS[kk]; break; }
      }
      if (!name) { name = 'MASTER'; warns.push('难度头「' + line + '」认不出来，当作 MASTER'); }
      curName = name;
      continue;
    }
    curBuf.push(line);
  }
  if (curName !== null) blocks.push([curName, curBuf.join('\n')]);
  else if (curBuf.length && /[1-8]/.test(curBuf.join(''))) blocks.push(['MASTER', curBuf.join('\n')]);

  var charts = {};
  for (var bi = 0; bi < blocks.length; bi++) {
    var diff = blocks[bi][0], body = blocks[bi][1];
    var bpm = meta.bpm, beatMs = 60000 / clamp(bpm, 20, 400);
    var t = meta.offset || 0, notes = [];
    var events = simaiSplitTop(body, ',');
    for (var ei = 0; ei < events.length; ei++) {
      var ev = events[ei].trim();
      if (!ev) continue;
      var mb = ev.match(/^\((\d+(?:\.\d+)?)\)/);
      if (mb) { bpm = parseFloat(mb[1]); beatMs = 60000 / clamp(bpm, 20, 400); ev = ev.slice(mb[0].length).trim(); if (!ev) continue; }
      if (ev.charAt(0) === '[') {
        var d0 = simaiDur(ev, beatMs, defBeats);
        if (d0[1]) t += d0[0] * beatMs;
        continue;
      }
      if (ev.charAt(0) === '{') {
        var close = ev.indexOf('}');
        if (close < 0) { warns.push(diff + '：同押的 { 没配对'); continue; }
        var inner = ev.slice(1, close), tail = ev.slice(close + 1).trim();
        var expl = [];
        var subs = simaiSplitTop(inner, ',');
        for (var si = 0; si < subs.length; si++) {
          var r1 = simaiNote(subs[si], t, beatMs, defBeats);
          notes = notes.concat(r1[0]);
          if (r1[2]) expl.push(r1[1]);
        }
        if (tail) {
          if (tail.charAt(0) === '[') { var d1 = simaiDur(tail, beatMs, defBeats); if (d1[1]) expl.push(d1[0]); }
          else { var r2 = simaiNote(tail, t, beatMs, defBeats); notes = notes.concat(r2[0]); if (r2[2]) expl.push(r2[1]); }
        }
        t += (expl.length ? Math.max.apply(null, expl) : defBeats) * beatMs;
        continue;
      }
      var r3 = simaiNote(ev, t, beatMs, defBeats);
      notes = notes.concat(r3[0]);
      t += r3[1] * beatMs;
    }
    if (!notes.length) { warns.push(diff + '：一个音符都没读出来'); continue; }
    notes.sort(function (a, b) { return a.t - b.t || (a.p || 0) - (b.p || 0); });
    for (var ni = 0; ni < notes.length; ni++) {
      notes[ni].t = Math.round(notes[ni].t * 100) / 100;
      if (notes[ni].star === undefined) notes[ni].star = 0;
    }
    var last = notes[notes.length - 1];
    charts[diff] = {
      title: meta.title || '导入谱面', artist: meta.artist || '',
      bpm: bpm, offset: meta.offset || 0, diff: diff, ds: meta.ds || 0,
      duration: (last.t + (last.d || 0)) / 1000 + 4,
      notes: notes, source: 'simai'
    };
  }
  return { charts: charts, errors: [], warnings: warns };
}

// ============================================================ 谱面生成器（JS 版，独立版用）
function makeRng(seed) {
  var s = seed >>> 0;
  return function () {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
function seedOf(title, diff) {
  var h = 2166136261, str = 'dx|' + title + '|' + diff;
  for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = (h * 16777619) >>> 0; }
  return h >>> 0;
}
var DSHAPES = [
  ['line'],
  ['line'],
  ['line', 'line', 'arc'],
  ['line', 'line', 'arc', 'arc', 'arc_l', 'arc_r', 'v'],
  ['line', 'arc', 'arc_l', 'arc_r', 'arc_r', 'v', 'wifi', 's_cur', 'z_cur', 'fan']
];
function buildChart(song, diffIdx, duration) {
  diffIdx = clamp(diffIdx | 0, 0, 4);
  duration = duration || 76;
  var bpm = clamp(parseFloat(song.bpm) || 150, 60, 260);
  var ds = clamp(parseFloat(song.ds) || 8, 1, 15.6);
  var beat = 60000 / bpm, step = beat / 4;
  var total = Math.max(64, Math.round(duration * 1000 / step));
  var rng = makeRng(seedOf(song.title || 'x', ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'RE:MASTER'][diffIdx]));
  var W = [[88, 12, 0, 0, 0, 0], [70, 16, 11, 3, 0, 0], [52, 13, 20, 7, 5, 3],
           [42, 11, 26, 11, 6, 4], [36, 9, 30, 13, 7, 5]][diffIdx];
  var MODES = [{ alt: .10, stair: 0, chord: 0, sweep: 0 },
               { alt: .12, stair: 0, chord: 0, sweep: .12 },
               { alt: .12, stair: .08, chord: .06, sweep: .12 },
               { alt: .12, stair: .10, chord: .08, sweep: .14 },
               { alt: .12, stair: .12, chord: .08, sweep: .16 }][diffIdx];
  var SEGS = [[0, .09, .42], [.09, .30, .85], [.30, .40, 1.02], [.40, .60, 1.22],
              [.60, .70, .80], [.70, .92, 1.34], [.92, 1.01, .55]];
  var nps = clamp(1.0 + (ds - 1.0) * 0.62, 0.8, 10.2);
  var GAP = Math.max(step * 0.5, 45);
  var notes = [], busy = [], lastTouch = -1e9, lastEx = -1e9, lastPos = -1;
  for (var q = 0; q < 8; q++) busy.push(-1e9);
  var sameT = { t: -1e9, n: 0 }, ctrT = { t: -1e9, n: 0 };

  function pick(arr) { return arr[Math.floor(rng() * arr.length)]; }
  function shape() { return pick(DSHAPES[diffIdx]); }
  function occupied(t) { return t - sameT.t < GAP ? sameT.n : 0; }
  function freePos(t, avoid) {
    var cand = [];
    for (var p = 0; p < 8; p++) if (t >= busy[p] + GAP) cand.push(p);
    if (cand.indexOf(avoid) >= 0 && cand.length > 1 && rng() < 0.78)
      cand = cand.filter(function (x) { return x !== avoid; });
    return cand.length ? pick(cand) : -1;
  }
  function emit(t, pos, kind, to, dur, star) {
    if (pos < 0) return false;
    var isCtr = kind === 'touch' || kind === 'ex' || kind === 'thold';
    if (t < busy[pos] + GAP) return false;
    if (isCtr) { if (t - ctrT.t < GAP && ctrT.n >= 1) return false; }
    else if (t - sameT.t < GAP && sameT.n >= 2) return false;
    if (kind === 'touch' || kind === 'thold') { if (t - lastTouch < beat * 1.5) return false; lastTouch = t; }
    if (kind === 'ex') { if (t - lastEx < beat * 1.5) return false; lastEx = t; }
    var n = { t: Math.round(t), k: kind, star: star || 0 };
    if (isCtr) {
      n.p = Math.floor(rng() * 8);
      n.z = kind === 'ex' ? 'E' : pick(['A', 'A', 'B', 'C']);
      if (kind === 'thold') n.d = Math.round(Math.max(beat, dur || beat * 2));
      busy[pos] = t + step;
    } else {
      n.p = pos;
      if (kind === 'hold') { n.d = Math.round(dur); busy[pos] = t + dur + GAP; }
      else if (kind === 'slide') {
        n.q = to; n.s = shape();
        n.d = Math.round(beat * 0.5);        // 半拍滑完，和真机一个量级
        busy[pos] = t + GAP * 2;
        busy[to] = Math.max(busy[to], t + beat * 0.5);
      } else busy[pos] = t + GAP;
    }
    notes.push(n);
    lastPos = pos;
    var slot = isCtr ? ctrT : sameT;
    if (t - slot.t < GAP) slot.n++; else { slot.t = t; slot.n = 1; }
    return true;
  }
  function kindOf(i, allowBreak) {
    var ws = W.slice();
    if (!allowBreak) ws[3] = 0;
    if (diffIdx < 2) { ws[4] = 0; ws[5] = 0; }
    if (i % 8 !== 0 && i % 8 !== 4) ws[3] = Math.round(ws[3] * 0.35);
    var tot = 0; for (var z = 0; z < ws.length; z++) tot += ws[z];
    if (tot <= 0) return 'tap';
    var r = rng() * tot, acc = 0, pool = ['tap', 'hold', 'slide', 'break', 'touch', 'ex'];
    for (var z2 = 0; z2 < ws.length; z2++) { acc += ws[z2]; if (r < acc) return pool[z2]; }
    return 'tap';
  }
  function advance(i, k) {
    var j = i + Math.max(1, k), nxt = (Math.floor(i / 16) + 1) * 16;
    return (j > nxt && nxt > i) ? nxt : j;
  }
  var i = 0;
  while (i < total) {
    var frac = i / total, mul = 0.55;
    for (var si2 = 0; si2 < SEGS.length; si2++)
      if (frac >= SEGS[si2][0] && frac < SEGS[si2][1]) { mul = SEGS[si2][2]; break; }
    var dens = clamp(nps * (step / 1000) * mul, 0.02, 0.95);
    var t = i * step, allowBreak = (i % 8 === 0);
    if (i % 16 === 0 && diffIdx >= 1 && rng() < (0.10 + diffIdx * 0.11)) {
      var bp = freePos(t, lastPos);
      if (bp >= 0 && occupied(t) < 2) {
        if (diffIdx >= 2 && rng() < 0.36) {
          var sp = pick([2, 3, 4, 5]);
          if (emit(t, bp, 'slide', (bp + sp * (rng() < .5 ? 1 : -1) + 8) % 8, 0, 1)) { i = advance(i, 2); continue; }
        } else if (emit(t, bp, 'tap', -1, 0, 1)) { i = advance(i, 2); continue; }
      }
    }
    if (rng() >= dens) { i++; continue; }
    if (occupied(t) >= 2) { i++; continue; }
    var r = rng(), a = MODES.alt, b = a + MODES.stair, c = b + MODES.chord, d = c + MODES.sweep;
    if (r < a) {
      var p0 = freePos(t, lastPos); if (p0 < 0) { i++; continue; }
      var p1 = (p0 + pick([2, 3, 4, 5])) % 8, k = 4 + Math.floor(rng() * 5), gp = dens > 0.5 ? 1 : 2;
      for (var j1 = 0; j1 < k; j1++) {
        var tt = (i + j1 * gp) * step, pp = (j1 % 2 === 0) ? p0 : p1;
        if (tt >= busy[pp] + GAP) { emit(tt, pp, 'tap'); busy[pp] = Math.max(busy[pp], tt + GAP); }
      }
      i = advance(i, k * gp); continue;
    }
    if (a <= r && r < b) {
      var p2 = freePos(t, lastPos); if (p2 < 0) { i++; continue; }
      var dir = rng() < .5 ? 1 : -1, k2 = 4 + Math.floor(rng() * 5), gp2 = dens > 0.55 ? 1 : 2;
      for (var j2 = 0; j2 < k2; j2++) {
        var tt2 = (i + j2 * gp2) * step, pp2 = (p2 + dir * j2 + 80) % 8;
        emit(tt2, pp2, 'tap'); busy[pp2] = Math.max(busy[pp2], tt2 + GAP);
      }
      i = advance(i, k2 * gp2); continue;
    }
    if (b <= r && r < c) {
      var p3 = freePos(t, lastPos); if (p3 < 0) { i++; continue; }
      var p4 = (p3 + pick([3, 4, 5])) % 8;
      if (emit(t, p3, 'tap')) emit(t, p4, 'tap');
      i = advance(i, 2); continue;
    }
    if (c <= r && r < d && W[2] > 0) {
      var p5 = freePos(t, lastPos); if (p5 < 0) { i++; continue; }
      var dir2 = rng() < .5 ? 1 : -1, k3 = 2 + Math.floor(rng() * 2);
      var span = pick(diffIdx <= 2 ? [1, 2, 3] : [2, 3, 4, 5]);
      for (var j3 = 0; j3 < k3; j3++) {
        var tt3 = (i + j3 * 4) * step;
        var pp3 = (p5 + dir2 * j3 * 2 + 80) % 8;
        var qq3 = (pp3 + dir2 * span + 80) % 8;
        emit(tt3, pp3, 'slide', qq3, 0, rng() < 0.14 ? 1 : 0);
        busy[pp3] = Math.max(busy[pp3], tt3 + GAP * 2);
        busy[qq3] = Math.max(busy[qq3], tt3 + beat * 0.5);
      }
      i = advance(i, k3 * 4); continue;
    }
    var kind = kindOf(i, allowBreak);
    if (kind === 'touch' && diffIdx >= 3 && rng() < 0.10) kind = 'thold';
    if (kind === 'touch' || kind === 'ex' || kind === 'thold') {
      emit(t, freePos(t, lastPos), kind, -1, beat * pick([1, 1.5, 2]), 0);
    } else {
      var pos = freePos(t, lastPos);
      if (pos < 0) { i++; continue; }
      if (kind === 'hold') emit(t, pos, 'hold', -1, beat * pick([1, 1.5, 2, 2, 3]), 0);
      else if (kind === 'slide') {
        var sp2 = pick(diffIdx <= 2 ? [1, 1, 2, 2, 3] : [1, 2, 3, 4, 5, 6]);
        var to2 = (pos + sp2 * (rng() < .5 ? 1 : -1) + 8) % 8;
        if (to2 === pos) to2 = (pos + 2) % 8;
        emit(t, pos, 'slide', to2, 0, (allowBreak && rng() < 0.16) ? 1 : 0);
      } else emit(t, pos, kind, -1, 0, kind === 'break' ? 1 : 0);
    }
    i++;
  }
  notes.sort(function (x, y) { return x.t - y.t || (x.p || 0) - (y.p || 0); });
  var counts = {};
  for (var ci = 0; ci < notes.length; ci++) {
    counts[notes[ci].k] = (counts[notes[ci].k] || 0) + 1;
    if (notes[ci].star) counts.break = (counts.break || 0) + 1;
  }
  return {
    song: { title: song.title || '未知曲', artist: song.artist || '', bpm: Math.round(bpm),
            ds: Math.round(ds * 10) / 10, diff: ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'RE:MASTER'][diffIdx] },
    bpm: Math.round(bpm), beat: beat, step: step,
    duration: (notes.length ? notes[notes.length - 1].t : duration * 1000) / 1000 + 2.2,
    notes: notes, counts: counts, source: 'gen'
  };
}

// ============================================================ 存档（成绩 / 设置 / 导入的谱面）
var LS = {
  get: function (k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
  set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { } },
  jget: function (k, d) { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } },
  jset: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }
};

// ============================================================ 成绩码（与 Python 侧同一套）
function djb36(s) {
  var h = 5381;
  for (var i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  var digits = '0123456789abcdefghijklmnopqrstuvwxyz', o = '';
  while (h > 0) { o = digits[h % 36] + o; h = Math.floor(h / 36); }
  return (o || '0').slice(0, 5);
}
function b64enc(str) {
  if (typeof btoa === 'function') return btoa(unescape(encodeURIComponent(str)));
  return '';                                    // node 烟测里没有 btoa，成绩码降级为空
}
function makeCode(obj) {
  var b = b64enc(JSON.stringify(obj));
  if (!b) return '';
  return 'MM1:' + b + ':' + djb36(b);
}

// ============================================================ 引擎状态
var cv = document.getElementById('dxcv');
if (!cv) return;
var ctx = cv.getContext('2d');
var CW = cv.width, CH = cv.height;

var S = {
  scene: 'select',            // select | play | result | import | help
  chart: null,
  notes: [], idx: 0,
  t0: 0, now: 0,
  running: false,
  combo: 0, maxCombo: 0,
  cnt: { cp: 0, p: 0, gr: 0, gd: 0, miss: 0 },
  fast: 0, slow: 0,
  judged: [],
  flash: [0, 0, 0, 0, 0, 0, 0, 0],
  keyFlash: [0, 0, 0, 0, 0, 0, 0, 0],
  ctrFlash: 0,
  ripple: [],                       // 命中涟漪特效队列
  lastJudge: null, lastJudgeAt: -9999,
  speed: 1.0, offset: 0, appr: 1500,
  selLib: 0, selDiff: 3, selRow: 0,
  libFiltered: [],
  importText: '', importMsg: '',
  importDiv: 4,
  customCharts: LS.jget('dx_custom_charts', []),
  result: null,
  paused: false
};

// 设置持久化
var st = LS.jget('dx_settings', {});
S.speed = st.speed || 1.0;
S.offset = st.offset || 0;
AU.on = st.se === undefined ? true : st.se;
AU.bgmOn = st.bgm === undefined ? true : st.bgm;
AU.setVol(st.vol === undefined ? 0.7 : st.vol);
AU.setSe(st.seVol === undefined ? 0.55 : st.seVol);

function saveSettings() {
  LS.jset('dx_settings', { speed: S.speed, offset: S.offset, se: AU.on, bgm: AU.bgmOn,
                           vol: AU.vol, seVol: AU.seVol });
}

// ============================================================ 几何
// 独立版（不是嵌在 iframe 里）时，画布跟着窗口／屏幕铺满，手机上就是全屏机台。
var FULL = (window.parent === window);
// 嵌进「大厅」时（window.DXHUB.idle 为真）表示机台这一页没在显示：
// 这时候键盘、粘贴、绘制全部让出去，免得在大厅别处打字也把机台敲响。
function hubIdle() { return !!(window.DXHUB && window.DXHUB.idle); }
var CX = Math.round(CW / 2), CY = Math.round(CH * 0.52);
var R_J = Math.round(Math.min(CW, CH) * 0.40);      // 判定环
var R_0 = Math.round(R_J * 0.20);                   // 出生半径
var R_C = Math.round(R_J * 0.46);                   // 中央屏
function px(a, r) { return CX + Math.cos(a) * r; }
function py(a, r) { return CY + Math.sin(a) * r; }

function relayout() {
  if (!FULL) return;
  var w = Math.max(320, window.innerWidth || CW);
  var h = Math.max(320, window.innerHeight || CH);
  var dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.style.width = w + 'px';
  cv.style.height = h + 'px';
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(h * dpr);
  if (typeof ctx !== 'undefined' && ctx && ctx.setTransform) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  CW = w; CH = h;                                  // 之后所有绘制用 CSS 像素坐标
  CX = Math.round(CW / 2); CY = Math.round(CH * 0.52);
  R_J = Math.round(Math.min(CW, CH) * 0.40);
  R_0 = Math.round(R_J * 0.20);
  R_C = Math.round(R_J * 0.46);
}

// ============================================================ 谱面装载
function loadChart(c) {
  c = c || S.chart;
  if (!c) return false;
  S.chart = c;
  S.notes = (c.notes || []).map(function (n) {
    return {
      t: n.t, k: n.k, p: n.p || 0, q: n.q, d: n.d || 0, s: n.s || 'line',
      star: n.star ? 1 : 0, z: n.z || 'A',
      done: false, lv: null, holding: false, sliding: false, started: false,
      slideUntil: 0, holdFrom: 0
    };
  });
  S.notes.sort(function (a, b) { return a.t - b.t; });
  S.idx = 0; S.combo = 0; S.maxCombo = 0;
  S.cnt = { cp: 0, p: 0, gr: 0, gd: 0, miss: 0 };
  S.fast = 0; S.slow = 0; S.judged = [];
  S.result = null; S.lastJudge = null;
  return true;
}
function totalNotes() { return S.notes.length; }
function totalBreaks() { var n = 0; for (var i = 0; i < S.notes.length; i++) if (S.notes[i].star) n++; return n; }
function liveAch() {
  var s = 0, cpb = 0;
  for (var i = 0; i < S.judged.length; i++) {
    var j = S.judged[i];
    s += VAL[j.lv] || 0;
    if (j.star && j.lv === 'cp') cpb++;
  }
  var n = S.notes.length || 1;
  var bonus = 0;
  if (totalBreaks() > 0) bonus = Math.min(BREAK_CAP, 100 * BREAK_BONUS * cpb / (NOTE_POINTS * n));
  return s / n * 100 + bonus;
}

// ============================================================ 判定
function judgeLv(delta) {
  var ad = Math.abs(delta);
  if (ad <= W_CP) return 'cp';
  if (ad <= W_P) return 'p';
  if (ad <= W_GR) return 'gr';
  if (ad <= W_GD) return 'gd';
  return 'miss';
}
function finishNote(n, lv, delta) {
  n.done = true; n.lv = lv;
  S.judged.push({ lv: lv, star: n.star });
  if (lv === 'miss') { S.cnt.miss++; S.combo = 0; showJudge('MISS', C_MISS); AU.se('miss'); return; }
  S.cnt[lv]++;
  S.combo++;
  if (S.combo > S.maxCombo) S.maxCombo = S.combo;
  if (delta !== undefined && lv !== 'cp') { if (delta < 0) S.fast++; else S.slow++; }
  var label = lv === 'cp' ? 'CRITICAL PERFECT' : lv === 'p' ? 'PERFECT'
            : lv === 'gr' ? 'GREAT' : 'GOOD';
  var color = lv === 'cp' ? C_STAR : lv === 'p' ? C_TAP : lv === 'gr' ? '#7FD1FF' : '#9aa7ad';
  showJudge(label, color);
  var seKind = n.k === 'slide' ? 'slide' : n.k === 'hold' ? 'hold'
             : n.k === 'touch' || n.k === 'thold' ? 'touch' : n.k === 'ex' ? 'ex'
             : (n.star ? 'break' : 'tap');
  AU.se(seKind, n.star);
  S.ripple.push({ t: performance.now(), color: color, big: !!(n.star || lv === 'cp') });
  while (S.ripple.length > 14) S.ripple.shift();
}
function beatHalf() { var b = (S.chart && S.chart.beat) ? S.chart.beat : 500; return Math.max(200, b * 0.5); }
function showJudge(text, color) { S.lastJudge = { text: text, color: color }; S.lastJudgeAt = S.now; }

function findNote(kind, pos, nowMs) {
  var best = null, bd = 1e9;
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (n.done || n.k !== kind) continue;
    if (n.p !== pos) continue;
    var d = nowMs - n.t;
    if (d > W_MISS) continue;
    if (d < -W_MISS) break;
    if (Math.abs(d) < Math.abs(bd)) { bd = d; best = n; }
  }
  return best ? [best, bd] : null;
}
function findAnyRing(pos, nowMs) {
  // 环上任意类型（tap / hold / slide 头）都可被这个键触发
  var best = null, bd = 1e9;
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (n.done || n.k === 'touch' || n.k === 'ex' || n.k === 'thold') continue;
    if (n.p !== pos) continue;
    var d = nowMs - n.t;
    if (d > W_MISS) continue;
    if (d < -W_MISS) break;
    if (Math.abs(d) < Math.abs(bd)) { bd = d; best = n; }
  }
  return best ? [best, bd] : null;
}
function findCenter(nowMs) {
  var best = null, bd = 1e9;
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (n.done || (n.k !== 'touch' && n.k !== 'ex' && n.k !== 'thold')) continue;
    var d = nowMs - n.t;
    if (d > W_MISS) continue;
    if (d < -W_MISS) break;
    if (Math.abs(d) < Math.abs(bd)) { bd = d; best = n; }
  }
  return best ? [best, bd] : null;
}

function pressRing(pos) {
  var nowMs = S.now;
  S.keyFlash[pos] = 1;
  var r = findAnyRing(pos, nowMs);
  if (!r) { return; }
  var n = r[0], bd = r[1];
  var lv = judgeLv(bd);
  if (n.k === 'hold') {
    finishNote(n, lv, bd);
    n.holding = true; n.holdFrom = nowMs;
    return;
  }
  if (n.k === 'slide') {
    finishNote(n, lv, bd);
    n.sliding = true;
    n.slideUntil = nowMs + Math.max(200, n.d || beatHalf());
    return;
  }
  finishNote(n, lv, bd);
}
function releaseRing(pos) {
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (!n.holding || n.p !== pos) continue;
    n.holding = false;
    var held = S.now - n.holdFrom;
    if (held < (n.d || 0) * 0.72) {           // 提前松手 → 掉到 GOOD
      n.lv = 'gd';
      var jr = S.judged[S.judged.length - 1];
      if (jr && jr.lv !== 'gd' && jr.lv !== 'miss') {
        S.cnt[jr.lv]--; S.cnt.gd++;
        jr.lv = 'gd';
      }
    }
  }
}
function slideEnd(pos) {
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (!n.sliding || n.q !== pos) continue;
    n.sliding = false;
  }
}
function pressCenter() {
  var nowMs = S.now;
  S.ctrFlash = 1;
  var r = findCenter(nowMs);
  if (!r) return;
  var n = r[0], bd = r[1];
  var lv = judgeLv(bd);
  if (n.k === 'thold') { finishNote(n, lv, bd); n.holding = true; n.holdFrom = nowMs; }
  else finishNote(n, lv, bd);
}
function releaseCenter() {
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (!n.holding || n.k !== 'thold') continue;
    n.holding = false;
    if (S.now - n.holdFrom < (n.d || 0) * 0.72) {
      n.lv = 'gd';
      var jc = S.judged[S.judged.length - 1];
      if (jc && jc.lv !== 'gd' && jc.lv !== 'miss') {
        S.cnt[jc.lv]--; S.cnt.gd++;
        jc.lv = 'gd';
      }
    }
  }
}

// ============================================================ 主循环
function startPlay() {
  if (S.running) return;                    // 幂等：已经在跑就不重来（避免重复启动把整局冲掉）
  if (!loadChart(S.chart)) return;
  AU.resume();
  S.scene = 'play';
  S.running = true;
  S.t0 = performance.now() + 2200;          // 2.2 秒准备
  S.now = 0;
  var dh = document.getElementById('dxhint'); if (dh) dh.textContent = '';
  try { AU.startBGM(S.chart.bpm || 120, (S.chart.duration || 80) * 1000 + 3000); }
  catch (e) { /* 伴奏合成失败不影响打歌 */ }
}
function endPlay() {
  S.running = false;
  AU.stopBGM();
  var c = S.chart || {};
  var ach = Math.round(liveAch() * 10000) / 10000;
  var rk = rankOf(ach);
  var key = 'dx_best_' + (c.song ? c.song.title : '') + '_' + (c.song ? c.song.diff : '');
  var prev = parseFloat(LS.get(key, '0')) || 0;
  var isNew = ach > prev;
  if (isNew) LS.set(key, String(ach));
  var payload = {
    g: 'dx', t: (c.song && c.song.title) || (c.title) || '',
    d: (c.song && c.song.diff) || (c.diff) || '',
    ds: (c.song && c.song.ds) || c.ds || 0,
    ach: ach, rk: rk, mx: S.maxCombo,
    cp: S.cnt.cp, p: S.cnt.p, gr: S.cnt.gr, gd: S.cnt.gd, m: S.cnt.miss,
    fast: S.fast, slow: S.slow, n: S.notes.length
  };
  S.result = {
    ach: ach, rk: rk, isNew: isNew, prev: prev,
    cnt: S.cnt, fast: S.fast, slow: S.slow, maxCombo: S.maxCombo,
    total: S.notes.length, code: makeCode(payload), payload: payload
  };
  S.scene = 'result';
  AU.se(isNew ? 'clear' : 'coin');
  window.__dxLastResult = S.result;
  if (window.__dxOnResult) { try { window.__dxOnResult(S.result); } catch (e) {} }
}

function sweep(nowMs) {
  // 时间推到 nowMs 之后，把该判 MISS 的判掉、该结束的 HOLD/SLIDE 收尾。
  // 抽成独立函数是为了能在 node 里手动推进整首做烟测。
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    if (n.done && !n.holding && !n.sliding) continue;
    if (n.holding) {
      if (nowMs >= n.holdFrom + (n.d || 0)) n.holding = false;
      continue;
    }
    if (n.sliding) {
      if (nowMs > n.slideUntil) {           // 没送到终点 → 掉到 GOOD
        n.sliding = false;
        n.lv = 'gd';
        var jl = S.judged[S.judged.length - 1];
        if (jl && jl.lv !== 'gd' && jl.lv !== 'miss') {
          S.cnt[jl.lv]--; S.cnt.gd++;       // 计数跟着改，别让结算页自相矛盾
          jl.lv = 'gd';
        }
      }
      continue;
    }
    if (!n.done && nowMs > n.t + W_GD) finishNote(n, 'miss');
  }
}

function tick() {
  if (hubIdle()) { window.__dxRAF = requestAnimationFrame(tick); return; }      // 大厅在别的页面：只空转
  if (S.scene === 'play' && S.running) {
    S.now = performance.now() - S.t0;
    sweep(S.now - S.offset);
    var last = S.notes.length ? S.notes[S.notes.length - 1] : null;
    if (last && S.now > (last.t + (last.d || 0) + 1800)) endPlay();
  }
  for (var f = 0; f < 8; f++) { S.flash[f] *= 0.86; S.keyFlash[f] *= 0.80; }
  S.ctrFlash *= 0.86;
  draw();
  window.__dxRAF = requestAnimationFrame(tick);
}

// ============================================================ 绘制
function starPath(c2, x, y, r, spikes) {
  c2.beginPath();
  for (var i = 0; i < spikes * 2; i++) {
    var a = Math.PI * i / spikes - Math.PI / 2;
    var rr = (i % 2 === 0) ? r : r * 0.46;
    if (i === 0) c2.moveTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
    else c2.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  c2.closePath();
}
function slidePath(c2, n, prog) {
  // 按形状画出 SLIDE 的轨迹（prog 0→1 是滑动进度）
  var a0 = POS_A[n.p], a1 = POS_A[n.q];
  var r0 = R_J, r1 = R_J;
  c2.beginPath();
  var steps = 26, cur;
  if (n.s === 'line') {
    var x0 = px(a0, r0), y0 = py(a0, r0), x1 = px(a1, r1), y1 = py(a1, r1);
    c2.moveTo(x0, y0);
    c2.lineTo(lerp(x0, x1, prog), lerp(y0, y1, prog));
  } else if (n.s === 'arc' || n.s === 'arc_l' || n.s === 'arc_r') {
    var dir = n.s === 'arc_l' ? -1 : 1;
    var da = a1 - a0;
    while (da > Math.PI) da -= Math.PI * 2;
    while (da < -Math.PI) da += Math.PI * 2;
    if (n.s === 'arc_l' && da > 0) da -= Math.PI * 2;
    if (n.s === 'arc_r' && da < 0) da += Math.PI * 2;
    for (var i = 0; i <= steps; i++) {
      var t = i / steps * prog;
      var a = a0 + da * t;
      var r = lerp(r0, r1, t);
      var x = px(a, r), y = py(a, r);
      if (i === 0) c2.moveTo(x, y); else c2.lineTo(x, y);
    }
  } else if (n.s === 'v' || n.s === 'wifi') {
    var mid = n.s === 'v' ? 0.55 : 0.5;
    var rr = n.s === 'v' ? R_J * 0.62 : R_J * 0.30;
    var am = (a0 + a1) / 2;
    var pts = [[a0, r0], [am, rr], [a1, r1]];
    if (n.s === 'wifi') pts = [[a0, r0], [(a0 + am) / 2, rr], [am, R_J * 0.72], [(am + a1) / 2, rr], [a1, r1]];
    var tot = pts.length - 1;
    var tt = prog * tot, seg = Math.min(tot - 1, Math.floor(tt)), ft = tt - seg;
    c2.moveTo(px(pts[0][0], pts[0][1]), py(pts[0][0], pts[0][1]));
    for (var j = 1; j <= seg; j++) c2.lineTo(px(pts[j][0], pts[j][1]), py(pts[j][0], pts[j][1]));
    var aA = lerp(pts[seg][0], pts[seg + 1][0], ft), aB = lerp(pts[seg][1], pts[seg + 1][1], ft);
    c2.lineTo(px(aA, aB), py(aA, aB));
  } else if (n.s === 's_cur' || n.s === 'z_cur') {
    var sgn = n.s === 's_cur' ? 1 : -1;
    c2.moveTo(px(a0, r0), py(a0, r0));
    for (var k = 0; k <= steps; k++) {
      var t2 = k / steps * prog;
      var a2 = lerp(a0, a1, t2);
      var wob = Math.sin(t2 * Math.PI) * 0.30 * sgn;
      var r2 = R_J * (1 - wob);
      var x2 = px(a2, r2), y2 = py(a2, r2);
      c2.lineTo(x2, y2);
    }
  } else {                                    // fan 扇形
    var aStart = a0, aEnd = a1;
    var da2 = aEnd - aStart;
    while (da2 > Math.PI) da2 -= Math.PI * 2;
    while (da2 < -Math.PI) da2 += Math.PI * 2;
    c2.moveTo(px(aStart, R_J * 0.35), py(aStart, R_J * 0.35));
    for (var m2 = 0; m2 <= steps; m2++) {
      var t3 = m2 / steps * prog;
      var a3 = aStart + da2 * t3;
      c2.lineTo(px(a3, R_J * 0.35 + R_J * 0.55 * Math.sin(t3 * Math.PI)),
                py(a3, R_J * 0.35 + R_J * 0.55 * Math.sin(t3 * Math.PI)));
    }
  }
  cur = null;
}

function drawRing() {
  ctx.save();
  // 判定环随 BPM 呼吸发光（舞萌最具辨识度的视觉）
  var _rt = performance.now() / 1000;
  var _rbpm = (S.chart && S.chart.bpm) || 132;
  var _rbeat = 60 / Math.max(40, _rbpm);
  var _rl = 0.5 + 0.5 * Math.cos(((_rt % _rbeat) / _rbeat) * Math.PI * 2);

  // 外圈光晕
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  var _hg = ctx.createRadialGradient(CX, CY, R_J * 0.86, CX, CY, R_J * 1.26);
  _hg.addColorStop(0, 'rgba(57,197,187,0)');
  _hg.addColorStop(0.5, 'rgba(57,197,187,' + (0.05 + _rl * 0.08).toFixed(3) + ')');
  _hg.addColorStop(1, 'rgba(57,197,187,0)');
  ctx.fillStyle = _hg;
  ctx.beginPath(); ctx.arc(CX, CY, R_J * 1.26, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  // 判定环本体
  ctx.save();
  ctx.shadowColor = 'rgba(57,197,187,.9)';
  ctx.shadowBlur = 10 + _rl * 18;
  ctx.lineWidth = 3;
  ctx.strokeStyle = 'rgba(150,225,230,' + (0.32 + _rl * 0.30).toFixed(3) + ')';
  ctx.beginPath(); ctx.arc(CX, CY, R_J, 0, Math.PI * 2); ctx.stroke();
  ctx.restore();

  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(160,200,205,.14)';
  ctx.beginPath(); ctx.arc(CX, CY, R_J * 0.55, 0, Math.PI * 2); ctx.stroke();
  // 8 个分区的键位提示
  for (var i = 0; i < 8; i++) {
    var a = POS_A[i];
    var lit = S.keyFlash[i];
    var x = px(a, R_J * 1.13), y = py(a, R_J * 1.13);
    ctx.beginPath();
    ctx.arc(x, y, R_J * 0.085, 0, Math.PI * 2);
    ctx.fillStyle = lit > 0.05 ? 'rgba(57,197,187,' + (0.18 + lit * 0.55) + ')'
                               : 'rgba(255,255,255,.05)';
    ctx.fill();
    ctx.strokeStyle = lit > 0.05 ? C_TAP : 'rgba(160,200,205,.24)';
    ctx.lineWidth = lit > 0.05 ? 2 : 1;
    ctx.stroke();
    ctx.fillStyle = lit > 0.05 ? '#eafffd' : 'rgba(200,225,228,.55)';
    ctx.font = 'bold ' + Math.round(R_J * 0.085) + 'px Consolas,monospace';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(KEYS[i].toUpperCase(), x, y);
  }

  // 命中涟漪：从判定环向外扩散的一圈光波
  var _rn = performance.now();
  for (var ri = S.ripple.length - 1; ri >= 0; ri--) {
    var rp = S.ripple[ri];
    var age = (_rn - rp.t) / 480;
    if (age >= 1) { S.ripple.splice(ri, 1); continue; }
    if (age < 0) continue;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = (1 - age) * 0.8;
    ctx.strokeStyle = rp.color;
    ctx.lineWidth = (rp.big ? 4.5 : 2.6) * (1 - age) + 0.6;
    ctx.beginPath();
    ctx.arc(CX, CY, R_J * (1 + age * (rp.big ? 0.5 : 0.32)), 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}

function drawNotes(nowMs) {
  var appr = S.appr / S.speed;
  for (var i = 0; i < S.notes.length; i++) {
    var n = S.notes[i];
    var dt = n.t - nowMs;
    if (dt > appr + 60) break;
    if (dt < -420) continue;
    if (n.done && !n.holding && !n.sliding) continue;

    var isCtr = n.k === 'touch' || n.k === 'ex' || n.k === 'thold';
    if (isCtr) { drawCenterNote(n, dt, appr); continue; }

    var prog = clamp(1 - dt / appr, 0, 1.25);
    var r = R_0 + (R_J - R_0) * Math.min(1, prog);
    var a = POS_A[n.p];
    var x = px(a, r), y = py(a, r);
    var size = R_J * 0.115 * (0.75 + prog * 0.35);

    // HOLD / SLIDE 的尾巴与轨迹
    if (n.k === 'hold') {
      var tailEnd = n.holding ? R_J : (n.d ? R_J : R_J);
      ctx.save();
      ctx.strokeStyle = n.star ? 'rgba(245,212,66,.55)' : 'rgba(127,209,255,.55)';
      ctx.lineWidth = size * 0.85;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.arc(CX, CY, R_J, POS_A[n.p] - 0.13, POS_A[n.p] + 0.13);
      ctx.stroke();
      ctx.restore();
    }
    if (n.k === 'slide') {
      var sp = n.sliding ? clamp((nowMs - (n.t)) / Math.max(1, n.d || 260), 0, 1)
                         : (n.done ? 1 : clamp(prog, 0, 1));
      ctx.save();
      ctx.strokeStyle = n.star ? 'rgba(245,212,66,.60)' : 'rgba(176,124,255,.60)';
      ctx.lineWidth = n.star ? size * 0.55 : size * 0.42;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      slidePath(ctx, n, n.done || n.sliding ? sp : Math.max(0.001, (prog - 0.55) / 0.45));
      ctx.stroke();
      ctx.restore();
    }

    // 音符本体
    ctx.save();
    if (n.star) {
      ctx.fillStyle = C_STAR;
      ctx.shadowColor = 'rgba(245,212,66,.85)'; ctx.shadowBlur = size * 1.1;
      starPath(ctx, x, y, size * 1.15, 5);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = 'rgba(255,255,255,.92)'; ctx.lineWidth = Math.max(1, size * 0.14);
      ctx.stroke();
    } else if (n.k === 'slide') {
      ctx.fillStyle = C_SLIDE;
      ctx.shadowColor = 'rgba(176,124,255,.7)'; ctx.shadowBlur = size * 0.8;
      ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = Math.max(1, size * 0.12); ctx.stroke();
      // 箭头指向终点
      var aq = POS_A[n.q];
      var dxp = px(aq, R_J) - x, dyp = py(aq, R_J) - y;
      var len = Math.sqrt(dxp * dxp + dyp * dyp) || 1;
      ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = Math.max(1, size * 0.10);
      ctx.beginPath();
      ctx.moveTo(x + dxp / len * size * 0.6, y + dyp / len * size * 0.6);
      ctx.lineTo(x + dxp / len * size * 1.5, y + dyp / len * size * 1.5);
      ctx.stroke();
    } else if (n.k === 'hold') {
      ctx.fillStyle = C_HOLD;
      ctx.shadowColor = 'rgba(127,209,255,.7)'; ctx.shadowBlur = size * 0.7;
      ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = Math.max(1, size * 0.12); ctx.stroke();
    } else {
      ctx.fillStyle = C_TAP;
      ctx.shadowColor = 'rgba(57,197,187,.7)'; ctx.shadowBlur = size * 0.7;
      ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = Math.max(1, size * 0.12); ctx.stroke();
    }
    ctx.restore();

    // 到达判定环时的高亮
    if (Math.abs(dt) < 90 && !n.done) {
      ctx.save();
      ctx.strokeStyle = n.star ? 'rgba(245,212,66,.9)' : 'rgba(255,255,255,.7)';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, size * 1.5, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
    }
  }
}

function drawCenterNote(n, dt, appr) {
  var prog = clamp(1 - dt / appr, 0, 1.25);
  var rr = R_C * (n.z === 'C' ? 0.28 : n.z === 'B' ? 0.62 : 0.92) * clamp(prog, 0.15, 1);
  var ang = POS_A[n.p || 0];
  var x = CX + Math.cos(ang) * rr, y = CY + Math.sin(ang) * rr;
  var size = R_C * 0.20 * (0.7 + prog * 0.4);
  ctx.save();
  if (n.k === 'ex') {
    ctx.fillStyle = C_EX;
    ctx.shadowColor = 'rgba(255,176,32,.8)'; ctx.shadowBlur = size;
    starPath(ctx, x, y, size * 1.1, 6); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.4; ctx.stroke();
  } else if (n.star) {
    ctx.fillStyle = C_STAR;
    ctx.shadowColor = 'rgba(245,212,66,.8)'; ctx.shadowBlur = size;
    starPath(ctx, x, y, size * 1.1, 5); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.3; ctx.stroke();
  } else {
    ctx.fillStyle = C_TOUCH;
    ctx.shadowColor = 'rgba(255,143,209,.7)'; ctx.shadowBlur = size * 0.8;
    ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.lineWidth = 1.2; ctx.stroke();
  }
  ctx.restore();
}

function drawHud() {
  var c = S.chart || {};
  var song = c.song || {};
  ctx.save();
  ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  ctx.fillStyle = 'rgba(223,240,239,.95)';
  ctx.font = 'bold 19px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText(song.title || c.title || '', 16, 14);
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText((song.artist || c.artist || '') +
    '　BPM ' + (c.bpm || 0) + '　' + (song.diff || c.diff || '') +
    '　定数 ' + (song.ds !== undefined ? song.ds : (c.ds || '')), 16, 38);

  // 达成率
  var ach = liveAch();
  ctx.textAlign = 'right';
  ctx.font = 'bold 30px Consolas,monospace';
  ctx.fillStyle = ach >= 100 ? C_STAR : '#dff0ef';
  ctx.fillText(ach.toFixed(4) + '%', CW - 16, 12);
  ctx.font = '11px "Segoe UI",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText('达成率　目标 ' + (100 + (totalBreaks() ? Math.min(1, 100 * BREAK_BONUS * totalBreaks() / (NOTE_POINTS * (S.notes.length || 1))) : 0)).toFixed(4) + '%',
    CW - 16, 46);

  // COMBO（中央屏里）
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  if (S.combo > 2) {
    ctx.font = 'bold ' + Math.round(R_C * 0.42) + 'px Consolas,monospace';
    ctx.fillStyle = '#eafffd';
    ctx.fillText(String(S.combo), CX, CY - R_C * 0.06);
    ctx.font = Math.round(R_C * 0.15) + 'px "Segoe UI",sans-serif';
    ctx.fillStyle = 'rgba(160,200,205,.8)';
    ctx.fillText('COMBO', CX, CY + R_C * 0.24);
  }
  // 判定文字
  if (S.lastJudge && S.now - S.lastJudgeAt < 620) {
    var al = 1 - (S.now - S.lastJudgeAt) / 620;
    ctx.globalAlpha = clamp(al * 1.6, 0, 1);
    ctx.font = 'bold ' + Math.round(R_C * 0.24) + 'px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillStyle = S.lastJudge.color;
    ctx.fillText(S.lastJudge.text, CX, CY - R_C * 1.55);
    ctx.globalAlpha = 1;
  }
  // 进度条
  var total = (c.duration || 80) * 1000;
  var pr = clamp(S.now / total, 0, 1);
  ctx.fillStyle = 'rgba(255,255,255,.10)';
  ctx.fillRect(0, CH - 5, CW, 5);
  ctx.fillStyle = C_TAP;
  ctx.fillRect(0, CH - 5, CW * pr, 5);
  ctx.restore();
}

function drawCenterScreen() {
  ctx.save();
  ctx.beginPath(); ctx.arc(CX, CY, R_C, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(10,18,24,.72)'; ctx.fill();
  ctx.strokeStyle = S.ctrFlash > 0.05 ? 'rgba(255,143,209,.9)' : 'rgba(160,200,205,.30)';
  ctx.lineWidth = S.ctrFlash > 0.05 ? 3 : 1.5;
  ctx.stroke();
  // 中央屏的三个区
  [0.28, 0.62, 0.92].forEach(function (rr, i) {
    ctx.beginPath(); ctx.arc(CX, CY, R_C * rr, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(160,200,205,.13)'; ctx.lineWidth = 1; ctx.stroke();
  });
  ctx.restore();
}

function drawSelect() {
  ctx.save();
  ctx.fillStyle = 'rgba(223,240,239,.96)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.font = 'bold 26px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('舞萌 DX 机台', CX, 26);
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText('选一首，然后投币开打　·　左右选难度　·　Enter 开始　·　I 导入谱面　·　H 帮助', CX, 60);

  // 曲库列表
  var list = S.libFiltered.length ? S.libFiltered : LIB;
  var perPage = 8;
  var start = Math.max(0, Math.min(list.length - perPage, S.selRow - 3));
  ctx.textAlign = 'left';
  for (var i = 0; i < perPage; i++) {
    var idx = start + i;
    if (idx >= list.length) break;
    var it = list[idx];
    var y = 92 + i * 34;
    var on = idx === S.selRow;
    ctx.fillStyle = on ? 'rgba(57,197,187,.20)' : 'rgba(255,255,255,.035)';
    ctx.fillRect(40, y - 4, CW - 200, 30);
    if (on) { ctx.strokeStyle = C_TAP; ctx.lineWidth = 1.5; ctx.strokeRect(40, y - 4, CW - 200, 30); }
    ctx.fillStyle = on ? '#eafffd' : 'rgba(220,238,240,.86)';
    ctx.font = (on ? 'bold ' : '') + '14px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText((it.title || '').slice(0, 34), 52, y + 2);
    ctx.fillStyle = 'rgba(150,175,180,.85)';
    ctx.font = '11px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText((it.artist || '').slice(0, 22) + '　BPM ' + (it.bpm || 0), 52, y + 18);
  }
  if (!list.length) {
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(150,175,180,.9)';
    ctx.font = '13px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText('曲库是空的 —— 按 I 导入一份 Simai 谱面，或直接用外面选好的那首。', CX, 110);
  }

  // 难度列
  var diffs = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'RE:MASTER'];
  var dcn = ['基础', '进阶', '专家', '大师', '里大师'];
  var dc = ['#3FA34D', '#E8A33D', '#E5484D', '#A66BFF', '#F2B8E8'];
  ctx.textAlign = 'left';
  for (var d = 0; d < 5; d++) {
    var dy = 110 + d * 56;
    var on2 = d === S.selDiff;
    ctx.fillStyle = on2 ? dc[d] : 'rgba(255,255,255,.06)';
    ctx.globalAlpha = on2 ? 0.30 : 1;
    ctx.fillRect(CW - 148, dy - 6, 116, 46);
    ctx.globalAlpha = 1;
    if (on2) { ctx.strokeStyle = dc[d]; ctx.lineWidth = 2; ctx.strokeRect(CW - 148, dy - 6, 116, 46); }
    ctx.fillStyle = on2 ? '#ffffff' : 'rgba(210,230,232,.8)';
    ctx.font = 'bold 12px Consolas,monospace';
    ctx.fillText(diffs[d], CW - 140, dy + 2);
    ctx.font = '11px "Microsoft YaHei",sans-serif';
    ctx.fillStyle = on2 ? 'rgba(255,255,255,.9)' : 'rgba(160,190,195,.85)';
    ctx.fillText(dcn[d], CW - 140, dy + 22);
  }

  // 底部设置
  ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.font = '12px Consolas,monospace';
  ctx.fillText('速度 ' + S.speed.toFixed(1) + '  ( [ / ] 调 )　　判定偏移 ' + S.offset + 'ms  ( - / = 调 )　　' +
    '判定音 ' + (AU.on ? '开' : '关') + ' (M)　　伴奏 ' + (AU.bgmOn ? '开' : '关') + ' (B)　　音量 ' +
    Math.round(AU.vol * 100) + '% ( , / . )', 40, CH - 34);
  ctx.fillStyle = 'rgba(150,175,180,.65)';
  ctx.font = '11px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('已导入谱面 ' + S.customCharts.length + ' 张　·　↑↓ 选曲　·　←→ 选难度　·　Enter 开始', 40, CH - 18);
  ctx.restore();
}

function drawResult() {
  var r = S.result; if (!r) return;
  ctx.save();
  ctx.fillStyle = 'rgba(4,8,12,.90)';
  ctx.fillRect(0, 0, CW, CH);
  var c = S.chart || {}, song = c.song || {};
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.fillStyle = 'rgba(223,240,239,.96)';
  ctx.font = 'bold 22px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText(song.title || c.title || '', CX, 48);
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText((song.diff || '') + '　定数 ' + (song.ds !== undefined ? song.ds : '') +
    '　BPM ' + (c.bpm || 0), CX, 78);

  // 评级
  var rc = r.ach >= 100 ? C_STAR : r.ach >= 98 ? '#39C5BB' : r.ach >= 90 ? '#7FD1FF' : '#dff0ef';
  ctx.font = 'bold ' + '78px' + ' Consolas,monospace';
  ctx.fillStyle = rc;
  ctx.shadowColor = rc; ctx.shadowBlur = 26;
  ctx.fillText(r.rk, CX, 96);
  ctx.shadowBlur = 0;
  ctx.font = 'bold 30px Consolas,monospace';
  ctx.fillStyle = '#eafffd';
  ctx.fillText(r.ach.toFixed(4) + '%', CX, 186);
  if (r.isNew) {
    ctx.font = 'bold 13px "Segoe UI",sans-serif';
    ctx.fillStyle = C_STAR;
    ctx.fillText('★ NEW RECORD　（旧纪录 ' + (r.prev ? r.prev.toFixed(4) + '%' : '无') + '）', CX, 224);
  } else {
    ctx.font = '12px "Segoe UI",sans-serif';
    ctx.fillStyle = 'rgba(150,175,180,.85)';
    ctx.fillText('个人最佳 ' + r.prev.toFixed(4) + '%', CX, 224);
  }

  // 明细
  var rows = [
    ['CRITICAL PERFECT', r.cnt.cp, C_STAR],
    ['PERFECT', r.cnt.p, '#39C5BB'],
    ['GREAT', r.cnt.gr, '#7FD1FF'],
    ['GOOD', r.cnt.gd, '#9aa7ad'],
    ['MISS', r.cnt.miss, C_MISS],
    ['MAX COMBO', r.maxCombo + ' / ' + r.total, '#eafffd'],
    ['FAST / SLOW', r.fast + ' / ' + r.slow, '#FFB020']
  ];
  ctx.textAlign = 'left';
  for (var i = 0; i < rows.length; i++) {
    var y = 252 + i * 26;
    ctx.fillStyle = rows[i][2];
    ctx.font = '13px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText(rows[i][0], CX - 210, y);
    ctx.textAlign = 'right';
    ctx.font = 'bold 15px Consolas,monospace';
    ctx.fillText(String(rows[i][1]), CX + 210, y);
    ctx.textAlign = 'left';
  }

  // 成绩码
  ctx.textAlign = 'center';
  ctx.font = '11px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText('成绩码 —— 复制后粘回主界面的「成绩登记处」，这局就存进你的账号', CX, CH - 74);
  ctx.fillStyle = 'rgba(5,12,18,.9)';
  ctx.fillRect(60, CH - 56, CW - 120, 26);
  ctx.strokeStyle = 'rgba(57,197,187,.4)'; ctx.lineWidth = 1; ctx.strokeRect(60, CH - 56, CW - 120, 26);
  ctx.fillStyle = '#9fe8e2';
  ctx.font = '11px Consolas,monospace';
  var code = r.code || '（浏览器不支持 base64，无法生成成绩码）';
  // 按画布实际宽度截断：手机上 CW 可能只有 380 出头，写死 96 个字符会溢出屏幕
  var _avail = CW - 130;
  if (ctx.measureText(code).width > _avail) {
    var _unit = ctx.measureText('M').width || 6.6;
    var _maxN = Math.max(8, Math.floor(_avail / _unit) - 1);
    code = code.slice(0, _maxN) + '…';
  }
  ctx.fillText(code, CX, CH - 50);
  ctx.fillStyle = 'rgba(150,175,180,.75)';
  ctx.font = '11px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('点下方重打　·　点别处回到选曲', CX, CH - 22);
  ctx.restore();
}

function drawImport() {
  ctx.save();
  ctx.fillStyle = 'rgba(223,240,239,.96)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.font = 'bold 22px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('导入 Simai 谱面', CX, 20);
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.9)';
  ctx.fillText('从剪贴板粘贴（Ctrl+V）或点下面的示例　·　Enter 解析并开打　·　Esc 返回', CX, 50);

  // 文本预览
  ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(5,12,18,.85)';
  ctx.fillRect(40, 76, CW - 80, CH - 200);
  ctx.strokeStyle = 'rgba(120,200,200,.2)'; ctx.lineWidth = 1; ctx.strokeRect(40, 76, CW - 80, CH - 200);
  ctx.fillStyle = '#9fe8e2';
  ctx.font = '11px Consolas,monospace';
  var lines = (S.importText || '（还没有内容）').split('\n').slice(0, 14);
  for (var i = 0; i < lines.length; i++) ctx.fillText(lines[i].slice(0, 92), 52, 88 + i * 15);

  // 消息
  ctx.textAlign = 'center';
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = S.importMsg.indexOf('失败') >= 0 || S.importMsg.indexOf('看不懂') >= 0
    ? C_MISS : '#9fe8e2';
  ctx.fillText(S.importMsg || '默认时值 1/' + S.importDiv + ' 拍（Tab 切换 4 / 8 / 16）', CX, CH - 108);

  // 示例
  ctx.font = '11px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillStyle = 'rgba(150,175,180,.85)';
  ctx.fillText('1 简单连打　2 滑动星星　3 TOUCH/EX（按数字键载入示例）　·　默认时值 ' +
    '1/' + S.importDiv + ' 拍　·　Tab 切换', CX, CH - 84);
  ctx.restore();
}

function drawHelp() {
  ctx.save();
  ctx.fillStyle = 'rgba(223,240,239,.96)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.font = 'bold 22px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('键位与音符', CX, 18);
  var rows = [
    ['TAP', '青色圆点 —— 扩到判定环那一下敲'],
    ['BREAK 星星', '金色五角星 —— 打出 CRITICAL 才有加成，全谱上限 101%'],
    ['HOLD', '蓝色圆点 + 环上尾巴 —— 按住到结束，早松掉到 GOOD'],
    ['SLIDE', '紫色圆点带箭头 —— 敲头，再送终点'],
    ['滑动星星', '金色五角星 + 金色轨迹 —— 判定按 BREAK 算，最值钱'],
    ['TOUCH', '粉色圆点（中央屏）—— 空格'],
    ['TOUCH HOLD', '粉色圆点带时长 —— 空格按住'],
    ['EX', '黄色六角星（中央屏）—— Shift'],
    ['键位', 'A S D F J K L ;  = 环上八分区（左上起顺时针）'],
    ['触屏', '直接点圆环的方位 / 中央屏；SLIDE 点完头再点终点']
  ];
  ctx.textAlign = 'left';
  for (var i = 0; i < rows.length; i++) {
    var y = 52 + i * 32;
    ctx.fillStyle = '#9fe8e2';
    ctx.font = 'bold 13px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText(rows[i][0], 60, y);
    ctx.fillStyle = 'rgba(210,232,234,.9)';
    ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillText(rows[i][1], 210, y + 1);
  }
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(150,175,180,.8)';
  ctx.font = '12px "Segoe UI","Microsoft YaHei",sans-serif';
  ctx.fillText('判定窗口（真机值）：CRITICAL ±33ms　PERFECT ±67ms　GREAT ±100ms　GOOD ±150ms', CX, CH - 40);
  ctx.fillText('Esc 返回', CX, CH - 20);
  ctx.restore();
}

function drawCountdown() {
  var left = -S.now;
  if (left > 0) {
    ctx.save();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    var n = Math.ceil(left / 1000);
    ctx.font = 'bold 96px Consolas,monospace';
    ctx.fillStyle = C_TAP;
    ctx.globalAlpha = clamp(1 - (left % 1000) / 1000, 0.15, 1);
    ctx.fillText(n > 3 ? 'READY' : String(n), CX, CY);
    ctx.globalAlpha = 1;
    ctx.font = '14px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillStyle = 'rgba(200,230,232,.85)';
    ctx.fillText('点一下画面让浏览器允许出声（Web Audio 需要用户交互）', CX, CY + 78);
    ctx.restore();
  }
}

function draw() {
  ctx.clearRect(0, 0, CW, CH);
  // 背景跟着 BPM 呼吸、色相缓慢流动，再加一道旋转扫光（舞萌机台的舞台感）
  var _t = performance.now() / 1000;
  var _bpm = (S.chart && S.chart.bpm) || 132;
  var _beat = 60 / Math.max(40, _bpm);
  var _ph = (_t % _beat) / _beat;
  var _pl = 0.5 + 0.5 * Math.cos(_ph * Math.PI * 2);
  var _hue = (_t * 12) % 360;
  var g = ctx.createRadialGradient(CX, CY, 10, CX, CY, Math.max(CW, CH) * 0.78);
  g.addColorStop(0, 'hsl(' + _hue.toFixed(0) + ',40%,' + (9 + _pl * 5).toFixed(1) + '%)');
  g.addColorStop(0.55, '#08131b');
  g.addColorStop(1, '#03060a');
  ctx.fillStyle = g; ctx.fillRect(0, 0, CW, CH);
  ctx.save();
  ctx.translate(CX, CY);
  ctx.rotate(_t * 0.18);
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = 0.05 + _pl * 0.05;
  ctx.fillStyle = 'hsl(' + ((_hue + 150) % 360).toFixed(0) + ',70%,60%)';
  ctx.beginPath(); ctx.moveTo(0, 0);
  ctx.arc(0, 0, Math.max(CW, CH) * 0.75, -0.20, 0.20); ctx.closePath(); ctx.fill();
  ctx.restore();

  if (S.scene === 'select') { drawSelect(); return; }
  if (S.scene === 'import') { drawImport(); return; }
  if (S.scene === 'help') { drawHelp(); return; }
  if (S.scene === 'result') { drawResult(); return; }

  if (S.scene === 'play' && !S.running) {
    // 等第一次点击开打之前：明确提示，解决「点了没反应」的困惑
    drawCenterScreen();
    drawRing();
    ctx.save();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = 'bold 38px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillStyle = '#9fe8e2';
    ctx.fillText('👆 点击画面任意位置开始', CX, CY - 26);
    ctx.font = '15px "Segoe UI","Microsoft YaHei",sans-serif';
    ctx.fillStyle = 'rgba(200,230,232,.82)';
    ctx.fillText('点完即开打，接着按圆环节奏敲就行', CX, CY + 20);
    ctx.restore();
    return;
  }

  var nowMs = S.now - S.offset;
  drawCenterScreen();
  drawRing();
  if (S.now < 0) { drawCountdown(); drawHud(); return; }
  drawNotes(nowMs);
  drawHud();
}

// ============================================================ 输入
function keyIndex(e) {
  var k = (e.key || '').toLowerCase();
  if (KEY_ALIAS[k]) k = KEY_ALIAS[k];
  var i = KEYS.indexOf(k);
  return i;
}
document.addEventListener('keydown', function (e) {
  if (hubIdle()) return;
  var k = (e.key || '').toLowerCase();
  AU.resume();

  if (S.scene === 'select') {
    var list = S.libFiltered.length ? S.libFiltered : LIB;
    if (k === 'arrowdown') { S.selRow = Math.min(list.length - 1, S.selRow + 1); e.preventDefault(); }
    else if (k === 'arrowup') { S.selRow = Math.max(0, S.selRow - 1); e.preventDefault(); }
    else if (k === 'arrowright') { S.selDiff = Math.min(4, S.selDiff + 1); e.preventDefault(); }
    else if (k === 'arrowleft') { S.selDiff = Math.max(0, S.selDiff - 1); e.preventDefault(); }
    else if (k === 'enter') {
      if (list.length) {
        S.chart = buildChart(list[S.selRow], S.selDiff);
        startPlay();
      } else if (CHART) { S.chart = CHART; startPlay(); }
      e.preventDefault();
    }
    else if (k === 'i') { S.scene = 'import'; S.importMsg = ''; }
    else if (k === 'h') { S.scene = 'help'; }
    else if (k === '[') { S.speed = clamp(S.speed - 0.1, 0.5, 2.4); saveSettings(); }
    else if (k === ']') { S.speed = clamp(S.speed + 0.1, 0.5, 2.4); saveSettings(); }
    else if (k === '-') { S.offset -= 5; saveSettings(); }
    else if (k === '=') { S.offset += 5; saveSettings(); }
    else if (k === 'm') { AU.on = !AU.on; saveSettings(); }
    else if (k === 'b') { AU.bgmOn = !AU.bgmOn; saveSettings(); }
    else if (k === ',') { AU.setVol(clamp(AU.vol - 0.1, 0, 1)); saveSettings(); }
    else if (k === '.') { AU.setVol(clamp(AU.vol + 0.1, 0, 1)); saveSettings(); }
    else if (k === 'p' && CHART) { S.chart = CHART; startPlay(); }
    return;
  }

  if (S.scene === 'help') { if (k === 'escape' || k === 'enter') S.scene = 'select'; return; }

  if (S.scene === 'import') {
    if (k === 'escape') { S.scene = 'select'; return; }
    if (k === 'tab') { S.importDiv = S.importDiv === 4 ? 8 : (S.importDiv === 8 ? 16 : 4); e.preventDefault(); return; }
    if (k === '1' || k === '2' || k === '3') {
      S.importText = EXAMPLES[parseInt(k, 10) - 1];
      S.importMsg = '已载入示例 ' + k;
      return;
    }
    if (k === 'enter') { doImport(); return; }
    if (k === 'backspace') { S.importText = S.importText.slice(0, -1); return; }
    return;
  }

  if (S.scene === 'result') {
    if (k === 'enter') { startPlay(); }
    else if (k === 'escape') { S.scene = LIB.length ? 'select' : 'select'; S.running = false; AU.stopBGM(); }
    return;
  }

  // 演奏中
  if (k === 'escape') { S.running = false; AU.stopBGM(); S.scene = 'select'; return; }
  var ki = keyIndex(e);
  if (ki >= 0) { pressRing(ki); e.preventDefault(); return; }
  if (k === ' ') { pressCenter(); e.preventDefault(); return; }
  if (k === 'shift') { pressCenter(); return; }
});
document.addEventListener('keyup', function (e) {
  if (hubIdle()) return;
  var k = (e.key || '').toLowerCase();
  if (S.scene !== 'play') return;
  var ki = keyIndex(e);
  if (ki >= 0) { releaseRing(ki); return; }
  if (k === ' ' || k === 'shift') { releaseCenter(); }
});

// 触屏 / 鼠标：点圆环方位 = 敲那个分区；点中央屏 = TOUCH；
// 按住后拖到另一个方位 = SLIDE 送达终点（手机上就这么划）
function angDiff(a, b) {
  return Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));
}
function sectorOf(x, y) {
  var ang = Math.atan2(y - CY, x - CX), bi = 0, bd = 99;
  for (var i = 0; i < 8; i++) {
    var d = angDiff(ang, POS_A[i]);
    if (d < bd) { bd = d; bi = i; }
  }
  return bi;
}
function pointerPos(ev) {
  var rect = cv.getBoundingClientRect();
  var x = (ev.clientX - rect.left) / (rect.width || 1) * CW;
  var y = (ev.clientY - rect.top) / (rect.height || 1) * CH;
  return [x, y];
}
var POINTERS = {};              // pointerId → 当前所在的分区（多点触控用）

function handlePointer(ev) {
  AU.resume();
  var p = pointerPos(ev), x = p[0], y = p[1];
  var dx = x - CX, dy = y - CY;
  var dist = Math.sqrt(dx * dx + dy * dy);
  if (S.scene === 'play') {
    if (dist <= R_C * 1.05) { pressCenter(); return; }
    var sec = sectorOf(x, y);
    POINTERS[ev.pointerId] = sec;
    pressRing(sec);
    // 拖到终点也算送达：手指从起点方位划到终点方位
    var self = this;
    setTimeout(function () {
      for (var j = 0; j < S.notes.length; j++) {
        var n = S.notes[j];
        if (n.sliding && n.q === sec) { slideEnd(n.q); }
      }
    }, 110);
    return;
  }
  if (S.scene === 'select') {
    var list = S.libFiltered.length ? S.libFiltered : LIB;
    for (var r = 0; r < 8; r++) {
      var yy = 92 + r * 34;
      var idx = Math.max(0, Math.min(list.length - 8, S.selRow - 3)) + r;
      if (idx < list.length && y >= yy - 4 && y <= yy + 26 && x >= 40 && x <= CW - 200) {
        if (idx === S.selRow) { S.chart = buildChart(list[idx], S.selDiff); startPlay(); }
        else S.selRow = idx;
        return;
      }
    }
    for (var d3 = 0; d3 < 5; d3++) {
      var dy2 = 110 + d3 * 56;
      if (x >= CW - 148 && x <= CW - 32 && y >= dy2 - 6 && y <= dy2 + 40) {
        S.selDiff = d3; return;
      }
    }
    return;
  }
  if (S.scene === 'result') {
    if (y > CH - 90 && y < CH - 30) { startPlay(); return; }
    S.scene = 'select'; S.running = false; AU.stopBGM();
    return;
  }
  if (S.scene === 'import' && y > CH - 90) { doImport(); return; }
}
cv.addEventListener('pointerdown', handlePointer);
cv.addEventListener('pointermove', function (ev) {
  if (S.scene !== 'play') return;
  if (!(ev.pointerId in POINTERS)) return;
  var p = pointerPos(ev);
  var sec = sectorOf(p[0], p[1]);
  var from = POINTERS[ev.pointerId];
  if (sec !== from) {
    // 手指划过去了 —— 若正好有 SLIDE 在等这个终点，就算送达
    for (var j = 0; j < S.notes.length; j++) {
      var n = S.notes[j];
      if (n.sliding && n.q === sec) { slideEnd(sec); break; }
    }
    POINTERS[ev.pointerId] = sec;
  }
});
function endPointer(ev) {
  delete POINTERS[ev.pointerId];
  if (S.scene !== 'play') return;
  var p = pointerPos(ev);
  if (Math.sqrt(Math.pow(p[0] - CX, 2) + Math.pow(p[1] - CY, 2)) <= R_C * 1.05) {
    releaseCenter(); return;
  }
  releaseRing(sectorOf(p[0], p[1]));
}
cv.addEventListener('pointerup', endPointer);
cv.addEventListener('pointercancel', endPointer);
cv.addEventListener('pointerleave', endPointer);

// 粘贴导入
document.addEventListener('paste', function (e) {
  if (hubIdle()) return;
  if (S.scene !== 'import') return;
  var txt = (e.clipboardData || window.clipboardData).getData('text');
  if (txt) { S.importText = txt; S.importMsg = '已粘贴 ' + txt.length + ' 字，按 Enter 解析'; }
});

var EXAMPLES = [
  '&bpm=150\n&offset=0\n&title=8分连打练习\n\n#MASTER\n(150)1[2:16],2[2:16],3[2:16],4[2:16],5[2:16],6[2:16],7[2:16],8[2:16],1[2:16],3[2:16],5[2:16],7[2:16],2[2:16],4[2:16],6[2:16],8[2:16],',
  '&bpm=160\n&offset=0\n&title=滑动星星练习\n\n#MASTER\n(160)1^3,2b^4,5^7,6b^8,1-5,3-7,2bv6,4bw8,1[4:16],2[4:16],3[4:16],4[4:16],1h[8:16],5[8:16],6[8:16],7[8:16],',
  '&bpm=155\n&offset=0\n&title=中央屏练习\n\n#MASTER\n(155)A1[4:16],B3[4:16],C[4:16],E1[4:16],A5[4:16],B7[4:16],C[4:16],E5[4:16],1[4:16],A2[4:16],3[4:16],B6[4:16],5[4:16],C[4:16],7[4:16],E3[4:16],'
];

function doImport() {
  var txt = (S.importText || '').trim();
  if (!txt) { S.importMsg = '还没有内容 —— 按 Ctrl+V 粘贴，或按 1 / 2 / 3 载入示例'; return; }
  var res;
  try { res = parseSimai(txt, S.importDiv); }
  catch (err) { S.importMsg = '解析失败：' + err.message; return; }
  var keys = Object.keys(res.charts || {});
  if (!keys.length) {
    S.importMsg = '一个音符都没读出来。检查：音符是不是 1~8？同押的 {} 配对了吗？';
    return;
  }
  var diff = keys.indexOf('MASTER') >= 0 ? 'MASTER' : keys[0];
  var ch = res.charts[diff];
  ch.song = { title: ch.title, artist: ch.artist, bpm: Math.round(ch.bpm),
              ds: ch.ds || 0, diff: diff };
  S.customCharts.push({ title: ch.title, diff: diff, at: Date.now() });
  LS.jset('dx_custom_charts', S.customCharts);
  S.chart = ch;
  S.importMsg = '读出来 ' + ch.notes.length + ' 个音符（' + diff + '）' +
    (res.warnings.length ? '　⚠ ' + res.warnings[0] : '');
  if (ch.notes.length) { setTimeout(function () { startPlay(); }, 500); }
}

// ============================================================ 启动
if (CHART) {
  S.chart = CHART;
  if (!LIB.length) S.scene = 'play';            // 外面已经选好曲了 → 直接进机台
  else S.scene = 'select';
} else {
  S.scene = 'select';
}
S.libFiltered = LIB.slice();
if (S.scene === 'play') {
  // 等一次用户交互再开（浏览器不允许自动播放）
  var dh = document.getElementById('dxhint');
  if (dh) dh.textContent = '👆 点击画面任意位置开始';
  var kick = function () {
    if (hubIdle()) return;
    if (S.running) return;                       // 已经在跑就不重来
    AU.resume();
    // 先把监听器摘掉：哪怕下面 startPlay 抛错也不会被反复触发，避免把整局冲掉
    document.removeEventListener('pointerdown', kick);
    document.removeEventListener('keydown', kick);
    try { startPlay(); }
    catch (e) { /* 启动失败也不留监听器 */ }
  };
  document.addEventListener('pointerdown', kick);
  document.addEventListener('keydown', kick);
}
S.appr = 1500;
if (FULL) {
  relayout();
  if (window.addEventListener) window.addEventListener('resize', relayout);
  if (window.screen && screen.orientation && screen.orientation.addEventListener) {
    try { screen.orientation.addEventListener('change', function () { setTimeout(relayout, 120); }); }
    catch (e) { }
  }
  // 手机上别让页面跟着手指滚
  cv.style.touchAction = 'none';
  document.documentElement.style.overscrollBehavior = 'none';
  document.body.style.overscrollBehavior = 'none';
}
window.__dxRAF = requestAnimationFrame(tick);

// 给外部（独立版 / 测试）用的口子
window.DX = {
  S: S, AU: AU, parseSimai: parseSimai, buildChart: buildChart, relayout: relayout,
  makeCode: makeCode, rankOf: rankOf, loadChart: loadChart,
  startPlay: startPlay, endPlay: endPlay, sweep: sweep, slideEnd: slideEnd,
  pressRing: pressRing, pressCenter: pressCenter,
  releaseRing: releaseRing, releaseCenter: releaseCenter,
  liveAch: liveAch, judgeLv: judgeLv, KEYS: KEYS, POS_A: POS_A,
  totalBreaks: totalBreaks, finishNote: finishNote
};
})();

// 供外部（纯前端版）在反复进出机台时停止上一局的 rAF 循环，避免旧实例空转
window.__dxStop = function () {
  if (window.__dxRAF) { try { cancelAnimationFrame(window.__dxRAF); } catch (e) {} window.__dxRAF = null; }
};
