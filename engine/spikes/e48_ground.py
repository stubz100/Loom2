"""Spike E48 (M14 and E47's floor band; journal 2026-10-31 10:13): a street's ground faces filled from above — on E47's copy (its facades set
back to D's textures), the road and both pavements filled again through the app's own route under the candidate lead in the working tree
(place_sets.fill_prompt: "A flat plan view of ‹material›, seen from directly above …", no place words):
- L    no material named;
- LM   "wet grey stone paving slabs" named;
- LMC  LM with the ground's texels seen at a cosine under 0.35 handed to Fill too (the coverage edited, as E46's G).
The faces keep LMC's textures at the end; faces.json names every arm's, so e48_pick.py can set another. Outputs under engine/spikes/out/e48/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e48_ground.py
"""
from __future__ import annotations

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
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PID, PROJECT, STATE, VID  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e48"
PORT, TOKEN = 8766, "devtoken"
GROUND = ("road", "pavement_left", "pavement_right")
D_TEXTURES = {"facade_right": "ast_5c8917b2", "facade_left": "ast_579546a0"}    # E47's arm D
MATERIAL = "wet grey stone paving slabs"
GRAZING = 0.35


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    st = StoryStore(ws)
    for fid, aid in D_TEXTURES.items():
        st.update_face(PID, VID, fid, texture_asset_id=aid)
    face = lambda fid: next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == fid)  # noqa: E731
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "arms": {}}
    textures: dict[str, Image.Image] = {}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(STATE), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def materials(m: str) -> None:
        p = api.get(f"/story/profiles/{PID}").json()
        ps = next(x for x in p["versions"] if x["id"] == VID)["place_set"]
        for fa in ps["faces"]:
            if fa["id"] in GROUND:
                fa["material"] = m
        api.put(f"/story/profiles/{PID}/versions/{VID}/set", json={"revision": p["revision"], "place_set": ps}).raise_for_status()

    def fill(arm: str) -> None:
        for fid in GROUND:
            before, t0 = face(fid).texture_asset_id, time.time()
            r = api.post(f"/story/profiles/{PID}/versions/{VID}/set/fill", json={"faces": [fid]})
            r.raise_for_status()
            jid = r.json()["job_id"]
            while True:
                j = api.get(f"/jobs/{jid}").json()
                if j["status"] not in ("queued", "running"):
                    break
                time.sleep(3)
            for _ in range(30):
                if face(fid).texture_asset_id != before:
                    break
                time.sleep(1)
            f = face(fid)
            textures[f"{arm} {fid}"] = Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB")
            results["arms"][f"{arm} {fid}"] = {"job": jid, "status": j["status"], "seconds": round(time.time() - t0), "texture": f.texture_asset_id,
                                                "prompt": (j.get("recipe") or {}).get("prompt_text"), "error": j.get("error")}
            print(f"{arm} {fid}: {results['arms'][f'{arm} {fid}']}", flush=True)

    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        materials("")
        fill("L")
        materials(MATERIAL)
        fill("LM")
        for fid in GROUND:                                                      # LMC: the grazing ground the Fill's too
            p = cat.abs_path(cat.get(face(fid).coverage_asset_id))
            cov = np.asarray(Image.open(p).convert("RGB")).copy()
            cov[..., 0] = np.where(cov[..., 0] / 255.0 < GRAZING, 0, cov[..., 0])
            Image.fromarray(cov).save(p, format="PNG")
        fill("LMC")
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    (OUT / "faces.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    keys = list(textures)
    W = 1500
    sheet = Image.new("RGB", (W, 120 * len(keys)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(keys):
        sheet.paste(textures[k].rotate(90, expand=True).resize((W, 100)), (0, i * 120 + 18))
        d.text((4, i * 120 + 3), f"{k} (the far end left, the picture's camera right)", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
