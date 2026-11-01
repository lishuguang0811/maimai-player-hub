/*
 * 在 node 里把一整首真打完 —— 机台引擎的烟测。
 *
 * 不是只测 JS 语法，而是真的模拟按键：按谱面时间轴推时钟，到点敲对应的键，
 * HOLD 按满、SLIDE 送终点、TOUCH/EX 敲中央屏，然后核对达成率 / 评级 / COMBO / MISS。
 * 再加一组「手滑版」（漏敲 + 早松 + 不送终点）验证扣分路径。
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

// ---------------------------------------------------------------- 最小 DOM
function makeCanvas() {
  const noop = () => {};
  const grad = { addColorStop: noop };
  const ctx = new Proxy({}, {
    get(_, k) {
      if (k === 'createRadialGradient' || k === 'createLinearGradient') return () => grad;
      if (k === 'measureText') return () => ({ width: 10 });
      if (typeof k === 'string' && ['fillStyle', 'strokeStyle', 'lineWidth', 'font', 'globalAlpha',
        'textAlign', 'textBaseline', 'shadowColor', 'shadowBlur', 'lineCap', 'lineJoin'].includes(k)) return '';
      return noop;
    },
    set() { return true; }
  });
  return {
    width: 960, height: 560,
    getContext: () => ctx,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 960, height: 560 }),
    addEventListener: noop
  };
}

function runEngine(chart, lib) {
  const store = {};
  const canvas = makeCanvas();
  const sandbox = {
    console,
    performance: { now: () => 0 },
    requestAnimationFrame: () => 0,        // 不自动跑帧，测试里手动推进
    setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    },
    document: {
      getElementById: (id) => (id === 'dxcv' ? canvas : null),
      addEventListener: () => {},
      removeEventListener: () => {}
    },
    Math, JSON, Date, parseInt, parseFloat, isNaN, String, Number, Object, Array, Boolean, Error,
    Buffer,
    unescape: (s) => s, escape: (s) => s,
    btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
    atob: (s) => Buffer.from(s, 'base64').toString('binary')
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.CHART = chart || null;
  sandbox.DXLIB = lib || [];
  const code = fs.readFileSync(path.join(ROOT, 'modules/dx_cabinet.js'), 'utf8');
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: 'dx_cabinet.js' });
  return sandbox.DX;
}

// ---------------------------------------------------------------- 打一首
function play(DX, chart, mode) {
  const sloppy = mode === 'sloppy';
  DX.S.chart = chart;
  DX.loadChart(chart);
  DX.S.scene = 'play';
  DX.S.running = true;
  DX.S.t0 = 0;                               // now 就是音符时间，直接设
  DX.S.offset = 0;
  const notes = DX.S.notes;
  const pending = [];
  const isCtr = (k) => k === 'touch' || k === 'ex' || k === 'thold';

  for (let i = 0; i < notes.length; i++) {
    const n = notes[i];
    const nowMs = n.t;
    DX.S.now = nowMs;
    // 先把到期的「松手 / 送终点」做掉，再扫漏判 —— 顺序反了会把已经送到的
    // SLIDE 误判成没送到。真机上玩家的动作也是先于判定发生的。
    for (let pi = 0; pi < pending.length; pi++) {
      const p = pending[pi];
      if (p.at <= nowMs) {
        DX.S.now = p.at;
        if (p.ctr) DX.releaseCenter();
        else if (p.slide !== undefined) DX.slideEnd(p.slide);
        else DX.releaseRing(p.key);
        pending.splice(pi, 1); pi--;
      }
    }
    DX.S.now = nowMs;
    DX.sweep(nowMs);
    if (!n.done) {
      const skip = sloppy && (i % 5 === 0);
      if (!skip) {
        if (isCtr(n.k)) {
          DX.pressCenter();
          if (n.k === 'thold') pending.push({ at: n.t + (n.d || 0) + 20, ctr: true });
        } else {
          DX.pressRing(n.p);
          if (n.k === 'hold') {
            const short = sloppy && (i % 7 === 1);
            pending.push({ at: n.t + (short ? (n.d || 0) * 0.3 : (n.d || 0) + 20), key: n.p });
          } else if (n.k === 'slide') {
            const drop = sloppy && (i % 6 === 2);
            if (!drop) pending.push({ at: n.t + Math.min(60, (n.d || 240) * 0.4), slide: n.q });
          }
        }
      }
    }
  }
  const endT = (notes.length ? notes[notes.length - 1].t + 400 : 1000);
  // 收尾同样是先做掉到期的动作，最后才扫漏判
  for (const p of pending) {
    DX.S.now = p.at;
    if (p.ctr) DX.releaseCenter();
    else if (p.slide !== undefined) DX.slideEnd(p.slide);
    else DX.releaseRing(p.key);
  }
  DX.S.now = endT;
  DX.sweep(endT + 500);
  const ach = DX.liveAch();
  return {
    ach: Math.round(ach * 10000) / 10000,
    rk: DX.rankOf(ach),
    mx: DX.S.maxCombo,
    cp: DX.S.cnt.cp, p: DX.S.cnt.p, gr: DX.S.cnt.gr, gd: DX.S.cnt.gd, m: DX.S.cnt.miss,
    fast: DX.S.fast, slow: DX.S.slow,
    total: notes.length
  };
}

// ---------------------------------------------------------------- 主流程
const index = JSON.parse(fs.readFileSync(path.join(ROOT, 'work/_dx_index.json'), 'utf8'));
console.log('谱面样本：' + index.length + ' 张\n');

for (const info of index) {
  const chart = JSON.parse(fs.readFileSync(path.join(ROOT, info.file), 'utf8'));
  const nb = chart.notes.filter((n) => n.star).length;
  const nsl = chart.notes.filter((n) => n.star && n.k === 'slide').length;
  console.log(`=== ${info.diff}  ${info.title}  ds=${info.ds}  N=${info.total}  bpm=${info.bpm}  星=${nb}(滑动星 ${nsl}) ===`);

  const DX = runEngine(chart, []);
  const a = play(DX, chart, 'perfect');
  const want = 100 + (nb ? Math.min(1, 100 * 100 * nb / (500 * a.total)) : 0);
  console.log(`  全 CP : ${a.ach}%  ${a.rk}  COMBO ${a.mx}  CP ${a.cp} / MISS ${a.m}  F/S ${a.fast}/${a.slow}`);
  check('全 CP 没有漏判', a.cp === a.total, `${a.cp}/${a.total}`);
  check('全 CP 没有 MISS', a.m === 0, `MISS ${a.m}`);
  check('全 CP 没有 GOOD/GREAT', a.gr === 0 && a.gd === 0, `gr=${a.gr} gd=${a.gd}`);
  check(`全 CP 达成率 = 理论值 ${want.toFixed(4)}%`, Math.abs(a.ach - want) < 0.02, `${a.ach}%`);
  check(`全 CP 评级 ${nb ? 'SSS+' : 'SSS'}`, a.rk === (nb ? 'SSS+' : 'SSS'), a.rk);
  check('COMBO = 全谱音符数', a.mx === a.total, `${a.mx}/${a.total}`);
  check('全 CP 没有 FAST/SLOW', a.fast === 0 && a.slow === 0, `${a.fast}/${a.slow}`);
  check('达成率不超过 101%', a.ach <= 101.0001, `${a.ach}%`);

  const DX2 = runEngine(chart, []);
  const b = play(DX2, chart, 'sloppy');
  console.log(`  手滑版: ${b.ach}%  ${b.rk}  COMBO ${b.mx}  CP ${b.cp} / MISS ${b.m}  GD ${b.gd}`);
  check('手滑版确实掉了音符', b.m > 0, `MISS ${b.m}`);
  check('手滑版达成率明显更低', b.ach < want - 3, `${b.ach}% vs ${want}%`);
  check('手滑版拿不到 SSS+', b.rk !== 'SSS+', b.rk);
  check('手滑版 COMBO 会断', b.mx < b.total, `${b.mx}/${b.total}`);
  check('手滑版达成率在合理区间', b.ach > 0 && b.ach <= 101, `${b.ach}%`);
  console.log('');
}

// ---------------------------------------------------------------- Simai 导入
console.log('=== Simai 导入 ===');
const DX3 = runEngine(null, []);
const samples = {
  '连打': '&bpm=150\n&offset=0\n&title=连打\n\n#MASTER\n(150)1[2:16],2[2:16],3[2:16],4[2:16],5[2:16],6[2:16],7[2:16],8[2:16],1[2:16],3[2:16],5[2:16],7[2:16],2[2:16],4[2:16],6[2:16],8[2:16],',
  '滑动星星': '&bpm=160\n&offset=0\n&title=滑动星星\n\n#MASTER\n(160)1^3,2b^4,5^7,6b^8,1-5,3-7,2bv6,4bw8,1[4:16],2[4:16],3[4:16],4[4:16],1h[8:16],5[8:16],6[8:16],7[8:16],',
  '中央屏': '&bpm=155\n&offset=0\n&title=中央屏\n\n#MASTER\n(155)A1[4:16],B3[4:16],C[4:16],E1[4:16],A5[4:16],B7[4:16],C[4:16],E5[4:16],1[4:16],A2[4:16],3[4:16],B6[4:16],5[4:16],C[4:16],7[4:16],E3[4:16],'
};
for (const [name, txt] of Object.entries(samples)) {
  const r = DX3.parseSimai(txt, 4);
  const keys = Object.keys(r.charts);
  check(`Simai「${name}」解析出谱面`, keys.length > 0, JSON.stringify(r.warnings));
  if (!keys.length) continue;
  const ch = r.charts[keys[0]];
  check(`Simai「${name}」音符数 = 16`, ch.notes.length === 16, `${ch.notes.length}`);
  const D = runEngine(null, []);
  const res = play(D, ch, 'perfect');
  console.log(`  「${name}」→ ${ch.notes.length} 音符，全 CP ${res.ach}% ${res.rk} COMBO ${res.mx}`);
  check(`Simai「${name}」能全 CP`, res.m === 0 && res.mx === ch.notes.length,
    `MISS ${res.m} COMBO ${res.mx}`);
}

// 滑动星星专项
console.log('\n=== 滑动星星 ===');
const starTxt = '&bpm=160\n&offset=0\n&title=星星专项\n\n#MASTER\n(160)1b^3[8:16],2b^4[8:16],5b^7[8:16],6b^8[8:16],';
const rs = DX3.parseSimai(starTxt, 4);
const cs = rs.charts[Object.keys(rs.charts)[0]];
const slStars = cs.notes.filter((n) => n.star && n.k === 'slide').length;
check('滑动星星被解析出来', slStars === 4, `${slStars}`);
const DStar = runEngine(null, []);
const rStar = play(DStar, cs, 'perfect');
console.log(`  4 个滑动星星全 CP：${rStar.ach}% ${rStar.rk}`);
check('全滑动星星全 CP → 101%', Math.abs(rStar.ach - 101) < 0.001, `${rStar.ach}%`);
check('全滑动星星全 CP → SSS+', rStar.rk === 'SSS+', rStar.rk);

// ---------------------------------------------------------------- 生成器 / 成绩码
console.log('\n=== 生成器与成绩码 ===');
const DX4 = runEngine(null, []);
const gen = DX4.buildChart({ title: '测试曲', artist: '', bpm: 170, ds: 13.2 }, 4, 60);
check('JS 生成器产出音符', gen.notes.length > 150, `${gen.notes.length}`);
check('JS 生成器有星星', (gen.counts.break || 0) > 5, `${gen.counts.break}`);
const genA = DX4.buildChart({ title: '测试曲', artist: '', bpm: 170, ds: 13.2 }, 4, 60);
check('JS 生成器是确定性的', JSON.stringify(gen.notes) === JSON.stringify(genA.notes), '两次结果不同');
const gsl = gen.notes.filter((n) => n.star && n.k === 'slide').length;
check('JS 生成器有滑动星星', gsl > 0, `${gsl}`);
console.log(`  生成谱：${gen.notes.length} 音符，星 ${gen.counts.break}（滑动星 ${gsl}）`);

const code = DX4.makeCode({ g: 'dx', t: '测试曲', ach: 100.5, rk: 'SSS+' });
console.log('  成绩码：' + code.slice(0, 56) + (code.length > 56 ? '…' : ''));
check('成绩码有 MM1 前缀', code.indexOf('MM1:') === 0, code.slice(0, 10));
check('成绩码有三段', code.split(':').length === 3, `${code.split(':').length} 段`);

// ---------------------------------------------------------------- 判定窗口
console.log('\n=== 判定窗口（真机值） ===');
check('±0ms → CRITICAL', DX4.judgeLv(0) === 'cp');
check('±33ms → CRITICAL', DX4.judgeLv(33) === 'cp');
check('±40ms → PERFECT', DX4.judgeLv(40) === 'p');
check('±67ms → PERFECT', DX4.judgeLv(67) === 'p');
check('±80ms → GREAT', DX4.judgeLv(80) === 'gr');
check('±120ms → GOOD', DX4.judgeLv(120) === 'gd');
check('±200ms → MISS', DX4.judgeLv(200) === 'miss');
check('早了算 FAST / 晚了算 SLOW',
  DX4.judgeLv(-40) === 'p' && DX4.judgeLv(40) === 'p', '');

console.log('\n' + (FAILS === 0
  ? `全部 PASS（${CHECKS} 项断言）`
  : `有 ${FAILS} 项 FAIL（共 ${CHECKS} 项）`));
process.exit(FAILS === 0 ? 0 : 1);
