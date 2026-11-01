# -*- coding: utf-8 -*-
"""
songs.py —— 曲库数据层

职责只有三件事：
1) 联网抓一次真实曲库，落地成本地 JSON 快照（带抓取时间）
2) 读快照（没网也能跑）
3) 把"一首歌 4~5 个难度"的原始结构，压平成"一行一个谱面"，方便筛选

初学者提示：这里的 records 每条形如
  {"title": "...", "artist": "...", "genre": "...", "bpm": 200,
   "diff": "Master", "level": "13", "ds": 13.7, "song_id": "11064"}
原始接口里 ds 是一个数组，下标 0~4 分别对应 Basic/Advanced/Expert/Master/Re:MASTER，
压平之后我们就能直接用 ds 数值区间来选难度，不用每次都去数下标。
"""
from __future__ import annotations

import json
from urllib.parse import quote
from datetime import datetime, timezone
from pathlib import Path

import requests

import config


def _now_text() -> str:
    """当前时间字符串（带时区），用于记录快照抓取时间。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def refresh_songs(timeout: int = 25) -> dict:
    """
    联网抓取真实曲库并写入本地快照。
    成功返回 {"ok": True, "count": n, "fetched_at": "..."}
    失败返回 {"ok": False, "error": "..."}，不抛异常（保证界面不崩）。
    """
    try:
        resp = requests.get(config.SONGS_API, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json()
        if not isinstance(raw, list) or not raw:
            return {"ok": False, "error": "接口返回内容格式异常（不是曲目列表）"}
        snapshot = {"fetched_at": _now_text(), "count": len(raw), "songs": raw}
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Path(config.SONGS_CACHE).write_text(
            json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
        )
        return {"ok": True, "count": len(raw), "fetched_at": snapshot["fetched_at"]}
    except Exception as exc:            # noqa: BLE001 —— 入门项目里统一兜底更好懂
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def load_snapshot() -> dict | None:
    """读本地快照。文件不存在或损坏时返回 None。"""
    path = Path(config.SONGS_CACHE)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("songs"), list):
            return data
    except Exception:                    # noqa: BLE001
        return None
    return None


def snapshot_age_days(snapshot: dict) -> int | None:
    """快照已经多少天了（用于提示"建议刷新"）。"""
    try:
        fetched = datetime.fromisoformat(snapshot["fetched_at"])
        return max(0, (datetime.now(timezone.utc).astimezone() - fetched).days)
    except Exception:                    # noqa: BLE001
        return None


def flatten(snapshot: dict) -> list[dict]:
    """
    把快照压平成"一行一个谱面"的记录列表。
    同一首歌的不同版本（比如普通版和 Re:MASTER 单独条目）会各占一行，
    最后按 (曲名, 难度) 去重，只保留定数更高的那条。
    """
    best: dict[tuple, dict] = {}
    for song in snapshot.get("songs", []):
        info = song.get("basic_info") or {}
        genre = (info.get("genre") or "").strip()
        if genre == "宴会場":            # 宴会场是娱乐谱，不参与正经推荐
            continue
        title = (song.get("title") or info.get("title") or "").strip()
        if not title:
            continue
        ds_list = song.get("ds") or []
        level_list = song.get("level") or []
        for idx, ds in enumerate(ds_list):
            if idx >= len(config.DIFF_ORDER):
                break
            try:
                ds_val = float(ds)
            except (TypeError, ValueError):
                continue
            if ds_val <= 0:              # 0 表示该难度没有谱面
                continue
            rec = {
                "song_id": str(song.get("id", "")),
                "title": title,
                "artist": (info.get("artist") or "").strip(),
                "genre": genre,
                "bpm": info.get("bpm"),
                "diff": config.DIFF_ORDER[idx],
                "level": str(level_list[idx]) if idx < len(level_list) else "",
                "ds": ds_val,
                "from": (info.get("from") or "").strip(),
                "is_new": bool(info.get("is_new")),
            }
            key = (title, rec["diff"])
            if key not in best or rec["ds"] > best[key]["ds"]:
                best[key] = rec
    return list(best.values())


def is_miku_related(rec: dict) -> bool:
    """是否是初音未来 / 世界计划相关（只看艺术家字段里的真实信息）。"""
    artist = rec.get("artist", "")
    return any(k in artist for k in config.MIKU_KEYWORDS)


def candidates_for_tier(records: list[dict], tier: dict) -> list[dict]:
    """按档位定数区间筛出候选谱面。"""
    lo, hi = tier["ds_min"], tier["ds_max"]
    # 允许一个档位匹配多种难度（如挑战档同时看 Master 和 Re:MASTER）
    want_diffs = tier.get("diffs") or [config.DIFF_ORDER[tier.get("diff_index", 3)]]
    pool = [
        r for r in records
        if r["diff"] in want_diffs and lo <= r["ds"] <= hi
    ]
    # 同曲名只留一条，避免"三首推荐其实是同一首歌的不同版本"
    seen, out = set(), []
    for r in sorted(pool, key=lambda x: (x["title"], -x["ds"])):
        if r["title"] in seen:
            continue
        seen.add(r["title"])
        out.append(r)
    return out


def song_select_view(records: list[dict]) -> list[dict]:
    """
    1:1 风格选曲页用的数据：每首歌聚合全部 5 个难度的 等级+定数，
    按最高定数降序。返回结构：
      {"title","artist","genre","bpm","is_miku","max_ds",
       "diffs":{"Basic":{"level","ds"}, ...}}
    """
    by: dict[str, dict] = {}
    for r in records:
        title = r["title"]
        if title not in by:
            by[title] = {
                "title": title, "artist": r.get("artist", ""),
                "genre": r.get("genre", ""), "bpm": r.get("bpm"),
                "diffs": {},
            }
        by[title]["diffs"][r["diff"]] = {"level": r.get("level", ""), "ds": r["ds"]}
    out = []
    for v in by.values():
        v["max_ds"] = max(d["ds"] for d in v["diffs"].values())
        v["is_miku"] = is_miku_related(v)
        out.append(v)
    out.sort(key=lambda x: (-x["max_ds"], x["title"]))
    return out


def bilibili_link(title: str) -> str:
    """
    生成 B 站搜索链接，直达该曲的 maimai 谱面确认视频搜索结果。
    不伪造具体视频地址（无法逐一核实），搜索链接真实可用、方便读谱。
    """
    kw = config.VIDEO_KEYWORD_TPL.format(title=title)
    return config.BILIBILI_SEARCH.format(kw=quote(kw))
