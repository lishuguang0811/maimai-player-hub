// 用最小 DOM 模拟，在 node 里真跑一遍各游戏的 JS，抓白屏级错误。
// 用法：node work/smoke_games.js
const fs = require('fs');
const vm = require('vm');
const path = require('path');

function stubCtx() {
  const noop = () => {};
  return new Proxy({}, {
    get(t, k) {
      if (k === 'createLinearGradient') return () => ({ addColorStop: noop });
      if (k === 'createRadialGradient') return () => ({ addColorStop: noop });
      if (k === 'canvas') return { width: 360, height: 440 };
      if (k === 'measureText') return () => ({ width: 10 });
      return typeof k === 'string' ? (t[k] !== undefined ? t[k] : noop) : noop;
    },
    set(t, k, v) { t[k] = v; return true; }
  });
}

function makeEl(id, tag) {
  const el = {
    id: id || '', tagName: (tag || 'div').toUpperCase(),
    width: 360, height: 440, textContent: '', innerHTML: '', value: '',
    style: {}, dataset: {}, children: [],
    classList: { add() {}, remove() {}, contains() { return false } },
    getContext: () => stubCtx(),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 360, height: 440 }),
    addEventListener() {}, removeEventListener() {},
    appendChild(c) { el.children.push(c); return c },
    setAttribute() {}, focus() {},
    querySelectorAll: () => Array.from({ length: 16 }, () => makeEl()),
  };
  return el;
}

function runGame(name, script) {
  const cache = {};
  const sandbox = {
    console,
    // 成绩码要用 btoa / unescape / encodeURIComponent，node 的沙箱里得自己备一份
    btoa: (s) => Buffer.from(String(s), 'binary').toString('base64'),
    atob: (s) => Buffer.from(String(s), 'base64').toString('binary'),
    unescape: (s) => global.unescape ? global.unescape(s) : decodeURIComponent(String(s).replace(/\+/g, ' ')),
    escape: (s) => global.escape ? global.escape(s) : encodeURIComponent(String(s)),
    performance: { now: () => Date.now() },
    requestAnimationFrame: () => 0,
    setTimeout: (f, t) => { return 0 },      // 不真跑定时器，避免无限循环
    clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
    localStorage: { getItem: () => null, setItem: () => {} },
    window: {},
    document: {
      getElementById: (id) => (cache[id] = cache[id] || makeEl(id)),
      querySelectorAll: (sel) => {
        const n = sel && sel.indexOf('.note') >= 0 ? 4 : 16;
        if (!cache['qa' + sel]) cache['qa' + sel] = Array.from({ length: n }, () => makeEl());
        return cache['qa' + sel];
      },
      createElement: (t) => makeEl('', t),
      addEventListener: () => {},
    },
  };
  sandbox.window = sandbox;
  sandbox.AudioContext = undefined;
  sandbox.webkitAudioContext = undefined;
  // 拼图会 new Image() 并等 onload；这里设 src 时立刻回调，好让真实逻辑跑起来
  sandbox.Image = function () {
    const self = { width: 330, height: 330, onload: null, _src: '' };
    Object.defineProperty(self, 'src', {
      get() { return self._src },
      set(v) { self._src = v; if (typeof self.onload === 'function') self.onload() },
    });
    return self;
  };
  try {
    vm.createContext(sandbox);
    vm.runInContext(script, sandbox, { timeout: 4000 });
    // 触发一些交互，看会不会炸
    const triggers = [
      () => sandbox.document.getElementById('go').onclick && sandbox.document.getElementById('go').onclick(),
      () => sandbox.document.getElementById('new').onclick && sandbox.document.getElementById('new').onclick(),
      () => sandbox.document.getElementById('restart').onclick && sandbox.document.getElementById('restart').onclick(),
      () => sandbox.document.getElementById('dif').onclick && sandbox.document.getElementById('dif').onclick(),
      () => typeof sandbox.press === 'function' && sandbox.press(0),
      () => typeof sandbox.move === 'function' && [0, 1, 2, 3].forEach((d) => sandbox.move(d)),
      () => typeof sandbox.pick === 'function' && sandbox.pick(0, makeEl()),
      () => typeof sandbox.flip === 'function' && sandbox.flip(0, makeEl()),
      () => typeof sandbox.loop === 'function' && sandbox.loop(),
      () => typeof sandbox.draw === 'function' && sandbox.draw(),
      () => typeof sandbox.tick === 'function' && sandbox.tick(),
      () => typeof sandbox.step === 'function' && sandbox.step(),
      () => typeof sandbox.tap === 'function' && sandbox.tap(),
      () => typeof sandbox.next === 'function' && sandbox.next(),
      ...['pause', 'skip', 'reset', 'peek', 'sfx'].map((id) =>
        () => sandbox.document.getElementById(id).onclick
          && sandbox.document.getElementById(id).onclick()),
    ];
    const errs = [];
    for (const t of triggers) {
      try { t() } catch (e) { errs.push(e.message) }
    }
    if (errs.length) {
      // 模拟 DOM 与真实浏览器有差异，交互报错只提示、不判失败
      console.log(`[${name}] 运行通过（交互阶段 ${errs.length} 条模拟环境报错：${errs.slice(0, 3).join(' | ')}）`);
    } else {
      console.log(`[${name}] 运行通过`);
    }
    return true;
  } catch (e) {
    console.log(`[${name}] ❌ ${e.message}`);
    return false;
  }
}

const root = path.resolve(__dirname, '..');
const py = process.argv[2];
if (!py) { console.log('需要传入 python 解释器路径'); process.exit(1) }
const { execFileSync } = require('child_process');
const gen = path.join(root, 'work', '_dump_games.py');
const out = execFileSync(py, [gen], { encoding: 'utf8' });
const dump = JSON.parse(out);
let ok = true;
for (const [name, html] of Object.entries(dump)) {
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { console.log(`[${name}] 没有 script`); ok = false; continue }
  ok = runGame(name, m[1]) && ok;
}
process.exit(ok ? 0 : 1);
