# -*- coding: utf-8 -*-
"""
maimai.py —— 舞萌 DX 机台（谱面引擎 + 演奏机台）

这不是「四轨下落式」，而是照着 DX 机台的样子做的：

  · 中央屏幕 —— 曲名 / BPM / COMBO / 判定文字 / 实时达成率，
                还有 DX 独有的 TOUCH（黄绿）和 EX（紫）触摸音符
  · 圆环判定区 —— 8 个分区（A1~A8）围成一圈，NOTE 从圆心生出来往外扩，
                扩到外圈那道判定环的瞬间敲下去
  · NOTE 类型 —— TAP / HOLD / SLIDE / BREAK / TOUCH / EX
  · 结算 —— 达成率（4 位小数）+ SSS+~D 评级 + CP/P/Gr/Gd/Miss 明细 + FAST/SLOW

谱面是本地按「曲名 + 难度」确定性生成的（同一首歌同一难度永远同一张谱，
所以能刷分），依据 BPM 与定数决定密度，按 intro / verse / build / chorus /
bridge / chorus2 / outro 分段，并混入交互、楼梯、双押、SLIDE 连扫这类
真实谱面里常见的配置。

合规：不引用任何真实谱面文件，不加载任何外部资源；
伴奏与判定音全部由 Web Audio 实时合成，离线可玩。
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

_JS_FILE = Path(__file__).with_name("dx_cabinet.js")

DIFF_NAMES = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "Re:MASTER"]
DIFF_CN = ["基础", "进阶", "专家", "大师", "里大师"]
DIFF_COLORS = ["#3FA34D", "#E8A33D", "#E5484D", "#A66BFF", "#F2B8E8"]
DEFAULT_DS = [3.0, 6.0, 9.0, 12.0, 13.5]
# 各难度合理的定数区间（防止拿错难度的定数去生成谱面）
_DS_BOUNDS = [(1.0, 7.5), (3.0, 9.5), (6.0, 12.5), (8.0, 14.6), (10.0, 15.6)]

# 达成率 → 评级（与现行机台阈值一致）
RANKS = [
    (100.5, "SSS+"), (100.0, "SSS"), (99.5, "SS+"), (99.0, "SS"), (98.5, "S+"),
    (98.0, "S"), (97.0, "AAA"), (94.0, "AA"), (90.0, "A"), (80.0, "BBB"),
    (75.0, "B"), (70.0, "C"), (0.0, "D"),
]


def rank_of(ach: float) -> str:
    for line, name in RANKS:
        if ach >= line:
            return name
    return "D"


def diff_index_of(name: str) -> int:
    """把曲库里的难度名（Basic / Re:Master …）换成 0~4 的下标。"""
    n = (name or "").strip().lower().replace(" ", "")
    for i, d in enumerate(DIFF_NAMES):
        if d.lower().replace(":", "").replace(" ", "") == n.replace(":", ""):
            return i
    for i, d in enumerate(DIFF_NAMES):
        if n.startswith(d.lower()[:4]):
            return i
    return 3


# 判定窗口（毫秒）：机台上就是这个宽严 —— CP 33 / P 67 / GREAT 100 / GOOD 150
WINDOWS = {"cp": 33.0, "p": 67.0, "gr": 100.0, "gd": 150.0, "miss": 200.0}

# 达成率系数（真机口径）：全 PERFECT 约 98%，全 GREAT 约 88%，全 GOOD 约 65%
NOTE_VALUE = {"cp": 1.0, "p": 0.98, "gr": 0.88, "gd": 0.65, "miss": 0.0}

# BREAK 加成：一个音符基础 500 分，每个打出 CP 的 BREAK 额外 +100 分，
# 但这份加成最多让整首的达成率 +1% —— 这就是舞萌上限 101.0000% 的来历。
NOTE_POINTS = 500.0
BREAK_BONUS_POINTS = 100.0
BREAK_BONUS_CAP = 1.0          # 百分点


def _seed(title: str, diff: str) -> int:
    h = hashlib.md5(f"dx|{title}|{diff}".encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


# 每个难度的音符类型权重：tap / hold / slide / break / touch / ex
_WEIGHTS = [
    (88, 12, 0,  0,  0, 0),      # BASIC     —— 只有 TAP 和 HOLD
    (70, 16, 11, 3,  0, 0),      # ADVANCED
    (52, 13, 20, 7,  5, 3),      # EXPERT    —— 开始出 TOUCH / EX
    (42, 11, 26, 11, 6, 4),      # MASTER
    (36, 9,  30, 13, 7, 5),      # Re:MASTER
]

# 每个难度里「模式」的出现概率（剩下的都是散音符）
#   alt = 左右交互 / stair = 楼梯 / chord = 双押 / sweep = SLIDE 连扫
_MODES = [
    {"alt": 0.10, "stair": 0.00, "chord": 0.00, "sweep": 0.00},
    {"alt": 0.12, "stair": 0.00, "chord": 0.00, "sweep": 0.12},
    {"alt": 0.12, "stair": 0.08, "chord": 0.06, "sweep": 0.12},
    {"alt": 0.12, "stair": 0.10, "chord": 0.08, "sweep": 0.14},
    {"alt": 0.12, "stair": 0.12, "chord": 0.08, "sweep": 0.16},
]

# 段落：起止比例 / 段落名 / 密度倍率
_SEGS = [
    (0.00, 0.09, "INTRO",   0.42),
    (0.09, 0.30, "VERSE",   0.85),
    (0.30, 0.40, "BUILD",   1.02),
    (0.40, 0.60, "CHORUS",  1.22),
    (0.60, 0.70, "BRIDGE",  0.80),
    (0.70, 0.92, "CHORUS2", 1.34),
    (0.92, 1.01, "OUTRO",   0.55),
]


def _seg_at(p: float) -> tuple[str, float]:
    for a, b, name, mul in _SEGS:
        if a <= p < b:
            return name, mul
    return "OUTRO", 0.55


# SLIDE 的形状。真机里这些形状决定了手指怎么走，也决定了轨迹怎么画。
SHAPES = ["line", "arc", "arc_l", "arc_r", "v", "wifi", "s_cur", "z_cur", "fan"]
SHAPE_CN = {"line": "直线", "arc": "圆弧", "arc_l": "左弧", "arc_r": "右弧",
            "v": "V 字", "wifi": "Wifi", "s_cur": "S 形", "z_cur": "Z 形",
            "fan": "扇形"}


def _pick_shape(diff_idx: int, rng) -> str:
    """难度越高，SLIDE 的花样越多。"""
    if diff_idx <= 1:
        return "line"
    if diff_idx == 2:
        return rng.choice(["line", "line", "arc"])
    if diff_idx == 3:
        return rng.choice(["line", "line", "arc", "arc", "arc_l", "arc_r", "v"])
    return rng.choice(["line", "arc", "arc_l", "arc_r", "arc_r",
                       "v", "wifi", "s_cur", "z_cur", "fan"])


def build_chart(song: dict, diff_idx: int = 3, duration: float = 76.0) -> dict:
    """
    按曲名 + 难度确定性生成一张谱面。

    song 需要 title / artist / bpm / ds / level / genre（曲库 flatten 后的任意一条）。
    定数越高密度越大，难度越高花样越多；生成的谱面保证：
      · 同一时刻同一分区不会有两个音符
      · HOLD 期间该分区不放别的音符
      · 同一时刻最多 2 个音符（双押），不会突然冒出 8 押
    """
    diff_idx = int(_clamp(diff_idx, 0, 4))
    title = (song.get("title") or "未知曲").strip() or "未知曲"
    artist = (song.get("artist") or "").strip()
    bpm = _clamp(float(song.get("bpm") or 150.0), 60.0, 260.0)
    try:
        ds = float(song.get("ds") or 0.0)
    except (TypeError, ValueError):
        ds = 0.0
    if ds <= 0:
        ds = DEFAULT_DS[diff_idx]
    _lo, _hi = _DS_BOUNDS[diff_idx]
    ds = _clamp(ds, _lo, _hi)

    beat = 60000.0 / bpm
    step = beat / 4.0                      # 一个 16 分格
    total_steps = max(64, int(duration * 1000.0 / step))
    rng = random.Random(_seed(title, DIFF_NAMES[diff_idx]))
    w = _WEIGHTS[diff_idx]

    # 密度直接按「每秒音符数」来定，只跟定数走、不受 BPM 牵连：
    # 定数 1 → 约 1 nps，定数 15 → 约 10 nps，和真实谱面的体感对得上
    nps_target = _clamp(1.0 + (ds - 1.0) * 0.62, 0.8, 10.2)

    # 同一个分区两个音符之间的最小间隔。按格算在高 BPM 下会掉到 30ms 以内，
    # 那就不是人能打的了 —— 所以给一个 45ms 的地板。
    GAP = max(step * 0.5, 45.0)

    notes: list[dict] = []
    busy = [-1e9] * 8                      # 每个分区到什么时候才空出来
    last_touch_t = -1e9
    last_ex_t = -1e9
    last_pos = -1

    def kind_of(step_i: int, allow_break: bool) -> str:
        pool = ["tap", "hold", "slide", "break", "touch", "ex"]
        ws = list(w)
        if not allow_break:
            ws[3] = 0
        if diff_idx < 2:                   # BASIC / ADVANCED 没有中央屏音符
            ws[4] = ws[5] = 0
        if step_i % 8 != 0 and step_i % 8 != 4:
            ws[3] = int(ws[3] * 0.35)      # BREAK 基本只落在 8 分位置
        if not any(ws):
            ws[0] = 1
        return rng.choices(pool, weights=ws, k=1)[0]

    def free_pos(t: float, avoid: int = -1) -> int:
        cand = [p for p in range(8) if t >= busy[p] + GAP]
        if avoid in cand and len(cand) > 1 and rng.random() < 0.78:
            cand = [p for p in cand if p != avoid]
        if not cand:
            return -1
        return rng.choice(cand)

    same_t = {"t": -1e9, "n": 0}      # 环上同一时刻放了几个
    ctr_t = {"t": -1e9, "n": 0}       # 中央屏同一时刻放了几个

    def occupied(t: float) -> int:
        """同一时刻环上已经放了几个音符（用来限制最多双押）。"""
        return same_t["n"] if t - same_t["t"] < GAP else 0

    def emit(t: float, pos: int, kind: str, to: int = -1, dur: float = 0.0,
             star: int = 0, shape: str = "line"):
        nonlocal last_touch_t, last_ex_t, last_pos
        if pos < 0:
            return False
        if kind == "break":                 # 兼容旧写法：星星 = 普通音符 + star 标记
            kind, star = "tap", 1
        if t < busy[pos] + GAP:
            return False
        if kind in ("touch", "ex", "thold"):
            if t - ctr_t["t"] < GAP and ctr_t["n"] >= 1:
                return False
        else:
            if t - same_t["t"] < GAP and same_t["n"] >= 2:
                return False          # 环上最多双押
        if kind in ("touch", "thold"):
            if t - last_touch_t < beat * 1.5:
                return False
            last_touch_t = t
        if kind == "ex":
            if t - last_ex_t < beat * 1.5:
                return False
            last_ex_t = t

        note: dict = {"t": round(t), "k": kind, "star": star}
        if kind in ("touch", "ex", "thold"):
            note["p"] = rng.randrange(8)          # 中央屏八分区
            note["z"] = "E" if kind == "ex" else rng.choice(["A", "A", "B", "C"])
            if kind == "thold":
                note["d"] = round(max(beat, dur or beat * 2))
            busy[pos] = max(busy[pos], t + step)
        else:
            note["p"] = pos
            if kind == "hold":
                note["d"] = round(dur)
                busy[pos] = max(busy[pos], t + dur + GAP)
            elif kind == "slide":
                note["q"] = to
                note["s"] = shape
                note["d"] = round(beat * 0.5)     # 半拍滑完
                busy[pos] = max(busy[pos], t + GAP * 2)
                busy[to] = max(busy[to], t + beat * 0.5)
            else:
                busy[pos] = max(busy[pos], t + GAP)
        notes.append(note)
        last_pos = pos
        slot = ctr_t if kind in ("touch", "ex") else same_t
        if t - slot["t"] < GAP:
            slot["n"] += 1
        else:
            slot["t"], slot["n"] = t, 1
        return True

    modes = _MODES[diff_idx]

    def advance(i: int, k: int) -> int:
        """推进游标，但不跨过下一条小节线（否则小节首拍的星星会被跳过）。"""
        j = i + max(1, k)
        nxt = ((i // 16) + 1) * 16
        return nxt if j > nxt > i else j

    i = 0
    while i < total_steps:
        p = i / total_steps
        _name, mul = _seg_at(p)
        dens = _clamp(nps_target * (step / 1000.0) * mul, 0.02, 0.95)
        t = i * step
        allow_break = (i % 8 == 0)

        # 小节首拍：按难度概率塞一颗星星。BREAK 是这类谱面的分数大头，
        # 少了就不是那个味儿了。高难度还会出「滑动星星」—— 头是星星的 SLIDE，
        # 判定按 BREAK 算，是最容易掉分也最值钱的那类音符。
        if i % 16 == 0 and diff_idx >= 1 and rng.random() < (0.10 + diff_idx * 0.11):
            bp = free_pos(t, last_pos)
            if bp >= 0 and occupied(t) < 2:
                if diff_idx >= 2 and rng.random() < 0.36:
                    span = rng.choice([2, 3, 4, 5])
                    qq = (bp + span * rng.choice([1, -1])) % 8
                    if emit(t, bp, "slide", to=qq, star=1,
                            shape=_pick_shape(diff_idx, rng)):
                        i = advance(i, 2)
                        continue
                elif emit(t, bp, "break"):
                    i = advance(i, 2)
                    continue

        if rng.random() >= dens:
            i += 1
            continue
        if occupied(t) >= 2:
            i += 1
            continue

        r = rng.random()
        _a = modes["alt"]
        _b = _a + modes["stair"]
        _c = _b + modes["chord"]
        _d = _c + modes["sweep"]
        # —— 模式：真实谱面里常见的那几种配置 ——
        if r < _a:
            # 交互：两个分区来回交替
            a = free_pos(t, last_pos)
            if a < 0:
                i += 1
                continue
            b = (a + rng.choice([2, 3, 4, 5])) % 8
            k = rng.randint(4, 8)
            gap = 1 if dens > 0.5 else 2
            for j in range(k):
                tt = (i + j * gap) * step
                pp = a if j % 2 == 0 else b
                if tt >= busy[pp] + GAP:
                    emit(tt, pp, "tap")
                    if j % 2 == 0:
                        busy[a] = max(busy[a], tt + GAP)
                    else:
                        busy[b] = max(busy[b], tt + GAP)
            i = advance(i, k * gap)
            continue

        if _a <= r < _b:
            # 楼梯：顺着环一路走上去（或走下来）
            a = free_pos(t, last_pos)
            if a < 0:
                i += 1
                continue
            d = rng.choice([1, -1])
            k = rng.randint(4, 8)
            gap = 1 if dens > 0.55 else 2
            for j in range(k):
                tt = (i + j * gap) * step
                pp = (a + d * j) % 8
                emit(tt, pp, "tap")
                busy[pp] = max(busy[pp], tt + GAP)
            i = advance(i, k * gap)
            continue

        if _b <= r < _c:
            # 双押：同一时刻两个分区
            a = free_pos(t, last_pos)
            if a < 0:
                i += 1
                continue
            b = (a + rng.choice([3, 4, 5])) % 8
            if emit(t, a, "tap"):
                emit(t, b, "tap")
            i = advance(i, 2)
            continue

        if _c <= r < _d and w[2] > 0:
            # SLIDE 连扫：一串 SLIDE 沿着环推过去
            a = free_pos(t, last_pos)
            if a < 0:
                i += 1
                continue
            d = rng.choice([1, -1])
            k = rng.randint(2, 3)
            span = rng.choice([1, 2, 3] if diff_idx <= 2 else [2, 3, 4, 5])
            for j in range(k):
                tt = (i + j * 4) * step
                pp = (a + d * j * 2) % 8
                qq = (pp + d * span) % 8
                emit(tt, pp, "slide", to=qq,
                     star=1 if rng.random() < 0.14 else 0,
                     shape=_pick_shape(diff_idx, rng))
                busy[pp] = max(busy[pp], tt + GAP * 2)
                busy[qq] = max(busy[qq], tt + beat * 0.5)
            i = advance(i, k * 4)
            continue

        # —— 单个音符 ——
        kind = kind_of(i, allow_break)
        if kind == "touch" and diff_idx >= 3 and rng.random() < 0.10:
            kind = "thold"                     # 中央屏的 TOUCH HOLD
        if kind in ("touch", "ex", "thold"):
            dur = beat * rng.choice([1.0, 1.5, 2.0])
            emit(t, free_pos(t, last_pos), kind, dur=dur)
        else:
            pos = free_pos(t, last_pos)
            if pos < 0:
                i += 1
                continue
            if kind == "hold":
                dur = beat * rng.choice([1.0, 1.5, 2.0, 2.0, 3.0])
                emit(t, pos, "hold", dur=dur)
            elif kind == "slide":
                span = rng.choice([1, 1, 2, 2, 3] if diff_idx <= 2 else [1, 2, 3, 4, 5, 6])
                to = (pos + span * rng.choice([1, -1])) % 8
                if to == pos:
                    to = (pos + 2) % 8
                emit(t, pos, "slide", to=to,
                     star=1 if (allow_break and rng.random() < 0.16) else 0,
                     shape=_pick_shape(diff_idx, rng))
            else:
                emit(t, pos, kind)
        i += 1

    notes.sort(key=lambda n: (n["t"], n["p"]))
    # 收尾：最后一个音符之后留 2 秒给结算动画
    end_ms = (notes[-1]["t"] if notes else duration * 1000) + 2200

    counts = {k: 0 for k in ("tap", "hold", "slide", "touch", "thold", "ex", "break")}
    for n in notes:
        counts[n["k"]] = counts.get(n["k"], 0) + 1
        if n.get("star"):
            counts["break"] += 1                # 星星总数（含滑动星星）

    return {
        "song": {
            "title": title, "artist": artist, "bpm": round(bpm),
            "ds": round(ds, 1), "level": song.get("level") or "",
            "genre": song.get("genre") or "", "diff": DIFF_NAMES[diff_idx],
            "diffIdx": diff_idx, "diffCn": DIFF_CN[diff_idx],
            "color": DIFF_COLORS[diff_idx],
        },
        "bpm": round(bpm), "beat": round(beat, 3), "step": round(step, 3),
        "duration": round(end_ms / 1000.0, 2),
        "notes": notes, "counts": counts,
        "sections": [{"a": a, "b": b, "name": n} for a, b, n, _m in _SEGS],
    }


def chart_stats(chart: dict) -> dict:
    """谱面统计：音符数、时长、每秒密度、各类型数量。"""
    notes = chart.get("notes") or []
    dur = max(1.0, float(chart.get("duration") or 76.0))
    return {
        "total": len(notes),
        "nps": round(len(notes) / dur, 2),
        "duration": dur,
        "counts": chart.get("counts") or {},
    }


def theoretical_ach(chart: dict) -> float:
    """
    这张谱全部 CRITICAL PERFECT 的达成率。
    有星星且星星够多 → 101.0000%；星星很少 → 按比例少一点；没星星 → 100.0000%。
    """
    notes = chart.get("notes") or []
    if not notes:
        return 0.0
    n = len(notes)
    nb = sum(1 for x in notes if x.get("star"))
    if not nb:
        return 100.0
    # 加成（百分点）= 100 × (nb×100) / (n×500)，封顶 1%
    return 100.0 + min(BREAK_BONUS_CAP,
                       100.0 * BREAK_BONUS_POINTS * nb / (NOTE_POINTS * n))


def achievement_of(judged: list[dict], total_notes: int, total_breaks: int) -> float:
    """
    按真机口径算达成率：判定倍率求平均 + BREAK 加成（上限 1%）。
    judged 是 [{lv:'cp'|'p'|'gr'|'gd'|'miss', star:0/1}, ...]
    """
    if total_notes <= 0:
        return 0.0
    s = 0.0
    cp_break = 0
    for j in judged:
        s += NOTE_VALUE.get(j.get("lv") or "miss", 0.0)
        if j.get("star") and j.get("lv") == "cp":
            cp_break += 1
    bonus = 0.0
    if total_breaks > 0:
        bonus = min(BREAK_BONUS_CAP,
                    100.0 * BREAK_BONUS_POINTS * cp_break / (NOTE_POINTS * total_notes))
    return round(s / total_notes * 100.0 + bonus, 4)


# ---------------------------------------------------------------- 机台
_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05080c;font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#dff0ef}
#dxroot{position:relative;width:100%;display:flex;flex-direction:column;align-items:center}
canvas{display:block;width:100%;height:auto;background:radial-gradient(circle at 50% 46%,#101820 0%,#05080c 72%);
  border-radius:14px;border:1px solid rgba(120,200,200,.14);cursor:pointer;touch-action:none}
#dxhint{margin-top:6px;font-size:11px;color:#7f8f96;line-height:1.7;text-align:center}
#dxhint b{color:#9fe8e2}
kbd{background:rgba(57,197,187,.16);border:1px solid rgba(57,197,187,.4);border-radius:4px;
  padding:1px 5px;font-family:Consolas,monospace;font-size:10px;color:#9fe8e2;margin:0 1px}
"""


def cabinet_html(chart: dict, height: int = 620) -> str:
    """把一张谱面渲染成一台可以真正打的自包含机台。"""
    js = _JS_FILE.read_text(encoding="utf-8")
    data = json.dumps(chart, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/")        # 防止曲名里的 </script> 提前闭合
    shell = (
        '<div id="dxroot">'
        '<canvas id="dxcv" width="960" height="560"></canvas>'
        '<div id="dxhint"></div>'
        "</div>"
        "<script>\nvar CHART=" + data + ";\n" + js + "\n</script>"
    )
    return (
        "<style>" + _CSS + "</style>"
        "<div style='background:#05080c;border-radius:14px;padding:8px'>"
        + shell + "</div>"
    )


def chart_breakdown(chart: dict) -> dict:
    """给界面用的详细统计：滑动星星数、各 SLIDE 形状数、BREAK 占比。"""
    notes = chart.get("notes") or []
    star_tap = star_slide = 0
    shapes: dict[str, int] = {}
    for n in notes:
        if not n.get("star"):
            continue
        if n["k"] == "slide":
            star_slide += 1
        else:
            star_tap += 1
    for n in notes:
        if n["k"] == "slide":
            s = n.get("s") or "line"
            shapes[s] = shapes.get(s, 0) + 1
    n = len(notes)
    nb = star_tap + star_slide
    return {
        "total": n, "breaks": nb, "star_tap": star_tap, "star_slide": star_slide,
        "break_ratio": round(nb / n * 100.0, 1) if n else 0.0,
        "shapes": shapes,
        "theoretical": round(theoretical_ach(chart), 4),
    }


# ---------------------------------------------------------------- Simai 进出
def to_simai(chart: dict) -> str:
    """把谱面写成 Simai 文本（可以拿去别的工具里改，也能再导回来）。"""
    from modules import simai
    return simai.dump(chart)


def from_simai(text: str, default_div: int = 4) -> dict:
    """
    读一份 Simai 谱面。返回 {"charts": {...}, "errors": [...], "warnings": [...]}。
    读不出来的难度会带一条人话错误，不会整个炸掉。
    """
    from modules import simai
    try:
        res = simai.parse(text, default_div=default_div)
    except simai.SimaiError as e:
        return {"charts": {}, "errors": [str(e)], "warnings": []}
    warnings: list[str] = []
    for diff, ch in list(res["charts"].items()):
        simai.normalize(ch)
        for msg in simai.validate(ch):
            warnings.append(f"{diff}：{msg}")
    return {"charts": res["charts"], "errors": [], "warnings": warnings}


def key_help() -> str:
    """给界面用的键位说明（HTML）。"""
    return (
        "环上 8 个分区（从左上逆时针一圈）："
        "<kbd>A</kbd>左上 <kbd>S</kbd>左 <kbd>D</kbd>左下 <kbd>F</kbd>下 "
        "<kbd>J</kbd>右下 <kbd>K</kbd>右 <kbd>L</kbd>右上 <kbd>;</kbd>上（也认 W / O）　·　"
        "中央屏 <kbd>空格</kbd>=TOUCH <kbd>Shift</kbd>=EX　·　"
        "<kbd>Esc</kbd> 中途放弃"
    )
