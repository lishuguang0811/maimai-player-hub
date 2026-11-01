package com.maimai.dx;

import java.util.ArrayList;
import java.util.List;

/**
 * 判定与结算 —— 纯 Java，不碰 android.*，可以在桌面上整首跑一遍做单测。
 *
 * 判定窗口是舞萌真机值：CRITICAL ±33 / PERFECT ±67 / GREAT ±100 / GOOD ±150 / MISS ±200（毫秒）。
 * 达成率口径也是真机：每音符 500 分，CP×1.0 / P×0.98 / Gr×0.88 / Gd×0.65，
 * 星星判 CP 再 +100 分，加成封顶全谱 +1% —— 所以理论上限正好 101.0000%。
 */
public final class Game {

    public static final int CP = 0, P = 1, GR = 2, GD = 3, MISS = 4;
    public static final int W_CP = 33, W_P = 67, W_GR = 100, W_GD = 150, W_MISS = 200;
    public static final double[] VAL = {1.0, 0.98, 0.88, 0.65, 0.0};
    public static final String[] LV_NAME = {"CRITICAL PERFECT", "PERFECT", "GREAT", "GOOD", "MISS"};

    private static final String[] RANKS = {"SSS+", "SSS", "SS+", "SS", "S+", "S",
            "AAA", "AA", "A", "BBB", "B", "C", "D"};
    private static final double[] RANK_CUT = {101, 100, 99.5, 99, 98.5, 98,
            97, 94, 90, 80, 75, 70, 0};

    public static String rankOf(double ach) {
        for (int i = 0; i < RANK_CUT.length; i++) if (ach >= RANK_CUT[i]) return RANKS[i];
        return "D";
    }

    public Chart chart;
    public List<Chart.Note> notes = new ArrayList<Chart.Note>();

    // 时间
    public long now;            // 谱面时间（毫秒，已扣掉 offset）
    public long rawNow;         // 未经 offset 修正的时间
    public long offset = 0;     // 判定偏移（毫秒），正 = 音符晚判
    public boolean running;
    public boolean finished;

    /** 当前被手指按住的环上分区位图（bit i = 第 i 区正按下）。由渲染层每帧同步，用于「提前按住星星」自动接住。 */
    public int heldMask = 0;

    // 计数
    public final int[] cnt = new int[5];
    public int combo, maxCombo, fast, slow;
    public final List<Integer> judgedLv = new ArrayList<Integer>();
    public final List<Integer> judgedStar = new ArrayList<Integer>();

    // 表现
    public final double[] flash = new double[8];
    public final double[] keyFlash = new double[8];
    public double ctrFlash;
    public int lastLv = -1;
    public long lastJudgeAt = -100000;

    public void load(Chart c) {
        chart = c;
        notes = c.notes;
        for (Chart.Note n : notes) {
            n.done = false;
            n.holding = false;
            n.sliding = false;
            n.captured = false;
            n.delivered = false;
            n.lv = -1;
            n.slidJudge = MISS;
            n.slidFrom = 0;
            if (n.k == Chart.SLIDE) {
                n.wp = Chart.slideWaypoints(n.p, n.q, n.s);
                n.wpIdx = 0;
            }
        }
        now = 0;
        rawNow = 0;
        running = false;
        finished = false;
        combo = 0;
        maxCombo = 0;
        fast = 0;
        slow = 0;
        for (int i = 0; i < 5; i++) cnt[i] = 0;
        judgedLv.clear();
        judgedStar.clear();
        lastLv = -1;
        lastJudgeAt = -100000;
    }

    public int total() { return notes.size(); }

    public int totalBreaks() {
        int n = 0;
        for (Chart.Note o : notes) if (o.star == 1) n++;
        return n;
    }

    /** 实时达成率 */
    public double achievement() {
        double s = 0;
        int cpb = 0;
        for (int i = 0; i < judgedLv.size(); i++) {
            int lv = judgedLv.get(i);
            s += VAL[lv];
            if (judgedStar.get(i) == 1 && lv == CP) cpb++;
        }
        int n = notes.size() == 0 ? 1 : notes.size();
        double bonus = 0;
        int tb = totalBreaks();
        if (tb > 0) bonus = Math.min(1.0, 100.0 * 100.0 * cpb / (500.0 * n));
        return s / n * 100.0 + bonus;
    }

    public static int judgeLevel(long delta) {
        long ad = Math.abs(delta);
        if (ad <= W_CP) return CP;
        if (ad <= W_P) return P;
        if (ad <= W_GR) return GR;
        if (ad <= W_GD) return GD;
        return MISS;
    }

    private void finish(Chart.Note n, int lv, long delta) {
        n.done = true;
        n.lv = lv;
        judgedLv.add(lv);
        judgedStar.add(n.star);
        lastLv = lv;
        lastJudgeAt = rawNow;
        if (lv == MISS) {
            cnt[MISS]++;
            combo = 0;
            return;
        }
        cnt[lv]++;
        combo++;
        if (combo > maxCombo) maxCombo = combo;
        if (lv != CP) {
            if (delta < 0) fast++;
            else slow++;
        }
    }

    /** 降级：把最后一次判定改成 GOOD，计数也要跟着改，否则结算页会自相矛盾 */
    private void downgradeLast() {
        if (judgedLv.isEmpty()) return;
        int idx = judgedLv.size() - 1;
        int old = judgedLv.get(idx);
        if (old == GD || old == MISS) return;
        judgedLv.set(idx, GD);
        cnt[old]--;
        cnt[GD]++;
    }

    private Chart.Note findRing(int pos, long t) {
        Chart.Note best = null;
        long bd = Long.MAX_VALUE;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (n.done || n.isCenter()) continue;
            if (n.p != pos) continue;
            long d = t - n.t;
            if (d > W_MISS) continue;
            if (d < -W_MISS) break;
            if (Math.abs(d) < Math.abs(bd)) { bd = d; best = n; }
        }
        return best == null ? null : best;
    }

    private long deltaOf(Chart.Note n, long t) { return t - n.t; }

    private Chart.Note findCenter(long t) {
        Chart.Note best = null;
        long bd = Long.MAX_VALUE;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (n.done || !n.isCenter()) continue;
            long d = t - n.t;
            if (d > W_MISS) continue;
            if (d < -W_MISS) break;
            if (Math.abs(d) < Math.abs(bd)) { bd = d; best = n; }
        }
        return best;
    }

    // ---------------------------------------------------------------- 输入

    /** 按下环上第 pos 分区。返回被吃掉的音符类型（用来挑音效），没吃到返回 -1。
     *  滑星星在这里只「接住星星」（锁定判定），真正的判定在送达终点时落地。 */
    public int pressRing(int pos) {
        if (!running || pos < 0 || pos > 7) return -1;
        keyFlash[pos] = 1;
        Chart.Note n = findRing(pos, now);
        if (n == null) return -1;
        long bd = deltaOf(n, now);
        int lv = judgeLevel(bd);
        if (n.k == Chart.HOLD) {
            finish(n, lv, bd);
            n.holding = true;
            n.holdFrom = (int) now;
            return Chart.HOLD;
        }
        if (n.k == Chart.SLIDE) {
            if (n.captured) return Chart.SLIDE;          // 已经接住，重复按下忽略
            if (Math.abs(bd) > W_MISS) return -1;         // 不在窗口里，不当作接星星
            n.captured = true;                            // ★ 接住星星
            n.slidFrom = (int) now;
            n.slidJudge = judgeLevel(bd);                 // 判定锁在「按星星」这一刻
            n.holding = true;
            n.sliding = true;                             // 进入「按住拖到终点」状态
            return Chart.SLIDE;
        }
        finish(n, lv, bd);
        return n.k;
    }

    /**
     * 手指移动到环上分区 s（s==-2 表示中央屏，内部按 -1 处理）。
     * AstroDX 风格：滑星星必须按序划过路径上的每个箭头才能送达，容许跳过中间若干个
     * （slideTolerance，对应真机允许漏划几颗箭头）。返回码：
     *   0 = 无变化；1 = 刚划过一个箭头（应播 tick 音）；2 = 送达终点（判定已落地）。
     */
    public int slideMove(int s) {
        if (!running) return 0;
        int ret = 0;
        int ss = (s == -2) ? -1 : s;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (!(n.captured && n.sliding && !n.delivered)) continue;
            if (n.wp == null || n.wp.length == 0) continue;
            // 从当前 wpIdx 起，找最远一个等于 ss 的箭头 —— 沿途都算划过（容许跳过）
            int j = -1;
            for (int k = n.wpIdx; k < n.wp.length; k++) {
                if (n.wp[k] == ss) { j = k; break; }
            }
            if (j < 0) continue;                 // 这个手指位置不在该星星的路径上
            n.wpIdx = j + 1;
            if (n.wpIdx >= n.wp.length) {         // 划到终点了
                n.delivered = true;
                n.sliding = false;
                n.holding = false;
                flash[n.q] = 1;
                finish(n, n.slidJudge, n.slidFrom - n.t);   // 落地：用锁定时的判定
                ret = 2;
            } else {
                ret = (ret == 2) ? 2 : 1;          // 划过一个箭头
            }
        }
        return ret;
    }

    /** 松开环上第 pos 分区（仅 HOLD 在此处理：早松降级为 GOOD） */
    public void releaseRing(int pos) {
        if (!running) return;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (!n.holding || n.p != pos) continue;
            if (n.k == Chart.SLIDE) continue;               // 滑星星收尾在 lift() 里按「抬指」处理
            n.holding = false;
            if (n.k == Chart.HOLD && now - n.holdFrom < n.d * 0.72) {
                n.lv = GD;
                downgradeLast();
            }
        }
    }

    /** 手指完全抬起第 pos 分区：HOLD 早松降级；滑星星没收尾 → MISS（真机：没拖到终点就是没过） */
    public void lift(int pos) {
        if (!running) return;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (n.p != pos || !n.holding) continue;
            if (n.k == Chart.SLIDE) {
                if (n.captured && n.sliding && !n.delivered) {
                    n.sliding = false;
                    n.holding = false;
                    finish(n, MISS, now - n.t);             // 接住星星却没拖到终点 → MISS
                }
            } else if (n.k == Chart.HOLD) {
                n.holding = false;
                if (now - n.holdFrom < n.d * 0.72) {
                    n.lv = GD;
                    downgradeLast();
                }
            }
        }
    }

    public int pressCenter() {
        if (!running) return -1;
        ctrFlash = 1;
        Chart.Note n = findCenter(now);
        if (n == null) return -1;
        long bd = deltaOf(n, now);
        int lv = judgeLevel(bd);
        if (n.k == Chart.THOLD) {
            finish(n, lv, bd);
            n.holding = true;
            n.holdFrom = (int) now;
        } else {
            finish(n, lv, bd);
        }
        return n.k;
    }

    public void releaseCenter() {
        if (!running) return;
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (!n.holding || n.k != Chart.THOLD) continue;
            n.holding = false;
            if (now - n.holdFrom < n.d * 0.72) {
                n.lv = GD;
                downgradeLast();
            }
        }
    }

    // ---------------------------------------------------------------- 推进

    /**
     * 把谱面时间推到 raw（未经 offset 修正的毫秒）。
     * 会把该判 MISS 的判掉、该收尾的 HOLD/SLIDE 收尾。
     */
    public void advance(long raw) {
        rawNow = raw;
        now = raw - offset;
        if (!running) return;
        sweep(now);
        Chart.Note last = notes.isEmpty() ? null : notes.get(notes.size() - 1);
        if (last != null && now > last.t + last.d + 1800) finished = true;
    }

    public void sweep(long t) {
        for (int i = 0; i < notes.size(); i++) {
            Chart.Note n = notes.get(i);
            if (n.done) continue;

            if (n.k == Chart.SLIDE) {
                if (n.captured) {
                    // 接住星星但没拖到终点：超过收尾时限 → MISS
                    if (n.sliding && !n.delivered && t > n.slidFrom + slideGrace(n)) {
                        n.sliding = false;
                        n.holding = false;
                        finish(n, MISS, t - n.t);
                    }
                } else {
                    // 还没按到星星：若面板正被按住则自动接住（提前按住也能接）；否则过了窗口判 MISS
                    if ((heldMask & (1 << n.p)) != 0
                            && t >= n.t - W_MISS && t <= n.t + W_GD) {
                        n.captured = true;
                        n.slidFrom = (int) t;
                        n.slidJudge = judgeLevel(t - n.t);
                        n.holding = true;
                        n.sliding = true;
                    } else if (t > n.t + W_GD) {
                        finish(n, MISS, t - n.t);
                    }
                }
                continue;
            }

            if (n.holding) {
                if (t >= n.holdFrom + n.d) n.holding = false;
                continue;
            }
            if (t > n.t + W_GD) finish(n, MISS, t - n.t);
        }
    }

    /** 滑星星「按住拖到终点」的收尾时限（毫秒） */
    private long slideGrace(Chart.Note n) {
        return Math.max(250, n.d + 120);
    }

    /** 每帧衰减一次高亮 */
    public void decay() {
        for (int f = 0; f < 8; f++) {
            flash[f] *= 0.86;
            keyFlash[f] *= 0.80;
        }
        ctrFlash *= 0.86;
    }

    public void start() {
        running = true;
        finished = false;
    }

    public void stop() { running = false; }

    /** 结算用的结果快照 */
    public static final class Result {
        public double ach;
        public String rank;
        public int combo, maxCombo, fast, slow;
        public int[] cnt = new int[5];
        public int total, breaks;
        public boolean fullCombo, allPerfect;

        public boolean cleared() { return ach >= 80.0; }
    }

    public Result result() {
        Result r = new Result();
        r.ach = achievement();
        r.rank = rankOf(r.ach);
        r.combo = maxCombo;
        r.maxCombo = maxCombo;
        r.fast = fast;
        r.slow = slow;
        r.cnt = cnt.clone();
        r.total = notes.size();
        r.breaks = totalBreaks();
        r.fullCombo = (cnt[MISS] == 0) && (cnt[GD] == 0);
        r.allPerfect = (cnt[MISS] == 0) && (cnt[GD] == 0) && (cnt[GR] == 0) && (cnt[P] == 0);
        return r;
    }
}
