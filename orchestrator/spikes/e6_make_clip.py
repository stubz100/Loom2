"""E6 spike, backend half: make a 121-frame 24 fps test clip and benchmark exact frame seeks with PyAV.

Run:  orchestrator/.venv/Scripts/python.exe orchestrator/spikes/e6_make_clip.py

Writes frontend/public/spikes/e6_clip.mp4 (h264 yuv420p, 1024×576, 121 frames @ 24 fps, frame index burned in
and encoded into the pixels as a 7-bit code in the top-left so the browser can verify frame-accurate stepping),
and orchestrator/spikes/out/e6_backend.json with per-frame exact-seek timings (seek to keyframe + decode
forward, which is what PyAV offers; TorchCodec exact mode is the later option if it ships Windows wheels).
"""
from __future__ import annotations

import json
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "engine" / "spikes" / "out" / "e0_fp8-20st-960x544_s20261004.png"
OUT_MP4 = REPO / "frontend" / "public" / "spikes" / "e6_clip.mp4"
OUT_JSON = REPO / "orchestrator" / "spikes" / "out" / "e6_backend.json"
W, H, N, FPS = 1024, 576, 121, 24


def make_frames():
    base = Image.open(SRC).convert("RGB") if SRC.exists() else Image.new("RGB", (1920, 1080), (40, 60, 80))
    bw, bh = base.size
    font = ImageFont.load_default()
    for i in range(N):
        # slow push-in + pan: crop window shrinks from 100% to 70% and drifts right
        s = 1.0 - 0.3 * i / (N - 1)
        cw, ch = int(bw * s), int(bh * s)
        x0 = int((bw - cw) * (0.2 + 0.6 * i / (N - 1)))
        y0 = (bh - ch) // 2
        frame = base.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
        d = ImageDraw.Draw(frame)
        # 7-bit frame code: 7 squares of 16 px, white = 1, black = 0, at (16..128, 16)
        for b in range(7):
            v = 255 if (i >> (6 - b)) & 1 else 0
            d.rectangle([16 + b * 16, 16, 16 + b * 16 + 14, 30], fill=(v, v, v))
        d.rectangle([16, 36, 140, 52], fill=(0, 0, 0))
        d.text((18, 38), f"frame {i:03d}", fill=(255, 255, 255), font=font)
        yield np.asarray(frame)


VARIANTS = {  # proxy encodings loom2 controls: GOP length decides random-access decode cost
    OUT_MP4: {"g": "24"},
    OUT_MP4.with_name("e6_clip_g6.mp4"): {"g": "6"},
    OUT_MP4.with_name("e6_clip_intra.mp4"): {"g": "1"},
}


def encode():
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    frames = list(make_frames())
    for path, extra in VARIANTS.items():
        t0 = time.perf_counter()
        with av.open(str(path), "w") as c:
            s = c.add_stream("libx264", rate=FPS)
            s.width, s.height, s.pix_fmt = W, H, "yuv420p"
            s.options = {"crf": "18", "preset": "medium", "movflags": "+faststart", **extra}
            for arr in frames:
                vf = av.VideoFrame.from_ndarray(arr, format="rgb24")
                for pkt in s.encode(vf):
                    c.mux(pkt)
            for pkt in s.encode():
                c.mux(pkt)
        print(f"[e6] encoded {N} frames @ {FPS} fps (gop {extra['g']}) -> {path.name} ({path.stat().st_size/2**20:.1f} MiB) in {time.perf_counter()-t0:.1f}s")


def read_code(arr: np.ndarray) -> int:
    v = 0
    for b in range(7):
        v = (v << 1) | int(arr[23, 16 + b * 16 + 7, 0] > 127)
    return v


def seek_benchmark(path: Path = OUT_MP4, gop: str = "24"):
    times, wrong = [], 0
    with av.open(str(path)) as c:
        st = c.streams.video[0]
        st.thread_type = "AUTO"
        tb = st.time_base
        order = list(range(N))[::7] + list(range(N))[::-11]  # scattered forward + backward seeks
        for i in order:
            t0 = time.perf_counter()
            target = int(Fraction(i, FPS) / tb)
            c.seek(target, stream=st, backward=True, any_frame=False)
            got = None
            for fr in c.decode(st):
                if fr.pts is not None and fr.pts >= target:
                    got = fr
                    break
            dt = (time.perf_counter() - t0) * 1e3
            code = read_code(got.to_ndarray(format="rgb24")) if got is not None else -1
            if code != i:
                wrong += 1
            times.append(dt)
    res = {"clip": path.name, "gop": gop, "frames": N, "fps": FPS, "seeks": len(order), "wrong_frame": wrong,
           "seek_ms_min": round(min(times), 1), "seek_ms_median": round(sorted(times)[len(times) // 2], 1),
           "seek_ms_max": round(max(times), 1), "method": "PyAV seek(backward, keyframe) + decode forward"}
    print("[e6] backend exact-seek:", json.dumps(res))
    return res


if __name__ == "__main__":
    encode()
    results = [seek_benchmark(p, extra["g"]) for p, extra in VARIANTS.items()]
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2))
