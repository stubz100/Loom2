"""E58 (D180's clean, after E57 and the rig's fifth run, journal 2026-11-01): which Fill takes the ferry out reliably. On the kept ferry's
whole mask (the product's: SAM 3's with its thin parts, grown 14 px), three samples so far of Fill (LanPaint, "image first", λ 5) gave
three outcomes — fog (E57), a ghost ship (the rig, the mast left out), the ferry painted back nearly pixel for pixel (the fifth run). E8b's
other removal recipe was LanPaint "prompt first" (λ 8). Three seeds each, the same seeds across recipes, each on its own document of the
picture, one job at a time on the copy's orchestrator (alone on the GPU): image first with the clean's prompt, prompt first with it, prompt
first with the background-only prompt. Outputs in engine/spikes/out/e58 (`e58_sheet.jpg`: a row a recipe, before then the seeds).

    orchestrator/.venv/Scripts/python.exe engine/spikes/e58_clean_seeds.py
    orchestrator/.venv/Scripts/python.exe engine/spikes/e58_clean_seeds.py --b   # E58b: an instruction naming the thing, against the clean's prompt
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

OUT = r.ROOT / "engine" / "spikes" / "out" / ("e58b" if "--b" in sys.argv else "e58")
PICTURE = "ast_7d42a22b"
OLD = "the same place with the thing gone: the water, the ground and the background continue where it was, the same light"
NEW = "Seamless background: the same ground, water, walls, sky and haze as around it, continued with the same light and grain."
INSTR = "Remove the ferry: only what was behind it remains — the water, the ground and the background continued, the same light."
SEEDS = [3687985960, 44, 55] if "--b" in sys.argv else [11, 22, 33]                 # --b: the rig's fifth run's seed first (the ferry came back)
RECIPES = {"image_first": {"mode": "fill", "prompt_mode": "image_first", "prompt_text": OLD},
           "instruction": {"mode": "fill", "prompt_mode": "image_first", "prompt_text": INSTR}} if "--b" in sys.argv else {
    "image_first": {"mode": "fill", "prompt_mode": "image_first", "prompt_text": OLD},
    "prompt_first": {"mode": "fill", "prompt_mode": "prompt_first", "prompt_text": OLD},
    "prompt_first_bg": {"mode": "fill", "prompt_mode": "prompt_first", "prompt_text": NEW},
}


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(r.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {}
    proc, api = r.orchestrator(OUT / "orchestrator.log")
    try:
        pier = next(p for p in api.get("/story/profiles").json()["items"] if p["name"] == "Harbour pier")
        thing = next(v for v in pier["versions"] if v["id"] == pier["current"])["place_set"]["things"][0]
        mask = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{thing['mask_asset_id']}/file").content)).convert("L")) > 127
        pic = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{PICTURE}/file").content)).convert("RGB"))
        grown = np.asarray(Image.fromarray(np.where(mask, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(29))) > 127
        h, w = grown.shape
        for name, extra in RECIPES.items():
            for seed in SEEDS:
                doc = api.post("/documents", json={"from_asset": PICTURE, "name": f"e58 {name} {seed}"}).json()["id"]
                api.put(f"/documents/{doc}/selection", params={"w": w, "h": h}, content=np.where(grown, 255, 0).astype(np.uint8).tobytes()).raise_for_status()
                t0 = time.time()
                q = api.post(f"/documents/{doc}/ai", json={"recipe": {"kind": "inpaint", "feather": 8, "seeds": [seed], **extra}})
                q.raise_for_status()
                j = r.wait(api, q.json()["jobs"][0]["id"])
                out = np.asarray(Image.open(io.BytesIO(api.post(f"/documents/{doc}/export", json={"format": "png"}).content)).convert("RGB"))
                Image.fromarray(out).save(OUT / f"{name}_{seed}.png")
                res[f"{name}_{seed}"] = {"status": j["status"], "seconds": round(time.time() - t0), "inside_diff": round(float(np.abs(pic[mask].astype(int) - out[mask].astype(int)).mean()), 1)}
                print(name, seed, res[f"{name}_{seed}"], flush=True)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    ys, xs = np.nonzero(grown)
    y0, y1, x0, x1 = max(0, ys.min() - 20), min(h, ys.max() + 20), max(0, xs.min() - 20), min(w, xs.max() + 20)
    gap_v = np.full((y1 - y0, 6, 3), 255, np.uint8)
    rows = []
    for name in RECIPES:
        tiles = [pic[y0:y1, x0:x1]] + [np.asarray(Image.open(OUT / f"{name}_{s}.png"))[y0:y1, x0:x1] for s in SEEDS]
        rows.append(np.concatenate([x for t in tiles for x in (t, gap_v)][:-1], 1))
    gap_h = np.full((6, rows[0].shape[1], 3), 255, np.uint8)
    sheet = np.concatenate([x for row in rows for x in (row, gap_h)][:-1], 0)
    Image.fromarray(sheet).resize((sheet.shape[1] * 3 // 2, sheet.shape[0] * 3 // 2), Image.LANCZOS).save(OUT / "e58_sheet.jpg", quality=90)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
