package com.maimai.dx;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;

/** 所有绘制都在这里。判定区布局照真机：中央屏 + 外面一圈八分区圆环。 */
public final class Render {

    private static final int BG = Color.rgb(5, 8, 12);
    private static final int C_TAP = Color.rgb(0x39, 0xC5, 0xBB);
    private static final int C_STAR = Color.rgb(0xF5, 0xD4, 0x42);
    private static final int C_HOLD = Color.rgb(0x7F, 0xD1, 0xFF);
    private static final int C_SLIDE = Color.rgb(0xB0, 0x7C, 0xFF);
    private static final int C_TOUCH = Color.rgb(0xFF, 0x8F, 0xD1);
    private static final int C_EX = Color.rgb(0xFF, 0xB0, 0x20);
    private static final int C_MISS = Color.rgb(0xE5, 0x48, 0x4D);
    private static final int C_TXT = Color.rgb(0xEA, 0xF2, 0xF5);
    private static final int C_DIM = Color.rgb(0x6B, 0x7C, 0x86);
    private static final int C_PANEL = Color.rgb(0x0E, 0x17, 0x1F);

    private final GameView v;
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();

    public Render(GameView view) {
        v = view;
        stroke.setStyle(Paint.Style.STROKE);
        text.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
    }

    // ============================================================ 入口

    public void draw(Canvas c) {
        c.drawColor(BG);
        switch (v.scene) {
            case GameView.SCENE_HOME:
                drawHome(c);
                break;
            case GameView.SCENE_SELECT:
                drawSelect(c);
                break;
            case GameView.SCENE_PLAY:
                drawPlay(c);
                break;
            case GameView.SCENE_RESULT:
                drawResult(c);
                break;
            case GameView.SCENE_SCORES:
                drawScores(c);
                break;
            default:
                drawSettings(c);
                break;
        }
    }

    // ============================================================ 主菜单

    private void drawHome(Canvas c) {
        float s = v.uiScale;
        // 背景圆环装饰
        stroke.setColor(C_TAP);
        stroke.setAlpha(40);
        stroke.setStrokeWidth(3 * s);
        c.drawCircle(v.cx, v.H * 0.30f, v.H * 0.16f, stroke);
        stroke.setAlpha(255);

        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, "舞萌 DX", v.W * 0.5f, v.H * 0.30f, 54 * s, C_STAR);
        txtC(c, "NATIVE  ·  离线 · 不联网", v.W * 0.5f, v.H * 0.30f + 38 * s, 14 * s, C_DIM);
        text.setTextAlign(Paint.Align.LEFT);

        float bw = v.W * 0.56f, bh = v.H * 0.11f, bx = v.W * 0.22f;
        float[] cyc = {v.H * 0.42f, v.H * 0.58f, v.H * 0.74f};
        String[] labels = {"曲库 / 开始", "成绩", "设置"};
        int[] cols = {C_TAP, C_HOLD, C_SLIDE};
        for (int i = 0; i < 3; i++) {
            fill.setColor(C_PANEL);
            c.drawRoundRect(bx, cyc[i] - bh / 2, bx + bw, cyc[i] + bh / 2, 14 * s, 14 * s, fill);
            stroke.setColor(cols[i]);
            stroke.setAlpha(180);
            stroke.setStrokeWidth(2.5f * s);
            c.drawRoundRect(bx, cyc[i] - bh / 2, bx + bw, cyc[i] + bh / 2, 14 * s, 14 * s, stroke);
            stroke.setAlpha(255);
            txtC(c, labels[i], v.W * 0.5f, cyc[i] + bh * 0.18f, 22 * s, C_TXT);
        }
        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, "点任意按钮进入", v.W * 0.5f, v.H * 0.90f, 13 * s, C_DIM);
        text.setTextAlign(Paint.Align.LEFT);
    }

    // ============================================================ 选曲 / 曲库

    private void drawSelect(Canvas c) {
        float s = v.uiScale;
        float pad = 18 * s;

        backBtn(c);

        // 标题
        txt(c, "曲库", pad + v.W * 0.12f, 34 * s, 26 * s, C_TXT);

        // 顶部难度筛选 chips
        String[] chip = {"全部", "BASIC", "ADV", "EXP", "MAS", "ReM"};
        float cw = (v.W * 0.96f) / 6, cx0 = v.W * 0.02f, cy0 = v.H * 0.105f, ch = v.H * 0.07f;
        for (int i = 0; i < 6; i++) {
            int nd = i == 0 ? -1 : i - 1;
            boolean on = (nd == v.libDiff);
            fill.setColor(on ? C_TAP : C_PANEL);
            fill.setAlpha(on ? 220 : 255);
            c.drawRoundRect(cx0 + i * cw + 2 * s, cy0, cx0 + (i + 1) * cw - 2 * s, cy0 + ch, 8 * s, 8 * s, fill);
            fill.setAlpha(255);
            txtC(c, chip[i], cx0 + i * cw + cw / 2, cy0 + ch * 0.66f, 13 * s,
                    on ? Color.rgb(5, 8, 12) : C_DIM);
        }

        // ---- 左：曲名列表（可滚动）
        float top = v.H * 0.22f;
        float bottom = v.H;
        int n = v.listCount();
        int first = (int) (v.scroll / v.rowH) - 1;
        if (first < 0) first = 0;
        for (int i = first; i < n; i++) {
            float y = top + i * v.rowH - v.scroll;
            if (y > bottom || y + v.rowH < top - v.rowH) {
                if (y > bottom) break;
                continue;
            }
            int si = v.listSong(i);
            boolean sel = (si == v.songIdx);
            fill.setColor(sel ? Color.rgb(0x16, 0x2A, 0x36) : Color.TRANSPARENT);
            if (sel) {
                c.drawRoundRect(pad * 0.5f, y + 3 * s, v.W * 0.60f, y + v.rowH - 3 * s,
                        8 * s, 8 * s, fill);
            }
            float maxds = 0;
            for (int d = 0; d < 5; d++) maxds = Math.max(maxds, Songs.ds[si][d]);
            txt(c, Songs.title[si], pad, y + v.rowH * 0.42f, 17 * s, sel ? C_TAP : C_TXT);
            txt(c, Songs.artist[si], pad, y + v.rowH * 0.78f, 12 * s, C_DIM);
            txt(c, maxds > 0 ? String.format("%.1f", maxds) : "-",
                    v.W * 0.56f, y + v.rowH * 0.42f, 16 * s, C_STAR);
            float best = bestAny(si);
            if (best > 0)
                txt(c, String.format("%.2f%%", best), v.W * 0.60f - pad, y + v.rowH * 0.42f,
                        12 * s, C_DIM);
        }

        stroke.setColor(Color.rgb(0x22, 0x30, 0x3A));
        stroke.setStrokeWidth(2 * s);
        c.drawLine(v.W * 0.62f, top, v.W * 0.62f, bottom, stroke);

        // ---- 右：当前曲 + 难度按钮 + 各难度最佳
        float rx = v.W * 0.64f + pad;
        txt(c, Songs.title[v.songIdx], rx, v.H * 0.12f, 19 * s, C_TXT);
        txt(c, Songs.artist[v.songIdx], rx, v.H * 0.165f, 13 * s, C_DIM);
        txt(c, "BPM " + Songs.bpm[v.songIdx], rx, v.H * 0.205f, 13 * s, C_DIM);

        int[] d = Songs.diffsOf(v.songIdx);
        if (d.length == 0) {
            txt(c, "这首没有可用难度", rx, v.H * 0.4f, 15 * s, C_DIM);
            return;
        }
        float bh = v.H * 0.58f / d.length;
        float by = v.H * 0.24f;
        for (int k = 0; k < d.length; k++) {
            int di = d[k];
            int col = di == 0 ? Color.rgb(0x5F, 0xC8, 0x6A)
                    : di == 1 ? C_STAR
                    : di == 2 ? Color.rgb(0xE5, 0x6B, 0x6B)
                    : di == 3 ? Color.rgb(0xB0, 0x7C, 0xFF)
                    : Color.rgb(0xE0, 0x7A, 0xE0);
            float y = by + k * bh;
            fill.setColor(col);
            fill.setAlpha(di == v.diffIdx ? 235 : 70);
            c.drawRoundRect(rx, y + 4 * s, v.W - pad, y + bh - 6 * s, 10 * s, 10 * s, fill);
            fill.setAlpha(255);
            txt(c, Songs.DIFF_CN[di], rx + 14 * s, y + bh * 0.45f, 16 * s,
                    di == v.diffIdx ? Color.rgb(5, 8, 12) : C_TXT);
            txt(c, String.format("%.1f", Songs.ds[v.songIdx][di]),
                    v.W - pad - 60 * s, y + bh * 0.45f, 16 * s,
                    di == v.diffIdx ? Color.rgb(5, 8, 12) : C_TXT);
            float best = v.bestOf(v.songIdx, di);
            if (best > 0)
                txt(c, String.format("%.2f%%", best), v.W - pad - 150 * s, y + bh * 0.45f, 13 * s,
                        di == v.diffIdx ? Color.rgb(5, 8, 12) : C_DIM);
        }
        txt(c, "点右侧难度直接开打", rx, v.H * 0.92f, 12 * s, C_DIM);
    }

    private float bestAny(int si) {
        float b = -1;
        for (int d = 0; d < 5; d++) b = Math.max(b, v.bestOf(si, d));
        return b;
    }

    // ============================================================ 演奏

    private void drawPlay(Canvas c) {
        float s = v.uiScale;
        Game g = v.game;
        long now = g.now;

        // 判定环
        stroke.setColor(Color.rgb(0xA0, 0xC8, 0xCD));
        stroke.setAlpha(80);
        stroke.setStrokeWidth(3 * s);
        c.drawCircle(v.cx, v.cy, v.rJ, stroke);
        stroke.setAlpha(255);

        // 八分区分隔线
        stroke.setColor(Color.rgb(0x50, 0x68, 0x72));
        stroke.setAlpha(120);
        stroke.setStrokeWidth(1.5f * s);
        for (int i = 0; i < 8; i++) {
            double a = GameView.POS_A[i];
            float x0 = (float) (v.cx + Math.cos(a) * v.rC);
            float y0 = (float) (v.cy + Math.sin(a) * v.rC);
            float x1 = (float) (v.cx + Math.cos(a) * v.rJ * 1.16f);
            float y1 = (float) (v.cy + Math.sin(a) * v.rJ * 1.16f);
            c.drawLine(x0, y0, x1, y1, stroke);
        }
        stroke.setAlpha(255);

        // 按下高亮（扇区）
        for (int i = 0; i < 8; i++) {
            float k = (float) g.keyFlash[i];
            if (k <= 0.02f) continue;
            double a = GameView.POS_A[i];
            stroke.setColor(C_TAP);
            stroke.setAlpha((int) (200 * k));
            stroke.setStrokeWidth(7 * s * k + 2 * s);
            float r1 = v.rC, r2 = v.rJ * 1.12f;
            c.drawLine((float) (v.cx + Math.cos(a) * r1), (float) (v.cy + Math.sin(a) * r1),
                    (float) (v.cx + Math.cos(a) * r2), (float) (v.cy + Math.sin(a) * r2), stroke);
        }
        stroke.setAlpha(255);

        // 中央屏
        fill.setColor(Color.rgb(0x0A, 0x12, 0x18));
        c.drawCircle(v.cx, v.cy, v.rC, fill);
        stroke.setColor(Color.rgb(0x39, 0xC5, 0xBB));
        stroke.setAlpha((int) (60 + 150 * Math.min(1, g.ctrFlash)));
        stroke.setStrokeWidth(2.5f * s);
        c.drawCircle(v.cx, v.cy, v.rC, stroke);
        stroke.setAlpha(255);

        // ---- 音符
        float travel = 900f / v.speed;
        for (int i = 0; i < g.notes.size(); i++) {
            Chart.Note n = g.notes.get(i);
            if (n.done && !n.holding && !n.sliding && !n.captured) continue;
            float appar = n.t - travel;
            if (now < appar - 60) continue;
            float prog = (now - appar) / travel;
            if (prog > 1.55f && !n.holding && !n.captured) continue;
            drawNote(c, n, prog, now, s);
        }

        // ---- 中央屏里的字
        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, v.chart == null ? "" : v.chart.title, v.cx, v.cy - v.rC * 0.18f, 13 * s, C_DIM);
        if (g.combo > 1) {
            txtC(c, String.valueOf(g.combo), v.cx, v.cy + v.rC * 0.12f, 30 * s, C_TXT);
            txtC(c, "COMBO", v.cx, v.cy + v.rC * 0.34f, 11 * s, C_DIM);
        } else {
            txtC(c, String.format("%.2f%%", g.achievement()), v.cx, v.cy + v.rC * 0.12f,
                    22 * s, C_STAR);
        }
        text.setTextAlign(Paint.Align.LEFT);

        // 判定文字
        if (g.lastLv >= 0 && g.rawNow - g.lastJudgeAt < 520) {
            int col = g.lastLv == Game.CP ? C_STAR : g.lastLv == Game.P ? C_TAP
                    : g.lastLv == Game.GR ? C_HOLD : g.lastLv == Game.GD
                    ? Color.rgb(0x9A, 0xA7, 0xAD) : C_MISS;
            text.setTextAlign(Paint.Align.CENTER);
            txtC(c, Game.LV_NAME[g.lastLv], v.cx, v.cy - v.rJ * 0.62f, 17 * s, col);
            text.setTextAlign(Paint.Align.LEFT);
        }

        // ---- HUD
        float pad = 16 * s;
        if (v.chart != null) {
            txt(c, v.chart.title, pad, 26 * s, 15 * s, C_TXT);
            txt(c, v.chart.diff + "  " + String.format("%.1f", v.chart.ds)
                    + "  BPM " + (int) v.chart.bpm, pad, 44 * s, 12 * s, C_DIM);
        }
        text.setTextAlign(Paint.Align.RIGHT);
        txt(c, String.format("%.4f%%", g.achievement()), v.W - pad, 26 * s, 17 * s, C_STAR);
        txt(c, Game.rankOf(g.achievement()), v.W - pad, 44 * s, 12 * s, C_DIM);
        text.setTextAlign(Paint.Align.LEFT);

        // 进度条
        int last = v.chart == null ? 1 : v.chart.lastEnd();
        float pr = Math.max(0, Math.min(1, now / (float) Math.max(1, last)));
        fill.setColor(Color.rgb(0x1A, 0x24, 0x2C));
        c.drawRect(0, v.H - 5 * s, v.W, v.H, fill);
        fill.setColor(C_TAP);
        c.drawRect(0, v.H - 5 * s, v.W * pr, v.H, fill);

        // 倒计时 / 提示
        if (now < 0) {
            text.setTextAlign(Paint.Align.CENTER);
            txtC(c, String.valueOf((int) ((-now) / 1000) + 1), v.cx, v.cy - v.rJ * 0.35f,
                    46 * s, C_STAR);
            txtC(c, "准备", v.cx, v.cy - v.rJ * 0.20f, 14 * s, C_DIM);
            txtC(c, "星星：按住起点再拖到终点", v.cx, v.cy + v.rJ * 0.55f, 13 * s, C_DIM);
            text.setTextAlign(Paint.Align.LEFT);
        }
    }

    private void drawNote(Canvas c, Chart.Note n, float prog, long now, float s) {
        double a = GameView.POS_A[n.p];
        float rad = v.r0 + (v.rJ - v.r0) * prog;
        float x = (float) (v.cx + Math.cos(a) * rad);
        float y = (float) (v.cy + Math.sin(a) * rad);

        switch (n.k) {
            case Chart.TAP: {
                if (n.star == 1) star(c, x, y, v.rJ * 0.115f, C_STAR);
                else {
                    fill.setColor(C_TAP);
                    c.drawCircle(x, y, v.rJ * 0.095f, fill);
                    stroke.setColor(Color.rgb(0x0A, 0x1A, 0x1E));
                    stroke.setStrokeWidth(2 * s);
                    c.drawCircle(x, y, v.rJ * 0.095f, stroke);
                }
                break;
            }
            case Chart.HOLD: {
                float tailRad = v.r0 + (v.rJ - v.r0) * ((now - (n.t + n.d - 900f / v.speed))
                        / (900f / v.speed));
                if (tailRad < v.r0) tailRad = v.r0;
                float x0 = (float) (v.cx + Math.cos(a) * Math.min(rad, v.rJ));
                float y0 = (float) (v.cy + Math.sin(a) * Math.min(rad, v.rJ));
                float x1 = (float) (v.cx + Math.cos(a) * Math.min(tailRad, v.rJ * 1.02f));
                float y1 = (float) (v.cy + Math.sin(a) * Math.min(tailRad, v.rJ * 1.02f));
                stroke.setColor(C_HOLD);
                stroke.setAlpha(n.holding ? 255 : 190);
                stroke.setStrokeWidth(v.rJ * 0.13f);
                stroke.setStrokeCap(Paint.Cap.ROUND);
                c.drawLine(x0, y0, x1, y1, stroke);
                stroke.setAlpha(255);
                fill.setColor(C_HOLD);
                c.drawCircle(x0, y0, v.rJ * 0.085f, fill);
                break;
            }
            case Chart.SLIDE: {
                int col = n.star == 1 ? C_STAR : C_SLIDE;
                // 静态轨迹
                path.rewind();
                slidePath(path, n.p, n.q, n.s, 1.0f);
                stroke.setColor(col);
                stroke.setAlpha(70);
                stroke.setStrokeWidth(v.rJ * 0.05f);
                stroke.setStrokeCap(Paint.Cap.ROUND);
                c.drawPath(path, stroke);
                // 进行中：跟手填充 + 锁定星星
                if (n.captured && n.sliding && !n.delivered) {
                    float vis = Math.max(180, n.d);
                    float f = (now - n.slidFrom) / vis;
                    if (f > 1) f = 1;
                    path.rewind();
                    slidePath(path, n.p, n.q, n.s, f);
                    stroke.setAlpha(245);
                    stroke.setStrokeWidth(v.rJ * 0.075f);
                    c.drawPath(path, stroke);
                    // 跟手的小圆点（你手指拖到哪，亮点就到哪）
                    if (v.dragAngle != 0) {
                        float dr = v.rJ * 1.02f;
                        float dx = (float) (v.cx + Math.cos(v.dragAngle) * dr);
                        float dy = (float) (v.cy + Math.sin(v.dragAngle) * dr);
                        fill.setColor(C_STAR);
                        c.drawCircle(dx, dy, v.rJ * 0.07f, fill);
                    }
                }
                // 路径箭头（AstroDX 的 tick 点）：按序划过时逐颗亮起
                if (n.wp != null) {
                    for (int kk = 0; kk < n.wp.length; kk++) {
                        int wq = n.wp[kk];
                        float wx, wy;
                        if (wq < 0) { wx = v.cx; wy = v.cy; }
                        else {
                            double aw = GameView.POS_A[wq];
                            wx = (float) (v.cx + Math.cos(aw) * v.rJ);
                            wy = (float) (v.cy + Math.sin(aw) * v.rJ);
                        }
                        boolean lit = (n.captured && n.sliding && !n.delivered)
                                ? (kk < n.wpIdx) : (n.delivered || n.done);
                        fill.setColor(lit ? Color.rgb(0xFF, 0xFF, 0xFF) : col);
                        fill.setAlpha(lit ? 255 : 130);
                        c.drawCircle(wx, wy, v.rJ * 0.042f, fill);
                    }
                    fill.setAlpha(255);
                }
                stroke.setAlpha(255);
                // 头：锁定时画大、脉动
                float headR = (n.captured && n.sliding && !n.delivered)
                        ? (float) (v.rJ * 0.14 * (1 + 0.12 * Math.sin(now / 60.0)))
                        : v.rJ * 0.10f;
                if (n.star == 1) star(c, x, y, headR, col);
                else { fill.setColor(col); c.drawCircle(x, y, headR, fill); }
                // 终点箭头
                double a2 = GameView.POS_A[n.q];
                float qx = (float) (v.cx + Math.cos(a2) * v.rJ);
                float qy = (float) (v.cy + Math.sin(a2) * v.rJ);
                stroke.setColor(col);
                stroke.setAlpha(150 + (int) (105 * Math.min(1, g_flash(v, n.q))));
                stroke.setStrokeWidth(3 * s);
                c.drawCircle(qx, qy, v.rJ * 0.07f, stroke);
                stroke.setAlpha(255);
                break;
            }
            default: {  // TOUCH / EX / THOLD —— 画在中央屏里
                double aa = GameView.POS_A[n.p];
                float rr = v.rC * 0.62f;
                float tx = (float) (v.cx + Math.cos(aa) * rr);
                float ty = (float) (v.cy + Math.sin(aa) * rr);
                int col = n.k == Chart.EX ? C_EX : C_TOUCH;
                fill.setColor(col);
                c.drawCircle(tx, ty, v.rC * 0.17f, fill);
                text.setTextAlign(Paint.Align.CENTER);
                txtC(c, n.k == Chart.EX ? "EX" : n.z, tx, ty + v.rC * 0.06f, 12 * v.uiScale,
                        Color.rgb(10, 14, 18));
                text.setTextAlign(Paint.Align.LEFT);
                if (n.k == Chart.THOLD && n.holding) {
                    stroke.setColor(col);
                    stroke.setStrokeWidth(4 * v.uiScale);
                    float left = 1f - (now - n.holdFrom) / (float) Math.max(1, n.d);
                    c.drawArc(new RectF(tx - v.rC * 0.22f, ty - v.rC * 0.22f,
                                    tx + v.rC * 0.22f, ty + v.rC * 0.22f),
                            -90, 360 * Math.max(0, left), false, stroke);
                }
                break;
            }
        }
    }

    private float g_flash(GameView v, int q) {
        return (float) v.game.flash[q];
    }

    /** SLIDE 轨迹：把 JS 版那 9 种花样原样搬过来 */
    private void slidePath(Path out, int p, int q, String shape, float prog) {
        double a0 = GameView.POS_A[p], a1 = GameView.POS_A[q];
        float r = v.rJ;
        int steps = 26;
        if (prog <= 0) {
            out.moveTo(ptx(a0, r), pty(a0, r));
            return;
        }
        if (shape == null || shape.equals("line")) {
            float x0 = ptx(a0, r), y0 = pty(a0, r), x1 = ptx(a1, r), y1 = pty(a1, r);
            out.moveTo(x0, y0);
            out.lineTo(x0 + (x1 - x0) * prog, y0 + (y1 - y0) * prog);
            return;
        }
        if (shape.equals("arc") || shape.equals("arc_l") || shape.equals("arc_r")) {
            double da = a1 - a0;
            while (da > Math.PI) da -= Math.PI * 2;
            while (da < -Math.PI) da += Math.PI * 2;
            if (shape.equals("arc_l") && da > 0) da -= Math.PI * 2;
            if (shape.equals("arc_r") && da < 0) da += Math.PI * 2;
            for (int i = 0; i <= steps; i++) {
                float t = i / (float) steps * prog;
                double a = a0 + da * t;
                float x = ptx(a, r), y = pty(a, r);
                if (i == 0) out.moveTo(x, y);
                else out.lineTo(x, y);
            }
            return;
        }
        if (shape.equals("v") || shape.equals("wifi")) {
            double am = (a0 + a1) / 2;
            double[][] pts;
            if (shape.equals("v")) {
                pts = new double[][]{{a0, r}, {am, r * 0.62f}, {a1, r}};
            } else {
                pts = new double[][]{{a0, r}, {(a0 + am) / 2, r * 0.30f},
                        {am, r * 0.72f}, {(am + a1) / 2, r * 0.30f}, {a1, r}};
            }
            int tot = pts.length - 1;
            float tt = prog * tot;
            int seg = Math.min(tot - 1, (int) tt);
            float ft = tt - seg;
            out.moveTo(ptx(pts[0][0], (float) pts[0][1]), pty(pts[0][0], (float) pts[0][1]));
            for (int j = 1; j <= seg; j++)
                out.lineTo(ptx(pts[j][0], (float) pts[j][1]), pty(pts[j][0], (float) pts[j][1]));
            double aa = pts[seg][0] + (pts[seg + 1][0] - pts[seg][0]) * ft;
            double rr = pts[seg][1] + (pts[seg + 1][1] - pts[seg][1]) * ft;
            out.lineTo(ptx(aa, (float) rr), pty(aa, (float) rr));
            return;
        }
        if (shape.equals("s_cur") || shape.equals("z_cur")) {
            double sgn = shape.equals("s_cur") ? 1 : -1;
            out.moveTo(ptx(a0, r), pty(a0, r));
            for (int k = 0; k <= steps; k++) {
                float t = k / (float) steps * prog;
                double a = a0 + (a1 - a0) * t;
                double wob = Math.sin(t * Math.PI) * 0.30 * sgn;
                double rr = r * (1 - wob);
                out.lineTo(ptx(a, (float) rr), pty(a, (float) rr));
            }
            return;
        }
        // fan 扇形
        double da = a1 - a0;
        while (da > Math.PI) da -= Math.PI * 2;
        while (da < -Math.PI) da += Math.PI * 2;
        out.moveTo(ptx(a0, r * 0.35f), pty(a0, r * 0.35f));
        for (int m = 0; m <= steps; m++) {
            float t = m / (float) steps * prog;
            double a = a0 + da * t;
            double rr = r * 0.35f + r * 0.55f * Math.sin(t * Math.PI);
            out.lineTo(ptx(a, (float) rr), pty(a, (float) rr));
        }
    }

    private float ptx(double a, float r) { return (float) (v.cx + Math.cos(a) * r); }

    private float pty(double a, float r) { return (float) (v.cy + Math.sin(a) * r); }

    private void star(Canvas c, float x, float y, float r, int color) {
        path.rewind();
        for (int i = 0; i < 10; i++) {
            double a = Math.PI * i / 5 - Math.PI / 2;
            float rr = (i % 2 == 0) ? r : r * 0.46f;
            float px = (float) (x + Math.cos(a) * rr);
            float py = (float) (y + Math.sin(a) * rr);
            if (i == 0) path.moveTo(px, py);
            else path.lineTo(px, py);
        }
        path.close();
        fill.setColor(color);
        c.drawPath(path, fill);
    }

    // ============================================================ 结算

    private void drawResult(Canvas c) {
        float s = v.uiScale;
        Game.Result r = v.result;
        if (r == null) return;

        fill.setColor(Color.rgb(0x0A, 0x12, 0x18));
        c.drawRoundRect(v.W * 0.12f, v.H * 0.10f, v.W * 0.88f, v.H * 0.90f,
                18 * s, 18 * s, fill);
        stroke.setColor(C_TAP);
        stroke.setStrokeWidth(2 * s);
        c.drawRoundRect(v.W * 0.12f, v.H * 0.10f, v.W * 0.88f, v.H * 0.90f,
                18 * s, 18 * s, stroke);

        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, Songs.title[v.songIdx], v.W * 0.5f, v.H * 0.19f, 20 * s, C_TXT);
        txtC(c, Songs.DIFF_CN[v.diffIdx] + "  "
                        + String.format("%.1f", Songs.ds[v.songIdx][v.diffIdx]),
                v.W * 0.5f, v.H * 0.25f, 13 * s, C_DIM);

        int rc = rankColor(r.rank);
        txtC(c, r.rank, v.W * 0.5f, v.H * 0.37f, 44 * s, rc);
        txtC(c, String.format("%.4f%%", r.ach), v.W * 0.5f, v.H * 0.46f, 26 * s, C_STAR);
        if (v.newRecord) txtC(c, "NEW RECORD", v.W * 0.5f, v.H * 0.52f, 14 * s, C_STAR);

        String[] names = {"CRITICAL", "PERFECT", "GREAT", "GOOD", "MISS"};
        int[] cols = {C_STAR, C_TAP, C_HOLD, Color.rgb(0x9A, 0xA7, 0xAD), C_MISS};
        for (int i = 0; i < 5; i++) {
            float y = v.H * 0.585f + i * v.H * 0.045f;
            txt(c, names[i], v.W * 0.20f, y, 13 * s, cols[i]);
            text.setTextAlign(Paint.Align.RIGHT);
            txt(c, String.valueOf(r.cnt[i]), v.W * 0.80f, y, 13 * s, cols[i]);
            text.setTextAlign(Paint.Align.CENTER);
        }
        txtC(c, "MAX COMBO " + r.maxCombo + "     FAST " + r.fast + " / SLOW " + r.slow,
                v.W * 0.5f, v.H * 0.735f, 13 * s, C_DIM);

        float bw = v.W * 0.22f, bh = v.H * 0.12f, by = v.H * 0.80f;
        fill.setColor(Color.rgb(0x16, 0x2A, 0x36));
        c.drawRoundRect(v.W * 0.5f - bw - 10, by, v.W * 0.5f - 10, by + bh, 10 * s, 10 * s, fill);
        c.drawRoundRect(v.W * 0.5f + 10, by, v.W * 0.5f + bw + 10, by + bh, 10 * s, 10 * s, fill);
        txtC(c, "再来一次", v.W * 0.5f - bw / 2 - 10, by + bh * 0.62f, 15 * s, C_TXT);
        txtC(c, "选曲", v.W * 0.5f + bw / 2 + 10, by + bh * 0.62f, 15 * s, C_TXT);
        text.setTextAlign(Paint.Align.LEFT);
    }

    private int rankColor(String rank) {
        if (rank.startsWith("SSS")) return C_STAR;
        if (rank.startsWith("SS")) return Color.rgb(0xFF, 0xD8, 0x66);
        if (rank.startsWith("S")) return C_TAP;
        if (rank.startsWith("AAA") || rank.startsWith("AA")) return Color.rgb(0x9A, 0xE5, 0x9A);
        if (rank.equals("A")) return Color.rgb(0xE5, 0x9A, 0x9A);
        return C_DIM;
    }

    // ============================================================ 成绩

    private void drawScores(Canvas c) {
        float s = v.uiScale;
        backBtn(c);
        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, "成绩", v.W * 0.5f, 34 * s, 26 * s, C_TXT);
        text.setTextAlign(Paint.Align.LEFT);

        if (v.scSong == null || v.scSong.length == 0) {
            text.setTextAlign(Paint.Align.CENTER);
            txtC(c, "还没有记录，去打一首吧", v.W * 0.5f, v.H * 0.5f, 16 * s, C_DIM);
            text.setTextAlign(Paint.Align.LEFT);
            return;
        }
        float top = v.H * 0.16f;
        float rh = v.H * 0.085f;
        int shown = Math.min(v.scSong.length, 18);
        for (int i = 0; i < shown; i++) {
            float y = top + i * rh;
            int si = v.scSong[i], di = v.scDiff[i];
            fill.setColor(i % 2 == 0 ? C_PANEL : Color.TRANSPARENT);
            c.drawRoundRect(v.W * 0.04f, y, v.W * 0.96f, y + rh - 4 * s, 8 * s, 8 * s, fill);
            txt(c, Songs.title[si], v.W * 0.06f, y + rh * 0.42f, 16 * s, C_TXT);
            txt(c, Songs.DIFF_CN[di], v.W * 0.62f, y + rh * 0.42f, 14 * s, C_STAR);
            txt(c, String.format("%.2f%%", v.scAch[i]), v.W * 0.80f, y + rh * 0.42f, 15 * s, C_TAP);
        }
        if (v.scSong.length > shown)
            txt(c, "… 共 " + v.scSong.length + " 条记录", v.W * 0.06f, top + shown * rh + 14 * s,
                    12 * s, C_DIM);
    }

    // ============================================================ 设置

    private void drawSettings(Canvas c) {
        float s = v.uiScale;
        backBtn(c);
        text.setTextAlign(Paint.Align.CENTER);
        txtC(c, "设置", v.W * 0.5f, v.H * 0.14f, 24 * s, C_TXT);
        text.setTextAlign(Paint.Align.LEFT);

        String[] rows = {
                "音符速度    " + String.format("%.1f", v.speed),
                "判定偏移    " + v.offsetMs + " ms",
                "伴奏音量    " + String.format("%.0f%%", v.audio.bgmVol * 100),
                "判定音量    " + String.format("%.0f%%", v.audio.seVol * 100),
                "保存并返回"
        };
        for (int i = 0; i < rows.length; i++) {
            float y = v.H * 0.22f + i * v.H * 0.13f;
            fill.setColor(i == 4 ? Color.rgb(0x16, 0x2A, 0x36) : C_PANEL);
            c.drawRoundRect(v.W * 0.12f, y, v.W * 0.88f, y + v.H * 0.11f, 10 * s, 10 * s, fill);
            txt(c, rows[i], v.W * 0.16f, y + v.H * 0.075f, 16 * s, C_TXT);
            if (i < 4) {
                fill.setColor(Color.rgb(0x16, 0x2A, 0x36));
                c.drawRoundRect(v.W * 0.28f, y + v.H * 0.012f, v.W * 0.47f,
                        y + v.H * 0.098f, 8 * s, 8 * s, fill);
                c.drawRoundRect(v.W * 0.53f, y + v.H * 0.012f, v.W * 0.72f,
                        y + v.H * 0.098f, 8 * s, 8 * s, fill);
                text.setTextAlign(Paint.Align.CENTER);
                txt(c, "－", v.W * 0.375f, y + v.H * 0.082f, 18 * s, C_TXT);
                txt(c, "＋", v.W * 0.625f, y + v.H * 0.082f, 18 * s, C_TXT);
                text.setTextAlign(Paint.Align.LEFT);
            }
        }
        txt(c, "左右两边点 ±，改完自动存", v.W * 0.12f, v.H * 0.92f, 12 * s, C_DIM);
    }

    private void backBtn(Canvas c) {
        float s = v.uiScale;
        fill.setColor(C_PANEL);
        c.drawRoundRect(v.W * 0.02f, v.H * 0.02f, v.W * 0.11f, v.H * 0.095f, 8 * s, 8 * s, fill);
        txt(c, "←", v.W * 0.045f, v.H * 0.078f, 22 * s, C_TXT);
    }

    // ============================================================ 小工具

    private void txt(Canvas c, String s, float x, float y, float size, int color) {
        text.setColor(color);
        text.setTextSize(size);
        c.drawText(s == null ? "" : s, x, y, text);
    }

    private void txtC(Canvas c, String s, float x, float y, float size, int color) {
        text.setColor(color);
        text.setTextSize(size);
        c.drawText(s == null ? "" : s, x, y, text);
    }
}
