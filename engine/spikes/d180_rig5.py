"""D180's clean accepted on the rig after E57 (journal 2026-11-01): the kept ferry carries its thin parts (the mast SAM 3 leaves out) and the
clean is a Fill again. On the copy, alone on the GPU: the set put back as before the first clean (d180_rig4.reset), the ferry found with
the walkthrough's two clicks (none on the mast), kept, the earlier things removed, the picture cleaned through POST …/set/things/clean.
Build's re-bake and Clay are the app's (scratchpad step d180clean.cjs). Outputs in engine/spikes/out/d180: `results5.json`,
`clean5_pair.jpg` (before · after, the ferry's region enlarged), `mask5_over.jpg`.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d180_rig5.py
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
from d180_rig4 import ORIGINAL, reset  # noqa: E402


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(r.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    reset()
    res: dict = {}
    proc, api = r.orchestrator(r.OUT / "orchestrator.log")
    try:
        pier = next(p for p in api.get("/story/profiles").json()["items"] if p["name"] == "Harbour pier")
        pid, vid = pier["id"], pier["current"]
        base = f"/story/profiles/{pid}/versions/{vid}/set/things"
        ps = next(v for v in pier["versions"] if v["id"] == vid)["place_set"]
        assert ps["sources"][0]["asset_id"] == ORIGINAL and not ps["keep_fills_key"]
        old = [t["id"] for t in ps["things"]]
        pic = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{ORIGINAL}/file").content)).convert("RGB"))
        res["find"] = r.wait(api, api.post(f"{base}/find", json={"points": r.POINTS}).json()["job_id"])["status"]
        p = api.post(base, json={"name": "Ferry", "points": r.POINTS}).json()
        thing = next(v for v in p["versions"] if v["id"] == vid)["place_set"]["things"][-1]
        for tid in old:
            api.delete(f"{base}/{tid}")
        m = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{thing['mask_asset_id']}/file").content)).convert("L")) > 127
        ys, xs = np.nonzero(m)
        res["mask"] = {"px": int(m.sum()), "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "size_m": [thing["width_m"], thing["height_m"]],
                       "mast": bool(m[150:166, 634:639].any())}
        print("kept:", res["mask"], flush=True)
        t0 = time.time()
        q = api.post(f"{base}/clean")
        q.raise_for_status()
        j = r.wait(api, q.json()["job_id"])
        res["clean"] = {"status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"), "mode": j["recipe"]["mode"],
                        "model": j["recipe"].get("model_id"), "coverage": q.json()["coverage"]}
        p = api.get(f"/story/profiles/{pid}").json()
        ps = next(v for v in p["versions"] if v["id"] == vid)["place_set"]
        res["set"] = {"picture": ps["sources"][0]["asset_id"], "baked_key": ps["baked_key"], "keep_fills": bool(ps["keep_fills_key"]),
                      "things": [(t["name"], t["cleaned"]) for t in ps["things"]]}
        after = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{ps['sources'][0]['asset_id']}/file").content)).convert("RGB"))
        print("clean:", res["clean"], res["set"], flush=True)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    grown = np.asarray(Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(29))) > 127
    res["outside_mean_diff"] = round(float(np.abs(pic[~grown].astype(int) - after[~grown].astype(int)).mean()), 2)
    h, w = m.shape
    gy, gx = np.nonzero(grown)
    y0, y1, x0, x1 = max(0, gy.min() - 30), min(h, gy.max() + 30), max(0, gx.min() - 30), min(w, gx.max() + 30)
    pair = np.concatenate([pic[y0:y1, x0:x1], np.full((y1 - y0, 6, 3), 255, np.uint8), after[y0:y1, x0:x1]], 1)
    Image.fromarray(pair).resize((pair.shape[1] * 2, pair.shape[0] * 2), Image.LANCZOS).save(r.OUT / "clean5_pair.jpg", quality=90)
    v = pic.astype(float).copy()
    v[m] = v[m] * 0.5 + np.array([240, 166, 58]) * 0.5
    Image.fromarray(v[y0:y1, x0:x1].astype(np.uint8)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS).save(r.OUT / "mask5_over.jpg", quality=90)
    (r.OUT / "results5.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
