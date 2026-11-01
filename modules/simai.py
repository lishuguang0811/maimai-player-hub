"""
Simai 谱面格式：导入 / 导出。

Simai 是舞萌圈通用的谱面文本格式（.txt / .simai），astroDX、Majdata、各种谱面工具都能读。
这里实现的是"能读、能写、读错了会说清楚哪里错"的那一层，Python 侧用它做校验与转换，
浏览器里那份 JS（dx_cabinet.js 内）用的是同一套记号规则。

支持范围
--------
头部指令： &bpm= &offset= &lv= &title= &artist=
难度块：   #Basic / #Advanced / #Expert / #Master / #Re:Master（也认 #00104:13.5:Master 这类）
BPM 变更： (192) 放在任意事件前，作用于其后所有事件
同押：     {1,2} 花括号内同一时刻
音符：     1~8        TAP（1 对应左上，顺时针一圈 —— 与机台键位 A S D F J K L ; 一一对应）
           1b / b1    BREAK 星星
           1h[4:1]    HOLD（[x:y] = x/y 拍）
           1-2         SLIDE，形状符号： - 直线  ^ 弧  < > 左右弧  v V字
                                        w wifi  s S形  z Z形  p q  $ 扇
           1b-2        滑动星星（BREAK SLIDE），头是星星的 SLIDE
           1-2-3       连滑，拆成 1-2 与 2-3 两段
           A1~A8       TOUCH  A 区（中央屏外圈）
           B1~B8       TOUCH  B 区
           C           TOUCH  中央
           C1h[4:1]    TOUCH HOLD
           E1~E8       EX 音符
时间推进： 每个事件占 [x:y] 拍（x/y 拍）；没写就用 default_div（默认 1/4 拍 = 16 分音符）
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------- 常量
DIFF_ORDER = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"]
DIFF_ALIAS = {
    "BASIC": "BASIC", "BAS": "BASIC", "B": "BASIC", "基本": "BASIC", "基础": "BASIC",
    "ADVANCED": "ADVANCED", "ADV": "ADVANCED", "A": "ADVANCED", "进阶": "ADVANCED",
    "EXPERT": "EXPERT", "EXP": "EXPERT", "E": "EXPERT", "专家": "EXPERT",
    "MASTER": "MASTER", "MAS": "MASTER", "M": "MASTER", "大师": "MASTER",
    "RE:MASTER": "RE:MASTER", "REMASTER": "RE:MASTER", "REM": "RE:MASTER",
    "RE": "RE:MASTER", "R": "RE:MASTER", "里大师": "RE:MASTER", "宴": "RE:MASTER",
}

# simai 的形状符号 → 内部名
SHAPE_OF = {
    "-": "line", "—": "line",
    "^": "arc", "~": "arc",
    "<": "arc_l", ">": "arc_r",
    "v": "v", "V": "v",
    "w": "wifi", "W": "wifi",
    "s": "s_cur", "S": "s_cur",
    "z": "z_cur", "Z": "z_cur",
    "p": "p_cur", "q": "q_cur",
    "$": "fan",
}
SHAPE_CHARS = "".join(SHAPE_OF.keys())
# 反向：内部名 → simai 符号
CHAR_OF = {
    "line": "-", "arc": "^", "arc_l": "<", "arc_r": ">",
    "v": "v", "wifi": "w", "s_cur": "s", "z_cur": "z",
    "p_cur": "p", "q_cur": "q", "fan": "$",
}

# 音符记号的正则（一次抓一个）
RE_SLIDE = re.compile(
    r"^(?P<a>[1-8])(?P<ab>b?)(?P<sh>[" + re.escape(SHAPE_CHARS) + r"]+)"
    r"(?P<b>[1-8])(?P<bb>b?)")
RE_SLIDE_MORE = re.compile(
    r"^(?P<sh>[" + re.escape(SHAPE_CHARS) + r"]+)(?P<b>[1-8])(?P<bb>b?)")
RE_TAP = re.compile(r"^(?P<a>[1-8])(?P<ab>b?)(?P<h>h?)(?P<dur>\[[^\]]*\])?")
RE_TOUCH = re.compile(
    r"^(?P<z>[A-Ea-e])(?P<p>[1-8]?)(?P<ab>b?)(?P<h>h?)(?P<dur>\[[^\]]*\])?")


class SimaiError(Exception):
    """谱面读不懂。带行号/小节号，直接给用户看。"""

    def __init__(self, msg: str, where: str = ""):
        super().__init__((where + "：" + msg) if where else msg)
        self.where = where


# ---------------------------------------------------------------- 工具
def _split_top(text: str, sep: str = ",") -> list[str]:
    """按顶层分隔符切开，花括号 / 圆括号 / 方括号里的内容不受影响。"""
    out, buf, depth = [], [], 0
    for ch in text:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == sep and depth <= 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def _parse_dur(tok: str, beat_ms: float, default_beats: float) -> tuple[float, bool]:
    """
    解析 [x:y] → 拍数。返回 (拍数, 是否显式给了)。
    [4:1] = 4 拍；[1:4] = 0.25 拍；[2] = 2 拍。x 可以是小数。
    """
    if not tok:
        return default_beats, False
    inner = tok.strip()[1:-1].strip()
    if not inner:
        return default_beats, False
    if ":" in inner:
        x, _, y = inner.partition(":")
        try:
            xf = float(x)
            yf = float(y) if y.strip() else 1.0
        except ValueError:
            return default_beats, False
        if yf == 0:
            return default_beats, False
        return xf / yf, True
    try:
        return float(inner), True
    except ValueError:
        return default_beats, False


def _beat_ms_of(bpm: float) -> float:
    return 60000.0 / max(1.0, float(bpm or 120.0))


# ---------------------------------------------------------------- 解析
def _parse_note(tok: str, t: float, beat_ms: float, default_beats: float,
                where: str) -> tuple[list[dict], float, bool]:
    """
    解析一个音符记号（可能带连滑），返回 (音符列表, 这个事件占用的拍数, 时值是否显式写了)。
    """
    s = tok.strip()
    if not s:
        return [], default_beats, False
    out: list[dict] = []

    # ---- SLIDE：1-2 / 1b-2 / 1-2-3 ----
    m = RE_SLIDE.match(s)
    if m:
        star = 1 if (m.group("ab") or m.group("bb")) else 0
        a = int(m.group("a")) - 1
        b = int(m.group("b")) - 1
        shape = SHAPE_OF.get(m.group("sh")[-1], "line")
        if len(m.group("sh")) > 1 and m.group("sh")[-1] == "-" and \
                m.group("sh")[0] in ("p", "q"):
            shape = SHAPE_OF[m.group("sh")[0]]
        rest = s[m.end():]
        dur_tok = ""
        md = re.match(r"^(\[[^\]]*\])", rest)
        if md:
            dur_tok = md.group(1)
            rest = rest[md.end():]
        dur_beats, given = _parse_dur(dur_tok, beat_ms, default_beats)
        slide_ms = dur_beats * beat_ms if given else beat_ms * 0.5
        slide_ms = max(120.0, min(slide_ms, beat_ms * 4))
        out.append({"t": round(t, 2), "k": "slide", "p": a, "q": b,
                    "d": round(slide_ms, 1), "s": shape, "star": star})
        # 连滑：后面还有 -3 / ^5 之类
        while True:
            m2 = RE_SLIDE_MORE.match(rest.strip())
            if not m2:
                break
            nb = int(m2.group("b")) - 1
            shape2 = SHAPE_OF.get(m2.group("sh")[-1], "line")
            out.append({"t": round(t, 2), "k": "slide", "p": b, "q": nb,
                        "d": round(slide_ms, 1), "s": shape2,
                        "star": 1 if m2.group("bb") else star})
            b = nb
            rest = rest[m2.end():]
            md = re.match(r"^(\[[^\]]*\])", rest.strip())
            if md:
                rest = rest[md.end():]
        advance = dur_beats if given else default_beats
        return out, advance, given

    # ---- TOUCH / EX：A1 B3 C E5 ----
    m = RE_TOUCH.match(s)
    if m:
        z = m.group("z").upper()
        pos = int(m.group("p")) - 1 if m.group("p") else 0
        star = 1 if m.group("ab") else 0
        hold = bool(m.group("h"))
        dur_beats, given = _parse_dur(m.group("dur") or "", beat_ms, default_beats)
        if z == "E":
            out.append({"t": round(t, 2), "k": "ex", "z": "E", "p": pos})
        elif hold:
            out.append({"t": round(t, 2), "k": "thold", "z": z, "p": pos,
                        "d": round(max(120.0, dur_beats * beat_ms), 1), "star": star})
        else:
            out.append({"t": round(t, 2), "k": "touch", "z": z, "p": pos, "star": star})
        return out, (dur_beats if given else default_beats), given

    # ---- TAP / BREAK / HOLD ----
    m = RE_TAP.match(s)
    if m:
        p = int(m.group("a")) - 1
        star = 1 if m.group("ab") else 0
        hold = bool(m.group("h"))
        dur_beats, given = _parse_dur(m.group("dur") or "", beat_ms, default_beats)
        if hold:
            out.append({"t": round(t, 2), "k": "hold", "p": p, "star": star,
                        "d": round(max(120.0, dur_beats * beat_ms), 1)})
        else:
            out.append({"t": round(t, 2), "k": "tap", "p": p, "star": star})
        return out, (dur_beats if given else default_beats), given

    raise SimaiError(f"看不懂的音符记号「{s}」", where)


def _parse_block(body: str, meta: dict, default_beats: float,
                 diff: str) -> dict:
    """解析一个难度块的正文。"""
    bpm = float(meta.get("bpm") or 120.0)
    offset_ms = float(meta.get("offset_ms") or 0.0)
    beat_ms = _beat_ms_of(bpm)
    t = offset_ms
    notes: list[dict] = []
    events = _split_top(body, ",")
    bar = 1
    beats_in_bar = 0.0

    for ei, ev in enumerate(events):
        ev = ev.strip()
        if not ev:
            continue
        where = f"{diff} 第{bar}小节第{ei + 1}个"

        # BPM 变更
        mb = re.match(r"^\((\d+(?:\.\d+)?)\)", ev)
        if mb:
            bpm = float(mb.group(1))
            beat_ms = _beat_ms_of(bpm)
            ev = ev[mb.end():].strip()
            if not ev:
                continue

        # 纯时值：只写 [8:16] 表示空过一段时间（有些谱面这么写休止）
        if ev.startswith("["):
            md0 = re.match(r"^(\[[^\]]*\])", ev)
            if md0 and not ev[md0.end():].strip():
                adv, _ = _parse_dur(md0.group(1), beat_ms, default_beats)
                t += adv * beat_ms
                beats_in_bar += adv
                if beats_in_bar >= 3.999:
                    beats_in_bar = 0.0
                    bar += 1
                continue

        # 同押 {1,2}
        if ev.startswith("{"):
            close = ev.find("}")
            if close < 0:
                raise SimaiError("同押的 { 没有配对的 }", where)
            inner = ev[1:close]
            tail = ev[close + 1:].strip()
            explicit: list[float] = []
            for tok in _split_top(inner, ","):
                ns, adv, given = _parse_note(tok, t, beat_ms, default_beats, where)
                notes.extend(ns)
                if given:
                    explicit.append(adv)
            if tail:
                if tail.startswith("["):       # 同押组后面的纯时值
                    adv0, given0 = _parse_dur(tail, beat_ms, default_beats)
                    if given0:
                        explicit.append(adv0)
                else:
                    ns, adv, given = _parse_note(tail, t, beat_ms, default_beats, where)
                    notes.extend(ns)
                    if given:
                        explicit.append(adv)
            sub_adv = max(explicit) if explicit else default_beats
            t += sub_adv * beat_ms
            beats_in_bar += sub_adv
            if beats_in_bar >= 3.999:
                beats_in_bar = 0.0
                bar += 1
            continue

        ns, adv, _g = _parse_note(ev, t, beat_ms, default_beats, where)
        notes.extend(ns)
        t += adv * beat_ms
        beats_in_bar += adv
        if beats_in_bar >= 3.999:
            beats_in_bar = 0.0
            bar += 1

    notes.sort(key=lambda n: (n["t"], n.get("p", 0)))
    if not notes:
        raise SimaiError("这个难度块里一个音符都没读出来", diff)
    last = notes[-1]
    end = last["t"] + (last.get("d") or 0.0)
    duration = round(max(8.0, (end - offset_ms) / 1000.0 + 4.0), 2)
    counts: dict[str, int] = {}
    for n in notes:
        counts[n["k"]] = counts.get(n["k"], 0) + 1
    return {
        "title": meta.get("title") or "导入谱面",
        "artist": meta.get("artist") or "",
        "bpm": round(bpm, 2),
        "offset": round(offset_ms, 1),
        "diff": diff,
        "ds": float(meta.get("ds") or 0.0),
        "duration": duration,
        "notes": notes,
        "counts": counts,
        "source": "simai",
    }


def parse(text: str, default_div: int = 4) -> dict:
    """
    解析一份 Simai 谱面文本。
    default_div：没写 [x:y] 时每个事件占多少分之一拍（4 = 1/4 拍 = 16 分音符）。
    返回 {"meta": {...}, "charts": {难度: 谱面}, "errors": [...]}，errors 只是警告不致命。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    meta: dict[str, Any] = {}
    blocks: list[tuple[str, str]] = []
    errors: list[str] = []

    # ---- 头部指令 ----
    cur_diff = None
    cur_buf: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("&"):
            m = re.match(r"^&(\w+)\s*=\s*(.*)$", line)
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                if key == "bpm":
                    try:
                        meta["bpm"] = float(re.split(r"[^\d.]", val)[0] or 120)
                    except (ValueError, IndexError):
                        errors.append(f"&bpm= 读不出来：「{val}」，按 120 算")
                elif key == "offset":
                    try:
                        meta["offset_ms"] = float(re.split(r"[^\d.\-]", val)[0] or 0) * 1000.0
                    except (ValueError, IndexError):
                        meta["offset_ms"] = 0.0
                elif key == "title":
                    meta["title"] = val
                elif key == "artist":
                    meta["artist"] = val
                elif key in ("lv", "level", "ds"):
                    try:
                        meta["ds"] = float(re.split(r"[^\d.]", val)[0] or 0)
                    except (ValueError, IndexError):
                        pass
            continue
        if line.startswith("#") or line.startswith("＃"):
            if cur_diff is not None:
                blocks.append((cur_diff, "\n".join(cur_buf)))
            cur_buf = []
            head = line.lstrip("#＃").strip()
            name = None
            # #Master 13.5 / #00104:13.5:Master / #Master
            for part in re.split(r"[:：\s]+", head):
                up = part.upper()
                if up in DIFF_ALIAS:
                    name = DIFF_ALIAS[up]
                    break
            if name is None:
                for key, val in DIFF_ALIAS.items():
                    if key in head.upper():
                        name = val
                        break
            if name is None:
                name = DIFF_ORDER[min(len(blocks), len(DIFF_ORDER) - 1)]
                errors.append(f"难度头「{head}」认不出来，当作 {name}")
            mlv = re.search(r"(\d{1,2}(?:\.\d)?)", head)
            if mlv and not meta.get("ds"):
                try:
                    meta["ds"] = float(mlv.group(1))
                except ValueError:
                    pass
            cur_diff = name
            continue
        cur_buf.append(line)
    if cur_diff is not None:
        blocks.append((cur_diff, "\n".join(cur_buf)))
    elif cur_buf:
        # 没有 # 分隔：整段当一个难度
        body = "\n".join(cur_buf)
        if re.search(r"[1-8]", body):
            blocks.append(("MASTER", body))

    if not blocks:
        raise SimaiError("这不像 Simai 谱面：既没有难度块（#Master），也找不到任何音符。")

    default_beats = 1.0 / max(1, int(default_div or 4))
    charts: dict[str, dict] = {}
    for diff, body in blocks:
        try:
            ch = _parse_block(body, meta, default_beats, diff)
        except SimaiError as e:
            errors.append(str(e))
            continue
        if diff in charts:                      # 同名难度合并
            charts[diff]["notes"].extend(ch["notes"])
            charts[diff]["notes"].sort(key=lambda n: (n["t"], n.get("p", 0)))
        else:
            charts[diff] = ch
    if not charts:
        raise SimaiError("一个难度都没解析成功：" + "；".join(errors[:3]))
    return {"meta": meta, "charts": charts, "errors": errors}


# ---------------------------------------------------------------- 导出
_FMT_DIV = 192          # 时值精度：1/192 拍（BPM 200 时约 1.5ms，足够）


def _fmt_beats(beats: float) -> str:
    """把拍数写成 [x:192] 这样的 simai 时值记号。"""
    x = int(round(max(0.0, beats) * _FMT_DIV))
    if x <= 0:
        x = 1
    return f"[{x}:{_FMT_DIV}]"


def dump(chart: dict) -> str:
    """把我们内部的谱面模型写成 Simai 文本（可以再导回来）。"""
    notes = sorted(chart.get("notes") or [], key=lambda n: n["t"])
    if not notes:
        return ""
    bpm = float(chart.get("bpm") or 120.0)
    beat_ms = _beat_ms_of(bpm)
    offset_ms = float(chart.get("offset") or 0.0)
    if offset_ms <= 0.0:
        # 谱面没标 offset，但第一个音符不一定在 0 —— 这段前置静默要写进 &offset，
        # 否则导回来整首会往前挪。
        offset_ms = float(notes[0].get("t") or 0.0)
    title = (chart.get("title") or (chart.get("song") or {}).get("title") or "")
    artist = (chart.get("artist") or (chart.get("song") or {}).get("artist") or "")
    lines = [
        f"&bpm={bpm:g}",
        f"&offset={offset_ms / 1000.0:.3f}",
        f"&title={title}",
    ]
    if artist:
        lines.append(f"&artist={artist}")
    if chart.get("ds"):
        lines.append(f"&lv={chart['ds']:g}")
    lines.append("")
    lines.append(f"#{(chart.get('diff') or 'MASTER').upper()}")

    # 同一时刻的音符合成一个 { } 同押组
    groups: list[tuple[float, list[dict]]] = []
    for n in notes:
        if groups and abs(groups[-1][0] - n["t"]) < 1.0:
            groups[-1][1].append(n)
        else:
            groups.append((n["t"], [n]))

    # 关键：时值用「下一个音符的绝对拍位 − 这一个的绝对拍位」来算。
    # 如果各自 round 间隔再累加，量化误差会一路累积到几十毫秒；
    # 锚在绝对拍位上，每个音符的位置误差就只有 1/(2×192) 拍，且不会累积。
    xs = [int(round((t - offset_ms) / beat_ms * _FMT_DIV)) for t, _ in groups]

    out: list[str] = []
    for i, (t, grp) in enumerate(groups):
        x = (xs[i + 1] - xs[i]) if i + 1 < len(groups) else _FMT_DIV
        if x < 1:
            x = 1
        toks = []
        own_beats = 0.0                     # 组内 HOLD / SLIDE 自身的时长
        for n in grp:
            k = n["k"]
            star = 1 if n.get("star") else 0
            if k == "break":                # 旧模型：星星单独一种类型
                k, star = "tap", 1
            if k == "slide":
                sh = CHAR_OF.get(n.get("s") or "line", "-")
                toks.append(f"{n['p'] + 1}{'b' if star else ''}{sh}{n['q'] + 1}")
                own_beats = max(own_beats, (n.get("d") or 0) / beat_ms)
            elif k == "hold":
                toks.append(f"{n['p'] + 1}{'b' if star else ''}h")
                own_beats = max(own_beats, (n.get("d") or 0) / beat_ms)
            elif k == "tap":
                toks.append(f"{n['p'] + 1}{'b' if star else ''}")
            elif k == "touch":
                toks.append(f"{n.get('z') or 'A'}{(n.get('p') or 0) + 1}"
                            f"{'b' if star else ''}")
            elif k == "thold":
                toks.append(f"{n.get('z') or 'C'}{(n.get('p') or 0) + 1}h")
                own_beats = max(own_beats, (n.get("d") or 0) / beat_ms)
            elif k == "ex":
                toks.append(f"E{(n.get('p') or 0) + 1}")
        body = ",".join(toks)
        if len(grp) > 1:
            body = "{" + body + "}"
        # simai 的 [x:y] 既是这个音符的时长、也决定时间推进，两者没法分开写。
        # 真谱面也是这么做的 —— 所以直接用「到下一个音符的间隔」
        # （HOLD 尾巴会顶到下一个音符，这是格式本身的取舍）。
        out.append(f"{body}[{x}:{_FMT_DIV}]")
    lines.append(",".join(out) + ",")
    return "\n".join(lines)


# ---------------------------------------------------------------- 校验
def validate(chart: dict) -> list[str]:
    """谱面体检，返回给人看的问题列表（空 = 没问题）。"""
    notes = chart.get("notes") or []
    problems: list[str] = []
    if not notes:
        return ["谱面是空的。"]
    if not (1.0 <= float(chart.get("bpm") or 0) <= 500.0):
        problems.append(f"BPM {chart.get('bpm')} 不正常。")
    for i, n in enumerate(notes):
        if n["k"] in ("tap", "hold", "slide") and not (0 <= (n.get("p") or 0) <= 7):
            problems.append(f"第 {i + 1} 个音符位置 {n.get('p')} 越界（应为 0~7）。")
        if n["k"] == "slide":
            if not (0 <= (n.get("q") or 0) <= 7):
                problems.append(f"第 {i + 1} 个 SLIDE 终点越界。")
            if n.get("q") == n.get("p"):
                problems.append(f"第 {i + 1} 个 SLIDE 起点终点相同。")
        if n["k"] in ("hold", "thold", "slide") and (n.get("d") or 0) <= 0:
            problems.append(f"第 {i + 1} 个 {n['k']} 没有时长。")
    # 同位置重叠
    by_pos: dict[int, list[dict]] = {}
    for n in notes:
        if n["k"] in ("tap", "hold", "slide"):
            by_pos.setdefault(n["p"], []).append(n)
    for p, arr in by_pos.items():
        for a, b in zip(arr, arr[1:]):
            gap = b["t"] - a["t"] - (a.get("d") if a["k"] == "hold" else 0.0)
            if gap < 30.0:
                problems.append(
                    f"位置 {p + 1} 上 {a['t']:.0f}ms 与 {b['t']:.0f}ms 两个音符挤在一起"
                    f"（间隔 {gap:.0f}ms，人手打不了）。")
    # 密度
    dur = max(1.0, float(chart.get("duration") or 1.0))
    nps = len(notes) / dur
    if nps > 22:
        problems.append(f"平均 {nps:.1f} 音符/秒，比任何真实谱面都密，多半是时值没设对。")
    seen = set()
    uniq = []
    for x in problems:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq[:12]


def normalize(chart: dict) -> dict:
    """补齐字段、排序、算统计 —— 导入的谱面过一遍再用。"""
    notes = sorted(chart.get("notes") or [], key=lambda n: (n["t"], n.get("p", 0)))
    for n in notes:
        n.setdefault("star", 0)
        n.setdefault("p", 0)
        if n["k"] == "slide":
            n.setdefault("q", (n["p"] + 2) % 8)
            n.setdefault("s", "line")
            n.setdefault("d", 300.0)
        if n["k"] in ("hold", "thold"):
            n.setdefault("d", 300.0)
    chart["notes"] = notes
    counts: dict[str, int] = {}
    for n in notes:
        counts[n["k"]] = counts.get(n["k"], 0) + 1
    chart["counts"] = counts
    last = notes[-1]
    end = last["t"] + (last.get("d") or 0.0)
    chart["duration"] = round(max(6.0, end / 1000.0 + 3.0), 2)
    chart.setdefault("title", "导入谱面")
    chart.setdefault("artist", "")
    chart.setdefault("diff", "MASTER")
    chart.setdefault("bpm", 120.0)
    chart.setdefault("offset", 0.0)
    chart.setdefault("ds", 0.0)
    return chart


def examples() -> dict[str, str]:
    """给导入框用的示例谱面（点一下就能打）。"""
    return {
        "简单 8 分连打（BPM 150）": (
            "&bpm=150\n&offset=0\n&title=8分连打练习\n\n"
            "#MASTER\n(150)1[2:16],2[2:16],3[2:16],4[2:16],"
            "5[2:16],6[2:16],7[2:16],8[2:16],"
            "1[2:16],3[2:16],5[2:16],7[2:16],"
            "2[2:16],4[2:16],6[2:16],8[2:16],"
        ),
        "滑动星星 + SLIDE（BPM 160）": (
            "&bpm=160\n&offset=0\n&title=滑动星星练习\n\n"
            "#MASTER\n(160)1^3,2b^4,5^7,6b^8,"
            "1-5,3-7,2bv6,4bw8,"
            "1[4:16],2[4:16],3[4:16],4[4:16],"
            "1h[8:16],5[8:16],6[8:16],7[8:16],"
        ),
        "TOUCH / EX（BPM 155）": (
            "&bpm=155\n&offset=0\n&title=中央屏练习\n\n"
            "#MASTER\n(155)A1[4:16],B3[4:16],C[4:16],E1[4:16],"
            "A5[4:16],B7[4:16],C[4:16],E5[4:16],"
            "1[4:16],A2[4:16],3[4:16],B6[4:16],"
            "5[4:16],C[4:16],7[4:16],E3[4:16],"
        ),
    }
