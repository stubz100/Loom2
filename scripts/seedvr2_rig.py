"""D153's rig: SeedVR2 3B as the Upscale tool runs it — through the app (a temporary orchestrator, the real engine on 8188): a document from
the bench's alley board (960×544), Upscale with the default model (SeedVR2 ×2 → a Catalogue asset at 1920×1088), the same with the cheap
one (Real-ESRGAN ×2 — the second choice still works), then SeedVR2 ×2 + the tiled refine (Klein base, tile 1024 / 128, strength 0.25).
Seconds and peak VRAM per job; a sheet of the three results' crops beside the source.

Bars: every job done with an asset at twice the size; the plain SeedVR2 ×2 warm ≤ 20 s (E40 measured 7–8; the app's path adds the
document's read and the asset's write) and peak ≤ 15.5 GB; the refined one done inside 10 min.

    orchestrator/.venv/Scripts/python.exe scripts/seedvr2_rig.py

Results: engine/spikes/out/seedvr2/results.json, sheet.jpg. One GPU job at a time (rule 10).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]

PORT = 8782
TOKEN = "seedvr2token"
OUT = ROOT / "engine" / "spikes" / "out" / "seedvr2"
BOARD = next((ROOT / "bench" / "i2v" / "frames").glob("alley-rain_s*.png"))
BAR_WARM_S, BAR_PEAK_GB, BAR_REFINE_S = 20.0, 15.5, 600.0
CROP = 420


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


def crop(im: Image.Image, rel=(0.62, 0.38)) -> Image.Image:
    x = int(min(max(im.width * rel[0] - CROP / 2, 0), im.width - CROP)); y = int(min(max(im.height * rel[1] - CROP / 2, 0), im.height - CROP))
    return im.crop((x, y, x + CROP, y + CROP))


def main() -> int:
    import cr_acceptance as cr
    from m1_acceptance import port_busy
    from loom2.config import AppState
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-seedvr2-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "board": BOARD.name, "jobs": [], "failures": []}
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
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "SeedVR2", "size_cap_gb": 20})
        caps = api("GET", "/capabilities")
        default = caps["defaults"]["upscale"]
        cheap = next((i for i, t in caps["tools"].items() if t["graph"] == "esrgan" and t["recipes"]["upscale_factor"] == 2), None)
        refine_model = caps["defaults"]["i2i"]
        results |= {"default_upscale": default, "cheap": cheap, "refine_model": refine_model, "tool": caps["tools"].get(default)}
        check(caps["tools"].get(default, {}).get("graph") == "seedvr2", f"the default upscaler is SeedVR2 ({default}: {caps['tools'].get(default, {}).get('label')}, health {caps['tools'].get(default, {}).get('health')})")
        src_id = api("POST", "/assets/import", {"paths": [str(BOARD)]})["items"][0]["id"]
        doc = api("POST", "/documents", {"from_asset": src_id, "name": "alley"})
        did, W, H = doc["id"], doc["w"], doc["h"]
        source = Image.open(BOARD).convert("RGB")
        tiles.append(("source 960×544 (lanczos ×2)", crop(source.resize((W * 2, H * 2), Image.Resampling.LANCZOS))))
        vram.mark()
        runs = [("SeedVR2 ×2 (the default)", {"kind": "upscale", "model_id": default, "source": "visible", "as_layer": False, "seeds": [0]}),
                ("SeedVR2 ×2 again (warm)", {"kind": "upscale", "model_id": default, "source": "visible", "as_layer": False, "seeds": [0]}),
                ("Real-ESRGAN ×2 (the cheap one)", {"kind": "upscale", "model_id": cheap, "source": "visible", "as_layer": False, "seeds": [0]}),
                ("SeedVR2 ×2 + tiled refine", {"kind": "upscale", "model_id": default, "source": "visible", "as_layer": False, "seeds": [0], "refine": True, "refine_model_id": refine_model,
                                               "strength": 0.25, "tile": 1024, "overlap": 128, "prompt_text": "a rain-soaked alley at night, a young woman in a green hooded cloak"})]
        for label, recipe in runs:
            if recipe.get("model_id") is None:
                results["jobs"].append({"label": label, "status": "skipped"}); continue
            prev = api("POST", "/recipes/preview", {"recipe": {**recipe, "document_id": did}}) if label.startswith("SeedVR2 ×2 (") else None
            vram.mark()
            t1 = time.time()
            job = api("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]
            j = wait_job(job["id"])
            peak = vram.window()
            res = j.get("result") or {}
            aid = (res.get("asset_ids") or [None])[0]
            size = None
            if aid:
                a = api("GET", f"/assets/{aid}")
                size = [a.get("w"), a.get("h")]
                png = api("GET", f"/assets/{aid}/file", raw=True)
                im = Image.open(io.BytesIO(png)).convert("RGB")
                im.save(OUT / f"{label.split(' (')[0].replace(' ', '_').replace('×', 'x').replace('+', 'plus')}.png")
                tiles.append((f"{label} · {j.get('wall_s')} s", crop(im)))
            row = {"label": label, "status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "peak_gb": peak, "asset": aid, "size": size,
                   "node_times": j.get("node_times"), "error": j.get("error"), "preview": (prev or {}).get("estimate") if prev else None}
            results["jobs"].append(row)
            check(j["status"] == "done" and size == [W * 2, H * 2], f"{label}: {j['status']} in {j.get('wall_s')} s, asset {size}, peak {peak} GB {j.get('error') or ''}")
        rows = {r["label"]: r for r in results["jobs"]}
        warm = rows.get("SeedVR2 ×2 again (warm)", {})
        check(bool(warm.get("wall_s")) and warm["wall_s"] <= BAR_WARM_S, f"the plain SeedVR2 ×2 warm ≤ {BAR_WARM_S:g} s ({warm.get('wall_s')} s; the first {rows.get('SeedVR2 ×2 (the default)', {}).get('wall_s')} s)")
        peaks = [r["peak_gb"] for r in results["jobs"] if r.get("peak_gb")]
        check(bool(peaks) and max(peaks) <= BAR_PEAK_GB, f"peak VRAM ≤ {BAR_PEAK_GB} GB ({peaks})")
        ref = rows.get("SeedVR2 ×2 + tiled refine", {})
        check(ref.get("status") == "done" and (ref.get("wall_s") or 1e9) <= BAR_REFINE_S, f"the refined one inside {BAR_REFINE_S:g} s ({ref.get('wall_s')} s)")
        sheet = Image.new("RGB", (len(tiles) * (CROP + 6), CROP + 20), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for i, (lbl, im) in enumerate(tiles):
            sheet.paste(im, (i * (CROP + 6), 18)); dr.text((i * (CROP + 6) + 3, 3), lbl, fill=(230, 230, 230))
        sheet.save(OUT / "sheet.jpg", quality=90)
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
