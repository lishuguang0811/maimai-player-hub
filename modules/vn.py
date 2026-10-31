# -*- coding: utf-8 -*-
"""
vn.py —— 《SECRET ARCHIVE》视觉小说 UI（VIP 专属空间）

三种子视图（session_state["gg_view"]）：lobby(主页) / story(剧情) / gallery(图鉴)。
剧情数据来自 data/story.json，引擎在 modules/galgame.py，信件 data/letter.md。
打字机为"点击显示全文"近似；自动播放用 st.fragment 定时推进；不伪造任何状态。
"""
from __future__ import annotations

import random

import streamlit as st

import config
from modules import galgame

SPR = config.DATA_DIR / "sprites"

VN_CSS = """
<style>
.vnscene{height:150px;border-radius:16px;margin:8px 0 14px;position:relative;overflow:hidden;
  border:1px solid rgba(255,255,255,.08);}
.vnscene .vntag{position:absolute;left:16px;bottom:12px;color:#eaf6f5;font-size:.8rem;
  background:rgba(0,0,0,.35);padding:3px 10px;border-radius:8px;}
.vnbox{border:1px solid color-mix(in srgb,var(--miku) 40%,transparent);border-radius:14px;
  padding:16px 20px;background:rgba(13,18,24,.86);min-height:120px;}
.vnspeaker{color:var(--miku);font-weight:700;font-size:.95rem;margin-bottom:8px;letter-spacing:1px;}
.vntext{color:#eef4f4;font-size:1.05rem;line-height:1.9;white-space:pre-line;}
.vnflash{position:fixed;inset:0;background:rgba(57,197,187,.18);pointer-events:none;
  animation:vnflash 1.2s ease-out;}
@keyframes vnflash{0%{opacity:.9}100%{opacity:0}}
.vnchoice{margin:4px 0;}
.vndim{color:#7f8f96;}
.vnp{position:absolute;bottom:-8px;width:6px;height:6px;border-radius:50%;background:var(--miku);opacity:.7;animation:vnrise 6s linear infinite;}
@keyframes vnrise{0%{transform:translateY(0);opacity:0}12%{opacity:.85}100%{transform:translateY(-170px);opacity:0}}
</style>
"""

BG_STYLE = {
    "teal": "linear-gradient(135deg,#0d2b2a,#134e4a 60%,#0d1117)",
    "star": "radial-gradient(120% 120% at 50% 0%,#1b2a4a,#0a0e1a 70%)",
    "dark": "linear-gradient(160deg,#101418,#0a0d11)",
    "cyber": "linear-gradient(135deg,#1a1030,#2a1650 55%,#0d1117)",
    "pink": "linear-gradient(135deg,#2a1020,#4a1830 55%,#120a10)",
    "dawn": "linear-gradient(180deg,#2a3550,#3a5a6a 55%,#1a3a3a)",
}
BG_LABEL = {"teal": "青绿 · 主界面", "star": "星空 · 档案入口", "dark": "暗室 · 档案深处",
            "cyber": "赛博 · 隐藏程序", "pink": "心跳 · 幻想线", "dawn": "黎明 · 终章"}


def _toast_newly():
    newly = st.session_state.pop("gg_newly", [])
    for a in newly:
        st.success(f"🏆 成就解锁：{a}")


def render_gallery(user):
    st.markdown(VN_CSS, unsafe_allow_html=True)
    st.markdown("### 📚 剧情图鉴 · SECRET ARCHIVE")
    if st.button("← 返回剧情"):
        st.session_state["gg_view"] = "story"; st.rerun()
    st.markdown("#### 🏆 成就")
    for a in galgame.achievements_view(user):
        if a["unlocked"]:
            st.markdown(f"<div class='egg'><b>{a['id']}</b>　<span class='vndim'>[{a['rarity']}]</span><br>"
                        f"{a['desc']}　·　获得于 {a['unlocked'][:19]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='egg' style='opacity:.5'><b>？？？</b>　<span class='vndim'>[{a['rarity']}]</span><br>"
                        f"尚未解锁</div>", unsafe_allow_html=True)
    st.markdown("#### 🎬 结局")
    for e in galgame.endings_view(user):
        if e["unlocked"]:
            st.markdown(f"<div class='egg'><b>{e['id']} · {e['title']}</b>　<span class='vndim'>[{e['rarity']}]</span><br>"
                        f"解锁于 {e['unlocked'][:19]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='egg' style='opacity:.5'><b>{e['id']} · ？？？</b>　<span class='vndim'>[{e['rarity']}]</span><br>"
                        f"尚未解锁</div>", unsafe_allow_html=True)


def render_story(user):
    st.markdown(VN_CSS, unsafe_allow_html=True)
    node = galgame.current(user) or galgame.start(user)
    _toast_newly()
    if node.get("effect") == "flash":
        st.markdown("<div class='vnflash'></div>", unsafe_allow_html=True)
    # 场景背景（含可选青绿粒子）
    parts = ""
    if st.session_state.get("gg_particles", True):
        rng = random.Random((hash(node["id"]) & 0xffff))
        parts = "".join(
            f"<span class='vnp' style='left:{rng.randint(2,98)}%;animation-delay:{rng.uniform(0,6):.1f}s;"
            f"animation-duration:{rng.uniform(4,8):.1f}s'></span>" for _ in range(14))
    st.markdown(f"<div class='vnscene' style='background:{BG_STYLE.get(node.get('bg','teal'))}'>{parts}"
                f"<div class='vntag'>{node.get('chapter','')} · {BG_LABEL.get(node.get('bg','teal'),'')}</div></div>",
                unsafe_allow_html=True)
    # 立绘 + 对话框
    spk = node.get("speaker", "")
    sprite = SPR / "miku_bust.png" if spk in ("ARCHIVE", "系统") else None
    text = (node.get("text") or "")
    dialog_html = (f"<div class='vnbox'><div class='vnspeaker'>{spk}</div>"
                   f"<div class='vntext'>{text}</div></div>")
    if sprite and sprite.exists():
        _cl, _cr = st.columns([1, 3])
        from PIL import Image as _PIL
        _im = _PIL.open(sprite)
        _im.thumbnail((260, 260))
        _cl.image(_im)
        _cr.markdown(dialog_html, unsafe_allow_html=True)
    else:
        st.markdown(dialog_html, unsafe_allow_html=True)

    kind = node.get("kind", "line")
    if kind == "birthday":
        ans = st.text_input("输入你的生日（YYYY-MM-DD）", key="gg_bday")
        if st.button("确认", key="gg_bday_ok", type="primary"):
            n, newly, okb = galgame.check_birthday(user, ans)
            st.session_state["gg_newly"] = newly
            if not okb:
                st.warning("……不对哦。再想想。")
            st.rerun()
    elif kind == "choice":
        for i, ch in enumerate(node.get("choices", [])):
            if st.button(ch["label"], key=f"ggc_{node['id']}_{i}", width="stretch"):
                n, newly = galgame.choose(user, i)
                st.session_state["gg_newly"] = newly; st.rerun()
    elif kind == "letter":
        st.markdown(galgame.load_letter())
        c = st.columns(3)
        if c[0].button("再读一遍"):
            st.rerun()
        if c[1].button("返回播放器"):
            st.session_state["gg_view"] = "lobby"; st.session_state["page"] = "tracks"; st.rerun()
        if c[2].button("回忆模式"):
            st.session_state["gg_view"] = "gallery"; st.rerun()
    else:  # line
        if st.button("继续 ▶", key="gg_next", type="primary", width="stretch"):
            n, newly = galgame.go(user, node.get("next"))
            st.session_state["gg_newly"] = newly; st.rerun()

    # 自动播放
    if st.checkbox("▶ 自动播放", key="gg_auto"):
        if node.get("kind") == "line" and node.get("next"):
            @st.fragment(run_every="3s")
            def _auto():
                cur = galgame.current(user)
                if cur and cur.get("kind") == "line" and cur.get("next"):
                    n, newly = galgame.go(user, cur["next"])
                    st.session_state["gg_newly"] = newly; st.rerun()
            _auto()

    # 工具栏
    st.write("")
    st.checkbox("✨ 粒子特效", key="gg_particles", value=st.session_state.get("gg_particles", True))
    tb = st.columns([1, 1, 1, 1, 1, 1])
    if tb[0].button("⏩ 跳过已读"):
        galgame.skip_read(user); st.rerun()
    with tb[1].popover("📜 历史"):
        for h in galgame.history(user):
            st.markdown(f"<div class='note'><b>{h['speaker']}</b>：{h['text']}</div>", unsafe_allow_html=True)
    with tb[2].popover("💾 存档"):
        for s in (1, 2, 3):
            if st.button(f"存到槽位 {s}", key=f"ggs_{s}"):
                galgame.save_slot(user, s); st.success(f"已存到槽位 {s}")
    with tb[3].popover("📂 读档"):
        for s in (1, 2, 3):
            if st.button(f"读取槽位 {s}", key=f"ggl_{s}"):
                if galgame.load_slot(user, s):
                    st.rerun()
                else:
                    st.caption(f"槽位 {s} 为空")
    if tb[4].button("📚 图鉴"):
        st.session_state["gg_view"] = "gallery"; st.rerun()
    if tb[5].button("🏠 私人空间主页"):
        st.session_state["gg_view"] = "lobby"; st.rerun()
    pr = galgame.progress(user)
    st.markdown(f"<div class='note'>进度：已读 {pr['read']}/{pr['total']} 节点 · "
                f"成就 {pr['ach']} · 结局 {pr['endings']}</div>", unsafe_allow_html=True)


def render_lobby(user):
    from datetime import datetime
    from modules import owner
    st.markdown(VN_CSS, unsafe_allow_html=True)
    sub = config.OWNER_SUBJECT
    now = datetime.now()
    if owner.is_birthday(now):
        st.balloons(); st.snow()
        st.markdown(f"<div class='bdaybar'>🎂 生日快乐，{sub['name']}！今天 {owner.age(now)} 岁 🎉</div>",
                    unsafe_allow_html=True)
    likes_html = "".join(f"<span class='badge'>{x}</span>" for x in sub["likes"])
    st.markdown(f"<div class='hero'><div class='name'>{sub['name']} 的专属空间</div>"
                f"<div class='meta'>{sub['welcome']}</div><div style='margin-top:8px'>{likes_html}</div></div>",
                unsafe_allow_html=True)
    pr = galgame.progress(user)
    c = st.columns(3)
    c[0].metric("剧情进度", f"{pr['read']}/{pr['total']}")
    c[1].metric("成就", pr["ach"])
    c[2].metric("结局", pr["endings"])
    st.write("")
    b1, b2, b3 = st.columns(3)
    if b1.button("▶ 进入《SECRET ARCHIVE》", type="primary", width="stretch"):
        st.session_state["gg_view"] = "story"; st.rerun()
    if b2.button("📚 剧情图鉴", width="stretch"):
        st.session_state["gg_view"] = "gallery"; st.rerun()
    if b3.button("🎵 返回播放器", width="stretch"):
        st.session_state["page"] = "tracks"; st.rerun()


def render(user):
    st.session_state.setdefault("gg_view", "lobby")
    view = st.session_state["gg_view"]
    if view == "story":
        render_story(user)
    elif view == "gallery":
        render_gallery(user)
    else:
        render_lobby(user)