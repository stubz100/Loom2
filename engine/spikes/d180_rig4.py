"""D180's clean, again (journal 2026-11-01): the first clean (d180_rig3.py: Fill, LanPaint) took the painted ferry out but SAM 3's mask
had left the mast out, and Klein painted a ferry back into the fog around it. On the same copy, alone on the GPU: the set put back as it
was before that clean (the picture, the things' document, the bake due), the ferry found again with a third click on its mast, kept, the old
thing removed; then A/B on that one mask, one job after the other — A: the first clean's recipe (Fill, its prompt) on a document of the
picture; B: the product path (POST …/set/things/clean: Edit's Remove, Q17 / E8b, a background-only prompt). Outputs in
engine/spikes/out/d180: `results4.json`, `clean_ab.jpg` (before · A · B, the ferry's region enlarged).

    orchestrator/.venv/Scripts/python.exe engine/spikes/d180_rig4.py
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

ORIGINAL = "ast_7d42a22b"                                                       # the pier's set picture as the walkthrough made it
OLD_PROMPT = "the same place with the thing gone: the water, the ground and the background continue where it was, the same light"


def reset() -> None:
    """The copy's pier set as it was before the first clean (the orchestrator is not running)."""
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    store = StoryStore(Workspace(r.PROJECT))
    p = next(x for x in store.profiles() if x.name == "Harbour pier")
    ps = p.version(p.current).place_set.model_copy(deep=True)
    ps.sources[0].asset_id, ps.things_document_id, ps.clean_job_id = ORIGINAL, None, None
    if ps.keep_fills_key:
        ps.baked_key, ps.keep_fills_key = ps.keep_fills_key, None
    for t in ps.things:
        t.cleaned = False
    store.set_place_set(p.id, p.current, ps)


def mast_point(pic: np.ndarray) -> dict:
    """The mast above the cabin: the darkest column near the ferry's centre line, rows 150–165."""
    grey = pic[150:166, 625:649].astype(float).mean(2).mean(0)
    return {"x": 625 + int(np.argmin(grey)), "y": 158, "label": 1}


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
        points = [*r.POINTS, mast_point(pic)]
        res["points"] = points
        t0 = time.time()
        res["find"] = r.wait(api, api.post(f"{base}/find", json={"points": points}).json()["job_id"])["status"]
        p = api.post(base, json={"name": "Ferry", "points": points}).json()
        thing = next(v for v in p["versions"] if v["id"] == vid)["place_set"]["things"][-1]
        for tid in old:
            api.delete(f"{base}/{tid}")
        m = np.asarray(Image.open(io.BytesIO(api.get(f"/assets/{thing['mask_asset_id']}/file").content)).convert("L")) > 127
        ys, xs = np.nonzero(m)
        res["mask"] = {"px": int(m.sum()), "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "seconds": round(time.time() - t0),
                       "size_m": [thing["width_m"], thing["height_m"]]}
        print("mask:", res["mask"], flush=True)
        grown = np.asarray(Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(29))) > 127
        # A: the first clean's recipe on a document of the picture, the same grown mask
        doc = api.post("/documents", json={"from_asset": ORIGINAL, "name": "d180 A"}).json()["id"]
        h, w = grown.shape
        api.put(f"/documents/{doc}/selection", params={"w": w, "h": h}, content=np.where(grown, 255, 0).astype(np.uint8).tobytes()).raise_for_status()
        t1 = time.time()
        ja = api.post(f"/documents/{doc}/ai", json={"recipe": {"kind": "inpaint", "mode": "fill", "prompt_text": OLD_PROMPT, "feather": 8}}).json()["jobs"][0]
        ja = r.wait(api, ja["id"])
        res["A"] = {"status": ja["status"], "seconds": round(time.time() - t1), "error": ja.get("error"), "summary": (ja.get("result") or {}).get("summary")}
        a_png = api.post(f"/documents/{doc}/export", json={"format": "png"}).content
        (r.OUT / "clean_A.png").write_bytes(a_png)
        print("A:", res["A"], flush=True)
        # B: the product path
        t2 = time.time()
        q = api.post(f"{base}/clean")
        q.raise_for_status()
        jb = r.wait(api, q.json()["job_id"])
        res["B"] = {"status": jb["status"], "seconds": round(time.time() - t2), "error": jb.get("error"), "mode": jb["recipe"]["mode"],
                    "model": jb["recipe"].get("model_id"), "coverage": q.json()["coverage"]}
        p = api.get(f"/story/profiles/{pid}").json()
        ps = next(v for v in p["versions"] if v["id"] == vid)["place_set"]
        res["set"] = {"picture": ps["sources"][0]["asset_id"], "baked_key": ps["baked_key"], "keep_fills": bool(ps["keep_fills_key"]),
                      "cleaned": [t["cleaned"] for t in ps["things"]]}
        (r.OUT / "clean_B.png").write_bytes(api.get(f"/assets/{ps['sources'][0]['asset_id']}/file").content)
        print("B:", res["B"], res["set"], flush=True)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    a, b = (np.asarray(Image.open(r.OUT / n).convert("RGB")) for n in ("clean_A.png", "clean_B.png"))
    ys, xs = np.nonzero(grown)
    y0, y1, x0, x1 = max(0, ys.min() - 30), min(h, ys.max() + 30), max(0, xs.min() - 30), min(w, xs.max() + 30)
    gap = np.full((y1 - y0, 6, 3), 255, np.uint8)
    row = np.concatenate([pic[y0:y1, x0:x1], gap, a[y0:y1, x0:x1], gap, b[y0:y1, x0:x1]], 1)
    Image.fromarray(row).resize((row.shape[1] * 2, row.shape[0] * 2), Image.LANCZOS).save(r.OUT / "clean_ab.jpg", quality=90)
    for k, img in (("A", a), ("B", b)):
        res[k]["outside_mean_diff"] = round(float(np.abs(pic[~grown].astype(int) - img[~grown].astype(int)).mean()), 2)
    (r.OUT / "results4.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
