# -*- coding: utf-8 -*-
"""
recommend.py —— 今日选曲核心逻辑（按账号等级 + 爱好加权）

设计：
1) 等级 -> 三档（热身/主打/挑战），把该等级的定数区间三等分，
   每档覆盖该等级允许的全部难度色（绿黄紫红白），全分类选曲。
2) 加权偏向术力口 / 初音，再叠加"爱好加成"：账号填的爱好命中
   某分类/艺术家时额外加权，实现"按爱好筛歌"。
3) 随机种子 = 当天日期 + 档位，同一天结果固定，第二天换一批。
"""
from __future__ import annotations

import random
from datetime import date

import config
from modules import settings
from modules.songs import candidates_for_tier, is_miku_related

REASON_BY_THEME = {
    "sunny": "晴天配 {genre}，BPM {bpm} 的节奏正好顶得上今天的光照强度。",
    "cloudy": "多云天不刺眼，{bpm} BPM 的 {genre} 适合稳稳读谱。",
    "rain": "雨天场子里人少，正好安静地把这首 {genre} 的谱面细节磨一遍。",
    "snow": "下雪天碰上这首 {genre}，属于今天独有的纪念局。",
    "hot": "高温天手汗多，{bpm} BPM 别贪，先把手感稳住。",
    "cold": "冷天先暖手，这首 {genre} 的密度刚好能把状态拉起来。",
    "fog": "雾天练专注，把 {genre} 的读谱一致性打出来。",
    "offline": "今日标准配置，{genre} 里这首的谱面结构值得过一遍。",
}

TIER_REASON = {
    "warmup": "热身：{ds} 定数，先把手感叫回来，不追成绩。",
    "main": "主打：{ds} 定数，状态最好的一段留给它，可以认真冲一次。",
    "boss": "挑战：{ds} 定数，收尾冲一发，摸到就是赚到，别上头连币。",
}

TIER_LABELS = [
    ("warmup", "热身曲", "🎧"),
    ("main", "主打曲", "🎤"),
    ("boss", "挑战曲", "⚡"),
]


def tiers_for_level(level: str) -> list[dict]:
    """把等级的定数区间三等分成 热身/主打/挑战 三档，难度色用该等级允许的集合。"""
    levels = settings.get_levels()
    lv = levels.get(level, levels.get(config.DEFAULT_LEVEL, config.LEVELS[config.DEFAULT_LEVEL]))
    lo, hi = lv["ds_min"], lv["ds_max"]
    span = (hi - lo) / 3.0
    bounds = [(lo, lo + span), (lo + span, lo + 2 * span), (lo + 2 * span, hi)]
    tiers = []
    for (key, label, emoji), (a, b) in zip(TIER_LABELS, bounds):
        tiers.append({
            "key": key, "label": label, "emoji": emoji,
            "diffs": lv["diffs"],
            "ds_min": round(a, 1), "ds_max": round(b, 1),
            "desc": lv["tip"],
        })
    return tiers


def _user_weight(rec: dict, hobbies, user_fav, score_ds) -> float:
    """收藏 + 成绩定数邻近 的加成（可解释）。"""
    w = _hobby_weight(rec, hobbies)
    if user_fav and rec["title"] in user_fav:
        w += config.W_FAV
    if score_ds is not None and abs(rec["ds"] - score_ds) <= 0.6:
        w += config.W_SCORE_PROX
    return w


def _hobby_weight(rec: dict, hobbies: list[str] | None) -> float:
    """爱好加成：账号爱好命中某分类时额外加权。"""
    if not hobbies:
        return 0.0
    blob = " ".join(str(h).lower() for h in hobbies)
    extra = 0.0
    for keywords, rule in config.HOBBY_BOOST:
        if any(k.lower() in blob for k in keywords):
            genre = rule.get("genre")
            if genre and rec.get("genre") == genre:
                extra += rule.get("weight", 0.0)
            if rule.get("miku_extra") and is_miku_related(rec):
                extra += rule["miku_extra"]
    return extra


def _weight(rec: dict, hobbies=None, user_fav=None, score_ds=None) -> float:
    """总权重 = 术力口/初音基础分 + 分类微调 + 爱好 + 收藏 + 成绩邻近。"""
    w = 1.0
    if rec.get("genre") == config.VOCALOID_GENRE:
        w += config.W_VOCALOID
    if is_miku_related(rec):
        w += config.W_MIKU
    try:
        w *= config.GENRE_PRIORITY.index(rec.get("genre")) * -0.12 + 1.0
    except ValueError:
        w *= 0.9
    w += _user_weight(rec, hobbies, user_fav, score_ds)
    return max(w, 0.1)


def _pick_many(rng, pool, used, n, hobbies, user_fav=None, score_ds=None):
    out = []
    free = [r for r in pool if r["title"] not in used]
    for _ in range(n):
        if not free:
            break
        weights = [_weight(r, hobbies, user_fav, score_ds) for r in free]
        rec = rng.choices(free, weights=weights, k=1)[0]
        free.remove(rec)
        used.add(rec["title"])
        out.append(rec)
    return out


def daily_picks(records, today, theme, tiers=None, per_tier=None,
                hobbies=None, level=None, user_fav=None, user_scores=None) -> list[dict]:
    """
    返回三档推荐。tiers 不传时按 level 自动生成（默认高手）。
    结构：[{"tier":..., "songs":[{"song","reason"},...], "pool_size":n}, ...]
    """
    if tiers is None:
        tiers = tiers_for_level(level or config.DEFAULT_LEVEL)
    per_tier = per_tier or config.PICKS_PER_TIER
    seed = today.strftime("%Y-%m-%d")
    out, used = [], set()
    fav_set = set(user_fav) if user_fav else None
    score_ds = None
    if user_scores:
        ds_list = sorted(s.get("ds") for s in user_scores if s.get("ds"))
        if ds_list:
            score_ds = ds_list[len(ds_list) // 2]      # 中位定数
    for tier in tiers:
        pool = candidates_for_tier(records, tier)
        rng = random.Random(f"{seed}-{tier['key']}")
        chosen = _pick_many(rng, pool, used, per_tier, hobbies, fav_set, score_ds)
        out.append({
            "tier": tier,
            "songs": [{"song": r, "reason": _reason(r, tier, theme, fav_set, score_ds)} for r in chosen],
            "pool_size": len(pool),
        })
    return out


def _reason(rec, tier, theme, user_fav=None, score_ds=None):
    tpl_base = TIER_REASON.get(tier["key"], "{ds} 定数，今天挑了这首。")
    base = tpl_base.format(ds=f"{rec['ds']:.1f}")
    if user_fav and rec["title"] in user_fav:
        base += " 你收藏过这首。"
    if score_ds is not None and abs(rec["ds"] - score_ds) <= 0.6:
        base += f" 接近你常玩的 {score_ds:.1f} 定数。"
    tpl = REASON_BY_THEME.get(theme.get("key", "offline"), REASON_BY_THEME["offline"])
    detail = tpl.format(
        genre=rec["genre"] or "未分类",
        bpm=rec["bpm"] if rec["bpm"] not in (None, 0) else "未记录",
    )
    miku = "　★初音未来/世界计划相关" if is_miku_related(rec) else ""
    return f"{base} {detail}{miku}"


def lucky_song(records, today, level=None) -> dict | None:
    """今日幸运曲：在该等级允许的术力口池里抽。"""
    levels = settings.get_levels()
    lv = levels.get(level or config.DEFAULT_LEVEL, config.LEVELS[config.DEFAULT_LEVEL])
    pool = [
        r for r in records
        if r["genre"] == config.VOCALOID_GENRE
        and r["diff"] in lv["diffs"]
        and lv["ds_min"] <= r["ds"] <= lv["ds_max"]
    ]
    seen, uniq = set(), []
    for r in pool:
        if r["title"] in seen:
            continue
        seen.add(r["title"])
        uniq.append(r)
    if not uniq:
        return None
    rng = random.Random(f"{today.strftime('%Y-%m-%d')}-lucky")
    return rng.choices(uniq, weights=[_weight(r) for r in uniq], k=1)[0]


def genre_stats(records, tiers) -> dict:
    stats = {}
    for tier in tiers:
        pool = candidates_for_tier(records, tier)
        stats[tier["key"]] = {
            "total": len(pool),
            "vocaloid": sum(1 for r in pool if r["genre"] == config.VOCALOID_GENRE),
            "miku": sum(1 for r in pool if is_miku_related(r)),
        }
    return stats