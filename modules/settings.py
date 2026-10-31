# -*- coding: utf-8 -*-
"""
settings.py —— 管理员可改的设置覆盖层

基础默认值在 config.py；管理员面板的修改存到 data/settings.json，
这里把两者合并。每次调用都重新读文件，所以管理员改完立刻生效，
不用重启、不用改 Python 源码。
"""
from __future__ import annotations

import json
from pathlib import Path

import config


def _defaults() -> dict:
    return {
        "app_name": config.APP_NAME,
        "owner_birthday": list(config.OWNER_BIRTHDAY),
        "owner_birth_year": config.OWNER_BIRTH_YEAR,
        "levels": config.LEVELS,
        "default_welcome": config.DEFAULT_WELCOME,
    }


def load_settings() -> dict:
    d = _defaults()
    p = Path(config.SETTINGS_FILE)
    if p.exists():
        try:
            ov = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(ov, dict):
                for k, v in ov.items():
                    if k == "levels":
                        if isinstance(v, dict) and v:
                            d["levels"] = v
                    else:
                        d[k] = v
        except Exception:                    # noqa: BLE001
            pass
    return d


def save_overrides(overrides: dict) -> None:
    """把管理员的修改合并进 data/settings.json。"""
    p = Path(config.SETTINGS_FILE)
    cur = {}
    if p.exists():
        try:
            cur = json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:                    # noqa: BLE001
            cur = {}
    cur.update(overrides)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")


def get_app_name() -> str:
    return load_settings().get("app_name") or config.APP_NAME


def get_owner() -> tuple:
    s = load_settings()
    b = s.get("owner_birthday") or list(config.OWNER_BIRTHDAY)
    return tuple(b), s.get("owner_birth_year", config.OWNER_BIRTH_YEAR)


def get_levels() -> dict:
    return load_settings().get("levels") or config.LEVELS


def get_welcome() -> str:
    return load_settings().get("default_welcome") or config.DEFAULT_WELCOME