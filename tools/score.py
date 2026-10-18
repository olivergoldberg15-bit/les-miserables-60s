"""Music bed + sound effects + narration -> audio/mix.wav (-14 LUFS).
Everything is synthesized here; cue times come from data/timing.js, same as the visuals."""
import json, os, re, subprocess
import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
TM = json.loads(open(os.path.join(ROOT, "data", "timing.js"), encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))
DUR = TM["duration"]
N = int(DUR * SR) + 1
LINES = TM["lines"]
LN = {l["id"]: l for l in LINES}
CUT = [0] + [(LINES[i - 1]["end"] + LINES[i]["start"]) / 2 for i in range(1, len(LINES))]
norm = lambda s: re.sub(r"[^a-z0-9']", "", s.lower())


def cue(lid, w, nth=1):
    n = 0
    for x in LN[lid]["words"]:
        if norm(x["w"]) == norm(w):
            n += 1
            if n == nth:
                return x["s"]
    raise KeyError((lid, w))


rng = np.random.default_rng(7)
mf = lambda m: 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = np.ones_like(f)
    if hi:
        H *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        H *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def add(buf, t0, sig, gain=1.0):
    a = int(t0 * SR)
    if a >= len(buf) or a + len(sig) <= 0:
        return
    s = sig[max(0, -a):]
    a = max(0, a)
    b = min(len(buf), a + len(s))
    buf[a:b] += gain * s[: b - a]


def env_ad(n, att, dec):
    t = np.arange(n) / SR
    return (1 - np.exp(-t / max(att, 1e-4))) * np.exp(-t / dec)


# ------------------------------------------------------------- music
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [  # (bass, pad notes)
    (45, [57, 60, 64, 67, 71]),  # Am9
    (41, [53, 57, 60, 64, 69]),  # Fmaj7
    (48, [55, 60, 64, 67, 74]),  # C add9
    (43, [55, 59, 62, 64, 67]),  # G6
]
END_MUSIC = LN["cta"]["end"] + 0.2
pad = np.zeros(N)
arp = np.zeros(N)
drums = np.zeros(N)
bass = np.zeros(N)

seg_len = 2 * BAR
nseg = int(np.ceil(DUR / seg_len)) + 1
for si in range(nseg):
    t0 = si * seg_len
    if t0 >= DUR:
        break
    root, notes = CHORDS[si % 4]
    L = int((seg_len + 1.2) * SR)
    tt = np.arange(L) / SR
    sig = np.zeros(L)
    for m in notes:
        for det in (-0.07, 0.0, 0.07):
            f = mf(m) * 2 ** (det / 12)
            for k in range(1, 7):
                sig += (0.5 ** (k - 1)) / k * np.sin(2 * np.pi * f * k * tt + k * det * 9)
    e = np.minimum(1, tt / 0.7) * np.where(tt > seg_len, np.exp(-(tt - seg_len) / 0.45), 1.0)
    add(pad, t0, sig * e, 0.010)
    # bass: root on beat 1 and the "and" of 2
    for bar in range(2):
        for off in (0, 1.5 * BEAT):
            bt = t0 + bar * BAR + off
            if bt < CUT[1] - 0.05 or bt > END_MUSIC:
                continue
            n = int(1.2 * SR)
            x = np.arange(n) / SR
            f = mf(root - 12 + 12)
            add(bass, bt, (np.sin(2 * np.pi * f * x) + 0.25 * np.sin(4 * np.pi * f * x)) * env_ad(n, 0.005, 0.45), 0.16)
    # arp: 8th notes through the chord, an octave up
    pat = [0, 2, 1, 3, 2, 4, 1, 3]
    for i in range(16):
        at = t0 + i * BEAT / 2
        if at < CUT[1] - 0.05 or at > END_MUSIC:
            continue
        m = notes[pat[i % 8]] + 12
        n = int(0.6 * SR)
        x = np.arange(n) / SR
        f = mf(m)
        tone = np.sin(2 * np.pi * f * x) + 0.35 * np.sin(4 * np.pi * f * x) * np.exp(-x / 0.08)
        add(arp, at, tone * env_ad(n, 0.003, 0.2), 0.05)

# drums from the second shot on
kick_n = int(0.35 * SR)
kx = np.arange(kick_n) / SR
kick = np.sin(2 * np.pi * np.cumsum(45 + 75 * np.exp(-kx / 0.05)) / SR) * env_ad(kick_n, 0.002, 0.16)
hat_n = int(0.06 * SR)
hat = fft_filter(rng.standard_normal(hat_n), lo=7000) * env_ad(hat_n, 0.001, 0.018)
b = CUT[2]
while b < END_MUSIC - 0.5:
    add(drums, b, kick, 0.33)
    add(drums, b + 2 * BEAT, kick, 0.26)
    for h in range(4):
        add(drums, b + h * BEAT + BEAT / 2, hat, 0.05)
    b += BAR

# gentle fade in/out, ducked under the voice
tt = np.arange(N) / SR
duck = np.zeros(N)
for l in LINES:
    a, b2 = int((l["start"] - 0.08) * SR), int((l["end"] + 0.12) * SR)
    duck[max(0, a):b2] = 1
k = int(0.12 * SR)
duck = np.convolve(duck, np.ones(k) / k, mode="same")
g = np.minimum(1, tt / 0.6) * np.clip((DUR - tt) / 1.6, 0, 1) * (1 - 0.45 * duck)
music = (pad + drums + bass) * g * 0.63
arpL = arp * g * 0.63
d = int(0.014 * SR)
arpR = np.concatenate([np.zeros(d), arpL[:-d]])

# ------------------------------------------------------------- sfx
sfx = np.zeros(N)


def whoosh(t0, dur=0.55, gain=0.09):
    n = int(dur * SR)
    x = np.arange(n) / SR
    noise = fft_filter(rng.standard_normal(n), lo=500, hi=4500)
    e = np.sin(np.pi * x / dur) ** 2
    add(sfx, t0 - dur * 0.6, noise * e, gain)


def tick(t0, gain=0.08):
    n = int(0.02 * SR)
    x = np.arange(n) / SR
    add(sfx, t0, np.sin(2 * np.pi * 2600 * x) * np.exp(-x / 0.004), gain)


def thunk(t0, gain=0.3):
    n = int(0.4 * SR)
    x = np.arange(n) / SR
    s = np.sin(2 * np.pi * (150 + 60 * np.exp(-x / 0.03)) * x) * np.exp(-x / 0.12)
    s += 0.3 * fft_filter(rng.standard_normal(n), hi=2500) * np.exp(-x / 0.02)
    add(sfx, t0, s, gain)


def ding(t0, gain=0.11, notes=(84, 91)):
    for i, m in enumerate(notes):
        n = int(1.0 * SR)
        x = np.arange(n) / SR
        f = mf(m)
        add(sfx, t0 + i * 0.06, (np.sin(2 * np.pi * f * x) + 0.2 * np.sin(2 * np.pi * 2.76 * f * x) * np.exp(-x / 0.05)) * env_ad(n, 0.002, 0.32), gain)


def click(t0, gain=0.12):
    n = int(0.03 * SR)
    add(sfx, t0, fft_filter(rng.standard_normal(n), lo=1500) * env_ad(n, 0.0005, 0.006), gain)


def glitch(t0, dur=0.6, gain=0.08):
    n = int(dur * SR)
    x = np.arange(n) / SR
    gate = (np.sin(2 * np.pi * 26 * x) > 0.2).astype(float)
    add(sfx, t0, fft_filter(rng.standard_normal(n), lo=800, hi=6000) * gate * np.exp(-x / 0.35), gain)


def riser(t0, dur, gain=0.07):
    n = int(dur * SR)
    x = np.arange(n) / SR
    f = 300 + 1500 * (x / dur) ** 2
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + fft_filter(rng.standard_normal(n), lo=2000) * 0.6
    add(sfx, t0, s * (x / dur) ** 2, gain)


for i in range(1, len(CUT)):
    if LINES[i]["id"] != "cta":
        whoosh(CUT[i])
# hook hops (9 per second on screen)
x = 0.0
while x < CUT[1]:
    tick(x, 0.05)
    x += 1 / 9
IDX = {l["id"]: i for i, l in enumerate(LINES)}
END = lambda lid: CUT[IDX[lid] + 1] if IDX[lid] + 1 < len(CUT) else DUR
click(cue("advert", "Open") + 0.05)
whoosh(cue("shake", "scrambled") + 0.5, 0.8, 0.06)
ding(cue("shake", "same") + 0.2)
whoosh(cue("shake", "anyone"), 0.7, 0.05)
thunk(cue("shake", "can't"))
ding(cue("saved", "saves") + 0.6, 0.08, (79, 86))
whoosh(cue("inside", "inside") + 0.6, 0.9, 0.08)
ding(cue("stem", "antenna"), 0.1, (88, 95))
tick(cue("catch", "antenna") + 0.2, 0.12)
ding(cue("catch", "H2"), 0.07, (91,))
thunk(cue("catch", "speaker"), 0.18)
# hop ticks
tJ = cue("hop", "jumping")
x = tJ
while x < END("hop"):
    tick(x)
    x += 1 / 6.4
tJam = cue("resend", "jammed")
for i in range(4):
    tick(tJam - (3 - i) * 0.3)
thunk(tJam)
r0 = cue("resend", "resent") - 0.3
tick(r0)
ding(r0 + 0.45)
tC = max(cue("resend", "skips") + 0.2, r0 + 1.1)
x = tC
while x < END("resend"):
    tick(x)
    x += 1 / 6.4
glitch(cue("body", "glitch"))
tRu = cue("name", "runes")
riser(tRu - 0.6, 1.4)
ding(tRu + 0.85, 0.13, (76, 83, 88))

# ------------------------------------------------------------- mix
vo, sr = sf.read(os.path.join(ROOT, "audio", "vo.wav"))
assert sr == SR
vo = np.pad(vo, (0, max(0, N - len(vo))))[:N]
left = vo + music + arpL + sfx
right = vo + music + arpR + sfx
def _r(sig, a, b):
    return round(20 * np.log10(np.sqrt(np.mean(sig[int(a * SR):int(b * SR)] ** 2)) + 1e-9), 1)
print("stems dB (14-20s speech): vo", _r(vo, 14, 20), "music", _r(music + arpL, 14, 20), "sfx", _r(sfx, 14, 20),
      "| music in 40-44s", _r(music + arpL, 40, 44), "| sfx 44-52 hop ticks", _r(sfx, 47.6, 51.7))
st = np.stack([left, right], 1)
st /= max(1e-9, np.abs(st).max()) / 0.89
raw = os.path.join(ROOT, "audio", "mix_raw.wav")
sf.write(raw, st.astype(np.float32), SR)

# two-pass loudnorm to -14 LUFS
p1 = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
m = json.loads(p1[p1.rindex("{"): p1.rindex("}") + 1])
af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le",
                os.path.join(ROOT, "audio", "mix.wav")], check=True)
print("mix written", DUR, "s; measured input", m["input_i"], "LUFS")
