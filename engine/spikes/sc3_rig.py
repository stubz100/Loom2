"""SC3 (D120) rig: a set from an image through the app on the real engine — a private orchestrator, a fresh project, bench/sets/room.jpg
imported, a stage, POST /stages/{id}/image-set, the job (MoGe on the engine), then the stage read back: the relief asset, the locked set,
the picture's camera (active, the lens, the height), and the relief's own numbers from the finisher. One GPU job (D97): the engine must not
be running before this starts (the orchestrator starts it for the job).

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3_rig.py [--image bench/sets/room.jpg] [--relief cut|sheet] [--lens 0]
Outputs under engine/spikes/out/sc3/ (git-ignored): rig.log, result.json, the relief GLB copied beside them.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch  # noqa: E402
from loom2.config import AppState  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")        # the log carries → and °; the console is cp1252

OUT = REPO / "engine" / "spikes" / "out" / "sc3"
MODELS = Path("F:/loom2-models")
PORT = 8779


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=str(REPO / "bench" / "sets" / "room.jpg"))
    ap.add_argument("--relief", default="cut", choices=["cut", "sheet"])
    ap.add_argument("--lens", type=float, default=0.0, help="the picture's horizontal field of view; 0 = MoGe's own reading")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {}
    try:
        h = o.http
        r = h.post("/project", json={"path": str(OUT / "_proj"), "name": "SC3 rig", "size_cap_gb": 20})
        assert r.status_code == 200, r.text[:300]
        pic = h.post("/assets/import", json={"paths": [a.image]}).json()["items"][0]
        st = h.post("/stages", json={"name": "Picture room"}).json()
        log(f"picture {pic['id']} {pic['w']}×{pic['h']} · stage {st['id']} with {len(st['cameras'])} camera")
        t0 = time.time()
        r = h.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "relief": a.relief, "lens_deg": a.lens or None}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        j = o.wait_job(r.json()["job_id"], {"done", "failed", "cancelled"}, timeout=900)
        wall = time.time() - t0
        log(f"job {j['id']} {j['status']} in {wall:.0f} s (the engine started for it): {(j.get('log_tail') or [])[-3:]}")
        result = {"status": j["status"], "wall_s": round(wall), "error": j.get("error"), "relief": (j.get("result") or {}).get("relief"), "log": (j.get("log_tail") or [])[-6:]}
        if j["status"] != "done":
            raise SystemExit(1)
        st2 = h.get(f"/stages/{st['id']}").json()
        obj = next(x for x in st2["objects"] if x["kind"] == "set" and x["preset"] == "image")
        cam = next(c for c in st2["cameras"] if c["id"] == obj["plate_camera_id"])
        asset = h.get(f"/assets/{obj['asset_id']}").json()
        log(f"the set: {obj['name']} (locked {obj['locked']}) lens {obj['lens_deg']}° floor {obj['floor_y']} m · camera {cam['name']} at {cam['pos']} → {cam['target']}, {cam['focal_mm']} mm, "
            f"active {st2['active_camera'] == cam['id']} · relief asset {asset['id']} {asset['kind']} {(asset.get('bytes') or 0) / 2**20:.1f} MiB, lineage {asset.get('lineage_kind')} ← {asset.get('parents')}, "
            f"thumb {asset.get('thumb_status')}")
        result.update({"set": obj, "camera": cam, "asset": {k: asset.get(k) for k in ("id", "kind", "bytes", "lineage_kind", "parents", "thumb_status", "params")}, "active": st2["active_camera"] == cam["id"]})
        src = OUT / "_proj" / asset["path"]
        if src.is_file():
            shutil.copyfile(src, OUT / f"relief_{a.relief}.glb")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
