"""D180's clean on the rig: the Last Ferry copy's pier set picture cleaned under its kept ferry through the product path, alone on the GPU
(POST …/set/things/clean, the Fill on the set picture's document). The faces are baked from the cleaned picture by Build itself (the app's
look, scratchpad step d180clean.cjs). Outputs beside the first runs' (engine/spikes/out/d180: `results3.json`, the picture before and after,
the ferry's region of each enlarged).

    orchestrator/.venv/Scripts/python.exe engine/spikes/d180_rig3.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d180_rig as r  # noqa: E402


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(r.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    res: dict = {}
    proc, api = r.orchestrator(r.OUT / "orchestrator.log")
    try:
        pier = next(p for p in api.get("/story/profiles").json()["items"] if p["name"] == "Harbour pier")
        pid, vid = pier["id"], pier["current"]
        ps = next(v for v in pier["versions"] if v["id"] == vid)["place_set"]
        before = ps["sources"][0]["asset_id"]
        t0 = time.time()
        q = api.post(f"/story/profiles/{pid}/versions/{vid}/set/things/clean")
        print("clean:", q.status_code, q.text[:200], flush=True)
        q.raise_for_status()
        j = r.wait(api, q.json()["job_id"])
        res["clean"] = {"status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"), "coverage": q.json()["coverage"],
                        "things": q.json()["things"], "model": j["recipe"].get("model_id")}
        p = api.get(f"/story/profiles/{pid}").json()
        ps = next(v for v in p["versions"] if v["id"] == vid)["place_set"]
        res["picture"] = {"before": before, "after": ps["sources"][0]["asset_id"]}
        res["set"] = {"baked_key": ps["baked_key"], "keep_fills": bool(ps["keep_fills_key"]), "cleaned": [t["cleaned"] for t in ps["things"]]}
        print(json.dumps(res), flush=True)
        for key, name in ((before, "pic_before.png"), (ps["sources"][0]["asset_id"], "pic_after.png")):
            (r.OUT / name).write_bytes(api.get(f"/assets/{key}/file").content)
        mask = ps["things"][0]["mask_asset_id"]
        (r.OUT / "mask3.png").write_bytes(api.get(f"/assets/{mask}/file").content)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    a, b = (np.asarray(Image.open(r.OUT / n).convert("RGB")) for n in ("pic_before.png", "pic_after.png"))
    m = np.asarray(Image.open(r.OUT / "mask3.png").convert("L")) > 127
    ys, xs = np.nonzero(m)
    pad = 40
    y0, y1, x0, x1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad), max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad)
    pair = np.concatenate([a[y0:y1, x0:x1], np.full((y1 - y0, 6, 3), 255, np.uint8), b[y0:y1, x0:x1]], 1)
    Image.fromarray(pair).resize((pair.shape[1] * 3, pair.shape[0] * 3), Image.LANCZOS).save(r.OUT / "clean_pair.jpg", quality=90)
    grown = np.asarray(Image.open(r.OUT / "mask3.png").convert("L").filter(ImageFilter.MaxFilter(2 * 14 + 1 + 16))) > 127   # the clean's reach and its feather
    res["unchanged_outside"] = round(float(np.abs(a[~grown].astype(int) - b[~grown].astype(int)).mean()), 2)   # the picture away from the ferry kept
    res["changed_inside"] = round(float(np.abs(a[m].astype(int) - b[m].astype(int)).mean()), 1)
    (r.OUT / "results3.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
