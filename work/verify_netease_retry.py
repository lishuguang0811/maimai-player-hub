# -*- coding: utf-8 -*-
"""
verify_netease_retry.py —— 针对第一轮判定为 weak / not_found 的曲名做定向补跑

为什么需要：曲库里不少曲名带后缀或出处标注，例如
    "Scream out! -maimai SONIC WASHER Edit-"
    "Last Brave ～ Go to zero"
第一轮拿全名去搜，会被后缀拉低相似度而漏判。这一轮把后缀去掉再搜，
并且**放宽门槛但不放松佐证**：必须满足下面之一才敢记为可听——
  1) 曲名归一化后完全相等，且网易云艺人与本地艺人对得上；
  2) 曲名归一化后完全相等，且曲名本身足够独特（>=8 个字符，不会撞名）。
艺人对不上又不独特的（jelly / ECHO 这类），依然只给搜索入口，不给直达链接。

用法：
    python work/verify_netease_retry.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                    # noqa: E402
from modules import songs                        # noqa: E402
import verify_netease as V                       # noqa: E402

OUT = config.DATA_DIR / "netease_map.json"

# 去掉这些尾巴：版本标注 / 出处标注 / 副标题
STRIP = re.compile(
    r"(\s*[-－—–]\s*(maimai[^\[\]（）]*)?)?\s*[（(\[【][^）)\]】]*[）)\]】]\s*$", re.I)
STRIP2 = re.compile(r"\s*[-－—–]\s*[^-－—–]{2,}$")            # " -maimai SONIC WASHER Edit-"
TILDE = re.compile(r"\s*[～~]\s+.+$")                          # " ～ Go to zero"


def variants(title: str) -> list[str]:
    """生成去噪后的候选曲名，按可信度从高到低。"""
    out, seen = [], set()

    def add(s: str):
        s = (s or "").strip()
        if s and s not in seen and V.norm(s):
            seen.add(s); out.append(s)

    add(title)
    cur = title
    for _ in range(2):                      # 括号可能嵌套多層，最多剥两次
        nxt = STRIP.sub("", cur).strip()
        if nxt == cur:
            break
        cur = nxt
    add(cur)
    add(STRIP2.sub("", cur).strip())
    add(TILDE.sub("", cur).strip())
    return out


def main() -> None:
    snap = songs.load_snapshot() or {}
    recs = songs.flatten(snap)
    local_artist: dict[str, str] = {}
    for r in recs:
        t = (r.get("title") or "").strip()
        if t:
            local_artist.setdefault(t, (r.get("artist") or "").strip())

    m = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"items": {}}
    items = m.setdefault("items", {})
    todo = [t for t, v in items.items() if v.get("status") != "found"]
    print(f"待补跑 {len(todo)} 首（第一轮判为 同名未确认 / 未收录）\n", flush=True)

    rescued, gave_up = 0, 0
    for i, title in enumerate(todo, 1):
        la = local_artist.get(title, "")
        best = items[title]
        for cand in variants(title):
            for kw in ([cand] + ([f"{cand} {la}"] if la else [])):
                for song in V.search(kw):
                    name = song.get("name") or ""
                    exact = V.norm(cand) and V.norm(cand) == V.norm(name)
                    a_hit = V.artist_hit(la, song)
                    distinctive = len(V.norm(cand)) >= 8
                    if exact and (a_hit or distinctive):
                        best = {"status": "found", "score": 1.0, "id": song.get("id"),
                                "name": name,
                                "artist": "/".join(a.get("name", "") for a in (song.get("artists") or [])),
                                "album": (song.get("album") or {}).get("name", ""),
                                "artist_matched": a_hit, "keyword": kw, "retry": True}
                        break
                if best.get("status") == "found":
                    break
            if best.get("status") == "found":
                break
            time.sleep(V.SLEEP)

        items[title] = best
        if best.get("status") == "found":
            rescued += 1
            print(f"[{i}/{len(todo)}] ✔ 救回 {title} -> {best['name']} ({best['artist']})", flush=True)
        else:
            gave_up += 1
            print(f"[{i}/{len(todo)}] · 维持不给链接 {title}", flush=True)
        if i % 20 == 0:
            m["checked_at"] = datetime.now().isoformat(timespec="seconds")
            m["found"] = sum(1 for v in items.values() if v.get("status") == "found")
            m["total"] = len(items)
            OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"    …已落盘 {i} 首", flush=True)

    m["checked_at"] = datetime.now().isoformat(timespec="seconds")
    m["found"] = sum(1 for v in items.values() if v.get("status") == "found")
    m["total"] = len(items)
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    f = m["found"]
    print(f"\n补跑完成：救回 {rescued} 首，{gave_up} 首仍不给直达链接")
    print(f"最终：共 {m['total']} 首 → 确认可听 {f} · 不给直达链接 {m['total'] - f}")


if __name__ == "__main__":
    main()
