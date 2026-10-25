"""CW7 (proto01_UIcast 02 §9, 04 §5; D137 stage 6): a place's built set in a shot, on the rig — the real engine on CW6's rig project:

1. a stage with the farm kitchen's set bound (CW6's, baked and filled) and Mara's figure bound, standing 2.5 m ahead of the picture's camera;
2. in the app's page: the camera keyed to dolly 0.8 m in over two seconds, the final shot made (*Make the final shot*, F16) — its plate
   is the built set (method `set`), rendered there along the move; no Klein still is queued;
3. Mara's layer performed by Wan Animate on her guide, matted, and the shot assembled (one GPU job at a time, the browser closed);
4. a sheet: the plate, Mara's layer and the assembled shot at its first, middle and last frames.

    orchestrator/.venv/Scripts/python.exe scripts/cw7_acceptance.py          (Vite on 1420 for the browser half; CW6's rig ran first)

Results: engine/spikes/out/cw7/results.json; the sheet: .docs/proto01_UIcast/img/cw7-final.jpg.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

CW6 = ROOT / "engine" / "spikes" / "out" / "cw6"
OUT = ROOT / "engine" / "spikes" / "out" / "cw7"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"


def browser(*args: str) -> dict:
    r = subprocess.run(["node", str(ROOT / "scripts" / "cw6_browser.cjs"), *args], cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                       timeout=3600, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
    (OUT / f"browser_{args[0]}.log").write_text(r.stderr, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"the browser half failed: {r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def final(fid: str) -> dict:
    return P.api("GET", f"/finals/{fid}")


def layer(fid: str, lid: str) -> dict:
    return next(x for x in final(fid)["layers"] if x["id"] == lid)


def wait_layer(fid: str, lid: str, timeout: float = 3600) -> dict:
    deadline = time.time() + timeout
    lay = layer(fid, lid)
    while time.time() < deadline and lay["status"] not in ("done", "failed"):
        time.sleep(5)
        lay = layer(fid, lid)
    for jid in lay.get("job_ids") or []:
        P.wait_job(jid)
    return layer(fid, lid)


def clip_frames(clip_id: str, picks: list[float]) -> list[Path]:
    """The assembled clip's frames at these fractions of its length (PyAV), as PNGs."""
    import av
    c = P.api("GET", f"/clips/{clip_id}")
    src = CW6 / "proj" / P.api("GET", f"/assets/{c['asset_id']}")["path"] if c.get("asset_id") else None
    path = next((CW6 / "proj" / p for p in [c.get("path")] if p), src)
    frames = []
    with av.open(str(path)) as box:
        for fr in box.decode(video=0):
            frames.append(fr.to_image())
    out = []
    for k, t in enumerate(picks):
        p = OUT / f"shot_{k}.png"
        frames[min(len(frames) - 1, int(t * (len(frames) - 1)))].save(p)
        out.append(p)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    s = json.loads((CW6 / "state.json").read_text(encoding="utf-8"))
    P.OUT = OUT
    app = P.App(CW6 / "proj")
    res: dict = {}
    checks: list[tuple[str, bool, str]] = []
    try:
        kitchen = P.api("GET", f"/story/profiles/{s['places']['kitchen']}")
        mara = next(p for p in P.api("GET", "/story/profiles")["items"] if p["name"] == "Mara")
        kv = next(v for v in kitchen["versions"] if v["id"] == kitchen["current"])
        mv = next(v for v in mara["versions"] if v["id"] == mara["current"])
        ps = kv["place_set"]
        cam = ps["sources"][0]["camera"]
        d = np.array([cam["target"][0] - cam["pos"][0], 0.0, cam["target"][2] - cam["pos"][2]])
        d /= np.linalg.norm(d) or 1.0
        at = [round(cam["pos"][0] + 2.5 * d[0], 3), 0.0, round(cam["pos"][2] + 2.5 * d[2], 3)]
        st = P.api("POST", "/stages", {"name": "CW7 kitchen"})
        objs = [{"id": "set_kitchen", "kind": "set", "name": kitchen["name"], "preset": "built", "locked": True, "profile_id": kitchen["id"], "place_set": ps, "colour_id": 1},
                {"id": "fig_m", "kind": "mannequin", "name": "Mara", "preset": "adult", "profile_id": mara["id"], "body": mv["body"], "detail": (mv["body"] or {}).get("figure") or "female",
                 "pose": {"preset": "stand"}, "transform": {"pos": at, "rot": [0, 0, 0], "scale": [1, 1, 1]}, "colour_id": 2}]
        cams = [{"id": "cam_pic", "name": "The picture's camera", **{k: cam[k] for k in ("pos", "target", "roll", "focal_mm", "sensor_mm")}}]
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": cams, "active_camera": "cam_pic"})
        res["stage_id"] = st["id"]
        shots_before = sum(1 for j in P.api("GET", "/jobs")["items"] if j["kind"] == "stage_shot")
        P.drain()
        t0 = time.time()
        made = browser("final", str(OUT), st["id"])
        fid = made["final_id"]
        res["final_id"], res["make_s"] = fid, made.get("seconds")
        f = final(fid)
        plate = layer(fid, "plate")
        res["plate"] = {"method": plate["method"], "status": plate["status"], "frames": f"{plate['frames_done']}/{f['frames']}", "still": plate["still_asset_id"]}
        checks.append(("the plate is the built set, rendered in the page", plate["method"] == "set" and plate["status"] == "done" and plate["frames_done"] == f["frames"],
                       f"{plate['method']} {plate['status']} {plate['frames_done']}/{f['frames']} in {made.get('seconds')} s (the passes and the plate)"))
        checks.append(("its still is the set's picture; no Klein still queued", plate["still_asset_id"] == ps["sources"][0]["asset_id"]
                       and sum(1 for j in P.api("GET", "/jobs")["items"] if j["kind"] == "stage_shot") == shots_before, plate["still_asset_id"] or "none"))
        # Mara performed, matted; the shot assembled
        fig = next(x for x in f["layers"] if x["kind"] == "figure")
        t1 = time.time()
        P.api("POST", f"/finals/{fid}/layers/{fig['id']}/run", {})
        lay = wait_layer(fid, fig["id"])
        res["perform_s"] = round(time.time() - t1, 1)
        checks.append(("Mara performed by Wan Animate on her guide", lay["status"] == "done" and lay["frames_done"] == f["frames"], f"{lay['status']} in {res['perform_s']} s"))
        store_matte = CW6 / "proj" / "finals" / fid / fig["id"] / "matte"
        if len(list(store_matte.glob("*.png"))) != f["frames"]:
            P.wait_job(P.api("POST", f"/finals/{fid}/layers/{fig['id']}/matte")["job_id"])
        t2 = time.time()
        job = P.wait_job(P.api("POST", f"/finals/{fid}/assemble")["job_id"], timeout=1800)
        res["assemble_s"] = round(time.time() - t2, 1)
        f = final(fid)
        checks.append(("the shot assembled on the built set's plate", job["status"] == "done" and bool(f.get("clip_id")), f"{job['status']} · clip {f.get('clip_id')} in {res['assemble_s']} s"))
        res["clip_id"] = f.get("clip_id")
        # the sheet: the plate, Mara's layer, the shot — first, middle, last
        n = f["frames"]
        idx = [0, n // 2, n - 1]
        base = CW6 / "proj" / "finals" / fid
        rows = [("the plate (the set)", [base / "plate" / "frames" / f"{i:04d}.png" for i in idx]),
                ("Mara (Wan Animate)", [base / fig["id"] / "frames" / f"{i:04d}.png" for i in idx])]
        if f.get("clip_id"):
            rows.append(("the shot", clip_frames(f["clip_id"], [0.0, 0.5, 1.0])))
        tw, th = 420, 236
        im = Image.new("RGB", (150 + 3 * (tw + 6), len(rows) * (th + 6) + 28), (24, 24, 24))
        dr = ImageDraw.Draw(im)
        for k, h in enumerate(["first frame", "middle", "last (dollied 0.8 m in)"]):
            dr.text((150 + k * (tw + 6) + 4, 6), h, fill=(225, 225, 225))
        for i, (label, paths) in enumerate(rows):
            dr.text((6, 28 + i * (th + 6) + th // 2), label, fill=(225, 225, 225))
            for k, q in enumerate(paths):
                if Path(q).is_file():
                    t = Image.open(q).convert("RGB")
                    t.thumbnail((tw, th))
                    im.paste(t, (150 + k * (tw + 6), 28 + i * (th + 6)))
        im.save(IMG / "cw7-final.jpg", quality=86)
    finally:
        app.close()
    for name, ok, note in checks:
        print(("PASS" if ok else "FAIL"), name, "·", note)
    print(f"{sum(ok for _, ok, _ in checks)}/{len(checks)}")
    res["checks"] = [{"name": n, "ok": ok, "note": note} for n, ok, note in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
