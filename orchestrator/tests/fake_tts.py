"""A stand-in for voices/tts.py (CN2's tests and the e2e smoke): reads the request, prints the runner's lines ("loading …", "item k/n"),
writes a 24 kHz 16-bit mono tone of 0.06 s per character (≥ 0.5 s) for every line and the result JSON. Standard library only; never
touches a GPU. FAKE_TTS_FAIL=1 exits 1 after loading (a crash), FAKE_TTS_STEP_S delays each line.

    python fake_tts.py <request.json>
"""
from __future__ import annotations

import json
import math
import os
import struct
import sys
import time
import wave
from pathlib import Path


def tone(path: str, seconds: float, sr: int = 24000, hz: float = 440.0) -> None:
    n = int(seconds * sr)
    frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * i / sr) * min(1.0, i / 2400, (n - i) / 2400))) for i in range(n))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)


def main(argv: list[str]) -> int:
    req = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    items = req["items"]
    print(f"loading {req['model']} ({req.get('voice') or 'clone'}) on the {'CPU' if req['tier'] == 'draft' else 'GPU'}", flush=True)
    time.sleep(0.05)
    print("loaded in 0.1 s", flush=True)
    if os.environ.get("FAKE_TTS_FAIL"):
        print("boom: the fake runner was told to fail", flush=True)
        return 1
    if req["tier"] == "cloning":
        ref = req.get("reference") or {}
        if not Path(ref.get("audio", "")).is_file():
            print(f"no reference clip at {ref.get('audio')}", flush=True)
            return 2
        print("cloned the reference in 0.1 s", flush=True)
    delay = float(os.environ.get("FAKE_TTS_STEP_S") or 0.0)
    results = []
    for n, it in enumerate(items, 1):
        secs = max(0.5, round(0.06 * len(it["text"]), 3))
        tone(it["out"], secs, hz=330.0 + 55.0 * n)
        results.append({"i": it["i"], "file": it["out"], "duration_s": secs, "seconds": round(secs * 0.9, 3), "sample_rate": 24000})
        print(f"item {n}/{len(items)}: {secs} s of speech in {secs * 0.9:.2f} s", flush=True)
        if delay:
            time.sleep(delay)
    out = {"tier": req["tier"], "model": req["model"], "load_s": 0.1, "peak_vram_gb": 2.6 if req["tier"] == "cloning" else None, "items": results, "wall_s": 0.2}
    Path(req["result"]).write_text(json.dumps(out), encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
