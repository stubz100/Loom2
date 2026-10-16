"""D91: the sample models accepted on the rig, through the app's API — Klein 4B (the default), Lumina Image 2.0 and SD 3.5 Medium.

Per sample model (`/capabilities.sample_models`, the full build) with the engine restarted (cold):
  `style`   the style sample — `config.STYLE_SAMPLE_PROMPT` at the model's `sample_px.style`, square: once cold, twice warm (other seeds);
  `swatch`  three preset swatches through the real route — Settings › Samples › Sample model set to the model, then
            `POST /preset-icons/make` (lighting · mood · style, one value each, unstaged) at its `sample_px.swatch`;
  `draft`   one Generate job at Draft 960×544 (the style prompt), warm;
  `refine`  a Refine at 0.3 on a bench frame for the sample models that declare i2i (SD 3.5 Medium): the layout similarity to the
            source (1 − the 32×32 greyscale correlation distance, as cr_acceptance.py).
Wall seconds per job, the engine's peak VRAM (total − free from /system_stats, sampled every 0.5 s) per job kind, the output sane (the
size, not black or flat). Bars: peak ≤ 14.5 GB (the 16 GB card with `--reserve-vram` and the editor's headroom), every job done.
The images are saved under engine/spikes/out/sm/ for the author's look; results append to engine/spikes/out/sm/results.jsonl.

Needs port 8188 free (the orchestrator starts the engine) and the weights on F: (scripts/fetch_weights.py --only sm).

    orchestrator/.venv/Scripts/python.exe scripts/sm_acceptance.py [--models id,id] [--parts style,swatch,draft,refine]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "orchestrator"))

import cr_acceptance as cr  # noqa: E402  (the API helpers, the VRAM sampler, the sanity and layout checks)

cr.PORT, cr.TOKEN = 8779, "sm"
OUT = ROOT / "engine" / "spikes" / "out" / "sm"
DRAFT = (960, 544)
SWATCHES = [("lighting", "golden hour"), ("mood", "eerie"), ("style", "ink wash")]
BARS = {"peak_gb": 14.5, "keep_at_0_3": 0.8}
api, log = cr.api, cr.log


def run(recipe: dict) -> dict:
    j = api("POST", "/jobs", {"recipe": recipe})["jobs"][0]
    return cr.wait_jobs([j["id"]])[0]


def save(proj: Path, j: dict, name: str) -> Image.Image:
    img = cr.asset_image(proj, j["result"]["asset_ids"][0])
    img.save(OUT / name)
    return img


def model_part(m: dict, parts: str, check, proj: Path, vram: cr.VramSampler, caps: dict) -> dict:
    from loom2.config import STYLE_SAMPLE_PROMPT
    mid, res = m["id"], {"label": m["label"], "style_px": m["style_px"], "swatch_px": m["swatch_px"]}
    cr.restart_engine()
    if "style" in parts:
        px = m["style_px"]
        times, peaks = [], []
        for i, seed in enumerate((90, 91, 92)):
            vram.mark()
            j = run({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": STYLE_SAMPLE_PROMPT, "width": px, "height": px, "seeds": [seed]})
            ok = j["status"] == "done"
            check(ok, f"{mid} style sample s{seed}: {j['status']} {j.get('error') or ''}")
            if not ok:
                continue
            img = save(proj, j, f"{mid}_style_s{seed}.png")
            check(cr.sane(img, (px, px)), f"{mid} style sample s{seed}: {img.size}, not black or flat")
            times.append(float(j["wall_s"]))
            peaks.append(vram.window())
            log(f"  {mid} style {px}² s{seed}: {j['wall_s']} s{' (cold)' if i == 0 else ''}, peak {peaks[-1]} GB")
        if times:
            res["style"] = {"cold_s": times[0], "warm_s": round(sum(times[1:]) / len(times[1:]), 1) if len(times) > 1 else None, "peak_gb": max(peaks), "times": times}
    if "swatch" in parts:
        api("PUT", "/settings", {"samples": {"model_id": None if m["default"] else mid}})
        vram.mark()
        made = api("POST", "/preset-icons/make", {"items": [{"field": f, "value": v} for f, v in SWATCHES], "stage": False})
        check(all(j["recipe"]["model_id"] == mid for j in made["jobs"]), f"{mid}: the swatch route ran the Settings › Samples model")
        jobs = cr.wait_jobs([j["id"] for j in made["jobs"]])
        times = []
        for (field, value), j in zip(SWATCHES, jobs):
            ok = j["status"] == "done"
            check(ok, f"{mid} swatch {field}={value}: {j['status']} {j.get('error') or ''}")
            if not ok:
                continue
            img = save(proj, j, f"{mid}_swatch_{field}.png")
            check(cr.sane(img, (m["swatch_px"],) * 2), f"{mid} swatch {field}: {img.size}, not black or flat")
            times.append(float(j["wall_s"]))
        icons = {(i["field"], i["value"]): i for i in api("GET", "/preset-icons")["items"]}
        check(all(icons.get(s, {}).get("model_id") == mid for s in SWATCHES), f"{mid}: the three swatches stored with the model as lineage")
        res["swatch"] = {"times": times, "warm_s": round(sum(times) / len(times), 1) if times else None, "peak_gb": vram.window()}
        log(f"  {mid} swatches {m['swatch_px']}²: {times} s, peak {res['swatch']['peak_gb']} GB")
    if "draft" in parts:
        vram.mark()
        j = run({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": STYLE_SAMPLE_PROMPT, "width": DRAFT[0], "height": DRAFT[1], "seeds": [90]})
        check(j["status"] == "done", f"{mid} Generate draft: {j['status']} {j.get('error') or ''}")
        if j["status"] == "done":
            img = save(proj, j, f"{mid}_draft.png")
            check(cr.sane(img, DRAFT), f"{mid} Generate draft: {img.size}, not black or flat")
            res["draft"] = {"warm_s": float(j["wall_s"]), "peak_gb": vram.window()}
            log(f"  {mid} draft {DRAFT}: {j['wall_s']} s, peak {res['draft']['peak_gb']} GB")
    if "refine" in parts and caps["models"][mid]["recipes"]["i2i"] and not m["default"]:
        a_ = api("POST", "/assets/import", {"paths": [str(cr.FRAMES[0])]})["items"][0]
        src = Image.open(cr.FRAMES[0]).convert("RGB")
        d = api("POST", "/documents", {"from_asset": a_["id"], "name": f"sm-{mid}"})
        vram.mark()
        recipe = {"kind": "i2i", "model_id": mid, "source": "visible", "strength": 0.3, "prompt_text": "", "seeds": [1]}
        j = cr.wait_jobs([x["id"] for x in api("POST", f"/documents/{d['id']}/ai", {"recipe": recipe})["jobs"]])[0]
        ok = j["status"] == "done" and (j.get("result") or {}).get("layers")
        check(bool(ok), f"{mid} refine @ 0.3: {j['status']} {j.get('error') or ''}")
        if ok:
            lid = j["result"]["layers"][0]
            img = Image.open(io.BytesIO(api("GET", f"/documents/{d['id']}/layers/{lid}/pixels", raw=True))).convert("RGB").resize(src.size)
            img.save(OUT / f"{mid}_refine_0.3.png")
            sim = cr.layout_sim(src, img)
            res["refine"] = {"layout_sim": sim, "wall_s": float(j["wall_s"]), "peak_gb": vram.window()}
            check(sim >= BARS["keep_at_0_3"], f"{mid}: Refine 0.3 keeps the composition (layout {sim}, bar ≥ {BARS['keep_at_0_3']})")
            log(f"  {mid} refine 0.3: layout {sim}, {j['wall_s']} s, peak {res['refine']['peak_gb']} GB")
    peaks = [v["peak_gb"] for v in res.values() if isinstance(v, dict) and v.get("peak_gb") is not None]
    if peaks:
        check(max(peaks) <= BARS["peak_gb"], f"{mid}: peak VRAM {max(peaks)} GB (bar ≤ {BARS['peak_gb']} GB)")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="style,swatch,draft,refine")
    ap.add_argument("--models", default="", help="comma-separated model ids (default: every sample model of the full build)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://{cr.ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)")
        return 2
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="loom2-sm-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full"})
    env = {**os.environ, "LOOM2_TOKEN": cr.TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(cr.PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"),
                            env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    log(f"orchestrator on {cr.PORT}, state {tmp}")
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "parts": a.parts, "models": {}}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    vram = cr.VramSampler()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:
                time.sleep(0.3)
        proj = tmp / "proj"
        api("POST", "/project", {"path": str(proj), "name": "SM", "size_cap_gb": 20})
        api("POST", "/queue/unpause", {})
        caps = api("GET", "/capabilities")
        sample = [m for m in caps["sample_models"] if not a.models or m["id"] in a.models.split(",")]
        for m in sample:
            check(m["health"] in ("present", "verified"), f"{m['id']}: a sample model, weights {m['health']}")
        for m in sample:
            if m["health"] in ("present", "verified"):
                row["models"][m["id"]] = model_part(m, a.parts, check, proj, vram, caps)
    except Exception as e:  # noqa: BLE001
        check(False, f"exception: {type(e).__name__}: {e}")
    finally:
        vram.stop = True
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=30)
        except Exception:
            orch.kill()
        orch_log.close()
        shutil.rmtree(tmp, ignore_errors=True)
    row["failures"] = failures
    (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(row, default=str) + "\n")
    print(json.dumps(row, indent=1, default=str))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
