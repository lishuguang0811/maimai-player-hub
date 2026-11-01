# -*- coding: utf-8 -*-
"""
playlog.py —— 游玩记录：成绩码回传 / 存档 / 打卡 / 能力统计

iframe 里跑的小游戏拿不到 Streamlit 的 session，Python 侧读不到它们的分数。
所以让游戏在结算时生成一枚「成绩码」（base64 + 5 位校验），用户粘回主界面，
这局成绩就落进自己的账号 —— 这是目前唯一可靠、且不依赖任何网络的回传通道。

数据全部落在 data/playlog.json，按规范化账号名分桶，用户之间互相看不见。
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, date, timedelta
from pathlib import Path

import config

LOG_FILE = config.DATA_DIR / "playlog.json"
PREFIX = "MM1"
MAX_KEEP = 200            # 每人最多保留的游玩记录条数

# 各游戏归属的「能力维度」，用于玩家档案的雷达图
DIM_OF_GAME = {
    "cabinet": "节奏", "dx": "节奏", "rhythm": "节奏", "offset": "节奏", "steady": "节奏",
    "tap": "反应", "stamina": "反应",
    "simon": "记忆", "memory": "记忆", "recall": "记忆",
    "dsquiz": "知识", "bpmquiz": "知识", "duel": "知识", "type": "知识", "bingo": "知识",
    "score": "读谱", "merge": "策略", "drop": "策略", "snake": "策略",
    "puzzle": "耐心", "ambient": "耐心", "fortune": "运气",
}
DIMS = ["节奏", "反应", "记忆", "知识", "读谱", "策略"]


# ---------------------------------------------------------------- 成绩码
def _crc(s: str) -> str:
    """与前端 JS 完全一致的 5 位 base36 校验（djb2 变体）。"""
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while h:
        out = digits[h % 36] + out
        h //= 36
    return (out or "0")[:5]


def encode(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return f"{PREFIX}:{b64}:{_crc(b64)}"


def decode(code: str) -> tuple[bool, dict | str]:
    """解析成绩码。返回 (是否成功, payload 或错误信息)。"""
    if not code or not isinstance(code, str):
        return False, "成绩码是空的。"
    code = code.strip().replace(" ", "").replace("\n", "")
    parts = code.split(":")
    if len(parts) != 3 or parts[0] != PREFIX:
        return False, "这看起来不是本机的成绩码（应以 MM1: 开头）。"
    _, b64, chk = parts
    if _crc(b64) != chk:
        return False, "校验位对不上，成绩码可能被截断或改动过，请重新复制完整。"
    try:
        data = json.loads(base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8"))
    except Exception:                                   # noqa: BLE001
        return False, "成绩码解不开，请重新复制一次。"
    if not isinstance(data, dict) or "g" not in data:
        return False, "成绩码内容不完整。"
    if "ach" in data:
        try:
            a = float(data["ach"])
        except (TypeError, ValueError):
            return False, "成绩码里的达成率读不出来。"
        if not (0 <= a <= 101):
            return False, "达成率超出合理范围（0~101）。"
    return True, data


# ---------------------------------------------------------------- 存档
def _key(user: str) -> str:
    return (user or "").strip().replace(" ", "").lower()


def _load() -> dict:
    if LOG_FILE.exists():
        try:
            d = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                               # noqa: BLE001
            return {}
    return {}


def _save(d: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def submit(user: str, code: str) -> tuple[bool, str]:
    ok, payload = decode(code)
    if not ok:
        return False, str(payload)
    d = _load()
    k = _key(user)
    b = d.setdefault(k, {"plays": [], "checkin": []})
    b.setdefault("plays", [])
    rec = dict(payload)
    rec["at"] = datetime.now().isoformat(timespec="seconds")
    rec["day"] = date.today().isoformat()
    b["plays"].append(rec)
    b["plays"] = b["plays"][-MAX_KEEP:]
    d[k] = b
    _save(d)
    title = rec.get("t") or "本局"
    ach = rec.get("ach")
    extra = f"，达成率 {ach:.2f}%" if isinstance(ach, (int, float)) else ""
    return True, f"已记录：{title}（{rec.get('rk', '')}）{extra}。"


def list_plays(user: str, game: str | None = None, limit: int = 60) -> list[dict]:
    b = _load().get(_key(user), {})
    items = b.get("plays", [])
    if game:
        items = [p for p in items if p.get("g") == game]
    return items[-limit:][::-1]


def best_of(user: str, game: str) -> dict | None:
    """取某个游戏的最佳一局（有达成率看达成率，否则看分数）。"""
    items = [p for p in _load().get(_key(user), {}).get("plays", []) if p.get("g") == game]
    if not items:
        return None
    def _k(p):
        v = p.get("ach")
        if isinstance(v, (int, float)):
            return v
        v = p.get("sc") or p.get("score") or 0
        return float(v) / 100000.0
    return max(items, key=_k)


def best_map(user: str) -> dict[str, dict]:
    b = _load().get(_key(user), {}).get("plays", [])
    out: dict[str, dict] = {}
    for p in b:
        g = p.get("g")
        if not g:
            continue
        cur = out.get(g)
        if cur is None or _better(p, cur):
            out[g] = p
    return out


def _better(a: dict, b: dict) -> bool:
    ka = a.get("ach") if isinstance(a.get("ach"), (int, float)) else (a.get("sc") or 0) / 1e5
    kb = b.get("ach") if isinstance(b.get("ach"), (int, float)) else (b.get("sc") or 0) / 1e5
    return ka > kb


def dimension_scores(user: str) -> dict[str, float]:
    """把各游戏最佳成绩折算成 0~100 的能力值，供雷达图用。"""
    bm = best_map(user)
    out: dict[str, list[float]] = {}
    for g, p in bm.items():
        dim = DIM_OF_GAME.get(g)
        if not dim:
            continue
        v = p.get("ach")
        if isinstance(v, (int, float)):
            val = max(0.0, min(100.0, (v - 70) / 30 * 100))     # 70%→0 分，100%→100 分
        else:
            sc = p.get("sc") or p.get("score") or 0
            val = max(0.0, min(100.0, float(sc) / 3000))
        out.setdefault(dim, []).append(val)
    return {d: round(sum(v) / len(v), 1) for d, v in out.items()}


def total_plays(user: str) -> int:
    return len(_load().get(_key(user), {}).get("plays", []))


# ---------------------------------------------------------------- 每日打卡
def checkin(user: str, note: str = "") -> tuple[bool, str, int]:
    d = _load()
    k = _key(user)
    b = d.setdefault(k, {"plays": [], "checkin": []})
    b.setdefault("checkin", [])
    today = date.today().isoformat()
    if any(c.get("day") == today for c in b["checkin"]):
        return False, "今天已经打过卡了，明天再来。", streak(user)
    b["checkin"].append({"day": today, "note": note,
                         "at": datetime.now().isoformat(timespec="seconds")})
    b["checkin"] = b["checkin"][-400:]
    d[k] = b
    _save(d)
    return True, "打卡成功。", streak(user)


def streak(user: str) -> int:
    days = {c.get("day") for c in _load().get(_key(user), {}).get("checkin", []) if c.get("day")}
    n = 0
    cur = date.today()
    if cur.isoformat() not in days:
        cur -= timedelta(days=1)
    while cur.isoformat() in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def checked_today(user: str) -> bool:
    today = date.today().isoformat()
    return any(c.get("day") == today
               for c in _load().get(_key(user), {}).get("checkin", []))


def clear(user: str) -> None:
    d = _load()
    if _key(user) in d:
        del d[_key(user)]
        _save(d)
