"""Deterministic piano score and synthesized SFX for SCRIPT.md -> audio/mix.wav.
Run: python tools/score.py
"""
import json
import os
import re
import subprocess
import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000

with open(os.path.join(ROOT, "data", "timing.json"), encoding="utf-8") as _f:
    TM = json.load(_f)

DUR = float(TM["duration"])
N = int(round(DUR * SR))
LINES = TM["lines"]
LN = {l["id"]: l for l in LINES}
IDX = {l["id"]: i for i, l in enumerate(LINES)}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def lineStart(lid):
    return float(LN[lid]["start"])


def lineEnd(lid):
    return float(LN[lid]["end"])


def shotRange(lid):
    i = IDX[lid]
    a = (LINES[i - 1]["end"] + LINES[i]["start"]) / 2.0 if i > 0 else 0.0
    b = (LINES[i]["end"] + LINES[i + 1]["start"]) / 2.0 if i < len(LINES) - 1 else DUR
    return float(a), float(b)


def word_time(lid, word, nth=1, edge="s"):
    if lid not in LN:
        raise ValueError(f"Missing timing line: {lid!r}")
    matches = [x for x in LN[lid]["words"] if norm(x["w"]) == norm(word)]
    if nth < 1 or nth > len(matches):
        raise ValueError(f"Missing cue: line={lid!r}, word={word!r}, occurrence={nth}")
    return float(matches[nth - 1][edge])


def cue(lid, word, nth=1):
    return word_time(lid, word, nth)


# Validate every scheduled word before allocating or synthesizing audio.
PIANO_PLAN = {
    "open": [("October", 69), ("walks", 65)],
    "bread": [("Jean", 62), ("seven", 58)],
    "years": [("Five", 50), ("Four", 65), ("nineteen", 62)],
    "passport": [("passport", 57)],
    "rejected": [("away", 55), ("prison", 53)],
    "bishop": [("Bishop", 62), ("gave", 66), ("door", 69)],
    "door": [("knocks", 62)],
    "dinner": [("sir", 66), ("candlesticks", 69), ("dinner", 74)],
    "night": [("At", 38), ("clock", 45)],
    "bedside": [("stands", 38), ("iron", 46)],
    "steal": [("takes", 38), ("jumps", 45)],
    "caught": [("By", 33), ("police", 52), ("back", 58)],
    "cliff": [("opens", 33), ("silver", 52), ("Valjean", 58), ("says", 61)],
}
SFX_CUES = [("open", "walks"), ("door", "knocks"), ("night", "clock"),
            ("steal", "silver"), ("steal", "jumps"), ("caught", "police"),
            ("cliff", "opens"), ("cliff", "says")]
for lid, notes in PIANO_PLAN.items():
    for word, _ in notes:
        cue(lid, word)
for lid, word in SFX_CUES:
    cue(lid, word)
CUT_TIME = word_time("cliff", "says", edge="e")
CARD_TIME = CUT_TIME + 0.6
CUT_SAMPLE = int(round(CUT_TIME * SR))
CARD_SAMPLE = int(round(CARD_TIME * SR))
if not 0 < CUT_SAMPLE < CARD_SAMPLE < N:
    raise ValueError("Timing duration must include the cliffhanger silence and end-card note")


rng = np.random.default_rng(1815)


def mf(m):
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


def fft_filter(x, lo=None, hi=None, order=2):
    if len(x) == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    H = np.ones_like(f)
    if hi is not None:
        H *= 1.0 / np.sqrt(1.0 + (f / float(hi)) ** (2 * order))
    if lo is not None:
        H *= 1.0 / np.sqrt(1.0 + (float(lo) / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def add(buf, t0, sig, gain=1.0):
    a = int(round(t0 * SR))
    if a >= len(buf) or a + len(sig) <= 0:
        return
    s = sig[max(0, -a):]
    a = max(0, a)
    b = min(len(buf), a + len(s))
    buf[a:b] += gain * s[: b - a]


def add_stereo(bufL, bufR, t0, sig, gain=1.0, pan=0.0):
    theta = (np.clip(pan, -1.0, 1.0) + 1.0) * (np.pi / 4.0)
    add(bufL, t0, sig, gain * np.cos(theta))
    add(bufR, t0, sig, gain * np.sin(theta))


def env_ad(n, att, dec):
    t = np.arange(n) / SR
    return (1.0 - np.exp(-t / max(att, 1e-4))) * np.exp(-t / max(dec, 1e-4))


def env_asr(n, att, rel):
    t = np.arange(n) / SR
    dur = n / SR
    a = np.clip(t / max(att, 1e-4), 0.0, 1.0)
    r = np.clip((dur - t) / max(rel, 1e-4), 0.0, 1.0)
    return 0.5 * (1.0 - np.cos(np.pi * a)) * 0.5 * (1.0 - np.cos(np.pi * r))


# -------------------------------------------------------------
# 1. Sparse Felt Piano with Restrained Chamber Undertones
#    Weary minor -> brief warmth -> low suspense -> unresolved dread.
# -------------------------------------------------------------
padL = np.zeros(N, dtype=np.float64)
padR = np.zeros(N, dtype=np.float64)
pianoL = np.zeros(N, dtype=np.float64)
pianoR = np.zeros(N, dtype=np.float64)


def synth_string_chord(notes, dur, cutoff=1350.0, vib_depth=0.035):
    L = int(round(dur * SR))
    if L <= 0:
        return np.zeros(0), np.zeros(0)
    t = np.arange(L) / SR
    sigL = np.zeros(L, dtype=np.float64)
    sigR = np.zeros(L, dtype=np.float64)
    for idx, m in enumerate(notes):
        base_f = mf(m)
        pan = -0.35 + 0.7 * (idx / max(1, len(notes) - 1))
        voice = np.zeros(L, dtype=np.float64)
        for det_i, det in enumerate((-0.055, 0.0, 0.055)):
            f0 = base_f * (2.0 ** (det / 12.0))
            vib_rate = 4.4 + 0.35 * ((idx + det_i) % 3)
            vib_phase = 0.7 * idx + 1.3 * det_i
            inst_f = f0 * (1.0 + (vib_depth / 12.0) * np.log(2.0) * np.sin(2.0 * np.pi * vib_rate * t + vib_phase))
            phase = 2.0 * np.pi * np.cumsum(inst_f) / SR
            for k in range(1, 9):
                if f0 * k > 5500.0:
                    break
                amp = (1.0 / (k ** 1.45)) * (0.85 if k % 2 == 0 else 1.0)
                voice += amp * np.sin(k * phase + 0.4 * k + det_i)
        bow_noise = fft_filter(rng.standard_normal(L), lo=base_f * 0.8, hi=min(3200.0, base_f * 4.0))
        voice = voice + 0.025 * bow_noise
        theta = (pan + 1.0) * (np.pi / 4.0)
        sigL += voice * np.cos(theta)
        sigR += voice * np.sin(theta)
    env = env_asr(L, min(0.85, dur * 0.28), min(1.1, dur * 0.32))
    sigL = fft_filter(sigL * env, lo=45.0, hi=cutoff)
    sigR = fft_filter(sigR * env, lo=45.0, hi=cutoff)
    return sigL, sigR


def add_piano_note(t0, midi, dur=2.2, vel=0.65, pan=0.0):
    L = int(round(dur * SR))
    if L <= 0:
        return
    t = np.arange(L) / SR
    f0 = mf(midi)
    B = 0.00014
    sig = np.zeros(L, dtype=np.float64)
    for k in range(1, 8):
        fk = f0 * k * np.sqrt(1.0 + B * (k ** 2))
        if fk > 6500.0:
            break
        decay_k = (1.35 / (1.0 + 0.38 * (k - 1)))
        amp_k = (vel ** (0.85 + 0.12 * k)) / (k ** 1.55)
        sig += amp_k * np.sin(2.0 * np.pi * fk * t + 0.2 * k) * np.exp(-t / decay_k)
    # Soft felt hammer thump
    hammer = fft_filter(rng.standard_normal(L), lo=120.0, hi=900.0) * np.exp(-t / 0.009) * 0.06 * vel
    env = (1.0 - np.exp(-t / 0.006)) * (0.55 * np.exp(-t / 0.32) + 0.45 * np.exp(-t / 1.65))
    env *= np.clip((dur - t) / 0.08, 0.0, 1.0)
    out = fft_filter((sig + hammer) * env, lo=55.0, hi=1800.0 + 900.0 * vel)
    add_stereo(pianoL, pianoR, t0, out, gain=0.052, pan=pan)
    # Subtle stereo early reflection
    add_stereo(pianoL, pianoR, t0 + 0.065, out * 0.24, gain=0.052, pan=-pan * 0.7)
    add_stereo(pianoL, pianoR, t0 + 0.145, fft_filter(out, hi=1200.0) * 0.14, gain=0.052, pan=pan * 0.4)


# Sparse weary piano, a brief warm major color, then low unresolved dread.
# Keep strings absent in the weary opening and nearly subliminal thereafter.
for lid, notes, gain in [
    ("bishop", [38, 50, 54, 57], 0.0025),
    ("door", [38, 50, 54, 57], 0.0025),
    ("dinner", [41, 53, 57, 62], 0.003),
    ("night", [26, 38, 45], 0.002),
    ("bedside", [26, 38, 46], 0.0025),
    ("steal", [26, 38, 45], 0.003),
    ("caught", [33, 45, 52, 58], 0.004),
    ("cliff", [33, 45, 52, 58, 61], 0.005),
]:
    a, b = shotRange(lid)
    sL, sR = synth_string_chord(notes, b - a + 0.5, cutoff=950.0)
    add(padL, a, sL, gain)
    add(padR, a, sR, gain)

for lid, notes in PIANO_PLAN.items():
    vel = 0.46 if IDX[lid] < IDX["bishop"] else 0.54
    if IDX[lid] >= IDX["night"]:
        vel = 0.43 + 0.025 * (IDX[lid] - IDX["night"])
    for i, (word, midi) in enumerate(notes):
        add_piano_note(cue(lid, word), midi, 2.8, vel, (-0.12, 0.12)[i % 2])

# Duck smoothly under narration; increase tension through caught and cliff.
tt = np.arange(N) / SR
speech_gate = np.zeros(N, dtype=np.float64)
for l in LINES:
    s_idx = max(0, int((l["start"] - 0.08) * SR))
    e_idx = min(N, int((l["end"] + 0.12) * SR))
    speech_gate[s_idx:e_idx] = 1.0
win_len = int(0.18 * SR)
# Cumulative sum gives the same centered box smoothing without a long convolution.
cs = np.concatenate(([0.0], np.cumsum(np.pad(speech_gate, (win_len // 2, (win_len - 1) // 2)))))
speech_env = (cs[win_len:] - cs[:-win_len]) / win_len
swell = 0.88 + 0.45 * np.clip((tt - lineStart("caught")) / (CUT_TIME - lineStart("caught")), 0, 1)
music_gain = np.clip(tt / 0.7, 0, 1) * swell * (1.0 - 0.52 * speech_env)
musicL = (padL + pianoL) * music_gain
musicR = (padR + pianoR) * music_gain
musicL[CUT_SAMPLE:] = 0.0
musicR[CUT_SAMPLE:] = 0.0

# One quiet low note after the exact 0.6-second silence, ringing to file end.
pianoL.fill(0.0)
pianoR.fill(0.0)
add_piano_note(CARD_TIME, 38, DUR - CARD_TIME, 0.38, 0.0)
musicL += pianoL
musicR += pianoR


# -------------------------------------------------------------
# 2. Diegetic SFX Keyed to Cue Words
# -------------------------------------------------------------
sfxL = np.zeros(N, dtype=np.float64)
sfxR = np.zeros(N, dtype=np.float64)


def sfx_gravel_step(t0, gain=0.14, pan=0.0):
    """Single boot + walking staff crunch on coarse gravel."""
    n = int(0.24 * SR)
    t = np.arange(n) / SR
    # Heel thud + sole crunch + high gravel grit bursts
    heel = np.sin(2.0 * np.pi * (95.0 + 45.0 * np.exp(-t / 0.02)) * t) * np.exp(-t / 0.035) * 0.45
    grit_env = np.exp(-((t - 0.025) / 0.035) ** 2) + 0.75 * np.exp(-((t - 0.085) / 0.045) ** 2)
    gravel_bursts = (rng.random(n) > 0.72).astype(np.float64) * rng.standard_normal(n)
    crunch = fft_filter(gravel_bursts, lo=650.0, hi=5200.0) * grit_env * 0.9
    add_stereo(sfxL, sfxR, t0, heel + crunch, gain=gain, pan=pan)


def sfx_glass_shatter(t0, gain=0.34):
    """Pane crack + deterministic glass shatter on 'stole'."""
    n = int(0.85 * SR)
    t = np.arange(n) / SR
    # Initial sharp pane snap + impact
    impact = np.sin(2.0 * np.pi * (240.0 + 500.0 * np.exp(-t / 0.008)) * t) * np.exp(-t / 0.022) * 0.6
    crack = fft_filter(rng.standard_normal(n), lo=1800.0, hi=9500.0) * np.exp(-t / 0.035) * 0.9
    shatter = impact + crack
    # Crystalline ringing shards + falling glass tinkles over 0.75s
    shard_freqs = [2350, 3120, 3890, 4680, 5420, 6350, 7480, 8620]
    for i in range(22):
        delay = 0.012 + 0.028 * i + 0.006 * (i % 3)
        idx = int(delay * SR)
        if idx >= n:
            continue
        rem = n - idx
        ts = np.arange(rem) / SR
        f1 = shard_freqs[i % len(shard_freqs)] * (1.0 + 0.03 * ((i * 7) % 5 - 2))
        f2 = f1 * 1.414
        dec = 0.035 + 0.025 * (i % 4)
        shard = (np.sin(2.0 * np.pi * f1 * ts) + 0.6 * np.sin(2.0 * np.pi * f2 * ts)) * env_ad(rem, 0.0006, dec)
        shard += 0.45 * fft_filter(rng.standard_normal(rem), lo=3500.0, hi=11000.0) * env_ad(rem, 0.0005, 0.015)
        shatter[idx:] += shard * (0.42 * (0.92 ** i))
    add_stereo(sfxL, sfxR, t0, shatter, gain=gain, pan=0.08)


def sfx_scratch_tick(t0, dur=0.14, gain=0.18, pan=0.0):
    """Chisel/nail scratching a tally mark into rough stone wall."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    click_atk = fft_filter(rng.standard_normal(n), lo=1600.0, hi=7500.0) * env_ad(n, 0.0005, 0.009) * 0.7
    scrape_mod = 0.65 + 0.35 * np.sin(2.0 * np.pi * 68.0 * t)
    scrape = fft_filter(rng.standard_normal(n) * scrape_mod, lo=1100.0, hi=5800.0)
    scrape *= np.sin(np.pi * t / dur) ** 0.7
    stone_res = np.sin(2.0 * np.pi * 2450.0 * t) * env_ad(n, 0.001, 0.025) * 0.2
    add_stereo(sfxL, sfxR, t0, click_atk + scrape + stone_res, gain=gain, pan=pan)


def sfx_paper_rustle(t0, gain=0.22):
    """Dry aged yellow passport paper unfolding and rustling on 'passport'."""
    n = int(0.62 * SR)
    t = np.arange(n) / SR
    burst1 = np.exp(-((t - 0.06) / 0.045) ** 2)
    burst2 = 0.85 * np.exp(-((t - 0.19) / 0.065) ** 2)
    burst3 = 0.55 * np.exp(-((t - 0.36) / 0.085) ** 2)
    crinkle_gate = (rng.random(n) > 0.55).astype(np.float64)
    raw_noise = rng.standard_normal(n) * (0.5 + 0.5 * crinkle_gate)
    paper = fft_filter(raw_noise, lo=950.0, hi=7200.0) * (burst1 + burst2 + burst3)
    add_stereo(sfxL, sfxR, t0, paper, gain=gain, pan=-0.08)


def sfx_door_slam(t0, gain=0.38):
    """Heavy wooden inn door slam on 'Inns'."""
    n = int(0.65 * SR)
    t = np.arange(n) / SR
    # Low heavy oak door thump + wood panel resonance + iron latch clack
    sub_thump = np.sin(2.0 * np.pi * (62.0 + 85.0 * np.exp(-t / 0.025)) * t) * np.exp(-t / 0.095) * 0.85
    panel = (0.45 * np.sin(2.0 * np.pi * 138.0 * t) + 0.25 * np.sin(2.0 * np.pi * 215.0 * t)) * np.exp(-t / 0.07)
    latch = fft_filter(rng.standard_normal(n), lo=900.0, hi=4200.0) * env_ad(n, 0.0008, 0.022) * 0.55
    room_tail = fft_filter(rng.standard_normal(n), lo=80.0, hi=550.0) * env_ad(n, 0.005, 0.18) * 0.4
    add_stereo(sfxL, sfxR, t0, sub_thump + panel + latch + room_tail, gain=gain, pan=-0.18)


def sfx_wicket_clack(t0, gain=0.28):
    """Iron-bound prison wicket sliding and clacking shut on 'prison'."""
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    slide = fft_filter(rng.standard_normal(n), lo=800.0, hi=3800.0) * np.exp(-((t - 0.04) / 0.035) ** 2) * 0.35
    t_hit = np.maximum(0.0, t - 0.06)
    hit_gate = (t >= 0.06).astype(np.float64)
    iron_modes = (
        np.sin(2.0 * np.pi * 680.0 * t_hit) * np.exp(-t_hit / 0.035)
        + 0.7 * np.sin(2.0 * np.pi * 1420.0 * t_hit) * np.exp(-t_hit / 0.025)
        + 0.5 * np.sin(2.0 * np.pi * 2680.0 * t_hit) * np.exp(-t_hit / 0.018)
    ) * hit_gate
    clack_noise = fft_filter(rng.standard_normal(n), lo=1200.0, hi=6000.0) * np.exp(-t_hit / 0.012) * hit_gate * 0.65
    add_stereo(sfxL, sfxR, t0, slide + 0.55 * iron_modes + clack_noise, gain=gain, pan=0.15)


def sfx_dog_growl(t0, gain=0.26):
    """Low guttural dog growl on 'kennel'."""
    n = int(0.82 * SR)
    t = np.arange(n) / SR
    # Low fundamental ~82 Hz with throat flutter ~23 Hz and formant resonances around 220 Hz and 580 Hz
    flutter = 1.0 + 0.18 * np.sin(2.0 * np.pi * 23.5 * t) + 0.08 * np.sin(2.0 * np.pi * 37.0 * t)
    f0 = (84.0 + 14.0 * np.sin(np.pi * t / 0.82) - 10.0 * (t / 0.82)) * flutter
    phase = 2.0 * np.pi * np.cumsum(f0) / SR
    glottal = np.zeros(n, dtype=np.float64)
    for k in range(1, 14):
        glottal += (1.0 / (k ** 0.85)) * np.sin(k * phase)
    formant1 = fft_filter(glottal, lo=110.0, hi=360.0, order=3) * 0.75
    formant2 = fft_filter(glottal, lo=450.0, hi=920.0, order=2) * 0.35
    snarl_breath = fft_filter(rng.standard_normal(n), lo=250.0, hi=1400.0) * flutter * 0.32
    env = np.sin(np.pi * t / 0.82) ** 1.2 * (0.65 + 0.35 * np.sin(2.0 * np.pi * 23.5 * t))
    add_stereo(sfxL, sfxR, t0, (formant1 + formant2 + snarl_breath) * env, gain=gain, pan=0.12)


def sfx_three_knocks(t0, gain=0.32):
    """Three firm knuckles-on-oak-door knocks on 'knocks'."""
    for i in range(3):
        kt = t0 + i * 0.175
        n = int(0.18 * SR)
        t = np.arange(n) / SR
        f_wood = 148.0 + 10.0 * i
        wood = (
            np.sin(2.0 * np.pi * (f_wood + 90.0 * np.exp(-t / 0.008)) * t) * np.exp(-t / 0.032)
            + 0.55 * np.sin(2.0 * np.pi * (f_wood * 2.15) * t) * np.exp(-t / 0.018)
        )
        knuckle = fft_filter(rng.standard_normal(n), lo=600.0, hi=3200.0) * env_ad(n, 0.0005, 0.008) * 0.5
        vel = 0.88 if i < 2 else 1.0
        add_stereo(sfxL, sfxR, kt, (wood + knuckle) * vel, gain=gain, pan=-0.05)


def sfx_match_strike(t0, gain=0.24):
    """Crisp match strike scrape + sulfur flare on 'lights'."""
    n = int(0.52 * SR)
    t = np.arange(n) / SR
    # Abrasive strike (0..0.09s) + ignition pop (0.09s) + soft candle wick flare (0.09..0.50s)
    scrape_env = np.exp(-((t - 0.045) / 0.028) ** 2)
    scrape = fft_filter(rng.standard_normal(n), lo=2200.0, hi=9000.0) * scrape_env * 0.85
    pop_env = np.exp(-((t - 0.095) / 0.008) ** 2)
    pop = fft_filter(rng.standard_normal(n), lo=500.0, hi=3500.0) * pop_env * 0.65
    t_flare = np.maximum(0.0, t - 0.095)
    flare_gate = (t >= 0.095).astype(np.float64)
    flare = fft_filter(rng.standard_normal(n), lo=350.0, hi=2600.0) * env_ad(n, 0.02, 0.14) * flare_gate * 0.5
    add_stereo(sfxL, sfxR, t0, scrape + pop + flare, gain=gain, pan=0.06)


def sfx_silver_clink(t0, gain=0.25):
    """Silver forks and spoons clinking in the basket on 'silver' in 'steal'."""
    hits = [
        (0.00, [2480.0, 3920.0, 5840.0, 8120.0], 1.0, -0.08),
        (0.09, [2760.0, 4310.0, 6420.0, 8950.0], 0.82, 0.10),
        (0.19, [2320.0, 3680.0, 5490.0, 7640.0], 0.68, -0.04),
    ]
    for off, freqs, amp, pan in hits:
        n = int(0.42 * SR)
        t = np.arange(n) / SR
        sig = np.zeros(n, dtype=np.float64)
        for k, f in enumerate(freqs):
            dec = 0.095 / (1.0 + 0.35 * k)
            sig += (0.7 ** k) * np.sin(2.0 * np.pi * f * t) * env_ad(n, 0.0005, dec)
        transient = fft_filter(rng.standard_normal(n), lo=3000.0, hi=10000.0) * env_ad(n, 0.0004, 0.004) * 0.35
        add_stereo(sfxL, sfxR, t0 + off, (sig + transient) * amp, gain=gain, pan=pan)


def sfx_wall_thud(t0, gain=0.35):
    """Heavy landing thud on dirt/stone on 'wall'."""
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    body_thud = np.sin(2.0 * np.pi * (58.0 + 70.0 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.11) * 0.9
    earth_scuff = fft_filter(rng.standard_normal(n), lo=120.0, hi=1800.0) * env_ad(n, 0.003, 0.065) * 0.55
    add_stereo(sfxL, sfxR, t0, body_thud + earth_scuff, gain=gain, pan=0.05)


def sfx_police_boots(t0, gain=0.26):
    """Heavy gendarme boots marching/dragging on 'police'."""
    steps = [
        (0.00, 1.00, -0.14, 105.0),
        (0.16, 0.88, 0.14, 98.0),
        (0.33, 0.92, -0.08, 108.0),
        (0.49, 0.78, 0.10, 100.0),
    ]
    for off, amp, pan, f0 in steps:
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        heel = np.sin(2.0 * np.pi * (f0 + 55.0 * np.exp(-t / 0.015)) * t) * np.exp(-t / 0.04) * 0.75
        sole = fft_filter(rng.standard_normal(n), lo=450.0, hi=3600.0) * env_ad(n, 0.002, 0.028) * 0.65
        add_stereo(sfxL, sfxR, t0 + off, (heel + sole) * amp, gain=gain, pan=pan)


def sfx_coin_roll_and_stop(t0, gain=0.28):
    """40-sou silver coin rolling/wobbling across dirt and stopped dead by Valjean's boot on 'coin'."""
    # Coin edge bounces/rolls with accelerating wobble pulses, then damped abruptly by boot stomp
    roll_dur = 0.52
    n = int(0.72 * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    # Rolling metallic impulses accelerating before the boot stop
    pulse_t = 0.0
    step_idx = 0
    while pulse_t < roll_dur:
        prog = pulse_t / roll_dur
        idx = int(pulse_t * SR)
        rem = int(round((roll_dur + 0.02 - pulse_t) * SR))
        if rem > 10 and idx + rem <= n:
            ts = np.arange(rem) / SR
            f_base = 2620.0 + 180.0 * np.sin(step_idx * 1.3)
            ring = (
                np.sin(2.0 * np.pi * f_base * ts)
                + 0.65 * np.sin(2.0 * np.pi * (f_base * 1.58) * ts)
                + 0.40 * np.sin(2.0 * np.pi * (f_base * 2.41) * ts)
            ) * env_ad(rem, 0.0005, 0.028 * (1.0 - 0.55 * prog))
            dirt_scrape = fft_filter(rng.standard_normal(rem), lo=1200.0, hi=5500.0) * env_ad(rem, 0.0005, 0.012) * 0.35
            sig[idx: idx + rem] += (ring + dirt_scrape) * (0.55 + 0.35 * prog)
        pulse_t += max(0.018, 0.075 * (1.0 - 0.72 * prog))
        step_idx += 1

    # Abrupt damping when the heavy boot comes down at t = roll_dur
    stop_idx = int(roll_dur * SR)
    sig[stop_idx:] *= np.exp(-np.arange(n - stop_idx) / (0.004 * SR))

    # Heavy boot stomp + final muted coin clink under the sole at roll_dur
    stomp_rem = n - stop_idx
    ts = np.arange(stomp_rem) / SR
    boot_stomp = np.sin(2.0 * np.pi * (78.0 + 60.0 * np.exp(-ts / 0.02)) * ts) * np.exp(-ts / 0.055) * 0.95
    boot_grit = fft_filter(rng.standard_normal(stomp_rem), lo=400.0, hi=3800.0) * env_ad(stomp_rem, 0.001, 0.025) * 0.75
    muted_clink = np.sin(2.0 * np.pi * 2840.0 * ts) * env_ad(stomp_rem, 0.0004, 0.009) * 0.55
    sig[stop_idx:] += boot_stomp + boot_grit + muted_clink

    add_stereo(sfxL, sfxR, t0, sig, gain=gain, pan=0.06)


def sfx_cathedral_bell(t0, gain=0.045):
    """Deep inharmonic bell with a soft attack and long decay."""
    n = int(4.5 * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for ratio, amp, decay in [(0.5, 0.7, 2.8), (1, 1, 2.2), (1.506, 0.45, 1.7),
                              (2, 0.25, 1.2), (2.514, 0.16, 0.8)]:
        sig += amp * np.sin(2 * np.pi * 130.81 * ratio * t) * env_ad(n, 0.008, decay)
    add_stereo(sfxL, sfxR, t0, sig, gain=gain, pan=0.0)


def sfx_door_creak(t0, gain=0.035):
    """Quiet wooden hinge strain, with irregular friction and resonance."""
    n = int(0.85 * SR)
    t = np.arange(n) / SR
    freq = 170 + 55 * np.sin(np.pi * t / 0.85) + 9 * np.sin(2 * np.pi * 13 * t)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    creak = (np.sin(phase) + 0.35 * np.sin(2.07 * phase))
    creak += 0.25 * fft_filter(rng.standard_normal(n), lo=180, hi=1500)
    creak *= env_asr(n, 0.08, 0.2) * (0.7 + 0.3 * np.sin(2 * np.pi * 19 * t))
    add_stereo(sfxL, sfxR, t0, creak, gain=gain, pan=-0.1)


open_a, open_b = shotRange("open")
t_walks = cue("open", "walks")
for i, step_t in enumerate(np.arange(open_a + 0.22, open_b - 0.24, 0.56)):
    near_walks = np.exp(-((step_t - t_walks) / 1.4) ** 2)
    sfx_gravel_step(step_t, gain=0.025 + 0.015 * near_walks, pan=(-0.08, 0.08)[i % 2])
sfx_three_knocks(cue("door", "knocks"), gain=0.09)
for off in (0.0, 1.1):
    sfx_cathedral_bell(cue("night", "clock") + off)
sfx_silver_clink(cue("steal", "silver"), gain=0.035)
sfx_wall_thud(cue("steal", "jumps"), gain=0.075)
sfx_police_boots(cue("caught", "police"), gain=0.07)
sfx_door_creak(cue("cliff", "opens"))
sfxL[CUT_SAMPLE:] = 0.0
sfxR[CUT_SAMPLE:] = 0.0


# -------------------------------------------------------------
# 3. Mix Narration + Score + SFX & Normalize to ~-16 LUFS
# -------------------------------------------------------------
vo, sr = sf.read(os.path.join(ROOT, "audio", "vo.wav"))
assert sr == SR, f"Expected {SR} Hz vo.wav, got {sr}"
if vo.ndim > 1:
    vo = vo.mean(axis=1)
if len(vo) < N:
    vo = np.pad(vo, (0, N - len(vo)))
else:
    vo = vo[:N]

left = vo + musicL + sfxL
right = vo + musicR + sfxR

st = np.stack([left, right], axis=1)
# Cut narration as well: no room tone or synthesis tail in the cliffhanger gap.
st[CUT_SAMPLE:CARD_SAMPLE] = 0.0
st[CARD_SAMPLE:] = np.stack([musicL[CARD_SAMPLE:], musicR[CARD_SAMPLE:]], axis=1)
peak = max(1e-9, float(np.abs(st).max()))
st = st / (peak / 0.89)

raw = os.path.join(ROOT, "audio", "mix_raw.wav")
out_wav = os.path.join(ROOT, "audio", "mix.wav")
sf.write(raw, st.astype(np.float32), SR)

try:
    p1 = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", raw,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    m = json.loads(p1[p1.rindex("{"): p1.rindex("}") + 1])
    af = (
        f"loudnorm=I=-16:TP=-1.5:LRA=11:"
        f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
        f"offset={m['target_offset']}:linear=true"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", raw,
            "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le", out_wav,
        ],
        check=True,
    )
finally:
    if os.path.exists(raw):
        os.remove(raw)

# Ensure exact sample count N matching TIMING.duration
mix_data, mix_sr = sf.read(out_wav, dtype="int16")
if len(mix_data) != N:
    if len(mix_data) < N:
        pad_width = ((0, N - len(mix_data)), (0, 0)) if mix_data.ndim > 1 else (0, N - len(mix_data))
        mix_data = np.pad(mix_data, pad_width)
    else:
        mix_data = mix_data[:N]

# Reassert the hard edit after loudnorm/resampling to remove any filter ringing.
mix_data[CUT_SAMPLE:CARD_SAMPLE] = 0
sf.write(out_wav, mix_data, SR, subtype="PCM_16")

print(f"mix written: {out_wav} ({N / SR:.3f} s, {SR} Hz, target -16 LUFS)")
