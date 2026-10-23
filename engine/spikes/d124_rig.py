"""D124 rig: *Make the things* cleans the plate under the things and under their shadows, on the real engine.

A private orchestrator, a fresh project, bench/sets/room.jpg as a set at 69.2°, its four things picked by points (the SC3c rig's clicks)
and kept; the shadows the clean will take read back (`GET …/things/shadows`) and the browser shown the sheet (`session.json`, then
`sheet` written by the screenshot spec). Then *Make the things*: the Fill under the things and their shadows, the relief rebuilt from the
clean plate — the four Pixal3D models are cancelled once queued (D124's check is the plate; SC3c measured the models). The clean plate
against the picture inside each thing's shadow (how much it lifted), the engine stopped (D97) and held for the last screenshot (`stop`).

  orchestrator/.venv/Scripts/python.exe engine/spikes/d124_rig.py [--hold 1500]
Outputs under engine/spikes/out/d124/ (git-ignored): rig.log, result.json, session.json, clean.jpg.
"""
from __future__ import annotations

import argparse
import json
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
from loom2.config import AppState  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = REPO / "engine" / "spikes" / "out" / "d124"
MODELS = Path("F:/loom2-models")
PORT = 8786
THINGS = {"Crate": [(325, 490)], "Table": [(790, 455), (722, 540)], "Small block": [(640, 590)], "Big block": [(1070, 480)]}


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=1500.0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("stop", "sheet", "session.json", "rig.log"):
        (OUT / f).unlink(missing_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {}
    try:
        h = o.http
        assert h.post("/project", json={"path": str(OUT / "_proj"), "name": "D124 rig", "size_cap_gb": 30}).status_code == 200
        picture = REPO / "bench" / "sets" / "room.jpg"
        pic = h.post("/assets/import", json={"paths": [str(picture)]}).json()["items"][0]
        rgb = np.asarray(Image.open(picture).convert("RGB"), np.float32)
        H, W = rgb.shape[:2]
        st = h.post("/stages", json={"name": "Picture room"}).json()

        def wait(job_id: str, what: str, timeout: float = 1800) -> dict:
            t0 = time.time()
            j = o.wait_job(job_id, {"done", "failed", "cancelled"}, timeout=timeout)
            log(f"{what}: {j['status']} in {time.time() - t0:.1f} s · {(j.get('log_tail') or [])[-1:]}")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return j

        wait(h.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": 69.2}).json()["job_id"], "the set at 69.2°")
        doc = h.get(f"/stages/{st['id']}").json()
        sset = next(x for x in doc["objects"] if x["kind"] == "set" and x["preset"] == "image")
        base = f"/stages/{st['id']}/sets/{sset['id']}/things"
        for name, pts in THINGS.items():
            points = [{"x": x, "y": y, "label": 1} for x, y in pts]
            wait(h.post(f"{base}/find", json={"points": points}).json()["job_id"], f"find {name}", 600)
            assert h.post(base, json={"name": name, "points": points}).status_code == 200
        t0 = time.time()
        r = h.get(f"{base}/shadows")
        shadows = np.frombuffer(r.content, np.uint8).reshape(H, W) > 127
        result["shadows"] = {"share": round(float(shadows.mean()), 4), "s": round(time.time() - t0, 2)}
        log(f"the shadows the clean will take: {shadows.mean() * 100:.2f} % of the picture ({time.time() - t0:.2f} s)")
        h.post("/engine/stop", timeout=60)                                       # D97: the sheet's screenshot renders with WebGL; the Make starts it again
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st["id"], "set_id": sset["id"], "step": "sheet"}, indent=1), encoding="utf-8")
        t1 = time.time()
        while not (OUT / "sheet").exists() and time.time() - t1 < a.hold:
            time.sleep(1.0)
        m = h.post(f"{base}/make").json()
        log(f"make: the shadows {m['shadows'] * 100:.2f} % of the picture; the clean plate {m['clean_job_id']}, {len(m['models'])} models to follow")
        cj = wait(m["clean_job_id"], "the clean plate (the things and their shadows)")
        rebuild, *models = cj["result"]["next_job_ids"]
        for jid in models:                                                       # D124's check is the plate (SC3c measured the models)
            h.post(f"/jobs/{jid}/cancel")
        wait(rebuild, "the relief rebuilt from it")
        clean_id = cj["result"]["clean_plate_id"]
        clean_path = next(p for p in (OUT / "_proj" / "assets").rglob(f"{clean_id}.*") if p.suffix.lower() in (".png", ".jpg", ".webp"))
        clean = np.asarray(Image.open(clean_path).convert("RGB"), np.float32)
        lum = lambda x: x @ np.array([0.2126, 0.7152, 0.0722], np.float32)  # noqa: E731
        lifted = float(np.median(lum(clean)[shadows]) / max(1e-3, np.median(lum(rgb)[shadows])))
        result.update({"clean_plate_id": clean_id, "shadow_lifted": round(lifted, 2), "make": m})
        log(f"the clean plate: inside the shadows it took the picture is {lifted:.2f}× as bright as it was (1: untouched)")
        sheet = Image.new("RGB", (1280 + 4, 360 + 26), (24, 24, 26))
        sheet.paste(Image.fromarray(rgb.astype(np.uint8)).resize((640, 360), Image.LANCZOS), (0, 26))
        sheet.paste(Image.fromarray(clean.astype(np.uint8)).resize((640, 360), Image.LANCZOS), (644, 26))
        sheet.save(OUT / "clean.jpg", quality=88)
        shutil.copyfile(OUT / "clean.jpg", REPO / ".docs" / "proto01_animate" / "img" / "25-d124-clean.jpg")
        h.post("/engine/stop", timeout=60)
        log("the engine stopped (D97: the screenshots render with WebGL next)")
        (OUT / "session.json").write_text(json.dumps({"port": PORT, "token": o.token, "stage_id": st["id"], "set_id": sset["id"], "step": "made"}, indent=1), encoding="utf-8")
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
