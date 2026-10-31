# -*- coding: utf-8 -*-
"""
app.py —— MAIMAI PLAYER HUB（减法式重构 + 音乐系统）

五页导航：首页 / 曲目与收藏 / 练习与成绩 / 私人空间 / 我的与设置。
已移除：每日天气推荐词、地图、每币价格、最近/附近机台与距离（按需求彻底删除）。
保留：账号注册登录、私人空间身份验证、收藏、练习成绩、攻略、名言、分享图、主题切换、BGM。

音乐系统：统一播放状态(session) + 音源适配器(本地原创BGM可播放 / 舞萌曲库仅展示+来源链接 /
SoundCloud 未配置密钥时明确提示不伪装)。紧凑迷你播放器 + 完整播放器。
"""
from __future__ import annotations

import random
import time
from datetime import date, datetime

import streamlit as st
import streamlit.components.v1 as components

import config
from modules import (accounts, arcade_map, background, easter_egg, guides, music,
                     quotes, recommend, settings, share_card, songs,
                     userdata, vip, weather)

accounts.ensure_admin()

st.set_page_config(page_title="MAIMAI PLAYER HUB", page_icon="🎧",
                   layout="wide", initial_sidebar_state="auto")

THEMES = {"初音青绿": "#39C5BB", "原创赛博": "#8b5cf6"}
CSS = """
<style>
:root{--miku:__ACCENT__;}
html,body,[class*="css"]{font-family:"Segoe UI","Microsoft YaHei",sans-serif;}
.stApp{background:linear-gradient(rgba(10,14,20,.70),rgba(10,14,20,.88)),url(__BG__);
  background-size:cover;background-position:center;background-attachment:fixed;}
h1,h2,h3,h4{color:#e8f6f5 !important;letter-spacing:.4px;}
.topbar{display:flex;align-items:center;gap:12px;margin-bottom:2px;}
.logo{width:42px;height:42px;border-radius:11px;background:linear-gradient(135deg,var(--miku),#155e58);
  display:flex;align-items:center;justify-content:center;font-size:22px;}
.hero{border:1px solid color-mix(in srgb,var(--miku) 35%,transparent);border-radius:14px;padding:14px 18px;
  background:rgba(18,24,31,.72);}
.hero .name{font-size:1.5rem;font-weight:700;color:var(--miku);}
.hero .meta{color:#a9b7bd;font-size:.88rem;margin-top:5px;line-height:1.6;}
.badge{display:inline-block;padding:2px 9px;margin:2px 5px 2px 0;border-radius:999px;
  border:1px solid color-mix(in srgb,var(--miku) 45%,transparent);color:#cdeeea;font-size:.78rem;}
.quote{border-left:3px solid #e36e96;padding:8px 14px;margin:6px 0;background:rgba(227,110,150,.08);
  border-radius:0 10px 10px 0;color:#f3dbe4;font-size:.92rem;line-height:1.6;}
.quote .src{color:#c79aab;font-size:.76rem;margin-top:3px;}
.bdaybar{border:1px solid rgba(232,146,190,.7);border-radius:12px;padding:12px 16px;
  background:linear-gradient(120deg,rgba(232,146,190,.22),rgba(57,197,187,.14));
  color:#ffd6ec;font-size:1.1rem;font-weight:800;margin-bottom:10px;text-align:center;}
.msong{border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:11px 13px;
  background:rgba(18,24,31,.76);margin-bottom:10px;}
.msong.miku{border-color:color-mix(in srgb,var(--miku) 55%,transparent);background:color-mix(in srgb,var(--miku) 8%,rgba(18,24,31,.76));}
.mrow1{display:flex;justify-content:space-between;gap:10px;align-items:baseline;}
.mtitle{font-size:1rem;font-weight:700;color:#fff;word-break:break-all;line-height:1.3;}
.martist{color:#9fb0b6;font-size:.76rem;white-space:nowrap;}
.mchips{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0 6px;}
.chip{padding:2px 8px;border-radius:6px;font-size:.76rem;font-weight:700;}
.chip.off{background:#2a3138;color:#6b7680;}
.mmeta{color:#8d9aa1;font-size:.75rem;}
.mtip{color:#c6d2d7;font-size:.8rem;line-height:1.5;margin-top:6px;border-top:1px dashed rgba(255,255,255,.12);padding-top:6px;}
.mlink{margin-top:7px;}
.mlink a{color:var(--miku);text-decoration:none;font-size:.82rem;font-weight:600;}
.mlink a:hover{text-decoration:underline;}
.egg{border-left:3px solid var(--miku);padding:9px 13px;margin-bottom:9px;background:color-mix(in srgb,var(--miku) 9%,transparent);
  border-radius:0 10px 10px 0;color:#dbe7ea;font-size:.88rem;line-height:1.6;}
.egg b{color:#fff;}
.gcard{border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:11px 15px;background:rgba(18,24,31,.72);margin-bottom:9px;}
.gcard .gt{font-weight:700;color:#fff;font-size:.93rem;}
.gcard .gb{color:#c6d2d7;font-size:.83rem;line-height:1.6;margin-top:4px;}
.vipframe{border:1px solid rgba(232,146,190,.5);border-radius:16px;padding:20px;background:rgba(18,24,31,.82);max-width:560px;margin:24px auto;}
.miniplayer{position:sticky;bottom:0;border-top:1px solid color-mix(in srgb,var(--miku) 30%,transparent);
  background:rgba(13,17,23,.92);backdrop-filter:blur(6px);padding:8px 14px;border-radius:12px 12px 0 0;margin-top:16px;}
.kind{display:inline-block;padding:1px 7px;border-radius:5px;font-size:.7rem;font-weight:700;}
.kind.full{background:#1f6f4a;color:#d8ffe9;} .kind.info{background:#3a4149;color:#c2ccd2;}
.note{color:#9aa7ad;font-size:.76rem;line-height:1.6;}
.warn{color:#f2c14e;font-size:.84rem;}
div[data-testid="stMetricValue"]{color:var(--miku);}
button[data-testid="stBaseButton-header"]{display:none !important;}
@media(max-width:700px){.hero .name{font-size:1.25rem;}.mtitle{font-size:.94rem;}
  .block-container{padding-left:12px !important;padding-right:12px !important;}}
</style>
"""


def bg_pool():
    pool = []
    for d in (config.BG_DIR, config.MIKU_DIR):
        if d.exists():
            pool += sorted(d.glob("*.jpg")) + sorted(d.glob("*.png"))
    return pool


def current_bg_uri():
    if "bg_uri" not in st.session_state:
        background.ensure_backgrounds()
        pool = bg_pool(); path = random.choice(pool) if pool else None
        st.session_state["bg_uri"] = background.to_data_uri(path) if path else ""
        st.session_state["bg_name"] = path.name if path else "无"
    return st.session_state["bg_uri"]


def css_html(accent):
    return CSS.replace("__BG__", current_bg_uri()).replace("__ACCENT__", accent)


NEUTRAL_THEME = {"key": "steady", "name": "标准节奏", "line": "", "color": "#39C5BB"}


@st.cache_data(show_spinner=False)
def cached_snapshot():
    return songs.load_snapshot()


def ensure_snapshot():
    snap = cached_snapshot()
    if snap is None:
        with st.spinner("首次运行：正在抓取真实曲库（约 1 MB）…"):
            res = songs.refresh_songs()
        if res.get("ok"):
            cached_snapshot.clear(); snap = cached_snapshot()
        else:
            st.error(f"曲库抓取失败：{res.get('error')}")
    return snap


def maimai_card(sv, tip=""):
    chips = []
    for diff in config.DIFF_ORDER:
        meta = config.DIFF_META[diff]; d = sv["diffs"].get(diff)
        chips.append(f"<span class='chip' style='background:{meta['color']};color:{meta['text']}'>{meta['short']} {d['level']}</span>"
                     if d else f"<span class='chip off'>{meta['short']} —</span>")
    miku = "　<span style='color:var(--miku);font-weight:700'>★ MIKU/世界计划</span>" if sv["is_miku"] else ""
    link = songs.bilibili_link(sv["title"])
    tip_html = f"<div class='mtip'>💡 {tip}</div>" if tip else ""
    return f"""<div class='msong{' miku' if sv['is_miku'] else ''}'>
      <div class='mrow1'><span class='mtitle'>{sv['title']}</span><span class='martist'>{sv['artist'] or ''}</span></div>
      <div class='mchips'>{''.join(chips)}</div>
      <div class='mmeta'>最高定数 {sv['max_ds']:.1f} · BPM {sv['bpm'] or '—'} · {sv['genre'] or '—'}{miku}</div>
      {tip_html}<div class='mlink'><a href='{link}' target='_blank'>📺 B站搜谱面确认视频</a></div></div>"""


def song_view(song):
    return {"title": song["title"], "artist": song["artist"], "genre": song["genre"],
            "bpm": song["bpm"], "max_ds": song["ds"], "is_miku": songs.is_miku_related(song),
            "diffs": {song["diff"]: {"level": song["level"], "ds": song["ds"]}}}


# ---------------- 音乐播放器 ----------------
def mstate():
    return st.session_state.setdefault("music", music.new_state())


def track_row(tr, uname, compact=False):
    kind_cls = "full" if tr["playable"] else "info"
    kind_txt = {"full": "可播放", "embed": "官方嵌入", "preview": "官方试听", "info": "仅展示"}.get(tr["play_kind"], tr["play_kind"])
    dur = f" · {tr['duration']}" if tr.get("duration") else ""
    st.markdown(f"<div class='msong'><div class='mrow1'><span class='mtitle'>{tr['title']}</span>"
                f"<span class='martist'>{tr['artist'] or ''}</span></div>"
                f"<div class='mmeta'>{tr['source']}{dur}　<span class='kind {kind_cls}'>{kind_txt}</span></div></div>",
                unsafe_allow_html=True)
    cols = st.columns([1, 1, 2])
    if tr["playable"]:
        if cols[0].button("▶ 播放", key=f"play_{tr['id']}"):
            st.session_state["music"] = music.play_now(mstate(), tr); st.rerun()
    else:
        cols[0].markdown(f"<div class='mlink'><a href='{tr['url']}' target='_blank'>↗ 来源</a></div>", unsafe_allow_html=True)
    if cols[1].button("＋ 队列", key=f"q_{tr['id']}"):
        st.session_state["music"] = music.add_to_queue(mstate(), tr); st.rerun()
    if userdata.is_favorite(uname, tr["title"]):
        if cols[2].button("💔 取消收藏", key=f"fv_{tr['id']}"):
            userdata.remove_favorite(uname, tr["title"]); st.rerun()
    else:
        if cols[2].button("⭐ 收藏", key=f"fv_{tr['id']}"):
            userdata.add_favorite(uname, {"title": tr["title"], "artist": tr["artist"],
                                          "ds": None, "diff": "", "genre": ""}); st.rerun()


def render_now_playing(uname):
    st_ = mstate(); cur = music.current(st_)
    st.markdown("#### ▶ 正在播放")
    if not cur:
        st.caption("队列为空。搜索后点「▶ 播放」或「＋ 队列」。")
        return
    kind_txt = {"full": "可播放", "embed": "官方嵌入", "preview": "官方试听", "info": "仅展示"}.get(cur["play_kind"], "")
    st.markdown(f"<div class='hero'><div class='name' style='font-size:1.15rem'>{cur['title']}</div>"
                f"<div class='meta'>{cur['artist'] or ''} · 来源 {cur['source']} · <span class='kind {'full' if cur['playable'] else 'info'}'>{kind_txt}</span></div></div>",
                unsafe_allow_html=True)
    if cur["play_kind"] == "embed" and cur.get("embed_url"):
        st.iframe(cur["embed_url"], height=360)   # 官方嵌入，YouTube 自带控件
        st.markdown(f"<div class='note'>官方嵌入播放器（由 YouTube 控制 播放/暂停/进度/音量）。"
                    f"若无法播放（视频禁止嵌入 / 地区限制 / 网络失败），"
                    f"<a href='{cur['url']}' target='_blank' style='color:var(--miku)'>↗ 在 YouTube 官方页面打开</a>。</div>",
                    unsafe_allow_html=True)
    elif cur["playable"] and cur.get("file"):
        if st_.get("muted"):
            st.info("🔇 已静音（点下方取消静音恢复播放）")
        else:
            st.audio(cur["file"])     # 原生 播放/暂停/进度/音量
        _mm = st.columns([1, 3])
        if _mm[0].button("🔊 取消静音" if st_.get("muted") else "🔇 静音", key="mute_btn"):
            st.session_state["music"] = music.toggle_mute(st_); st.rerun()
        _mm[1].caption("状态：播放中 · 用播放器控件 播放/暂停/拖动/音量")
    else:
        st.markdown(f"<div class='note'>本曲无可用音频授权，不能在本程序播放。"
                    f"<a href='{cur.get('url','#')}' target='_blank' style='color:var(--miku)'>↗ 前往官方来源播放</a></div>",
                    unsafe_allow_html=True)
        st.caption("状态：无播放权限（仅展示曲目信息）")
    c = st.columns([1, 1, 1, 2])
    if c[0].button("⏮ 上一首"):
        st.session_state["music"] = music.prev_track(st_); st.rerun()
    mode_label = {"list": "🔁 列表循环", "one": "🔂 单曲循环", "shuffle": "🔀 随机"}[st_.get("mode", "list")]
    if c[1].button(mode_label):
        nxt = {"list": "one", "one": "shuffle", "shuffle": "list"}[st_.get("mode", "list")]
        st.session_state["music"] = music.set_mode(st_, nxt); st.rerun()
    if c[2].button("⏭ 下一首"):
        st.session_state["music"] = music.next_track(st_); st.rerun()
    c[3].caption(f"队列 {len(st_.get('queue', []))} 首 · 第 {st_.get('index', 0) + 1} 首")
    q = st_.get("queue", [])
    if q:
        with st.expander(f"播放队列（{len(q)}）"):
            for i, t in enumerate(q):
                qc = st.columns([5, 1, 1])
                mark = "▶ " if i == st_.get("index") else "　"
                qc[0].markdown(f"<div class='note'>{mark}{i+1}. {t['title']} <span style='color:#6b7680'>({t['source']})</span></div>",
                               unsafe_allow_html=True)
                if qc[1].button("播", key=f"qp_{i}"):
                    ns = dict(st_); ns["index"] = i; ns["status"] = "playing" if t["playable"] else "info"
                    st.session_state["music"] = ns; st.rerun()
                if qc[2].button("✕", key=f"qr_{i}"):
                    nq = [x for j, x in enumerate(q) if j != i]
                    ns = dict(st_); ns["queue"] = nq
                    ns["index"] = min(ns.get("index", 0), max(0, len(nq) - 1))
                    st.session_state["music"] = ns; st.rerun()


def render_mini_player(uname):
    st_ = mstate(); cur = music.current(st_)
    with st.container():
        st.markdown("<div class='miniplayer'>", unsafe_allow_html=True)
        if cur:
            mc = st.columns([4, 1, 1, 2])
            mc[0].markdown(f"<div class='note' style='color:#e8f6f5'>🎵 <b>{cur['title']}</b> "
                           f"<span style='color:#8d9aa1'>· {cur['source']}</span></div>", unsafe_allow_html=True)
            if mc[1].button("⏮", key="mini_prev"):
                st.session_state["music"] = music.prev_track(st_); st.rerun()
            if mc[2].button("⏭", key="mini_next"):
                st.session_state["music"] = music.next_track(st_); st.rerun()
            if mc[3].button("打开完整播放器 →", key="mini_open"):
                st.session_state["page"] = "tracks"; st.rerun()
        else:
            mc = st.columns([5, 2])
            mc[0].markdown("<div class='note'>🎵 未在播放</div>", unsafe_allow_html=True)
            if mc[1].button("打开完整播放器 →", key="mini_open2"):
                st.session_state["page"] = "tracks"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


APP_NAME = settings.get_app_name()
for k, v in {"user": None, "vip": False, "vip_verify": False, "vip_verify_name": None, "page": "home"}.items():
    st.session_state.setdefault(k, v)
# ================= 私人空间身份验证页 =================
def render_vip_verify():
    name = st.session_state.get("vip_verify_name") or config.OWNER_NAME
    st.markdown(css_html("#39C5BB"), unsafe_allow_html=True)
    st.markdown("<div class='vipframe'>", unsafe_allow_html=True)
    st.markdown("#### 确认一下，你是不是那位熟悉的人？")
    st.caption("完成几个小问题，解锁专属的音乐空间。（知识问答仅为额外验证，不保证真实身份）")
    if st.button("← 跳过，返回普通模式"):
        st.session_state["vip_verify"] = False; st.rerun()
    if not vip.is_configured():
        st.warning("身份验证问题尚未配置。请运行 `python work/make_vip_answers.py` 设置后再来。")
        st.markdown("</div>", unsafe_allow_html=True); st.stop()
    lock_until = st.session_state.get("vip_lock", 0)
    if time.time() < lock_until:
        st.error(f"尝试次数过多，请 {int(lock_until - time.time())} 秒后再试。")
        st.markdown("</div>", unsafe_allow_html=True); st.stop()
    qtexts = vip.question_texts()
    answers = [st.text_input(f"问题 {i+1}：{q}", type="password", key=f"vq_{i}") for i, q in enumerate(qtexts)]
    if st.button("提交验证", type="primary", width="stretch"):
        if vip.verify_answers(answers):
            accounts.grant_vip(name)
            st.session_state["user"] = accounts.find_account(name)[1]
            st.session_state["vip"] = True; st.session_state["vip_verify"] = False
            st.session_state.pop("vip_fail", None); st.session_state.pop("vip_lock", None)
            st.success("验证通过，VIP 已开通！"); st.rerun()
        else:
            fails = st.session_state.get("vip_fail", 0) + 1
            st.session_state["vip_fail"] = fails
            if fails >= config.VIP_MAX_FAILS:
                st.session_state["vip_lock"] = time.time() + config.VIP_LOCK_SECONDS
                st.session_state["vip_fail"] = 0; st.error("尝试次数过多，已临时锁定。")
            else:
                st.error("验证未通过，请稍后再试。")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


if st.session_state.get("vip_verify"):
    render_vip_verify()

# ================= 未登录：登录/注册/找回 =================
if st.session_state["user"] is None:
    st.markdown(css_html("#39C5BB"), unsafe_allow_html=True)
    st.markdown(f"<div class='topbar'><div class='logo'>🎧</div><h1 style='margin:0'>{APP_NAME}</h1></div>", unsafe_allow_html=True)
    st.write("")
    tab_login, tab_reg, tab_rec = st.tabs(["🔑 登录", "📝 注册", "🔑 找回密码"])
    with tab_login:
        with st.form("login_form"):
            li_name = st.text_input("账号名 / 手机号")
            li_pwd = st.text_input("密码", type="password")
            if st.form_submit_button("登录", type="primary", width="stretch"):
                ok, msg, acc = accounts.login(li_name, li_pwd)
                if ok:
                    st.session_state["user"] = acc; st.success(msg); st.rerun()
                else:
                    st.error(msg)
    with tab_reg:
        with st.form("reg_form"):
            rg_name = st.text_input("用户名")
            c1, c2 = st.columns(2)
            rg_pwd = c1.text_input("密码", type="password", help=f"至少 {config.PW_MIN_LEN} 位，含数字+大写+小写")
            rg_pwd2 = c2.text_input("确认密码", type="password")
            rg_phone = st.text_input("手机号（可选，可登录/找回）")
            d1, d2 = st.columns(2)
            rg_bday = d1.date_input("生日（可选，找回要用）", value=None,
                                    min_value=date(config.BIRTH_MIN_YEAR, 1, 1),
                                    max_value=date(config.BIRTH_MAX_YEAR, 12, 31))
            rg_city = d2.text_input("常驻城市", value=config.DEFAULT_CITY["name"])
            rg_level = st.selectbox("等级", config.LEVEL_ORDER, index=config.LEVEL_ORDER.index(config.DEFAULT_LEVEL))
            rg_hobbies = st.multiselect("爱好（用于筛歌）",
                ["初音未来", "VOCALOID/术力口", "世界计划", "东方Project", "音击/中二节奏", "动漫", "50 Cent"])
            if st.form_submit_button("注册", type="primary", width="stretch"):
                if rg_pwd != rg_pwd2:
                    st.error("两次输入的密码不一致。")
                else:
                    ok, msg = accounts.register(rg_name, rg_pwd,
                        rg_bday.strftime("%Y-%m-%d") if rg_bday else None,
                        rg_city, rg_level, rg_hobbies, "", rg_phone)
                    if ok:
                        if accounts.is_owner_name(rg_name):
                            st.session_state["vip_verify"] = True
                            st.session_state["vip_verify_name"] = rg_name.strip()
                            st.rerun()
                        else:
                            _, _, acc = accounts.login(rg_name, rg_pwd)
                            st.session_state["user"] = acc; st.success(msg); st.rerun()
                    else:
                        st.error(msg)
    with tab_rec:
        st.caption("凭「账号名/手机号 + 注册时填的生日」找回，本地核验。")
        with st.form("rec_form"):
            rc_id = st.text_input("账号名 / 手机号")
            rc_bday = st.date_input("注册时填的生日", value=None,
                                    min_value=date(config.BIRTH_MIN_YEAR, 1, 1),
                                    max_value=date(config.BIRTH_MAX_YEAR, 12, 31))
            rc_pwd = st.text_input("新密码", type="password", help=f"至少 {config.PW_MIN_LEN} 位，含数字+大写+小写")
            if st.form_submit_button("重置密码", type="primary", width="stretch"):
                ok, msg = accounts.reset_password(rc_id, rc_bday.strftime("%Y-%m-%d") if rc_bday else "", rc_pwd)
                (st.success if ok else st.error)(msg)
    st.stop()


user = st.session_state["user"]
uname = user["name"]
level = user.get("level", config.DEFAULT_LEVEL)
hobbies = user.get("hobbies", [])
today = date.today()
user_is_vip = accounts.is_vip(user)
user_pending = user.get("vip_status") == "pending"
theme_pref = userdata.get_pref(uname, "theme", "初音青绿")
accent = THEMES.get(theme_pref, "#39C5BB")
st.markdown(css_html(accent), unsafe_allow_html=True)
_tb = st.columns([1, 7, 3])
with _tb[0]:
    if st.button("🎧", key="logo_btn", help=" "):
        st.session_state["logo_clicks"] = st.session_state.get("logo_clicks", 0) + 1
        if st.session_state["logo_clicks"] >= 5:
            st.session_state["logo_clicks"] = 0; st.session_state["show_egg"] = True
with _tb[1]:
    st.markdown(f"<h1 style='margin:0'>{APP_NAME}</h1>", unsafe_allow_html=True)
with _tb[2]:
    st.markdown(f"<div class='note' style='text-align:right'>{uname}{'　💎VIP' if user_is_vip else ''}</div>",
                unsafe_allow_html=True)
if st.session_state.get("show_egg"):
    st.success("🎁 被你发现了：谢谢你打开这个小小的音乐空间。愿每一首歌，都刚好是你今天想听的那首。")
    st.session_state["show_egg"] = False

snap = ensure_snapshot()
records = songs.flatten(snap) if snap else []
source = music.MusicSource(records)

PAGE_KEY = {"首页": "home", "曲目与收藏": "tracks", "练习与成绩": "practice",
            "我的与设置": "me", "私人空间": "vip", "🔐 完成验证": "vip"}


def _nav_label(page):
    if page == "vip":
        return "私人空间" if user_is_vip else "🔐 完成验证"
    return {"home": "首页", "tracks": "曲目与收藏", "practice": "练习与成绩",
            "me": "我的与设置"}.get(page, "首页")


PAGES = ["首页", "曲目与收藏", "练习与成绩"]
if user_is_vip:
    PAGES.append("私人空间")
elif user_pending:
    PAGES.append("🔐 完成验证")
PAGES.append("我的与设置")
_cur = st.session_state.get("page", "home")
if _cur == "vip" and not (user_is_vip or user_pending):
    _cur = "home"; st.session_state["page"] = "home"
with st.sidebar:
    _lbl = _nav_label(_cur)
    if _lbl not in PAGES:
        _lbl = "首页"
    nav = st.radio("导航", PAGES, index=PAGES.index(_lbl), key="nav_radio")
    st.session_state["page"] = PAGE_KEY[nav]
    st.divider()
    if st.button("🚪 退出登录", width="stretch"):
        st.session_state["user"] = None; st.session_state["vip"] = False
        st.session_state["page"] = "home"; st.rerun()


def page_home():
    if not userdata.get_pref(uname, "seen_guide", False):
        with st.expander("👋 首次使用引导", expanded=True):
            st.markdown("1️⃣ 「曲目与收藏」里搜本地原创 BGM 直接播放，或粘贴 YouTube 链接用官方嵌入播放。\n"
                        "2️⃣ 收藏喜欢的歌 → 加入练习清单 → 在「练习与成绩」手动记录成绩。\n"
                        "3️⃣ 「我的与设置」切换主题、改密码、下载数据备份。\n"
                        "4️⃣ 连点左上角 🎧 五次，有个小惊喜。")
            if st.button("我知道了，不再显示", key="guide_ok"):
                userdata.set_pref(uname, "seen_guide", True); st.rerun()
    _miku = []
    if config.MIKU_DIR.exists():
        _miku = sorted(config.MIKU_DIR.glob("*.jpg")) + sorted(config.MIKU_DIR.glob("*.png"))
    if _miku:
        st.image(str(random.Random(today.toordinal()).choice(_miku)), width="stretch")
    st.markdown(f"<div class='hero'><div class='name'>你好，{uname}</div>"
                f"<div class='meta'>{config.PRIVATE_TITLE if user_is_vip else '今天想听点什么？'}<br>"
                f"等级 {level} · {user.get('city', '—')}</div></div>", unsafe_allow_html=True)
    qi = st.session_state.get("quote_idx", 0); st.session_state["quote_idx"] = qi + 1
    q = quotes.pick_quote(qi)
    if q:
        st.markdown(f"<div class='quote'>“{q['text']}”<div class='src'>—— {q.get('speaker','')}《{q.get('work','')}》({q.get('year','')})</div></div>",
                    unsafe_allow_html=True)
    st.write("")
    qe = st.columns(3)
    if qe[0].button("🎵 去听歌 / 搜曲", width="stretch", type="primary"):
        st.session_state["page"] = "tracks"; st.rerun()
    if qe[1].button("📋 练习与成绩", width="stretch"):
        st.session_state["page"] = "practice"; st.rerun()
    if user_is_vip:
        if qe[2].button("💿 私人空间", width="stretch"):
            st.session_state["page"] = "vip"; st.rerun()
    elif user_pending:
        if qe[2].button("🔐 完成验证", width="stretch"):
            st.session_state["page"] = "vip"; st.rerun()
    else:
        if qe[2].button("⚙️ 我的与设置", width="stretch"):
            st.session_state["page"] = "me"; st.rerun()
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("收藏", len(userdata.list_favorites(uname)))
    m2.metric("成绩", userdata.stats(uname)["count"])
    m3.metric("练习中", sum(1 for x in userdata.list_practice(uname) if x["status"] != "已完成"))
    m4.metric("曲库", snap.get("count", 0) if snap else 0)


def page_tracks():
    st.markdown("### 🎵 音乐播放器")
    with st.expander("🎬 粘贴 YouTube 链接/ID，用官方嵌入播放（无需任何密钥）"):
        yc = st.columns([3, 2, 1])
        yt_in = yc[0].text_input("YouTube 链接或 11 位视频 ID", key="yt_in")
        yt_title = yc[1].text_input("标题（可选，不填不伪造）", key="yt_title")
        if yc[2].button("加载播放器", key="yt_load"):
            _tr = music.track_from_youtube(yt_in, yt_title)
            if _tr:
                st.session_state["music"] = music.play_now(mstate(), _tr); st.rerun()
            else:
                st.error("仅支持 YouTube 官方链接或 11 位视频 ID；已拒绝嵌入任意网址。")
    sq = st.text_input("搜索本地原创 BGM / 舞萌曲库", key="music_q")
    st.markdown("<div class='note'>在线搜索需要平台 API 密钥，当前未配置，<b>不伪造搜索结果</b>。"
                "以下为本地原创 BGM 与舞萌曲库（真实、无需密钥）。要听 YouTube 上的歌，用上方「粘贴链接」或官方搜索入口。</div>",
                unsafe_allow_html=True)
    if sq:
        st.markdown(f"<div class='mlink'><a href='{music.youtube_search_url(sq)}' target='_blank'>↗ YouTube 官方搜索「{sq}」</a>　"
                    f"<a href='{songs.bilibili_link(sq)}' target='_blank'>↗ B 站搜索「{sq}」</a></div>", unsafe_allow_html=True)
    for n in source.configured_note():
        st.markdown(f"<div class='warn'>⚠ {n}</div>", unsafe_allow_html=True)
    results, has_more = source.search(sq, page=st.session_state.get("music_page", 1))
    if sq and not results:
        st.info("没有匹配的曲目。")
    for tr in results:
        track_row(tr, uname)
    if has_more:
        if st.button("加载更多"):
            st.session_state["music_page"] = st.session_state.get("music_page", 1) + 1; st.rerun()
    else:
        st.session_state["music_page"] = 1
    st.divider()
    render_now_playing(uname)
    st.divider()
    st.markdown("### 🕹️ 舞萌曲库（全难度 · 仅谱面信息）")
    lib = songs.song_select_view(records)
    fq, fc = st.columns([3, 2])
    qtext = fq.text_input("搜索曲名 / 艺术家", key="sel_q")
    only_miku = fc.checkbox("只看初音/世界计划", key="sel_miku")
    only_fav = st.checkbox("只看已收藏", key="sel_fav")
    fr = st.columns(3)
    genre_f = fr[0].multiselect("分类", sorted({r["genre"] for r in lib if r["genre"]}), key="sel_genre")
    diff_f = fr[1].selectbox("按难度筛选", ["全部"] + config.DIFF_ORDER, key="sel_diff")
    sort_f = fr[2].selectbox("排序", ["定数↓", "曲名", "BPM↓"], key="sel_sort")
    shown = lib
    if qtext.strip():
        k = qtext.strip().lower()
        shown = [s for s in shown if k in s["title"].lower() or k in (s["artist"] or "").lower()]
    if only_miku:
        shown = [s for s in shown if s["is_miku"]]
    if only_fav:
        _ft = {f["title"] for f in userdata.list_favorites(uname)}
        shown = [s for s in shown if s["title"] in _ft]
    if genre_f:
        shown = [s for s in shown if s["genre"] in genre_f]
    if diff_f != "全部":
        shown = [s for s in shown if diff_f in s["diffs"]]
    if sort_f == "定数↓":
        shown = sorted(shown, key=lambda x: -x["max_ds"])
    elif sort_f == "曲名":
        shown = sorted(shown, key=lambda x: x["title"])
    elif sort_f == "BPM↓":
        shown = sorted(shown, key=lambda x: -(x["bpm"] or 0))
    PAGE = 24; pages = max(1, (len(shown) + PAGE - 1) // PAGE)
    st.markdown(f"<div class='note'>共 {len(shown)} 首 · 绿黄红紫白全难度</div>", unsafe_allow_html=True)
    if not shown:
        st.info("没有匹配的曲目，试试清空筛选。")
    pg = st.number_input("页码", 1, pages, 1, key="sel_pg")
    lv_tip = settings.get_levels().get(level, {}).get("tip", "")
    for sv in shown[(pg - 1) * PAGE: pg * PAGE]:
        st.markdown(maimai_card(sv, tip=lv_tip), unsafe_allow_html=True)
        _fk = f"selfav_{sv['title']}"
        if userdata.is_favorite(uname, sv["title"]):
            if st.button("💔 取消收藏", key=_fk):
                userdata.remove_favorite(uname, sv["title"]); st.rerun()
        else:
            if st.button("⭐ 收藏", key=_fk):
                userdata.add_favorite(uname, {"title": sv["title"], "artist": sv["artist"],
                                              "ds": sv["max_ds"], "diff": "", "genre": sv["genre"]}); st.rerun()
    st.divider()
    st.markdown("### ⭐ 我的收藏")
    favs = userdata.list_favorites(uname)
    if favs:
        for fv in favs:
            cc = st.columns([4, 1, 1])
            cc[0].markdown(f"<div class='msong'><div class='mtitle'>{fv['title']}</div><div class='mmeta'>{fv.get('artist','')} · {fv.get('diff','')} {fv.get('ds','')}</div></div>", unsafe_allow_html=True)
            if cc[1].button("📋 练习", key=f"fp_{fv['title']}"):
                userdata.add_practice(uname, {"title": fv["title"], "diff": fv.get("diff", ""), "ds": fv.get("ds")}, "", "来自收藏")
                st.success("已加入练习清单。")
            if cc[2].button("移除", key=f"rm_{fv['title']}"):
                userdata.remove_favorite(uname, fv["title"]); st.rerun()
    else:
        st.caption("还没有收藏。")

def render_practice_scores(user):
    st.markdown("### 📋 练习清单")
    st.caption("计划练习 ≠ 真实成绩；完成后到下方「成绩记录」手动登记。")
    with st.form(f"prac_add_{user}"):
        pc = st.columns([3, 2, 2, 2])
        pa_title = pc[0].text_input("曲名")
        pa_diff = pc[1].selectbox("难度", config.DIFF_ORDER, key=f"pd_{user}")
        pa_ds = pc[2].number_input("定数", 1.0, 15.0, 12.0, 0.1, key=f"pds_{user}")
        pa_date = pc[3].date_input("计划日期", value=None, key=f"pdate_{user}")
        pa_note = st.text_input("备注（可选）", key=f"pnote_{user}")
        if st.form_submit_button("➕ 加入练习清单"):
            if pa_title.strip():
                userdata.add_practice(user, {"title": pa_title.strip(), "diff": pa_diff, "ds": pa_ds},
                                      pa_date.strftime("%Y-%m-%d") if pa_date else "", pa_note.strip())
                st.success("已加入。")
            else:
                st.warning("曲名不能为空。")
    for it in userdata.list_practice(user):
        row = st.columns([4, 2, 2, 1])
        row[0].markdown(f"<div class='msong' style='margin-bottom:6px'><div class='mtitle'>{it['title']}</div>"
                        f"<div class='mmeta'>{it.get('diff','')} 定数 {it.get('ds','')} · 计划 {it.get('planned_date') or '—'} · {it.get('note') or ''}</div></div>",
                        unsafe_allow_html=True)
        ns = row[1].selectbox("状态", ["未开始", "进行中", "已完成"],
                              index=["未开始", "进行中", "已完成"].index(it["status"]), key=f"ps_{user}_{it['id']}")
        ad = row[2].date_input("完成日期", value=None, key=f"pad_{user}_{it['id']}")
        if ns != it["status"]:
            userdata.set_practice_status(user, it["id"], ns, ad.strftime("%Y-%m-%d") if ad else "")
        if row[3].button("删", key=f"prm_{user}_{it['id']}"):
            userdata.remove_practice(user, it["id"]); st.rerun()
    st.markdown("### 🏆 成绩记录 <span class='note'>(手动录入，非官方同步)</span>",
                unsafe_allow_html=True)
    with st.form(f"score_add_{user}"):
        sc = st.columns([3, 2, 2, 2, 2])
        sa_title = sc[0].text_input("曲名", key=f"st_{user}")
        sa_diff = sc[1].selectbox("难度", config.DIFF_ORDER, key=f"sd_{user}")
        sa_ds = sc[2].number_input("定数", 1.0, 15.0, 13.0, 0.1, key=f"sds_{user}")
        sa_score = sc[3].number_input("分数", 0, 1010000, 0, key=f"ss_{user}")
        sa_ach = sc[4].number_input("达成率%", 0.0, 101.0, 0.0, 0.0001, key=f"sa_{user}")
        sc2 = st.columns([1, 1, 4])
        sa_fc = sc2[0].checkbox("FC", key=f"fc_{user}"); sa_ap = sc2[1].checkbox("AP", key=f"ap_{user}")
        sa_note = sc2[2].text_input("备注（可选）", key=f"sn_{user}")
        if st.form_submit_button("➕ 记录成绩"):
            if sa_title.strip():
                okk, msg = userdata.add_score(user, sa_title.strip(), sa_diff, sa_ds, sa_score, sa_ach, sa_fc, sa_ap, sa_note.strip())
                (st.success if okk else st.error)(msg)
            else:
                st.warning("曲名不能为空。")
    stt = userdata.stats(user)
    if stt["count"]:
        st.caption(f"共 {stt['count']} 条 · 平均达成率 {stt['avg_achievement']}% · FC {stt['fc']} · AP {stt['ap']} · 最高定数 {stt['max_ds']}")
    for s in userdata.list_scores(user):
        row = st.columns([5, 1])
        row[0].markdown(f"<div class='msong' style='margin-bottom:6px'><div class='mtitle'>{s['title']}</div>"
                        f"<div class='mmeta'>{s.get('diff','')} 定数 {s.get('ds','')} · 分数 {s.get('score')} · 达成率 {s.get('achievement')}%"
                        f"{' · FC' if s.get('fc') else ''}{' · AP' if s.get('ap') else ''} · {(s.get('date') or '')[:10]} · {s.get('source','')}</div></div>",
                        unsafe_allow_html=True)
        if row[1].button("删", key=f"srm_{user}_{s['id']}"):
            userdata.remove_score(user, s["id"]); st.rerun()


def page_practice():
    render_practice_scores(uname)


def page_vip():
    from modules import galgame, vn
    if not user_is_vip:
        st.markdown("<div class='vipframe'>", unsafe_allow_html=True)
        st.markdown("#### 💿 私人空间")
        if user_pending:
            st.caption("你的专属账号待验证。")
            if st.button("🔐 完成专属身份验证", type="primary"):
                st.session_state["vip_verify"] = True; st.session_state["vip_verify_name"] = uname; st.rerun()
        else:
            st.caption("此空间需要专属权限。")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    if not galgame.STORY_FILE.exists():
        st.info("私人空间还没有剧情数据。把 story.json 放到 data/ 后重新进入即可。")
        return
    vn.render(uname)


def page_me():
    st.markdown("### 👤 我的与设置")
    likes_html = "".join(f"<span class='badge'>{x}</span>" for x in hobbies) or "<span class='note'>未填写爱好</span>"
    st.markdown(f"<div class='hero'><div class='name'>{uname}</div><div class='meta'>生日：{user.get('birthday') or '—'}　|　"
                f"城市：{user.get('city', '—')}　|　等级：<b style='color:var(--miku)'>{level}</b>"
                f"{'　|　💎 VIP' if user_is_vip else ''}<br>{likes_html}</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎨 主题")
        themes = list(THEMES.keys())
        sel = st.radio("界面主题", themes, index=themes.index(theme_pref) if theme_pref in themes else 0)
        if sel != theme_pref:
            userdata.set_pref(uname, "theme", sel); st.rerun()
    with c2:
        st.markdown("#### 🎚️ 等级")
        nl = st.selectbox("切换等级", config.LEVEL_ORDER, index=config.LEVEL_ORDER.index(level))
        if nl != level:
            accounts.update_field(uname, level=nl); st.rerun()
    st.markdown("#### 🔒 修改密码")
    with st.form("chg_pw"):
        opw = st.text_input("原密码", type="password")
        npw = st.text_input("新密码（至少8位 数字+大写+小写）", type="password")
        if st.form_submit_button("修改密码"):
            okc, msgc = accounts.change_password(uname, opw, npw); (st.success if okc else st.error)(msgc)
    st.markdown("#### 💾 数据备份")
    if st.button("生成数据备份 (zip)", key="bk_gen"):
        import io as _io, zipfile as _zf
        _buf = _io.BytesIO()
        with _zf.ZipFile(_buf, "w", _zf.ZIP_DEFLATED) as _z:
            for _f in config.DATA_DIR.glob("*.json"):
                _z.write(_f, f"data/{_f.name}")
        st.session_state["_backup_bytes"] = _buf.getvalue()
    if st.session_state.get("_backup_bytes"):
        st.download_button("保存备份文件", data=st.session_state["_backup_bytes"],
                           file_name=f"maimai_hub_backup_{date.today()}.zip",
                           mime="application/zip", key="bk_dl")
    st.caption("恢复：解压覆盖 data/ 下同名 json 后重启。备份只含数据 json（不含可再生的图片/音频），密码为哈希不含明文。")
    if accounts.is_admin(uname):
        st.markdown("#### 🛠️ 管理员")
        with st.expander("管理员面板（修改即时生效）", expanded=False):
            with st.form("admin_basic"):
                an = st.text_input("应用名", value=APP_NAME)
                gb = st.columns(3)
                gm = gb[0].number_input("专属生日·月", 1, 12, settings.get_owner()[0][0])
                gd = gb[1].number_input("专属生日·日", 1, 31, settings.get_owner()[0][1])
                gy = gb[2].number_input("专属出生年", config.BIRTH_MIN_YEAR, config.BIRTH_MAX_YEAR, settings.get_owner()[1])
                if st.form_submit_button("保存基础设置"):
                    settings.save_overrides({"app_name": an, "owner_birthday": [int(gm), int(gd)], "owner_birth_year": int(gy)})
                    st.success("已保存。")
            st.markdown("##### 名言管理")
            with st.form("admin_quote_add"):
                qt = st.text_input("名言内容"); qw = st.text_input("作品")
                qy = st.number_input("年份", config.QUOTES_YEAR_MIN, config.QUOTES_YEAR_MAX, 2010)
                if st.form_submit_button("添加名言"):
                    if qt.strip() and qw.strip():
                        quotes.add_quote(qt.strip(), qw.strip(), int(qy), ""); st.success("已添加。")
                    else:
                        st.warning("内容和作品不能为空。")
            cur_q = quotes.load_quotes(); st.caption(f"当前 {len(cur_q)} 条")
            del_q = st.number_input("删除第几条名言", 1, max(1, len(cur_q)), 1, key="del_q")
            if st.button("删除该名言"):
                if quotes.delete_quote(int(del_q) - 1): st.success("已删除。")
            st.markdown("##### 攻略管理")
            with st.form("admin_guide_add"):
                gc = st.text_input("分类", value="新手入门"); gt = st.text_input("攻略标题"); gbody = st.text_area("攻略内容")
                if st.form_submit_button("添加攻略"):
                    if gt.strip() and gbody.strip():
                        guides.add_guide(gc.strip(), gt.strip(), gbody.strip()); st.success("已添加。")
                    else:
                        st.warning("标题和内容不能为空。")
            cur_g = guides.load_guides(); st.caption(f"当前 {len(cur_g)} 条")
            del_g = st.number_input("删除第几条攻略", 1, max(1, len(cur_g)), 1, key="del_g")
            if st.button("删除该攻略"):
                if guides.delete_guide(int(del_g) - 1): st.success("已删除。")
    st.divider()
    st.markdown("### 📖 舞萌攻略专区")
    for cat, items in guides.by_category(guides.load_guides()).items():
        with st.expander(f"📘 {cat}（{len(items)} 条）", expanded=(cat == "新手入门")):
            for g in items:
                st.markdown(f"<div class='gcard'><div class='gt'>{g['title']}</div><div class='gb'>{g['body']}</div></div>", unsafe_allow_html=True)


# ---------------- 路由 ----------------
page = st.session_state.get("page", "home")
if page == "home":
    page_home()
elif page == "tracks":
    page_tracks()
elif page == "practice":
    page_practice()
elif page == "vip":
    page_vip()
else:
    page_me()

# 迷你播放器（非曲目页显示，保持播放状态跨页）
if page != "tracks":
    render_mini_player(uname)

st.divider()
st.markdown(f"""<div class='note'>
数据说明：曲库为 {config.SONGS_SOURCE_NOTE} 原值，不推测。音乐仅播放 data/bgm/ 已授权音频与本地原创 BGM；
在线曲目（舞萌曲库/SoundCloud）为仅展示+来源链接，未授权不播放、不伪装。视频链接为 B 站搜索链接。
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>""", unsafe_allow_html=True)
