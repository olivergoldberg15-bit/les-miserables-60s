"""Restrained period score (D minor -> D major on 'soul', swelling under 'weep' and end card)
+ diegetic SFX keyed to data/timing.js cue words + narration -> audio/mix.wav (48 kHz, ~-16 LUFS).
Run: python tools/score.py"""
import json
import os
import re
import subprocess
import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000

with open(os.path.join(ROOT, "data", "timing.js"), encoding="utf-8") as _f:
    TM = json.loads(_f.read().split("=", 1)[1].strip().rstrip(";"))

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


def cue(lid, word=None, nth=1):
    if word is None:
        target = norm(lid)
        n = 0
        for l in LINES:
            for x in l["words"]:
                if norm(x["w"]) == target:
                    n += 1
                    if n == nth:
                        return float(x["s"])
        raise KeyError((lid, nth))
    target = norm(word)
    n = 0
    for x in LN[lid]["words"]:
        if norm(x["w"]) == target:
            n += 1
            if n == nth:
                return float(x["s"])
    raise KeyError((lid, word, nth))


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
# 1. Restrained Period Score (Chamber Strings + Sparse Felt Piano)
#    D minor in shots 1..10 -> resolves to D major on 'soul' ->
#    swells softly under 'weep' and the end card.
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


# Score harmonic plan across the 14 shots:
# Shots 1-10 stay in D minor (and relative/subdominant minor colors);
# Shot 11 ('soul') resolves from suspension into warm D major on 'soul';
# Shots 13 ('weep') and 14 ('end') swell softly in D major.
SHOT_CHORDS_DM = {
    "open":     ([38, 45, 50, 53, 57], 0.013, 1200.0),      # Dm (D2 A2 D3 F3 A3)
    "bread":    ([43, 50, 55, 58, 62], 0.012, 1150.0),      # Gm
    "years":    ([34, 41, 50, 53, 57], 0.012, 1100.0),      # Bbmaj7
    "passport": ([38, 45, 50, 53, 60], 0.012, 1150.0),      # Dm7
    "rejected": ([40, 46, 50, 55, 58], 0.012, 1100.0),      # Em7b5
    "door":     ([38, 45, 50, 53, 57, 62], 0.013, 1300.0),  # Dm (warmer voicing)
    "dinner":   ([41, 48, 53, 57, 60, 62], 0.014, 1400.0),  # F6 / Dm7
    "steal":    ([43, 50, 55, 58], 0.011, 1050.0),          # Gm (tense, darker)
    "caught":   ([33, 45, 52, 55, 61], 0.012, 1100.0),      # A7 (dominant tension)
    "gift":     ([43, 50, 53, 58, 62], 0.013, 1250.0),      # Gm7 -> prepares resolution
}

for lid, (notes, gain, cutoff) in SHOT_CHORDS_DM.items():
    a, b = shotRange(lid)
    dur = (b - a) + 0.65
    sL, sR = synth_string_chord(notes, dur, cutoff=cutoff)
    add(padL, max(0.0, a - 0.15), sL, gain)
    add(padR, max(0.0, a - 0.15), sR, gain)

# Shot 11 ('soul'): begins on a quiet Dsus2/Dm whisper, then resolves to luminous D major on the 'soul' line
soul_a, soul_b = shotRange("soul")
t_soul_quote = cue("soul", "You")
t_soul_word = cue("soul", "soul")
# Pre-resolution quiet suspension (D2 A2 D3 E3 A3)
sL, sR = synth_string_chord([38, 45, 50, 52, 57], max(0.8, t_soul_quote - soul_a + 0.5), cutoff=1250.0)
add(padL, soul_a - 0.1, sL, 0.012)
add(padR, soul_a - 0.1, sR, 0.012)
# D major resolution entering gently on "You" and blossoming on "soul" (D2 A2 D3 F#3 A3 D4 F#4)
sL, sR = synth_string_chord([38, 45, 50, 54, 57, 62, 66], (soul_b - t_soul_quote) + 0.8, cutoff=1750.0)
add(padL, t_soul_quote - 0.1, sL, 0.016)
add(padR, t_soul_quote - 0.1, sR, 0.016)

# Shot 12 ('coin'): poignant B minor7 / Gmaj7 (within D major key)
coin_a, coin_b = shotRange("coin")
sL, sR = synth_string_chord([43, 50, 54, 59, 62], (coin_b - coin_a) + 0.6, cutoff=1350.0)
add(padL, coin_a - 0.15, sL, 0.013)
add(padR, coin_a - 0.15, sR, 0.013)

# Shot 13 ('weep'): soft emotional swell in D major (Gmaj9 -> D/F# -> A6)
weep_a, weep_b = shotRange("weep")
t_weep_word = cue("weep", "weeps")
sL1, sR1 = synth_string_chord([43, 50, 54, 59, 62, 66], (weep_b - weep_a) + 0.7, cutoff=1950.0, vib_depth=0.045)
add(padL, weep_a - 0.15, sL1, 0.018)
add(padR, weep_a - 0.15, sR1, 0.018)
sL2, sR2 = synth_string_chord([38, 45, 54, 57, 62, 66, 69], (weep_b - t_weep_word) + 0.9, cutoff=2100.0, vib_depth=0.05)
add(padL, t_weep_word - 0.1, sL2, 0.016)
add(padR, t_weep_word - 0.1, sR2, 0.016)

# Shot 14 ('end'): warm D major swell under the final line and end card ("LES MISERABLES")
end_a, end_b = shotRange("end")
t_end_card = cue("end", "Les")
sL3, sR3 = synth_string_chord([38, 45, 50, 54, 57, 62, 66], (end_b - end_a), cutoff=1950.0, vib_depth=0.045)
add(padL, end_a - 0.2, sL3, 0.018)
add(padR, end_a - 0.2, sR3, 0.018)
# End-card D major warm glow (D2 A2 D3 F#3 A3 D4 F#4 A4)
sL4, sR4 = synth_string_chord([38, 45, 50, 54, 57, 62, 66, 69], max(1.2, DUR - t_end_card + 0.2), cutoff=2250.0, vib_depth=0.05)
add(padL, t_end_card - 0.15, sL4, 0.022)
add(padR, t_end_card - 0.15, sR4, 0.022)


# Sparse Piano Motif:
# In D minor through shots 1..10 (using D4=62, E4=64, F4=65, G4=67, A4=69, Bb4=70),
# resolving to D major (F#4=66, A4=69, D5=74) on 'soul', and singing softly in 'weep' and 'end'.
def schedule_piano():
    # Shot 1 ('open'): sparse D minor motif (A4 - F4 - E4 - D4)
    a, b = shotRange("open")
    add_piano_note(a + 0.25, 69, 2.4, 0.60, -0.15)
    add_piano_note(cue("open", "October") + 0.55, 65, 2.2, 0.54, 0.10)
    add_piano_note(cue("open", "walks") + 0.15, 64, 1.9, 0.50, -0.08)
    add_piano_note(lineEnd("open") - 0.15, 62, 2.6, 0.58, 0.12)

    # Shot 2 ('bread'): plaintive Gm answer (Bb4 - A4 - G4)
    add_piano_note(lineStart("bread") + 0.15, 70, 2.1, 0.52, 0.18)
    add_piano_note(cue("bread", "seven"), 69, 1.9, 0.48, -0.12)
    add_piano_note(lineEnd("bread") - 0.1, 67, 2.3, 0.52, 0.08)

    # Shot 3 ('years'): low tolling fifth + F4 - E4 - D4
    add_piano_note(lineStart("years") + 0.1, 50, 2.8, 0.56, -0.20)
    add_piano_note(cue("years", "Four") - 0.15, 65, 2.0, 0.50, 0.14)
    add_piano_note(cue("years", "nineteen"), 62, 2.5, 0.55, -0.10)

    # Shot 4 ('passport'): single sparse minor reflection (A4 - F4)
    add_piano_note(lineStart("passport") + 0.2, 69, 2.1, 0.48, 0.12)
    add_piano_note(lineEnd("passport") - 0.1, 65, 2.3, 0.50, -0.14)

    # Shot 5 ('rejected'): descending minor step (G4 - F4 - E4)
    add_piano_note(cue("rejected", "away") + 0.1, 67, 1.8, 0.48, -0.15)
    add_piano_note(cue("rejected", "prison") + 0.25, 65, 1.8, 0.46, 0.12)
    add_piano_note(lineEnd("rejected") - 0.05, 64, 2.1, 0.50, -0.08)

    # Shot 6 ('door'): warm fifth lift as the bishop's door opens (D4 - A4 - F4)
    add_piano_note(cue("door", "Bishop"), 62, 2.2, 0.52, -0.12)
    add_piano_note(lineEnd("door") - 0.1, 69, 2.4, 0.58, 0.15)

    # Shot 7 ('dinner'): gentle warm interior motif (F4 - A4 - C5 - A4)
    add_piano_note(cue("dinner", "sir") + 0.1, 65, 2.2, 0.55, -0.14)
    add_piano_note(cue("dinner", "candlesticks") + 0.15, 69, 2.2, 0.58, 0.14)
    add_piano_note(lineEnd("dinner") - 0.1, 72, 2.5, 0.54, 0.05)

    # Shot 8 ('steal'): nocturnal low Dm/Gm pulse (D3 - Bb3 - A3)
    add_piano_note(lineStart("steal") + 0.15, 50, 2.4, 0.50, -0.18)
    add_piano_note(cue("steal", "steals"), 58, 2.0, 0.48, 0.12)
    add_piano_note(cue("steal", "jumps"), 57, 2.0, 0.48, -0.10)

    # Shot 9 ('caught'): low dominant tension (A3 - G4 - E4)
    add_piano_note(lineStart("caught") + 0.1, 57, 2.2, 0.52, -0.15)
    add_piano_note(lineEnd("caught") - 0.1, 64, 2.2, 0.50, 0.12)

    # Shot 10 ('gift'): gentle questioning motif preparing D major (G4 - F4 - E4 - A4)
    add_piano_note(cue("gift", "candlesticks"), 67, 2.1, 0.54, -0.12)
    add_piano_note(cue("gift", "Why"), 64, 2.0, 0.52, 0.14)
    add_piano_note(lineEnd("gift") - 0.05, 69, 2.5, 0.56, 0.0)

    # Shot 11 ('soul'): RESOLVES TO D MAJOR (F#4 = 66, A4 = 69, D5 = 74)
    add_piano_note(cue("soul", "You"), 66, 2.8, 0.64, -0.12)       # F#4 (major third!)
    add_piano_note(cue("soul", "evil") + 0.15, 69, 2.6, 0.62, 0.14)  # A4
    add_piano_note(cue("soul", "soul"), 50, 3.4, 0.66, -0.20)       # D3 bass anchor
    add_piano_note(cue("soul", "soul") + 0.04, 66, 3.2, 0.68, 0.05) # F#4
    add_piano_note(cue("soul", "soul") + 0.10, 74, 3.2, 0.72, 0.18) # D5 luminous resolution
    add_piano_note(lineEnd("soul") + 0.05, 69, 2.8, 0.62, -0.08)    # A4

    # Shot 12 ('coin'): sparse reflective D major / Bm notes (F#4 - D4 - E4)
    add_piano_note(lineStart("coin") + 0.2, 66, 2.2, 0.52, -0.10)
    add_piano_note(lineEnd("coin") + 0.05, 62, 2.4, 0.54, 0.12)

    # Shot 13 ('weep'): tender D major motif swelling under 'weep' (F#4 - A4 - B4 - A4 - F#4 - D5)
    add_piano_note(lineStart("weep") + 0.05, 66, 2.6, 0.64, -0.15)
    add_piano_note(cue("weep", "weeps"), 50, 3.2, 0.68, -0.22)
    add_piano_note(cue("weep", "weeps") + 0.05, 69, 2.8, 0.72, 0.12)
    add_piano_note(cue("weep", "first"), 71, 2.5, 0.68, 0.18)
    add_piano_note(cue("weep", "nineteen"), 66, 2.8, 0.70, -0.10)
    add_piano_note(lineEnd("weep") + 0.05, 74, 3.0, 0.74, 0.14)

    # Shot 14 ('end'): noble D major cadence swelling into the end card ("LES MISERABLES")
    add_piano_note(lineStart("end") + 0.1, 66, 2.6, 0.64, -0.14)
    add_piano_note(cue("end", "road") + 0.1, 69, 2.6, 0.66, 0.12)
    t_les = cue("end", "Les")
    add_piano_note(t_les - 0.05, 38, 3.5, 0.76, -0.20)   # D2
    add_piano_note(t_les, 50, 3.5, 0.74, -0.10)          # D3
    add_piano_note(t_les + 0.05, 66, 3.4, 0.78, 0.08)    # F#4
    add_piano_note(t_les + 0.12, 69, 3.3, 0.76, 0.16)    # A4
    add_piano_note(lineEnd("end") + 0.15, 74, 2.6, 0.80, 0.0)   # D5 final bell-like tonic
    add_piano_note(lineEnd("end") + 0.65, 66, 2.1, 0.68, -0.12) # F#4 warm third


schedule_piano()

# Shape overall score dynamics: restrained in shots 1..10, warming on 'soul',
# swelling softly under 'weep' and the end card, ducking smoothly under speech.
tt = np.arange(N) / SR
speech_gate = np.zeros(N, dtype=np.float64)
for l in LINES:
    s_idx = max(0, int((l["start"] - 0.08) * SR))
    e_idx = min(N, int((l["end"] + 0.12) * SR))
    speech_gate[s_idx:e_idx] = 1.0

win_len = int(0.18 * SR)
speech_env = np.convolve(speech_gate, np.ones(win_len) / win_len, mode="same")

# Swell curve tied to cue/shot times (no hard-coded times)
swell = np.ones(N, dtype=np.float64) * 0.88
# Warm lift on 'soul'
soul_swell = 0.22 * np.clip((tt - cue("soul", "You")) / 1.2, 0.0, 1.0) * np.clip((shotRange("coin")[0] + 0.6 - tt) / 0.9, 0.0, 1.0)
# Soft swell under 'weep' and the end card
weep_start = shotRange("weep")[0]
weep_swell = 0.48 * np.clip((tt - weep_start) / 1.4, 0.0, 1.0)
end_card_swell = 0.32 * np.clip((tt - (cue("end", "Les") - 0.2)) / 0.9, 0.0, 1.0)
swell = swell + soul_swell + weep_swell + end_card_swell

# Fade in at start, smooth fade out at the very end of TIMING.duration
fade_in = np.clip(tt / 0.7, 0.0, 1.0)
fade_out = np.clip((DUR - tt) / 0.75, 0.0, 1.0)
# Duck music under speech (less ducking during 'weep' and 'end' so the soft swell is felt)
duck_depth = np.where(tt >= weep_start, 0.38, 0.52)
music_gain = fade_in * fade_out * swell * (1.0 - duck_depth * speech_env)

musicL = (padL + pianoL) * music_gain
musicR = (padR + pianoR) * music_gain


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


# Schedule all required SFX keyed to data/timing.js cues:
# 1. Footsteps on gravel under 'open'
open_a, open_b = shotRange("open")
t_walks = cue("open", "walks")
step_t = open_a + 0.22
step_i = 0
while step_t < open_b - 0.20:
    # Emphasize footsteps around "walks"
    near_walks = np.exp(-((step_t - t_walks) / 1.4) ** 2)
    sfx_gravel_step(step_t, gain=0.11 + 0.05 * near_walks, pan=-0.08 + 0.16 * (step_i % 2))
    step_t += 0.56
    step_i += 1

# 2. Glass shatter on 'stole'
sfx_glass_shatter(cue("bread", "stole"))

# 3. Scratch ticks across 'years' (on 'Five', 'years', and across 'Four' .. 'nineteen')
t_five = cue("years", "Five")
t_years_word = cue("years", "years")
t_four = cue("years", "Four")
t_nineteen = cue("years", "nineteen")
sfx_scratch_tick(t_five, dur=0.13, gain=0.17, pan=-0.12)
sfx_scratch_tick(t_years_word, dur=0.14, gain=0.16, pan=-0.06)
for esc_i in range(4):
    t_esc = t_four + (t_nineteen - t_four) * (esc_i / 4.0)
    sfx_scratch_tick(t_esc, dur=0.13, gain=0.17, pan=-0.08 + 0.06 * esc_i)
sfx_scratch_tick(t_nineteen, dur=0.18, gain=0.20, pan=0.12)

# 4. Paper rustle on 'passport'
sfx_paper_rustle(cue("passport", "passport"))

# 5. Door slam on 'Inns'
sfx_door_slam(cue("rejected", "Inns"))

# 6. Wicket clack on 'prison'
sfx_wicket_clack(cue("rejected", "prison"))

# 7. Low dog growl on 'kennel'
sfx_dog_growl(cue("rejected", "kennel"))

# 8. Three knocks on 'knocks'
sfx_three_knocks(cue("door", "knocks"))

# 9. Match strike on 'lights'
sfx_match_strike(cue("dinner", "lights"))

# 10. Silver clink on 'silver' in 'steal'
sfx_silver_clink(cue("steal", "silver"))

# 11. Thud on 'wall'
sfx_wall_thud(cue("steal", "wall"))

# 12. Boots on 'police'
sfx_police_boots(cue("caught", "police"))

# 13. Coin roll and stop on 'coin'
sfx_coin_roll_and_stop(cue("coin", "coin"))


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
    sf.write(out_wav, mix_data, SR, subtype="PCM_16")

print(f"mix written: {out_wav} ({N / SR:.3f} s, {SR} Hz, target -16 LUFS)")
