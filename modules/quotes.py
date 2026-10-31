# -*- coding: utf-8 -*-
"""
quotes.py —— 每次刷新一句 2000-2017 动漫/Galgame 哲学名言

名言存在 data/quotes.json，可自行增删。
"每次刷新换一句"用会话计数器实现：每重跑一次脚本 index+1，循环取下一句，
所以每次交互/刷新都看到不同的名言，且顺序可复现。
"""
from __future__ import annotations

import json
from pathlib import Path

import config


def load_quotes() -> list[dict]:
    p = Path(config.QUOTES_FILE)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        quotes = data.get("quotes", []) if isinstance(data, dict) else data
        # 只保留年份在 2000-2017 的，防御性过滤
        return [
            q for q in quotes
            if isinstance(q, dict) and q.get("text")
            and config.QUOTES_YEAR_MIN <= int(q.get("year", 0)) <= config.QUOTES_YEAR_MAX
        ]
    except Exception:                        # noqa: BLE001
        return []


def pick_quote(index: int) -> dict | None:
    """按序号循环取一句。index 由调用方递增（每次刷新 +1）。"""
    quotes = load_quotes()
    if not quotes:
        return None
    return quotes[index % len(quotes)]

def _raw() -> dict:
    p = Path(config.QUOTES_FILE)
    if not p.exists():
        return {"note": "", "quotes": []}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"quotes": d}
    except Exception:                        # noqa: BLE001
        return {"note": "", "quotes": []}


def save_quotes(quotes: list[dict]) -> None:
    d = _raw()
    d["quotes"] = quotes
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Path(config.QUOTES_FILE).write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def add_quote(text: str, work: str, year: int, speaker: str = "") -> None:
    quotes = _raw().get("quotes", [])
    quotes.append({"text": text, "work": work, "year": int(year), "speaker": speaker})
    save_quotes(quotes)


def delete_quote(index: int) -> bool:
    quotes = _raw().get("quotes", [])
    if 0 <= index < len(quotes):
        quotes.pop(index)
        save_quotes(quotes)
        return True
    return False