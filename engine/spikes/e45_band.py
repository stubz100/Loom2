"""Spike E45 (D164, journal 2026-10-30 19:44): the head sizes where D118's face pass gains a character's identity over a D163 take in its
window — the band *Perform the owed layers ▶* queues the face pass for.

On the E43 copy of the walkthrough's project (scratch), five heads from 11 px to a close shot, through the app's own routes alone on the
GPU: a layer's take in its window (`POST /finals/{fid}/layers/{lid}/run`, D163) where the case asks for one, then the face pass
(`POST …/pass {"preset": "face"}`, its chain of jobs followed). Measured on 12 evenly spaced frames, each the head box (heads.head_boxes,
in the frame) cropped and resized to 512²: FaceSim against the character's animation reference (the largest face; cosine) and the share
of frames with a face found — on the shown frames before (the walkthrough's take at the frame), on the window take and on the pass's
pasted take; the pass's own 512² head too (an upper bound); the seconds of each step.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e45_band.py [--cases A,B,B2,C,D] [--measure-only]

Outputs under engine/spikes/out/e45/ (results.json, sheet_<case>.jpg, log.txt). The orchestrator (8766, the copy as its project) is
started here and stopped at the end; the engine starts with the first job and is stopped too. One GPU job at a time (rule 10).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
PROJECT = Path("F:/loom2-projects/_e43/last-ferry-copy")
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
PORT, TOKEN = 8766, "devtoken"
OUT = ROOT / "engine" / "spikes" / "out" / "e45"
SAMPLES = 12
# case: (label, final, layer, perform in its window first)
CASES = {
    "A": ("Arrival · Tomas (11 px)", "fin_b608e3d8", "fig_04370fc0", False),
    "B": ("Stay · Tomas (26–43 px)", "fin_95c0b546", "fig_6b0726a1", True),
    "B2": ("Arrival · Ines (13–45 px)", "fin_b608e3d8", "fig_q98kue1v", True),
    "C": ("The seal · Tomas (55 px)", "fin_47a428a0-e43ib", "fig_04370fc0", True),
    "D": ("The ferryman · Tomas (110 px)", "fin_0d49874c", "fig_04370fc0", True),
}
# dropped at the set-up (19:47): Departure · Ines (27 px) is seen from behind; The ferryman · Ines has her head outside the frame (a shoulder)


def log(m: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
    print(line, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def head_px(kps: list) -> float:
    """The head box's side in the frame without heads.MIN_SIDE's floor (2.6 × nose–neck, at least 1.8 × the ear spread), the median."""
    out = []
    for k in kps:
        k = np.array(k, dtype=float).reshape(-1, 3)
        out.append(max(2.6 * float(np.hypot(*(k[0][:2] - k[1][:2]))), 1.8 * float(np.hypot(*(k[16][:2] - k[17][:2])))))
    return round(float(np.median(out)), 1)


def sample_idx(n: int) -> list[int]:
    return sorted({int(round(i * (n - 1) / max(1, SAMPLES - 1))) for i in range(min(SAMPLES, n))})


def face_score(fs, hero: np.ndarray | None, crops: list[Image.Image]) -> dict:
    """FaceSim of each crop against the hero (the best of its three largest faces), the share with a face found."""
    sims: list[float | None] = []
    heights: list[float | None] = []                                  # the largest face's height in the crop (its share of the side)
    for im in crops:
        a = np.asarray(im.convert("RGB"))
        faces = fs.detect(a)
        sims.append(round(max(fs.similarity(hero, fs.embed(a, x.kps)) for x in faces[:3]), 3) if faces and hero is not None else None)
        heights.append(round(float(faces[0].bbox[3] - faces[0].bbox[1]) / a.shape[0], 3) if faces else None)
    found = [s for s in sims if s is not None]
    hs = [x for x in heights if x is not None]
    return {"mean": round(float(np.mean(found)), 3) if found else None, "found": len(found), "of": len(sims), "per": sims,
            "face_h": round(float(np.median(hs)), 3) if hs else None, "heights": heights}


def crops_of(frames: list[Path], boxes: list[tuple[int, int, int]], idx: list[int]) -> list[Image.Image]:
    from loom2.heads import box_crop
    return [box_crop(Image.open(frames[i]).convert("RGB"), boxes[i]) for i in idx]


def keep(key: str, row: str, crops: list[Image.Image]) -> None:
    """The measured crops kept for the case's sheet (a later run may have replaced the frames they came from)."""
    d = OUT / "crops" / key / row
    d.mkdir(parents=True, exist_ok=True)
    for i, im in enumerate(crops):
        im.resize((160, 160), Image.LANCZOS).save(d / f"{i:02d}.png")


def sheet(key: str) -> None:
    rows = [r for r in ("frame", "window_take", "pass_v1", "head512_v1", "pass", "head512") if (OUT / "crops" / key / r).is_dir()]
    names = {"frame": "shown before", "window_take": "window take", "pass_v1": "pass (head-only ref)", "head512_v1": "its 512² head", "pass": "face pass", "head512": "its 512² head"}
    if not rows:
        return
    w = 160
    im = Image.new("RGB", (w * 4 + 110, (w + 4) * len(rows)), (24, 24, 24))
    dr = ImageDraw.Draw(im)
    for r_, row in enumerate(rows):
        files = sorted((OUT / "crops" / key / row).glob("*.png"))
        dr.text((6, r_ * (w + 4) + w // 2), names[row], fill=(230, 230, 230))
        for c_, p in enumerate([0, len(files) // 3, 2 * len(files) // 3, len(files) - 1]):
            if 0 <= p < len(files):
                im.paste(Image.open(files[p]).convert("RGB"), (110 + c_ * w, r_ * (w + 4)))
    im.save(OUT / f"sheet_{key}.jpg", quality=88)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="A,B,B2,C,D")
    ap.add_argument("--measure-only", action="store_true", help="no GPU: the shown frames measured, nothing run")
    ap.add_argument("--state", default=str(Path(os.environ.get("TEMP", ".")) / "loom2-e45-state"))
    ap.add_argument("--redo-pass", action="store_true", help="the face pass again on the window take (the earlier one kept as pass_v1, the layer shown its own frames first)")
    a = ap.parse_args()
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.heads import head_boxes
    from loom2.story import StoryStore
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    if not a.measure_only and (port_busy(8188) or port_busy(PORT)):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    store, cat, story = FinalStore(ws), Catalogue(ws), StoryStore(ws)
    fs = FaceSim(MODELS)
    rp = OUT / "results.json"
    results: dict = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {"cases": {}}
    results["stamp"] = time.strftime("%Y-%m-%d %H:%M")

    def save() -> None:
        rp.write_text(json.dumps(results, indent=1), encoding="utf-8")

    keys = [k.strip() for k in a.cases.split(",") if k.strip() in CASES]
    orch = None
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    if not a.measure_only:
        logf = (OUT / "orchestrator.log").open("a", encoding="utf-8")
        orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state", a.state, "--project", str(PROJECT)],
                                cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=logf, stderr=subprocess.STDOUT)
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)

    def layer_of(fid: str, lid: str) -> dict:
        return next(x for x in api.get(f"/finals/{fid}").json()["layers"] if x["id"] == lid)

    def follow(job_id: str) -> list[dict]:
        steps = []
        while job_id:
            t0 = time.time()
            while True:
                j = api.get(f"/jobs/{job_id}").json()
                if j["status"] not in ("queued", "running"):
                    break
                time.sleep(4)
            c = (j.get("result") or {}).get("compiled") or {}
            steps.append({"job": job_id, "status": j["status"], "stage": c.get("stage"), "k": c.get("k"), "of": c.get("of"), "wall_s": j.get("wall_s"), "waited_s": round(time.time() - t0),
                          "error": j.get("error")})
            log(f"    {j['status']} {job_id}: {c.get('stage')} {c.get('k')}/{c.get('of')} · {j.get('wall_s')} s")
            if j["status"] != "done":
                break
            job_id = (j.get("result") or {}).get("next_job_id")
        return steps

    try:
        for key in keys:
            label, fid, lid, perform = CASES[key]
            f = store.get(fid)
            lay = next(x for x in f.layers if x.id == lid)
            kps = store.keypoints(fid, lid)
            boxes = head_boxes(kps, f.frames, f.size["w"], f.size["h"])
            idx = sample_idx(f.frames)
            v = story.profile(lay.profile_id).version(lay.version)
            ref = cat.get(v.anim_ref_asset_id)
            ra = np.asarray(Image.open(cat.abs_path(ref)).convert("RGB"))
            rf = fs.detect(ra)
            hero = fs.embed(ra, rf[0].kps) if rf else None
            res = results["cases"].get(key) or {}
            res.update({"label": label, "final": fid, "layer": lid, "frames": f.frames, "head_px": head_px(kps), "box_px": int(np.median([b[2] for b in boxes])), "hero_face": bool(rf)})
            shown = sorted(store.frames_dir(fid, lid).glob("*.png"))[: f.frames]
            if "frame" not in res:
                c0 = crops_of(shown, boxes, idx)
                res["frame"] = {**face_score(fs, hero, c0), "window": round(min(w[2] for w in lay.window), 2) if lay.window else None}
                keep(key, "frame", c0)
                sheet(key)
            log(f"{key} {label}: head {res['head_px']} px (box {res['box_px']}) · shown before {res['frame']}")
            results["cases"][key] = res
            save()
            if a.measure_only:
                continue
            if perform and "window_take" not in res:
                t0 = time.time()
                r = api.post(f"/finals/{fid}/layers/{lid}/run", json={})
                r.raise_for_status()
                log(f"  run: {r.json()}")
                while time.time() - t0 < 3600:
                    lj = layer_of(fid, lid)
                    if lj["status"] == "failed" or (lj["status"] == "done" and lj.get("matte_check") is not None):
                        break
                    time.sleep(5)
                f = store.get(fid)
                lay = next(x for x in f.layers if x.id == lid)
                shown = sorted(store.frames_dir(fid, lid).glob("*.png"))[: f.frames]
                c1 = crops_of(shown, boxes, idx)
                res["window_take"] = {**face_score(fs, hero, c1), "status": lj["status"], "window": round(min(w[2] for w in lay.window), 2) if lay.window else None,
                                      "seconds": round(time.time() - t0), "matte_strays": len((lj.get("matte_check") or {}).get("strays") or [])}
                keep(key, "window_take", c1)
                log(f"  window take: {res['window_take']}")
                save()
                if lj["status"] != "done":
                    continue
            if a.redo_pass and "pass" in res:
                res["pass_v1"] = res.pop("pass")
                api.post(f"/finals/{fid}/layers/{lid}/source", json={"take": None}).raise_for_status()
                d = OUT / "crops" / key / "pass"
                if d.is_dir():
                    d.rename(OUT / "crops" / key / "pass_v1")
                if (OUT / "crops" / key / "head512").is_dir():
                    (OUT / "crops" / key / "head512").rename(OUT / "crops" / key / "head512_v1")
            if "pass" not in res:
                t0 = time.time()
                r = api.post(f"/finals/{fid}/layers/{lid}/pass", json={"preset": "face"})
                if r.status_code != 200:
                    res["pass"] = {"error": f"{r.status_code} {r.text[:300]}"}
                    log(f"  face pass refused: {res['pass']['error']}")
                    save()
                    continue
                steps = follow(r.json()["job_id"])
                lj = layer_of(fid, lid)
                take = lj["takes"][-1] if lj.get("takes") and lj["takes"][-1].get("preset") == "face" else None
                if not take or any(s["status"] != "done" for s in steps):
                    res["pass"] = {"error": "no take", "steps": steps}
                    log(f"  face pass: no take {[s['status'] for s in steps]}")
                    save()
                    continue
                tdir = store.pass_dir(fid, lid, f"passes/{take['id']}")
                pasted = sorted(tdir.glob("*.png"))[: f.frames]
                heads = sorted((tdir / "head").glob("*.png"))[: f.frames]
                c2 = crops_of(pasted, boxes, idx)
                h512 = [Image.open(heads[i]).convert("RGB") for i in idx if i < len(heads)]
                head_batches = [s for s in steps if s["stage"] == "head"]
                res["pass"] = {**face_score(fs, hero, c2), "take": take["id"], "head512": face_score(fs, hero, h512), "seconds": round(time.time() - t0),
                               "batches": len(head_batches), "batch_s": [s["wall_s"] for s in head_batches], "steps": steps}
                keep(key, "pass", c2)
                keep(key, "head512", h512)
                log(f"  face pass: {json.dumps({k: res['pass'][k] for k in ('mean', 'found', 'of', 'seconds', 'batch_s')})} · head512 {res['pass']['head512']['mean']}")
                save()
            sheet(key)
    finally:
        if orch is not None:
            try:
                api.post("/engine/stop")
            except Exception:  # noqa: BLE001
                pass
            try:
                orch.terminate()
                orch.wait(timeout=30)
            except Exception:  # noqa: BLE001
                orch.kill()
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
