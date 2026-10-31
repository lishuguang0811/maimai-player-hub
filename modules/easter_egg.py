# -*- coding: utf-8 -*-
"""
easter_egg.py —— 趣味彩蛋

全部由"当天日期"决定，所以是每日固定的，不会点一次变一次。
文案走玩家之间的吐槽风格，不煽情。
"""
from __future__ import annotations

import random
from datetime import date

FORTUNES = [
    ("SSS+", "今天手感在线，13 定数区间随便摸，别浪费。"),
    ("SSS", "稳定发挥日，适合把常年差一点的那首收掉。"),
    ("SS", "普通水平日，按热身-主打-挑战的顺序打，别乱跳。"),
    ("S", "手感有点飘，建议多打一局热身再上主打。"),
    ("B", "今天的你是来交学费的，控制币数，别连冲。"),
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
]

LUCKY_LINES = [
    "抽到这首，今天的运气算是用掉一半了。",
    "这首歌的谱面属于越打越顺的类型，适合当今天的主心骨。",
    "幸运曲不是保证 FC，是保证你今天有话题可聊。",
    "如果这首打崩了，就当是运气在给你留后手。",
]


def _rng(today: date, tag: str) -> random.Random:
    return random.Random(f"{today.strftime('%Y-%m-%d')}-{tag}")


def fortune(today: date, override: tuple | None = None) -> dict:
    """override 用于生日特别模式：直接指定等级和文案，不走随机。"""
    if override:
        return {"rank": override[0], "text": override[1]}
    rank, text = _rng(today, "fortune").choice(FORTUNES)
    return {"rank": rank, "text": text}


def task(today: date) -> str:
    return _rng(today, "task").choice(TASKS)


def lucky_line(today: date) -> str:
    return _rng(today, "lucky").choice(LUCKY_LINES)


def trivia(today: date, items: list[str]) -> str:
    if not items:
        return ""
    return _rng(today, "trivia").choice(items)