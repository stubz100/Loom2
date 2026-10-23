"""SC3b (D120) rig: a set from an image rebuilt with a corrected lens, on the real engine, then left open for the screenshots.

A private orchestrator, a fresh project, bench/sets/room.jpg imported, a stage, POST /stages/{id}/image-set (MoGe's own lens), then the
same set rebuilt in place at `--lens2` (`replace_set_id`): the wall times, the set and its camera read back. Then a figure and a light are
put on the stage (the light's shadow falls on the relief), two more cameras (inside E30's budget and well beyond it), the engine is
stopped (D97: the browser that takes the screenshots renders with WebGL) and `session.json` says where the orchestrator is; the script
waits for `stop` in the output folder (or `--hold` seconds) and shuts the orchestrator down.

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3b_rig.py [--image bench/sets/room.jpg] [--lens2 75] [--hold 600]
Outputs under engine/spikes/out/sc3b/ (git-ignored): rig.log, result.json, session.json.
"""
from __future__ import annotations

import argparse
import json
import math
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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = REPO / "engine" / "spikes" / "out" / "sc3b"
MODELS = Path("F:/loom2-models")
PORT = 8779


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def tf(x: float, y: float, z: float, ry: float = 0.0) -> dict:
    return {"pos": [x, y, z], "rot": [0, ry, 0], "scale": [1, 1, 1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=str(REPO / "bench" / "sets" / "room.jpg"))
    ap.add_argument("--lens2", type=float, default=75.0, help="the corrected lens the rebuild uses")
    ap.add_argument("--hold", type=float, default=600.0, help="seconds to keep the orchestrator up for the screenshots")
    ap.add_argument("--light", default="2.0,4.0,-6.0", help="the light's position (behind the figure: its shadow falls forward on the floor)")
    ap.add_argument("--tag", default="room", help="the screenshots' name part")
    a = ap.parse_args()
    a.image = str(Path(a.image).resolve())                                   # the orchestrator resolves paths from its own folder
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("stop", "session.json"):
        (OUT / f).unlink(missing_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {}
    try:
        h = o.http
        r = h.post("/project", json={"path": str(OUT / "_proj"), "name": "SC3b rig", "size_cap_gb": 20})
        assert r.status_code == 200, r.text[:300]
        pic = h.post("/assets/import", json={"paths": [a.image]}).json()["items"][0]
        st = h.post("/stages", json={"name": "Picture room"}).json()
        log(f"picture {pic['id']} {pic['w']}×{pic['h']} · stage {st['id']}")

        def run(body: dict, what: str) -> dict:
            t0 = time.time()
            r = h.post(f"/stages/{st['id']}/image-set", json=body, timeout=60)
            assert r.status_code == 200, r.text[:300]
            j = o.wait_job(r.json()["job_id"], {"done", "failed", "cancelled"}, timeout=900)
            wall = time.time() - t0
            log(f"{what}: job {j['id']} {j['status']} in {wall:.1f} s · {(j.get('log_tail') or [])[-2:]}")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return {"wall_s": round(wall, 1), "relief": (j.get("result") or {}).get("relief"), "set_id": (j.get("result") or {}).get("set_id")}

        first = run({"asset_id": pic["id"]}, "the set (MoGe's lens)")
        doc = h.get(f"/stages/{st['id']}").json()
        obj = next(x for x in doc["objects"] if x["kind"] == "set" and x["preset"] == "image")
        cam = next(c for c in doc["cameras"] if c["id"] == obj["plate_camera_id"])
        log(f"  {obj['name']} lens {obj['lens_deg']}° floor {obj['floor_y']} · {cam['name']} {cam['focal_mm']} mm at {cam['pos']}")
        second = run({"asset_id": pic["id"], "lens_deg": a.lens2, "replace_set_id": obj["id"]}, f"the rebuild at {a.lens2}°")
        doc = h.get(f"/stages/{st['id']}").json()
        sets = [x for x in doc["objects"] if x["kind"] == "set" and x["preset"] == "image"]
        obj2 = sets[0]
        cam2 = next(c for c in doc["cameras"] if c["id"] == obj2["plate_camera_id"])
        ok = len(sets) == 1 and obj2["id"] == obj["id"] and obj2["asset_id"] != obj["asset_id"] and abs(obj2["lens_deg"] - a.lens2) < 0.6 and cam2["id"] == cam["id"]
        log(f"  {'ok  ' if ok else 'FAIL'} one set, the same id, a new relief: lens {obj2['lens_deg']}° floor {obj2['floor_y']} · camera {cam2['focal_mm']} mm at {cam2['pos']}")
        result = {"first": first, "rebuild": second, "set": obj2, "camera": cam2, "same_set": ok}

        # a figure on the floor in front of the picture camera, a light whose shadow falls on the relief, two more cameras
        hgt = cam2["pos"][1]
        fig = {"id": "fig_ada", "kind": "mannequin", "name": "Ada", "preset": "adult", "transform": tf(0.4, 0.0, -3.0, 20)}
        lx, ly, lz = (float(v) for v in a.light.split(","))
        sun = {"id": "light_sun", "kind": "light", "name": "Sun", "transform": tf(lx, ly, lz),
               "light": {"intensity": 2.3, "colour": "#fff4e0", "softness": 0, "shadows": True, "target": [0.4, 0.0, -3.0]}}
        pan = math.radians(4)
        inside = {**cam2, "id": "cam_inside", "name": "Inside the budget", "pos": [0.2, hgt, 0.0], "target": [0.2 + math.sin(pan), hgt, -math.cos(pan)]}
        beyond = {**cam2, "id": "cam_beyond", "name": "Beyond the budget", "pos": [1.4, hgt + 0.4, 0.8], "target": [-0.6, hgt - 0.2, -3.5]}
        doc = h.put(f"/stages/{st['id']}", json={**doc, "objects": doc["objects"] + [fig, sun], "cameras": doc["cameras"] + [inside, beyond]}).json()
        log(f"  the figure, the light and two cameras added (revision {doc['revision']})")
        h.post("/engine/stop", timeout=60)
        log("  the engine stopped (D97: the screenshots render with WebGL next)")
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st["id"], "set_id": obj2["id"],
                                                      "cameras": {"picture": cam2["id"], "inside": "cam_inside", "beyond": "cam_beyond"}, "tag": a.tag}, indent=1), encoding="utf-8")
        t0 = time.time()
        while time.time() - t0 < a.hold and not (OUT / "stop").exists():
            time.sleep(1.0)
        log(f"  held {time.time() - t0:.0f} s for the screenshots")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
