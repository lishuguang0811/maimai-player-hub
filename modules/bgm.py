# -*- coding: utf-8 -*-
"""
bgm.py —— 背景音乐系统（3.0 第四节）

- 实际可播放音频来自 data/bgm/（mp3/wav/ogg/m4a/flac），由用户放入"已获授权"的文件。
  程序不打包任何未经许可的音乐（文档 5.2 禁止抓取/提取商业音频）。
- data/bgm_candidates.json 是"十首术力口候选清单"，仅作推荐展示，标注授权/获取状态；
  未获授权的不作为可播放文件，不假装已接入。
- 播放用 Streamlit 内置 st.audio（自带 播放/暂停/进度/音量），默认不自动播放。
"""
from __future__ import annotations

import json
from pathlib import Path

import config

BGM_DIR = config.DATA_DIR / "bgm"
CANDIDATES_FILE = config.DATA_DIR / "bgm_candidates.json"
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}


def list_tracks() -> list[Path]:
    """data/bgm/ 里实际可播放的音频文件（用户自行放入已授权音乐）。"""
    if not BGM_DIR.exists():
        return []
    return sorted(p for p in BGM_DIR.iterdir() if p.suffix.lower() in AUDIO_EXTS)


def load_candidates() -> list[dict]:
    """十首术力口候选清单（仅展示，含授权/获取状态）。"""
    if CANDIDATES_FILE.exists():
        try:
            d = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
        except Exception:                    # noqa: BLE001
            return []
    return []