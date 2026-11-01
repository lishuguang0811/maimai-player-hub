# -*- coding: utf-8 -*-
"""
dan.py —— 段位认定（段位認定）

照着机台上那套「段位认定」做的：想升段，得先过两关。
  实技：交一枚街机厅模拟器打出来的成绩码，曲目定数和达成率都要够线；
  笔试：定数竞猜 / BPM 速猜 / 定数比大小，题目全部出自本地曲库快照。

两关都过才发证，段位只升不降，记录落在 data/dan.json（按账号隔离）。
为什么坚持要成绩码而不是手填：手填谁都能编，段位就没意义了。
"""
from __future__ import annotations

import json
from datetime import datetime

import config
from modules import minigames

DAN_FILE = config.DATA_DIR / "dan.json"

# 段位表：达成率线 / 曲目定数区间 / 笔试线 / 笔试题数
DANS = [
    {"name": "初段", "en": "1st DAN",  "need": 85.0, "ds": (3.0, 7.0),  "written": 40, "n": 6, "color": "#7FB069"},
    {"name": "二段", "en": "2nd DAN",  "need": 88.0, "ds": (4.0, 8.0),  "written": 45, "n": 6, "color": "#5FA8A0"},
    {"name": "三段", "en": "3rd DAN",  "need": 90.0, "ds": (5.0, 9.0),  "written": 50, "n": 7, "color": "#4E93C7"},
    {"name": "四段", "en": "4th DAN",  "need": 92.0, "ds": (6.0, 10.0), "written": 55, "n": 7, "color": "#7B6BD6"},
    {"name": "五段", "en": "5th DAN",  "need": 94.0, "ds": (7.0, 11.0), "written": 60, "n": 8, "color": "#A66BFF"},
    {"name": "六段", "en": "6th DAN",  "need": 95.0, "ds": (8.0, 12.0), "written": 64, "n": 8, "color": "#D264D2"},
    {"name": "七段", "en": "7th DAN",  "need": 96.0, "ds": (9.0, 13.0), "written": 68, "n": 9, "color": "#E5484D"},
    {"name": "八段", "en": "8th DAN",  "need": 97.0, "ds": (10.0, 13.5),"written": 72, "n": 9, "color": "#F2673F"},
    {"name": "九段", "en": "9th DAN",  "need": 98.0, "ds": (11.0, 14.0),"written": 76, "n": 10, "color": "#F5D442"},
    {"name": "十段", "en": "10th DAN", "need": 99.0, "ds": (12.0, 14.5),"written": 80, "n": 10, "color": "#FFB800"},
    {"name": "皆伝", "en": "ALL CLEAR","need": 100.0, "ds": (13.0, 15.0),"written": 86, "n": 12, "color": "#FFFFFF"},
]


def index_of(name: str) -> int:
    for i, d in enumerate(DANS):
        if d["name"] == name:
            return i
    return -1


def next_dan(name: str) -> dict | None:
    i = index_of(name)
    if i < 0:
        return DANS[0]
    return DANS[i + 1] if i + 1 < len(DANS) else None


# ---------------------------------------------------------------- 存档
def _key(user: str) -> str:
    return (user or "").strip().replace(" ", "").lower()


def _load() -> dict:
    if DAN_FILE.exists():
        try:
            d = json.loads(DAN_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                               # noqa: BLE001
            return {}
    return {}


def _save(d: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    DAN_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def get(user: str) -> dict:
    b = _load().get(_key(user))
    if isinstance(b, dict) and b.get("dan"):
        return b
    return {"dan": "", "at": "", "history": []}


def award(user: str, dan_name: str, detail: dict) -> bool:
    """发证。只升不降：已有更高段位时不覆盖。"""
    if index_of(dan_name) < 0:
        return False
    d = _load()
    k = _key(user)
    b = d.get(k) or {"dan": "", "at": "", "history": []}
    b.setdefault("history", [])
    if index_of(b.get("dan", "")) >= index_of(dan_name):
        return False
    b["dan"] = dan_name
    b["at"] = datetime.now().isoformat(timespec="seconds")
    b["history"].append({"dan": dan_name, "at": b["at"], **detail})
    b["history"] = b["history"][-50:]
    d[k] = b
    _save(d)
    return True


def all_ranks() -> dict[str, str]:
    """返回 {账号: 段位名}，用于排行榜。"""
    return {k: (v or {}).get("dan", "") for k, v in _load().items() if (v or {}).get("dan")}


# ---------------------------------------------------------------- 出题
def make_exam(dan: dict, records: list[dict], seed: str) -> list[dict]:
    """按段位生成一套笔试题：定数竞猜 / BPM 速猜 / 定数比大小轮流来。"""
    if not records:
        return []
    n = int(dan.get("n", 6))
    out = []
    kinds = ["ds", "bpm", "duel"]
    for i in range(n):
        k = kinds[i % 3]
        s = f"{seed}-{i}"
        if k == "ds":
            q = minigames.ds_round(records, s, hard=(i % 3 == 2))
        elif k == "bpm":
            q = minigames.bpm_round(records, s)
        else:
            q = minigames.ds_duel(records, s)
        if q:
            q["kind"] = k
            out.append(q)
    return out


def grade_exam(exam: list[dict], answers: dict) -> dict:
    """answers: {index: 用户答案}。返回每题得分与总分。"""
    rows, scores = [], []
    for i, q in enumerate(exam):
        ans = answers.get(i)
        k = q.get("kind")
        if ans is None:
            rows.append({"i": i, "kind": k, "score": 0, "text": "未作答"})
            scores.append(0.0)
            continue
        if k == "ds":
            r = minigames.ds_judge(float(ans), q["ds"])
            scores.append(float(r["score"]))
            rows.append({"i": i, "kind": "定数竞猜", "score": r["score"],
                         "text": f"《{q['title']}》 真实 {q['ds']} · 你差 {r['err']} · {r['judge']}"})
        elif k == "bpm":
            r = minigames.bpm_judge(float(ans), q["bpm"])
            scores.append(float(r["score"]))
            rows.append({"i": i, "kind": "BPM 速猜", "score": r["score"],
                         "text": f"《{q['title']}》 真实 {q['bpm']} · {r.get('judge', '')}"})
        else:
            ok = minigames.duel_judge(q, str(ans))
            scores.append(100.0 if ok else 0.0)
            rows.append({"i": i, "kind": "定数比大小", "score": 100 if ok else 0,
                         "text": ("《%s》%s vs 《%s》%s" % (q["a"]["title"], q["a"]["ds"],
                                                          q["b"]["title"], q["b"]["ds"]))
                                 + (" · 答对" if ok else " · 答错")})
    total = round(sum(scores) / max(1, len(scores)), 1)
    return {"rows": rows, "total": total}


def grade_practical(dan: dict, play: dict | None) -> dict:
    """实技判定：成绩码里的曲目定数要落在区间内，达成率要够线。"""
    if not play:
        return {"ok": False, "msg": "还没有交成绩码，先去街机厅模拟器打一局。"}
    ach = play.get("ach")
    ds = play.get("ds")
    lo, hi = dan.get("ds", (0, 99))
    try:
        ach = float(ach); ds = float(ds or 0)
    except (TypeError, ValueError):
        return {"ok": False, "msg": "成绩码里的数字读不出来，重新打一局吧。"}
    need = float(dan["need"])
    note = ""
    if ds < lo:
        need += 1.0
        note = f"曲目定数 {ds:g} 低于本段下限 {lo:g}，达成率要求 +1%（现在是 {need:.0f}%）。"
    elif ds > hi:
        note = f"曲目定数 {ds:g} 高于本段上限 {hi:g} —— 超纲不算，但也不拦你。"
    ok = ach >= need
    return {"ok": ok, "msg": ("达成率 %.2f%% ≥ 要求 %.0f%%，实技通过。" % (ach, need)) if ok
                      else ("达成率 %.2f%%，差 %.2f 个百分点。" % (ach, need - ach)),
            "ach": ach, "ds": ds, "need": need, "note": note,
            "title": play.get("t", ""), "diff": play.get("df", ""), "rank": play.get("rk", "")}


# ---------------------------------------------------------------- 段位牌
def badge_html(dan_name: str, user: str = "", size: int = 132) -> str:
    i = index_of(dan_name)
    d = DANS[i] if i >= 0 else {"name": "无段位", "en": "NO DAN", "color": "#5b6b73"}
    c = d["color"]
    return (
        f"<div style='width:{size}px;text-align:center;display:inline-block;margin:6px'>"
        f"<div style='width:{size}px;height:{size}px;border-radius:50%;"
        f"background:radial-gradient(circle at 35% 28%,{c}33,#0b1017 72%);"
        f"border:3px solid {c};box-shadow:0 0 22px {c}55;display:flex;"
        f"flex-direction:column;align-items:center;justify-content:center'>"
        f"<div style='font-size:{size//4}px;font-weight:900;color:{c};letter-spacing:2px;"
        f"line-height:1.05'>{d['name']}</div>"
        f"<div style='font-size:{size//13}px;color:#8fa3ab;letter-spacing:1px'>{d['en']}</div>"
        f"</div>"
        + (f"<div style='font-size:11px;color:#7f8f96;margin-top:5px'>{user}</div>" if user else "")
        + "</div>")


def ladder_html(current: str) -> str:
    cur = index_of(current)
    cells = []
    for i, d in enumerate(DANS):
        got = i <= cur
        c = d["color"]
        op = "1" if got else "0.22"
        cells.append(
            f"<div style='flex:1;min-width:52px;padding:7px 2px;border-radius:10px;text-align:center;"
            f"background:{'rgba(255,255,255,.07)' if got else 'rgba(255,255,255,.02)'};"
            f"border:1px solid {c}55;opacity:{op}'>"
            f"<div style='font-size:12px;font-weight:800;color:{c}'>{d['name']}</div>"
            f"<div style='font-size:9px;color:#7f8f96'>{d['need']:.0f}%</div></div>")
    return "<div style='display:flex;gap:4px;flex-wrap:wrap'>" + "".join(cells) + "</div>"
