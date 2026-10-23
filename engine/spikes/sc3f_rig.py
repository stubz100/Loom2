"""SC3f rig: the made things follow their set when it is rebuilt at a corrected lens; a prop moved by hand stays; the set laid level both
ways.

SC3d's project copied (bench/sets/room.jpg laid level, its clean plate, the crate and the small block as Pixal3D models), framed again as the
code now does it (its roll, its camera's subject distance) and its props stood again (each records the transform it was stood with). On
the real engine (MoGe, seconds): *Rebuild with this lens* at 62° — the props stood again on the new relief; then the crate moved by hand and
the set rebuilt at 66° — the crate stays, the small block follows. Measured each time: every prop's front edge projected through the
picture camera against the pixel where its thing touched the floor in the picture (px), and its height against the relief's floor under it.
The engine stopped (D97), `session.json` written and held for the screenshots (`stop`).

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3d_rig.py --restand   (once: SC3d's project as the code is)
  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3f_rig.py [--hold 1500]
Outputs under engine/spikes/out/sc3f/ (git-ignored): rig.log, result.json, session.json.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = REPO / "engine" / "spikes" / "out" / "sc3d"
OUT = REPO / "engine" / "spikes" / "out" / "sc3f"
PORT = 8787


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def project(cam: dict, x: np.ndarray, W: int, H: int) -> tuple[float, float, float]:
    """A stage point through a Stage camera (look-at with the world's up, then its roll; the lens on a 36 mm sensor) → picture pixels and depth."""
    p, t = np.array(cam["pos"]), np.array(cam["target"])
    zc = -(t - p) / np.linalg.norm(t - p)
    xc = np.cross([0.0, 1.0, 0.0], zc)
    xc /= np.linalg.norm(xc)
    yc = np.cross(zc, xc)
    r = math.radians(cam.get("roll") or 0.0)
    xr, yr = math.cos(r) * xc + math.sin(r) * yc, -math.sin(r) * xc + math.cos(r) * yc
    d = x - p
    depth = float(-d @ zc)
    k = cam["focal_mm"] / cam["sensor_mm"]
    return (0.5 + float(d @ xr) / depth * k) * W, (0.5 - float(d @ yr) / depth * k * W / H) * H, depth


def main() -> int:
    from loom2.catalogue import Catalogue
    from loom2.relief import floor_fit, glb_read, level_of_glb, mesh_arrays, to_stage
    from loom2.set_things import model_bounds, restand_things
    from loom2.stages import StageStore
    from loom2.workspace import Workspace
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=1500.0)
    a = ap.parse_args()
    sess = json.loads((SRC / "session.restand.json").read_text(encoding="utf-8"))
    st_id, set_id = sess["stage_id"], sess["set_id"]
    for d in ("_proj", "_state"):
        shutil.rmtree(OUT / d, ignore_errors=True)
        shutil.copytree(SRC / d, OUT / d)
    for f in ("stop", "session.json", "rig.log"):
        (OUT / f).unlink(missing_ok=True)
    ws = Workspace.open(OUT / "_proj")
    cat, store = Catalogue(ws), StageStore(ws)
    o_ = next(x for x in store.get(st_id).objects if x.id == set_id)
    store.replace_image_set(st_id, set_id, o_.asset_id, o_.lens_deg, o_.floor_y, o_.plate_asset_id, cat.abs_path(cat.get(o_.asset_id)))
    log(f"framed as the code is now and the props stood again: {restand_things(store, cat, st_id, set_id)}")
    rgb = np.asarray(Image.open(next(p for p in (OUT / '_proj' / 'assets').rglob(f'{o_.plate_asset_id}.*') if p.suffix.lower() in ('.png', '.jpg'))).convert("RGB"))
    H, W = rgb.shape[:2]
    result: dict = {"checks": []}

    def check(what: str) -> dict:
        st = store.get(st_id)
        s = next(x for x in st.objects if x.id == set_id)
        cam = next(c for c in st.cameras if c.id == s.plate_camera_id).model_dump()
        relief = cat.abs_path(cat.get(s.asset_id))
        doc, binary = glb_read(relief)
        pos, uv, _ = mesh_arrays(doc, binary)
        lift = -(s.floor_y if s.floor_y is not None else -1.0)
        level = level_of_glb(relief, lift) if s.level else None
        fit = floor_fit(pos, uv)
        on = np.abs(fit["a"] * pos[:, 0] + fit["b"] * pos[:, 2] + fit["c"] - pos[:, 1]) < 0.03
        floor = np.array([to_stage(q, lift, level) for q in pos[on][:: max(1, int(on.sum()) // 5000)]])
        row = {"what": what, "lens": s.lens_deg, "level": s.level, "camera": {k: cam[k] for k in ("pos", "target", "roll", "focal_mm")}, "props": []}
        for t in s.things:
            m = next((x for x in st.objects if x.id == t.object_id), None)
            if m is None:
                continue
            mask = np.asarray(Image.open(cat.abs_path(cat.get(t.mask_asset_id))).convert("L")) > 127
            ys, xs = np.nonzero(mask)
            bottom = ys >= np.percentile(ys, 97)
            touch = (float(np.median(xs[bottom])), float(np.percentile(ys, 99)))     # where the thing met the floor in the picture
            lo, hi = model_bounds(cat.abs_path(cat.get(t.mesh_asset_id)))
            sc = m.transform.scale[0]
            front = np.array(m.transform.pos) + np.array([0.0, 0.0, (hi[2] - lo[2]) * sc / 2])
            u, v, depth = project(cam, front, W, H)
            near = np.hypot(floor[:, 0] - m.transform.pos[0], floor[:, 2] - m.transform.pos[2]) < 0.35
            under = float(np.median(floor[near, 1])) if near.sum() >= 5 else None
            row["props"].append({"name": t.name, "pos": m.transform.pos, "scale": sc, "px_error": round(math.hypot(u - touch[0], v - touch[1]), 1),
                                 "touch_px": [round(touch[0]), round(touch[1])], "front_px": [round(u), round(v)], "floor_under": under and round(under, 3)})
        log(f"{what} (lens {s.lens_deg}°, level {s.level}, camera roll {cam['roll']}°): " + "; ".join(
            f"{p['name']} front at {p['front_px']} against its touch {p['touch_px']} — {p['px_error']} px, {p['pos'][1]:.3f} m over the floor {p['floor_under']}" for p in row["props"]))
        result["checks"].append(row)
        return row

    check("before")
    o = Orch(OUT / "_state", PORT, project=OUT / "_proj").start(timeout=180)
    try:
        h = o.http

        def rebuild(lens: float) -> dict:
            s = next(x for x in h.get(f"/stages/{st_id}").json()["objects"] if x["id"] == set_id)
            t0 = time.time()
            jid = h.post(f"/stages/{st_id}/image-set", json={"asset_id": s["plate_asset_id"], "lens_deg": lens, "replace_set_id": set_id}).json()["job_id"]
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=600)
            log(f"rebuilt at {lens}°: {j['status']} in {time.time() - t0:.1f} s · {(j.get('log_tail') or [])[-3:]}")
            if j["status"] != "done":
                raise SystemExit(f"the rebuild {j['status']}: {j.get('error')}")
            return j["result"]

        r62 = rebuild(62.0)
        result["rebuild_62"] = r62.get("restood")
        c62 = check("rebuilt at 62°")
        doc = h.get(f"/stages/{st_id}").json()                                      # the crate moved by hand
        crate = next(x for x in doc["objects"] if x["kind"] == "mesh" and x["name"] == "Crate")
        crate["transform"]["pos"] = [crate["transform"]["pos"][0] + 0.4, crate["transform"]["pos"][1], crate["transform"]["pos"][2] + 0.3]
        h.put(f"/stages/{st_id}", json=doc)
        r66 = rebuild(66.0)
        result["rebuild_66"] = r66.get("restood")
        check("the crate moved by hand, rebuilt at 66°")
        ok = (result["rebuild_62"] or {}).get("stood") == ["Crate", "Small block"] and (result["rebuild_66"] or {}).get("left") == ["Crate"] \
            and (result["rebuild_66"] or {}).get("stood") == ["Small block"] and all(p["px_error"] < 25 and abs(p["pos"][1]) < 0.05 for p in c62["props"])
        result["ok"] = ok
        log(f"{'ok  ' if ok else 'FAIL'} the props followed the lens (within 25 px of where their things touched the floor, on it); the moved crate stayed")
        h.post("/engine/stop", timeout=60)
        log("the engine stopped (D97: the screenshots render with WebGL next)")
        cam_id = next(x for x in doc["objects"] if x["id"] == set_id)["plate_camera_id"]
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st_id, "set_id": set_id, "cameras": {"picture": cam_id}}, indent=1), encoding="utf-8")
        t2 = time.time()
        while time.time() - t2 < a.hold and not (OUT / "stop").exists():
            time.sleep(1.0)
        log(f"held {time.time() - t2:.0f} s for the screenshots")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
