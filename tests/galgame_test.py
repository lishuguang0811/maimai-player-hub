# -*- coding: utf-8 -*-
"""galgame_test.py —— VN 引擎：生日序章/分支/成就/结局/存档/隔离。"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys

import config
from modules import galgame as g

ok = True
U = "_gg_tester"
U2 = "_gg_second"
U3 = "_gg_third"


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


def reset():
    d = g._load_saves()
    for u in [U, U2, U3]:
        d.pop(g._norm(u), None)
    g._save_saves(d)


def advance(user=U):
    """沿 next 推进，直到选择/生日/信件节点。"""
    guard = 0
    while guard < 200:
        guard += 1
        n = g.current(user)
        if n is None:
            return None
        if n["kind"] in ("choice", "birthday", "letter") or not n.get("next"):
            return n
        g.go(user, n["next"])
    return g.current(user)


def pick(substr, user=U):
    n = g.current(user)
    for i, c in enumerate(n["choices"]):
        if substr in c["label"]:
            return g.choose(user, i)
    raise AssertionError(f"no choice contains {substr!r} at {n['id']}")


reset()
print("=== 1. 启动 + 序章生日校验 ===")
n = g.start(U)
check("起始 p0", n and n["id"] == "p0")
n = advance()
check("到达 p0_r 选择", n and n["id"] == "p0_r")
pick("打开档案")
n = advance()
check("到达生日节点", n and n["kind"] == "birthday")
node, _, okb = g.check_birthday(U, "1999-01-01")
check("错误生日不通过", not okb and node["id"] == "p2r")
right = g.BIRTHDAY_ANSWER
node, _, okb = g.check_birthday(U, right)
check("正确生日通过+身份确认", okb and node["id"] == "p3" and "身份确认" in g.state(U)["achievements"])

print("=== 2. 分支：打开抽屉 ==")
n = advance()
check("到达 c1_r", g.current(U)["id"] == "c1_r")
pick("打开抽屉")
check("解锁好奇心过剩", "好奇心过剩" in g.state(U)["achievements"])
n = advance()
check("到达 c2_r", g.current(U)["id"] == "c2_r")
pick("想")
n = advance()
check("到达 c5", g.current(U)["id"] == "c5")

print("=== 3. END01 + 信件 ===")
pick("继续听")
check("解锁 END01", "END01" in g.state(U)["endings"])
n = advance()
check("到达信件节点", n and n["kind"] == "letter")
check("信件非空", len(g.load_letter()) > 50)

print("=== 4. 另外两个结局 + 派生成就 ===")
g.start(U2)
advance(U2); g.check_birthday(U2, right)
advance(U2); pick("打开抽屉", U2); advance(U2); pick("想", U2); advance(U2)
pick("合上档案", U2)
check("END02", "END02" in g.state(U2)["endings"])

g.start(U3)
advance(U3); g.check_birthday(U3, right)
advance(U3); pick("把谱面带走", U3); advance(U3)
check("END03", "END03" in g.state(U3)["endings"])

g.unlock_ending(U, "END02")
g.unlock_ending(U, "END03")
s = g.state(U)
check("派生平行世界旅行者", "平行世界旅行者" in s["achievements"])
check("派生故事收藏家", "故事收藏家" in s["achievements"])

print("=== 5. 存档/读档/历史/隔离/统计 ===")
g.save_slot(U, 1); before = g.current(U)["id"]
g.go(U, "p0"); g.load_slot(U, 1)
check("读档恢复", g.current(U)["id"] == before)
check("历史>0", len(g.history(U)) > 0)
check("进度统计", g.progress(U)["read"] > 5)
g.start("_gg_fresh")
check("用户隔离", g.state("_gg_fresh")["node"] == "p0" and "身份确认" not in g.state("_gg_fresh")["achievements"])
check("成就视图含稀有度", all("rarity" in a for a in g.achievements_view(U)))
check("结局视图 3 项", len(g.endings_view(U)) == 3)
check("选择节点 >= 4", sum(1 for x in g.nodes().values() if x["kind"] == "choice") >= 4)

reset()
print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
