# -*- coding: utf-8 -*-
"""
config.py —— 全局配置（舞萌助手）

所有可调参数集中在这里。账号数据在 data/accounts.json，
名言在 data/quotes.json，曲库快照在 data/maimai_songs.json。

想改成自己的版本，优先改本文件顶部的「个人资料」段，
不需要动业务代码。
"""
import os
from pathlib import Path

# ---------- 路径 ----------
BASE_DIR = Path(__file__).resolve().parent
# 打包成桌面版时，程序文件只读、用户数据写到可写目录；
# 开发时默认都放在项目内的 data/。
DATA_DIR = Path(os.environ.get("MPH_DATA_DIR", BASE_DIR / "data"))
SONGS_CACHE = DATA_DIR / "maimai_songs.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"     # 本地账号库（密码加盐哈希）
QUOTES_FILE = DATA_DIR / "quotes.json"         # 2000-2017 动漫/Galgame 名言
SHARE_DIR = DATA_DIR / "share"
BG_DIR = DATA_DIR / "bg"                       # 程序化生成的主题背景
MIKU_DIR = DATA_DIR / "miku"                   # 初音插画（原创/自备）

# ---------- 个人资料（改成你自己的） ----------
# 「私人空间」的入口：注册时使用这个用户名，会触发身份验证。
OWNER_NAME = "旅人"
OWNER_BIRTHDAY = (1, 1)          # 月, 日
OWNER_BIRTH_YEAR = 2000          # 用于算年龄

# 私人空间首页展示的资料。可自由修改，或登录管理员后在面板里改应用名/生日。
OWNER_SUBJECT = {
    "name": OWNER_NAME,
    "birthday": f"{OWNER_BIRTH_YEAR:04d}-{OWNER_BIRTHDAY[0]:02d}-{OWNER_BIRTHDAY[1]:02d}",
    "city": "北京市",
    "level": "高手",
    "level_tag": "高水平玩家",
    "likes": ["初音未来（Hatsune Miku）", "VOCALOID / 术力口",
              "《世界计划 缤纷舞台》", "舞萌 DX"],
    "welcome": "欢迎回来。今天也把手感养好，把喜欢的歌唱完。",
}
PRIVATE_TITLE = f"为{OWNER_NAME}准备的今日节奏计划"

# 专属登录限流：连续失败 N 次后锁定 cooldown 秒
VIP_MAX_FAILS = 5
VIP_LOCK_SECONDS = 60

# ---------- 天气：默认城市（可改） ----------
CITY = {
    "name": "北京市",
    "latitude": 39.9042,
    "longitude": 116.4074,
    "timezone": "Asia/Shanghai",
}
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_TIMEOUT = 8

# ---------- 曲库来源（国服口径） ----------
SONGS_API = "https://www.diving-fish.com/api/maimaidxprober/music_data"
SONGS_SOURCE_NOTE = "数据源：diving-fish 舞萌DX国服曲库快照"
CACHE_MAX_DAYS = 14

# 难度顺序与中文名（舞萌 DX 官方配色：绿黄红紫白）
DIFF_ORDER = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]
DIFF_META = {
    "Basic":     {"cn": "绿", "short": "BASIC", "color": "#3fa34d", "text": "#eaffea"},
    "Advanced":  {"cn": "黄", "short": "ADV",   "color": "#d99a00", "text": "#fff6e0"},
    "Expert":    {"cn": "红", "short": "EXP",   "color": "#d23b3b", "text": "#ffecec"},
    "Master":    {"cn": "紫", "short": "MAS",   "color": "#8e44ad", "text": "#f6ecff"},
    "Re:MASTER": {"cn": "白", "short": "ReM",   "color": "#e8e8e8", "text": "#222222"},
}

# ---------- 账号等级 -> 推荐窗口（跨难度，全分类） ----------
# 容量为 1404 首国服快照实测。每档窗口覆盖多个难度色，保证"绿黄紫红都有"。
LEVELS = {
    "新手": {
        "diffs": ["Basic", "Advanced", "Expert"], "ds_min": 1.0, "ds_max": 9.9,
        "tip": "先把手感养稳，挑 BPM 慢的，读谱压力小一半。",
        # 实测 1281 首
    },
    "进阶": {
        "diffs": ["Expert"], "ds_min": 8.0, "ds_max": 11.9,
        "tip": "Expert 是通往高手的必经之路，认真读谱，不追成绩。",
        # 实测 977 首
    },
    "高手": {
        "diffs": ["Expert", "Master"], "ds_min": 11.0, "ds_max": 13.9,
        "tip": "状态最好的一段留给 MASTER，可以认真冲一次。",
        # 实测 1268 首
    },
    "魔王": {
        "diffs": ["Master", "Re:MASTER"], "ds_min": 13.0, "ds_max": 15.0,
        "tip": "曲库天花板，量力而行，别上头连币。",
        # 实测 978 首
    },
}
LEVEL_ORDER = ["新手", "进阶", "高手", "魔王"]
DEFAULT_LEVEL = "高手"

# 每档推荐几首
PICKS_PER_TIER = 3
PICKS_MIN, PICKS_MAX = 1, 5

# ---------- 选曲权重 + 爱好加成 ----------
W_VOCALOID = 30.0
W_MIKU = 12.0
W_FAV = 20.0        # 用户收藏过的歌
W_SCORE_PROX = 6.0    # 接近用户常玩定数
# 爱好关键词 -> 加成。命中爱好的分类/艺术家会被加权，实现"按爱好筛歌"。
HOBBY_BOOST = [
    (["初音", "ミク", "miku", "vocaloid", "术力口", "术力", "世界计划", "プロセカ", "prosekai"],
     {"genre": "niconico & VOCALOID", "weight": 25.0, "miku_extra": 10.0}),
    (["东方", "touhou"], {"genre": "东方Project", "weight": 25.0}),
    (["音击", "中二", "ongeki", "chunithm"], {"genre": "音击&中二节奏", "weight": 20.0}),
    (["动漫", "动画", "anime", "流行"], {"genre": "流行&动漫", "weight": 15.0}),
    (["50 cent", "hiphop", "hip-hop", "说唱", "rap"], {"genre": None, "weight": 0.0,
     "note": "50 Cent 在国服曲库无收录，仅作偏好记录"}),
]
GENRE_PRIORITY = [
    "niconico & VOCALOID", "东方Project", "其他游戏",
    "音击&中二节奏", "流行&动漫", "舞萌",
]
VOCALOID_GENRE = "niconico & VOCALOID"
MIKU_KEYWORDS = ["初音ミク", "初音未来", "Hatsune Miku", "プロジェクトセカイ", "世界计划"]

# ---------- 生日彩蛋 ----------
BIRTHDAY_WISH_TITLE = "生日快乐"

# ---------- 名言（每次刷新一句，2000-2017 动漫/Galgame） ----------
QUOTES_YEAR_MIN, QUOTES_YEAR_MAX = 2000, 2017

# ---------- 视频链接（读谱用） ----------
# 不伪造具体视频地址，而是生成 B 站搜索链接（真实可用，直达该曲谱面确认视频搜索结果）。
BILIBILI_SEARCH = "https://search.bilibili.com/all?keyword={kw}"
VIDEO_KEYWORD_TPL = "maimai {title} 谱面确认"

# ---------- 背景图 ----------
BG_COUNT = 50
BG_WIDTH, BG_HEIGHT = 1600, 1000

# ---------- 分享图（Pillow） ----------
SHARE_WIDTH = 1080
SHARE_BG = (13, 17, 23)
SHARE_MIKU = (57, 197, 187)
SHARE_TEXT = (232, 246, 245)
SHARE_SUB = (159, 176, 182)
SHARE_CARD_BG = (23, 29, 38)
SHARE_LINE = (58, 70, 82)
FONT_TITLE_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothR.ttc", r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
]
FONT_CJK_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\YuGothR.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]
FONT_BOLD_CANDIDATES = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"]

# ---------- 界面文案 ----------
APP_NAME = "舞萌助手"
APP_SUBTITLE = "Hatsune Miku × maimai DX · 本地个人版"
DEFAULT_WELCOME = "今天是属于你的选曲日。手别凉着，先把手感找回来。"

# ---------- 管理员 ----------
ADMIN_NAME = "admin"          # 管理员账号名（登录后可进管理员面板改配置/名言/攻略）
ADMIN_PASSWORD_ENV = "MPH_ADMIN_PASSWORD"   # 首次运行时从这里读管理员密码

# ---------- 设置覆盖层（管理员面板可改，存 data/settings.json） ----------
SETTINGS_FILE = DATA_DIR / "settings.json"

# ---------- 密码规则 ----------
PW_MIN_LEN = 8               # 至少 8 位（不是"正好8位"）
# 必须同时包含 数字 + 大写字母 + 小写字母
# 生日可选范围
BIRTH_MIN_YEAR, BIRTH_MAX_YEAR = 1900, 2035

# ---------- 定位 / 机厅 / 币价 ----------
DEFAULT_CITY = {"name": "北京市", "latitude": 39.9042, "longitude": 116.4074}
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
IP_GEO_URLS = ["https://ipwho.is/", "https://ipinfo.io/json"]
GEO_TIMEOUT = 8
# 机厅 / 币价 搜索入口（真实可用，不伪造具体数据）
AMAP_SEARCH = "https://www.amap.com/search?query={kw}"
BAIDU_MAP_SEARCH = "https://map.baidu.com/search/{kw}"
MEITUAN_SEARCH = "https://apimall.meituan.com/#/search?keyword={kw}"
DOUYIN_SEARCH = "https://www.douyin.com/search/{kw}"
ARCADE_KEYWORD_TPL = "舞萌DX 机厅 {city}"
PRICE_KEYWORD_TPL = "舞萌DX 游戏币 价格 {city}"

# ---------- 攻略专区 ----------
GUIDES_FILE = DATA_DIR / "guides.json"

# ---------- 官方初音立绘 ----------
# 官方立绘为 Crypton 版权素材，程序不联网抓取、不打包。
# 个人非商用请从 piapro(https://piapro.net) 下载后用 work/import_miku.py 导入 data/miku/。
