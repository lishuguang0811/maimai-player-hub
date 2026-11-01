# -*- coding: utf-8 -*-
"""
minigames.py —— 轻量小游戏（maimai 主题，全部自包含，不依赖任何外部/侵权素材）

包含：
1) 今日运势 / 今日任务 / 幸运签（原 easter_egg 文案抢救，按日期固定，不煽情）
2) 猜曲挑战（quiz）：用本地曲库快照出题，给提示 + 四选一，可计分
3) 完美判定（timing）：反应力小游戏，测"GO 出现后多久点中"，映射 maimai 判定

所有随机都带"日期+标签"种子，所以同一天结果稳定、可复现。
"""
from __future__ import annotations

import random
from datetime import date

import config


# ============ 今日运势（玩家吐槽风，不煽情） ============
FORTUNES = [
    ("SSS+", "今天手感在线，13 定数区间随便摸，别浪费。"),
    ("SSS", "稳定发挥日，适合把常年差一点的那首收掉。"),
    ("SS", "普通水平日，按热身-主打-挑战的顺序打，别乱跳。"),
    ("S", "手感有点飘，建议多打一局热身再上主打。"),
    ("B", "今天的你是来交学费的，控制币数，别连冲。"),
    ("A", "中规中矩的一天，认真读谱比硬冲定数更划算。"),
    ("SSS-", "状态不错，适合挑战一首一直不敢碰的高难。"),
]

TASKS = [
    "用非惯用手打一局 EXPERT 11，体会一下另一边的世界。",
    "挑一首今天推荐的曲，全程不看手，只盯判定线。",
    "把主打曲打两遍，第二遍必须比第一遍准。",
    "今天不准打自己最拿手的那首，逼自己开新图。",
    "连续三局不接任何一次币，做完再说话。",
    "找一首 BPM 180 以上的术力口，练一下高速读谱。",
    "打之前先拉伸手指 30 秒，认真做，别糊弄。",
    "把今天推荐曲的谱面作者名字记下来，回家查他别的谱。",
    "试一首 Re:MASTER，体会一下白键的压迫感。",
    "今天的目标是：至少一首达成 ALL PERFECT。",
]

LUCKY_LINES = [
    "抽到这首，今天的运气算是用掉一半了。",
    "这首歌的谱面属于越打越顺的类型，适合当今天的主心骨。",
    "幸运曲不是保证 FC，是保证你今天有话题可聊。",
    "如果这首打崩了，就当是运气在给你留后手。",
    "把它当热身，进了状态再上你真正想冲的那首。",
]


def _rng(today: date, tag: str) -> random.Random:
    return random.Random(f"{today.strftime('%Y-%m-%d')}-{tag}")


def fortune(today: date, override: tuple | None = None) -> dict:
    """override=(rank,text) 用于生日特别模式，不走随机。"""
    if override:
        return {"rank": override[0], "text": override[1]}
    rank, text = _rng(today, "fortune").choice(FORTUNES)
    return {"rank": rank, "text": text}


def task(today: date) -> str:
    return _rng(today, "task").choice(TASKS)


def lucky_line(today: date) -> str:
    return _rng(today, "lucky").choice(LUCKY_LINES)


# ============ 猜曲挑战（quiz） ============
def quiz_question(records: list[dict], seed: str, n_choices: int = 4) -> dict | None:
    """
    从本地曲库出题：随机选一首作答案，再抽 n_choices-1 个干扰项（曲名）。
    返回 {"seed","answer":title,"options":[...],"hint":{...},"song_id":...}；
    曲库太小或无可读曲名时返回 None。
    """
    if not records:
        return None
    rng = random.Random(f"quiz-{seed}")
    pool = [r for r in records if (r.get("title") or "").strip()]
    if len(pool) < n_choices:
        return None
    answer = rng.choice(pool)
    options = {answer["title"]}
    while len(options) < n_choices:
        cand = rng.choice(pool)["title"]
        options.add(cand)
    options = list(options)
    rng.shuffle(options)
    return {
        "seed": seed,
        "answer": answer["title"],
        "options": options,
        "hint": {
            "genre": answer.get("genre") or "未分类",
            "bpm": answer.get("bpm") if answer.get("bpm") not in (None, 0) else None,
            "ds": round(answer.get("ds") or 0, 1),
            "miku": "初音未来/世界计划相关" if _is_miku(answer) else None,
        },
        "song_id": answer.get("song_id", ""),
    }


def _is_miku(rec: dict) -> bool:
    artist = rec.get("artist", "")
    return any(k in artist for k in config.MIKU_KEYWORDS)


def quiz_judge(question: dict, picked: str) -> bool:
    return picked == question.get("answer")


# ============ 定数竞猜（用真实曲库，考的是经验） ============
DS_JUDGE_TABLE = [
    (0.05, 100, "CRITICAL PERFECT", "误差 0.05 以内，这已经不是猜，是背过谱了。"),
    (0.15, 88, "PERFECT", "几乎正中，你对这张谱的手感有数。"),
    (0.30, 70, "GREAT", "方向对了，差在小数位。"),
    (0.50, 50, "GOOD", "量级猜对，细节还差一点。"),
    (0.80, 28, "MISS", "估偏了，回忆一下这谱到底有多难。"),
    (99.0, 0, "MISS", "差得有点远，下次先想想它大概在哪个档。"),
]

DS_RANKS = [(95, "定数仙人"), (85, "谱面研究员"), (70, "机厅老手"),
            (50, "还在上手"), (0, "先多打几百局")]


def ds_round(records: list[dict], seed: str, hard: bool = False) -> dict | None:
    """
    出一道定数竞猜题：给曲名（hard 模式只有曲名），猜它的谱面定数。
    答案全部来自本地曲库快照原值，不做任何推测。
    """
    pool = [r for r in (records or [])
            if (r.get("title") or "").strip() and r.get("ds") not in (None, 0)]
    if not pool:
        return None
    rng = random.Random(f"dsquiz-{seed}")
    pick = rng.choice(pool)
    return {
        "seed": seed,
        "title": pick["title"],
        "artist": pick.get("artist") or "未知",
        "genre": pick.get("genre") or "未分类",
        "bpm": pick.get("bpm") or None,
        "diff": pick.get("diff") or "",
        "level": pick.get("level") or "",
        "ds": round(float(pick["ds"]), 1),
        "hard": hard,
    }


def ds_judge(guess: float, answer: float) -> dict:
    err = abs(float(guess) - float(answer))
    for lim, score, judge, comment in DS_JUDGE_TABLE:
        if err <= lim:
            break
    return {"err": round(err, 2), "score": score, "judge": judge,
            "comment": comment, "answer": answer}


def ds_rank(avg: float) -> str:
    for lim, name in DS_RANKS:
        if avg >= lim:
            return name
    return DS_RANKS[-1][1]


# ============ BPM 速猜（真实曲库 BPM） ============
BPM_JUDGE_TABLE = [
    (0.02, 100, "CRITICAL PERFECT", "连 BPM 都背下来了，这歌你打过多少遍？"),
    (0.05, 85, "PERFECT", "很接近，节拍感是有的。"),
    (0.10, 65, "GREAT", "量级对，稍微偏一点。"),
    (0.20, 40, "GOOD", "差得有点多，想想它是快歌还是慢歌。"),
    (0.35, 18, "MISS", "基本是蒙的吧。"),
    (9.99, 0, "MISS", "差太远了，下次先用脚打个拍子。"),
]


def bpm_round(records: list[dict], seed: str) -> dict | None:
    pool = [r for r in (records or [])
            if (r.get("title") or "").strip() and (r.get("bpm") or 0)]
    if not pool:
        return None
    rng = random.Random(f"bpm-{seed}")
    pick = rng.choice(pool)
    return {"seed": seed, "title": pick["title"], "artist": pick.get("artist") or "",
            "genre": pick.get("genre") or "未分类", "bpm": int(pick["bpm"]),
            "ds": round(float(pick.get("ds") or 0), 1)}


def bpm_judge(guess: float, answer: float) -> dict:
    err = abs(float(guess) - float(answer))
    rel = err / max(1.0, float(answer))
    for lim, score, judge, comment in BPM_JUDGE_TABLE:
        if rel <= lim:
            break
    return {"err": int(err), "score": score, "judge": judge, "comment": comment,
            "answer": int(answer)}


# ============ 定数比大小（二选一，考的是对谱面的印象） ============
def ds_duel(records: list[dict], seed: str, min_gap: float = 0.2) -> dict | None:
    """
    抽两首歌，猜哪首定数更高。差距太小的不出（那是纯蒙），
    返回两首的曲名/艺人/流派，答案在结算时才给。
    """
    pool = [r for r in (records or [])
            if (r.get("title") or "").strip() and r.get("ds")]
    if len(pool) < 20:
        return None
    rng = random.Random(f"duel-{seed}")
    for _ in range(30):
        a, b = rng.sample(pool, 2)
        if a["title"] == b["title"]:
            continue
        da, db = float(a["ds"]), float(b["ds"])
        if abs(da - db) < min_gap:
            continue
        return {
            "seed": seed,
            "a": {"title": a["title"], "artist": a.get("artist") or "",
                  "genre": a.get("genre") or "", "ds": round(da, 1)},
            "b": {"title": b["title"], "artist": b.get("artist") or "",
                  "genre": b.get("genre") or "", "ds": round(db, 1)},
            "answer": "a" if da > db else "b",
            "gap": round(abs(da - db), 1),
        }
    return None


def duel_judge(duel: dict, pick: str) -> bool:
    return pick == duel.get("answer")


def duel_rank(correct: int, total: int) -> str:
    rate = correct / max(1, total)
    if rate >= 0.9:
        return "定数活字典"
    if rate >= 0.75:
        return "谱面研究员"
    if rate >= 0.6:
        return "机厅老手"
    if rate >= 0.45:
        return "还在上手"
    return "先把曲库混个脸熟"


# ============ 完美判定（timing 反应力） ============
def timing_judgement(reaction_ms: float, target_ms: float = 0) -> dict:
    """
    反应力小游戏判定：reaccion_ms 是"GO 出现后多久点的"。
    越接近 0（即 GO 一出现就点中）判定越好。
    返回 {"judge","score","comment"}，judge 用 maimai 判定语感。
    """
    diff = abs(reaction_ms - target_ms)
    if diff <= 60:
        return {"judge": "CRITICAL PERFECT", "score": 100,
                "comment": "完美！手和判定线同步了。"}
    if diff <= 130:
        return {"judge": "PERFECT", "score": 80,
                "comment": "稳。差一点点就是 AP 级反应。"}
    if diff <= 220:
        return {"judge": "GREAT", "score": 55,
                "comment": "不错，但还能更跟手。"}
    if diff <= 350:
        return {"judge": "GOOD", "score": 30,
                "comment": "慢了半拍，下次盯紧 GO。"}
    return {"judge": "MISS", "score": 0,
            "comment": "手滑了？深呼吸，再来一次。"}
