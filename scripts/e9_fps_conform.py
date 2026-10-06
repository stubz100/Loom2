"""E9 — fps conform spike (D27, 12 §7): what does interpolating a Wan 16 fps clip to 24 fps cost, against a native 24 fps
LTX clip of the same task?

Takes two clips from an open project (the M6 acceptance leaves `wan draft FLF · 03` and `ltx draft · 03`): the Wan
master (81 f @ 16) is interpolated to 121 f @ 24 with rife-ncnn-vulkan (RIFE v4.6, Vulkan on the RX 9070 XT, arbitrary
target count) and, for a second reference, by plain frame duplication (16 → 24 = repeat every second frame). Scores:

  flicker    mean / p95 of the mean absolute luminance change between consecutive frames (lower = smoother; a sawtooth
             from duplication shows up as a high std)
  ghosting   Laplacian variance of interpolated frames relative to their source neighbours (≪ 1 = blurred in-betweens)
  smoothness per-pixel second temporal difference energy (acceleration; lower = more even motion)
  identity   FaceSim is not wired yet (needs ArcFace on the rig) — judged on the frame sheet by eye (04 §6)

Writes engine/spikes/out/e9/: the 24 fps interpolated proxy, a frame sheet around the clip middle (source · RIFE · LTX),
and e9_results.json. Does not touch the engine; run it when the GPU is idle (RIFE uses Vulkan).

    LOOM2_TOKEN=devtoken python scripts/e9_fps_conform.py --port 8766 [--wan <clip_id>] [--ltx <clip_id>] [--model rife-v4.6]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "engine" / "spikes" / "out" / "e9"
RIFE = next(iter(sorted((REPO / "engine" / "tools").glob("rife-ncnn-vulkan-*/rife-ncnn-vulkan.exe"))), None)
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")


def call(base: str, method: str, path: str, body=None):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = r.read()
        return json.loads(payload) if payload else None


def load_frames(d: Path) -> list[np.ndarray]:
    return [np.asarray(Image.open(p).convert("RGB")) for p in sorted(d.glob("*.png"))]


def luma(f: np.ndarray) -> np.ndarray:
    return (0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]).astype(np.float32)


def laplacian_var(g: np.ndarray) -> float:
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def metrics(frames: list[np.ndarray], source_idx: set[int] | None = None) -> dict:
    ls = [luma(f) for f in frames]
    d1 = [float(np.abs(ls[i + 1] - ls[i]).mean()) for i in range(len(ls) - 1)]
    d2 = [float(np.abs(ls[i + 2] - 2 * ls[i + 1] + ls[i]).mean()) for i in range(len(ls) - 2)]
    sharp = [laplacian_var(g) for g in ls]
    out = {"frames": len(frames), "flicker_mean": round(float(np.mean(d1)), 3), "flicker_p95": round(float(np.percentile(d1, 95)), 3), "flicker_std": round(float(np.std(d1)), 3),
           "smoothness_d2_mean": round(float(np.mean(d2)), 3), "sharpness_mean": round(float(np.mean(sharp)), 1)}
    if source_idx:
        src = [s for i, s in enumerate(sharp) if i in source_idx]
        mid = [s for i, s in enumerate(sharp) if i not in source_idx]
        if src and mid:
            out["ghosting_sharpness_ratio"] = round(float(np.mean(mid) / max(1e-6, np.mean(src))), 3)
    return out


def encode(frames: list[np.ndarray], fps: int, out: Path) -> None:
    h, w = frames[0].shape[:2]
    with av.open(str(out), "w", format="mp4", options={"movflags": "+faststart"}) as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w - w % 2, h - h % 2, "yuv420p"
        s.options = {"crf": "18", "preset": "medium", "g": "6"}
        for f in frames:
            for pkt in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(f[: s.height, : s.width]), format="rgb24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)


def sheet(rows: list[tuple[str, list[np.ndarray]]], out: Path) -> None:
    tw = 320
    tiles = [[Image.fromarray(f).resize((tw, int(f.shape[0] * tw / f.shape[1])), Image.LANCZOS) for f in fr] for _, fr in rows]
    th = tiles[0][0].height
    cols = max(len(t) for t in tiles)
    img = Image.new("RGB", (cols * (tw + 4) + 4, len(rows) * (th + 26) + 4), (30, 30, 30))
    d = ImageDraw.Draw(img)
    for r, (label, _) in enumerate(rows):
        y = 4 + r * (th + 26)
        d.text((6, y + 2), label, fill=(240, 240, 240))
        for k, t in enumerate(tiles[r]):
            img.paste(t, (4 + k * (tw + 4), y + 20))
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--wan", default=None, help="clip id of the 16 fps Wan clip (default: newest Wan clip)")
    ap.add_argument("--ltx", default=None, help="clip id of the native 24 fps LTX clip (default: newest LTX clip)")
    ap.add_argument("--model", default="rife-v4.6")
    ap.add_argument("--target-fps", type=int, default=24)
    a = ap.parse_args()
    if RIFE is None:
        print("rife-ncnn-vulkan.exe not found under engine/tools/ (fetch the 20221029 Windows release)"); return 2
    base = f"http://127.0.0.1:{a.port}"
    proj = call(base, "GET", "/project")
    root = Path(proj["path"])
    clips = call(base, "GET", "/clips")["items"]
    wan = next((c for c in clips if (a.wan and c["id"] == a.wan) or (not a.wan and c["model_id"].startswith("wan"))), None)
    ltx = next((c for c in clips if (a.ltx and c["id"] == a.ltx) or (not a.ltx and c["model_id"].startswith("ltx"))), None)
    if not wan:
        print("no Wan clip in the project"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    src_dir = root / wan["master_dir"]
    src = load_frames(src_dir)
    n_target = int(round((len(src) - 1) * a.target_fps / wan["fps"])) + 1       # 81 @ 16 → 121 @ 24 (same 5 s)
    print(f"Wan clip {wan['id']}: {len(src)} f @ {wan['fps']} → {n_target} f @ {a.target_fps} with {a.model} on Vulkan", flush=True)
    with tempfile.TemporaryDirectory(prefix="e9-") as td:
        outd = Path(td) / "out"
        outd.mkdir()
        t0 = time.time()
        cmd = [str(RIFE), "-i", str(src_dir), "-o", str(outd), "-n", str(n_target), "-m", str(RIFE.parent / a.model), "-f", "%06d.png", "-g", "0"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        rife_s = round(time.time() - t0, 1)
        if r.returncode != 0:
            print("rife failed:", r.stderr[-1500:]); return 1
        rife = load_frames(outd)
    print(f"RIFE wrote {len(rife)} frames in {rife_s} s", flush=True)
    # which output frames coincide with source frames (timestamps k/16 that are also on the 24 fps grid: every 2nd source → every 3rd output)
    source_idx = {int(round(i * (len(rife) - 1) / (len(src) - 1))) for i in range(len(src)) if (i * (len(rife) - 1)) % (len(src) - 1) == 0}
    dup = [src[min(len(src) - 1, int(round(k * (len(src) - 1) / (n_target - 1))))] for k in range(n_target)]
    # hybrid: keep the master's own frames where the 24 fps grid hits a source timestamp, RIFE only in between
    hybrid = [src[int(round(k * (len(src) - 1) / (n_target - 1)))] if k in source_idx else rife[k] for k in range(n_target)]
    rife_at_source = [laplacian_var(luma(rife[k])) for k in sorted(source_idx)]
    orig_at_source = [laplacian_var(luma(src[int(round(k * (len(src) - 1) / (n_target - 1)))])) for k in sorted(source_idx)]
    res = {"wan_clip": wan["id"], "ltx_clip": ltx["id"] if ltx else None, "model": a.model, "rife_s": rife_s,
           "rife_softening_at_source_positions": round(float(np.mean(rife_at_source) / max(1e-6, np.mean(orig_at_source))), 3),
           "wan_16fps_native": metrics(src), "wan_24fps_rife": metrics(rife, source_idx), "wan_24fps_rife_hybrid": metrics(hybrid, source_idx), "wan_24fps_duplicate": metrics(dup)}
    ltx_frames = load_frames(root / ltx["master_dir"]) if ltx else []
    if ltx_frames:
        res["ltx_24fps_native"] = metrics(ltx_frames)
    print(f"  RIFE output at source timestamps keeps {res['rife_softening_at_source_positions'] * 100:.0f} % of the master's Laplacian variance")
    for k, v in res.items():
        if isinstance(v, dict):
            print(f"  {k:22s} {v}", flush=True)
    encode(rife, a.target_fps, OUT / f"{wan['id']}_rife24.mp4")
    encode(dup, a.target_fps, OUT / f"{wan['id']}_dup24.mp4")
    encode(hybrid, a.target_fps, OUT / f"{wan['id']}_hybrid24.mp4")
    mid = len(rife) // 2
    rows = [("Wan 16 fps source (frames around the middle)", [src[i] for i in range(max(0, mid * 2 // 3 - 2), min(len(src), mid * 2 // 3 + 3))]),
            (f"RIFE {a.model} → 24 fps", [rife[i] for i in range(max(0, mid - 3), min(len(rife), mid + 4))])]
    if ltx_frames:
        m2 = len(ltx_frames) // 2
        rows.append(("LTX-2.3 native 24 fps", [ltx_frames[i] for i in range(max(0, m2 - 3), min(len(ltx_frames), m2 + 4))]))
    sheet(rows, OUT / f"{wan['id']}_e9_sheet.png")
    (OUT / "e9_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT / (wan['id'] + '_rife24.mp4')}, {OUT / (wan['id'] + '_e9_sheet.png')}, e9_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
