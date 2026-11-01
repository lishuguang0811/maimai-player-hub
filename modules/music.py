# -*- coding: utf-8 -*-
"""
music.py —— 统一音乐来源适配器 + 播放状态管理（3.0/音乐改造）

设计原则（文档第三节）：
- 搜索到 ≠ 可播放。每首曲目带 play_kind：
    "full"   = 本地有音频文件，可完整播放
    "embed"  = 官方嵌入播放（需平台允许且已配置）
    "preview"= 官方试听
    "info"   = 仅展示曲目信息 + 合法来源链接（不可在本程序播放）
- 适配器独立，不把某平台写死。当前内置：
    LocalBgmAdapter   本地 data/bgm/ 原创音频 -> full（真实可播放）
    LibraryAdapter    本地 maimai 曲库检索 -> info（游戏谱面信息，附 B 站来源链接，无音频）
    SoundCloudAdapter 官方 API/嵌入 -> 未配置密钥时明确返回"未配置"，绝不伪装可用
- 不抓取受保护音频流、不绕过登录/地区/付费限制、不伪造播放状态。

播放状态是纯 dict（存 st.session_state["music"]），函数无副作用、可单测。
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import config
from modules import bgm, songs

PLAY_KINDS = ("full", "embed", "preview", "info")
MODES = ("list", "one", "shuffle")


# ---------------- 曲目模型 ----------------
def make_track(source, title, artist="", play_kind="info", url="", file=None,
               duration=None, track_id=None, embed_url=None):
    assert play_kind in PLAY_KINDS
    return {
        "id": track_id or f"{source}:{title}:{artist}",
        "source": source, "title": title, "artist": artist,
        "play_kind": play_kind, "url": url, "file": str(file) if file else None,
        "duration": duration, "embed_url": embed_url,
        "playable": play_kind in ("full", "embed", "preview"),
    }


# ---------------- 播放状态（纯函数） ----------------
def new_state():
    return {"queue": [], "index": 0, "mode": "list", "volume": 0.7,
            "muted": False, "status": "stopped"}


def current(state):
    q, i = state.get("queue", []), state.get("index", 0)
    return q[i] if q and 0 <= i < len(q) else None


def play_now(state, track):
    """把一首歌设为当前播放（替换队列为单首）。"""
    state = dict(state); state["queue"] = [track]; state["index"] = 0
    state["status"] = "playing" if track.get("playable") else "info"
    return state


def add_to_queue(state, track):
    state = dict(state); state["queue"] = list(state.get("queue", [])) + [track]
    if state["status"] == "stopped" and track.get("playable"):
        state["index"] = len(state["queue"]) - 1; state["status"] = "playing"
    return state


def _advance(state, direction, rng=None):
    q = state.get("queue", [])
    if not q:
        return dict(state)
    state = dict(state); mode = state.get("mode", "list")
    if mode == "one" and direction > 0:
        return state                                  # 单曲循环：停在当前
    if mode == "shuffle":
        rng = rng or random.Random()
        if len(q) > 1:
            ni = rng.randrange(len(q))
            while ni == state.get("index", 0):
                ni = rng.randrange(len(q))
        else:
            ni = 0
    else:
        ni = (state.get("index", 0) + direction) % len(q)   # 列表循环：到末尾回绕
    state["index"] = ni
    cur = q[ni]
    state["status"] = "playing" if cur.get("playable") else "info"
    return state


def next_track(state, rng=None):
    return _advance(state, +1, rng)


def prev_track(state):
    return _advance(state, -1)


def set_mode(state, mode):
    assert mode in MODES
    state = dict(state); state["mode"] = mode; return state


def set_volume(state, v):
    state = dict(state); state["volume"] = max(0.0, min(1.0, float(v))); return state


def toggle_mute(state):
    state = dict(state); state["muted"] = not state.get("muted", False); return state


# ---------------- 音源适配器 ----------------
class LocalBgmAdapter:
    """本地 data/bgm/ 原创音频 -> 可完整播放(full)。"""
    name = "本地原创BGM"

    def configured(self):
        return True

    def search(self, query="", page=1, page_size=20):
        tracks = []
        for p in bgm.list_tracks():
            title = p.stem
            if query and query.lower() not in title.lower():
                continue
            tracks.append(make_track("bgm", title, "原创合成", "full", file=p))
        start = (page - 1) * page_size
        return tracks[start:start + page_size], start + page_size < len(tracks)


class LibraryAdapter:
    """本地 maimai 曲库检索 -> 仅展示(info)，附 B 站来源链接，无音频。"""
    name = "舞萌曲库"

    def __init__(self, records):
        self.records = records or []

    def configured(self):
        return bool(self.records)

    def search(self, query="", page=1, page_size=20):
        q = (query or "").strip().lower()
        hits = []
        seen = set()
        for r in self.records:
            if q and q not in r["title"].lower() and q not in (r.get("artist") or "").lower():
                continue
            key = (r["title"], r.get("artist"))
            if key in seen:
                continue
            seen.add(key)
            hits.append(make_track(
                "maimai", r["title"], r.get("artist", ""), "info",
                url=songs.bilibili_link(r["title"]),
                track_id=f"maimai:{r['title']}"))
        start = (page - 1) * page_size
        chunk = hits[start:start + page_size]
        return chunk, start + page_size < len(hits)


ADAPTERS = [LocalBgmAdapter, LibraryAdapter]


class MusicSource:
    """统一搜索入口：合并各适配器、去重、不伪造。"""

    def __init__(self, records=None):
        self.adapters = [LocalBgmAdapter(), LibraryAdapter(records)]

    def configured_note(self):
        notes = []
        for a in self.adapters:
            if not a.configured():
                notes.append(f"{a.name}：未配置/不可用")
        return notes

    def search(self, query="", page=1, page_size=20):
        merged, has_more = [], False
        seen = set()
        for a in self.adapters:
            if not a.configured():
                continue
            try:
                items, more = a.search(query, page, page_size)
            except Exception:                    # noqa: BLE001
                items, more = [], False
            has_more = has_more or more
            for t in items:
                key = (t["source"], t["title"], t["artist"])
                if key in seen:
                    continue
                seen.add(key); merged.append(t)
        # 可播放的排前面，其次按来源/标题
        merged.sort(key=lambda t: (not t["playable"], t["source"], t["title"]))
        return merged, has_more

# ---------------- YouTube 官方嵌入（无需自有 API 密钥） ----------------
# 仅允许 YouTube 官方域名 + 11 位视频 ID；拒绝嵌入任意用户网址（文档第9条）。
import re as _re
from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs

_YT_ID = _re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_DOMAINS = ("youtube.com", "youtu.be", "youtube-nocookie.com",
               "m.youtube.com", "music.youtube.com")


def parse_youtube(s):
    """把 YouTube 链接或裸 ID 解析成 11 位视频 ID；非法/非 YouTube 返回 None。"""
    s = (s or "").strip()
    if not s:
        return None
    if _YT_ID.match(s):
        return s
    try:
        if not s.startswith("http"):
            s = "https://" + s
        u = _urlparse(s)
        host = (u.netloc or "").lower()
        if not any(host == d or host.endswith("." + d) for d in _YT_DOMAINS):
            return None
        if "youtu.be" in host:
            vid = u.path.strip("/").split("/")[0]
        elif u.path.startswith("/embed/") or u.path.startswith("/shorts/"):
            parts = u.path.split("/")
            vid = parts[2] if len(parts) > 2 else ""
        else:
            vid = (_parse_qs(u.query).get("v") or [""])[0]
        return vid if _YT_ID.match(vid or "") else None
    except Exception:                        # noqa: BLE001
        return None


def youtube_embed_url(vid):
    return f"https://www.youtube-nocookie.com/embed/{vid}"


def youtube_watch_url(vid):
    return f"https://www.youtube.com/watch?v={vid}"


def youtube_search_url(query):
    from urllib.parse import quote as _q
    return "https://www.youtube.com/results?search_query=" + _q(query or "")


# ---------------- 外部收听入口（跳转官方平台，不在本程序内播放） ----------------
# 舞萌曲库的曲目没有可用于本程序的音频授权，所以统一做成"跳转网易云搜索"：
# 用户点一下就在新标签页打开网易云的搜索结果，听歌在正版平台完成。
NETEASE_SEARCH = "https://music.163.com/#/search/m/?s={q}"
QQ_MUSIC_SEARCH = "https://y.qq.com/n/ryqq/search?w={q}"


def _q(s: str) -> str:
    from urllib.parse import quote
    return quote((s or "").strip())


def netease_search_url(query: str, artist: str = "") -> str:
    """网易云音乐搜索链接。带艺人能显著提高搜到正确版本的概率。"""
    kw = query or ""
    if artist and artist not in ("未知", ""):
        kw = f"{query} {artist}"
    return NETEASE_SEARCH.format(q=_q(kw))


def qqmusic_search_url(query: str, artist: str = "") -> str:
    kw = query or ""
    if artist and artist not in ("未知", ""):
        kw = f"{query} {artist}"
    return QQ_MUSIC_SEARCH.format(q=_q(kw))


def track_from_youtube(s, title=""):
    """合法 YouTube 链接/ID -> embed 曲目；非法返回 None（不嵌入任意网址）。"""
    vid = parse_youtube(s)
    if not vid:
        return None
    return make_track("youtube", title.strip() or f"YouTube · {vid}", "",
                      "embed", url=youtube_watch_url(vid),
                      embed_url=youtube_embed_url(vid), track_id=f"yt:{vid}")
