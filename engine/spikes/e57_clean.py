"""E57 (D180's clean, journal 2026-11-01): what takes the Last Ferry's ferry out of the pier's set picture without painting a vessel back.

The rig (d180_rig3/4) cleaned under SAM 3's ferry mask, which leaves out the mast (2–3 px wide at 960 px; a click on it adds nothing), and
both Fill (LanPaint) and Remove (Klein ICM, the hole mid grey, Q17 / E8b) painted a vessel around the mast that stayed. Here the mask is
made whole by hand — SAM 3's plus the mast and its yard (pixels 25+ darker than their 9 px median, in the ferry's column above it) — grown
as the clean grows it (14 px), and four recipes run on it, each on its own document of the picture, one job at a time on the copy's
orchestrator (alone on the GPU): Fill with the first clean's prompt, Remove with the background-only prompt, Remove pre-filled by
content-aware fill (D62), and Quick remove (content-aware fill alone, CPU). Outputs in engine/spikes/out/e57.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e57_clean.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d180_rig as r  # noqa: E402

OUT = r.ROOT / "engine" / "spikes" / "out" / "e57"
PICTURE = "ast_7d42a22b"
OLD_PROMPT = "the same place with the thing gone: the water, the ground and the background continue where it was, the same light"
NEW_PROMPT = "Seamless background: the same ground, water, walls, sky and haze as around it, continued with the same light and grain."
RECIPES = {
    "fill": {"mode": "fill", "prompt_text": OLD_PROMPT},
    "remove": {"mode": "remove", "prompt_text": NEW_PROMPT},
    "remove_prefill": {"mode": "remove", "prompt_text": NEW_PROMPT, "prefill": True},
    "quick_remove": {"mode": "quick_remove", "prompt_text": ""},
}


def whole_mask(pic: np.ndarray, sam: np.ndarray) -> np.ndarray:
    grey = pic.astype(float).mean(2)
    med = np.asarray(Image.fromarray(grey.astype(np.uint8)).filter(ImageFilter.MedianFilter(9))).astype(float)
    ys, xs = np.nonzero(sam)
    thin = med - grey > 25
    band = np.zeros_like(thin)
    band[max(0, ys.min() - 60):ys.min() + 8, xs.min():xs.max() + 1] = True          # above the mask, within its width
    return sam | (thin & band)


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(r.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {}
    proc, api = r.orchestrator(OUT / "orchestrator.log")
    try:
        pic = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{PICTURE}/file").content)).convert("RGB"))
        sam = np.asarray(Image.open(r.OUT / "mask3.png").convert("L")) > 127
        whole = whole_mask(pic, sam)
        grown = np.asarray(Image.fromarray(np.where(whole, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(29))) > 127
        res["mask"] = {"sam_px": int(sam.sum()), "whole_px": int(whole.sum()), "grown_share": round(float(grown.mean()), 4)}
        Image.fromarray(np.where(grown, 255, 0).astype(np.uint8)).save(OUT / "mask_grown.png")
        h, w = grown.shape
        for name, extra in RECIPES.items():
            doc = api.post("/documents", json={"from_asset": PICTURE, "name": f"e57 {name}"}).json()["id"]
            api.put(f"/documents/{doc}/selection", params={"w": w, "h": h}, content=np.where(grown, 255, 0).astype(np.uint8).tobytes()).raise_for_status()
            t0 = time.time()
            q = api.post(f"/documents/{doc}/ai", json={"recipe": {"kind": "inpaint", "feather": 8, **extra}})
            q.raise_for_status()
            j = r.wait(api, q.json()["jobs"][0]["id"])
            res[name] = {"status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"), "model": j["recipe"].get("model_id")}
            (OUT / f"{name}.png").write_bytes(api.post(f"/documents/{doc}/export", json={"format": "png"}).content)
            print(name, res[name], flush=True)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    ys, xs = np.nonzero(grown)
    y0, y1, x0, x1 = max(0, ys.min() - 30), min(h, ys.max() + 30), max(0, xs.min() - 30), min(w, xs.max() + 30)
    tiles = [pic[y0:y1, x0:x1]] + [np.asarray(Image.open(OUT / f"{n}.png").convert("RGB"))[y0:y1, x0:x1] for n in RECIPES]
    gap = np.full((y1 - y0, 6, 3), 255, np.uint8)
    row = np.concatenate([x for t in tiles for x in (t, gap)][:-1], 1)
    Image.fromarray(row).resize((row.shape[1] * 2, row.shape[0] * 2), Image.LANCZOS).save(OUT / "e57_sheet.jpg", quality=90)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
