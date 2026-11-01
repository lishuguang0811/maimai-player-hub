# -*- coding: utf-8 -*-
"""
app.py —— MAIMAI PLAYER HUB（减法式重构 + 音乐系统）

七页导航：首页 / 曲目与收藏 / 练习与成绩 / 小游戏厅 / 街机厅 / 玩家档案 / 我的与设置。
私人剧情/VIP 空间属于作者私人内容，未包含在公开版。
保留：账号注册登录、收藏、练习成绩、小游戏、街机厅、玩家档案、攻略、名言、BGM。

音乐系统：统一播放状态(session) + 音源适配器(本地原创BGM可播放 / 舞萌曲库仅展示+来源链接 /
SoundCloud 未配置密钥时明确提示不伪装)。紧凑迷你播放器 + 完整播放器。
"""
from __future__ import annotations

import random
import time
from datetime import date, datetime
from pathlib import Path

import streamlit as st

import config
from modules import (accounts, arcade, background, bgm, dan, guides, maimai, minigames, music, netease,
                     playlog, quotes, recommend, settings, simai, songs, userdata)

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


@st.cache_data(ttl=600)
def netease_index() -> dict:
    """整张网易云校对表（10 分钟缓存，避免每页都读一遍盘）。"""
    return netease.items()


def maimai_card(sv, tip="", ne=None):
    chips = []
    for diff in config.DIFF_ORDER:
        meta = config.DIFF_META[diff]; d = sv["diffs"].get(diff)
        chips.append(f"<span class='chip' style='background:{meta['color']};color:{meta['text']}'>{meta['short']} {d['level']}</span>"
                     if d else f"<span class='chip off'>{meta['short']} —</span>")
    miku = "　<span style='color:var(--miku);font-weight:700'>★ MIKU/世界计划</span>" if sv["is_miku"] else ""
    bili = songs.bilibili_link(sv["title"])
    tip_html = f"<div class='mtip'>💡 {tip}</div>" if tip else ""
    links = [f"<a href='{bili}' target='_blank'>📺 B站看谱面</a>"]
    note = ""
    if ne is None:
        pass                                   # 还没校对过，不妄下结论
    elif ne.get("status") == "found" and ne.get("id"):
        links.insert(0, f"<a href='{netease.song_url(ne['id'])}' target='_blank'>▶ 网易云听这首</a>")
        note = (f"<span style='color:#7f8f96'>　已校对 · 网易云《{ne.get('name','')}》"
                f"{(' / ' + ne['artist']) if ne.get('artist') else ''}</span>")
    elif ne.get("status") == "weak":
        links.insert(0, f"<a href='{netease.search_url(sv['title'], sv['artist'])}' target='_blank'>🔎 去网易云搜</a>")
        note = "<span style='color:#7f8f96'>　网易云有同名曲，没敢确认是同一首，所以不给直达链接</span>"
    elif ne.get("status") == "not_found":
        links.insert(0, f"<a href='{netease.search_url(sv['title'], '')}' target='_blank'>🔎 网易云搜一下</a>")
        note = "<span style='color:#7f8f96'>　网易云未收录，不放链接</span>"
    return f"""<div class='msong{' miku' if sv['is_miku'] else ''}'>
      <div class='mrow1'><span class='mtitle'>{sv['title']}</span><span class='martist'>{sv['artist'] or ''}</span></div>
      <div class='mchips'>{''.join(chips)}</div>
      <div class='mmeta'>最高定数 {sv['max_ds']:.1f} · BPM {sv['bpm'] or '—'} · {sv['genre'] or '—'}{miku}</div>
      {tip_html}<div class='mlink'>{'　'.join(links)}{note}</div></div>"""


def song_view(song):
    return {"title": song["title"], "artist": song["artist"], "genre": song["genre"],
            "bpm": song["bpm"], "max_ds": song["ds"], "is_miku": songs.is_miku_related(song),
            "diffs": {song["diff"]: {"level": song["level"], "ds": song["ds"]}}}


# ---------------- 音乐播放器 ----------------
def mstate():
    return st.session_state.setdefault("music", music.new_state())


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
st.session_state.setdefault("user", None)
st.session_state.setdefault("page", "home")

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
    st.markdown(f"<div class='note' style='text-align:right'>{uname}</div>",
                unsafe_allow_html=True)
if st.session_state.get("show_egg"):
    st.success("🎁 被你发现了：谢谢你打开这个小小的音乐空间。愿每一首歌，都刚好是你今天想听的那首。")
    st.session_state["show_egg"] = False

snap = ensure_snapshot()
records = songs.flatten(snap) if snap else []
source = music.MusicSource(records)

PAGE_KEY = {"首页": "home", "曲目与收藏": "tracks", "练习与成绩": "practice",
            "我的与设置": "me", "🎮 小游戏": "games", "🕹 街机厅": "cabinet",
            "📊 玩家档案": "profile"}


def _nav_label(page):
    return {"home": "首页", "tracks": "曲目与收藏", "practice": "练习与成绩",
            "me": "我的与设置", "games": "🎮 小游戏", "cabinet": "🕹 街机厅",
            "profile": "📊 玩家档案"}.get(page, "首页")


PAGES = ["首页", "曲目与收藏", "练习与成绩", "🎮 小游戏", "🕹 街机厅",
         "📊 玩家档案", "我的与设置"]
_cur = st.session_state.get("page", "home")
with st.sidebar:
    _lbl = _nav_label(_cur)
    if _lbl not in PAGES:
        _lbl = "首页"
    nav = st.radio("导航", PAGES, index=PAGES.index(_lbl), key="nav_radio")
    st.session_state["page"] = PAGE_KEY[nav]
    st.divider()
    if st.button("🚪 退出登录", width="stretch"):
        st.session_state["user"] = None
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
                f"<div class='meta'>今天想听点什么？<br>"
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
    if qe[2].button("⚙️ 我的与设置", width="stretch"):
        st.session_state["page"] = "me"; st.rerun()
    st.write("")
    _dn = dan.get(uname).get("dan", "") or "未认定"
    hc = st.columns([1, 1, 1, 1])
    hc[0].markdown(f"<div class='note' style='text-align:center'>🎖 段位<br>"
                   f"<b style='font-size:1.15rem'>{_dn}</b></div>", unsafe_allow_html=True)
    hc[1].markdown(f"<div class='note' style='text-align:center'>📅 连续打卡<br>"
                   f"<b style='font-size:1.15rem'>{playlog.streak(uname)} 天</b></div>",
                   unsafe_allow_html=True)
    hc[2].markdown(f"<div class='note' style='text-align:center'>🎮 登记成绩<br>"
                   f"<b style='font-size:1.15rem'>{playlog.total_plays(uname)} 局</b></div>",
                   unsafe_allow_html=True)
    with hc[3]:
        if playlog.checked_today(uname):
            st.success("今天已打卡")
        elif st.button("📅 今天打卡", key="home_checkin", width="stretch"):
            playlog.checkin(uname); st.rerun()
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("收藏", len(userdata.list_favorites(uname)))
    m2.metric("成绩", userdata.stats(uname)["count"])
    m3.metric("练习中", sum(1 for x in userdata.list_practice(uname) if x["status"] != "已完成"))
    m4.metric("曲库", snap.get("count", 0) if snap else 0)

    # ---- 今日运势 ----
    st.divider()
    ft = minigames.fortune(today)
    st.markdown(f"<div class='hero'><div class='name' style='font-size:1.2rem'>🎴 今日运势 · {ft['rank']}</div>"
                f"<div class='meta'>{ft['text']}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='note'>📝 今日小任务：{minigames.task(today)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='note'>🍀 {minigames.lucky_line(today)}</div>", unsafe_allow_html=True)

    # ---- 今日选曲（按等级 + 爱好加权）----
    st.divider()
    st.markdown("### 🎯 今日选曲")
    theme = {"key": "offline"}
    tier_objs = recommend.tiers_for_level(level)
    fav_titles = [f["title"] for f in userdata.list_favorites(uname)]
    picks = recommend.daily_picks(records, today, theme, tier_objs, config.PICKS_PER_TIER,
                                  hobbies, level, user_fav=fav_titles,
                                  user_scores=userdata.list_scores(uname))
    _nei_home = netease_index()
    for grp in picks:
        t = grp["tier"]
        st.markdown(f"<div class='badge'>{t['emoji']} {t['label']}　{t['ds_min']}–{t['ds_max']} 定数 · 候选 {grp['pool_size']} 首</div>",
                    unsafe_allow_html=True)
        for item in grp["songs"]:
            sv = item["song"]
            st.markdown(maimai_card({
                "title": sv["title"], "artist": sv["artist"], "genre": sv["genre"],
                "bpm": sv["bpm"], "max_ds": sv["ds"], "is_miku": songs.is_miku_related(sv),
                "diffs": {sv["diff"]: {"level": sv.get("level", ""), "ds": sv["ds"]}},
            }, tip=item["reason"], ne=_nei_home.get(sv["title"])), unsafe_allow_html=True)

    # ---- 曲库更新提示 ----
    if snap:
        age = songs.snapshot_age_days(snap)
        age_txt = f"（{age} 天前）" if age is not None else ""
        st.caption(f"🎵 曲库快照：{snap.get('fetched_at', '?')[:10]} 更新 {age_txt} · 共 {snap.get('count', 0)} 首 · 数据源 diving-fish 国服")


def page_tracks():
    st.markdown("### 🎵 音乐播放器")
    st.caption("舞萌曲库里的歌没有能放进本程序的音频授权，所以「听」这件事交给正版平台——"
               "点一下直接跳网易云。真正在本程序里能响的，是「氛围 BGM」里那 16 首原创曲。")

    t_song, t_bgm, t_out = st.tabs(["🎧 曲库点歌", "🌙 氛围 BGM（可播放）", "🔗 外部收听"])

    # ==================== 曲库点歌 ====================
    with t_song:
        lib = songs.song_select_view(records)
        fq, fc = st.columns([3, 2])
        qtext = fq.text_input("搜索曲名 / 艺术家", key="sel_q")
        only_miku = fc.checkbox("只看初音/世界计划", key="sel_miku")
        _f1, _f2 = st.columns(2)
        only_fav = _f1.checkbox("只看已收藏", key="sel_fav")
        only_play = _f2.checkbox("🎧 只看网易云确认能听的", key="sel_play")
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
        if only_play:
            _nei_p = netease_index()
            shown = [s for s in shown
                     if (_nei_p.get(s["title"]) or {}).get("status") == "found"]
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
        PAGE = 24
        pages = max(1, (len(shown) + PAGE - 1) // PAGE)
        _ns = netease.stats()
        if _ns["total"]:
            _age = f"（{_ns['age_days']} 天前校对）" if _ns["age_days"] else ""
            st.markdown(f"<div class='note'>共 {len(shown)} 首 · 网易云校对：已查 {_ns['total']} 首，"
                        f"<b style='color:#39C5BB'>{_ns['found']}</b> 首确认可听、"
                        f"{_ns['weak']} 首同名未确认、{_ns['not_found']} 首未收录{_age}。"
                        f"只有确认能听的才给直达链接。</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='note'>共 {len(shown)} 首 · 还没做过网易云校对，"
                        f"跑 <code>python work/verify_netease.py</code> 后会显示「能听」的直达链接</div>",
                        unsafe_allow_html=True)
        if not shown:
            st.info("没有匹配的曲目，试试清空筛选。")
        pg = st.number_input("页码", 1, pages, 1, key="sel_pg")
        lv_tip = settings.get_levels().get(level, {}).get("tip", "")
        _nei = netease_index()
        for sv in shown[(pg - 1) * PAGE: pg * PAGE]:
            st.markdown(maimai_card(sv, tip=lv_tip, ne=_nei.get(sv["title"])), unsafe_allow_html=True)
            _sc = st.columns([1, 1, 5])
            if userdata.is_favorite(uname, sv["title"]):
                if _sc[0].button("💔 取消收藏", key=f"selfav_{sv['title']}"):
                    userdata.remove_favorite(uname, sv["title"]); st.rerun()
            else:
                if _sc[0].button("⭐ 收藏", key=f"selfav_{sv['title']}"):
                    userdata.add_favorite(uname, {"title": sv["title"], "artist": sv["artist"],
                                                  "ds": sv["max_ds"], "diff": "", "genre": sv["genre"]}); st.rerun()
            if _sc[1].button("📋 加入练习", key=f"selprac_{sv['title']}"):
                userdata.add_practice(uname, {"title": sv["title"], "diff": diff_f if diff_f != "全部" else "",
                                              "ds": sv["max_ds"]}, "", "来自曲库")
                st.success(f"已把《{sv['title']}》加入练习清单。")
        st.divider()
        st.markdown("### ⭐ 我的收藏")
        favs = userdata.list_favorites(uname)
        if favs:
            for fv in favs:
                cc = st.columns([4, 1, 1])
                _nl = music.netease_search_url(fv["title"], fv.get("artist", ""))
                cc[0].markdown(f"<div class='msong'><div class='mtitle'>{fv['title']}</div>"
                               f"<div class='mmeta'>{fv.get('artist', '')} · {fv.get('diff', '')} {fv.get('ds', '')}"
                               f"</div><div class='mlink'><a href='{_nl}' target='_blank'>▶ 在网易云听这首</a></div></div>",
                               unsafe_allow_html=True)
                if cc[1].button("📋 练习", key=f"fp_{fv['title']}"):
                    userdata.add_practice(uname, {"title": fv["title"], "diff": fv.get("diff", ""),
                                                  "ds": fv.get("ds")}, "", "来自收藏")
                    st.success("已加入练习清单。")
                if cc[2].button("移除", key=f"rm_{fv['title']}"):
                    userdata.remove_favorite(uname, fv["title"]); st.rerun()
        else:
            st.caption("还没有收藏。")

    # ==================== 氛围 BGM（真的能播） ====================
    with t_bgm:
        _tracks = bgm.list_tracks()
        if not _tracks:
            st.info("data/bgm/ 里还没有音频。放几首你已获授权的 mp3/wav 进去，刷新就会出现在这里。")
        else:
            st.caption(f"共 {len(_tracks)} 首 · 程序自带原创合成氛围音，离线可播，不依赖任何外部平台。")
            _names = [bgm.track_label(p) for p in _tracks]
            _i = st.selectbox("选一首", range(len(_tracks)), format_func=lambda i: _names[i], key="bgm_pick")
            _p = _tracks[_i]
            st.audio(str(_p), loop=st.checkbox("🔂 单曲循环", key="bgm_loop"))
            _bc = st.columns([1, 1, 3])
            if _bc[0].button("🎲 随机来一首", key="bgm_rand"):
                import random as _r
                st.session_state["bgm_pick"] = _r.randrange(len(_tracks)); st.rerun()
            if _bc[1].button("＋ 加入播放列表", key="bgm_q"):
                _tr = music.make_track("bgm", _names[_i], "原创合成", "full", file=_p)
                st.session_state["music"] = music.add_to_queue(mstate(), _tr); st.rerun()
            _bc[2].caption("播放器自带 播放 / 暂停 / 进度 / 音量；勾选循环后会一直重复这一首。")
            st.divider()
            render_now_playing(uname)

    # ==================== 外部收听 ====================
    with t_out:
        _sq = st.text_input("搜一首歌（直接跳正版平台）", key="out_q")
        if _sq:
            st.markdown(f"<div class='mlink'>"
                        f"<a href='{music.netease_search_url(_sq)}' target='_blank'>▶ 网易云音乐搜「{_sq}」</a>　"
                        f"<a href='{music.qqmusic_search_url(_sq)}' target='_blank'>▶ QQ 音乐搜「{_sq}」</a>　"
                        f"<a href='{songs.bilibili_link(_sq)}' target='_blank'>📺 B 站搜「{_sq}」</a></div>",
                        unsafe_allow_html=True)
        else:
            st.caption("输入曲名/艺人后会出现三个平台的搜索入口。本程序不抓取、不转存任何音频。")
        with st.expander("🎬 粘贴 YouTube 链接，用官方嵌入播放（无需任何密钥）"):
            yc = st.columns([3, 2, 1])
            yt_in = yc[0].text_input("YouTube 链接或 11 位视频 ID", key="yt_in")
            yt_title = yc[1].text_input("标题（可选）", key="yt_title")
            if yc[2].button("加载播放器", key="yt_load"):
                _tr = music.track_from_youtube(yt_in, yt_title)
                if _tr:
                    st.session_state["music"] = music.play_now(mstate(), _tr); st.rerun()
                else:
                    st.error("仅支持 YouTube 官方链接或 11 位视频 ID；已拒绝嵌入任意网址。")
        with st.expander("🔁 播放列表在哪？"):
            st.caption("跨页迷你播放器和播放队列都在「🌙 氛围 BGM」那一页。"
                       "在那里把曲子加进列表后，切到别的页面底部也能看到当前曲目和控制按钮。")



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


def page_me():
    st.markdown("### 👤 我的与设置")
    likes_html = "".join(f"<span class='badge'>{x}</span>" for x in hobbies) or "<span class='note'>未填写爱好</span>"
    st.markdown(f"<div class='hero'><div class='name'>{uname}</div><div class='meta'>生日：{user.get('birthday') or '—'}　|　"
                f"城市：{user.get('city', '—')}　|　等级：<b style='color:var(--miku)'>{level}</b>"
                f"<br>{likes_html}</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎨 主题")
        themes = list(THEMES.keys())
        sel = st.radio("界面主题", themes, index=themes.index(theme_pref) if theme_pref in themes else 0)
        if sel != theme_pref:
            userdata.set_pref(uname, "theme", sel); st.rerun()
    with c2:
        st.markdown("#### 🎚️ 等级")
        lv_opts = list(settings.get_levels().keys())
        if level not in lv_opts:
            lv_opts.append(level)
        nl = st.selectbox("切换等级", lv_opts, index=lv_opts.index(level))
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
    st.divider()
    st.markdown("#### 🎵 曲库更新")
    st.caption("曲库是 diving-fish 国服快照，会随版本变旧。点下面联网重新抓取一次（约 1MB）。")
    if st.button("🔄 刷新曲库（联网）", key="refresh_songs"):
        with st.spinner("正在抓取最新曲库…"):
            res = songs.refresh_songs()
        if res.get("ok"):
            cached_snapshot.clear()
            st.success(f"已更新：{res.get('count')} 首（{res.get('fetched_at', '')[:19]}）")
        else:
            st.error(f"刷新失败：{res.get('error')}")
    if accounts.is_admin(uname):
        st.markdown("#### 🛠️ 管理员")
        with st.expander("管理员面板（修改即时生效）", expanded=False):
            with st.form("admin_basic"):
                an = st.text_input("应用名", value=APP_NAME)
                if st.form_submit_button("保存基础设置"):
                    settings.save_overrides({"app_name": an})
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


def page_games():
    st.markdown("### 🎮 小游戏厅")
    st.caption("全部离线可跑、不碰版权：音效是实时合成的，题目数据来自你本地那份曲库快照。"
               "切走再回来会重开一局，但最高纪录存在浏览器里。")

    _CATS = ["🎵 节奏手感", "🎚 判定与手感", "🧠 记忆脑力", "🎯 曲库知识", "📖 读谱与手速",
             "🕹 消磨时间", "🎱 曲库宾果", "🎴 今日运势"]
    _cat = st.radio("挑一类", _CATS, horizontal=True, key="games_cat",
                    label_visibility="collapsed")
    st.write("")

    if _cat == "🎵 节奏手感":
        _t0, _t1, _t2 = st.tabs(["🎵 节奏判定", "⚡ 打 NOTE", "🎚 判定偏移校准"])
        with _t0:
            st.markdown("**下落式节奏判定** —— 四条轨，键盘 **D F J K**，也可以直接点屏幕对应区域。"
                        "判定窗口 ±45ms 是 CRITICAL PERFECT，三档难度（BPM 88 / 118 / 150）随便挑。")
            st.iframe(arcade.rhythm_html(), height=640)

        with _t1:
            st.markdown("**打 NOTE** —— 30 秒限时，NOTE 亮了就点，越快分越高；"
                        "**红色的 ✕ 是假 NOTE，点中扣连击**。等人的时候刚好来一局。")
            st.iframe(arcade.tap_html(), height=580)

        with _t2:
            st.markdown("**判定偏移校准** —— 播 120 BPM 的节拍，你跟着敲空格；敲满 16 下，"
                        "它告诉你平均偏早/偏晚多少毫秒、波动多大、机台的判定偏移该设成多少。"
                        "节拍是实时合成的，不是任何音频文件。")
            st.iframe(arcade.offset_html(), height=560)

    elif _cat == "🎚 判定与手感":
        _t0, _t1, _t2 = st.tabs(["🎚 判定偏移挑战", "🤝 双押拆解", "💥 连击生存"])
        with _t0:
            st.markdown("**判定偏移挑战** —— 比「判定偏移校准」更贴近实战：BPM 按 "
                        "**90 → 120 → 150 → 180** 分四段连着来，每段敲 8 下空格，中间不停。"
                        "散点图是每一下的偏差、黄线是最近 5 下的移动平均。"
                        "最后给<b>逐段偏移趋势</b> —— 如果你的偏移跟着曲速走，这里一眼就能看出来。",
                        unsafe_allow_html=True)
            st.iframe(arcade.judge_html(), height=660)

        with _t1:
            st.markdown("**双押拆解** —— 圆环上同时亮 **2~3 个方位**，你要在极短的窗口内把对应的键"
                        "**一次**按下去（键盘 **1~8** 顺时针，正上方是 1，也可以直接点圆环）。"
                        "判的不是按没按到，是两个键落下的**时间差**：差超过 40ms 就算被拆开了。")
            st.iframe(arcade.chord_html(), height=680)

        with _t2:
            st.markdown("**连击生存** —— 四条轨，**D F J K**。NOTE 越来越快（110 → 220 BPM），"
                        "判定窗口越来越窄（±130ms 一路收到 ±40ms），**漏一个掉 20 血**，血空了结束。"
                        "CRITICAL 回 2 血、PERFECT 回 1 血 —— 撑得越久越赚。")
            st.iframe(arcade.survive_html(), height=700)

    elif _cat == "🧠 记忆脑力":
        _t0, _t1, _t2 = st.tabs(["🧠 音符记忆", "🃏 曲名翻牌", "🔁 谱面记忆复述"])
        with _t0:
            st.markdown("**音符记忆** —— 看好亮灯顺序再原样点一遍，每轮多一个音，"
                        "四个音高是 C-E-G-B（键盘 **D F J K**）。听着记比看着记容易。")
            st.iframe(arcade.simon_html(), height=600)

        with _t1:
            if records:
                import random as _r
                _pool = sorted({r["title"] for r in records if (r.get("title") or "").strip()})
                _pick = _r.sample(_pool, min(8, len(_pool)))
                st.markdown("**曲名记忆翻牌** —— 翻开两张，曲名一样就配对。曲名全部来自本地曲库快照。")
                st.iframe(arcade.memory_html(_pick), height=640)
            else:
                st.info("曲库还没加载，进首页等曲库就绪后再来。")

        with _t2:
            st.markdown("**谱面记忆复述** —— 先<b>听</b>一段：四个圆按节奏亮起来，音高各不相同；"
                        "放完轮到你，用 **D F J K** 把**方位和节奏一起**敲回来。"
                        "从 3 个音起，每过一轮加一个，最长 8 个 —— 方位错一个或漏敲就结束。",
                        unsafe_allow_html=True)
            st.iframe(arcade.echo_html(), height=620)


    elif _cat == "🎯 曲库知识":
        _t0, _t1, _t2, _t3 = st.tabs(["🎯 定数竞猜", "🥁 BPM 速猜", "⚖️ 定数比大小", "⌨️ 曲名打字"])
        with _t0:
            st.markdown("**定数竞猜** —— 给你一首歌，猜它的谱面定数。答案就是你本地曲库里的真实数值，不推测。")
            if not records:
                st.info("曲库未加载。")
            else:
                _hc = st.columns([1, 1, 3])
                hard = _hc[0].checkbox("困难模式（只给曲名）", key="ds_hard")
                if _hc[1].button("🔄 新的一轮（5 题）", key="ds_new"):
                    st.session_state["ds_rounds"] = [minigames.ds_round(records, f"{time.time()}-{i}", hard)
                                                     for i in range(5)]
                    st.session_state["ds_idx"] = 0; st.session_state["ds_scores"] = []
                    st.rerun()
                rounds = st.session_state.get("ds_rounds")
                if not rounds:
                    st.caption("点「新的一轮」开始，一共 5 题。猜得越准分越高，最后给个总评。")
                else:
                    idx = int(st.session_state.get("ds_idx", 0))
                    scores = st.session_state.get("ds_scores", [])
                    if idx >= len(rounds):
                        avg = sum(scores) / max(1, len(scores))
                        st.markdown(f"<div class='hero'><div class='name' style='font-size:1.5rem'>"
                                    f"{minigames.ds_rank(avg)}</div>"
                                    f"<div class='meta'>平均分 {avg:.0f} / 100 · 五题总分 {sum(scores)}</div></div>",
                                    unsafe_allow_html=True)
                        for i, q in enumerate(rounds):
                            r = q.get("result") or {}
                            st.markdown(f"<div class='note'>{i+1}. 《{q['title']}》　定数 <b>{q['ds']}</b>"
                                        f"　·　你差 {r.get('err', '-')}　·　{r.get('judge', '')}</div>",
                                        unsafe_allow_html=True)
                    else:
                        q = rounds[idx]
                        st.markdown(f"#### 第 {idx + 1} / {len(rounds)} 题")
                        info = f"**《{q['title']}》**"
                        if not q.get("hard"):
                            info += f" · 流派 {q['genre']} · BPM {q['bpm'] or '—'} · 艺人 {q['artist']}"
                        st.markdown(info)
                        guess = st.slider("你猜定数是多少？", 1.0, 15.0, 12.0, 0.1, key=f"ds_slider_{idx}")
                        if st.button("提交答案", key=f"ds_submit_{idx}", type="primary"):
                            r = minigames.ds_judge(guess, q["ds"])
                            q["result"] = {**r, "guess": guess}
                            st.session_state["ds_scores"] = scores + [r["score"]]
                            st.session_state["ds_idx"] = idx + 1
                            st.rerun()
                        prev = rounds[idx - 1].get("result") if idx > 0 else None
                        if prev:
                            st.markdown(f"<div class='note'>上一题《{rounds[idx-1]['title']}》真实定数 "
                                        f"<b>{prev['answer']}</b>　·　你差 {prev['err']}　·　<b>{prev['judge']}</b>"
                                        f"<br>{prev['comment']}</div>", unsafe_allow_html=True)

        with _t1:
            st.markdown("**BPM 速猜** —— 报歌名，你说它每分钟多少拍。答案同样是曲库里的真实 BPM。")
            if not records:
                st.info("曲库未加载。")
            else:
                if st.button("🔄 新的一轮（5 题）", key="bpm_new"):
                    st.session_state["bpm_rounds"] = [minigames.bpm_round(records, f"{time.time()}-{i}")
                                                      for i in range(5)]
                    st.session_state["bpm_idx"] = 0; st.session_state["bpm_scores"] = []
                    st.rerun()
                br = st.session_state.get("bpm_rounds")
                if not br:
                    st.caption("点「新的一轮」开始。误差在 2% 以内算 CRITICAL PERFECT。")
                else:
                    bi = int(st.session_state.get("bpm_idx", 0))
                    bsc = st.session_state.get("bpm_scores", [])
                    if bi >= len(br):
                        avg = sum(bsc) / max(1, len(bsc))
                        st.markdown(f"<div class='hero'><div class='name' style='font-size:1.5rem'>"
                                    f"{minigames.ds_rank(avg)}</div>"
                                    f"<div class='meta'>平均分 {avg:.0f} / 100</div></div>", unsafe_allow_html=True)
                        for i, q in enumerate(br):
                            r = q.get("result") or {}
                            st.markdown(f"<div class='note'>{i+1}. 《{q['title']}》　真实 <b>{q['bpm']}</b> BPM"
                                        f"　·　差 {r.get('err', '-')}　·　{r.get('judge', '')}</div>",
                                        unsafe_allow_html=True)
                    else:
                        q = br[bi]
                        st.markdown(f"#### 第 {bi + 1} / {len(br)} 题")
                        st.markdown(f"**《{q['title']}》** · 艺人 {q['artist']} · 流派 {q['genre']} · 定数 {q['ds']}")
                        gp = st.slider("你觉得是多少 BPM？", 60, 260, 150, 1, key=f"bpm_slider_{bi}")
                        if st.button("提交答案", key=f"bpm_submit_{bi}", type="primary"):
                            r = minigames.bpm_judge(gp, q["bpm"])
                            q["result"] = r
                            st.session_state["bpm_scores"] = bsc + [r["score"]]
                            st.session_state["bpm_idx"] = bi + 1
                            st.rerun()
                        prev = br[bi - 1].get("result") if bi > 0 else None
                        if prev:
                            st.markdown(f"<div class='note'>上一题《{br[bi-1]['title']}》真实 "
                                        f"<b>{prev['answer']}</b> BPM　·　差 {prev['err']}　·　<b>{prev['judge']}</b>"
                                        f"<br>{prev['comment']}</div>", unsafe_allow_html=True)

        with _t2:
            st.markdown("**定数比大小** —— 两首歌摆一起，猜哪首定数更高。定数差太小的题不出（那是纯蒙）。")
            if not records:
                st.info("曲库未加载。")
            else:
                if st.button("🔄 新的一轮（10 题）", key="duel_new"):
                    st.session_state["duel_rounds"] = [minigames.ds_duel(records, f"{time.time()}-{i}")
                                                       for i in range(10)]
                    st.session_state["duel_idx"] = 0; st.session_state["duel_ok"] = 0
                    st.rerun()
                dr = st.session_state.get("duel_rounds")
                if not dr:
                    st.caption("点「新的一轮」开始，10 题，做完给评级。")
                else:
                    di = int(st.session_state.get("duel_idx", 0))
                    dok = int(st.session_state.get("duel_ok", 0))
                    if di >= len(dr):
                        st.markdown(f"<div class='hero'><div class='name' style='font-size:1.5rem'>"
                                    f"{minigames.duel_rank(dok, len(dr))}</div>"
                                    f"<div class='meta'>答对 {dok} / {len(dr)}</div></div>", unsafe_allow_html=True)
                    else:
                        d = dr[di]
                        st.markdown(f"#### 第 {di + 1} / {len(dr)} 题　（已答对 {dok}）")
                        _a, _b = st.columns(2)
                        _a.markdown(f"<div class='msong'><div class='mtitle'>A · {d['a']['title']}</div>"
                                    f"<div class='mmeta'>{d['a']['artist']} · {d['a']['genre']}</div></div>",
                                    unsafe_allow_html=True)
                        _b.markdown(f"<div class='msong'><div class='mtitle'>B · {d['b']['title']}</div>"
                                    f"<div class='mmeta'>{d['b']['artist']} · {d['b']['genre']}</div></div>",
                                    unsafe_allow_html=True)
                        ca, cb = st.columns(2)
                        pick = None
                        if ca.button("A 更高", key=f"duel_a_{di}", width="stretch"):
                            pick = "a"
                        if cb.button("B 更高", key=f"duel_b_{di}", width="stretch"):
                            pick = "b"
                        if pick:
                            ok = minigames.duel_judge(d, pick)
                            d["picked"] = pick
                            st.session_state["duel_ok"] = dok + (1 if ok else 0)
                            st.session_state["duel_idx"] = di + 1
                            st.rerun()
                        prev = dr[di - 1].get("picked") if di > 0 else None
                        if prev:
                            pd = dr[di - 1]
                            okk = prev == pd["answer"]
                            st.markdown(f"<div class='note'>上一题：{'✅ 对了' if okk else '❌ 错了'}　"
                                        f"A《{pd['a']['title']}》{pd['a']['ds']}　vs　"
                                        f"B《{pd['b']['title']}》{pd['b']['ds']}　（差 {pd['gap']}）</div>",
                                        unsafe_allow_html=True)

        with _t3:
            st.markdown("**曲名打字** —— 60 秒，照着曲名敲，比 WPM 和准确率。"
                        "曲名全部来自本地曲库，只挑了能用键盘直接敲的（纯英文/数字/符号）。")
            if not records:
                st.info("曲库未加载。")
            else:
                _pool = sorted({r["title"].strip() for r in records
                                if (r.get("title") or "").strip()
                                and all(ord(c) < 128 for c in r["title"].strip())
                                and len(r["title"].strip()) >= 4})
                if not _pool:
                    st.info("曲库里没有能直接用键盘敲的曲名。")
                else:
                    if "type_pool" not in st.session_state:
                        import random as _r
                        st.session_state["type_pool"] = _r.sample(_pool, min(60, len(_pool)))
                    if st.button("🔄 换一批曲名", key="type_new"):
                        import random as _r2
                        st.session_state["type_pool"] = _r2.sample(_pool, min(60, len(_pool)))
                    st.iframe(arcade.type_html(st.session_state["type_pool"]), height=560)

    elif _cat == "🕹 消磨时间":
        _t0, _t1, _t2 = st.tabs(["🧩 难度 2048", "🧱 NOTE 落块", "🐍 音符蛇"])
        with _t0:
            st.markdown("**maimai 2048** —— 合并的是难度：**BASIC → ADVANCED → EXPERT → MASTER → "
                        "Re:MASTER → 宴 → …**。方向键 / WASD / 手机滑动都行，还能撤销一步。")
            st.iframe(arcade.merge_html(), height=720)

        with _t1:
            st.markdown("**NOTE 落块** —— 就是俄罗斯方块，方块用舞萌的难度配色。"
                        "消一行加一层，等级越高掉得越快。")
            st.iframe(arcade.drop_html(), height=640)
        with _t2:
            st.markdown("**音符蛇** —— 吃音符变长，撞墙或撞到自己就结束，吃得越多越快。纯消磨时间。")
            st.iframe(arcade.snake_html(), height=600)

    elif _cat == "🎴 今日运势":
        _t0 = st.tabs(["🎴 今日运势"])[0]
        with _t0:
            ft = minigames.fortune(today)
            st.markdown(f"<div class='hero'><div class='name' style='font-size:1.3rem'>今日运势 · {ft['rank']}</div>"
                        f"<div class='meta'>{ft['text']}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='note'>📝 今日小任务：{minigames.task(today)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='note'>🍀 {minigames.lucky_line(today)}</div>", unsafe_allow_html=True)
            st.caption("同一天的结果固定，明天才会换——不是随口编的鸡汤，是给今天挑个打法。")





    elif _cat == "📖 读谱与手速":
        _t0, _t1, _t2 = st.tabs(["📖 读谱训练", "🎚 节奏稳定性", "🔥 连打耐力"])
        with _t0:
            st.markdown("**读谱训练** —— 给一小段谱面，判断它是交替 / 连打 / 双押 / 混 BREAK / 稀疏，"
                        "或者数里面有几个 BREAK。**眼先读懂，手才跟得上**，这是真机上最值钱的能力。")
            st.iframe(arcade.score_html(records), height=640)
        with _t1:
            st.markdown("**节奏稳定性** —— 比「判定偏移校准」更狠：120 BPM 敲满 **32 下**，"
                        "看你的偏差是不是越敲越飘。给平均偏移、标准差、前后漂移和建议偏移值。")
            st.iframe(arcade.steady_html(), height=600)
        with _t2:
            st.markdown("**连打耐力** —— 30 秒，左右手交替敲 **F / J**（连敲同一个键不算）。"
                        "结束给一条每秒手速的柱子图，还有后段掉速百分比 —— 掉得越少，耐力越好。")
            st.iframe(arcade.stamina_html(), height=600)

    elif _cat == "🎱 曲库宾果":
        _t0 = st.tabs(["🎱 曲库宾果"])[0]
        with _t0:
            st.markdown("**曲库宾果** —— 5×5 卡上是 24 首真实曲目，每开一球给一个条件"
                        "（BPM ≥ 180 / 定数 ≥ 13.0 / 流派：xxx / 曲名里有「xx」……），"
                        "你找出卡上满足条件的那格点掉它。先连成一条线就 BINGO。")
            if not records:
                st.info("曲库还没加载。")
            else:
                _seed = st.session_state.get("bingo_seed") or f"{today}-{time.time()}"
                if st.button("🆕 换一张卡", key="bingo_new"):
                    _seed = f"{today}-{time.time()}"
                    st.session_state["bingo_seed"] = _seed
                    st.rerun()
                _card = arcade.bingo_cards(records, _seed)
                if not _card:
                    st.info("曲库太少，凑不出一张卡。")
                else:
                    st.iframe(arcade.bingo_html(_card), height=700)

    else:
        st.info("还没有这一类。")


# ---------------- 能力雷达 ----------------
def radar_svg(vals: dict, size: int = 300) -> str:
    import math
    dims = playlog.DIMS
    n = len(dims)
    cx = cy = size / 2
    r = size * 0.34

    def pt(i, ratio):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + math.cos(a) * r * ratio, cy + math.sin(a) * r * ratio

    rings = "".join(
        "<polygon points='%s' fill='none' stroke='rgba(255,255,255,.13)' stroke-width='1'/>"
        % " ".join("%.1f,%.1f" % pt(i, lv) for i in range(n))
        for lv in (0.25, 0.5, 0.75, 1.0))
    axes = ""
    for i, d in enumerate(dims):
        x, y = pt(i, 1.0)
        lx, ly = cx + (x - cx) * 1.22, cy + (y - cy) * 1.22
        axes += (f"<line x1='{cx:.1f}' y1='{cy:.1f}' x2='{x:.1f}' y2='{y:.1f}' "
                 f"stroke='rgba(255,255,255,.10)'/>"
                 f"<text x='{lx:.1f}' y='{ly:.1f}' fill='#9fb3bb' font-size='11' "
                 f"text-anchor='middle' dominant-baseline='middle'>{d}</text>")
    pts = [pt(i, max(0.02, float(vals.get(d, 0)) / 100.0)) for i, d in enumerate(dims)]
    poly = " ".join("%.1f,%.1f" % p for p in pts)
    dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.2' fill='#39C5BB'/>" for x, y in pts)
    vals_txt = "".join(
        f"<text x='{x:.1f}' y='{y - 8:.1f}' fill='#cfe6e4' font-size='9' "
        f"text-anchor='middle'>{int(vals.get(d, 0))}</text>"
        for (x, y), d in zip(pts, dims))
    return (f"<svg viewBox='0 0 {size} {size}' width='100%' height='{size}'>"
            f"{rings}{axes}"
            f"<polygon points='{poly}' fill='rgba(57,197,187,.26)' stroke='#39C5BB' stroke-width='2'/>"
            f"{dots}{vals_txt}</svg>")


# ---------------- 街机厅 / 段位认定 ----------------
def page_cabinet():
    st.markdown("### 🕹 街机厅")
    st.caption("一台模拟机：投币 → 选曲 → 选难度 → 演奏 → 结算，流程和真机一致。"
               "判定是圆环扩散式的 —— NOTE 从圆心生出来往外扩，扩到外圈那道环的瞬间敲下去。")

    # 整合好的「独立版」：一个 HTML 文件，手机和电脑都能离线跑
    with st.expander("📦 独立版（一个文件，手机 / 电脑都能离线玩）", expanded=False):
        st.markdown(
            "<div class='note'>把机台、20 个小游戏、曲库、成绩、设置<b>整合进一个 HTML 文件</b>，"
            "不联网也能跑：<br>"
            "· <b>电脑</b>：下载后双击就开玩，或者用 <code>package/dist/舞萌DX大厅.exe</code><br>"
            "· <b>手机</b>：传到手机上用浏览器打开 → 「添加到主屏幕」，就跟装了个 app 一样；"
            "也可以拿 <code>package/android/</code> 编 APK<br>"
            "· 曲库、成绩、设置都存在<b>本机浏览器</b>里（这台电脑/这部手机各存各的）</div>",
            unsafe_allow_html=True)
        _hub = Path(__file__).resolve().parent / "standalone" / "maimai-hub.html"
        if _hub.exists():
            st.download_button(
                "⬇️ 下载整合大厅（单文件 HTML）",
                data=_hub.read_bytes(),
                file_name="舞萌DX大厅.html",
                mime="text/html",
                help="双击打开即可，离线可用，零外部请求。")
            st.caption(f"当前这份 {_hub.stat().st_size / 1024:.0f} KB。"
                       "改完机台或小游戏后跑 `python work/build_hub.py` 就能更新。")
        else:
            st.caption("还没有生成：跑 `python work/build_hub.py` 就会出现在 standalone/ 里。")

    _ct = st.tabs(["🕹 机台", "📄 导入谱面", "🎖 段位认定", "📥 成绩登记"])

    with _ct[0]:
        if not records:
            st.info("曲库还没加载，先回首页等曲库就绪。")
        elif st.session_state.get("dx_playing") and st.session_state.get("dx_chart"):
            # 游戏中：只留机台 + 「换一首」，页面上没有任何会触发 rerun 的控件，
            # 这样在机台里点来点去（打音符）绝不会把整局冲掉
            st.iframe(maimai.cabinet_html(st.session_state["dx_chart"]), height=700)
            if st.button("🔄 换一首 / 返回选曲", key="dx_back", type="secondary"):
                st.session_state["dx_playing"] = False
                st.session_state.pop("dx_chart", None)
                st.rerun()
        else:
            _kw = (st.text_input("🔍 搜曲名或艺人（留空就是整库）",
                                 value=st.session_state.get("dx_kw", ""),
                                 key="dx_kw_in", placeholder="比如 Bad Apple / 初音")
                   or "").strip().lower()
            st.session_state["dx_kw"] = _kw

            _bucket: dict[str, dict] = {}
            for _r in records:
                _t = (_r.get("title") or "").strip()
                if not _t:
                    continue
                if _kw and _kw not in _t.lower() and _kw not in (_r.get("artist") or "").lower():
                    continue
                _b = _bucket.setdefault(_t, {"title": _t, "artist": _r.get("artist") or "",
                                             "bpm": _r.get("bpm") or 0, "diffs": []})
                _b["diffs"].append({"name": _r.get("diff") or "", "ds": _r.get("ds"),
                                    "level": _r.get("level") or "", "rec": _r})
                if len(_bucket) >= 600:
                    break
            _pool = sorted(_bucket.values(), key=lambda x: x["title"])
            if not _pool:
                st.info(f"没搜到「{_kw}」，换个词试试。")
            else:
                _labels = [f"{p['title']}　·　{p['artist'][:20]}" for p in _pool[:400]]
                _prev = st.session_state.get("dx_song")
                _ix = _labels.index(_prev) if _prev in _labels else 0
                _sel = st.selectbox(f"选曲（共 {len(_pool)} 首{'' if len(_pool) <= 400 else '，列出前 400 首'}）",
                                    _labels, index=_ix, key="dx_song_box")
                st.session_state["dx_song"] = _sel
                _song = _pool[_labels.index(_sel)]

                # ---- 难度 ----
                _ds = sorted(_song["diffs"], key=lambda d: maimai.diff_index_of(d["name"]))
                _cols = st.columns(max(1, len(_ds)))
                _cur = st.session_state.get("dx_diff")
                for _i, _d in enumerate(_ds):
                    _di = maimai.diff_index_of(_d["name"])
                    _cn = maimai.DIFF_CN[_di]
                    _col = maimai.DIFF_COLORS[_di]
                    _picked = (_cur == _di) or (_cur is None and _di == len(_ds) - 1)
                    _lab = (f"{'▶ ' if _picked else ''}{_cn}\n\n"
                            f"<span style='color:{_col};font-size:19px;font-weight:800'>"
                            f"{_d['level'] or '?'}</span>\n\n"
                            f"<span style='color:#7f8f96;font-size:11px'>"
                            f"定数 {_d['ds'] if _d['ds'] else '—'}</span>")
                    with _cols[_i]:
                        st.markdown(f"<div style='text-align:center;line-height:1.25'>{_lab}</div>",
                                    unsafe_allow_html=True)
                        if st.button(f"打这个 · {_cn}", key=f"dx_diff_{_song['title']}_{_di}"):
                            st.session_state["dx_diff"] = _di
                            _pick = _ds[_di]
                            st.session_state["dx_chart"] = maimai.build_chart(
                                _pick["rec"], maimai.diff_index_of(_pick["name"]))
                            st.session_state["dx_playing"] = True
                            st.rerun()

                _di = st.session_state.get("dx_diff")
                if _di is None or _di >= len(_ds):
                    _di = len(_ds) - 1
                _pick = _ds[_di]
                _rec = _pick["rec"]
                _chart = maimai.build_chart(_rec, maimai.diff_index_of(_pick["name"]))
                _st = maimai.chart_stats(_chart)
                _ct2 = _st["counts"]
                _bd = maimai.chart_breakdown(_chart)
                _shapes = "　".join(
                    f"{maimai.SHAPE_CN.get(k, k)} {v}" for k, v in
                    sorted(_bd["shapes"].items(), key=lambda kv: -kv[1])[:5]) or "—"

                st.markdown(
                    f"<div class='note'>🎼 <b>{_chart['song']['title']}</b>　"
                    f"<span style='color:{_chart['song']['color']};font-weight:700'>"
                    f"{_chart['song']['diff']}</span>　定数 {_chart['song']['ds']}　"
                    f"BPM {_chart['bpm']}　·　谱面 {_st['total']} 个音符（{_st['nps']}/秒，"
                    f"约 {int(_st['duration'])} 秒）<br>"
                    f"<span style='color:#7f8f96'>TAP {_ct2.get('tap',0)}　"
                    f"HOLD {_ct2.get('hold',0)}　SLIDE {_ct2.get('slide',0)}　"
                    f"TOUCH {_ct2.get('touch',0)}　EX {_ct2.get('ex',0)}　"
                    f"<b style='color:#F5D442'>星星 {_ct2.get('break',0)}</b>"
                    f"（其中<b>滑动星星 {_bd['star_slide']}</b>）</span><br>"
                    f"<span style='color:#7f8f96'>SLIDE 形状：{_shapes}　·　"
                    f"全部 CRITICAL 的理论达成率 "
                    f"<b>{_bd['theoretical']:.4f}%</b></span></div>",
                    unsafe_allow_html=True)

                st.caption("👆 选好难度后点上面的「打这个 · 难度」，机台会在下方出现；"
                           "进了机台点画面任意位置即可开打。打的过程中这一页没有任何会刷新的控件，放心点。")

                with st.expander("⌨️ 键位与音符（点开看清楚再打）", expanded=False):
                    st.markdown(maimai.key_help(), unsafe_allow_html=True)
                    st.markdown(
                        "<div class='note' style='margin-top:6px'>"
                        "<b>TAP</b> 青色圆点　<b>BREAK 星星</b> 金色五角星　"
                        "<b>HOLD</b> 蓝色圆点带尾巴（按住）　<b>SLIDE</b> 紫色圆点带箭头（敲头再送终点）　"
                        "<b>滑动星星</b> 金色五角星 + 金色轨迹（判定按 BREAK 算，最值钱）　"
                        "<b>TOUCH / EX</b> 在中央屏（空格 / Shift）<br>"
                        "判定窗口和真机一致：CRITICAL ±33ms　PERFECT ±67ms　GREAT ±100ms　GOOD ±150ms。"
                        "</div>", unsafe_allow_html=True)
                    st.caption("机台里按 H 看同一份说明，按 I 直接导入谱面。")

                st.download_button(
                    "⬇️ 导出这张谱的 Simai 文本",
                    data=maimai.to_simai(_chart).encode("utf-8"),
                    file_name=f"{_chart['song']['title']}_{_chart['song']['diff']}.txt",
                    mime="text/plain", key="dx_dump",
                    help="导出的文本可以拿去别的谱面工具里改，也能再从「导入谱面」读回来。")

                st.markdown(
                    "<div class='note'>按舞萌真实的达成率评级结算："
                    "SSS+ / SSS / SS+ / SS / S+ / S / AAA / AA / A / BBB / B / C / D，"
                    "明细拆成 CRITICAL PERFECT / PERFECT / GREAT / GOOD / MISS，另外统计 FAST / SLOW。"
                    "结算页底部有一枚 <b>成绩码</b>，复制它，到「成绩登记」粘一下，这局就归你了。</div>",
                    unsafe_allow_html=True)
                st.caption("⚠️ 进了机台先点一下画面（或按 Enter）让它拿到键盘焦点；"
                           "换歌或换难度之后也一样，点一下再开打。")

    with _ct[1]:
        st.markdown("#### 📄 导入谱面")
        st.caption(
            "支持舞萌圈通用的 **Simai** 文本格式（.txt / .simai），astroDX、Majdata 那些工具用的都是它。"
            "粘进来或传文件都行，读出来的谱面直接进机台打。")

        _ex = simai.examples()
        _c1, _c2 = st.columns([1, 1])
        with _c1:
            _pick_ex = st.selectbox("载入一份示例（对照着看语法）",
                                    ["（不选）"] + list(_ex.keys()), key="simai_ex")
        with _c2:
            _div = st.selectbox("默认时值（谱面里没写 [x:y] 时用这个）",
                                [4, 8, 16], index=0, key="simai_div",
                                help="4 = 每个逗号 1/4 拍（16 分音符），8 = 1/8 拍（32 分），16 = 1/16 拍。")
        _up = st.file_uploader("或者上传谱面文件（.txt / .simai / .json）",
                               type=["txt", "simai", "json", "ma2"], key="simai_up")

        # 注意：text_area 带了 key，一旦渲染过，后面再改 value 是不生效的
        # （widget 状态会压过新默认值）。所以「选了示例 / 传了文件」时，
        # 要在控件创建之前把新内容写进 session_state，才能真的灌进框里。
        _default = ""
        _src = ""
        if _pick_ex != "（不选）":
            _default = _ex[_pick_ex]
            _src = "ex:" + str(_pick_ex)
        if _up is not None:
            try:
                _default = _up.getvalue().decode("utf-8", errors="replace")
                _src = "up:" + str(getattr(_up, "name", "") or "")
            except Exception:
                _default = ""
                _src = ""
        if _src and st.session_state.get("simai_src") != _src:
            st.session_state["simai_src"] = _src
            st.session_state["simai_slot"] = int(st.session_state.get("simai_slot") or 0) + 1
        _slot = int(st.session_state.get("simai_slot") or 0)

        _txt = st.text_area("谱面文本（Simai）", value=_default, height=200,
                            key=f"simai_text_{_slot}",
                            placeholder="&bpm=160\n&offset=0\n&title=我的谱面\n\n#MASTER\n(160)1^3,2b^4,5^7,6b^8,")

        if st.button("🔍 解析并打这一张", key="simai_go", type="primary"):
            if not (_txt or "").strip():
                st.warning("先粘点内容进来（或者选一份示例）。")
            else:
                _res = maimai.from_simai(_txt, default_div=int(_div))
                if _res["errors"]:
                    st.error("读不出来：" + "；".join(_res["errors"]))
                elif not _res["charts"]:
                    st.error("一个难度都没解析成功。")
                else:
                    st.session_state["dx_import"] = _res
                    st.success(f"读出来 {len(_res['charts'])} 个难度：" +
                               "、".join(_res["charts"].keys()))
                    if _res["warnings"]:
                        st.warning("\n".join(_res["warnings"][:6]))

        _imp = st.session_state.get("dx_import")
        if _imp and _imp.get("charts"):
            _names = list(_imp["charts"].keys())
            _dn = st.selectbox("打哪个难度", _names, key="simai_diff")
            _ch = _imp["charts"][_dn]
            _bd2 = maimai.chart_breakdown(_ch)
            st.markdown(
                f"<div class='note'>🎼 <b>{_ch.get('title') or '导入谱面'}</b>　"
                f"{_ch.get('diff','')}　BPM {_ch.get('bpm',0)}　·　"
                f"{_bd2['total']} 个音符　<span style='color:#F5D442'>星星 {_bd2['breaks']}</span>"
                f"（滑动星星 {_bd2['star_slide']}）　·　理论达成率 "
                f"<b>{_bd2['theoretical']:.4f}%</b></div>", unsafe_allow_html=True)
            st.iframe(maimai.cabinet_html(_ch), height=700)

        with st.expander("📖 Simai 语法速查", expanded=False):
            st.markdown(
                "<div class='note'>"
                "<b>头部</b>：<code>&amp;bpm=160</code>　<code>&amp;offset=0</code>　"
                "<code>&amp;title=曲名</code>　<code>&amp;artist=艺人</code><br>"
                "<b>难度块</b>：<code>#Master</code>　<code>#Expert</code>（认不出来会当作 MASTER）<br>"
                "<b>BPM 变更</b>：写在事件前，<code>(192)</code><br>"
                "<b>同押</b>：花括号，<code>{1,2}</code><br>"
                "<b>时值</b>：方括号，<code>[4:1]</code> = 4 拍，<code>[1:4]</code> = 1/4 拍<br><br>"
                "<b>TAP</b>　<code>1</code> ~ <code>8</code>　（1 对应左上，顺时针一圈，和键位 A S D F J K L ; 一一对应）<br>"
                "<b>星星</b>　<code>1b</code><br>"
                "<b>HOLD</b>　<code>1h[4:1]</code><br>"
                "<b>SLIDE</b>　<code>1-3</code> 直线　<code>1^3</code> 弧　<code>1&lt;3</code> 左弧　"
                "<code>1&gt;3</code> 右弧　<code>1v3</code> V字　<code>1w3</code> Wifi　"
                "<code>1s3</code> S形　<code>1z3</code> Z形　<code>1$3</code> 扇形<br>"
                "<b>滑动星星</b>　<code>1b^3</code>（头是星星的 SLIDE，判定按 BREAK 算）<br>"
                "<b>连滑</b>　<code>1-2-3</code>（拆成 1-2 和 2-3 两段）<br>"
                "<b>中央屏 TOUCH</b>　<code>A1</code>~<code>A8</code>　<code>B1</code>~<code>B8</code>　"
                "<code>C</code>（中心）　带 h 是 TOUCH HOLD：<code>C1h[4:1]</code><br>"
                "<b>EX</b>　<code>E1</code>~<code>E8</code>"
                "</div>", unsafe_allow_html=True)

    with _ct[3]:
        st.markdown("#### 📥 成绩登记")
        st.caption("把游戏结算页那枚成绩码粘进来。它带校验位，改过或截断了会被认出来。")
        _code = st.text_area("成绩码（MM1: 开头那一串）", height=90, key="pl_code",
                             placeholder="MM1:eyJnIjoiY2FiaW5ldC...:xxxxx")
        if st.button("📥 登记这局成绩", key="pl_submit", type="primary"):
            ok, msg = playlog.submit(uname, _code or "")
            if ok:
                st.success(msg); st.rerun()
            else:
                st.error(msg)
        _plays = playlog.list_plays(uname, limit=8)
        if _plays:
            st.markdown("**最近登记的几局**")
            for p in _plays:
                st.markdown(
                    f"<div class='note'>🎮 {p.get('t', '—')}　"
                    f"<b>{p.get('rk', '')}</b>　达成率 {p.get('ach', '—')}%　"
                    f"<span style='color:#7f8f96'>{p.get('day', '')} {str(p.get('at', ''))[11:19]}</span></div>",
                    unsafe_allow_html=True)
        else:
            st.info("还没有登记过成绩。")

    with _ct[1]:
        st.markdown("#### 🎖 段位认定")
        _cur = dan.get(uname).get("dan", "")
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(dan.badge_html(_cur or "无段位", uname), unsafe_allow_html=True)
        with c2:
            st.markdown("**段位只升不降。** 想升段得过两关："
                        "① 实技 —— 交一枚机台成绩码，曲目定数和达成率都要够线；"
                        "② 笔试 —— 定数竞猜 / BPM 速猜 / 定数比大小，题目全部出自本地曲库。")
            st.markdown(dan.ladder_html(_cur), unsafe_allow_html=True)

        _target = dan.next_dan(_cur) or dan.DANS[-1]
        _names = [d["name"] for d in dan.DANS]
        _pick = st.selectbox("要考哪一段？", _names,
                             index=_names.index(_target["name"]) if _target["name"] in _names else 0,
                             key="dan_pick")
        _tgt = dan.DANS[dan.index_of(_pick)]

        st.markdown(f"<div class='note'>报考 <b>{_tgt['name']}</b>："
                    f"实技达成率 ≥ <b>{_tgt['need']:.0f}%</b>（曲目定数 {_tgt['ds'][0]:g}~{_tgt['ds'][1]:g}）　·　"
                    f"笔试 ≥ <b>{_tgt['written']}</b> 分（{_tgt['n']} 题）</div>",
                    unsafe_allow_html=True)

        # ---- 实技 ----
        st.markdown("**① 实技**")
        _cab_plays = playlog.list_plays(uname, game="cabinet", limit=12)
        _play = None
        if _cab_plays:
            _opts = [f"《{p.get('t','')}》{p.get('df','')} {p.get('ds','')} · "
                     f"{p.get('ach','')}% {p.get('rk','')} · {p.get('day','')}"
                     for p in _cab_plays]
            _sel = st.selectbox("用哪一局成绩？", _opts, key="dan_play")
            _play = _cab_plays[_opts.index(_sel)]
        else:
            st.warning("还没有机台成绩。先去「🕹 机台」打一局，把结算页的成绩码粘到「成绩登记」，"
                       "再回来考段位。")
        _pcode = st.text_input("或者直接粘一枚新的成绩码", key="dan_code")
        if st.button("📥 登记并用它", key="dan_code_go"):
            ok, msg = playlog.submit(uname, _pcode or "")
            if ok:
                st.success(msg); st.rerun()
            else:
                st.error(msg)
        _pr = dan.grade_practical(_tgt, _play)
        st.markdown(f"<div class='note'>{'✅' if _pr['ok'] else '⏳'} {_pr['msg']}"
                    + (f"<br>{_pr['note']}" if _pr.get("note") else "") + "</div>",
                    unsafe_allow_html=True)

        # ---- 笔试 ----
        st.markdown("**② 笔试**")
        if not records:
            st.info("曲库未加载，出不了题。")
        else:
            if st.button("📝 生成这套题", key="dan_exam_new"):
                st.session_state["dan_exam"] = {
                    "dan": _pick,
                    "quiz": dan.make_exam(_tgt, records, f"{uname}-{time.time()}"),
                }
                st.session_state["dan_ans"] = {}
                st.rerun()
            _ex = st.session_state.get("dan_exam")
            if _ex and _ex.get("dan") == _pick and _ex.get("quiz"):
                _ans = st.session_state.get("dan_ans", {})
                for i, q in enumerate(_ex["quiz"]):
                    k = q.get("kind")
                    if k == "ds":
                        _info = f"**《{q['title']}》**"
                        if not q.get("hard"):
                            _info += f" · {q['genre']} · BPM {q['bpm'] or '—'} · {q['artist']}"
                        st.markdown(_info)
                        _ans[i] = st.slider("定数", 1.0, 15.0, 12.0, 0.1, key=f"danq_{i}")
                    elif k == "bpm":
                        st.markdown(f"**《{q['title']}》** · {q['artist']}")
                        _ans[i] = st.number_input("BPM", 40, 320, 150, 1, key=f"danq_{i}")
                    else:
                        st.markdown(f"**哪首定数更高？**")
                        _ca, _cb = q["a"], q["b"]
                        _ans[i] = st.radio(
                            f"A 《{_ca['title']}》　vs　B 《{_cb['title']}》",
                            ["a", "b"], format_func=lambda x: ("A" if x == "a" else "B"),
                            horizontal=True, key=f"danq_{i}")
                st.session_state["dan_ans"] = _ans
                if st.button("✅ 交卷", key="dan_grade", type="primary"):
                    _g = dan.grade_exam(_ex["quiz"], _ans)
                    _need = int(_tgt["written"])
                    _pass_w = _g["total"] >= _need
                    for row in _g["rows"]:
                        st.markdown(f"<div class='note'>{row['i']+1}. {row['kind']}　"
                                    f"<b>{row['score']}</b> 分　{row['text']}</div>",
                                    unsafe_allow_html=True)
                    st.markdown(f"<div class='hero'><div class='name' style='font-size:1.4rem'>"
                                f"笔试 {_g['total']} 分 / 需要 {_need} 分</div>"
                                f"<div class='meta'>{'通过' if _pass_w else '没过'}</div></div>",
                                unsafe_allow_html=True)
                    if _pass_w and _pr.get("ok"):
                        _ok = dan.award(uname, _pick, {
                            "written": _g["total"], "ach": _pr.get("ach"),
                            "dan_before": _cur})
                        if _ok:
                            st.balloons()
                            st.success(f"🎖 合格！{uname} 现在是 **{_pick}**。")
                            st.session_state.pop("dan_exam", None)
                            st.session_state.pop("dan_ans", None)
                        else:
                            st.info("已经有过同等或更高的段位了。")
                    elif not _pass_w:
                        st.warning("笔试没过，再练练曲库知识。")
                    else:
                        st.warning("笔试过了，但实技那关还没够线。")


# ---------------- 玩家档案 ----------------
def page_profile():
    st.markdown("### 📊 玩家档案")
    _dan = dan.get(uname).get("dan", "")
    _c1, _c2 = st.columns([1, 2])
    with _c1:
        st.markdown(dan.badge_html(_dan or "无段位", uname, size=150), unsafe_allow_html=True)
        st.markdown(dan.ladder_html(_dan), unsafe_allow_html=True)
    with _c2:
        _sp = playlog.streak(uname)
        _done = playlog.checked_today(uname)
        st.markdown(f"<div class='hero'><div class='name' style='font-size:1.4rem'>{uname}</div>"
                    f"<div class='meta'>段位 {_dan or '—'}　·　连续打卡 {_sp} 天　·　"
                    f"已登记 {playlog.total_plays(uname)} 局</div></div>", unsafe_allow_html=True)
        if _done:
            st.success(f"今天已经打过卡了（连续 {_sp} 天）。")
        else:
            if st.button("📅 今天打卡", key="pl_checkin", type="primary"):
                ok, msg, n = playlog.checkin(uname)
                if ok:
                    st.success(f"{msg} 连续 {n} 天。"); st.rerun()
                else:
                    st.info(msg)

    _dims = playlog.dimension_scores(uname)
    _p1, _p2 = st.columns([1, 1])
    with _p1:
        st.markdown("#### 🕸 能力雷达")
        if _dims:
            st.markdown(radar_svg(_dims), unsafe_allow_html=True)
            st.caption("每一维取你在对应小游戏里最好的一局折算成 0~100。"
                       "没有成绩的维度显示为 0 —— 去玩一局就有了。")
        else:
            st.info("还没有登记任何小游戏成绩。去「🎮 小游戏」或「🕹 街机厅」玩一局，"
                    "把结算页的成绩码粘进「成绩登记」，这里就会长出形状。")
    with _p2:
        st.markdown("#### 🏅 各项目最佳")
        _bm = playlog.best_map(uname)
        if _bm:
            for g, p in _bm.items():
                st.markdown(f"<div class='note'>{playlog.DIM_OF_GAME.get(g, '综合')} · "
                            f"<b>{p.get('t', g)}</b>　{p.get('rk', '')}　"
                            f"{p.get('ach', '—')}%</div>", unsafe_allow_html=True)
        else:
            st.caption("暂无。")

    st.divider()
    st.markdown("#### 📄 成绩单（本地版 B30）")
    _sc = userdata.list_scores(uname)
    if not _sc:
        st.info("还没有手动录入的成绩。到「练习与成绩」里录几条，这里会排出你的 Best。")
    else:
        _by_ds = sorted([s for s in _sc if s.get("ds")],
                        key=lambda s: (-float(s["ds"]), -float(s.get("achievement") or 0)))[:10]
        _used = {id(s) for s in _by_ds}
        _by_ach = sorted([s for s in _sc if id(s) not in _used],
                         key=lambda s: -float(s.get("achievement") or 0))[:20]
        _ca, _cb = st.columns(2)
        with _ca:
            st.markdown("**Best 10 · 按定数**")
            for i, s in enumerate(_by_ds):
                st.markdown(f"<div class='note'>{i+1}. 《{s['title']}》{s.get('diff','')} "
                            f"<b>{s.get('ds')}</b>　{s.get('achievement')}%"
                            + ("　<b style='color:#F5D442'>FC</b>" if s.get("fc") else "")
                            + ("　<b style='color:#39C5BB'>AP</b>" if s.get("ap") else "")
                            + "</div>", unsafe_allow_html=True)
        with _cb:
            st.markdown("**Best 20 · 按达成率**")
            for i, s in enumerate(_by_ach):
                st.markdown(f"<div class='note'>{i+1}. 《{s['title']}》{s.get('diff','')} "
                            f"<b>{s.get('achievement')}%</b>　定数 {s.get('ds')}</div>",
                            unsafe_allow_html=True)
        _st = userdata.stats(uname)
        st.caption(f"共 {_st['count']} 条手动成绩 · 平均达成率 {_st['avg_achievement']}% · "
                   f"FC {_st['fc']} 次 · AP {_st['ap']} 次 · 最高定数 {_st['max_ds']}　"
                   f"（全部手动录入，非官方同步）")

    _plays = playlog.list_plays(uname, limit=20)
    if _plays:
        st.divider()
        st.markdown("#### 🎮 游玩记录（成绩码登记）")
        for p in _plays:
            st.markdown(f"<div class='note'>{p.get('day','')} {str(p.get('at',''))[11:19]}　"
                        f"《{p.get('t','—')}》{p.get('df','') or ''}　<b>{p.get('rk','')}</b>　"
                        f"{p.get('ach','—')}%"
                        + (f"　MAX {p.get('mx')}" if p.get("mx") else "")
                        + "</div>", unsafe_allow_html=True)
        if st.button("🗑 清空我的游玩记录", key="pl_clear"):
            playlog.clear(uname); st.rerun()


# ---------------- 路由 ----------------
page = st.session_state.get("page", "home")
if page == "home":
    page_home()
elif page == "tracks":
    page_tracks()
elif page == "practice":
    page_practice()
elif page == "games":
    page_games()
elif page == "cabinet":
    page_cabinet()
elif page == "profile":
    page_profile()
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
