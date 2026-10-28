"""D151's rig: the AI tab's Instruct operation through the app — Qwen-Image-Edit 2509 fp8 + Lightning without the angles LoRA on the
document's visible composite, an instruction, a new layer back at the source's size. Two pictures (the inpaint bench's alley at 960×544,
the i2v bench's fish market at 832×480), two instructions each, one seed; per job the wall seconds and the engine's node times, the
peak VRAM over the run, the layer's size against the document's; a sheet (the source, then each result) for a look.

Bars: a warm job ≤ 45 s (E12: 31.6 s at 1 MP with the angles LoRA), the peak ≤ 15.5 GB, every result layer the document's size.

    orchestrator/.venv/Scripts/python.exe scripts/instruct_rig.py [--seed 7]

Results: engine/spikes/out/instruct/results.json, sheet.jpg. One GPU job at a time (serial through the queue).
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from PIL import Image, ImageDraw  # noqa: E402

PORT = 8776
TOKEN = "instructtoken"
OUT = ROOT / "engine" / "spikes" / "out" / "instruct"
PICTURES = [ROOT / "bench" / "inpaint" / "source.png", ROOT / "bench" / "i2v" / "frames" / "fish-market_s20261004.png"]
INSTRUCTIONS = ["make it dusk, the lamps lit, a warm light from the windows", "snow falling, the ground and the roofs white"]
BAR_WARM_S, BAR_PEAK_GB = 45.0, 15.5


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
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
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    import cr_acceptance as cr
    from m1_acceptance import port_busy
    from loom2.config import AppState
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-instruct-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "seed": a.seed, "jobs": [], "failures": []}
    vram = cr.VramSampler()
    tiles: list[tuple[str, Image.Image]] = []

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
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "Instruct", "size_cap_gb": 20})
        caps = api("GET", "/capabilities")["instruct"]
        model = caps["default"]
        check(bool(model) and caps["models"][model]["health"] != "missing", f"the edit-by-instruction model is offered with its weights ({model}: {caps['models'].get(model, {}).get('health')})")
        results["model"] = model
        vram.mark()
        for pic in PICTURES:
            asset = api("POST", "/assets/import", {"paths": [str(pic)]})["items"][0]["id"]
            doc = api("POST", "/documents", {"from_asset": asset, "name": pic.stem})
            did, W, H = doc["id"], doc["w"], doc["h"]
            tiles.append((f"{pic.stem} {W}×{H}", Image.open(pic).convert("RGB")))
            for text in INSTRUCTIONS:
                t1 = time.time()
                jobs = api("POST", f"/documents/{did}/ai", {"recipe": {"kind": "instruct", "prompt_text": text, "seeds": [a.seed]}})["jobs"]
                j = wait_job(jobs[0]["id"])
                wall = round(time.time() - t1, 1)
                row = {"picture": pic.name, "instruction": text, "status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": wall, "node_times": j.get("node_times"), "error": j.get("error")}
                results["jobs"].append(row)
                check(j["status"] == "done", f"{pic.stem} · {text[:28]}…: {j['status']} in {j.get('wall_s')} s {j.get('error') or ''}")
                if j["status"] != "done":
                    tiles.append((f"failed: {text[:24]}", Image.new("RGB", (W, H), (60, 20, 20))))
                    continue
                lid = (j.get("result") or {}).get("layers", [None])[0]
                d = api("GET", f"/documents/{did}")
                layer = next((n for n in d.get("layers", []) for n in ([n] + n.get("children", []))if n.get("id") == lid), None)
                png = api("GET", f"/documents/{did}/layers/{lid}/pixels", raw=True)
                im = Image.open(io.BytesIO(png)).convert("RGB")
                row["layer"] = {"id": lid, "size": [im.width, im.height], "name": layer.get("name") if layer else None}
                check((im.width, im.height) == (W, H), f"the result layer is the document's size ({im.width}×{im.height} against {W}×{H})")
                tiles.append((text[:30], im))
        peak = vram.window()
        results["peak_gb"] = peak
        warm = [r["wall_s"] for r in results["jobs"][1:] if r.get("wall_s")]
        check(bool(warm) and max(warm) <= BAR_WARM_S, f"a warm job ≤ {BAR_WARM_S:g} s (warm {warm}, the first {results['jobs'][0].get('wall_s') if results['jobs'] else None} s cold)")
        check(peak <= BAR_PEAK_GB, f"peak VRAM {peak} GB (bar ≤ {BAR_PEAK_GB} GB)")
        # the sheet: each picture then its results, scaled to a 420 px height
        hh = 420
        scaled = [(lbl, im.resize((round(im.width * hh / im.height), hh))) for lbl, im in tiles]
        sheet = Image.new("RGB", (sum(im.width + 8 for _, im in scaled), hh + 18), (24, 24, 24))
        d = ImageDraw.Draw(sheet)
        x = 0
        for lbl, im in scaled:
            sheet.paste(im, (x, 18)); d.text((x + 3, 3), lbl, fill=(230, 230, 230)); x += im.width + 8
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
