"""The unsharp pass after RIFE (D27's follow-up, E9's note of 2026-10-07; the backlog's item 2): does a mild unsharp mask give a conformed
clip back the sharpness RIFE takes (E9: the 24 fps output keeps ≈ 80 % of the master's Laplacian variance, uniformly) without putting
in what was not there?

A Wan clip master (81 frames at 16 fps, the M6 acceptance's clp_33774c9c by default — E9's own) is conformed to 24 fps with the app's own
`final_assembly.conform_24` (rife-ncnn-vulkan, RIFE v4.6; the card's Vulkan — nothing else on the GPU), then every frame is given an
unsharp mask at each radius / amount tried. For each: the Laplacian variance of the luma against the master's (the sharpness ratio, 1.0 = the
master's), the mean absolute error of the frames at the master's own timestamps against the master (lower = closer to what was rendered —
a mask that only invents detail raises it), the flicker of consecutive frames (E9's measure; an unsharp must not bring the sawtooth
back), and the overshoot (the share of pixels pushed past the master's local range by more than 8 levels: halos).

    orchestrator/.venv/Scripts/python.exe scripts/unsharp_rig.py [--master DIR] [--radii 1,1.5] [--amounts 30,50,80]

Results: engine/spikes/out/unsharp/results.json and a sheet (the master · RIFE · each mask) of a crop around the middle frame.
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from loom2.final_assembly import conform_24, rife_binary  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "unsharp"
MASTER = Path("F:/loom2-projects/m6-acceptance/clips/clp_33774c9c/master")


def luma(a: np.ndarray) -> np.ndarray:
    return (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.float32)


def laplacian_var(g: np.ndarray) -> float:
    k = -4 * g
    k[1:] += g[:-1]; k[:-1] += g[1:]; k[:, 1:] += g[:, :-1]; k[:, :-1] += g[:, 1:]
    return float(k[1:-1, 1:-1].var())


def flicker(frames: list[np.ndarray]) -> dict:
    d = [float(np.abs(luma(a) - luma(b)).mean()) for a, b in zip(frames, frames[1:])]
    return {"mean": round(float(np.mean(d)), 3), "p95": round(float(np.percentile(d, 95)), 3), "std": round(float(np.std(d)), 3)}


def overshoot(sharp: np.ndarray, ref: np.ndarray) -> float:
    """The share of pixels the mask pushed past the reference's 3×3 range by more than 8 levels (halos)."""
    g, r = luma(sharp), luma(ref)
    lo, hi = r.copy(), r.copy()
    for dy, dx in itertools.product((-1, 0, 1), repeat=2):
        s = np.roll(np.roll(r, dy, 0), dx, 1)
        lo, hi = np.minimum(lo, s), np.maximum(hi, s)
    return float(((g > hi + 8) | (g < lo - 8))[2:-2, 2:-2].mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", default=str(MASTER))
    ap.add_argument("--radii", default="1,1.5")
    ap.add_argument("--amounts", default="30,50,80", help="percent, as PIL's UnsharpMask takes it")
    a = ap.parse_args()
    master = Path(a.master)
    srcs = sorted(master.glob("*.png"))
    if len(srcs) < 9:
        raise SystemExit(f"no master frames at {master}")
    if rife_binary() is None:
        raise SystemExit("rife-ncnn-vulkan is not installed under engine/tools")
    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"
    shutil.rmtree(work, ignore_errors=True)
    src_dir, dst_dir = work / "in", work / "rife24"
    src_dir.mkdir(parents=True)
    for i, p in enumerate(srcs):
        Image.open(p).convert("RGB").save(src_dir / f"{i:06d}.png")
    t0 = time.time()
    conformed = conform_24(src_dir, dst_dir, len(srcs))
    rife_s = round(time.time() - t0, 1)
    if not conformed:
        raise SystemExit("conform_24 gave nothing")
    master_frames = [np.asarray(Image.open(p).convert("RGB")) for p in srcs]
    rife_frames = [np.asarray(Image.open(p).convert("RGB")) for p in conformed]
    n16, n24 = len(master_frames), len(rife_frames)
    # the master's own timestamps in the 24 fps sequence (E9's mapping: the ends meet, the rest by proportion)
    at = {k: int(round(k * (n16 - 1) / (n24 - 1))) for k in range(n24)}
    source_pos = {k for k in range(n24) if abs(k * (n16 - 1) / (n24 - 1) - at[k]) < 1e-6}
    master_sharp = float(np.mean([laplacian_var(luma(f)) for f in master_frames]))

    def score(frames: list[np.ndarray]) -> dict:
        sharp = [laplacian_var(luma(f)) for f in frames]
        mae = [float(np.abs(frames[k].astype(np.float32) - master_frames[at[k]].astype(np.float32)).mean()) for k in sorted(source_pos)]
        over = [overshoot(frames[k], master_frames[at[k]]) for k in sorted(source_pos)[::6]]
        return {"sharpness_ratio": round(float(np.mean(sharp)) / master_sharp, 3), "sharpness_ratio_at_source": round(float(np.mean([sharp[k] for k in source_pos])) / master_sharp, 3),
                "sharpness_ratio_between": round(float(np.mean([sharp[k] for k in range(n24) if k not in source_pos])) / master_sharp, 3),
                "mae_at_source": round(float(np.mean(mae)), 3), "overshoot_share": round(float(np.mean(over)), 5), "flicker": flicker(frames)}

    results: dict = {"master": str(master), "frames": [n16, n24], "rife_s": rife_s, "master_sharpness": round(master_sharp, 1), "master_flicker": flicker(master_frames),
                     "rife": score(rife_frames), "masks": {}}
    print(f"RIFE {n16} → {n24} in {rife_s} s · master Laplacian {master_sharp:.0f} · RIFE ratio {results['rife']['sharpness_ratio']} (at source {results['rife']['sharpness_ratio_at_source']}, "
          f"between {results['rife']['sharpness_ratio_between']}) · MAE {results['rife']['mae_at_source']} · flicker {results['rife']['flicker']}", flush=True)
    radii = [float(x) for x in a.radii.split(",")]
    amounts = [int(x) for x in a.amounts.split(",")]
    best = None
    for r, pct in itertools.product(radii, amounts):
        f = ImageFilter.UnsharpMask(radius=r, percent=pct, threshold=2)
        frames = [np.asarray(Image.fromarray(x).filter(f)) for x in rife_frames]
        s = score(frames)
        results["masks"][f"r{r}_a{pct}"] = {"radius": r, "percent": pct, **s}
        print(f"  unsharp r {r} · {pct} %: ratio {s['sharpness_ratio']} (source {s['sharpness_ratio_at_source']}, between {s['sharpness_ratio_between']}) · MAE {s['mae_at_source']} · "
              f"overshoot {s['overshoot_share'] * 100:.2f} % · flicker {s['flicker']}", flush=True)
        # the pick: the lowest error against the master among the masks that do not pass it in sharpness
        if s["sharpness_ratio_at_source"] <= 1.05 and (best is None or s["mae_at_source"] < results["masks"][best]["mae_at_source"]):
            best = f"r{r}_a{pct}"
    results["pick"] = best
    results["pick_reason"] = "the lowest MAE against the master among the masks whose sharpness at the master's timestamps stays within 5 % of the master's"
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    # the sheet: a crop of the middle frame — the master, RIFE, each mask
    mid24 = n24 // 2
    mid16 = at[mid24]
    h, w = master_frames[0].shape[:2]
    box = (w // 2 - 160, h // 2 - 120, w // 2 + 160, h // 2 + 120)
    tiles = [("master", master_frames[mid16]), ("RIFE", rife_frames[mid24])]
    for key, s in results["masks"].items():
        f = ImageFilter.UnsharpMask(radius=s["radius"], percent=s["percent"], threshold=2)
        tiles.append((key + (" ★" if key == best else ""), np.asarray(Image.fromarray(rife_frames[mid24]).filter(f))))
    from PIL import ImageDraw
    cw, ch = box[2] - box[0], box[3] - box[1]
    sheet = Image.new("RGB", (len(tiles) * (cw + 8), ch + 18), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (label, fr) in enumerate(tiles):
        sheet.paste(Image.fromarray(fr).crop(box), (i * (cw + 8), 18))
        d.text((i * (cw + 8) + 3, 3), label, fill=(230, 230, 230))
    sheet.save(OUT / "sheet.png")
    print(f"pick: {best} → {OUT / 'results.json'}, {OUT / 'sheet.png'}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
