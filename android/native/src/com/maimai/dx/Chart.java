package com.maimai.dx;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * 谱面引擎 —— 确定性生成 + Simai 解析。
 *
 * 纯 Java，一行 android.* 都不 import，所以能直接在桌面上用 javac/java 跑单测。
 * 生成算法和网页版机台是同一套（同曲同难度永远得到同一张谱），判定窗口、
 * 达成率口径都按真机来。
 */
public final class Chart {

    public static final int TAP = 0, HOLD = 1, SLIDE = 2, TOUCH = 3, THOLD = 4, EX = 5;

    public static final String[] KIND_NAME = {"tap", "hold", "slide", "touch", "thold", "ex"};

    /** 一个音符。t=绝对毫秒，k=类型，p=分区0~7，q=SLIDE终点，d=时长，star=是否星星 */
    public static final class Note {
        public int t;
        public int k;
        public int p;
        public int q = -1;
        public int d;
        public int star;
        public String s = "line";   // SLIDE 花样
        public String z = "A";      // TOUCH 区域 A/B/C/E

        // 运行时状态
        public boolean done, holding, sliding, captured, delivered;
        public int lv;              // 0=CP 1=P 2=GR 3=GD 4=MISS
        public int holdFrom, delta;
        public int slidJudge, slidFrom;   // 滑星星：锁定的判定与锁定时刻
        // 滑星星路径：有序箭头 waypoint（不含起点 p，含终点 q）；-1 = 中央屏
        public int[] wp;
        public int wpIdx;

        public boolean isCenter() { return k == TOUCH || k == EX || k == THOLD; }
    }

    public String title = "", artist = "", diff = "MASTER";
    public double bpm = 150, ds = 8;
    public double beat = 400, step = 100;
    public double duration = 0;
    public List<Note> notes = new ArrayList<Note>();
    public int stars = 0;
    public String source = "gen";

    /** 理论达成率：星星 CP 加成封顶 +1%，所以上限 101.0000% */
    public double theoretical() {
        int n = notes.size();
        if (n == 0) return 100.0;
        return 100.0 + Math.min(1.0, 100.0 * 100.0 * stars / (500.0 * n));
    }

    public int countOf(int kind) {
        int c = 0;
        for (Note n : notes) if (n.k == kind) c++;
        return c;
    }

    /** 最后一颗音符结束的时刻（毫秒） */
    public int lastEnd() {
        int m = 0;
        for (Note n : notes) m = Math.max(m, n.t + n.d);
        return m;
    }

    /**
     * 滑星星路径上的有序箭头分区 —— 对应 AstroDX 按 ArrowDistance 把路径切成一串箭头。
     * 返回「不含起点 p、含终点 q」的分区序列；-1 表示「手指要穿过中央屏」。
     * 沿环花样（arc / arc_l / arc_r）走短弧；穿心花样（line / v / wifi / fan / s_cur / z_cur）过中央。
     * 真机手感的关键：手指必须按序划过这些箭头，每个箭头过线时播一次 click 音。
     */
    public static int[] slideWaypoints(int p, int q, String shape) {
        if (p == q) return new int[]{q};
        boolean through = shape != null && (shape.equals("line") || shape.equals("v")
                || shape.equals("wifi") || shape.equals("fan")
                || shape.equals("s_cur") || shape.equals("z_cur"));
        if (through) return new int[]{-1, q};
        // 沿环短弧从 p 到 q（delta<=4 顺时针，否则逆时针）
        int delta = ((q - p) % 8 + 8) % 8;
        ArrayList<Integer> a = new ArrayList<Integer>();
        if (delta <= 4) {
            for (int s = (p + 1) % 8; s != q; s = (s + 1) % 8) a.add(s);
        } else {
            for (int s = (p + 7) % 8; s != q; s = (s + 7) % 8) a.add(s);
        }
        a.add(q);
        int[] r = new int[a.size()];
        for (int i = 0; i < r.length; i++) r[i] = a.get(i);
        return r;
    }

    // ============================================================ 随机数（xorshift32 + FNV-1a 种子）

    public static int seedOf(String title, String diff) {
        int h = 0x811c9dc5;
        String s = "dx|" + title + "|" + diff;
        for (int i = 0; i < s.length(); i++) {
            h ^= s.charAt(i);
            h = (int) ((h & 0xFFFFFFFFL) * 16777619L);
        }
        return h;
    }

    public static final class Rng {
        private int s;

        public Rng(int seed) {
            s = seed;
            if (s == 0) s = 0x9e3779b9;
        }

        public double next() {
            s ^= s << 13;
            s ^= s >>> 17;
            s ^= s << 5;
            return (s & 0xFFFFFFFFL) / 4294967296.0;
        }

        /** [0,n) 的整数 */
        public int nextInt(int n) { return (int) (next() * n); }

        public <T> T pick(T[] arr) { return arr[nextInt(arr.length)]; }

        public int pick(int[] arr) { return arr[nextInt(arr.length)]; }
    }

    // ============================================================ 生成

    private static final String[] DIFFS = {"BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"};

    private static final int[][] W = {
            {88, 12, 0, 0, 0, 0},
            {70, 16, 11, 3, 0, 0},
            {52, 13, 20, 7, 5, 3},
            {42, 11, 26, 11, 6, 4},
            {36, 9, 30, 13, 7, 5}
    };

    private static final double[][] MODES = {
            {0.10, 0, 0, 0},
            {0.12, 0, 0, 0.12},
            {0.12, 0.08, 0.06, 0.12},
            {0.12, 0.10, 0.08, 0.14},
            {0.12, 0.12, 0.08, 0.16}
    };

    private static final double[][] SEGS = {
            {0, .09, .42}, {.09, .30, .85}, {.30, .40, 1.02}, {.40, .60, 1.22},
            {.60, .70, .80}, {.70, .92, 1.34}, {.92, 1.01, .55}
    };

    private static final String[][] DSHAPES = {
            {"line"},
            {"line"},
            {"line", "line", "arc"},
            {"line", "line", "arc", "arc", "arc_l", "arc_r", "v"},
            {"line", "arc", "arc_l", "arc_r", "arc_r", "v", "wifi", "s_cur", "z_cur", "fan"}
    };

    private static double clamp(double x, double a, double b) {
        return x < a ? a : (x > b ? b : x);
    }

    /**
     * 确定性生成一张谱。
     *
     * @param diffIdx 0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=Re:MASTER
     * @param seconds 谱面长度（秒）
     */
    public static Chart generate(String title, String artist, double bpm, double ds,
                                 int diffIdx, double seconds) {
        diffIdx = Math.max(0, Math.min(4, diffIdx));
        if (seconds <= 0) seconds = 76;
        bpm = clamp(bpm <= 0 ? 150 : bpm, 60, 260);
        ds = clamp(ds <= 0 ? 8 : ds, 1, 15.6);
        double beat = 60000.0 / bpm, step = beat / 4;
        int total = Math.max(64, (int) Math.round(seconds * 1000.0 / step));

        final int di = diffIdx;                 // 内部类里要用，必须是 final
        Rng rng = new Rng(seedOf(title == null ? "x" : title, DIFFS[diffIdx]));
        int[] ws = W[diffIdx];
        double[] md = MODES[diffIdx];

        double nps = clamp(1.0 + (ds - 1.0) * 0.62, 0.8, 10.2);
        double GAP = Math.max(step * 0.5, 45);

        final List<Note> notes = new ArrayList<Note>();
        final double[] busy = new double[8];
        for (int q = 0; q < 8; q++) busy[q] = -1e9;
        final double[] lastTouch = {-1e9};
        final double[] lastEx = {-1e9};
        final int[] lastPos = {-1};
        final double[] sameT = {-1e9}, ctrT = {-1e9};
        final double[] sameN = {0}, ctrN = {0};

        class Ctx {
            boolean emit(double t, int pos, int kind, int to, double dur, int star) {
                if (pos < 0) return false;
                boolean isCtr = kind == TOUCH || kind == EX || kind == THOLD;
                if (t < busy[pos] + GAP) return false;
                if (isCtr) {
                    if (t - ctrT[0] < GAP && ctrN[0] >= 1) return false;
                } else if (t - sameT[0] < GAP && sameN[0] >= 2) return false;
                if (kind == TOUCH || kind == THOLD) {
                    if (t - lastTouch[0] < beat * 1.5) return false;
                    lastTouch[0] = t;
                }
                if (kind == EX) {
                    if (t - lastEx[0] < beat * 1.5) return false;
                    lastEx[0] = t;
                }
                Note n = new Note();
                n.t = (int) Math.round(t);
                n.k = kind;
                n.star = star;
                if (isCtr) {
                    n.p = rng.nextInt(8);
                    n.z = kind == EX ? "E" : new String[]{"A", "A", "B", "C"}[rng.nextInt(4)];
                    if (kind == THOLD) n.d = (int) Math.round(Math.max(beat, dur));
                    busy[pos] = t + step;
                } else {
                    n.p = pos;
                    if (kind == HOLD) {
                        n.d = (int) Math.round(dur);
                        busy[pos] = t + dur + GAP;
                    } else if (kind == SLIDE) {
                        n.q = to;
                        n.s = DSHAPES[di][rng.nextInt(DSHAPES[di].length)];
                        n.d = (int) Math.round(beat * 0.5);
                        busy[pos] = t + GAP * 2;
                        busy[to] = Math.max(busy[to], t + beat * 0.5);
                    } else {
                        busy[pos] = t + GAP;
                    }
                }
                notes.add(n);
                lastPos[0] = pos;
                if (isCtr) {
                    if (t - ctrT[0] < GAP) ctrN[0]++;
                    else { ctrT[0] = t; ctrN[0] = 1; }
                } else {
                    if (t - sameT[0] < GAP) sameN[0]++;
                    else { sameT[0] = t; sameN[0] = 1; }
                }
                return true;
            }

            int freePos(double t, int avoid) {
                int[] cand = new int[8];
                int cn = 0;
                for (int p = 0; p < 8; p++) if (t >= busy[p] + GAP) cand[cn++] = p;
                if (cn == 0) return -1;
                if (cn > 1 && rng.next() < 0.78) {
                    int[] f = new int[8];
                    int fn = 0;
                    for (int i = 0; i < cn; i++) if (cand[i] != avoid) f[fn++] = cand[i];
                    if (fn > 0) { cn = fn; System.arraycopy(f, 0, cand, 0, fn); }
                }
                return cand[rng.nextInt(cn)];
            }

            int occupied(double t) { return (t - sameT[0] < GAP) ? (int) sameN[0] : 0; }
        }
        Ctx ctx = new Ctx();

        int i = 0;
        while (i < total) {
            double frac = (double) i / total, mul = 0.55;
            for (double[] sg : SEGS) if (frac >= sg[0] && frac < sg[1]) { mul = sg[2]; break; }
            double dens = clamp(nps * (step / 1000.0) * mul, 0.02, 0.95);
            double t = i * step;
            boolean allowBreak = (i % 8 == 0);

            // 小节线：星星 TAP 或星星 SLIDE
            if (i % 16 == 0 && diffIdx >= 1 && rng.next() < (0.10 + diffIdx * 0.11)) {
                int bp = ctx.freePos(t, lastPos[0]);
                if (bp >= 0 && ctx.occupied(t) < 2) {
                    if (diffIdx >= 2 && rng.next() < 0.36) {
                        int sp = new int[]{2, 3, 4, 5}[rng.nextInt(4)];
                        int dir = rng.next() < .5 ? 1 : -1;
                        if (ctx.emit(t, bp, SLIDE, (bp + sp * dir + 8) % 8, 0, 1)) {
                            i = advance(i, 2, total);
                            continue;
                        }
                    } else if (ctx.emit(t, bp, TAP, -1, 0, 1)) {
                        i = advance(i, 2, total);
                        continue;
                    }
                }
            }

            if (rng.next() >= dens) { i++; continue; }
            if (ctx.occupied(t) >= 2) { i++; continue; }

            double r = rng.next();
            double a = md[0], b = a + md[1], c = b + md[2], d = c + md[3];

            if (r < a) {                       // 交替
                int p0 = ctx.freePos(t, lastPos[0]);
                if (p0 < 0) { i++; continue; }
                int span = new int[]{2, 3, 4, 5}[rng.nextInt(4)];
                int p1 = (p0 + span) % 8;
                int k = 4 + rng.nextInt(5);
                int gp = dens > 0.5 ? 1 : 2;
                for (int j = 0; j < k; j++) {
                    double tt = (i + j * gp) * step;
                    int pp = (j % 2 == 0) ? p0 : p1;
                    if (tt >= busy[pp] + GAP) {
                        ctx.emit(tt, pp, TAP, -1, 0, 0);
                        busy[pp] = Math.max(busy[pp], tt + GAP);
                    }
                }
                i = advance(i, k * gp, total);
                continue;
            }
            if (a <= r && r < b) {              // 阶梯
                int p2 = ctx.freePos(t, lastPos[0]);
                if (p2 < 0) { i++; continue; }
                int dir = rng.next() < .5 ? 1 : -1;
                int k2 = 4 + rng.nextInt(5);
                int gp2 = dens > 0.55 ? 1 : 2;
                for (int j = 0; j < k2; j++) {
                    double tt = (i + j * gp2) * step;
                    int pp = (p2 + dir * j + 80) % 8;
                    ctx.emit(tt, pp, TAP, -1, 0, 0);
                    busy[pp] = Math.max(busy[pp], tt + GAP);
                }
                i = advance(i, k2 * gp2, total);
                continue;
            }
            if (b <= r && r < c) {              // 双押
                int p3 = ctx.freePos(t, lastPos[0]);
                if (p3 < 0) { i++; continue; }
                int p4 = (p3 + new int[]{3, 4, 5}[rng.nextInt(3)]) % 8;
                if (ctx.emit(t, p3, TAP, -1, 0, 0)) ctx.emit(t, p4, TAP, -1, 0, 0);
                i = advance(i, 2, total);
                continue;
            }
            if (c <= r && r < d && ws[2] > 0) { // 连续 SLIDE
                int p5 = ctx.freePos(t, lastPos[0]);
                if (p5 < 0) { i++; continue; }
                int dir2 = rng.next() < .5 ? 1 : -1;
                int k3 = 2 + rng.nextInt(2);
                int[] spans = diffIdx <= 2 ? new int[]{1, 2, 3} : new int[]{2, 3, 4, 5};
                int span = spans[rng.nextInt(spans.length)];
                for (int j = 0; j < k3; j++) {
                    double tt = (i + j * 4) * step;
                    int pp = (p5 + dir2 * j * 2 + 80) % 8;
                    int qq = (pp + dir2 * span + 80) % 8;
                    ctx.emit(tt, pp, SLIDE, qq, 0, rng.next() < 0.14 ? 1 : 0);
                    busy[pp] = Math.max(busy[pp], tt + GAP * 2);
                    busy[qq] = Math.max(busy[qq], tt + beat * 0.5);
                }
                i = advance(i, k3 * 4, total);
                continue;
            }

            int kind = kindOf(rng, ws, i, allowBreak, diffIdx);
            if (kind == TOUCH && diffIdx >= 3 && rng.next() < 0.10) kind = THOLD;
            if (kind == TOUCH || kind == EX || kind == THOLD) {
                double[] ds2 = {1, 1.5, 2};
                ctx.emit(t, ctx.freePos(t, lastPos[0]), kind, -1,
                        beat * ds2[rng.nextInt(3)], 0);
            } else {
                int pos = ctx.freePos(t, lastPos[0]);
                if (pos < 0) { i++; continue; }
                if (kind == HOLD) {
                    double[] dd = {1, 1.5, 2, 2, 3};
                    ctx.emit(t, pos, HOLD, -1, beat * dd[rng.nextInt(5)], 0);
                } else if (kind == SLIDE) {
                    int[] sps = diffIdx <= 2 ? new int[]{1, 1, 2, 2, 3}
                            : new int[]{1, 2, 3, 4, 5, 6};
                    int sp = sps[rng.nextInt(sps.length)];
                    int dir = rng.next() < .5 ? 1 : -1;
                    int to = (pos + sp * dir + 8) % 8;
                    if (to == pos) to = (pos + 2) % 8;
                    ctx.emit(t, pos, SLIDE, to, 0, (allowBreak && rng.next() < 0.16) ? 1 : 0);
                } else {
                    ctx.emit(t, pos, TAP, -1, 0, kind == 3 ? 1 : 0);
                }
            }
            i++;
        }

        Collections.sort(notes, new Comparator<Note>() {
            public int compare(Note x, Note y) {
                return x.t != y.t ? (x.t - y.t) : (x.p - y.p);
            }
        });

        Chart ch = new Chart();
        ch.title = title;
        ch.artist = artist;
        ch.diff = DIFFS[diffIdx];
        ch.bpm = Math.round(bpm);
        ch.ds = Math.round(ds * 10) / 10.0;
        ch.beat = beat;
        ch.step = step;
        ch.notes = notes;
        ch.source = "gen";
        for (Note n : notes) if (n.star == 1) ch.stars++;
        ch.duration = ch.lastEnd() / 1000.0 + 2.2;
        return ch;
    }

    private static int kindOf(Rng rng, int[] ws, int i, boolean allowBreak, int diffIdx) {
        int[] w = ws.clone();
        if (!allowBreak) w[3] = 0;
        if (diffIdx < 2) { w[4] = 0; w[5] = 0; }
        if (i % 8 != 0 && i % 8 != 4) w[3] = (int) Math.round(w[3] * 0.35);
        int tot = 0;
        for (int z = 0; z < w.length; z++) tot += w[z];
        if (tot <= 0) return TAP;
        double r = rng.next() * tot, acc = 0;
        for (int z = 0; z < w.length; z++) {
            acc += w[z];
            if (r < acc) return z;
        }
        return TAP;
    }

    private static int advance(int i, int k, int total) {
        int j = i + Math.max(1, k);
        int nxt = ((i / 16) + 1) * 16;
        return (j > nxt && nxt > i) ? nxt : j;
    }

    // ============================================================ Simai 解析

    private static final java.util.Map<Character, String> SHAPE_OF =
            new java.util.HashMap<Character, String>();

    static {
        SHAPE_OF.put('-', "line");
        SHAPE_OF.put('—', "line");
        SHAPE_OF.put('^', "arc");
        SHAPE_OF.put('~', "arc");
        SHAPE_OF.put('<', "arc_l");
        SHAPE_OF.put('>', "arc_r");
        SHAPE_OF.put('v', "v");
        SHAPE_OF.put('V', "v");
        SHAPE_OF.put('w', "wifi");
        SHAPE_OF.put('W', "wifi");
        SHAPE_OF.put('s', "s_cur");
        SHAPE_OF.put('S', "s_cur");
        SHAPE_OF.put('z', "z_cur");
        SHAPE_OF.put('Z', "z_cur");
        SHAPE_OF.put('p', "s_cur");
        SHAPE_OF.put('q', "z_cur");
        SHAPE_OF.put('$', "fan");
    }

    private static final String SHAPE_CHARS = "-—^~<>vVwWsSzZpq$";

    /**
     * 解析 Simai 文本。支持：&amp;bpm &amp;offset &amp;title &amp;artist、#难度块、
     * (192) 变速、{1,2} 同押、[x:y] 时值、1b 星星、1h[4:1] HOLD、
     * 1^3 / 1-3 / 1v3 / 1w3 / 1s3 / 1$3 花样、1-2-3 链滑、A1~C1h TOUCH、E EX。
     */
    public static Chart parseSimai(String text, double defaultDiv) {
        Chart ch = new Chart();
        ch.source = "simai";
        double bpm = 120, offset = 0;
        // 和网页版同一个约定：默认时值 = 1/defaultDiv 拍（4 → 十六分）
        double defaultDivBeats = defaultDiv > 0 ? (1.0 / defaultDiv) : 0.25;

        String body = null;
        String wantDiff = null;
        for (String raw : text.split("\\r?\\n")) {
            String line = raw.trim();
            if (line.startsWith("&")) {
                String[] kv = line.substring(1).split("=", 2);
                if (kv.length == 2) {
                    String k = kv[0].trim().toLowerCase(), v = kv[1].trim();
                    if (k.equals("bpm")) bpm = parseDouble(v, bpm);
                    else if (k.equals("offset")) offset = parseDouble(v, 0) * 1000.0;
                    else if (k.equals("title")) ch.title = v;
                    else if (k.equals("artist")) ch.artist = v;
                }
                continue;
            }
            if (line.startsWith("#") && body == null) {
                wantDiff = line.substring(1).trim();
                body = "";
                continue;
            }
            if (body != null) body += raw + "\n";
        }
        if (body == null) body = text;

        ch.bpm = bpm;
        ch.beat = 60000.0 / bpm;
        ch.step = ch.beat / 4;
        if (wantDiff != null && wantDiff.length() > 0) ch.diff = wantDiff.toUpperCase();

        double[] curBpm = {bpm};
        double beatMs = 60000.0 / bpm;
        double cur = offset;                       // 当前拍位（毫秒）
        List<Note> pending = new ArrayList<Note>();

        for (String tok : splitTop(body, ",")) {
            tok = tok.trim();
            if (tok.length() == 0) continue;
            if (tok.startsWith("(") && tok.endsWith(")")) {
                curBpm[0] = parseDouble(tok.substring(1, tok.length() - 1).trim(), curBpm[0]);
                beatMs = 60000.0 / curBpm[0];
                continue;
            }
            if (tok.startsWith("[")) {            // 纯时值（休止）
                double[] dd = durOf(tok, beatMs, defaultDivBeats);
                cur += dd[1] * beatMs;
                continue;
            }
            if (tok.startsWith("{")) {            // 同押
                String inner = tok.substring(1, tok.length() - 1);
                double adv = 0;
                for (String sub : splitTop(inner, ",")) {
                    double[] res = oneNote(sub.trim(), cur, beatMs, defaultDivBeats, ch);
                    adv = Math.max(adv, res[1] * beatMs);
                }
                cur += adv;
                continue;
            }
            double[] res = oneNote(tok, cur, beatMs, defaultDivBeats, ch);
            cur += res[1] * beatMs;
        }

        Collections.sort(ch.notes, new Comparator<Note>() {
            public int compare(Note x, Note y) {
                return x.t != y.t ? (x.t - y.t) : (x.p - y.p);
            }
        });
        for (Note n : ch.notes) if (n.star == 1) ch.stars++;
        ch.duration = ch.lastEnd() / 1000.0 + 2.2;
        pending.clear();
        return ch;
    }

    /** 解析单个音符 token，返回 {自身时长(拍), 前进量(拍)} */
    private static double[] oneNote(String tok, double t, double beatMs,
                                    double defBeats, Chart ch) {
        // 拆出尾部时值 [x:y]
        double own = defBeats, adv = defBeats;
        int bi = tok.indexOf('[');
        if (bi >= 0) {
            String durTok = tok.substring(bi);
            tok = tok.substring(0, bi).trim();
            double[] dd = durOf(durTok, beatMs, defBeats);
            own = dd[0];
            adv = dd[1];
        }
        if (tok.length() == 0) return new double[]{own, adv};

        char c0 = tok.charAt(0);

        // TOUCH / EX
        if (c0 == 'A' || c0 == 'B' || c0 == 'C' || c0 == 'D' || c0 == 'E') {
            Note n = new Note();
            n.t = (int) Math.round(t);
            n.z = String.valueOf(c0);
            String rest = tok.substring(1);
            boolean hold = rest.contains("h");
            int pos = 1;
            for (int i = 0; i < rest.length(); i++) {
                char c = rest.charAt(i);
                if (c >= '1' && c <= '8') { pos = c - '0'; break; }
            }
            n.p = pos - 1;
            n.k = (c0 == 'E') ? EX : (hold ? THOLD : TOUCH);
            if (hold) n.d = (int) Math.round(own * beatMs);
            ch.notes.add(n);
            return new double[]{own, adv};
        }

        // 环上音符：起点
        if (c0 < '1' || c0 > '8') return new double[]{own, adv};
        int p = c0 - '1';
        String rest = tok.substring(1);
        boolean star = rest.indexOf('b') >= 0;
        int hi = rest.indexOf('h');
        if (hi >= 0) {                                  // HOLD
            Note n = new Note();
            n.t = (int) Math.round(t);
            n.k = HOLD;
            n.p = p;
            n.star = star ? 1 : 0;
            n.d = (int) Math.round(own * beatMs);
            ch.notes.add(n);
            return new double[]{own, adv};
        }
        // SLIDE：找花样字符
        int si = -1;
        for (int i = 0; i < rest.length(); i++) {
            if (SHAPE_CHARS.indexOf(rest.charAt(i)) >= 0) { si = i; break; }
        }
        if (si < 0) {                                   // 普通 TAP
            Note n = new Note();
            n.t = (int) Math.round(t);
            n.k = TAP;
            n.p = p;
            n.star = star ? 1 : 0;
            ch.notes.add(n);
            return new double[]{own, adv};
        }
        String tail = rest.substring(si + 1);
        int end = -1;
        for (int i = 0; i < tail.length(); i++) {
            char c = tail.charAt(i);
            if (c >= '1' && c <= '8') { end = c - '1'; break; }
        }
        if (end < 0) {                                  // 只有花样没有终点 → 当 TAP
            Note n = new Note();
            n.t = (int) Math.round(t);
            n.k = TAP;
            n.p = p;
            n.star = star ? 1 : 0;
            ch.notes.add(n);
            return new double[]{own, adv};
        }
        Note n = new Note();
        n.t = (int) Math.round(t);
        n.k = SLIDE;
        n.p = p;
        n.q = end;
        n.s = SHAPE_OF.get(rest.charAt(si));
        if (n.s == null) n.s = "line";
        n.star = star ? 1 : 0;
        n.d = (int) Math.round(beatMs * 0.5);
        ch.notes.add(n);

        // 链滑 1-2-3：后续每一段再来一颗
        String more = tail.substring(1);
        while (true) {
            int s2 = -1;
            for (int i = 0; i < more.length(); i++) {
                if (SHAPE_CHARS.indexOf(more.charAt(i)) >= 0) { s2 = i; break; }
            }
            if (s2 < 0) break;
            String t2 = more.substring(s2 + 1);
            int e2 = -1;
            for (int i = 0; i < t2.length(); i++) {
                char c = t2.charAt(i);
                if (c >= '1' && c <= '8') { e2 = c - '1'; break; }
            }
            if (e2 < 0) break;
            Note n2 = new Note();
            n2.t = n.t;
            n2.k = SLIDE;
            n2.p = end;
            n2.q = e2;
            n2.s = SHAPE_OF.get(more.charAt(s2));
            if (n2.s == null) n2.s = "line";
            n2.d = (int) Math.round(beatMs * 0.5);
            ch.notes.add(n2);
            end = e2;
            more = t2.substring(1);
        }
        return new double[]{own, adv};
    }

    /** [x:y] → {自身时值(拍), 前进量(拍)} */
    private static double[] durOf(String tok, double beatMs, double defBeats) {
        String body = tok.trim();
        if (body.startsWith("[") && body.endsWith("]")) body = body.substring(1, body.length() - 1);
        else if (body.startsWith("[")) body = body.substring(1);
        int c = body.indexOf(':');
        if (c < 0) return new double[]{defBeats, defBeats};
        double x = parseDouble(body.substring(0, c).trim(), 1);
        double y = parseDouble(body.substring(c + 1).trim(), 1);
        if (y <= 0) y = 1;
        double beats = x / y;                    // [x:y] = x/y 拍
        return new double[]{beats, beats};
    }

    private static double parseDouble(String s, double dflt) {
        try {
            return Double.parseDouble(s);
        } catch (Exception e) {
            return dflt;
        }
    }

    /** 按顶层分隔符切分，跳过 {} 和 [] 内部 */
    static List<String> splitTop(String s, String sep) {
        List<String> out = new ArrayList<String>();
        int depth = 0, last = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '{' || c == '[') depth++;
            else if (c == '}' || c == ']') depth--;
            else if (depth == 0 && sep.indexOf(c) >= 0) {
                out.add(s.substring(last, i));
                last = i + 1;
            }
        }
        out.add(s.substring(last));
        return out;
    }
}
