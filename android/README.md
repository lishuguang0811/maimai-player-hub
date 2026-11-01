# 打包说明：独立运行版 / exe / APK

现在有两份原料，**整合大厅**是推荐的那份：

| 原料 | 内容 | 大小 |
|---|---|---|
| `standalone/maimai-hub.html` | **整合大厅**：机台 + 20 个小游戏 + 曲库（能直接开打）+ 成绩 + 设置 + 运势 | 约 380 KB |
| `standalone/maimai-dx.html` | 只有机台（全屏打歌，最纯粹） | 约 105 KB |

两份都是**单文件、零外部请求、离线可玩**——引擎和曲库都内联在里面，
断网、拷 U 盘、发给别人都能跑。

## 0. 先生成原料

```bash
cd k-k-clean-unzipped
python work/build_hub.py 400             # 整合大厅（推荐）
python work/build_standalone.py 400      # 纯机台版，可选项
```

`400` = 内置曲库首数，可以改。


## 1. 最省事：直接双击

双击 `standalone/maimai-hub.html`，用浏览器打开就能玩 —— 电脑上这样最快。
想更像一个应用：命令行 `msedge.exe --app=<文件路径>` 就开一个没有地址栏的独立窗口。

## 2. Windows exe（轻量版，推荐）

```bash
python package/build_exe.py              # 整合大厅
python package/build_exe.py cabinet      # 只要纯机台
```

产出 `package/dist/舞萌DX大厅.exe`（约 7.7 MB，PyInstaller 单文件，秒开）。
图标优先用工程根的 `app-icon.ico`（找不到就退回外部那一份，再找不到就不带图标）。

启动器做的事：
- 把内嵌的 HTML 释放到 `%LOCALAPPDATA%\MaimaiDX\www`
- 起一个只有 `127.0.0.1` 能访问的静态服务 —— **用 http:// 而不是 file://**，
  这样 localStorage（个人最佳、判定偏移、导入的谱面）才存得住
- 找 Edge / Chrome 用 `--app` 模式开一个独立窗口；都找不到就退回系统默认浏览器
- 关掉窗口后进程自己退出

不需要 Python、不需要联网。

## 2.5 Windows exe（完整版：整个主程序）

```bash
python package/build_full_exe.py         # onedir：一个文件夹，启动快
python package/build_full_exe.py onefile # 单文件 exe，但每次启动要解压，慢
```

这个把**整个 Streamlit 主程序**都打进去了 —— 账号、私人剧情与信件、
曲库收藏、练习成绩、段位、攻略、所有小游戏、机台全都在里面，
电脑上不装 Python 也能双击打开。

代价是体积：Streamlit + pandas / numpy / pyarrow 那一堆依赖一起进去，
是**几百 MB** 的量级，启动要等几秒（数据在 `%LOCALAPPDATA%\MaimaiHub\data`）。
只想要「打歌 + 小游戏」的话用上面的轻量版就够了。

## 3. Android APK —— A. 真原生版（推荐）

```
package\apk\舞萌DX-原生版.apk        （约 0.15 MB）
```

**没有 WebView，没有 HTML。** 整个游戏是一套 Java 原生引擎，和 AstroDX 一个路子：

| 层 | 用什么 |
|---|---|
| 画面 | `SurfaceView` + 自己的渲染线程，Canvas 直出（判定环、八分区、NOTE、9 种 SLIDE 轨迹、HUD、**首页/选曲/演奏/结算/成绩/设置 六个场景**） |
| 声音 | `AudioTrack` 现场合成 —— 按 BPM 生成 4 小节伴奏（鼓/军鼓/踩镲/贝斯/和弦/旋律）+ **13 种舞萌风「咔哒」判定音效**（接住星星的 blip、划过每颗箭头的「カチッ」tick、划过的「嗖」、各档判定的短促高频 click），**不打包任何音频文件** |
| 输入 | `MotionEvent` 多点触控：手指落在判定环哪个扇区就敲哪个，按住起点星星后**按序划过路径箭头**到终点 = SLIDE 送达，点中央屏 = TOUCH / EX，支持多指同押 |
| 数据 | `SharedPreferences` 存个人最佳（按 曲+难度）、音符速度、判定偏移、音量 |
| 曲库 | 内置 **约 1277 首**（本地快照全量），每首 5 个难度，谱面按 BPM + 定数确定性生成 |

引擎代码在 `package/native/src/com/maimai/dx/`：

```
Chart.java   谱面生成（xorshift32 + FNV-1a 种子，同曲同难度永远同一张谱）+ Simai 解析
Game.java    判定（真机窗口 33/67/100/150/200ms）+ 达成率（星星加成封顶 +1%，上限 101.0000%）
Audio.java   AudioTrack 合成器
Render.java  全部绘制
GameView.java 渲染线程 + 触控 + 六个场景（首页/选曲/演奏/结算/成绩/设置）
MainActivity.java  入口
Songs.java   内置曲库（由 work/gen_songs_java.py 生成）
```

**Chart / Game 是纯 Java，一行 android.* 都没有**，所以能在桌面上直接跑单测：

```bash
javac -encoding UTF-8 -d out package\native\src\com\maimai\dx\{Chart,Game,Songs}.java package\native\test\EngineTest.java
java -cp out com.maimai.dx.EngineTest      # 71 项，全过
```

单测会把整首歌真打一遍：全 CP 打法正好打到理论达成率（101.0000%）、
手滑打法掉到 51.78% / D、判定窗口边界、星星加成封顶、谱面确定性、
五个难度都有星星 SLIDE、同分区零冲突、Simai 解析、曲库全可用、
**以及滑星星的「接住→拖到终点」完整手感（接住锁判定、拖到终点落地、抬指没收尾=MISS、超时没收尾=MISS、提前按住自动接住）**。

### 完整 App 结构（不是只有一个游戏）

启动直接进**首页（HOME）**，三个大按钮：**曲库 / 开始、成绩、设置**。
整套流程是真·APP 外壳，而不只是单个打歌画面：

| 场景 | 内容 |
|---|---|
| 首页 HOME | 标题 + 三个入口（曲库·开始 / 成绩 / 设置） |
| 选曲 SELECT | 6 个难度筛选 chip（全部/BASIC/ADV/EXP/MAS/ReM）、可滚动歌单、每首显示历史最佳达成率、右侧难度按钮 |
| 演奏 PLAY | 判定环 + 八分区 + NOTE + SLIDE 轨迹 + HUD（分数/连击/进度/达成率）+ 倒计时提示「星星：按住起点再拖到终点」 |
| 结算 RESULT | 评级、分数、达成率、各判定数、最大连击，可回选曲 |
| 成绩 SCORES | 按达成率排序的历史最佳前若干条（按 曲+难度存 `SharedPreferences`） |
| 设置 SET | 音符速度、判定偏移、音量 |

### 滑星星手感（照 AstroDX 真机逻辑移植）

这版直接照 **AstroDX（`MonsterDruide1/AstroDX` 开源）** 的滑星星逻辑移植，核心是按序划过箭头：

1. **按下起点扇区 = 接住星星**：判定**在按下那一刻锁定**（用当时的时机窗口定 CP/P/GR/GD），
   头星脉动、画出跟随手指的轨迹。
2. **路径被切成一串有序箭头 waypoint**：`Chart.slideWaypoints` 把从起点到终点的路径切成一颗颗箭头
   （沿环花样走短弧 `p→...→q`；line/v/wifi/fan/s_cur/z_cur 等穿心花样则 `[中央, q]`）。
3. **手指按序划过每颗箭头才送达**：`Game.slideMove` 要求手指依次经过这些箭头扇区，
   每划过一颗播一次「カチッ」tick 音（`Audio.SE_SLIDE_TICK`）、并点亮那颗箭头（Render 里逐颗亮起）；
   容許漏划中间几颗（对应真机的 `slideTolerance`），但必须到达终点才落地锁定的判定。
   **划不过去、抬指没收尾、或超时没收尾 → MISS。**
4. **提前按住目标扇区**：手指在星星到达前已按住（`heldMask`），星星一到**自动接住**，再划到终点同样送达。

引擎层 `Game.pressRing / slideMove / lift / sweep` + `Chart.slideWaypoints` 实现，
**16 条专项单测**（路径箭头计算、逐箭头返回 tick、跳中间直接到终点也送达、拖到终点落地 CP、
抬指/超时/完全没碰=MISS、提前按住自动接住、line 穿心过中央也送达 等）全过。

### 音效（舞萌风「咔哒」，非正弦 ding）

之前用的是正弦「叮」。这版按舞萌那种**短促高频、起音带一点噪声 click、指数快速衰减**的
「咔哒」味来合成（`Audio.mkTick`），接住星星给一个 blip、划过给一个带通噪声「嗖」（`mkSweep`）、
MISS 给一个低沉闷响。真舞萌的音源没法打包进 APK（版权 + 体积），这是**同风格的实时合成近似**，
听感比纯正弦更接近街机。

```bash
python package/build_native_apk.py
```

产出 `package/apk/舞萌DX-原生版.apk`，minSdk 23 / targetSdk 35 / 横屏 / 常亮 / 硬件加速，v1+v2+v3 签名。

## 3.5 Android APK —— B. WebView 版（整合大厅）

```
package\apk\舞萌DX大厅-3.2.0.apk     （约 0.4 MB）
```

**不装 Android Studio、不用 Gradle，直接就编出来了。** `package/build_apk.py`
自己走完官方工具链的每一步：

```
aapt2 compile（编译资源/图标）
   ↓
aapt2 link（生成二进制 AndroidManifest.xml + resources.arsc，塞进 assets）
   ↓
javac（对着 android.jar 编 MainActivity.java）
   ↓
d8（class → classes.dex，min-api 23）
   ↓
zipalign -p 4
   ↓
apksigner（v1 + v2 + v3 三套签名）
```

编出来的 APK：`minSdk 23`（Android 6+）/ `targetSdk 35`（Android 15）/ 包名 `com.maimai.hub`，
里面只有 `classes.dex`（3.6 KB）+ 整合大厅 HTML（390 KB，STORED 不压缩）+ 图标，
**零网络权限、零外链**，装上就能离线玩。

### 怎么编

```bash
python package/fetch_toolchain.py     # 第一次：拉 JDK17 + build-tools35 + platform35（约 400 MB）
python package/build_apk.py           # 之后每次改完引擎重跑这一条就够
```

`fetch_toolchain.py` 从**官方分发包**直接下载解压，不装 IDE、不装 SDK Manager：

| 东西 | 来源 |
|---|---|
| JDK 17 | 华为镜像的 OpenJDK（国内快；不通就自动换 Microsoft） |
| build-tools 35 | `dl.google.com/android/repository/build-tools_r35.0.1_windows.zip` |
| platform 35（android.jar） | `dl.google.com/android/repository/platform-35_r02.zip` |

默认落在 `..\ .toolchain`（工程目录外面，不把工程撑大）。想换位置：
`python package/fetch_toolchain.py D:\tools\android`，然后
`set APK_TOOLCHAIN=D:\tools\android` 再编。

### 已经调好的几件事
- **横竖屏都行**（`screenOrientation=sensor`）+ 沉浸式全屏，状态栏不吃掉判定区
- `FLAG_KEEP_SCREEN_ON` 打歌时不息屏
- `setMediaPlaybackRequiresUserGesture(false)` —— Web Audio 不用先点一下才出声
- `setDomStorageEnabled(true)` + `setAllowUniversalAccessFromFileURLs(true)` ——
  `file://` 下 localStorage 可用，成绩和设置存得住
- `hardwareAccelerated` —— Canvas 走 GPU，NOTE 多也不掉帧
- `-0 html` —— HTML 资产不压缩（绕开 AssetManager 对压缩资产的解包上限）
- 返回键：Web 页面能后退就后退，退不动才退出 App

### 备用：Gradle 工程

`package/android/` 那份 Gradle 工程还在（Android Studio 打开就能 Build），
适合你想改原生代码、加 SDK、或用正式签名的情况。两条路产物是一样的。

## 4. 手机上怎么用

装好 APK（或把 `maimai-hub.html` 传过去用浏览器打开、加到主屏幕）之后：

- 大厅顶部横向滑着选：**机台 / 小游戏 / 曲库 / 成绩 / 设置 / 运势 / 说明**
- 机台里的操作：
  - 点圆环的某个方位 = 敲那个分区
  - **按住再划到另一个方位** = SLIDE 送达终点
  - 点中央屏 = TOUCH / EX
  - 支持多点同时按（双押要两根手指）
- 曲库页搜到歌点「开打」直接进机台
- 横过来判定环更大；竖屏也能玩

## 4.5 怎么把这个文件弄到手机上

三种都行，挑最顺手的：

1. **微信 / QQ / 邮件**发给自己，手机上用浏览器打开 → 加到主屏幕（最快）
2. **同一 WiFi 直接开**：在电脑上 `cd standalone && python -m http.server 8000`，
   手机浏览器访问 `http://电脑的IPv4:8000/maimai-hub.html`
3. **装 APK**：把 `package\apk\舞萌DX大厅-3.2.0.apk` 传到手机点开安装（会提示"未知来源"，允许即可）—— 见第 3 节

## 5. 换曲库 / 换引擎之后

只要重新跑一遍：

```bash
python work/gen_songs_java.py         # 曲库变了才需要
python work/build_hub.py 400          # 重生成整合大厅
python package/build_exe.py           # 重打 Windows exe
python package/build_native_apk.py    # 重打原生 Android apk
python package/build_apk.py           # 重打 WebView 版 apk
```

三份产物就都更新了。

> 两个 exe 都实测能起来：解包 HTML → 起 127.0.0.1 本地服务 → 拉起 Edge 窗口
> （日志里能看到 `GET /index.html 200`）。
> APK 实测：原生版 `apksigner verify` → `Verifies`（v1/v2/v3 全 true）、
> `zipalign -c -p 4` 通过、`aapt2 dump badging` 正常读出 `com.maimai.dx` / 标签「舞萌 DX」、
> `dexdump` 能看到 `Lcom/maimai/dx/MainActivity;` 以及全部 7 个引擎类（含 Chart/Game/Audio/Render/GameView）。
> WebView 整合大厅版 `dexdump` 能看到 `Lcom/maimai/hub/MainActivity;` 继承 `android.app.Activity`。

