"""RS0b (D197, proto02 03; PG22): the A-pose buttons' frame on the rig. Before RS0b the route made a character's A-pose at the project's
16:9 at 720 px tall (CA0) while Make's reference framing made D177's 2:3 portrait; now the route makes the portrait for every caller. This
makes one A-pose front through the route on the buttons' default model (the clay-reference model, Klein 9B under `full`), from char01's hero
and words in stubz002 — copied into a scratch project, nothing written to stubz002 — then reads it with SDPose (the body fit's own read) to
check the whole figure is in the frame: the ankles found, the figure clear of the top and bottom edges.

    orchestrator/.venv/Scripts/python.exe scripts/rs0b_apose_rig.py [--seed 0]

Results: engine/spikes/out/rs0b/apose.json and .docs/proto01/img/rs0b-apose-frame.jpg (the new portrait beside char01's picked front, made
in Make, and Followed's Nora front, made by the button at 16:9 on 2026-11-03). One GPU job at a time: it refuses to start while the engine
port is busy, and runs its two jobs one after the other on its own orchestrator.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]

from edit_refs_rig import PORT, TOKEN, api, wait_job  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "rs0b"
SHEET = ROOT / ".docs" / "proto01" / "img" / "rs0b-apose-frame.jpg"
STUBZ002 = Path("F:/loom2-projects/stubz002")
FOLLOWED = Path("F:/loom2-projects/propo02-followed")
CHAR01 = "prf_2fb0d705"
NORA_FRONT = "ast_964abfa1"                     # Followed's Nora, picked front, made by the button at 1280×720 (2026-11-03)


def asset_file(project: Path, aid: str) -> Path:
    hit = next(project.glob(f"assets/*/{aid}.png"), None)
    if hit is None:
        raise SystemExit(f"{aid} not found in {project}")
    return hit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import cr_acceptance as cr
    from m1_acceptance import port_busy
    from loom2.config import AppState
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    prof = json.loads((STUBZ002 / "story" / "profiles" / f"{CHAR01}.json").read_text(encoding="utf-8"))
    ver = next(v for v in prof["versions"] if v["id"] == prof["current"])
    hero = asset_file(STUBZ002, ver["hero_asset_id"])
    picked = asset_file(STUBZ002, ver["anim_ref_asset_id"])
    nora = asset_file(FOLLOWED, NORA_FRONT)

    models = os.environ.get("LOOM2_MODELS", "F:/loom2-models")
    tmp = Path(tempfile.mkdtemp(prefix="loom2-rs0b-"))
    AppState(tmp / "state").update_settings({"models_root": models, "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    res: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "character": prof["name"], "seed": a.seed}
    vram = cr.VramSampler()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "RS0b", "size_cap_gb": 20})   # the default format: 1920×1080 @ 24, as stubz002
        hero_id = api("POST", "/assets/import", {"paths": [str(hero)]})["items"][0]["id"]
        p = api("POST", "/story/profiles", {"name": prof["name"], "cls": "character", "hero_asset_id": hero_id,
                                            "appearance": ver.get("appearance") or "", "outfit": ver.get("outfit") or ""})
        vram.mark()
        t1 = time.time()
        made = api("POST", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "count": 1})
        res["model_id"] = made["model_id"]
        j = wait_job(made["job_ids"][0])
        res["make"] = {"status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "error": j.get("error"),
                       "recipe_size": [j["recipe"]["width"], j["recipe"]["height"]]}
        print(f"A-pose front: {j['status']} {j.get('wall_s')} s at {j['recipe']['width']}x{j['recipe']['height']} on {made['model_id']} {j.get('error') or ''}", flush=True)
        if j["status"] != "done":
            return 1
        aid = (j.get("result") or {}).get("asset_ids", [None])[0]
        img = Image.open(io.BytesIO(api("GET", f"/assets/{aid}/file", raw=True))).convert("RGB")
        res["picture"] = [img.width, img.height]
        k = wait_job(api("POST", "/jobs", {"recipe": {"kind": "keypoints", "asset_id": aid}})["jobs"][0]["id"])
        people = (k.get("result") or {}).get("people") or []
        res["keypoints"] = {"status": k["status"], "people": len(people)}
        if people:
            pts = people[0].get("pose_keypoints_2d") or []
            xy = [(pts[i], pts[i + 1], pts[i + 2]) for i in range(0, len(pts), 3)]
            ankles = [xy[10], xy[13]] if len(xy) > 13 else []                       # OpenPose-18: right ankle 10, left ankle 13
            seen = [p for p in xy if p[2] > 0.3]
            top, bottom = min(y for _, y, _ in seen), max(y for _, y, _ in seen)
            res["keypoints"].update({"ankles_conf": [round(c, 2) for *_, c in ankles], "nose_y": round(xy[0][1]),
                                     "ankle_y": [round(y) for _, y, _ in ankles], "top_margin_px": round(top), "bottom_margin_px": round(img.height - bottom)})
            res["whole_figure"] = bool(ankles) and all(c > 0.3 for *_, c in ankles) and top > 8 and img.height - bottom > 8
        print(json.dumps(res["keypoints"]), "whole figure:", res.get("whole_figure"), flush=True)
        res["peak_gb"] = vram.window()

        tiles = [(f"RS0b: the button now · {img.width}x{img.height} · {made['model_id']} · {res['make']['wall_s']} s", img),
                 (f"char01's picked front (Make) · {Image.open(picked).width}x{Image.open(picked).height}", Image.open(picked).convert("RGB")),
                 (f"before: Nora front by the button · {Image.open(nora).width}x{Image.open(nora).height}", Image.open(nora).convert("RGB"))]
        hh = 520
        scaled = [(lbl, im.resize((round(im.width * hh / im.height), hh))) for lbl, im in tiles]
        sheet = Image.new("RGB", (sum(im.width + 10 for _, im in scaled), hh + 22), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        x = 0
        for lbl, im in scaled:
            sheet.paste(im, (x, 22)); dr.text((x + 4, 5), lbl, fill=(230, 230, 230)); x += im.width + 10
        sheet.save(SHEET, quality=88)
        img.save(OUT / "apose_front.png")
        (OUT / "apose.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"peak {res['peak_gb']} GB · {SHEET}", flush=True)
        return 0 if res.get("whole_figure") else 2
    finally:
        vram.stop = True
        try:
            api("POST", "/engine/stop")
            api("POST", "/shutdown")
            time.sleep(1.5)
        except Exception:  # noqa: BLE001
            pass
        if proc.poll() is None:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
