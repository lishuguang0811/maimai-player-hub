# -*- coding: utf-8 -*-
"""
owner.py —— 主人（私人空间）的生日彩蛋逻辑

抽成独立函数是为了能在测试里指定任意时间验证，不用真等到生日当天。
"""
from __future__ import annotations

from datetime import datetime

import config
from modules import settings


def is_birthday(now: datetime) -> bool:
    bd, _ = settings.get_owner()
    return (now.month, now.day) == bd


def age(now: datetime) -> int:
    _, year = settings.get_owner()
    return now.year - year


def next_birthday(now: datetime) -> datetime:
    """下一个生日 00:00。如果今年的已过，则算明年。"""
    m, d = settings.get_owner()[0]
    target = datetime(now.year, m, d)
    if target <= now:
        target = datetime(now.year + 1, m, d)
    return target


def countdown_parts(now: datetime) -> dict | None:
    """
    返回到下一个生日的 {days,hours,minutes,seconds,target}。
    当天（已是生日）返回 None，由调用方显示"生日快乐"。
    """
    if is_birthday(now):
        return None
    remain = next_birthday(now) - now
    if remain.total_seconds() <= 0:
        return None
    return {
        "days": remain.days,
        "hours": remain.seconds // 3600,
        "minutes": (remain.seconds % 3600) // 60,
        "seconds": remain.seconds % 60,
        "target": next_birthday(now),
    }
