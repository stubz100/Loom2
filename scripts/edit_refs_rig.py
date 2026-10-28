"""D152's rig: references in Edit AI, measured where they matter — the inpaint bench's face fix (task 05: the box around the young woman's
face on the alley render, the prompt "the same young woman's face…") run as the AI tab runs it (Fill: Klein + LanPaint), with the hero
(bench/angles/07.jpg, her close-up) as reference image 1 against no reference, two seeds each. Each result (the layer pasted over the
source) is scored with FaceSim (ArcFace, `loom2.tools.facesim`) against the hero's face; the time per job and the peak VRAM beside it.

Bars: every job done, a warm fill ≤ 60 s without the reference and ≤ 90 s with it (the reference's tokens are paid in the sampler:
measured 2026-10-28 on Klein 9B, 42 → 67 s; its VAE encode 0.2 s), the peak ≤ 15.5 GB; FaceSim with the reference ≥ FaceSim without (the
gain is the point; the numbers are advisory, as 11 §11 item 6 keeps them). Needs the FaceSim weights (scripts/fetch_facesim.py).

    orchestrator/.venv/Scripts/python.exe scripts/edit_refs_rig.py [--seeds 1,2]

Results: engine/spikes/out/edit_refs/results.json, sheet.jpg (the source, then each fill, the reference last). One GPU job at a time.
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
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]

PORT = 8779
TOKEN = "refstoken"
OUT = ROOT / "engine" / "spikes" / "out" / "edit_refs"
SOURCE = ROOT / "bench" / "inpaint" / "source.png"
MASK = ROOT / "bench" / "inpaint" / "masks" / "05-face-fix.png"
HERO = ROOT / "bench" / "angles" / "07.jpg"
BAR_WARM_S, BAR_WARM_REF_S, BAR_PEAK_GB = 60.0, 90.0, 15.5


def api(method: str, path: str, body=None, raw: bool = False, data: bytes | None = None):
    payload = data if data is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {"X-Loom-Token": TOKEN, "Content-Type": "application/octet-stream" if data is not None else "application/json"}
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=payload, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def wait_job(jid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1.0)
    raise TimeoutError(jid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--prompt", default="the same young woman's face, freckles, calm expression, looking at the viewer, natural eyes, same lighting")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",")]
    import cr_acceptance as cr
    from m1_acceptance import port_busy
    from loom2.config import AppState
    from loom2.tools.facesim import FaceSim
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    fs = FaceSim(Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")))
    hero_img = np.asarray(Image.open(HERO).convert("RGB"))
    hero_faces = fs.detect(hero_img)
    if not hero_faces:
        raise SystemExit("no face found on the hero")
    hero_emb = fs.embed(hero_img, hero_faces[0].kps)

    def sim(rgb: np.ndarray) -> float | None:
        faces = fs.detect(rgb)
        if not faces:
            return None
        f = max(faces, key=lambda x: x.area)
        return round(FaceSim.similarity(fs.embed(rgb, f.kps), hero_emb), 3)

    tmp = Path(tempfile.mkdtemp(prefix="loom2-refs-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "seeds": seeds, "jobs": [], "failures": []}
    vram = cr.VramSampler()
    source = Image.open(SOURCE).convert("RGBA")
    results["source_facesim"] = sim(np.asarray(source.convert("RGB")))
    tiles: list[tuple[str, Image.Image]] = [("source", source.convert("RGB"))]

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "Refs", "size_cap_gb": 20})
        src_id = api("POST", "/assets/import", {"paths": [str(SOURCE)]})["items"][0]["id"]
        hero_id = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
        doc = api("POST", "/documents", {"from_asset": src_id, "name": "face-fix"})
        did, W, H = doc["id"], doc["w"], doc["h"]
        mask = np.asarray(Image.open(MASK).convert("L").resize((W, H), Image.Resampling.NEAREST))
        api("PUT", f"/documents/{did}/selection?w={W}&h={H}", data=np.ascontiguousarray(mask).tobytes())
        vram.mark()
        for with_ref in (False, True):
            for seed in seeds:
                recipe = {"kind": "inpaint", "mode": "fill", "prompt_text": a.prompt, "seeds": [seed], **({"refs": [{"asset_id": hero_id, "note": "the hero"}]} if with_ref else {})}
                t1 = time.time()
                job = api("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]
                j = wait_job(job["id"])
                row = {"reference": with_ref, "seed": seed, "status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "error": j.get("error")}
                row["node_times"] = j.get("node_times")
                results["jobs"].append(row)
                check(j["status"] == "done", f"fill {'with' if with_ref else 'without'} the reference, seed {seed}: {j['status']} in {j.get('wall_s')} s {j.get('error') or ''}")
                if j["status"] != "done":
                    continue
                lid = (j.get("result") or {}).get("layers", [None])[0]
                d = api("GET", f"/documents/{did}")
                layer = next((n for n in d.get("layers", []) for n in ([n] + (n.get("children") or [])) if n.get("id") == lid), None)
                png = api("GET", f"/documents/{did}/layers/{lid}/pixels", raw=True)
                im = Image.open(io.BytesIO(png)).convert("RGBA")
                comp = source.copy()
                comp.alpha_composite(im, (int(layer["x"]) if layer else 0, int(layer["y"]) if layer else 0))
                rgb = np.asarray(comp.convert("RGB"))
                row["facesim"] = sim(rgb)
                row["layer"] = {"id": lid, "size": [im.width, im.height], "at": [layer.get("x"), layer.get("y")] if layer else None}
                tiles.append((f"{'ref' if with_ref else 'no ref'} · s{seed} · FaceSim {row['facesim']}", comp.convert("RGB")))
                print(f"     FaceSim to the hero {row['facesim']} (the source's own: {results['source_facesim']})", flush=True)
        peak = vram.window()
        results["peak_gb"] = peak
        warm = {k: [r["wall_s"] for r in results["jobs"][1:] if r.get("wall_s") and r["reference"] == k] for k in (False, True)}
        check(bool(warm[False]) and max(warm[False]) <= BAR_WARM_S, f"a warm fill without the reference ≤ {BAR_WARM_S:g} s (warm {warm[False]}, the session's first {results['jobs'][0].get('wall_s') if results['jobs'] else None} s)")
        check(bool(warm[True]) and max(warm[True]) <= BAR_WARM_REF_S, f"a warm fill with the reference ≤ {BAR_WARM_REF_S:g} s (warm {warm[True]}; the reference's tokens are paid in the sampler)")
        check(peak <= BAR_PEAK_GB, f"peak VRAM {peak} GB (bar ≤ {BAR_PEAK_GB} GB)")
        without = [r["facesim"] for r in results["jobs"] if not r["reference"] and r.get("facesim") is not None]
        withr = [r["facesim"] for r in results["jobs"] if r["reference"] and r.get("facesim") is not None]
        results["facesim_mean"] = {"without": round(float(np.mean(without)), 3) if without else None, "with": round(float(np.mean(withr)), 3) if withr else None}
        check(bool(without) and bool(withr) and np.mean(withr) >= np.mean(without), f"FaceSim with the reference ≥ without (with {withr}, without {without}; the source's own {results['source_facesim']})")
        tiles.append(("the reference (hero)", Image.open(HERO).convert("RGB")))
        hh = 360
        scaled = [(lbl, im.resize((round(im.width * hh / im.height), hh))) for lbl, im in tiles]
        sheet = Image.new("RGB", (sum(im.width + 8 for _, im in scaled), hh + 18), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        x = 0
        for lbl, im in scaled:
            sheet.paste(im, (x, 18)); dr.text((x + 3, 3), lbl, fill=(230, 230, 230)); x += im.width + 8
        sheet.save(OUT / "sheet.jpg", quality=88)
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"{len(results['failures'])} failure(s) → {OUT / 'results.json'}, {OUT / 'sheet.jpg'}", flush=True)
        return 1 if results["failures"] else 0
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
