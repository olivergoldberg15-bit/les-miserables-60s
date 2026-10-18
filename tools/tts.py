"""Stand-in narration (Oliver records the real VO): one edge-tts take per script line, word timings from WordBoundary,
assembled into audio/vo.wav and data/timing.js (window.TIMING).
Run: Python314/python.exe tools/tts.py [voice] [rate]"""
import asyncio, json, os, subprocess, sys
import numpy as np
import soundfile as sf
import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE = sys.argv[1] if len(sys.argv) > 1 else "en-US-AndrewNeural"
RATE = sys.argv[2] if len(sys.argv) > 2 else "-6%"
SR = 48000

# id, text, gap before (s). Scene turns get a longer breath.
LINES = [
    ("open",     "October 1815. An hour before sunset, a man walks into the town of Digne.", 0.9),
    ("bread",    "Jean Valjean, who once stole a loaf of bread for his sister's seven starving kids.", 0.30),
    ("years",    "Five years for the bread. Four failed escapes made it nineteen.", 0.20),
    ("passport", "His yellow passport brands him a convict.", 0.30),
    ("rejected", "Inns turn him away. So does the prison, and even a dog's kennel.", 0.30),
    ("bishop",   "Across town lives Bishop Myriel, who gave his palace to the hospital and never locks his door.", 0.45),
    ("door",     "Valjean knocks.", 0.25),
    ("dinner",   "The bishop calls him sir, lights his two silver candlesticks, and serves him dinner.", 0.40),
    ("night",    "At two in the morning, the cathedral clock wakes him.", 0.45),
    ("bedside",  "He stands over the sleeping bishop, an iron candlestick in his hand.", 0.35),
    ("steal",    "Then he takes the silver and jumps the garden wall.", 0.40),
    ("caught",   "By morning, police drag him back.", 0.50),
    ("cliff",    "The door opens. The bishop looks at the silver. Then at Valjean. And he says...", 0.40),
]
TAIL = 4.6


async def synth(text, mp3, tries=4):
    for k in range(tries):
        try:
            return await _synth(text, mp3)
        except edge_tts.exceptions.NoAudioReceived:
            print("  retry", k + 1, text[:30]); await asyncio.sleep(1.5)
    return await _synth(text.replace('"', ""), mp3)


async def _synth(text, mp3):
    com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    words, audio = [], bytearray()
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append({"w": ch["text"], "s": ch["offset"] / 1e7, "e": (ch["offset"] + ch["duration"]) / 1e7})
    open(mp3, "wb").write(audio)
    return words


def decode(mp3):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", mp3, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def trim(x, thr=0.004):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x, 0.0
    a = max(0, idx[0] - int(0.02 * SR))
    b = min(len(x), idx[-1] + int(0.06 * SR))
    return x[a:b], a / SR


SPEAK = {"open": "October, eighteen fifteen. An hour before sunset, a man walks into the town of Digne."}
MERGE = {("eighteen", "fifteen"): "1815"}


def merge(words):
    out, i = [], 0
    while i < len(words):
        pair = tuple(w["w"].lower() for w in words[i:i + 2])
        if pair in MERGE:
            out.append({"w": MERGE[pair], "s": words[i]["s"], "e": words[i + 1]["e"]})
            i += 2
        else:
            out.append(words[i]); i += 1
    return out


def attach_punct(words, text):
    """Display form of each word: the word as written in the line, with its trailing punctuation."""
    cur = 0
    for w in words:
        k = text.find(w["w"], cur)
        if k < 0:
            w["d"] = w["w"]; continue
        j = k + len(w["w"])
        while j < len(text) and text[j] in ",.?!:;\"”":
            j += 1
        while k > 0 and text[k - 1] in "\"“":
            k -= 1
        w["d"] = text[k:j]; cur = j


async def main():
    os.makedirs(os.path.join(ROOT, "audio", "lines"), exist_ok=True)
    out, t, lines = [], 0.0, []
    for i, (lid, text, gap) in enumerate(LINES):
        mp3 = os.path.join(ROOT, "audio", "lines", f"{i:02d}_{lid}.mp3")
        words = merge(await synth(SPEAK.get(lid, text), mp3))
        attach_punct(words, text)
        x, lead = trim(decode(mp3))
        t += gap
        start = t
        out.append((start, x))
        ws = [{"w": w["d"], "s": round(start + w["s"] - lead, 3), "e": round(start + w["e"] - lead, 3)} for w in words]
        t += len(x) / SR
        lines.append({"id": lid, "text": text, "start": round(start, 3), "end": round(t, 3), "words": ws})
        print(f"{lid:7s} {start:6.2f} -> {t:6.2f}  ({len(ws)} words)")
    total = t + TAIL
    buf = np.zeros(int(total * SR) + 1, dtype=np.float32)
    for start, x in out:
        a = int(start * SR)
        buf[a:a + len(x)] += x
    sf.write(os.path.join(ROOT, "audio", "vo.wav"), buf, SR)
    timing = {"voice": VOICE, "rate": RATE, "duration": round(total, 3), "lines": lines}
    with open(os.path.join(ROOT, "data", "timing.js"), "w", encoding="utf-8") as f:
        f.write("window.TIMING = " + json.dumps(timing, indent=1) + ";\n")
    print("total", round(total, 2))


asyncio.run(main())
