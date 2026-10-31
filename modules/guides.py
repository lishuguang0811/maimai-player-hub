# -*- coding: utf-8 -*-
"""
guides.py —— 舞萌攻略专区

攻略存 data/guides.json，结构：[{"category","title","body"}, ...]
管理员面板可增删。内容应为真实、通用的舞萌DX玩法知识，不编造数值。
"""
from __future__ import annotations

import json
from pathlib import Path

import config


def load_guides() -> list[dict]:
    p = Path(config.GUIDES_FILE)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [g for g in data if isinstance(g, dict) and g.get("title")]
    except Exception:                        # noqa: BLE001
        return []


def save_guides(guides: list[dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Path(config.GUIDES_FILE).write_text(
        json.dumps(guides, ensure_ascii=False, indent=2), encoding="utf-8")


def add_guide(category: str, title: str, body: str) -> None:
    guides = load_guides()
    guides.append({"category": category, "title": title, "body": body})
    save_guides(guides)


def delete_guide(index: int) -> bool:
    guides = load_guides()
    if 0 <= index < len(guides):
        guides.pop(index)
        save_guides(guides)
        return True
    return False


def by_category(guides: list[dict]) -> dict:
    out: dict[str, list] = {}
    for g in guides:
        out.setdefault(g.get("category", "其它"), []).append(g)
    return out