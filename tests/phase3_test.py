# -*- coding: utf-8 -*-
"""phase3_test.py —— 练习清单 / 手动成绩 / 每用户隔离 / 收藏加权推荐。"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys
from datetime import date

import config
from modules import recommend, songs, userdata

ok = True
A, B = "_p3_alice", "_p3_bob"


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


def clean():
    d = userdata._load()
    for u in [A, B]:
        d.pop(userdata._key(u), None)
    userdata._save(d)


clean()
print("=== 1. 收藏 + 每用户隔离 ===")
userdata.add_favorite(A, {"title": "歌X", "artist": "a", "ds": 13.0, "diff": "Master", "genre": "舞萌"})
check("A 收藏成功", userdata.is_favorite(A, "歌X"))
check("B 看不到 A 的收藏", not userdata.is_favorite(B, "歌X"))
check("B 收藏列表为空", len(userdata.list_favorites(B)) == 0)
userdata.add_favorite(A, {"title": "歌X", "ds": 13.0})   # 重复
check("重复收藏去重", len(userdata.list_favorites(A)) == 1)
check("A 取消收藏", userdata.remove_favorite(A, "歌X") and not userdata.is_favorite(A, "歌X"))

print("=== 2. 练习清单 ===")
pid = userdata.add_practice(A, {"title": "练习曲", "diff": "Expert", "ds": 11.5}, "2026-11-01", "练slide")
check("加入练习清单", len(userdata.list_practice(A)) == 1)
check("默认状态未开始", userdata.list_practice(A)[0]["status"] == "未开始")
check("B 看不到 A 的练习", len(userdata.list_practice(B)) == 0)
check("改状态为已完成", userdata.set_practice_status(A, pid, "已完成", "2026-11-02"))
check("非法状态被拒", not userdata.set_practice_status(A, pid, "乱写"))
check("练习与成绩分离(练习不计入成绩)", userdata.stats(A)["count"] == 0)
check("删除练习", userdata.remove_practice(A, pid) and len(userdata.list_practice(A)) == 0)

print("=== 3. 手动成绩 + 校验 ===")
okk, _ = userdata.add_score(A, "成绩曲", "Master", 13.5, 980000, 100.5, True, False, "测试")
check("合法成绩入库", okk)
sc = userdata.list_scores(A)[0]
check("标注手动录入", sc["source"] == "手动录入")
check("达成率保留", sc["achievement"] == 100.5)
check("越界达成率拒绝", not userdata.add_score(A, "x", "Master", 13, 1, 150)[0])
check("负分数拒绝", not userdata.add_score(A, "x", "Master", 13, -5, 90)[0])
check("非数字拒绝", not userdata.add_score(A, "x", "Master", 13, "abc", 90)[0])
check("B 看不到 A 的成绩", len(userdata.list_scores(B)) == 0)
stt = userdata.stats(A)
check("统计正确", stt["count"] == 1 and stt["fc"] == 1 and stt["max_ds"] == 13.5)
check("删除成绩", userdata.remove_score(A, sc["id"]) and userdata.stats(A)["count"] == 0)

print("=== 4. 推荐接入收藏/成绩 ===")
recs = songs.flatten(songs.load_snapshot())
voc = [r for r in recs if r["genre"] == config.VOCALOID_GENRE and r["diff"] == "Master"]
target = voc[0]
w_no = recommend._weight(target, None, None, None)
w_fav = recommend._weight(target, None, {target["title"]}, None)
w_score = recommend._weight(target, None, None, target["ds"])
check("收藏提升权重", w_fav > w_no, f"{w_no:.1f}->{w_fav:.1f}")
check("成绩邻近提升权重", w_score > w_no, f"{w_no:.1f}->{w_score:.1f}")
tiers = recommend.tiers_for_level("高手")
picks = recommend.daily_picks(recs, date(2026, 10, 24), {"key": "sunny"}, tiers, 3, None, "高手",
                              user_fav={target["title"]}, user_scores=[{"ds": target["ds"]}])
check("daily_picks 接受新参数且9首", sum(len(p["songs"]) for p in picks) == 9)
flat = [x["song"]["title"] for p in picks for x in p["songs"]]
check("无重复", len(set(flat)) == len(flat))

clean()
print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)