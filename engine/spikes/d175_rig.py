"""D175's acceptance on the rig (journal 2026-10-31 21:14): the product path on E47's copy, alone on the GPU — Mira's side view made by
Build's own make (POST …/anim-ref, side "side") and picked (PUT …/anim-ref), then a copy of Final 5's Mira layer run through the route
with nothing swapped: the run chooses the side view itself (side_view, mirrored); frames 10, 32, 60 against Final 5's (the front).
Outputs under engine/spikes/out/d175/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d175_rig.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e54_side as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "d175"


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.fsio import new_id
    from loom2.workspace import Workspace
    if port_busy(e.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(e.PROJECT)
    cat, finals = Catalogue(ws), FinalStore(ws)
    fid = new_id("fin")
    shutil.copytree(finals.folder(e.F5), finals.folder(fid))
    rec = json.loads(finals.path(fid).read_text(encoding="utf-8"))
    rec.update(id=fid, name="D175 side view (the product path)", assembly=None, assembled_at=None, clip_id=None)
    finals.path(fid).write_text(json.dumps(rec, indent=1), encoding="utf-8")
    res: dict = {"final": fid}
    proc, api = e.orchestrator(OUT / "orchestrator.log")
    try:
        t0 = time.time()
        r = api.post(f"/story/profiles/{e.MIRA}/versions/{e.VID}/anim-ref", json={"side": "side", "count": 1})
        print("make:", r.status_code, r.text[:200], flush=True)
        r.raise_for_status()
        j = e.wait(api, r.json()["job_ids"][0])
        side = (j.get("result") or {}).get("asset_ids", [None])[0]
        res["make"] = {"status": j["status"], "seconds": round(time.time() - t0), "asset": side, "prompt": (j.get("recipe") or {}).get("prompt_text", "")[-260:]}
        print("made:", res["make"], flush=True)
        Image.open(cat.abs_path(cat.get(side))).convert("RGB").save(OUT / "side.png")
        p = api.put(f"/story/profiles/{e.MIRA}/versions/{e.VID}/anim-ref", json={"side": "side", "asset_id": side}).json()
        res["picked"] = next(v for v in p["versions"] if v["id"] == e.VID)["anim_ref_side_asset_id"]
        t1 = time.time()
        r = api.post(f"/finals/{fid}/layers/{e.LAYER}/run", json={"seed": 0})
        print("run:", r.status_code, r.text[:300], flush=True)
        r.raise_for_status()
        res["run"] = r.json()
        while True:
            lay = next(x for x in api.get(f"/finals/{fid}").json()["layers"] if x["id"] == e.LAYER)
            if lay["status"] not in ("queued", "running"):
                break
            time.sleep(6)
        res["performed"] = {"status": lay["status"], "seconds": round(time.time() - t1), "error": lay.get("error")}
        print("performed:", res["performed"], flush=True)
        api.post("/engine/stop")
    finally:
        e.stop(proc)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    def frames(f_id: str) -> list[Path]:
        d = finals.folder(f_id) / e.LAYER
        w = sorted((d / "window" / "frames").glob("*.png"))
        return w if w else sorted((d / "frames").glob("*.png"))
    fa, fb = frames(e.F5), frames(fid)
    tw, th = 300, 530
    sheet = Image.new("RGB", (tw * 6, th + 20), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(e.SAMPLE):
        for jx, (name, fr) in enumerate((("front (Final 5)", fa), ("side view (D175)", fb))):
            if k < len(fr):
                im = Image.open(fr[k]).convert("RGB")
                im.thumbnail((tw, th))
                sheet.paste(im, ((i * 2 + jx) * tw, 20))
                d.text(((i * 2 + jx) * tw + 4, 4), f"{name} · frame {k}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=88)
    print(json.dumps({k: v for k, v in res.items() if k != "make"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
