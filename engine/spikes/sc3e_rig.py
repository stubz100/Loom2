"""SC3e rig: the final shot of a picture set — its plate the picture through its relief, the shot assembled from it.

SC3d's rig project (bench/sets/room.jpg laid level, its clean plate, the crate and the small block as Pixal3D models) copied; the figures
hidden (performing them is Wan Animate's, not this check's), a dolly camera keyed inside the picture's budget (0.45 m in, 0.15 m across over
two seconds), made the active one. The browser (a throwaway Playwright spec) makes the final shot — Stage renders the layers' passes and
the plate from the picture, no Klein still — and writes `made`; the rig then measures the plate (its first frame against the clean
picture: the picture camera's own view; its last against its first: the move's parallax), assembles the shot on the CPU, makes a contact
sheet of the plate and the shot, stops the engine if anything started it (D97: the screenshots render with WebGL), writes `assembled`
and holds for the last screenshots (until `stop`).

  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3d_rig.py --restand   (once, so SC3d's project is as the code is)
  orchestrator/.venv/Scripts/python.exe engine/spikes/sc3e_rig.py [--hold 1500] [--reuse]   (--reuse: the project and the final already made)
Outputs under engine/spikes/out/sc3e/ (git-ignored): rig.log, result.json, session.json, sheet.jpg.
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
OUT = REPO / "engine" / "spikes" / "out" / "sc3e"
PORT = 8783


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def unit(v: np.ndarray) -> np.ndarray:
    return v / max(1e-9, float(np.linalg.norm(v)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=1500.0)
    ap.add_argument("--reuse", action="store_true", help="the copied project and its final (`made`) as they are: measure, assemble, hold")
    a = ap.parse_args()
    sess = json.loads((SRC / "session.restand.json").read_text(encoding="utf-8"))
    if not a.reuse:
        for d in ("_proj", "_state"):
            shutil.rmtree(OUT / d, ignore_errors=True)
            shutil.copytree(SRC / d, OUT / d)
    for f in ("stop", "assembled", "session.json") + (() if a.reuse else ("made",)):
        (OUT / f).unlink(missing_ok=True)
    if not a.reuse:                                                                 # the set framed as the code is now (a rebuild without MoGe)
        from loom2.catalogue import Catalogue
        from loom2.stages import StageStore
        from loom2.workspace import Workspace
        ws = Workspace.open(OUT / "_proj")
        cat, store = Catalogue(ws), StageStore(ws)
        o_ = next(x for x in store.get(sess["stage_id"]).objects if x.id == sess["set_id"])
        st_ = store.replace_image_set(sess["stage_id"], o_.id, o_.asset_id, o_.lens_deg, o_.floor_y, o_.plate_asset_id, cat.abs_path(cat.get(o_.asset_id)))
        c_ = next(c for c in st_.cameras if c.id == o_.plate_camera_id)
        log(f"the set framed again: laid level {next(x for x in st_.objects if x.id == o_.id).level}; its camera {c_.pos} → {c_.target} "
            f"(the subject {math.dist(c_.pos, c_.target):.2f} m away)")
    o = Orch(OUT / "_state", PORT, project=OUT / "_proj").start(timeout=180)
    result: dict = {}
    try:
        h = o.http
        st_id, set_id = sess["stage_id"], sess["set_id"]
        doc = h.get(f"/stages/{st_id}").json()
        sset = next(x for x in doc["objects"] if x["id"] == set_id)
        pc = next(c for c in doc["cameras"] if c["id"] == sset["plate_camera_id"])
        if a.reuse:
            doc["cameras"] = [c for c in doc["cameras"] if c["id"] != "cam_dolly"]
        p0, t0 = np.array(pc["pos"]), np.array(pc["target"])
        fwd = unit(t0 - p0)
        right = unit(np.array([-fwd[2], 0.0, fwd[0]]))
        p1 = p0 + 0.45 * fwd + 0.15 * right
        dolly = {**pc, "id": "cam_dolly", "name": "Dolly"}
        key = lambda f, p, t: {"frame": f, "ease": "ease", "pos": [round(float(v), 4) for v in p], "target": [round(float(v), 4) for v in t], "focal_mm": pc["focal_mm"]}  # noqa: E731
        kf = doc.get("keyframes") or {"camera": {}, "objects": {}}
        kf.setdefault("camera", {})["cam_dolly"] = [key(0, p0, t0), key(48, p1, p1 + (t0 - p0))]
        doc.update({"cameras": [c for c in doc["cameras"] if c["id"] != "cam_dolly"] + [dolly], "active_camera": "cam_dolly", "keyframes": kf,
                    "range": {"start": 0, "end": 48},
                    "objects": [{**x, "visible": False} if x["kind"] == "mannequin" else x for x in doc["objects"]]})
        doc = h.put(f"/stages/{st_id}", json=doc).json()
        log(f"the dolly: {[round(float(v), 3) for v in p0]} → {[round(float(v), 3) for v in p1]} over frames 0–48; the figures hidden; "
            f"{sum(1 for x in doc['objects'] if x['kind'] == 'mesh')} props")
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st_id, "set_id": set_id}, indent=1), encoding="utf-8")
        t_start = time.time()
        while not (OUT / "made").exists() and time.time() - t_start < a.hold:
            time.sleep(1.0)
        fid = (OUT / "made").read_text(encoding="utf-8").strip()
        f = h.get(f"/finals/{fid}").json()
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        jobs = [j for j in h.get("/jobs").json()["items"] if j["kind"] == "stage_shot"]
        log(f"the final {fid}: {f['frames']} frames at {f['size']['w']}×{f['size']['h']}, {len(f['layers'])} layers; the plate {plate['method']} {plate['status']} "
            f"{plate['frames_done']} frames, its still {plate['still_asset_id']} (the set's picture {sset['plate_asset_id']}); stage_shot jobs: {len(jobs)}")
        # the plate measured: the first frame is the picture camera's own view of the clean picture; the last moved
        fdir = OUT / "_proj" / "finals" / fid / "plate" / "frames"
        frames = sorted(fdir.glob("*.png"))
        first = np.asarray(Image.open(frames[0]).convert("RGB"), np.float32)
        last = np.asarray(Image.open(frames[-1]).convert("RGB"), np.float32)
        pic_path = next(p for p in (OUT / "_proj" / "assets").rglob(f"{sset['plate_asset_id']}.*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        pic = Image.open(pic_path).convert("RGB")
        H, W = first.shape[:2]
        ph = round(W * pic.height / pic.width)                                           # the frame's width is the picture's (the lens is horizontal)
        ref = np.asarray(pic.resize((W, ph), Image.LANCZOS), np.float32)
        y0 = (H - ph) // 2
        if ph <= H:
            a_, b_ = first[y0:y0 + ph], ref
        else:
            a_, b_ = first, ref[-y0:-y0 + H]
        inner = (slice(8, -8), slice(8, -8))
        mad = float(np.abs(a_[inner] - b_[inner]).mean())
        moved = float(np.abs(last - first).mean())
        black = float((first.sum(axis=2) < 6).mean())
        result.update({"final_id": fid, "frames": f["frames"], "size": f["size"], "plate": plate, "stage_shot_jobs": len(jobs),
                       "first_vs_picture_mad": round(mad, 2), "last_vs_first_mad": round(moved, 2), "black_share_first": round(black, 4)})
        log(f"the plate's first frame against the clean picture: mean |Δ| {mad:.2f} / 255; black {black * 100:.2f} %; the last against the first {moved:.2f} (the move)")
        # the shot assembled on the CPU from the plate, the shadows and the two props
        t1 = time.time()
        jid = h.post(f"/finals/{fid}/assemble").json()["job_id"]
        j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=1800)
        log(f"assembled: {j['status']} in {time.time() - t1:.1f} s · {(j.get('log_tail') or [])[-2:]}")
        f = h.get(f"/finals/{fid}").json()
        result.update({"assemble_s": round(time.time() - t1, 1), "assemble_status": j["status"], "clip_id": f.get("clip_id"), "assembly": f.get("assembly")})
        eng = h.get("/engine").json()
        result["engine_ran"] = bool(eng.get("running"))
        if eng.get("running"):
            h.post("/engine/stop", timeout=60)
            log("the engine had started: stopped (D97: the screenshots render with WebGL next)")
        else:
            log("the engine never started: the plate and the assembly needed no GPU job")
        # a contact sheet: the plate and the assembled shot at the start, the middle and the end
        shot = sorted((OUT / "_proj" / "clips" / f["clip_id"] / "master").glob("*.png")) if f.get("clip_id") else []
        picks = [0, len(frames) // 2, len(frames) - 1]
        tw = 560
        rows = [[frames[i] for i in picks]] + ([[shot[min(len(shot) - 1, round(i * (len(shot) - 1) / max(1, len(frames) - 1)))] for i in picks]] if shot else [])
        th = round(tw * H / W)
        sheet = Image.new("RGB", (tw * 3 + 8, th * len(rows) + 4 * (len(rows) - 1)), (24, 24, 26))
        for r, row in enumerate(rows):
            for c, p in enumerate(row):
                sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (c * (tw + 4), r * (th + 4)))
        sheet.save(OUT / "sheet.jpg", quality=88)
        shutil.copyfile(OUT / "sheet.jpg", REPO / ".docs" / "proto01_animate" / "img" / "25-sc3e-frames.jpg")
        log(f"the contact sheet: the plate{' and the assembled shot' if shot else ''} at frames {picks} → proto01_animate/img/25-sc3e-frames.jpg")
        ok = plate["method"] == "picture" and plate["status"] == "done" and plate["still_asset_id"] == sset["plate_asset_id"] and not jobs and mad < 12 \
            and moved > 1 and j["status"] == "done"
        result["ok"] = ok
        log(f"{'ok  ' if ok else 'FAIL'} the plate is the picture (no Klein still), it moves with the camera, the shot assembled")
        (OUT / "assembled").write_text(fid, encoding="utf-8")
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
