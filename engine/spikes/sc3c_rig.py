"""SC3c (D123) rig: the things of a picture set on the real engine — picked by points, kept, made — then left open for the screenshots.

A private orchestrator, a fresh project, bench/sets/room.jpg imported, a stage, the set made at the lens asked for (`--lens`); each thing
found with SAM 3's point prompts on the set's document (`/things/find`) and kept by name; then *Make the things*: the Fill under them all
(the clean plate), the relief rebuilt from it, a Pixal3D model of each stood on the relief at its footprint. The wall times, the masks'
coverage, the footprints and the props read back. Then a figure and a light, two more cameras, the engine stopped (D97: the browser that
takes the screenshots renders with WebGL) and `session.json`; the script waits for `stop` (or `--hold` seconds).

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3c_rig.py [--lens 69.2] [--hold 900]
Outputs under engine/spikes/out/sc3c/ (git-ignored): rig.log, result.json, session.json.
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

OUT = REPO / "engine" / "spikes" / "out" / "sc3c"
MODELS = Path("F:/loom2-models")
PORT = 8781
THINGS = {"Crate": [(325, 490)], "Table": [(790, 455), (722, 540)], "Small block": [(640, 590)], "Big block": [(1070, 480)]}


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
    ap.add_argument("--lens", type=float, default=69.2, help="the lens asked for before the set's job (D123)")
    ap.add_argument("--hold", type=float, default=900.0)
    a = ap.parse_args()
    a.image = str(Path(a.image).resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("stop", "session.json"):
        (OUT / f).unlink(missing_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {"things": {}}
    try:
        h = o.http
        assert h.post("/project", json={"path": str(OUT / "_proj"), "name": "SC3c rig", "size_cap_gb": 30}).status_code == 200
        pic = h.post("/assets/import", json={"paths": [a.image]}).json()["items"][0]
        st = h.post("/stages", json={"name": "Picture room"}).json()

        def wait(job_id: str, what: str, timeout: float = 1800) -> dict:
            t0 = time.time()
            j = o.wait_job(job_id, {"done", "failed", "cancelled"}, timeout=timeout)
            log(f"{what}: {j['status']} in {time.time() - t0:.1f} s · {(j.get('log_tail') or [])[-1:]}")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return j

        r = h.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": a.lens}).json()
        t0 = time.time()
        wait(r["job_id"], f"the set at {a.lens}°")
        result["set_s"] = round(time.time() - t0, 1)
        doc = h.get(f"/stages/{st['id']}").json()
        sset = next(x for x in doc["objects"] if x["kind"] == "set" and x["preset"] == "image")
        base = f"/stages/{st['id']}/sets/{sset['id']}/things"
        for name, pts in THINGS.items():
            points = [{"x": x, "y": y, "label": 1} for x, y in pts]
            t0 = time.time()
            f = h.post(f"{base}/find", json={"points": points}).json()
            j = wait(f["job_id"], f"find {name}", timeout=600)
            cov = (j.get("result") or {}).get("selection", {}).get("coverage")
            k = h.post(base, json={"name": name, "points": points})
            assert k.status_code == 200, k.text[:300]
            result["things"][name] = {"find_s": round(time.time() - t0, 1), "coverage": cov}
            log(f"  {name}: {cov * 100 if cov is not None else '?'} % of the picture, kept")
        t0 = time.time()
        m = h.post(f"{base}/make").json()
        log(f"make: the clean plate {m['clean_job_id']}, {len(m['models'])} models queued")
        cj = wait(m["clean_job_id"], "the clean plate (Fill)")
        rj = wait(cj["result"]["next_job_id"], "the relief rebuilt from it")
        result["clean_s"], result["clean_plate"] = round(time.time() - t0, 1), cj["result"]["clean_plate_id"]
        for mm in m["models"]:
            mj = wait(mm["job_id"], f"the model of {mm['thing_id']}")
            result.setdefault("models", []).append({"thing_id": mm["thing_id"], "wall_s": mj.get("wall_s"), "footprint": (mj.get("result") or {}).get("footprint"),
                                                   "transform": (mj.get("result") or {}).get("transform"), "log": (mj.get("log_tail") or [])[-2:]})
        result["make_s"] = round(time.time() - t0, 1)
        doc = h.get(f"/stages/{st['id']}").json()
        sset = next(x for x in doc["objects"] if x["id"] == sset["id"])
        meshes = [x for x in doc["objects"] if x["kind"] == "mesh"]
        ok = len(meshes) == len(THINGS) and all(t["object_id"] for t in sset["things"]) and sset["plate_asset_id"] == result["clean_plate"]
        log(f"{'ok  ' if ok else 'FAIL'} {len(meshes)} props on the stage, the set's picture the clean plate: " + "; ".join(f"{x['name']} at {[round(v, 2) for v in x['transform']['pos']]} ×{x['transform']['scale'][0]}" for x in meshes))
        result.update({"props": meshes, "set": sset, "ok": ok})
        # a figure and a light for the look, two cameras beyond the picture's own
        cam = next(c for c in doc["cameras"] if c["id"] == sset["plate_camera_id"])
        hgt = cam["pos"][1]
        fig = {"id": "fig_ada", "kind": "mannequin", "name": "Ada", "preset": "adult", "transform": tf(-0.6, 0.0, -3.4, 30)}
        sun = {"id": "light_sun", "kind": "light", "name": "Sun", "transform": tf(-2.6, 4.2, -1.0),
               "light": {"intensity": 2.3, "colour": "#fff4e0", "softness": 0, "shadows": True, "target": [0.2, 0.0, -3.4]}}
        pan = math.radians(6)
        inside = {**cam, "id": "cam_inside", "name": "Inside the budget", "pos": [0.25, hgt, 0.0], "target": [0.25 + math.sin(pan), hgt, -math.cos(pan)]}
        beyond = {**cam, "id": "cam_beyond", "name": "Beyond the budget", "pos": [1.6, hgt + 0.3, -0.6], "target": [-0.4, hgt - 0.4, -4.0]}
        doc = h.put(f"/stages/{st['id']}", json={**doc, "objects": doc["objects"] + [fig, sun], "cameras": doc["cameras"] + [inside, beyond]}).json()
        h.post("/engine/stop", timeout=60)
        log("the engine stopped (D97: the screenshots render with WebGL next)")
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st["id"], "set_id": sset["id"], "tag": "room",
                                                      "cameras": {"picture": cam["id"], "inside": "cam_inside", "beyond": "cam_beyond"}}, indent=1), encoding="utf-8")
        t0 = time.time()
        while time.time() - t0 < a.hold and not (OUT / "stop").exists():
            time.sleep(1.0)
        log(f"held {time.time() - t0:.0f} s for the screenshots")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
