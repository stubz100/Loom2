"""SC3d rig: a picture set laid level by its floor on the real engine, and the things made on it standing on that floor.

A private orchestrator, a fresh project, bench/sets/room.jpg imported, a stage, the set made at the lens asked for (`--lens`) — laid level
by the floor fitted to the picture's lowest rows; two things found by points and kept, then *Make the things*: the clean plate, the relief
rebuilt from it (laid level again), a Pixal3D model of each stood on it. Read back: the levelling (the pitch, the camera), the floor's height
on the stage across the room (the clean relief's floor points through the set's transform, by depth), and each prop against the relief's
floor where it stands. Then figures near and deep in the room, a light, a camera beside the picture's, the engine stopped (D97: the
screenshots render with WebGL) and `session.json`; the script waits for `stop` (or `--hold` seconds).

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3d_rig.py [--lens 69.2] [--things "Crate,Small block"] [--hold 900]
  … sc3d_rig.py --restand     the last run's props stood again by the code as it is now (`set_things.stand`, no engine), checked, held
Outputs under engine/spikes/out/sc3d/ (git-ignored): rig.log, result.json, session.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch  # noqa: E402
from loom2 import set_things  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.relief import floor_fit, glb_read, level_of_glb, mesh_arrays, to_stage  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = REPO / "engine" / "spikes" / "out" / "sc3d"
MODELS = Path("F:/loom2-models")
PORT = 8782
THINGS = {"Crate": [(325, 490)], "Table": [(790, 455), (722, 540)], "Small block": [(640, 590)], "Big block": [(1070, 480)]}


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def tf(x: float, y: float, z: float, ry: float = 0.0) -> dict:
    return {"pos": [x, y, z], "rot": [0, ry, 0], "scale": [1, 1, 1]}


def asset_file(asset_id: str) -> Path:
    return next((OUT / "_proj" / "assets").rglob(f"{asset_id}.glb"))


def floor_on_stage(relief: Path, sset: dict) -> tuple[np.ndarray, dict]:
    """The relief's floor points (the fit's inliers among the lowest rows) on the stage, through the set's lift and levelling."""
    doc, binary = glb_read(relief)
    pos, uv, _ = mesh_arrays(doc, binary)
    lift = -(sset["floor_y"] if sset["floor_y"] is not None else -1.0)
    level = level_of_glb(relief, lift) if sset.get("level") else None
    fit = floor_fit(pos, uv)
    ok = np.isfinite(pos).all(axis=1) & (uv[:, 1] > 0.62)
    p = pos[ok]
    on = np.abs(fit["a"] * p[:, 0] + fit["b"] * p[:, 2] + fit["c"] - p[:, 1]) < 0.02 + 0.01 * np.abs(p[:, 2])
    stage = np.array([to_stage(q, lift, level) for q in p[on][:: max(1, int(on.sum()) // 6000)]])
    return stage, {"lift": lift, "level": level and {k: level[k] for k in ("rot", "pos", "pitch_deg", "roll_deg")}, "fit": fit}


def check(doc: dict, sset: dict, n_things: int, result: dict) -> bool:
    """The floor on the stage across the room (the set's relief's floor points through its transform, by depth) and each prop against
    the relief's floor where it stands."""
    pts, info = floor_on_stage(asset_file(sset["asset_id"]), sset)
    bins = {}
    for z0 in (-1.5, -2.5, -3.5, -4.5, -5.5, -6.5):
        sel = (pts[:, 2] <= z0 + 0.5) & (pts[:, 2] > z0 - 0.5)
        if sel.sum() >= 20:
            bins[f"{z0:+.1f}"] = {"n": int(sel.sum()), "y_median": round(float(np.median(pts[sel, 1])), 3), "y_p10_p90": [round(float(v), 3) for v in np.percentile(pts[sel, 1], [10, 90])]}
    log("the floor on the stage by depth (should be ≈ 0): " + "; ".join(f"z {k}: {v['y_median']} m ({v['n']})" for k, v in bins.items()))
    props = []
    for x in [x for x in doc["objects"] if x["kind"] == "mesh"]:
        p = x["transform"]["pos"]
        near = np.hypot(pts[:, 0] - p[0], pts[:, 2] - p[2]) < 0.35
        under = round(float(np.median(pts[near, 1])), 3) if near.sum() >= 5 else None
        props.append({"name": x["name"], "pos": p, "scale": x["transform"]["scale"][0], "floor_there": under, "n": int(near.sum())})
        log(f"  {x['name']} at {[round(v, 3) for v in p]} ×{x['transform']['scale'][0]}: the relief's floor there {under} m ({int(near.sum())} points)")
    ok = len(props) == n_things and all(t["object_id"] for t in sset["things"]) and sset["level"] is not None \
        and all(abs(b["y_median"]) < 0.05 for b in bins.values()) and all(abs(q["pos"][1]) < 0.05 for q in props)
    log(f"{'ok  ' if ok else 'FAIL'} the set laid level ({sset['level']['pitch_deg'] if sset['level'] else '-'}°), the floor ≈ 0 across the room, {len(props)} props on it")
    result.update({"floor_by_depth": bins, "props": props, "set": sset, "relief_info": info, "ok": ok})
    return ok


def hold(o: Orch, st_id: str, sset: dict, cam_id: str, seconds: float) -> None:
    (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st_id, "set_id": sset["id"], "tag": "room",
                                                  "cameras": {"picture": cam_id, "side": "cam_side"}}, indent=1), encoding="utf-8")
    t0 = time.time()
    while time.time() - t0 < seconds and not (OUT / "stop").exists():
        time.sleep(1.0)
    log(f"held {time.time() - t0:.0f} s for the screenshots")


def restand(seconds: float) -> int:
    """The last run's props stood again by `set_things.stand` as the code is now — on the project's files, before its orchestrator
    starts (no engine: the models and reliefs are made) — then checked and held for the screenshots."""
    from loom2.catalogue import Catalogue
    from loom2.stages import StageStore, Transform
    from loom2.workspace import Workspace
    src = OUT / ("session.json" if (OUT / "session.json").exists() else "session.restand.json")
    sess = json.loads(src.read_text(encoding="utf-8"))
    (OUT / "session.restand.json").write_text(json.dumps(sess), encoding="utf-8")     # the ids, kept for the next --restand
    for f in ("stop", "session.json"):
        (OUT / f).unlink(missing_ok=True)
    ws = Workspace.open(OUT / "_proj")
    cat, store = Catalogue(ws), StageStore(ws)
    result: dict = {"restand": {}}

    def fn(st, obj) -> None:
        for t in obj.things:
            if not t.object_id:
                continue
            foot, tfm = set_things.stand(cat, obj, t, t.mesh_asset_id)
            m = next(x for x in st.objects if x.id == t.object_id)
            log(f"  {t.name}: {[round(v, 3) for v in m.transform.pos]} → {tfm['pos']} ×{tfm['scale'][0]} (the footprint at z {foot['z']:.2f}, carried ×{foot.get('carried', 1.0):.3f})")
            result["restand"][t.name] = {"was": m.transform.model_dump(), "now": tfm, "footprint": {k: v for k, v in foot.items() if isinstance(v, (int, float))}}
            m.transform = Transform(**tfm)
    store.edit_picture_set(sess["stage_id"], sess["set_id"], fn)
    o = Orch(OUT / "_state", PORT, project=OUT / "_proj").start(timeout=180)
    try:
        doc = o.http.get(f"/stages/{sess['stage_id']}").json()
        sset = next(x for x in doc["objects"] if x["id"] == sess["set_id"])
        check(doc, sset, len(sset["things"]), result)
        hold(o, sess["stage_id"], sset, sess["cameras"]["picture"], seconds)
    finally:
        (OUT / "result-restand.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=str(REPO / "bench" / "sets" / "room.jpg"))
    ap.add_argument("--lens", type=float, default=69.2, help="the lens asked for before the set's job (D123)")
    ap.add_argument("--things", default="Crate,Small block")
    ap.add_argument("--hold", type=float, default=900.0)
    ap.add_argument("--restand", action="store_true", help="the last run's props stood again by the code as it is now (no engine)")
    a = ap.parse_args()
    if a.restand:
        return restand(a.hold)
    a.image = str(Path(a.image).resolve())
    things = {n: THINGS[n] for n in a.things.split(",")}
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
        assert h.post("/project", json={"path": str(OUT / "_proj"), "name": "SC3d rig", "size_cap_gb": 30}).status_code == 200
        pic = h.post("/assets/import", json={"paths": [a.image]}).json()["items"][0]
        st = h.post("/stages", json={"name": "Picture room"}).json()

        def wait(job_id: str, what: str, timeout: float = 1800) -> dict:
            t0 = time.time()
            j = o.wait_job(job_id, {"done", "failed", "cancelled"}, timeout=timeout)
            log(f"{what}: {j['status']} in {time.time() - t0:.1f} s · {(j.get('log_tail') or [])[-1:]}")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return j

        def the_set() -> tuple[dict, dict]:
            doc = h.get(f"/stages/{st['id']}").json()
            s = next(x for x in doc["objects"] if x["kind"] == "set" and x["preset"] == "image")
            return doc, s

        r = h.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": a.lens}).json()
        t0 = time.time()
        j = wait(r["job_id"], f"the set at {a.lens}°")
        result["set_s"] = round(time.time() - t0, 1)
        doc, sset = the_set()
        cam = next(c for c in doc["cameras"] if c["id"] == sset["plate_camera_id"])
        result["first"] = {"level": sset["level"], "transform": sset["transform"], "camera": {"pos": cam["pos"], "target": cam["target"]}, "floor_y": sset["floor_y"]}
        log(f"laid level: {sset['level']} · the set at {sset['transform']} · its camera {cam['pos']} → {cam['target']}")
        base = f"/stages/{st['id']}/sets/{sset['id']}/things"
        for name, pts in things.items():
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
        wait(cj["result"]["next_job_id"], "the relief rebuilt from it (laid level)")
        result["clean_s"], result["clean_plate"] = round(time.time() - t0, 1), cj["result"]["clean_plate_id"]
        for jid in cj["result"]["next_job_ids"][1:]:
            mj = wait(jid, f"a thing's model {jid}")
            result.setdefault("models", []).append({"job_id": jid, "wall_s": mj.get("wall_s"), "footprint": (mj.get("result") or {}).get("footprint"),
                                                   "transform": (mj.get("result") or {}).get("transform"), "log": (mj.get("log_tail") or [])[-2:]})
        result["make_s"] = round(time.time() - t0, 1)
        doc, sset = the_set()
        cam = next(c for c in doc["cameras"] if c["id"] == sset["plate_camera_id"])
        result["rebuilt"] = {"level": sset["level"], "transform": sset["transform"], "camera": {"pos": cam["pos"], "target": cam["target"]}, "floor_y": sset["floor_y"]}
        log(f"rebuilt, laid level: {sset['level']} · the set at {sset['transform']} · its camera {cam['pos']} → {cam['target']}")
        result["ok"] = check(doc, sset, len(things), result)
        # figures near and deep in the room, a light, a camera beside the picture's
        hgt = cam["pos"][1]
        figs = [{"id": "fig_ada", "kind": "mannequin", "name": "Ada", "preset": "adult", "transform": tf(-0.9, 0.0, -2.4, 30)},
                {"id": "fig_ben", "kind": "mannequin", "name": "Ben", "preset": "adult", "transform": tf(0.9, 0.0, -5.2, -20)}]
        sun = {"id": "light_sun", "kind": "light", "name": "Sun", "transform": tf(-2.6, 4.2, -1.0),
               "light": {"intensity": 2.3, "colour": "#fff4e0", "softness": 0, "shadows": True, "target": [0.2, 0.0, -3.6]}}
        side = {**cam, "id": "cam_side", "name": "From the side", "pos": [3.2, hgt + 0.2, -3.3], "target": [-0.6, 0.35, -3.8]}
        doc = h.put(f"/stages/{st['id']}", json={**doc, "objects": doc["objects"] + figs + [sun], "cameras": doc["cameras"] + [side]}).json()
        h.post("/engine/stop", timeout=60)
        log("the engine stopped (D97: the screenshots render with WebGL next)")
        hold(o, st["id"], sset, cam["id"], a.hold)
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
