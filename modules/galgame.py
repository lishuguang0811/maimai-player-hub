# -*- coding: utf-8 -*-
"""
galgame.py —— 《SECRET ARCHIVE》视觉小说引擎

剧情数据在 data/story.json（与 UI 分离），成就/结局在 data/achievements.json，
最终信件在 data/letter.md。玩家进度/存档/成就/结局按账号隔离存 data/galgame_saves.json。

引擎职责：节点推进、选择分支、flag 累加、成就/结局解锁（含派生成就）、
多存档槽、跳过已读、对话历史。不含任何 UI。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config

STORY_FILE = config.DATA_DIR / "story.json"
META_FILE = config.DATA_DIR / "achievements.json"
SAVES_FILE = config.DATA_DIR / "galgame_saves.json"
LETTER_FILE = config.DATA_DIR / "letter.md"
BIRTHDAY_ANSWER = (f"{config.OWNER_BIRTH_YEAR:04d}-"
                   f"{config.OWNER_BIRTHDAY[0]:02d}-{config.OWNER_BIRTHDAY[1]:02d}")


def _norm(user):
    return (user or "").strip().replace(" ", "").lower()


def load_story() -> dict:
    return json.loads(STORY_FILE.read_text(encoding="utf-8"))


def load_meta() -> dict:
    return json.loads(META_FILE.read_text(encoding="utf-8"))


def load_letter() -> str:
    return LETTER_FILE.read_text(encoding="utf-8") if LETTER_FILE.exists() else ""


def _load_saves() -> dict:
    if SAVES_FILE.exists():
        try:
            d = json.loads(SAVES_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                    # noqa: BLE001
            return {}
    return {}


def _save_saves(d):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAVES_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def state(user) -> dict:
    d = _load_saves(); k = _norm(user)
    if k not in d:
        d[k] = {"node": None, "flags": {}, "read": [], "history": [],
                "achievements": {}, "endings": {}, "slots": {}}
        _save_saves(d)
    s = d[k]
    for f in ("flags", "read", "history", "achievements", "endings", "slots"):
        s.setdefault(f, {} if f in ("flags", "achievements", "endings", "slots") else [])
    return s


def _persist(user):
    _save_saves(_load_saves())   # state() 已写回内存对象引用，统一落盘
    # 上面 state() 修改的是 _load_saves() 返回的新 dict，需重新合并落盘：
    # 为简单起见，所有修改函数末尾显式调用 _write(user)


def _write(user):
    _save_saves(_load_saves())


def nodes():
    return load_story()["nodes"]


def start(user):
    s = state(user); s["node"] = load_story()["start"]
    d = _load_saves(); d[_norm(user)] = s; _save_saves(d)
    return current(user)


def current(user):
    s = state(user); nid = s.get("node")
    return nodes().get(nid) if nid else None


def is_read(user, nid):
    return nid in state(user)["read"]


def unlock_achievement(user, ach_id):
    """解锁成就（含派生检查）。返回是否新解锁。"""
    d = _load_saves(); s = d[_norm(user)]
    meta = {a["id"]: a for a in load_meta()["achievements"]}
    newly = []
    if ach_id and ach_id not in s["achievements"]:
        s["achievements"][ach_id] = datetime.now().isoformat(timespec="seconds")
        newly.append(ach_id)
    # 派生：嘴硬鉴定师
    if s["flags"].get("tsundere", 0) >= 3 and "嘴硬鉴定师" not in s["achievements"]:
        s["achievements"]["嘴硬鉴定师"] = datetime.now().isoformat(timespec="seconds")
        newly.append("嘴硬鉴定师")
    # 派生：平行世界旅行者 / 故事收藏家
    all_end = [e["id"] for e in load_meta()["endings"]]
    if len(s["endings"]) >= 3 and "平行世界旅行者" not in s["achievements"]:
        s["achievements"]["平行世界旅行者"] = datetime.now().isoformat(timespec="seconds")
        newly.append("平行世界旅行者")
    if all(e in s["endings"] for e in all_end) and all_end and "故事收藏家" not in s["achievements"]:
        s["achievements"]["故事收藏家"] = datetime.now().isoformat(timespec="seconds")
        newly.append("故事收藏家")
    _save_saves(d)
    return newly


def unlock_ending(user, ending_id):
    d = _load_saves(); s = d[_norm(user)]
    newly_end = []
    if ending_id and ending_id not in s["endings"]:
        s["endings"][ending_id] = datetime.now().isoformat(timespec="seconds")
        newly_end.append(ending_id)
    _save_saves(d)
    newly_ach = unlock_achievement(user, None)   # 触发派生成就检查
    return newly_end, newly_ach


def go(user, nid):
    d = _load_saves(); s = d[_norm(user)]
    s["node"] = nid
    n = nodes().get(nid, {})
    if nid and nid not in s["read"]:
        s["read"].append(nid)
    if n:
        s["history"].append({"speaker": n.get("speaker", ""), "text": n.get("text", "")})
        s["history"] = s["history"][-200:]
    _save_saves(d)
    newly = []
    if n.get("ach"):
        newly += unlock_achievement(user, n["ach"])
    if n.get("ending"):
        _, na = unlock_ending(user, n["ending"]); newly += na
    return n, newly


def choose(user, index):
    n = current(user)
    if not n or n.get("kind") != "choice":
        return None, []
    chs = n.get("choices", [])
    if not (0 <= index < len(chs)):
        return None, []
    ch = chs[index]
    d = _load_saves(); s = d[_norm(user)]
    if ch.get("flag"):
        for k, v in ch["flag"].items():
            s["flags"][k] = s["flags"].get(k, 0) + v
    _save_saves(d)
    newly = []
    newly += unlock_achievement(user, ch.get("ach"))  # 每次跑派生检查
    if ch.get("ending"):
        _, na = unlock_ending(user, ch["ending"]); newly += na
    node, ng = go(user, ch["next"])
    return node, newly + ng


def check_birthday(user, answer):
    """序章生日校验：正确 -> 进入 p3；错误 -> p2r。返回 (node, newly, ok)。"""
    ok = (answer or "").strip() == BIRTHDAY_ANSWER
    node, newly = go(user, "p3" if ok else "p2r")
    return node, newly, ok


def skip_read(user):
    """沿 next 链跳过已读节点，停在第一个未读/选择/信件/生日节点。"""
    n = current(user); guard = 0
    while n and guard < 500:
        guard += 1
        if n.get("kind") in ("choice", "letter", "birthday"):
            break
        nxt = n.get("next")
        if not nxt or not is_read(user, nxt):
            if nxt:
                n, _ = go(user, nxt)
            break
        n, _ = go(user, nxt)
    return n


def save_slot(user, slot):
    d = _load_saves(); s = d[_norm(user)]
    s["slots"][str(slot)] = {"node": s.get("node"), "at": datetime.now().isoformat(timespec="seconds")}
    _save_saves(d)


def load_slot(user, slot):
    d = _load_saves(); s = d[_norm(user)]
    rec = s["slots"].get(str(slot))
    if not rec or not rec.get("node"):
        return None
    s["node"] = rec["node"]; _save_saves(d)
    return current(user)


def achievements_view(user):
    s = state(user); meta = load_meta()["achievements"]
    return [{"id": a["id"], "desc": a["desc"], "rarity": a["rarity"],
             "unlocked": s["achievements"].get(a["id"])} for a in meta]


def endings_view(user):
    s = state(user); meta = load_meta()["endings"]
    return [{"id": e["id"], "title": e["title"], "rarity": e["rarity"],
             "unlocked": s["endings"].get(e["id"])} for e in meta]


def history(user, limit=50):
    return state(user)["history"][-limit:]


def progress(user):
    s = state(user)
    return {"read": len(s["read"]), "total": len(nodes()),
            "ach": len(s["achievements"]), "endings": len(s["endings"])}