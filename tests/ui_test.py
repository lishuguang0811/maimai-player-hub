# -*- coding: utf-8 -*-
"""ui_test.py —— 完整版界面冒烟：登录/注册/七页导航/管理员。"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys

import config
from modules import accounts
from streamlit.testing.v1 import AppTest

ok = True
PWD = "Uitest12"
ADMIN_PWD = "Admin1234"


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


def html_of(at):
    return "\n".join(b.value for b in at.markdown)


def nav(at, page):
    at.sidebar.radio[0].set_value(page).run()


_pre = accounts.load_accounts()
for _n in ["测试君", "手机用户"]:
    _pre.pop(_n, None)
accounts.save_accounts(_pre)
accounts.ensure_admin()
accounts.register("测试君", PWD, "2000-01-01", "北京", "高手", ["初音未来"])
accounts.register("手机用户", PWD, "1995-03-03", "北京", "进阶", [], "", "13912345678")

try:
    print("=== A. 访客登录页 ===")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    check("脚本无异常", not at.exception, str(at.exception))
    check("标题", config.APP_NAME in html_of(at) or "PLAYER HUB" in html_of(at))
    check("登录/注册/找回按钮", all(any(b.label == x for b in at.button) for x in ["登录", "注册", "重置密码"]))

    print("=== B. 弱密码注册被拒 ===")
    atw = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    atw.text_input[2].set_value("弱密码用户"); atw.text_input[3].set_value("weak"); atw.text_input[4].set_value("weak")
    [b for b in atw.button if b.label == "注册"][0].click().run()
    check("弱密码不进入", "你好，弱密码用户" not in html_of(atw))

    print("=== C. 登录 + 七页导航 ===")
    at.text_input[0].set_value("测试君"); at.text_input[1].set_value(PWD)
    [b for b in at.button if b.label == "登录"][0].click().run()
    check("登录无异常", not at.exception, str(at.exception))
    check("首页问候", "你好，测试君" in html_of(at))
    pages = list(at.sidebar.radio[0].options)
    check("七页导航", len(pages) == 7, str(pages))
    check("包含街机厅/小游戏/玩家档案", all(p in pages for p in ["🎮 小游戏", "🕹 街机厅", "📊 玩家档案"]))
    check("没有 VIP 页", "VIP" not in "".join(pages))

    for pg in pages:
        nav(at, pg)
        check(f"{pg} 页无异常", not at.exception, str(at.exception))

    nav(at, "曲目与收藏")
    check("曲库页", "舞萌曲库" in html_of(at))
    nav(at, "我的与设置")
    check("数据备份入口", "数据备份" in html_of(at))
    nav(at, "🎮 小游戏")
    check("小游戏页", "小游戏厅" in html_of(at))
    nav(at, "🕹 街机厅")
    check("街机厅页", "街机厅" in html_of(at))
    nav(at, "📊 玩家档案")
    check("玩家档案页", "玩家档案" in html_of(at))

    print("=== D. 管理员 ===")
    ata = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    ata.text_input[0].set_value(config.ADMIN_NAME); ata.text_input[1].set_value(ADMIN_PWD)
    [b for b in ata.button if b.label == "登录"][0].click().run()
    nav(ata, "我的与设置")
    ha = html_of(ata)
    check("管理员面板在", "管理员" in ha)
    check("面板含名言/攻略管理", all(k in ha for k in ["名言管理", "攻略管理"]))
    check("不再有 VIP 设置", "VIP" not in ha)

    print("=== E. 手机号登录 ===")
    atp = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    atp.text_input[0].set_value("13912345678"); atp.text_input[1].set_value(PWD)
    [b for b in atp.button if b.label == "登录"][0].click().run()
    check("手机号登录", "你好，手机用户" in html_of(atp))
finally:
    a = accounts.load_accounts()
    for n in ["测试君", "手机用户"]:
        a.pop(n, None)
    accounts.save_accounts(a)
    print("   (已清理测试账号)")

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
