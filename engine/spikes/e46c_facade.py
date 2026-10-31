"""Spike E46c (M12; journal 2026-10-31 07:35): what an unnamed facade's Fill should name — the place's name (N) or its words without people,
floor or camera (S) — simulated through the face's material (a named material is the whole subject), two seeds each, on E46b's copy with
the candidate rule in place (place_sets.unseen_cos, the elevation lead). Outputs under engine/spikes/out/e46c/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e46c_facade.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e46_facade import sharp_at_shot  # noqa: E402

PROJECT = Path("F:/loom2-projects/_e46/market-copy-b")
OUT = ROOT / "engine" / "spikes" / "out" / "e46c"
PORT, TOKEN = 8766, "devtoken"
PID, VID, FACE = "prf_6d0533e5", "v1", "facade_right"
ARMS = {"N": "The buildings' fronts along Fish market",
        "S": "fish stalls in an old covered market hall: wooden counters heaped with fish on crushed ice, crates and baskets, hanging lamps, iron roof columns"}
SEEDS = 2


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.place_sets import fill_prompt
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    if not PROJECT.exists():
        raise SystemExit("run e46b_facade.py first (its copy)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    face = lambda: next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == FACE)  # noqa: E731
    texel = face().texel_m
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "arms": {}}
    textures: dict[str, Image.Image] = {}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(Path(os.environ.get("TEMP", ".")) / "loom2-e46c-state"), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        for arm, material in ARMS.items():
            p = api.get(f"/story/profiles/{PID}").json()
            ps = next(x for x in p["versions"] if x["id"] == VID)["place_set"]
            for fa in ps["faces"]:
                if fa["id"] == FACE:
                    fa["material"] = material
            api.put(f"/story/profiles/{PID}/versions/{VID}/set", json={"revision": p["revision"], "place_set": ps}).raise_for_status()
            for k in range(SEEDS):
                before, t0 = face().texture_asset_id, time.time()
                r = api.post(f"/story/profiles/{PID}/versions/{VID}/set/fill", json={"faces": [FACE]})
                r.raise_for_status()
                jid = r.json()["job_id"]
                while True:
                    j = api.get(f"/jobs/{jid}").json()
                    if j["status"] not in ("queued", "running"):
                        break
                    time.sleep(3)
                for _ in range(30):
                    if face().texture_asset_id != before:
                        break
                    time.sleep(1)
                key = f"{arm}{k + 1}"
                textures[key] = Image.open(cat.abs_path(cat.get(face().texture_asset_id))).convert("RGB")
                results["arms"][key] = {"prompt": fill_prompt(FACE, material, "", "street"), "job": jid, "status": j["status"], "seconds": round(time.time() - t0),
                                        "sharp_at_shot": sharp_at_shot(textures[key], texel)}
                textures[key].save(OUT / f"face_{key}.png")
                print(f"{key}: {results['arms'][key]}", flush=True)
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    W = 1500
    sheet = Image.new("RGB", (W, 272 * len(textures)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (key, im) in enumerate(textures.items()):
        dr.text((6, i * 272 + 4), f"{key}: {ARMS[key[0]]}", fill=(230, 230, 230))
        sheet.paste(im.resize((W, 250)), (0, i * 272 + 22))
    sheet.save(OUT / "sheet.jpg", quality=86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
