/*
 * 独立版烟测：把 standalone/maimai-dx.html 当成手机上那个全屏 WebView 跑一遍。
 *
 * 和 smoke_dx.js 的区别是这里走 FULL 分支（window.parent === window）：
 * 会触发 relayout（改 canvas 尺寸）、竖屏/横屏、触屏输入路径。
 * 验证的是"双击打开能不能玩"，不只是"引擎对不对"。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
let FAILS = 0, CHECKS = 0;
function check(name, ok, extra) {
  CHECKS++;
  if (!ok) { FAILS++; console.log(`  [FAIL] ${name}${extra ? '  → ' + extra : ''}`); }
  return ok;
}

const html = fs.readFileSync(path.join(ROOT, 'standalone/maimai-dx.html'), 'utf8');

// ---- 静态检查：这是个能离线跑的单文件
check('没有外链 http', html.indexOf('http://') < 0, '');
check('没有外链 https', html.indexOf('https://') < 0, '');
check('manifest 内联成 data URI', html.includes('data:application/manifest+json'));
check('声明 viewport', html.includes('name="viewport"'));
check('禁止缩放（手机上别被捏）', html.includes('user-scalable=no'));
check('canvas id 正确', html.includes('id="dxcv"'));

const mScript = html.match(/<script>[\s\S]*?<\/script>/g) || [];
check('有两个 script 块（曲库 + 引擎）', mScript.length === 2, `${mScript.length}`);
const libJs = mScript[0].replace(/^<script>/, '').replace(/<\/script>$/, '').trim();
const engineJs = mScript[1].replace(/^<script>/, '').replace(/<\/script>$/, '').trim();

// ---- 跑起来
function makeCanvas() {
  const noop = () => {};
  const grad = { addColorStop: noop };
  const calls = { resize: 0 };
  const ctx = new Proxy({}, {
    get(_, k) {
      if (k === 'createRadialGradient' || k === 'createLinearGradient') return () => grad;
      if (k === 'measureText') return () => ({ width: 10 });
      if (k === 'setTransform') return () => { calls.resize++; };
      if (typeof k === 'string' && ['fillStyle', 'strokeStyle', 'lineWidth', 'font', 'globalAlpha',
        'textAlign', 'textBaseline', 'shadowColor', 'shadowBlur', 'lineCap', 'lineJoin'].includes(k)) return '';
      return noop;
    },
    set() { return true; }
  });
  return {
    width: 960, height: 560, style: {},
    getContext: () => ctx,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 960, height: 560 }),
    addEventListener: noop, _calls: calls
  };
}

function boot(w, h) {
  const store = {};
  const canvas = makeCanvas();
  const winListeners = {};
  const sb = {
    console,
    performance: { now: () => 0 },
    requestAnimationFrame: () => 0,
    setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    },
    document: {
      getElementById: (id) => (id === 'dxcv' ? canvas : null),
      addEventListener: () => {}, removeEventListener: () => {},
      documentElement: { style: {} }, body: { style: {} }
    },
    Math, JSON, Date, parseInt, parseFloat, isNaN, String, Number, Object, Array, Boolean, Error,
    Buffer, unescape: (s) => s, escape: (s) => s,
    btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
    atob: (s) => Buffer.from(s, 'base64').toString('binary'),
    innerWidth: w, innerHeight: h, devicePixelRatio: 2,
    screen: { orientation: { addEventListener: () => {} } }
  };
  sb.addEventListener = (t, f) => { (winListeners[t] = winListeners[t] || []).push(f); };
  sb.window = sb;
  sb.globalThis = sb;
  sb.parent = sb;      // 顶层窗口：window.parent === window
  sb.top = sb;
  vm.createContext(sb);
  vm.runInContext(libJs, sb, { filename: 'lib.js' });
  check('内置曲库非空', Array.isArray(sb.DXLIB) && sb.DXLIB.length > 50,
    `${sb.DXLIB ? sb.DXLIB.length : 0} 首`);
  vm.runInContext(engineJs, sb, { filename: 'dx_cabinet.js' });
  return { DX: sb.DX, canvas, winListeners, sb };
}

console.log('=== 横屏 1180×760（桌面 exe 窗口） ===');
const A = boot(1180, 760);
check('引擎暴露出来', !!A.DX);
check('全屏模式下画布被重排', A.canvas.width !== 960, `${A.canvas.width}×${A.canvas.height}`);
check('按 devicePixelRatio 放大了', A.canvas.width === 1180 * 2, `${A.canvas.width}`);
check('注册了 resize 监听', (A.winListeners.resize || []).length > 0);
check('一开始在选曲画面', A.DX.S.scene === 'select', A.DX.S.scene);
check('曲库装载进引擎', A.DX.S.libFiltered.length > 50, `${A.DX.S.libFiltered.length}`);

// 用引擎内置生成器出一张谱并打完
const song = A.DX.S.libFiltered[0];
const chart = A.DX.buildChart(song, 3, 60);
check('能给选中的曲子生成谱面', chart.notes.length > 120, `${chart.notes.length}`);
console.log(`  选了「${song.title}」 ds=${song.ds} BPM=${song.bpm} → ${chart.notes.length} 音符`);

A.DX.S.chart = chart; A.DX.loadChart(chart);
A.DX.S.scene = 'play'; A.DX.S.running = true; A.DX.S.t0 = 0; A.DX.S.offset = 0;
const notes = A.DX.S.notes, pending = [];
const isCtr = (k) => k === 'touch' || k === 'ex' || k === 'thold';
for (let i = 0; i < notes.length; i++) {
  const n = notes[i], nowMs = n.t;
  for (let pi = 0; pi < pending.length; pi++) {
    const p = pending[pi];
    if (p.at <= nowMs) {
      A.DX.S.now = p.at;
      if (p.ctr) A.DX.releaseCenter();
      else if (p.slide !== undefined) A.DX.slideEnd(p.slide);
      else A.DX.releaseRing(p.key);
      pending.splice(pi, 1); pi--;
    }
  }
  A.DX.S.now = nowMs;
  A.DX.sweep(nowMs);
  if (!n.done) {
    if (isCtr(n.k)) { A.DX.pressCenter(); if (n.k === 'thold') pending.push({ at: n.t + (n.d || 0) + 20, ctr: true }); }
    else {
      A.DX.pressRing(n.p);
      if (n.k === 'hold') pending.push({ at: n.t + (n.d || 0) + 20, key: n.p });
      else if (n.k === 'slide') pending.push({ at: n.t + 60, slide: n.q });
    }
  }
}
for (const p of pending) {
  A.DX.S.now = p.at;
  if (p.ctr) A.DX.releaseCenter();
  else if (p.slide !== undefined) A.DX.slideEnd(p.slide);
  else A.DX.releaseRing(p.key);
}
A.DX.sweep(notes[notes.length - 1].t + 900);
const ach = A.DX.liveAch();
console.log(`  全 CP：${ach.toFixed(4)}%  ${A.DX.rankOf(ach)}  COMBO ${A.DX.S.maxCombo}/${notes.length}`);
check('独立版能全 CP', A.DX.S.cnt.miss === 0 && A.DX.S.maxCombo === notes.length,
  `MISS ${A.DX.S.cnt.miss}`);
check('独立版达成率 = 101%', Math.abs(ach - 101) < 0.02, `${ach.toFixed(4)}%`);

console.log('\n=== 竖屏 420×860（手机竖着拿） ===');
const B = boot(420, 860);
check('竖屏也能起来', !!B.DX && B.DX.S.scene === 'select', B.DX.S.scene);
check('竖屏画布尺寸跟着变', B.canvas.width === 420 * 2, `${B.canvas.width}`);

console.log('\n=== 手机横屏 860×420 ===');
const C = boot(860, 420);
check('手机横屏能起来', !!C.DX && C.DX.S.scene === 'select');
check('手机横屏画布正确', C.canvas.width === 860 * 2, `${C.canvas.width}`);

console.log('\n=== 触屏输入路径 ===');
const D = boot(1180, 760);
D.DX.S.chart = chart; D.DX.loadChart(chart);
D.DX.S.scene = 'play'; D.DX.S.running = true; D.DX.S.t0 = 0; D.DX.S.offset = 0;
// 直接调判定入口（模拟 pointerdown → pressRing 的那条路）
const first = D.DX.S.notes.filter((n) => n.k === 'tap' || n.k === 'slide')[0];
D.DX.S.now = first.t;
D.DX.pressRing(first.p);
check('触屏敲分区有判定', first.done && !!first.lv, `${first.lv}`);
const ctr = D.DX.S.notes.filter((n) => n.k === 'touch' || n.k === 'ex')[0];
if (ctr) {
  D.DX.S.now = ctr.t;
  D.DX.pressCenter();
  check('触屏点中央屏有判定', ctr.done && !!ctr.lv, `${ctr.lv}`);
} else {
  console.log('  （这张谱没有中央屏音符，跳过）');
}

console.log('\n' + (FAILS === 0
  ? `全部 PASS（${CHECKS} 项断言）`
  : `有 ${FAILS} 项 FAIL（共 ${CHECKS} 项）`));
process.exit(FAILS === 0 ? 0 : 1);
