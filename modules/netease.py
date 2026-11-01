# -*- coding: utf-8 -*-
"""
netease.py —— 网易云音乐「能不能听」的校对结果读取层

数据来自 work/verify_netease.py：拿曲库曲名去网易云公开搜索接口查过一遍，
只有确认搜得到、且曲名/艺人对得上的才记下来。本模块只负责读，不发请求。

三种状态，界面据此决定给不给链接（宁缺勿假）：
  found     → 给直达链接 https://music.163.com/#/song?id=xxx
  weak      → 有同名曲但不敢确定，只给搜索入口，不给直达
  not_found → 网易云确实搜不到，不放网易云链接
"""
from __future__ import annotations

import json
from datetime import datetime

import config

MAP_FILE = config.DATA_DIR / "netease_map.json"
SONG_URL = "https://music.163.com/#/song?id={id}"
SEARCH_URL = "https://music.163.com/#/search/m/?s={q}"


def _load() -> dict:
    if not MAP_FILE.exists():
        return {"items": {}, "checked_at": None, "total": 0, "found": 0}
    try:
        data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"items": {}}
    except Exception:                            # noqa: BLE001
        return {"items": {}, "checked_at": None, "total": 0, "found": 0}


def items() -> dict:
    """整张校对表（界面请缓存后用，别每次都读盘）。"""
    return _load().get("items") or {}


def lookup(title: str) -> dict | None:
    """返回该曲的校对结果；没校对过返回 None（不是"搜不到"）。"""
    return items().get((title or "").strip())


def song_url(song_id) -> str:
    return SONG_URL.format(id=song_id)


def search_url(query: str, artist: str = "") -> str:
    from urllib.parse import quote
    kw = f"{query} {artist}" if artist and artist not in ("未知", "") else query
    return SEARCH_URL.format(q=quote((kw or "").strip()))


def status_of(title: str) -> str:
    """found / weak / not_found / unchecked"""
    r = lookup(title)
    if not r:
        return "unchecked"
    return r.get("status", "not_found")


def playable(title: str) -> bool:
    return status_of(title) == "found"


def stats() -> dict:
    d = _load()
    items = d.get("items") or {}
    found = sum(1 for v in items.values() if v.get("status") == "found")
    weak = sum(1 for v in items.values() if v.get("status") == "weak")
    none = sum(1 for v in items.values() if v.get("status") == "not_found")
    checked_at = d.get("checked_at")
    days = None
    if checked_at:
        try:
            days = (datetime.now() - datetime.fromisoformat(checked_at)).days
        except Exception:                        # noqa: BLE001
            days = None
    return {"total": len(items), "found": found, "weak": weak, "not_found": none,
            "checked_at": checked_at, "age_days": days}
