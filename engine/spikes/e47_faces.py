"""Spike E47, phase 1 (M5 / M12; journal 2026-10-31 10:06): the side-on background at the shot — the market walk's facades named and
filled again under D170 through the app's own routes (arm D), then each through SeedVR2 3B ×4 (×2 twice, D153's weight; arm DU, saved
beside, swapped in by e47_swap.py after D's final is made). Phase 2 is the app: a final of the same shot for D, then for DU; phase 3
e47_compare.py. A fresh copy of the market project at F:/loom2-projects/_e47/market-copy; outputs under engine/spikes/out/e47/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e47_faces.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
SOURCE = Path("F:/loom2-projects/market-walk")
PROJECT = Path("F:/loom2-projects/_e47/market-copy")
STATE = Path("F:/loom2-projects/_e47/state")
OUT = ROOT / "engine" / "spikes" / "out" / "e47"
PORT, TOKEN = 8766, "devtoken"
PID, VID = "prf_6d0533e5", "v1"
FACES = ("facade_right", "facade_left")
MATERIAL = "fish market stalls: counters of fish on ice, crates below, lamps above"     # E46d's words, as an author would write them


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    print(f"copying {SOURCE} to {PROJECT}", flush=True)
    shutil.copytree(SOURCE, PROJECT)
    STATE.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    face = lambda fid: next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == fid)  # noqa: E731
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "material": MATERIAL, "faces": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(STATE), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        p = api.get(f"/story/profiles/{PID}").json()
        ps = next(x for x in p["versions"] if x["id"] == VID)["place_set"]
        for fa in ps["faces"]:
            if fa["id"] in FACES:
                fa["material"] = MATERIAL
        api.put(f"/story/profiles/{PID}/versions/{VID}/set", json={"revision": p["revision"], "place_set": ps}).raise_for_status()
        for fid in FACES:
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
            results["faces"][fid] = {"job": jid, "status": j["status"], "fill_s": round(time.time() - t0), "texture_D": f.texture_asset_id,
                                     "prompt": (j.get("recipe") or {}).get("prompt_text"), "error": j.get("error")}
            Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB").save(OUT / f"face_D_{fid}.png")
            print(f"D {fid}: {results['faces'][fid]}", flush=True)
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    from e12_angles import Engine
    from e40_seedvr2 import WEIGHTS, launch_engine, seedvr2_graph, stop_engine
    for _ in range(30):
        if not port_busy(8188):
            break
        time.sleep(1)
    elog = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None
    try:
        proc, launch = launch_engine(elog)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine("127.0.0.1:8188")
        for fid in FACES:
            im, t0 = Image.open(OUT / f"face_D_{fid}.png").convert("RGB"), time.time()
            for k in range(2):
                p = OUT / f"_up_{fid}_{k}.png"
                im.save(p)
                r = httpx.post("http://127.0.0.1:8188/upload/image", files={"image": (p.name, p.read_bytes(), "image/png")}, data={"overwrite": "true", "type": "input"}, timeout=120)
                r.raise_for_status()
                prefix = f"e47/{fid}_u{k}"
                shutil.rmtree((out_dir / prefix).parent, ignore_errors=True)
                eng.run(seedvr2_graph(r.json()["name"], WEIGHTS["int8"], 2, "lab", prefix), timeout=1800)
                im = Image.open(sorted((out_dir / prefix).parent.glob(f"{Path(prefix).name}*.png"))[0]).convert("RGB")
                p.unlink(missing_ok=True)
            im.save(OUT / f"face_DU_{fid}.png")
            results["faces"][fid].update({"upscale_s": round(time.time() - t0), "size_DU": list(im.size)})
            print(f"DU {fid}: {im.size} in {results['faces'][fid]['upscale_s']} s", flush=True)
    finally:
        if proc is not None:
            stop_engine(proc)
    (OUT / "faces.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
