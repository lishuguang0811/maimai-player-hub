# -*- coding: utf-8 -*-
"""vip_test.py —— 主人注册→三道验证→授权→私人空间（五页导航版）。"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys

import config
from modules import accounts, galgame as _ggm, vip
from streamlit.testing.v1 import AppTest

ok = True
PWD = "Owner2026"
OWNER = config.OWNER_NAME
DEMO_ANS = ["旅人", "青绿", "紫"]


def _clear_gg(name):
    d = _ggm._load_saves(); d.pop(_ggm._norm(name), None); _ggm._save_saves(d)


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


def html_of(at):
    return "\n".join(b.value for b in at.markdown)


def nav(at, page):
    at.sidebar.radio[0].set_value(page).run()


vip.save_questions([{"q": "q1", "answer": DEMO_ANS[0]}, {"q": "q2", "answer": DEMO_ANS[1]},
                    {"q": "q3", "answer": DEMO_ANS[2]}], configured=True)
for n in [OWNER, "路人甲"]:
    a = accounts.load_accounts(); a.pop(n, None); accounts.save_accounts(a)
    _clear_gg(n)

try:
    print("=== 1. 逻辑：注册主人=待验证 ===")
    accounts.register(OWNER, PWD, "2000-01-01", "北京", "高手", ["初音未来"])
    acc = accounts.find_account(OWNER)[1]
    check("vip_status=pending", acc.get("vip_status") == "pending")
    check("未验证非VIP", not accounts.is_vip(acc))
    accounts.register("路人甲", "Pass1234", None, "", "新手", [])
    check("普通用户非VIP", not accounts.is_vip(accounts.find_account("路人甲")[1]))

    print("=== 2. 逻辑：问答验证 ===")
    check("全对通过", vip.verify_answers(DEMO_ANS))
    check("容错(空格/大小写)", vip.verify_answers([" 旅人 ", "青绿", "紫"]))
    check("错一题拒绝", not vip.verify_answers(["旅人", "错", "紫"]))
    accounts.grant_vip(OWNER)
    check("grant后is_vip", accounts.is_vip(accounts.find_account(OWNER)[1]))
    a = accounts.load_accounts(); a[OWNER]["vip_status"] = "pending"; a[OWNER]["vip_verified_at"] = None; accounts.save_accounts(a)

    print("=== 3. UI：注册主人 -> 验证页 ===")
    a = accounts.load_accounts(); a.pop(OWNER, None); accounts.save_accounts(a)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.text_input[2].set_value(OWNER); at.text_input[3].set_value(PWD); at.text_input[4].set_value(PWD)
    [b for b in at.button if b.label == "注册"][0].click().run()
    check("无异常", not at.exception, str(at.exception))
    check("进入验证页", "确认一下" in html_of(at))
    check("不泄露答案", all(x not in html_of(at) for x in DEMO_ANS))

    print("=== 4. UI：错误答案 ===")
    at.text_input[0].set_value("x"); at.text_input[1].set_value("y"); at.text_input[2].set_value("z")
    [b for b in at.button if b.label == "提交验证"][0].click().run()
    check("未进私人空间", config.PRIVATE_TITLE not in html_of(at))
    check("统一失败提示", any("验证未通过" in e.value for e in at.error))
    check("仍pending", accounts.find_account(OWNER)[1].get("vip_status") == "pending")

    print("=== 5. UI：正确答案 -> 私人空间 ===")
    _clear_gg(OWNER)
    at.text_input[0].set_value(DEMO_ANS[0]); at.text_input[1].set_value(DEMO_ANS[1]); at.text_input[2].set_value(DEMO_ANS[2])
    [b for b in at.button if b.label == "提交验证"][0].click().run()
    check("无异常", not at.exception, str(at.exception))
    check("首页私人问候", config.PRIVATE_TITLE in html_of(at))
    check("已verified", accounts.find_account(OWNER)[1].get("vip_status") == "verified")
    nav(at, "私人空间")
    hv = html_of(at)
    check("私人空间档案", "的专属空间" in hv)
    check("有进入剧情按钮", any("进入《SECRET ARCHIVE》" in (b.label or "") for b in at.button))
    [b for b in at.button if "进入《SECRET ARCHIVE》" in (b.label or "")][0].click().run()
    check("剧情页无异常", not at.exception, str(at.exception))
    check("剧情对话框渲染", any("继续" in (b.label or "") for b in at.button))

    print("=== 6. UI：未验证主人登录=普通+可补验证 ===")
    a = accounts.load_accounts(); a.pop(OWNER, None); accounts.save_accounts(a)
    accounts.register(OWNER, PWD, "2000-01-01", "北京", "高手", [])
    at2 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at2.text_input[0].set_value(OWNER); at2.text_input[1].set_value(PWD)
    [b for b in at2.button if b.label == "登录"][0].click().run()
    check("普通首页(无私人问候)", f"你好，{OWNER}" in html_of(at2) and config.PRIVATE_TITLE not in html_of(at2))
    nav(at2, "🔐 完成验证")
    check("完成验证页显示补验证入口", any("完成专属身份验证" in (b.label or "") for b in at2.button))

    print("=== 7. UI：已验证主人重登恢复访问 ===")
    _clear_gg(OWNER)
    accounts.grant_vip(OWNER)
    at3 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at3.text_input[0].set_value(OWNER); at3.text_input[1].set_value(PWD)
    [b for b in at3.button if b.label == "登录"][0].click().run()
    check("重登首页私人问候", config.PRIVATE_TITLE in html_of(at3))
    nav(at3, "私人空间")
    check("重登可进私人空间", "的专属空间" in html_of(at3))

    print("=== 8. 普通用户无入口/不泄露 ===")
    at4 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at4.text_input[0].set_value("路人甲"); at4.text_input[1].set_value("Pass1234")
    [b for b in at4.button if b.label == "登录"][0].click().run()
    h4 = html_of(at4)
    allbtns = [b.label for b in at4.button] + [b.label for b in at4.sidebar.button]
    navopts = list(at4.sidebar.radio[0].options) if hasattr(at4.sidebar.radio[0], "options") else []
    check("普通用户导航无私人入口", not any(x in navopts for x in ["私人空间", "🔐 完成验证"]), str(navopts))
    check("普通用户无验证按钮", not any(x in allbtns for x in ["💿 私人空间", "🔐 完成验证", "完成专属身份验证"]))
    check("普通用户不泄露机制", OWNER not in h4 and "身份验证" not in h4 and config.OWNER_SUBJECT["welcome"] not in h4)
finally:
    a = accounts.load_accounts()
    for n in [OWNER, "路人甲"]:
        a.pop(n, None)
        _clear_gg(n)
    accounts.save_accounts(a)
    print("   (已清理测试账号)")

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
