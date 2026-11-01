# -*- coding: utf-8 -*-
"""music_test.py —— 播放状态机 + 音源适配器(诚实区分可播放/仅展示) + 统一搜索。"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _env import ROOT  # noqa: F401
from modules import music, songs

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


print("=== 1. 播放状态机 ===")
s = music.new_state()
check("初始空队列", s["queue"] == [] and s["status"] == "stopped")
t1 = music.make_track("bgm", "A", "", "full", file="x.wav")
t2 = music.make_track("bgm", "B", "", "full", file="y.wav")
t3 = music.make_track("maimai", "C", "", "info", url="http://x")
s = music.play_now(s, t1)
check("play_now 设为当前", music.current(s)["title"] == "A" and s["status"] == "playing")
s = music.add_to_queue(s, t2)
check("加入队列", len(s["queue"]) == 2)
s2 = music.next_track(s)
check("next 到第二首", music.current(s2)["title"] == "B")
s3 = music.next_track(s2)
check("列表循环回绕到第一首", music.current(s3)["title"] == "A")
sp = music.prev_track(s2)
check("prev 回第一首", music.current(sp)["title"] == "A")
sone = music.set_mode(s, "one")
sone2 = music.next_track(sone)
check("单曲循环 next 停在当前", music.current(sone2)["title"] == music.current(s)["title"])
ssh = music.set_mode(s2, "shuffle")
rng = random.Random(7)
ssh2 = music.next_track(ssh, rng)
check("随机模式仍在队列内", music.current(ssh2)["title"] in ("A", "B"))
check("set_volume 钳制", music.set_volume(s, 5)["volume"] == 1.0 and music.set_volume(s, -1)["volume"] == 0.0)
check("toggle_mute", music.toggle_mute(s)["muted"] is True)
# info 曲目播放状态标 info 而非 playing
si = music.play_now(s, t3)
check("仅展示曲目状态=info", si["status"] == "info" and not music.current(si)["playable"])

print("=== 2. 曲目模型 ===")
try:
    music.make_track("x", "t", "", "bogus_kind"); check("非法 play_kind 拒绝", False)
except AssertionError:
    check("非法 play_kind 拒绝", True)
check("full 可播放", music.make_track("a", "t", "", "full")["playable"] is True)
check("info 不可播放", music.make_track("a", "t", "", "info")["playable"] is False)

print("=== 3. 适配器 ===")
bg = music.LocalBgmAdapter()
check("本地BGM已配置", bg.configured())
res, more = bg.search("")
check("本地BGM搜到>=8首", len(res) >= 8, f"{len(res)}")
check("本地BGM均可播放(full)", all(t["playable"] and t["play_kind"] == "full" for t in res))
check("本地BGM带文件路径", all(t["file"] for t in res))
res2, _ = bg.search("ambient")
check("本地BGM关键词过滤", len(res2) == 1 and "ambient" in res2[0]["title"].lower())

recs = songs.flatten(songs.load_snapshot())
lib = music.LibraryAdapter(recs)
check("曲库适配器已配置", lib.configured())
lr, lmore = lib.search("初音ミクの消失")
check("曲库搜索命中", len(lr) >= 1 and lr[0]["title"] == "初音ミクの消失")
check("曲库结果仅展示(info)不可播放", all(t["play_kind"] == "info" and not t["playable"] for t in lr))
check("曲库结果带B站来源链接", all(t["url"].startswith("https://search.bilibili.com/") for t in lr))
empty, _ = lib.search("zzz不存在的曲目xyz")
check("曲库无结果返回空", len(empty) == 0)

# SoundCloud 适配器已经整个拿掉了（没有授权就不提供入口），这里确认它确实不在了
check("不再有 SoundCloud 适配器", not hasattr(music, "SoundCloudAdapter"))

print("=== 4. 统一搜索 ===")
ms = music.MusicSource(recs)
notes = ms.configured_note()
check("配置提示存在且不提 SoundCloud", isinstance(notes, list) and all("SoundCloud" not in n for n in notes), str(notes))
merged, _ = ms.search("初音")
check("合并结果非空", len(merged) > 0)
check("可播放排前面", merged[0]["playable"] if any(t["playable"] for t in merged) else True)
keys = [(t["source"], t["title"], t["artist"]) for t in merged]
check("去重", len(keys) == len(set(keys)))
allres, allmore = ms.search("")
check("空关键词返回第1页(BGM+分页曲库)", 8 <= len(allres) <= 20 + 20, f"{len(allres)}")
check("曲库分页 has_more=True", allmore is True)
pg2, _ = ms.search("", page=2)
check("第2页与第1页不重复", not {(t["source"],t["title"]) for t in pg2} & {(t["source"],t["title"]) for t in allres})

print("=== 5. YouTube 官方嵌入(无需密钥) ===")
yt_ok = {"dQw4w9WgXcQ": "dQw4w9WgXcQ",
         "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
         "https://youtu.be/dQw4w9WgXcQ": "dQw4w9WgXcQ",
         "https://www.youtube.com/embed/dQw4w9WgXcQ": "dQw4w9WgXcQ",
         "https://m.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ"}
for inp, exp in yt_ok.items():
    check("解析合法 " + inp[:34], music.parse_youtube(inp) == exp)
for inp in ["https://evil.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=short",
            "javascript:alert(1)", "not a url", "", "https://vimeo.com/12345"]:
    check("拒绝非法 " + repr(inp[:30]), music.parse_youtube(inp) is None)
tr = music.track_from_youtube("https://youtu.be/dQw4w9WgXcQ", "测试曲")
check("embed 曲目可播放标记", tr and tr["play_kind"] == "embed" and tr["playable"])
check("嵌入用 nocookie 官方域", tr["embed_url"].startswith("https://www.youtube-nocookie.com/embed/"))
check("非法输入不生成曲目", music.track_from_youtube("https://evil.com/x") is None)
check("搜索链接为官方", music.youtube_search_url("初音").startswith("https://www.youtube.com/results?search_query="))
print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)