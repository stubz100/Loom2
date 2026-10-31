"""Spike E46 (M12; journal 2026-10-31 07:21): the market walk's side-on stall fronts — repainted straight on, then sharpened.

On a copy of the market project (F:/loom2-projects/_e46/market-copy), the right-hand fronts (`facade_right`, 30 × 5 m at 4 cm a texel):
- A  the face as it is (bake + fill);
- G  the texels the picture saw at a cosine under 0.35 handed to Fill too (the coverage's red set to 0 there), the app's own route;
- GM G with the face's material named as a flat elevation (PUT …/set, the author's lever);
then SeedVR2 3B ×4 (×2 twice, D153's weight) on A, G and GM (AU, GU, GMU), on the spike's own engine.
Measured on each texture: the stretch (the mean horizontal gradient ÷ the vertical: a smear along the hall ≪ 1) and the sharpness (the
edge filter's variance) at the shot's density (7 mm a pixel); the seconds; a sheet and the shot's view. Outputs under engine/spikes/out/e46/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e46_facade.py
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
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
SOURCE = Path("F:/loom2-projects/market-walk")
PROJECT = Path("F:/loom2-projects/_e46/market-copy")
OUT = ROOT / "engine" / "spikes" / "out" / "e46"
PORT, TOKEN = 8766, "devtoken"
PID, VID, FACE = "prf_6d0533e5", "v1", "facade_right"
GRAZING = 0.35
SHOT_M_PER_PX = 0.007
MATERIAL = ("a flat elevation of fish market stalls seen square on: counters of fish on ice, crates below, lamps above, no perspective, "
            "no floor or ceiling in view")                                      # ≤ 200 characters, the face's material field (D143)
assert len(MATERIAL) <= 200


def stretch(im: Image.Image) -> float:
    a = np.asarray(im.convert("L"), dtype=np.float32)
    gx, gy = np.abs(np.diff(a, axis=1)).mean(), np.abs(np.diff(a, axis=0)).mean()
    return round(float(gx / max(1e-6, gy)), 3)


def sharp_at_shot(im: Image.Image, texel_m: float) -> float:
    """The edge filter's variance over the face's middle third, resized to the shot's density (texel_m → 7 mm a pixel)."""
    w, h = im.size
    mid = im.crop((w // 3, 0, 2 * w // 3, h))
    s = texel_m / SHOT_M_PER_PX
    big = mid.resize((max(1, round(mid.width * s)), max(1, round(mid.height * s))), Image.BICUBIC).convert("L")
    return round(float(np.asarray(big.filter(ImageFilter.FIND_EDGES), dtype=np.float32).var()), 1)


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    if not PROJECT.exists():
        print(f"copying {SOURCE} to {PROJECT}", flush=True)
        shutil.copytree(SOURCE, PROJECT)
    ws = Workspace(PROJECT)
    cat, st = Catalogue(ws), StoryStore(ws)
    face = lambda: next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == FACE)  # noqa: E731
    f0 = face()
    texel = f0.texel_m
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "face": FACE, "texel_m": texel, "arms": {}}
    textures: dict[str, Image.Image] = {"A": Image.open(cat.abs_path(cat.get(f0.texture_asset_id))).convert("RGB")}
    cov_p = cat.abs_path(cat.get(f0.coverage_asset_id))                         # G's coverage: a grazing texel counts as unseen
    cov = np.asarray(Image.open(cov_p).convert("RGB")).copy()
    results["seen_before"] = round(float((cov[..., 0] / 255.0 >= 0.05).mean()), 3)
    cov[..., 0] = np.where(cov[..., 0] / 255.0 < GRAZING, 0, cov[..., 0])
    Image.fromarray(cov).save(cov_p, format="PNG")
    results["seen_after"] = round(float((cov[..., 0] / 255.0 >= 0.05).mean()), 3)
    print(f"coverage: seen {results['seen_before']} -> {results['seen_after']} (cosine >= {GRAZING})", flush=True)
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(Path(os.environ.get("TEMP", ".")) / "loom2-e46-state"), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    last = f0.texture_asset_id
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)

        def fill(arm: str) -> None:
            nonlocal last
            t0 = time.time()
            r = api.post(f"/story/profiles/{PID}/versions/{VID}/set/fill", json={"faces": [FACE]})
            r.raise_for_status()
            jid = r.json()["job_id"]
            while True:
                j = api.get(f"/jobs/{jid}").json()
                if j["status"] not in ("queued", "running"):
                    break
                time.sleep(3)
            for _ in range(30):                                                  # the face takes its new texture as the job lands
                if face().texture_asset_id != last:
                    break
                time.sleep(1)
            f = face()
            last = f.texture_asset_id
            textures[arm] = Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB")
            results["arms"][arm] = {"job": jid, "status": j["status"], "seconds": round(time.time() - t0), "texture": f.texture_asset_id, "error": j.get("error")}
            print(f"{arm}: {results['arms'][arm]}", flush=True)

        fill("G")
        p = api.get(f"/story/profiles/{PID}").json()
        v = next(x for x in p["versions"] if x["id"] == VID)
        ps = v["place_set"]
        for fa in ps["faces"]:
            if fa["id"] == FACE:
                fa["material"] = MATERIAL
        api.put(f"/story/profiles/{PID}/versions/{VID}/set", json={"revision": p["revision"], "place_set": ps}).raise_for_status()
        fill("GM")
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

        for arm in ("A", "G", "GM"):
            if arm not in textures:
                continue
            im, t0 = textures[arm], time.time()
            for k in range(2):
                prefix = f"e46/{arm.lower()}u{k}"
                shutil.rmtree((out_dir / prefix).parent, ignore_errors=True)
                eng.run(seedvr2_graph(upload(im, f"{arm}_u{k}_in"), WEIGHTS["int8"], 2, "lab", prefix), timeout=1800)
                im = Image.open(sorted((out_dir / prefix).parent.glob(f"{Path(prefix).name}*.png"))[0]).convert("RGB")
            textures[arm + "U"] = im
            results["arms"][arm + "U"] = {"seconds": round(time.time() - t0), "size": list(im.size)}
            print(f"{arm}U: {results['arms'][arm + 'U']}", flush=True)
    finally:
        if proc is not None:
            stop_engine(proc)
    for arm, im in textures.items():
        tx = texel / (4 if arm.endswith("U") else 1)
        results["arms"].setdefault(arm, {}).update({"stretch": stretch(im), "sharp_at_shot": sharp_at_shot(im, tx), "size": list(im.size)})
        im.save(OUT / f"face_{arm}.png")
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    order = [a for a in ("A", "G", "GM", "AU", "GU", "GMU") if a in textures]
    W = 1500
    sheet = Image.new("RGB", (W, 272 * len(order)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, arm in enumerate(order):
        r = results["arms"][arm]
        dr.text((6, i * 272 + 4), f"{arm}: stretch {r['stretch']} · sharpness at the shot {r['sharp_at_shot']} · {r['size'][0]}x{r['size'][1]}", fill=(230, 230, 230))
        sheet.paste(textures[arm].resize((W, 250)), (0, i * 272 + 22))
    sheet.save(OUT / "sheet.jpg", quality=86)
    crops = []
    for arm in order:                                                            # what the shot sees: 848 px of the face at 7 mm a pixel
        im = textures[arm]
        tx = texel / (4 if arm.endswith("U") else 1)
        w, h = im.size
        cw = max(1, round(848 * SHOT_M_PER_PX / tx))
        mid = im.crop((int(w * 0.45), 0, int(w * 0.45) + cw, h))
        crops.append((arm, mid.resize((848, round(mid.height * 848 / mid.width)), Image.BICUBIC)))
    ch = max(c.height for _, c in crops)
    view = Image.new("RGB", (848, (ch + 22) * len(crops)), (20, 20, 20))
    dv = ImageDraw.Draw(view)
    for i, (arm, c) in enumerate(crops):
        dv.text((6, i * (ch + 22) + 4), f"{arm} at the shot's density", fill=(230, 230, 230))
        view.paste(c, (0, i * (ch + 22) + 22))
    view.save(OUT / "view.jpg", quality=86)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("stretch", "sharp_at_shot", "seconds")} for k, v in results["arms"].items()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
