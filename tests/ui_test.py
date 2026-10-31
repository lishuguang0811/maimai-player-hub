# -*- coding: utf-8 -*-
"""ui_test.py —— 五页导航的界面测试（登录/注册/导航/减法式移除/管理员）。"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys

import config
from modules import accounts
from streamlit.testing.v1 import AppTest

ok = True
PWD = "Uitest12"
OWNER = config.OWNER_NAME
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
for _n in [OWNER, "测试君", "新玩家甲", "手机用户"]:
    _pre.pop(_n, None)
accounts.save_accounts(_pre)
accounts.ensure_admin()
accounts.register(OWNER, PWD, "2000-01-01", "北京", "高手", ["初音未来"])
accounts.register("测试君", PWD, None, "北京", "新手", ["东方Project"])

try:
    print("=== A. 访客登录页 ===")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    check("脚本无异常", not at.exception, str(at.exception))
    check("标题", config.APP_NAME in html_of(at) or "PLAYER HUB" in html_of(at))
    check("登录/注册/找回按钮", all(any(b.label == x for b in at.button) for x in ["登录", "注册", "重置密码"]))
    check("不泄露私人内容", config.PRIVATE_TITLE not in html_of(at))

    print("=== B. 弱密码注册被拒 ===")
    atw = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    atw.text_input[2].set_value("弱密码用户"); atw.text_input[3].set_value("weak"); atw.text_input[4].set_value("weak")
    [b for b in atw.button if b.label == "注册"][0].click().run()
    check("弱密码不进入", "你好，弱密码用户" not in html_of(atw))

    print("=== C. 登录主人(待验证) + 导航 + 减法移除 ===")
    at.text_input[0].set_value(OWNER); at.text_input[1].set_value(PWD)
    [b for b in at.button if b.label == "登录"][0].click().run()
    check("登录无异常", not at.exception, str(at.exception))
    h = html_of(at)
    check("首页问候", f"你好，{OWNER}" in h)
    check("迷你播放器在首页", "打开完整播放器" in h or "未在播放" in h)
    check("首页首次引导", any("我知道了，不再显示" in (b.label or "") for b in at.button))
    for _ in range(5):
        [b for b in at.button if b.key == "logo_btn"][0].click().run()
    check("logo连点5次彩蛋", any("被你发现了" in s.value for s in at.success))
    nav(at, "曲目与收藏")
    ht = html_of(at)
    check("搜索不伪造提示", "不伪造搜索结果" in ht)
    check("YouTube官方嵌入入口", any("加载播放器" in (b.label or "") for b in at.button))
    nav(at, "我的与设置")
    check("数据备份入口", "数据备份" in html_of(at))
    removed = ["实时天气", "今日主题", "音游地图", "每个币", "离你最近", "附近机厅", "网络定位"]
    check("已移除天气/地图/币价/机台", all(x not in h for x in removed), str([x for x in removed if x in h]))
    for pg, kws in [("曲目与收藏", ["音乐播放器", "舞萌曲库", "我的收藏"]),
                    ("练习与成绩", ["练习清单", "成绩记录", "手动录入"]),
                    ("我的与设置", ["主题", "修改密码"])]:
        nav(at, pg)
        check(f"{pg} 页无异常", not at.exception, str(at.exception))
        check(f"{pg} 含 {kws[0]}", all(k in html_of(at) for k in kws), str([k for k in kws if k not in html_of(at)]))
    nav(at, "🔐 完成验证")
    check("待验证用户在完成验证页看到入口", any("完成专属身份验证" in (b.label or "") for b in at.button))
    check("待验证用户看不到私人内容", config.PRIVATE_TITLE not in html_of(at))

    print("=== D. 管理员 ===")
    ata = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    ata.text_input[0].set_value(config.ADMIN_NAME); ata.text_input[1].set_value(ADMIN_PWD)
    [b for b in ata.button if b.label == "登录"][0].click().run()
    nav(ata, "我的与设置")
    ha = html_of(ata)
    check("管理员面板在", "管理员" in ha)
    check("面板含名言/攻略管理", all(k in ha for k in ["名言管理", "攻略管理"]))

    print("=== E. 新手登录 ===")
    atn = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    atn.text_input[0].set_value("测试君"); atn.text_input[1].set_value(PWD)
    [b for b in atn.button if b.label == "登录"][0].click().run()
    check("新手首页", "你好，测试君" in html_of(atn))

    print("=== F. 手机号登录 ===")
    accounts.register("手机用户", PWD, "1995-03-03", "北京", "进阶", [], "", "13912345678")
    atp = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    atp.text_input[0].set_value("13912345678"); atp.text_input[1].set_value(PWD)
    [b for b in atp.button if b.label == "登录"][0].click().run()
    check("手机号登录", "你好，手机用户" in html_of(atp))
finally:
    a = accounts.load_accounts()
    for n in [OWNER, "测试君", "手机用户"]:
        a.pop(n, None)
    accounts.save_accounts(a)
    print("   (已清理测试账号)")

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
