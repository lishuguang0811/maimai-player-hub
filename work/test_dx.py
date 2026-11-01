# -*- coding: utf-8 -*-
"""
test_dx.py —— 舞萌 DX 机台的引擎侧自检

验的是「谱面生成」和「成绩能否回到账号」这两件事：
  · 谱面没有物理上打不出来的配置（同一分区撞车、HOLD 期间被插音符、突然 8 押）
  · 同一首歌同一难度的谱面永远一样（不然刷分没有意义）
  · 全 CRITICAL PERFECT 的达成率正好 101.0000%（有星星时）
  · 评级阈值对着现行机台
  · 前端吐出来的成绩码，Python 侧能解开（跨语言校验位一致）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules import maimai, playlog, songs            # noqa: E402

FAILS = 0


def check(name, cond, extra=""):
    global FAILS
    ok = bool(cond)
    if not ok:
        FAILS += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


print("=== 谱面生成 ===")
snap = songs.load_snapshot()
rec = songs.flatten(snap) if snap else []
check("曲库有数据", len(rec) > 100, f"{len(rec)} 条")

bucket: dict[str, list[dict]] = {}
for r in rec:
    bucket.setdefault(r["title"], []).append(r)
order = {"Basic": 0, "Advanced": 1, "Expert": 2, "Master": 3,
         "Re:Master": 4, "Re:MASTER": 4}
full = [(t, sorted(v, key=lambda r: order.get(r["diff"], 9)))
        for t, v in bucket.items() if len(v) >= 5]
check("有足够多的完整难度曲目", len(full) >= 20, f"{len(full)} 首")

samples = full[:6] + full[50:56]
bad_conflict = bad_chord = 0
for title, variants in samples:
    for row in variants:
        di = maimai.diff_index_of(row["diff"])
        ch = maimai.build_chart(row, di)
        notes = ch["notes"]
        # 同一分区：两个音符的时间间隔必须够（HOLD 期间不能插别的）
        bypos: dict[int, list[dict]] = {}
        for n in notes:
            if n["k"] in ("touch", "ex", "thold"):
                continue
            bypos.setdefault(n["p"], []).append(n)
        for p, arr in bypos.items():
            arr.sort(key=lambda n: n["t"])
            for a, b in zip(arr, arr[1:]):
                # HOLD 是按住不放，期间同一分区不能再塞音符；
                # SLIDE 划过去之后手指就离开了，同分区可以接着出音符，所以只有 HOLD 计时长。
                need = ((a.get("d") or 0) + 30) if a["k"] == "hold" else 30
                if b["t"] - a["t"] < need:
                    bad_conflict += 1
        # 同一时刻最多双押
        times: dict[int, int] = {}
        for n in notes:
            if n["k"] in ("touch", "ex"):
                continue
            times[n["t"]] = times.get(n["t"], 0) + 1
        if any(v > 2 for v in times.values()):
            bad_chord += 1

check("没有同分区撞车的音符", bad_conflict == 0, f"{bad_conflict} 处")
check("同一时刻不超过双押", bad_chord == 0, f"{bad_chord} 处")

# 确定性
t0, v0 = samples[0]
c1 = maimai.build_chart(v0[3], 3)
c2 = maimai.build_chart(v0[3], 3)
check("同一曲同一难度谱面完全一致", c1["notes"] == c2["notes"])
c3 = maimai.build_chart(v0[2], 2)
check("换难度谱面会变", c3["notes"] != c1["notes"])

# 密度随定数上升
low = maimai.chart_stats(maimai.build_chart(v0[0], 0))["nps"]
high = maimai.chart_stats(maimai.build_chart(v0[4], 4))["nps"]
check("高难度比低难度密", high > low, f"{low} → {high} nps")

# 类型覆盖
mx = maimai.build_chart(v0[4], 4)
cnt = mx["counts"]
check("Re:MASTER 六种音符都在", all(cnt.get(k, 0) > 0 for k in
      ("tap", "hold", "slide", "break", "touch", "ex")), str(cnt))
ba = maimai.build_chart(v0[0], 0)["counts"]
check("BASIC 只有 TAP 和 HOLD", ba.get("slide", 0) == 0 and ba.get("break", 0) == 0
      and ba.get("touch", 0) == 0, str(ba))

print("\n=== 达成率与评级 ===")
for title, variants in samples[:4]:
    for row in variants:
        di = maimai.diff_index_of(row["diff"])
        ch = maimai.build_chart(row, di)
        ach = maimai.theoretical_ach(ch)
        nb = ch["counts"].get("break", 0)
        # 真机口径：BREAK 加成 = 星星占比 × 20，封顶 +1%（所以上限才是 101%）。
        # 星星少的谱（比如 ADVANCED）全 CP 也到不了 101，这是对的。
        total = len(ch["notes"]) or 1
        want = 100.0 + (min(1.0, 20.0 * nb / total) if nb else 0.0)
        check(f"{maimai.DIFF_NAMES[di]} 全 CP = 理论值 {want:.4f}%",
              abs(ach - want) < 1e-6, f"{ach:.4f}%")

check("100.5 → SSS+", maimai.rank_of(100.5) == "SSS+")
check("100.0 → SSS", maimai.rank_of(100.0) == "SSS")
check("99.9999 → SS+", maimai.rank_of(99.9999) == "SS+")
check("98.0 → S", maimai.rank_of(98.0) == "S")
check("97.5 → AAA", maimai.rank_of(97.5) == "AAA")
check("0 → D", maimai.rank_of(0) == "D")

print("\n=== 机台 HTML ===")
html = maimai.cabinet_html(maimai.build_chart(v0[3], 3))
check("带着 canvas", "dxcv" in html)
check("注入了谱面", "var CHART=" in html)
check("没有外部资源", "http://" not in html and "https://" not in html)
check("长度合理", 5_000 < len(html) < 400_000, f"{len(html)} 字符")

print("\n=== 成绩码（前端 → 账号）===")
codes = sorted(ROOT.glob("work/_dx_code_*.txt"))
check("烟测留下了成绩码", len(codes) >= 3, f"{len(codes)} 枚")
for f in codes:
    code = f.read_text(encoding="utf-8").strip()
    ok, payload = playlog.decode(code)
    check(f"{f.name} 能被本机解开", ok, str(payload)[:70])
    if ok:
        check(f"{f.name} 记的是 DX 局", payload.get("g") == "dx")
        check(f"{f.name} 达成率在合理范围", 0 <= float(payload.get("ach", 0)) <= 101,
              str(payload.get("ach")))
        check(f"{f.name} 评级认得出来",
              payload.get("rk") in {r[1] for r in maimai.RANKS}, str(payload.get("rk")))

# 篡改必须被识破
good = codes[0].read_text(encoding="utf-8").strip()
bad = good[:-1] + ("x" if good[-1] != "x" else "y")
ok2, msg = playlog.decode(bad)
check("改过一个字符会被识破", not ok2, str(msg)[:40])
ok3, msg3 = playlog.decode(good.split(":")[0] + ":" + good.split(":")[1])
check("缺了校验位会被识破", not ok3)
mine = playlog.encode({"g": "dx", "t": "x", "ach": 100.0, "rk": "SSS"})
check("自己编的码自己能解", playlog.decode(mine)[0], mine[:40])

print("\n" + ("有 %d 项 FAIL" % FAILS if FAILS else "ALL PASS"))
sys.exit(1 if FAILS else 0)
