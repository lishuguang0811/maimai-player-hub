# -*- coding: utf-8 -*-
"""
verify_netease.py —— 曲库 × 网易云音乐 校对脚本（一次性，可断点续跑）

做的事：拿本地舞萌曲库的曲名，去网易云的**公开搜索接口**查一遍；
只有确认搜得到、且曲名/艺人对得上的，才把网易云的 song_id 记进
data/netease_map.json，界面据此给出「可听」直达链接。
搜不到或对不上的，记为 not_found —— 界面就不会放链接（不误导、不假装能听）。

边界：只请求搜索接口拿曲目元数据，**不抓取音频、不绕过登录/付费/地区限制**。
是否真能播放由网易云自己决定（部分歌曲需 VIP/下架），本脚本不做任何破解。

用法：
    python work/verify_netease.py --limit 50          # 先试 50 首看命中率
    python work/verify_netease.py                      # 全量（约 5~10 分钟，可中断续跑）
    python work/verify_netease.py --force              # 忽略已有结果，全部重查
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config                                    # noqa: E402
from modules import songs                        # noqa: E402

API = "https://music.163.com/api/search/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://music.163.com/",
    "Accept": "application/json, text/plain, */*",
    "Cookie": "appver=2.0.2",
}
OUT = config.DATA_DIR / "netease_map.json"
SLEEP = 0.28            # 礼貌抓取：约 3~4 次/秒
TIMEOUT = 8

# 曲名里这些尾巴跟"是不是同一首"无关，比较前先去掉
NOISE = re.compile(
    r"[-－—–]\s*(remaster\w*|remix|instrumental|cover|off\s?vocal|game\s*size|short\s*ver\w*|"
    r"tv\s*size|long\s*ver\w*|original\s*mix|extended\w*)\s*$", re.I)
BRACKETS = re.compile(r"[（(\[【][^）)\]】]*[）)\]】]")
NON_ALNUM = re.compile(r"[^0-9a-zA-Z\u3040-\u30ff\u4e00-\u9fff]+")


def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = NOISE.sub("", s)
    s = BRACKETS.sub("", s)
    return NON_ALNUM.sub("", s)


def tokens(s: str) -> set[str]:
    """把曲名拆成可比较的小块：CJK 按字，英文/数字按词。"""
    s = norm(s)
    out, buf = set(), ""
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff":
            if buf:
                out.add(buf); buf = ""
            out.add(ch)
        elif ch.isalnum():
            buf += ch
        else:
            if buf:
                out.add(buf); buf = ""
    if buf:
        out.add(buf)
    return {t for t in out if t}


def similarity(title: str, name: str) -> float:
    nt, nn = norm(title), norm(name)
    if not nt or not nn:
        return 0.0
    if nt == nn:
        return 1.0
    if len(nt) >= 4 and (nt in nn or nn in nt):
        return 0.9
    a, b = tokens(title), tokens(name)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return round(inter / min(len(a), len(b)) * 0.9, 3)


def artist_hit(artist: str, song: dict) -> bool:
    na = norm(artist)
    if not na:
        return False
    for ar in song.get("artists", []) or []:
        if norm(ar.get("name", "")) and (norm(ar.get("name", "")) in na or na in norm(ar.get("name", ""))):
            return True
    alias = song.get("alias") or []
    return any(na in norm(x) for x in alias)


def search(keyword: str) -> list[dict]:
    try:
        r = requests.get(API, params={"s": keyword, "type": 1, "offset": 0, "limit": 6},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        data = r.json()
        return ((data.get("result") or {}).get("songs") or [])
    except Exception:                                # noqa: BLE001
        return []


def verify(title: str, artist: str = "") -> dict:
    """
    查一首：先只查曲名，不够再带上艺人查一次。
    判定很保守——名字一样但艺人对不上的短曲名（Love You / jelly / Future 这类）
    一律不算「搜到」，避免给一个根本不是这首的链接。
      found      = 艺人对得上，或曲名足够独特且完全命中 → 给直达链接
      weak       = 名字像但不敢确定 → 不给直达链接，只给搜索入口
      not_found  = 网易云确实搜不到 → 不放链接
    """
    best: dict = {"status": "not_found", "score": 0.0}
    for kw in ([title] + ([f"{title} {artist}"] if artist else [])):
        for song in search(kw):
            name = song.get("name") or ""
            score = similarity(title, name)
            a_hit = artist_hit(artist, song)
            if a_hit:
                score = min(1.0, score + 0.12)
            # 没有艺人佐证时，要求曲名本身足够独特才敢认
            distinctive = len(norm(title)) >= 6 and score >= 0.95
            status = "found" if (score >= 0.75 and (a_hit or distinctive)) \
                else ("weak" if score >= 0.6 else "not_found")
            rank = score + (1.0 if status == "found" else 0.0)
            if rank > best.get("rank", 0):
                best = {"rank": rank, "status": status, "score": round(score, 3),
                        "id": song.get("id"), "name": name,
                        "artist": "/".join(a.get("name", "") for a in (song.get("artists") or [])),
                        "album": (song.get("album") or {}).get("name", ""),
                        "artist_matched": a_hit, "keyword": kw}
        if best.get("status") == "found" and best.get("score", 0) >= 0.95:
            break
        time.sleep(SLEEP)
    best.pop("rank", None)
    return best


def load_map() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            return {}
    return {"checked_at": None, "items": {}}


def save_map(m: dict) -> None:
    m["checked_at"] = datetime.now().isoformat(timespec="seconds")
    m["found"] = sum(1 for v in m["items"].values() if v.get("status") == "found")
    m["total"] = len(m["items"])
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只查前 N 首（0 = 全量）")
    ap.add_argument("--force", action="store_true", help="忽略已有结果重新查")
    args = ap.parse_args()

    snap = songs.load_snapshot() or {}
    records = songs.flatten(snap)
    uniq: dict[str, str] = {}
    for r in records:
        t = (r.get("title") or "").strip()
        if t and t not in uniq:
            uniq[t] = (r.get("artist") or "").strip()
    titles = list(uniq)
    if args.limit:
        titles = titles[:args.limit]

    m = load_map()
    items = m.setdefault("items", {})
    todo = [t for t in titles if args.force or t not in items]
    print(f"曲库唯一曲名 {len(titles)} 首，待校对 {len(todo)} 首（已有结果 {len(titles) - len(todo)}）")

    for i, t in enumerate(todo, 1):
        res = verify(t, uniq.get(t, ""))
        items[t] = res
        flag = {"found": "✔", "weak": "~", "not_found": "✘"}.get(res.get("status"), "?")
        print(f"[{i}/{len(todo)}] {flag} {t} -> {res.get('name', '')} "
              f"({res.get('artist', '')}) score={res.get('score')}", flush=True)
        if i % 25 == 0:
            save_map(m)
            print(f"    …已落盘 {i} 首", flush=True)
    save_map(m)
    found = sum(1 for v in items.values() if v.get("status") == "found")
    print(f"\n完成：共 {len(items)} 首，网易云确认可听 {found} 首，未收录 {len(items) - found} 首")


if __name__ == "__main__":
    main()
