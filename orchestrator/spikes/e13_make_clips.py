"""E13 timeline spike (ArtCraft 08 §7, D74), clip half: ten 5 s clips at 24 fps for a single-lane timeline to scrub.

Run:  orchestrator/.venv/Scripts/python.exe orchestrator/spikes/e13_make_clips.py

Writes frontend/public/spikes/e13/c00.mp4 … c09.mp4 (h264 yuv420p, 640×360, 120 frames, GOP 6 — the proxy policy from E6) and
clips.json. Every frame carries an 11-bit code in its top-left corner — 4 bits of clip id, 7 bits of frame index, 16 px squares, white = 1
— so the browser checks which clip and which frame it actually shows, not which it asked for. Each clip has its own hue and a slow
drift so a crossfade between two is visible.
"""
from __future__ import annotations

import colorsys
import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "frontend" / "public" / "spikes" / "e13"
W, H, N, FPS, CLIPS = 640, 360, 120, 24, 10


def frame(clip: int, i: int) -> np.ndarray:
    r, g, b = (int(255 * c) for c in colorsys.hsv_to_rgb(clip / CLIPS, 0.55, 0.75))
    im = Image.new("RGB", (W, H), (r // 3, g // 3, b // 3))
    d = ImageDraw.Draw(im)
    x = int((W - 200) * i / (N - 1))                                   # a block drifting across the frame
    d.rectangle([x, 120, x + 200, 300], fill=(r, g, b))
    code = (clip << 7) | i
    for k in range(11):                                                # the code: 11 squares at (8 + 16k, 8)
        v = 255 if (code >> (10 - k)) & 1 else 0
        d.rectangle([8 + k * 16, 8, 8 + k * 16 + 13, 21], fill=(v, v, v))
    d.rectangle([8, 28, 200, 44], fill=(0, 0, 0))
    d.text((10, 30), f"clip {clip:02d} · frame {i:03d}", fill=(255, 255, 255), font=ImageFont.load_default())
    return np.asarray(im)


def encode(clip: int, path: Path) -> None:
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=FPS)
        s.width, s.height, s.pix_fmt = W, H, "yuv420p"
        s.time_base = Fraction(1, FPS)
        s.options = {"g": "6", "crf": "18", "preset": "veryfast", "bf": "0"}
        for i in range(N):
            vf = av.VideoFrame.from_ndarray(frame(clip, i), format="rgb24")
            vf.pts = i
            for p in s.encode(vf):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for c in range(CLIPS):
        path = OUT / f"c{c:02d}.mp4"
        encode(c, path)
        meta.append({"id": c, "file": path.name, "frames": N, "fps": FPS, "bytes": path.stat().st_size})
    (OUT / "clips.json").write_text(json.dumps({"width": W, "height": H, "clips": meta}, indent=1) + "\n", encoding="utf-8")
    print(f"{CLIPS} clips -> {OUT} ({sum(m['bytes'] for m in meta) // 1024} KB)")


if __name__ == "__main__":
    main()
