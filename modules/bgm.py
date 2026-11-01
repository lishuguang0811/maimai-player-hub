# -*- coding: utf-8 -*-
"""
bgm.py —— 背景音乐系统（3.0 第四节）

- 实际可播放音频来自 data/bgm/（mp3/wav/ogg/m4a/flac），由用户放入"已获授权"的文件。
  程序不打包任何未经许可的音乐（文档 5.2 禁止抓取/提取商业音频）。
- 舞萌曲库里的曲目没有可用的音频授权，一律不本地播放，改为跳转到网易云等正版平台搜索
  （见 music.netease_search_url / qqmusic_search_url），不伪造"可播放"状态。
- 播放用 Streamlit 内置 st.audio（自带 播放/暂停/进度/音量），默认不自动播放。
"""
from __future__ import annotations

import json
from pathlib import Path

import config

BGM_DIR = config.DATA_DIR / "bgm"
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}


def list_tracks() -> list[Path]:
    """data/bgm/ 里实际可播放的音频文件（用户自行放入已授权音乐）。"""
    if not BGM_DIR.exists():
        return []
    return sorted(p for p in BGM_DIR.iterdir() if p.suffix.lower() in AUDIO_EXTS)


def track_label(p: Path) -> str:
    """把 bgm_01_ambient.wav 变成好读的『01 · Ambient』。"""
    stem = p.stem.replace("bgm_", "")
    parts = stem.split("_", 1)
    return f"{parts[0]} · {parts[1].capitalize()}" if len(parts) == 2 else stem.capitalize()