package com.maimai.dx;

import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * 声音 —— 全部现场合成，一个音频文件都不打包。
 *
 * 判定音效照舞萌那种「咔哒」味来合成：短促、高频、起音带一点噪声 click、指数快速衰减。
 * （无法打包舞萌原版采样，这是同风格的近似；要换原版音可把 se[] 换成读 assets 的 wav。）
 *
 * 伴奏是一段按 BPM 生成的 4 小节循环，判定音效走同一个 AudioTrack 混在一起出声。
 */
public final class Audio {

    public static final int SR = 44100;

    // 音效种类（和真机那种分类对应）
    public static final int SE_CRIT = 0, SE_PERF = 1, SE_GREAT = 2, SE_GOOD = 3, SE_MISS = 4,
            SE_SLIDE_START = 5, SE_SLIDE = 6, SE_BREAK = 7,
            SE_TOUCH = 8, SE_EX = 9, SE_HOLD = 10, SE_CLEAR = 11, SE_SLIDE_TICK = 12;

    private AudioTrack track;
    private Thread thread;
    private volatile boolean running;

    private short[] bgm;
    private int bgmPos;
    private final short[][] se = new short[13][];
    private final List<short[]> pending = new ArrayList<short[]>();
    private final List<Integer> pendingAt = new ArrayList<Integer>();

    public float bgmVol = 0.5f, seVol = 0.8f;

    private final Random rnd = new Random(20261031L);

    public Audio() {
        preloadSe();
    }

    // ============================================================ 合成小工具

    /** 加一个振荡器到 float 缓冲 */
    private void add(float[] f, int off, double hz, double dur, float amp, int wave) {
        int n = (int) (dur * SR);
        if (n <= 0) return;
        double w = 2 * Math.PI * hz / SR;
        for (int i = 0; i < n; i++) {
            int j = off + i;
            if (j >= f.length) break;
            double ph = w * i;
            double v;
            switch (wave) {
                case 0:  v = Math.sin(ph); break;                        // 正弦
                case 1:  v = Math.sin(ph) * 0.6 + Math.sin(2 * ph) * 0.3
                        + Math.sin(3 * ph) * 0.15; break;                // 锯齿味
                case 2:  v = Math.asin(Math.sin(ph)) * (2 / Math.PI); break; // 三角
                default: v = Math.sin(ph) >= 0 ? 1 : -1; break;          // 方波
            }
            f[j] += (float) (v * amp);
        }
    }

    /** 一段噪声（bright=true 留高频 / false 低通），带末端淡出 */
    private void noise(float[] f, int off, double dur, float amp, boolean bright) {
        int n = (int) (dur * SR);
        double[] lp = {0};
        for (int i = 0; i < n; i++) {
            int j = off + i;
            if (j >= f.length) break;
            double t = (double) i / n;
            float v = (rnd.nextFloat() * 2 - 1);
            if (bright) {
                lp[0] = v * 0.85 + lp[0] * 0.15;
                v = (float) (v - lp[0]);
            } else {
                lp[0] = v * 0.25 + lp[0] * 0.75;
                v = (float) lp[0];
            }
            f[j] += (float) (v * amp * (1.0 - t) * (1.0 - t));
        }
    }

    private void kick(float[] f, int off, float amp) {
        int n = (int) (0.14 * SR);
        double ph = 0;
        for (int i = 0; i < n; i++) {
            int j = off + i;
            if (j >= f.length) break;
            double t = i / (double) n;
            double hz = 130 * Math.exp(-t * 4.2) + 42;
            ph += 2 * Math.PI * hz / SR;
            f[j] += (float) (Math.sin(ph) * amp * Math.exp(-t * 5.0));
        }
    }

    private void snare(float[] f, int off, float amp) {
        noise(f, off, 0.16, amp, true);
        add(f, off, 190, 0.09, amp * 0.5f, 0);
    }

    private short[] toShort(float[] f, float scale) {
        short[] out = new short[f.length];
        for (int i = 0; i < f.length; i++) {
            float v = f[i] * scale;
            if (v > 1) v = 1;
            if (v < -1) v = -1;
            out[i] = (short) (v * 32000);
        }
        return out;
    }

    // ============================================================ 判定音效（舞萌风「咔哒」）

    /**
     * 合成一个「咔哒」判定音：极快起音 + 指数衰减 + 可选起始噪声 click。
     * @param tauSec 衰减时间常数（越小越短促）
     * @param clickAmp 起音噪声强度（0 = 无）
     */
    private short[] mkTick(double durSec, double hz, float amp, double tauSec, int wave, float clickAmp) {
        int n = (int) (durSec * SR);
        float[] f = new float[n];
        for (int i = 0; i < n; i++) {
            double t = (double) i / SR;
            double env = Math.exp(-t / tauSec);
            // 2 样本快速起音，避免「啪」的爆音
            if (i < 2) env *= (double) i / 2.0;
            double ph = 2 * Math.PI * hz * t;
            double v;
            switch (wave) {
                case 0:  v = Math.sin(ph); break;
                case 1:  v = Math.sin(ph) * 0.6 + Math.sin(2 * ph) * 0.3 + Math.sin(3 * ph) * 0.15; break;
                case 2:  v = Math.asin(Math.sin(ph)) * (2 / Math.PI); break;
                default: v = Math.sin(ph) >= 0 ? 1 : -1; break;
            }
            f[i] = (float) (v * amp * env);
        }
        if (clickAmp > 0) {
            for (int i = 0; i < (int) (0.0025 * SR) && i < n; i++) {
                f[i] += (float) ((rnd.nextFloat() * 2 - 1) * clickAmp * (1.0 - (double) i / (0.0025 * SR)));
            }
        }
        return toShort(f, 1.0f);
    }

    /** 滑行「嗖」—— 带通噪声扫频（低频到高频） */
    private short[] mkSweep(double dur) {
        int n = (int) (dur * SR);
        float[] f = new float[n];
        double[] bp = {0, 0};   // 2 阶带通状态
        double f0 = 900, f1 = 3200;
        for (int i = 0; i < n; i++) {
            double t = i / (double) n;
            float v = rnd.nextFloat() * 2 - 1;
            // 频率随进度上升的带通
            double k = f0 + (f1 - f0) * t;
            double w = 2 * Math.PI * k / SR;
            double a = 2 * Math.cos(w);
            double y = a * bp[1] - bp[0] + v;
            bp[0] = bp[1];
            bp[1] = y;
            f[i] = (float) (y * 0.35 * (1.0 - t * 0.6));
        }
        return toShort(f, 1.0f);
    }

    /** 滑星星接住的轻响（小 blip） */
    private short[] mkBlip(double dur, double hz, float amp) {
        int n = (int) (dur * SR);
        float[] f = new float[n];
        for (int i = 0; i < n; i++) {
            double t = (double) i / SR;
            double env = Math.exp(-t / (dur * 0.35));
            if (i < 2) env *= (double) i / 2.0;
            f[i] = (float) (Math.sin(2 * Math.PI * hz * t) * amp * env);
        }
        for (int i = 0; i < (int) (0.0015 * SR) && i < n; i++)
            f[i] += (float) ((rnd.nextFloat() * 2 - 1) * 0.18 * (1.0 - (double) i / (0.0015 * SR)));
        return toShort(f, 1.0f);
    }

    /** MISS：低沉的「咚」（低频正弦 + 低通噪声） */
    private short[] mkMiss() {
        int n = (int) (0.10 * SR);
        float[] f = new float[n];
        add(f, 0, 170, 0.10, 0.5f, 0);
        add(f, 0, 110, 0.10, 0.35f, 0);
        noise(f, 0, 0.07, 0.18f, false);
        for (int i = 0; i < n; i++) f[i] *= (1.0 - (double) i / n);
        return toShort(f, 1.0f);
    }

    /** 结算 jingle：上行琶音 */
    private short[] mkArp(double dur) {
        float[] f = new float[(int) (dur * SR)];
        double[] hz = {523.25, 659.25, 783.99, 1046.5};
        for (int i = 0; i < hz.length; i++) {
            add(f, (int) (i * 0.09 * SR), hz[i], dur - i * 0.09, 0.28f, 0);
        }
        int n = f.length;
        for (int i = 0; i < n; i++) f[i] *= (1.0f - i / (float) n * 0.6f);
        return toShort(f, 1.0f);
    }

    private void preloadSe() {
        se[SE_CRIT]       = mkTick(0.028, 3200, 0.55f, 0.008, 0, 0.28f);  // 更尖更高
        se[SE_PERF]       = mkTick(0.030, 2100, 0.52f, 0.010, 0, 0.22f);
        se[SE_GREAT]      = mkTick(0.044, 1350, 0.46f, 0.016, 2, 0.12f);
        se[SE_GOOD]       = mkTick(0.060, 760,  0.42f, 0.026, 2, 0.05f);  // 闷一点
        se[SE_MISS]       = mkMiss();
        se[SE_SLIDE_START]= mkBlip(0.018, 1500, 0.40f);                    // 接住星星
        se[SE_SLIDE]      = mkSweep(0.16);                                  // 嗖
        se[SE_SLIDE_TICK] = mkTick(0.020, 2600, 0.44f, 0.006, 0, 0.24f);   // 划过每个箭头的「カチッ」
        se[SE_BREAK]      = mk(0.085, new int[]{0, 0}, new double[]{2600, 3300}, new float[]{0.42f, 0.30f});
        se[SE_TOUCH]      = mkTick(0.030, 1000, 0.34f, 0.018, 0, 0.05f);
        se[SE_EX]         = mkTick(0.050, 1500, 0.38f, 0.020, 2, 0.06f);
        se[SE_HOLD]       = mkTick(0.022, 2200, 0.40f, 0.007, 0, 0.18f);
        se[SE_CLEAR]      = mkArp(0.55);
    }

    /** 双音（BREAK 用） */
    private short[] mk(double dur, int[] wave, double[] hz, float[] amp) {
        float[] f = new float[(int) (dur * SR)];
        for (int i = 0; i < hz.length; i++) add(f, 0, hz[i], dur, amp[i], wave[i]);
        int n = f.length;
        for (int i = 0; i < n; i++) {
            float t = i / (float) n;
            f[i] *= (1.0f - t) * (1.0f - t);
        }
        return toShort(f, 1.0f);
    }

    /** 触发一个音效 */
    public void se(int kind) {
        if (kind < 0 || kind >= se.length || se[kind] == null) return;
        synchronized (pending) {
            pending.add(se[kind]);
            pendingAt.add(0);
        }
    }

    // ============================================================ 伴奏

    /** 4 小节循环，跟着 BPM 走 */
    private short[] buildBgm(double bpm) {
        double beat = 60.0 / bpm;
        double stepDur = beat / 4;
        int steps = 64;
        int n = (int) (steps * stepDur * SR) + SR / 4;
        float[] f = new float[n];

        double[] roots = {110.0, 87.307, 130.813, 98.0};   // Am - F - C - G
        int[] pent = {0, 3, 5, 7, 10};

        for (int s = 0; s < steps; s++) {
            int off = (int) (s * stepDur * SR);
            int bar = s / 16;
            double root = roots[bar];

            if (s % 8 == 0 || s % 16 == 6 || s % 16 == 14) kick(f, off, 0.16f);
            if (s % 16 == 4 || s % 16 == 12) snare(f, off, 0.11f);
            if (s % 2 == 0) noise(f, off, 0.045, 0.030f, true);
            if (s % 4 == 0) add(f, off, root * 0.5, stepDur * 3.6, 0.085f, 1);
            if (s % 16 == 0) {
                add(f, off, root, beat * 1.7, 0.035f, 0);
                add(f, off, root * 1.1892, beat * 1.7, 0.030f, 0);
                add(f, off, root * 1.4983, beat * 1.7, 0.026f, 0);
            }
            if (s % 2 == 1 && rnd.nextFloat() < 0.55) {
                int semi = pent[rnd.nextInt(pent.length)] + (rnd.nextFloat() < 0.3 ? 12 : 0);
                double hz = 220.0 * Math.pow(2.0, semi / 12.0);
                add(f, off, hz, stepDur * 0.85, 0.040f, 2);
            }
        }
        return toShort(f, 0.85f);
    }

    // ============================================================ 播放

    public void startBgm(double bpm) {
        stop();
        bgm = buildBgm(bpm);
        bgmPos = 0;
        int min = AudioTrack.getMinBufferSize(SR, AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        int buf = Math.max(min, 2048);
        try {
            track = new AudioTrack(AudioManager.STREAM_MUSIC, SR,
                    AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    buf * 2, AudioTrack.MODE_STREAM);
        } catch (Exception e) {
            track = null;
            return;
        }
        running = true;
        final int frames = 1024;
        final short[] mix = new short[frames];
        track.play();
        thread = new Thread(new Runnable() {
            public void run() {
                while (running) {
                    fill(mix, frames);
                    if (track != null) {
                        try {
                            track.write(mix, 0, frames);
                        } catch (Exception e) {
                            running = false;
                        }
                    }
                }
            }
        }, "dx-audio");
        thread.setPriority(Thread.MAX_PRIORITY);
        thread.start();
    }

    private void fill(short[] out, int frames) {
        for (int i = 0; i < frames; i++) out[i] = 0;
        if (bgm != null && bgm.length > 0) {
            for (int i = 0; i < frames; i++) {
                out[i] = (short) (bgm[(bgmPos + i) % bgm.length] * bgmVol);
            }
            bgmPos = (bgmPos + frames) % bgm.length;
        }
        synchronized (pending) {
            for (int k = 0; k < pending.size(); k++) {
                short[] s = pending.get(k);
                int at = pendingAt.get(k);
                int n = Math.min(s.length - at, frames);
                for (int i = 0; i < n; i++) {
                    int v = out[i] + (int) (s[at + i] * seVol);
                    if (v > 32767) v = 32767;
                    if (v < -32767) v = -32767;
                    out[i] = (short) v;
                }
                at += n;
                if (at >= s.length) {
                    pending.remove(k);
                    pendingAt.remove(k);
                    k--;
                } else {
                    pendingAt.set(k, at);
                }
            }
        }
    }

    public void stop() {
        running = false;
        if (thread != null) {
            try {
                thread.join(300);
            } catch (InterruptedException e) {
                // ignore
            }
            thread = null;
        }
        if (track != null) {
            try {
                track.stop();
                track.release();
            } catch (Exception e) {
                // ignore
            }
            track = null;
        }
        synchronized (pending) {
            pending.clear();
            pendingAt.clear();
        }
    }
}
