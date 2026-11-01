package com.maimai.dx;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.view.MotionEvent;
import android.view.SurfaceHolder;
import android.view.SurfaceView;

import java.util.ArrayList;

/**
 * 机台本体 + App 外壳：SurfaceView + 自己的渲染线程 + 多点触控。
 *
 * 场景：HOME(主菜单) → SELECT/曲库(选曲+筛选) → PLAY(打歌) → RESULT(结算)
 *       HOME → SCORES(成绩) / SET(设置)
 *
 * 手机上没有 A S D F J K L ;，所以判定区直接按角度分成八块 ——
 * 手指落在哪一块就敲哪一块；滑星星要先「按住星星」再「拖到终点」才算过。
 */
public class GameView extends SurfaceView implements SurfaceHolder.Callback, Runnable {

    public static final int SCENE_SELECT = 0, SCENE_PLAY = 1, SCENE_RESULT = 2, SCENE_SET = 3,
            SCENE_HOME = 4, SCENE_SCORES = 5;

    /** 0=左上 1=左 2=左下 3=下 4=右下 5=右 6=右上 7=上（屏幕坐标，y 向下） */
    public static final double[] POS_A = new double[8];

    static {
        int[] deg = {225, 180, 135, 90, 45, 0, 315, 270};
        for (int i = 0; i < 8; i++) POS_A[i] = deg[i] * Math.PI / 180.0;
    }

    public int scene = SCENE_HOME;

    public final Game game = new Game();
    public final Audio audio = new Audio();
    public Render render;
    public Chart chart;

    // 选曲 / 曲库
    public int songIdx = 0;
    public int diffIdx = 4;
    public float scroll = 0, scrollVel = 0;
    public float rowH = 74;
    public int libDiff = -1;                 // -1=全部，0..4=只显示有该难度的曲子
    private int[] filt = null;               // 筛选后的曲库下标

    // 演奏
    public long t0;
    public long leadIn = 2600;          // 开场倒计时
    public float speed = 1.0f;
    public long offsetMs = 0;
    public Game.Result result;
    public boolean newRecord;

    // 成绩页
    public int[] scSong, scDiff;
    public float[] scAch;

    // 尺寸
    public int W = 1, H = 1;
    public float cx, cy, rJ, r0, rC;
    public float uiScale = 1f;

    private Thread thread;
    private volatile boolean alive;
    private SharedPreferences prefs;

    // 触控：pointerId -> 扇区（-2 中央，-1 无效）
    private final int[] pSector = new int[16];
    private final int[] pId = new int[16];
    private int pCount = 0;

    private float touchX, touchY, lastX, lastY;
    private long touchDownAt;
    private boolean dragging;

    private int heldMask = 0;                 // 当前按住的环上分区位图
    public double dragAngle = 0;              // 最近一次触摸角度（滑星星跟手用）

    public GameView(Context ctx) {
        super(ctx);
        getHolder().addCallback(this);
        setFocusable(true);
        setKeepScreenOn(true);
        render = new Render(this);
        prefs = ctx.getSharedPreferences("dx", Context.MODE_PRIVATE);
        speed = prefs.getFloat("speed", 1.0f);
        offsetMs = prefs.getLong("offset", 0);
        audio.bgmVol = prefs.getFloat("bgm", 0.5f);
        audio.seVol = prefs.getFloat("se", 0.8f);
        int[] d = Songs.diffsOf(0);
        diffIdx = d.length > 0 ? d[d.length - 1] : 4;
    }

    private void save() {
        SharedPreferences.Editor e = prefs.edit();
        e.putFloat("speed", speed);
        e.putLong("offset", offsetMs);
        e.putFloat("bgm", audio.bgmVol);
        e.putFloat("se", audio.seVol);
        e.apply();
    }

    // ============================================================ 生命周期

    public void surfaceCreated(SurfaceHolder h) {
        alive = true;
        thread = new Thread(this, "dx-render");
        thread.start();
    }

    public void surfaceChanged(SurfaceHolder holder, int fmt, int w, int nh) {
        W = w;
        H = nh;
        uiScale = Math.min(w / 1920f, nh / 1080f) * 1.6f;
        if (uiScale < 0.5f) uiScale = 0.5f;
        cx = w / 2f;
        cy = nh * 0.52f;
        rJ = Math.min(w, nh) * 0.40f;
        r0 = rJ * 0.20f;
        rC = rJ * 0.46f;
        rowH = nh / 11f;
        if (render == null) render = new Render(this);
    }

    public void surfaceDestroyed(SurfaceHolder h) {
        alive = false;
        audio.stop();
        if (thread != null) {
            try {
                thread.join(400);
            } catch (InterruptedException e) {
                // ignore
            }
            thread = null;
        }
    }

    public void run() {
        while (alive) {
            long a = System.nanoTime();
            try {
                step();
            } catch (Exception e) {
                // 别让一次异常把整个渲染线程带走（带走了就是黑屏）
            }
            Canvas c = null;
            try {
                c = getHolder().lockCanvas();
                if (c != null) {
                    synchronized (getHolder()) {
                        render.draw(c);
                    }
                }
            } catch (Exception e) {
                // ignore
            } finally {
                if (c != null) {
                    try {
                        getHolder().unlockCanvasAndPost(c);
                    } catch (Exception e) {
                        // ignore
                    }
                }
            }
            long cost = (System.nanoTime() - a) / 1000000L;
            long want = 8 - cost;                 // 目标 ~120fps 上限，省电靠 sleep
            if (want < 1) want = 1;
            if (want > 16) want = 16;
            try {
                Thread.sleep(want);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    private void step() {
        if (scene == SCENE_PLAY && game.running) {
            long raw = (System.nanoTime() - t0) / 1000000L - leadIn;
            game.offset = offsetMs;
            game.heldMask = heldMask;            // 把当前按住的扇区同步给引擎（提前按住也能接星星）
            game.advance(raw);
            if (game.finished) {
                endPlay();
            }
        } else if (scene == SCENE_PLAY) {
            game.decay();
        }
        if (scene == SCENE_SELECT) {
            scroll += scrollVel;
            scrollVel *= 0.86f;
            int n = listCount();
            float max = Math.max(0, n * rowH - (H - H * 0.22f));
            if (scroll < 0) { scroll = 0; scrollVel = 0; }
            if (scroll > max) { scroll = max; scrollVel = 0; }
        }
        game.decay();
    }

    // ============================================================ 流程

    public void startPlay(int song, int diff) {
        songIdx = song;
        diffIdx = diff;
        String title = Songs.title[song];
        int bpm = Songs.bpm[song] > 0 ? Songs.bpm[song] : 150;
        chart = Chart.generate(title, Songs.artist[song], bpm,
                Songs.ds[song][diff], diff, 78);
        game.load(chart);
        game.offset = offsetMs;
        game.start();
        result = null;
        newRecord = false;
        scene = SCENE_PLAY;
        t0 = System.nanoTime();
        audio.startBgm(chart.bpm);
    }

    private void endPlay() {
        game.stop();
        audio.stop();
        result = game.result();
        String key = "best|" + Songs.title[songIdx] + "|" + diffIdx;
        float old = prefs.getFloat(key, -1f);
        if (result.ach > old) {
            prefs.edit().putFloat(key, (float) result.ach).apply();
            newRecord = true;
        }
        audio.startBgm(chart.bpm <= 0 ? 150 : chart.bpm);
        audio.se(Audio.SE_CLEAR);
        scene = SCENE_RESULT;
    }

    public void backToSelect() {
        audio.stop();
        scene = SCENE_SELECT;
    }

    public void goHome() {
        audio.stop();
        scene = SCENE_HOME;
    }

    public float bestOf(int song, int diff) {
        return prefs.getFloat("best|" + Songs.title[song] + "|" + diff, -1f);
    }

    public int listCount() { return filt == null ? Songs.count() : filt.length; }

    public int listSong(int i) { return filt == null ? i : filt[i]; }

    private void rebuildFilt() {
        if (libDiff < 0) { filt = null; return; }
        ArrayList<Integer> a = new ArrayList<Integer>();
        for (int i = 0; i < Songs.count(); i++) {
            int[] d = Songs.diffsOf(i);
            for (int x : d) if (x == libDiff) { a.add(i); break; }
        }
        filt = new int[a.size()];
        for (int i = 0; i < a.size(); i++) filt[i] = a.get(i);
    }

    private void buildScores() {
        ArrayList<Integer> songs = new ArrayList<Integer>();
        ArrayList<Integer> diffs = new ArrayList<Integer>();
        ArrayList<Float> achs = new ArrayList<Float>();
        for (int i = 0; i < Songs.count(); i++) {
            for (int d = 0; d < 5; d++) {
                float b = bestOf(i, d);
                if (b >= 0) { songs.add(i); diffs.add(d); achs.add(b); }
            }
        }
        int n = songs.size();
        scSong = new int[n]; scDiff = new int[n]; scAch = new float[n];
        for (int i = 0; i < n; i++) { scSong[i] = songs.get(i); scDiff[i] = diffs.get(i); scAch[i] = achs.get(i); }
        // 按达成率降序
        for (int i = 0; i < n - 1; i++)
            for (int j = i + 1; j < n; j++)
                if (scAch[j] > scAch[i]) {
                    float fa = scAch[i]; scAch[i] = scAch[j]; scAch[j] = fa;
                    int ia = scSong[i]; scSong[i] = scSong[j]; scSong[j] = ia;
                    int ib = scDiff[i]; scDiff[i] = scDiff[j]; scDiff[j] = ib;
                }
        if (scSong.length > 300) {
            int m = 300;
            int[] a = new int[m]; int[] b = new int[m]; float[] c = new float[m];
            System.arraycopy(scSong, 0, a, 0, m);
            System.arraycopy(scDiff, 0, b, 0, m);
            System.arraycopy(scAch, 0, c, 0, m);
            scSong = a; scDiff = b; scAch = c;
        }
    }

    // ============================================================ 触控

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        int act = e.getActionMasked();
        if (scene == SCENE_PLAY) return playTouch(e, act);
        return uiTouch(e, act);
    }

    private boolean playTouch(MotionEvent e, int act) {
        switch (act) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN: {
                int idx = e.getActionIndex();
                int id = e.getPointerId(idx);
                float x = e.getX(idx), y = e.getY(idx);
                int s = sectorOf(x, y);
                remember(id, s);
                if (s >= 0) heldMask |= (1 << s);
                dragAngle = Math.atan2(y - cy, x - cx);
                press(s);
                break;
            }
            case MotionEvent.ACTION_MOVE: {
                for (int i = 0; i < e.getPointerCount(); i++) {
                    int id = e.getPointerId(i);
                    int old = sectorFor(id);
                    float x = e.getX(i), y = e.getY(i);
                    int s = sectorOf(x, y);
                    dragAngle = Math.atan2(y - cy, x - cx);
                    if (old >= -2 && s != old) {
                        remember(id, s);
                        if (old >= 0) { game.releaseRing(old); heldMask &= ~(1 << old); }
                        if (old == -2) game.releaseCenter();
                        if (s >= 0) heldMask |= (1 << s);
                        int sm = game.slideMove(s);     // 滑到新分区 → 沿路径划过箭头
                        if (sm == 1) audio.se(Audio.SE_SLIDE_TICK);          // 划过一个箭头
                        else if (sm == 2) audio.se(seForLv(game.lastLv));    // 送达终点（落地判定音）
                    }
                }
                break;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP: {
                int idx = e.getActionIndex();
                int id = e.getPointerId(idx);
                int s = sectorFor(id);
                if (s >= 0) { game.lift(s); heldMask &= ~(1 << s); }
                else if (s == -2) game.releaseCenter();
                forget(id);
                break;
            }
            case MotionEvent.ACTION_CANCEL:
                for (int i = 0; i < pCount; i++) {
                    if (pSector[i] >= 0) { game.lift(pSector[i]); heldMask &= ~(1 << pSector[i]); }
                }
                pCount = 0;
                heldMask = 0;
                break;
            default:
                break;
        }
        return true;
    }

    private void press(int s) {
        if (s == -2) {
            int k = game.pressCenter();
            audio.se(k == Chart.EX ? Audio.SE_EX : (k == Chart.THOLD ? Audio.SE_HOLD : Audio.SE_TOUCH));
        } else if (s >= 0) {
            int k = game.pressRing(s);
            if (k == Chart.SLIDE) {
                audio.se(Audio.SE_SLIDE_START);        // 接住星星的轻响
            } else if (k >= 0) {
                audio.se(seForLv(game.lastLv));        // 按判定等级发声
            }
        }
    }

    private int seForLv(int lv) {
        switch (lv) {
            case Game.CP: return Audio.SE_CRIT;
            case Game.P: return Audio.SE_PERF;
            case Game.GR: return Audio.SE_GREAT;
            case Game.GD: return Audio.SE_GOOD;
            default: return Audio.SE_MISS;
        }
    }

    /** 屏幕坐标 → 分区；-2 = 中央屏，-1 = 判定区外 */
    private int sectorOf(float x, float y) {
        double dx = x - cx, dy = y - cy;
        double dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < rC) return -2;
        if (dist > rJ * 1.45) return -1;
        double ang = Math.atan2(dy, dx);
        int best = -1;
        double bd = 1e9;
        for (int s = 0; s < 8; s++) {
            double d = ang - POS_A[s];
            while (d > Math.PI) d -= 2 * Math.PI;
            while (d < -Math.PI) d += 2 * Math.PI;
            if (Math.abs(d) < Math.abs(bd)) {
                bd = d;
                best = s;
            }
        }
        return best;
    }

    private void remember(int id, int s) {
        for (int i = 0; i < pCount; i++) {
            if (pId[i] == id) {
                pSector[i] = s;
                return;
            }
        }
        if (pCount < pId.length) {
            pId[pCount] = id;
            pSector[pCount] = s;
            pCount++;
        }
    }

    private int sectorFor(int id) {
        for (int i = 0; i < pCount; i++) if (pId[i] == id) return pSector[i];
        return -1;
    }

    private void forget(int id) {
        for (int i = 0; i < pCount; i++) {
            if (pId[i] == id) {
                pId[i] = pId[pCount - 1];
                pSector[i] = pSector[pCount - 1];
                pCount--;
                return;
            }
        }
    }

    // ---------------------------------------------------------------- 界面触控

    private boolean uiTouch(MotionEvent e, int act) {
        int idx = e.getActionIndex();
        float x = e.getX(idx), y = e.getY(idx);
        switch (act) {
            case MotionEvent.ACTION_DOWN:
                touchX = lastX = x;
                touchY = lastY = y;
                touchDownAt = System.currentTimeMillis();
                dragging = false;
                break;
            case MotionEvent.ACTION_MOVE: {
                float dy = y - lastY;
                if (Math.abs(y - touchY) > 8 * uiScale) dragging = true;
                if ((scene == SCENE_SELECT) && dragging && x < W * 0.62f) {
                    scrollVel = -dy * 0.9f;
                    scroll -= dy;
                    int n = listCount();
                    float max = Math.max(0, n * rowH - (H - H * 0.22f));
                    if (scroll < 0) scroll = 0;
                    if (scroll > max) scroll = max;
                }
                lastX = x; lastY = y;
                break;
            }
            case MotionEvent.ACTION_UP: {
                boolean tap = !dragging && System.currentTimeMillis() - touchDownAt < 400;
                if (tap) {
                    if (scene == SCENE_HOME) tapHome(x, y);
                    else if (scene == SCENE_SELECT) tapSelect(x, y);
                    else if (scene == SCENE_RESULT) tapResult(x, y);
                    else if (scene == SCENE_SCORES) tapScores(x, y);
                    else tapSet(x, y);
                }
                break;
            }
            default:
                break;
        }
        return true;
    }

    // ---- 主菜单
    private void tapHome(float x, float y) {
        float bw = W * 0.56f, bh = H * 0.11f, bx = W * 0.22f;
        float[] cyc = {H * 0.42f, H * 0.58f, H * 0.74f};
        String[] labels = {"曲库 / 开始", "成绩", "设置"};
        for (int i = 0; i < 3; i++) {
            if (x > bx && x < bx + bw && y > cyc[i] - bh / 2 && y < cyc[i] + bh / 2) {
                if (i == 0) { scene = SCENE_SELECT; scroll = 0; libDiff = -1; rebuildFilt(); }
                else if (i == 1) { scene = SCENE_SCORES; buildScores(); }
                else { scene = SCENE_SET; }
                return;
            }
        }
    }

    // ---- 选曲 / 曲库
    private void tapSelect(float x, float y) {
        float s = uiScale;
        // 返回键（左上）
        if (x < W * 0.12f && y < H * 0.10f) { goHome(); return; }
        // 难度筛选 chips（顶部一排）
        if (y > H * 0.105f && y < H * 0.175f) {
            int c = (int) ((x - W * 0.02f) / ((W * 0.96f) / 6));
            if (c >= 0 && c <= 5) {
                int nd = c == 0 ? -1 : c - 1;
                if (nd != libDiff) { libDiff = nd; rebuildFilt(); scroll = 0; }
                return;
            }
        }
        float listTop = H * 0.22f;
        if (x < W * 0.62f) {
            int i = (int) ((y - listTop + scroll) / rowH);
            if (i >= 0 && i < listCount()) { songIdx = listSong(i); scrollVel = 0; }
            return;
        }
        // 右侧难度按钮
        int[] d = Songs.diffsOf(songIdx);
        float top = H * 0.24f, h = H * 0.60f / Math.max(1, d.length);
        int k = (int) ((y - top) / h);
        if (k >= 0 && k < d.length) startPlay(songIdx, d[k]);
    }

    // ---- 成绩
    private void tapScores(float x, float y) {
        if (x < W * 0.12f && y < H * 0.10f) { goHome(); return; }
    }

    // ---- 结算
    private void tapResult(float x, float y) {
        float bw = W * 0.22f, bh = H * 0.12f, by = H * 0.80f;
        if (x > W * 0.5f - bw - 10 && x < W * 0.5f - 10 && y > by && y < by + bh) {
            startPlay(songIdx, diffIdx);
        } else {
            backToSelect();
        }
    }

    // ---- 设置
    private void tapSet(float x, float y) {
        if (x < W * 0.12f && y < H * 0.10f) { goHome(); return; }
        int row = (int) ((y - H * 0.22f) / (H * 0.13f));
        int col = x > W * 0.5f ? 1 : 0;
        switch (row) {
            case 0:
                speed += col == 0 ? -0.1f : 0.1f;
                speed = Math.max(0.5f, Math.min(2.5f, speed));
                break;
            case 1:
                offsetMs += col == 0 ? -5 : 5;
                offsetMs = Math.max(-200, Math.min(200, offsetMs));
                break;
            case 2:
                audio.bgmVol += col == 0 ? -0.1f : 0.1f;
                audio.bgmVol = Math.max(0f, Math.min(1f, audio.bgmVol));
                break;
            case 3:
                audio.seVol += col == 0 ? -0.1f : 0.1f;
                audio.seVol = Math.max(0f, Math.min(1f, audio.seVol));
                break;
            case 4:
                save();
                goHome();
                return;
            default:
                break;
        }
        save();
    }
}
