"""Spike E46b (M12; journal 2026-10-31 07:31): the candidate facade rule through the app's own Fill route — a facade's texels seen at a
cosine under 0.7 go to Fill (place_sets.unseen_cos) and its default lead names it a flat elevation (fill_prompt), no material named.

On a fresh copy of the market project (F:/loom2-projects/_e46/market-copy-b):
- A   the right-hand fronts as built (bake + fill), and the left;
- F   both facades filled again from their bakes under the candidate rule (POST …/set/fill, one face a job);
then SeedVR2 3B ×4 (×2 twice, D153's weight) on A's and F's right fronts (AU, FU), on the spike's own engine.
Measured on each texture: the sharpness (the edge filter's variance) at the shot's density (7 mm a pixel); the seconds; a sheet and the
shot's crop. E46's stretch is dropped (it scored a perspective hall above a square-on elevation). Outputs under engine/spikes/out/e46b/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e46b_facade.py
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
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e46_facade import SHOT_M_PER_PX, sharp_at_shot  # noqa: E402

SOURCE = Path("F:/loom2-projects/market-walk")
PROJECT = Path("F:/loom2-projects/_e46/market-copy-b")
OUT = ROOT / "engine" / "spikes" / "out" / "e46b"
PORT, TOKEN = 8766, "devtoken"
PID, VID = "prf_6d0533e5", "v1"
FACES = ("facade_right", "facade_left")


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.place_sets import fill_prompt
    from loom2.story import StoryStore, compose_sheet
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    if PROJECT.exists():                                                         # a fresh copy: E46's second run took a first run's fill as A
        shutil.rmtree(PROJECT)
    print(f"copying {SOURCE} to {PROJECT}", flush=True)
    shutil.copytree(SOURCE, PROJECT)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)

    def face(fid: str):
        return next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == fid)

    p0 = StoryStore(ws).profile(PID)
    v0 = p0.version(VID)
    texel = face(FACES[0]).texel_m
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "texel_m": texel, "arms": {},
                     "prompt": fill_prompt(FACES[0], face(FACES[0]).material, compose_sheet(v0, name=p0.name, cls=p0.cls), v0.place_set.kind)}
    print("prompt:", results["prompt"], flush=True)
    textures: dict[str, Image.Image] = {}
    for fid in FACES:
        textures[f"A {fid}"] = Image.open(cat.abs_path(cat.get(face(fid).texture_asset_id))).convert("RGB")
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(Path(os.environ.get("TEMP", ".")) / "loom2-e46b-state"), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
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
            for _ in range(30):                                                  # the face takes its new texture as the job lands
                if face(fid).texture_asset_id != before:
                    break
                time.sleep(1)
            f = face(fid)
            textures[f"F {fid}"] = Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB")
            results["arms"][f"F {fid}"] = {"job": jid, "status": j["status"], "seconds": round(time.time() - t0), "texture": f.texture_asset_id, "error": j.get("error")}
            print(f"F {fid}: {results['arms'][f'F {fid}']}", flush=True)
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
    for _ in range(30):                                                          # the orchestrator's engine let go of the port
        if not port_busy(8188):
            break
        time.sleep(1)
    elog = (OUT / "engine.log").open("a", encoding="utf-8")
    proc = None
    try:
        proc, launch = launch_engine(elog)
        out_dir = Path(launch["argv"][launch["argv"].index("--output-directory") + 1])
        eng = Engine("127.0.0.1:8188")

        def upload(im: Image.Image, name: str) -> str:
            p = OUT / f"{name}.png"
            im.save(p)
            r = httpx.post("http://127.0.0.1:8188/upload/image", files={"image": (p.name, p.read_bytes(), "image/png")}, data={"overwrite": "true", "type": "input"}, timeout=120)
            r.raise_for_status()
            return r.json()["name"]

        for arm in ("A", "F"):
            key = f"{arm} {FACES[0]}"
            if key not in textures:
                continue
            im, t0 = textures[key], time.time()
            for k in range(2):
                prefix = f"e46b/{arm.lower()}u{k}"
                shutil.rmtree((out_dir / prefix).parent, ignore_errors=True)
                eng.run(seedvr2_graph(upload(im, f"{arm}_u{k}_in"), WEIGHTS["int8"], 2, "lab", prefix), timeout=1800)
                im = Image.open(sorted((out_dir / prefix).parent.glob(f"{Path(prefix).name}*.png"))[0]).convert("RGB")
            textures[f"{arm}U {FACES[0]}"] = im
            results["arms"][f"{arm}U {FACES[0]}"] = {"seconds": round(time.time() - t0)}
            print(f"{arm}U: {results['arms'][f'{arm}U {FACES[0]}']}", flush=True)
    finally:
        if proc is not None:
            stop_engine(proc)
    up = lambda k: k.split(" ")[0].endswith("U")  # noqa: E731
    for key, im in textures.items():
        results["arms"].setdefault(key, {}).update({"sharp_at_shot": sharp_at_shot(im, texel / (4 if up(key) else 1)), "size": list(im.size)})
        im.save(OUT / f"face_{key.replace(' ', '_')}.png")
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    order = [k for k in (f"A {FACES[0]}", f"F {FACES[0]}", f"A {FACES[1]}", f"F {FACES[1]}", f"AU {FACES[0]}", f"FU {FACES[0]}") if k in textures]
    W = 1500
    sheet = Image.new("RGB", (W, 272 * len(order)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, key in enumerate(order):
        r = results["arms"][key]
        dr.text((6, i * 272 + 4), f"{key}: sharpness at the shot {r['sharp_at_shot']} · {r['size'][0]}x{r['size'][1]}", fill=(230, 230, 230))
        sheet.paste(textures[key].resize((W, 250)), (0, i * 272 + 22))
    sheet.save(OUT / "sheet.jpg", quality=86)
    crops = []
    for key in (k for k in order if FACES[0] in k):                              # what the shot sees: 848 px of the face at 7 mm a pixel
        im = textures[key]
        tx = texel / (4 if up(key) else 1)
        w, h = im.size
        cw = max(1, round(848 * SHOT_M_PER_PX / tx))
        mid = im.crop((int(w * 0.45), 0, int(w * 0.45) + cw, h))
        crops.append((key, mid.resize((848, round(mid.height * 848 / mid.width)), Image.BICUBIC)))
    ch = max(c.height for _, c in crops)
    view = Image.new("RGB", (848, (ch + 22) * len(crops)), (20, 20, 20))
    dv = ImageDraw.Draw(view)
    for i, (key, c) in enumerate(crops):
        dv.text((6, i * (ch + 22) + 4), f"{key} at the shot's density", fill=(230, 230, 230))
        view.paste(c, (0, i * (ch + 22) + 22))
    view.save(OUT / "view.jpg", quality=86)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("sharp_at_shot", "seconds")} for k, v in results["arms"].items()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
