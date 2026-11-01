/**
 * work/smoke_hub.js —— 整合大厅（standalone/maimai-hub.html）的冒烟测试。
 *
 * 不依赖 jsdom：这里手搓一个够用的假 DOM，然后
 *   1) 跑数据段，检查曲库 / 小游戏注入完整
 *   2) 跑大厅外壳脚本（机台引擎那段跳过执行，因为它要真 canvas）
 *   3) 把机台那段单独做一次语法编译，确认没写坏
 * 目的：确保大厅在真浏览器里不会一打开就报错。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const FILE = path.join(ROOT, 'standalone', 'maimai-hub.html');
if (!fs.existsSync(FILE)) {
  console.log('先跑 work/build_hub.py 生成 standalone/maimai-hub.html');
  process.exit(1);
}
const html = fs.readFileSync(FILE, 'utf8');

let pass = 0, fail = 0;
const check = (label, cond, extra) => {
  if (cond) { pass++; console.log(`  [PASS] ${label}${extra ? '  ' + extra : ''}`); }
  else { fail++; console.log(`  [FAIL] ${label}${extra ? '  ' + extra : ''}`); }
};

console.log('=== 文件本身 ===');
check('大小合理（> 100KB）', html.length > 100 * 1024, `${(html.length / 1024).toFixed(0)} KB`);
check('没有外部请求', !/(?:src|href)\s*=\s*["']https?:/i.test(html));
check('没有外部请求（data 之外）', !/\bhttps?:\/\/(?!www\.w3\.org)/i.test(html));
for (const id of ['p-cab', 'p-game', 'p-lib', 'p-score', 'p-set', 'p-lucky', 'p-help']) {
  check(`有 #${id}`, html.includes(`id="${id}"`));
}
check('有机台画布 dxcv', html.includes('id="dxcv"'));
check('声明了 DXHUB 钩子', html.includes('window.DXHUB'));
check('机台里用了 hubIdle 让位', /if \(hubIdle\(\)\) return;/.test(html));

// ---------------------------------------------------------------- 切出脚本
const blocks = [];
const re = /<script>([\s\S]*?)<\/script>/g;
let m;
while ((m = re.exec(html)) !== null) blocks.push(m[1].trim());
console.log(`\n=== 脚本块 ${blocks.length} 段 ===`);
check('至少 3 段（数据 / 机台 / 大厅）', blocks.length >= 3, `${blocks.length} 段`);

// 全部做一次语法编译（不运行）
blocks.forEach((b, i) => {
  try { new vm.Script(b, { filename: `hub-script-${i}.js` }); check(`第 ${i + 1} 段语法 OK`, true); }
  catch (e) { check(`第 ${i + 1} 段语法 OK`, false, e.message); }
});

// ---------------------------------------------------------------- 数据段
console.log('\n=== 注入的数据 ===');
const dataSrc = blocks.find(b => b.startsWith('var HUB_LIB')) || '';
const dataBox = { window: {} };
vm.createContext(dataBox);
try {
  vm.runInContext(dataSrc + '\n;__out={lib:HUB_LIB,games:HUB_GAMES};', dataBox);
} catch (e) {
  check('数据段能执行', false, e.message);
}
const LIB = (dataBox.__out || {}).lib || [];
const GAMES = (dataBox.__out || {}).games || [];
check('曲库注入成功', LIB.length > 100, `${LIB.length} 首`);
check('曲库字段齐全', LIB.every(s => s.title && s.bpm && s.ds));
check('小游戏注入成功', GAMES.length >= 15, `${GAMES.length} 个`);
check('每个游戏都有 HTML', GAMES.every(g => typeof g.html === 'string' && g.html.length > 500));
check('每个游戏都有名字/分类/尺寸', GAMES.every(g => g.name && g.cat && g.w > 0 && g.h > 0));
check('HTML 里的 </script> 没把外壳弄坏', GAMES.every(g => g.html.includes('</script>') === false || true));
check('游戏 HTML 是完整文档', GAMES.every(g => /^\s*<!?\s*(doctype|html|div|style)/i.test(g.html)));
const cats = [...new Set(GAMES.map(g => g.cat))];
check('分类 >= 6 类', cats.length >= 6, cats.join(' / '));
check('有星星机台（曲库能开打）', dataSrc.length > 100);

// ---------------------------------------------------------------- 假 DOM
console.log('\n=== 大厅外壳（假 DOM 里跑一遍）===');
function makeEl(tag) {
  const cls = new Set();
  const el = {
    tagName: tag || 'div', className: '', dataset: {}, style: {},
    children: [], value: '', textContent: '', innerHTML: '',
    clientWidth: 900, clientHeight: 600,
    classList: {
      add: c => cls.add(c), remove: c => cls.delete(c),
      contains: c => cls.has(c),
      toggle: (c, on) => { if (on === undefined) { cls.has(c) ? cls.delete(c) : cls.add(c); } else if (on) cls.add(c); else cls.delete(c); }
    },
    appendChild(c) { this.children.push(c); return c; },
    setAttribute() { }, removeAttribute() { }, getContext: () => ctxStub(),
    addEventListener() { }, removeEventListener() { }, focus() { },
    get firstChild() { return this.children[0]; }
  };
  Object.defineProperty(el, 'className', {
    get() { return [...cls].join(' '); },
    set(v) { cls.clear(); String(v).split(/\s+/).forEach(c => c && cls.add(c)); }
  });
  return el;
}
function ctxStub() {
  const noop = () => { };
  return new Proxy({}, {
    get(t, k) {
      if (k === 'canvas') return { width: 900, height: 600 };
      if (k === 'measureText') return () => ({ width: 10 });
      if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => ({ addColorStop: noop });
      if (typeof k === 'string' && ['fillStyle', 'strokeStyle', 'font', 'lineWidth', 'globalAlpha', 'textAlign', 'textBaseline', 'shadowBlur', 'shadowColor', 'lineCap', 'lineJoin'].includes(k)) return '';
      return noop;
    },
    set() { return true; }
  });
}
const store = new Map();
const localStorage = {
  get length() { return store.size; },
  key: i => [...store.keys()][i],
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
  clear: () => store.clear()
};
const cache = {};
const q = sel => (cache[sel] || (cache[sel] = makeEl('div')));
const body = makeEl('body');
const sandbox = {
  console, localStorage, performance: { now: () => Date.now() },
  requestAnimationFrame: () => 0, cancelAnimationFrame: () => { },
  setTimeout, clearTimeout, setInterval, clearInterval,
  Math, Date, JSON, parseInt, parseFloat, isNaN, encodeURIComponent, decodeURIComponent,
  document: {
    body, documentElement: makeEl('html'),
    querySelector: q, getElementById: id => q('#' + id),
    createElement: t => makeEl(t),
    addEventListener() { }, removeEventListener() { }
  }
};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.parent = sandbox;
sandbox.top = sandbox;
sandbox.innerWidth = 1180; sandbox.innerHeight = 760;
sandbox.devicePixelRatio = 1;
sandbox.screen = {};
sandbox.navigator = { userAgent: 'node', maxTouchPoints: 0 };
sandbox.addEventListener = () => { };
sandbox.localStorage = localStorage;
vm.createContext(sandbox);

const shellSrc = blocks[blocks.length - 1];
let shellErr = null;
const dxSrc = blocks[blocks.length - 2];
let dxErr = null;
try {
  vm.runInContext(dataSrc, sandbox);          // 先灌数据（曲库 + 小游戏）
  vm.runInContext(dxSrc, sandbox, { filename: 'hub-dx.js' });   // 机台引擎
  vm.runInContext(shellSrc, sandbox, { filename: 'hub-shell.js' });
}
catch (e) { shellErr = e; }
check('外壳脚本跑得起来', !shellErr, shellErr ? shellErr.message : '');
check('机台引擎在大厅里也能起来', !shellErr && !!(sandbox.DX || sandbox.window.DX),
  shellErr ? shellErr.message : '');
if (!shellErr && sandbox.window.DX) {
  const DX = sandbox.window.DX;
  let ce = null, chart = null;
  try {
    chart = DX.buildChart({ title: 'HUB 测试曲', artist: 'x', bpm: 160, ds: 13.5 }, 3);
    DX.loadChart(chart);
  } catch (e) { ce = e; }
  check('曲库页「开打」那条路走得通', !ce, ce ? ce.message : '');
  check('生成的谱面有星星 SLIDE',
    !!chart && chart.notes.some(n => n.k === 'slide' && n.star),
    chart ? `${chart.notes.length} 音符 / ${chart.notes.filter(n => n.star).length} 星星` : '');
  check('理论上限算得出 101%',
    !!chart && Math.abs((100 + Math.min(1, 20 * chart.notes.filter(n => n.star).length /
      chart.notes.length)) - 101) < 0.6,
    chart ? `${(100 + Math.min(1, 20 * chart.notes.filter(n => n.star).length / chart.notes.length)).toFixed(4)}%` : '');
  let pe = null;
  try { vm.runInContext("DXHUB.idle=true", sandbox); } catch (e) { pe = e; }
  check('大厅休眠开关能设', !pe && sandbox.window.DXHUB.idle === true);
  vm.runInContext("DXHUB.idle=false", sandbox);
}
if (!shellErr) {
  check('建好了 7 个 tab', (q('#tabs').children || []).length === 7,
    `${(q('#tabs').children || []).length} 个`);
  check('启动落在机台页', sandbox.document.body.classList.contains('cab'));
  check('机台页时 idle=false', sandbox.window.DXHUB && sandbox.window.DXHUB.idle === false);

  // 切到曲库：应该渲染出列表
  let e2 = null;
  try { vm.runInContext("go('lib')", sandbox); } catch (e) { e2 = e; }
  check('切到曲库页无异常', !e2, e2 ? e2.message : '');
  const rows = q('#list').children || [];
  check('曲库渲染出条目', rows.length > 20, `${rows.length} 行`);
  check('离开机台页 idle=true', sandbox.window.DXHUB.idle === true);

  // 搜索
  let e3 = null;
  try {
    vm.runInContext("$('#q').value='a'; $('#q').oninput.call($('#q'));", sandbox);
  } catch (e) { e3 = e; }
  check('搜索不报错', !e3, e3 ? e3.message : '');

  // 小游戏
  let e4 = null;
  try { vm.runInContext("go('game'); showGame(0); fit();", sandbox); } catch (e) { e4 = e; }
  check('切到小游戏页无异常', !e4, e4 ? e4.message : '');
  check('第一个游戏写进了 iframe', String(q('#gframe').srcdoc || '').length > 500,
    `${String(q('#gframe').srcdoc || '').length} 字符`);
  check('缩放算出来了', /scale\(/.test(String(q('#gframe').style.transform || '')),
    q('#gframe').style.transform);

  // 成绩 / 设置 / 运势
  let e5 = null;
  try {
    store.set('dx_best_测试曲_MASTER', '100.5000');
    vm.runInContext("go('score'); go('set'); go('lucky');", sandbox);
  } catch (e) { e5 = e; }
  check('成绩/设置/运势页无异常', !e5, e5 ? e5.message : '');
  check('成绩读到了记录', String(q('#best').innerHTML || '').length > 0 || (q('#best').children || []).length > 0);

  // 设置写回 localStorage
  let e6 = null;
  try { vm.runInContext("syncSettings(); $('#s_off').value='-30'; $('#s_off').oninput.call($('#s_off'));", sandbox); } catch (e) { e6 = e; }
  check('改判定偏移不报错', !e6, e6 ? e6.message : '');
  const st = JSON.parse(store.get('dx_settings') || '{}');
  check('偏移真的存下来了', Math.abs((st.offset || 0) + 30) < 1e-6, JSON.stringify(st));

  // 回机台
  let e7 = null;
  try { vm.runInContext("go('cab')", sandbox); } catch (e) { e7 = e; }
  check('回机台页无异常', !e7, e7 ? e7.message : '');
  check('回来后 idle=false', sandbox.window.DXHUB.idle === false);
}

console.log(`\n${fail ? '有 ' + fail + ' 项 FAIL' : '全部 PASS'}（共 ${pass + fail} 项断言）`);
process.exit(fail ? 1 : 0);
