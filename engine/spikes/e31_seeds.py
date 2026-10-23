"""Spike E31, the second half (D124): the Fill under the things and their shadows drew a new crate where the crate stood (E28b saw the
same failure). How often, with which seed, and does SAM 3 — asked at the author's own clicks on the clean plate — catch the thing come back?

The masks E31 kept (engine/spikes/out/e31/mask_*.png), `set_things.shadows_of` again, the union grown 14 px; the Fill at seeds 0–3 on four
documents of bench/sets/room.jpg; on each clean plate SAM 3's point prompt at every thing's clicks, the mask it finds against the thing's
own (IoU: a thing back reads high, the empty floor low). One GPU job at a time; the engine stopped at the end.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e31_seeds.py     (after e31_shadows.py)
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch  # noqa: E402
from loom2 import set_things  # noqa: E402
from loom2.config import AppState  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = REPO / "engine" / "spikes" / "out" / "e31"
OUT = SRC / "seeds"
MODELS = Path("F:/loom2-models")
PORT = 8785
PICTURE = REPO / "bench" / "sets" / "room.jpg"
THINGS = {"Crate": [(325, 490)], "Table": [(790, 455), (722, 540)], "Small block": [(640, 590)], "Big block": [(1070, 480)]}
SEEDS = [0, 1, 2, 3]


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rig.log").unlink(missing_ok=True)
    masks = {n: np.asarray(Image.open(SRC / f"mask_{n.replace(' ', '_')}.png")) > 127 for n in THINGS}
    rgb = np.asarray(Image.open(PICTURE).convert("RGB"))
    H, W = rgb.shape[:2]
    region = np.logical_or.reduce(list(masks.values()) + set_things.shadows_of(rgb, list(masks.values())))
    sel = np.where(set_things._grow(region, set_things.CLEAN_GROW), 255, 0).astype(np.uint8)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {"seeds": {}}
    try:
        h = o.http
        assert h.post("/project", json={"path": str(OUT / "_proj"), "name": "E31 seeds", "size_cap_gb": 10}).status_code == 200
        pic = h.post("/assets/import", json={"paths": [str(PICTURE)]}).json()["items"][0]

        def run(recipe: dict, what: str) -> dict:
            t0 = time.time()
            jid = h.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]["id"]
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=900)
            log(f"{what}: {j['status']} in {time.time() - t0:.1f} s")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return j

        plates = []
        for seed in SEEDS:
            doc = h.post("/documents", json={"from_asset": pic["id"]}).json()["id"]
            assert h.put(f"/documents/{doc}/selection?w={W}&h={H}", content=sel.tobytes(), headers={"Content-Type": "application/octet-stream"}).status_code == 200
            run({"kind": "inpaint", "mode": "fill", "document_id": doc, "prompt_text": set_things.CLEAN_PROMPT, "seeds": [seed]}, f"the clean plate, seed {seed}")
            plate = Image.open(io.BytesIO(h.post(f"/documents/{doc}/export", json={"format": "png"}).content)).convert("RGB")
            plate.save(OUT / f"clean_{seed}.png")
            # is a thing back? SAM 3 at the author's clicks on the clean plate, against the thing's own mask
            cleaned = h.post("/assets/import", json={"paths": [str(OUT / f"clean_{seed}.png")]}).json()["items"][0]
            cdoc = h.post("/documents", json={"from_asset": cleaned["id"]}).json()["id"]
            back = {}
            for name, pts in THINGS.items():
                run({"kind": "segment", "document_id": cdoc, "mode": "points", "points": [{"x": x, "y": y, "label": 1} for x, y in pts], "op": "replace"}, f"  SAM 3 at {name}'s clicks")
                r = h.get(f"/documents/{cdoc}/selection")
                found = np.frombuffer(r.content, np.uint8).reshape(H, W) > 127 if r.status_code == 200 else np.zeros((H, W), bool)
                m = masks[name]
                iou = float((found & m).sum() / max(1, (found | m).sum()))
                back[name] = {"iou": round(iou, 3), "found": round(float(found.mean()), 4)}
            result["seeds"][seed] = back
            log(f"seed {seed}: " + "; ".join(f"{n} IoU {v['iou']} ({v['found'] * 100:.1f} %)" for n, v in back.items()))
            plates.append((seed, plate, back))
        tw = 640
        th = round(tw * H / W)
        sheet = Image.new("RGB", (tw * 2 + 4, (th + 26) * 2 + 4), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        for i, (seed, plate, back) in enumerate(plates):
            x, y = (i % 2) * (tw + 4), (i // 2) * (th + 30)
            sheet.paste(plate.resize((tw, th), Image.LANCZOS), (x, y + 26))
            d.text((x + 6, y + 6), f"seed {seed}: " + ", ".join(f"{n} {v['iou']}" for n, v in back.items()), fill=(230, 230, 230))
        sheet.save(OUT / "seeds.jpg", quality=88)
        h.post("/engine/stop", timeout=60)
        log("the engine stopped; seeds.jpg")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
