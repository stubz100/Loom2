"""D180's acceptance on the rig (journal 2026-11-01 06:26): the Last Ferry's ferry through the product path, on a copy, alone on the GPU —
find (SAM 3's points), keep, the 3D model. The look in Clay is the app's (scratchpad step d180clay.cjs). Outputs under engine/spikes/out/d180/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d180_rig.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]

SRC, SRC_STATE = Path("F:/loom2-projects/ux-walk2-last-ferry"), Path("F:/loom2-projects/_ux-walk2-state")
COPY = Path("F:/loom2-projects/_d180")
PROJECT, STATE = COPY / "ferry-copy", COPY / "state"
OUT = ROOT / "engine" / "spikes" / "out" / "d180"
PORT, TOKEN = 8766, "devtoken"
POINTS = [{"x": 640, "y": 230, "label": 1}, {"x": 640, "y": 292, "label": 1}]      # the cabin and the hull on the 960×544 set picture


def orchestrator(log: Path) -> tuple[subprocess.Popen, httpx.Client]:
    f = log.open("a", encoding="utf-8")
    proc = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state", str(STATE),
                             "--project", str(PROJECT)], cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=f, stderr=subprocess.STDOUT)
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    for _ in range(120):
        try:
            api.get("/project").raise_for_status()
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return proc, api


def wait(api: httpx.Client, jid: str) -> dict:
    while True:
        j = api.get(f"/jobs/{jid}").json()
        if j["status"] not in ("queued", "running", "staged"):
            return j
        time.sleep(4)


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    if not PROJECT.exists():
        shutil.copytree(SRC, PROJECT)
        shutil.copytree(SRC_STATE, STATE)
    res: dict = {}
    proc, api = orchestrator(OUT / "orchestrator.log")
    try:
        pier = next(p for p in api.get("/story/profiles").json()["items"] if p["name"] == "Harbour pier")
        pid, vid = pier["id"], pier["current"]
        base = f"/story/profiles/{pid}/versions/{vid}/set/things"
        t0 = time.time()
        r = api.post(f"{base}/find", json={"points": POINTS})
        print("find:", r.status_code, r.text[:200], flush=True)
        r.raise_for_status()
        doc = r.json()["document_id"]
        j = wait(api, r.json()["job_id"])
        res["find"] = {"status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error")}
        sel = np.frombuffer(api.get(f"/documents/{doc}/selection").content, np.uint8)
        print("find:", res["find"], "mask px:", int((sel > 127).sum()), flush=True)
        p = api.post(base, json={"name": "Ferry", "points": POINTS}).json()
        thing = next(v for v in p["versions"] if v["id"] == vid)["place_set"]["things"][-1]
        cam = next(v for v in p["versions"] if v["id"] == vid)["place_set"]["sources"][0]["camera"]
        res["thing"] = {k: thing[k] for k in ("id", "base", "width_m", "height_m", "yaw_deg", "card_asset_id", "mask_asset_id")}
        res["distance_m"] = round(math.dist(thing["base"], cam["pos"]), 1)
        print("kept:", res["thing"], "distance:", res["distance_m"], flush=True)
        t1 = time.time()
        r = api.post(f"{base}/{thing['id']}/model")
        print("model:", r.status_code, r.text[:200], flush=True)
        r.raise_for_status()
        j = wait(api, r.json()["job_id"])
        res["model"] = {"status": j["status"], "seconds": round(time.time() - t1), "error": j.get("error"), "assets": (j.get("result") or {}).get("asset_ids")}
        p = api.get(f"/story/profiles/{pid}").json()
        res["landed"] = next(v for v in p["versions"] if v["id"] == vid)["place_set"]["things"][-1]["mesh_asset_id"]
        print("model:", res["model"], "landed:", res["landed"], flush=True)
        for key, name in (("mask_asset_id", "mask.png"), ("card_asset_id", "card.png")):
            (OUT / name).write_bytes(api.get(f"/assets/{thing[key]}/file").content)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    try:                                                                       # the mask over the picture, for the look
        from loom2.catalogue import Catalogue
        from loom2.workspace import Workspace
        cat = Catalogue(Workspace(PROJECT))
        pic = np.asarray(Image.open(cat.abs_path(cat.get("ast_7d42a22b"))).convert("RGB")).astype(float)
        m = np.asarray(Image.open(OUT / "mask.png").convert("L")) > 127
        pic[m] = pic[m] * 0.5 + np.array([240, 166, 58]) * 0.5
        Image.fromarray(pic.astype(np.uint8)).save(OUT / "mask_over.jpg", quality=90)
    except Exception as e:  # noqa: BLE001
        print("the overlay:", e)
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
