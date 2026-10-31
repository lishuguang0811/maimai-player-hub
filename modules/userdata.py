# -*- coding: utf-8 -*-
"""
userdata.py —— 每用户私有数据：收藏 / 练习清单 / 手动成绩 / 最近推荐

数据存 data/userdata.json，按"规范化账号名"分桶，**用户之间完全隔离**：
每个函数只读写自己那一份桶，A 看不到也改不了 B 的收藏/成绩/练习。

成绩为"手动录入"，明确标注 source=手动录入，不伪装成舞萌官方同步数据。
练习清单区分"计划练习"和"真实成绩"，计划不会被当作实际成绩。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import config

DATA_FILE = config.DATA_DIR / "userdata.json"
PRACTICE_STATUSES = ["未开始", "进行中", "已完成"]


def _key(user: str) -> str:
    return (user or "").strip().replace(" ", "").lower()


def _load() -> dict:
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                    # noqa: BLE001
            return {}
    return {}


def _save(d: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _bucket(user: str) -> dict:
    d = _load()
    k = _key(user)
    if k not in d:
        d[k] = {"favorites": [], "practice": [], "scores": [], "recent": []}
        _save(d)
    b = d[k]
    for field in ("favorites", "practice", "scores", "recent"):
        b.setdefault(field, [])
    return b


def _next_id(items: list) -> int:
    return max([it.get("id", 0) for it in items], default=0) + 1


# ---------------- 收藏 ----------------
def is_favorite(user: str, title: str) -> bool:
    return any(f.get("title") == title for f in _bucket(user)["favorites"])


def add_favorite(user: str, song: dict) -> None:
    b = _bucket(user)
    if any(f.get("title") == song["title"] for f in b["favorites"]):
        return
    b["favorites"].append({
        "title": song["title"], "artist": song.get("artist", ""),
        "ds": song.get("ds"), "diff": song.get("diff", ""), "genre": song.get("genre", ""),
        "added": datetime.now().isoformat(timespec="seconds"),
    })
    _save(_load() | {_key(user): b})


def remove_favorite(user: str, title: str) -> bool:
    d = _load(); b = d.get(_key(user), {})
    favs = b.get("favorites", [])
    n = len(favs)
    b["favorites"] = [f for f in favs if f.get("title") != title]
    if len(b["favorites"]) != n:
        d[_key(user)] = b; _save(d); return True
    return False


def list_favorites(user: str) -> list[dict]:
    return _bucket(user)["favorites"]


# ---------------- 练习清单（计划，非真实成绩） ----------------
def add_practice(user: str, song: dict, planned_date: str = "", note: str = "") -> int:
    b = _bucket(user)
    pid = _next_id(b["practice"])
    b["practice"].append({
        "id": pid, "title": song["title"], "artist": song.get("artist", ""),
        "ds": song.get("ds"), "diff": song.get("diff", ""),
        "planned_date": planned_date or "", "status": "未开始",
        "actual_date": "", "note": note or "",
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    _save(_load() | {_key(user): b})
    return pid


def list_practice(user: str) -> list[dict]:
    return _bucket(user)["practice"]


def set_practice_status(user: str, pid: int, status: str, actual_date: str = "") -> bool:
    if status not in PRACTICE_STATUSES:
        return False
    d = _load(); b = d.get(_key(user), {})
    for it in b.get("practice", []):
        if it.get("id") == pid:
            it["status"] = status
            if status == "已完成" and actual_date:
                it["actual_date"] = actual_date
            d[_key(user)] = b; _save(d); return True
    return False


def remove_practice(user: str, pid: int) -> bool:
    d = _load(); b = d.get(_key(user), {})
    n = len(b.get("practice", []))
    b["practice"] = [it for it in b.get("practice", []) if it.get("id") != pid]
    if len(b["practice"]) != n:
        d[_key(user)] = b; _save(d); return True
    return False


# ---------------- 手动成绩（真实游玩记录，手动录入） ----------------
def add_score(user, title, diff, ds, score, achievement, fc=False, ap=False,
              note="") -> tuple[bool, str]:
    """校验后记录一条手动成绩。achievement 0~101(%)，score>=0。"""
    try:
        score = int(score); achievement = float(achievement)
    except (TypeError, ValueError):
        return False, "分数和达成率必须是数字。"
    if score < 0:
        return False, "分数不能为负。"
    if not (0 <= achievement <= 101):
        return False, "达成率应在 0~101(%) 之间。"
    b = _bucket(user)
    sid = _next_id(b["scores"])
    b["scores"].append({
        "id": sid, "title": title, "diff": diff, "ds": ds,
        "score": score, "achievement": round(achievement, 4),
        "fc": bool(fc), "ap": bool(ap), "note": note or "",
        "source": "手动录入",                       # 明确标注，非官方同步
        "date": datetime.now().isoformat(timespec="seconds"),
    })
    _save(_load() | {_key(user): b})
    return True, "成绩已记录（手动录入）。"


def list_scores(user: str) -> list[dict]:
    return _bucket(user)["scores"]


def remove_score(user: str, sid: int) -> bool:
    d = _load(); b = d.get(_key(user), {})
    n = len(b.get("scores", []))
    b["scores"] = [it for it in b.get("scores", []) if it.get("id") != sid]
    if len(b["scores"]) != n:
        d[_key(user)] = b; _save(d); return True
    return False


def stats(user: str) -> dict:
    sc = _bucket(user)["scores"]
    if not sc:
        return {"count": 0, "avg_achievement": None, "fc": 0, "ap": 0, "max_ds": None}
    ach = [s["achievement"] for s in sc]
    return {
        "count": len(sc),
        "avg_achievement": round(sum(ach) / len(ach), 2),
        "fc": sum(1 for s in sc if s.get("fc")),
        "ap": sum(1 for s in sc if s.get("ap")),
        "max_ds": max((s.get("ds") or 0) for s in sc),
    }


# ---------------- 最近推荐 ----------------
def add_recent(user: str, date_str: str, titles: list) -> None:
    b = _bucket(user)
    b["recent"].append({"date": date_str, "titles": titles,
                        "at": datetime.now().isoformat(timespec="seconds")})
    b["recent"] = b["recent"][-30:]
    _save(_load() | {_key(user): b})


def list_recent(user: str, limit: int = 7) -> list[dict]:
    return _bucket(user)["recent"][-limit:][::-1]

# ---------------- 个人偏好（主题/BGM 等，跨登录持久） ----------------
def get_pref(user: str, key: str, default=None):
    return _bucket(user).get("prefs", {}).get(key, default)


def set_pref(user: str, key: str, value) -> None:
    d = _load(); b = d.get(_key(user), {})
    b.setdefault("prefs", {})[key] = value
    d[_key(user)] = b; _save(d)