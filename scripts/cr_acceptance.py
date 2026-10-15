"""CR6 (D89, `.docs/creative_image/04` §6): the creative t2i / i2i models accepted on the rig, through the app's API.

`t2i`: per Generate model (Krea 2 Turbo / Raw, Z-Image, Chroma1-HD) the engine restarted (cold), then three bench prompts (01 alley rain,
06 fish market, 07 portrait grief — the BFL trees, flattened to prose for these models) × 2 seeds at Draft 960×544: cold and warm wall
seconds, the engine's peak VRAM (sampled from /system_stats), the output sane (the size, not black or flat). Bars: warm ≤ 60 s for
the distilled Turbo, ≤ 180 s for the base models; peak ≤ 14.5 GB.

`variety`: one prompt × 8 seeds at Thumb on each Generate model and on Klein 9B and FLUX.2 dev as the baseline — the mean pairwise
layout distance (1 − the correlation of 32×32 greyscale thumbnails) and colour distance (mean ΔE of 8×8 Lab thumbnails). Recorded, no
bar (no DINO here: these are pixel proxies, said so in the journal).

`i2i`: per Refine model (Krea 2 Raw, Z-Image, Chroma1-HD, SD 3.5 Large) a document from a bench frame, Refine at 0.3 / 0.55 / 0.75 →
the layout similarity to the source (the same proxy): 0.3 keeps the composition (≥ 0.8), 0.75 re-imagines it (recorded). `turbo`:
Krea 2 Turbo's partial denoise probed outside the app (its spec has no i2i; the graph compiled with i2i on, sent to the engine).

`zimage-dtype`: Z-Image bf16 as stored vs cast to fp8_e4m3fn — peak and time.

`krea-size`: Krea 2 Turbo at 960×544 vs 1280×720, same seed — the two images saved for the author's look.

Needs port 8188 free (the orchestrator starts the engine) and the wave's weights on F: (scripts/fetch_weights.py --only cr). Results:
engine/spikes/out/cr/results.jsonl, the images under engine/spikes/out/cr/, the orchestrator log.

    orchestrator/.venv/Scripts/python.exe scripts/cr_acceptance.py [--parts t2i,variety,i2i,turbo,krea-size]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

PORT, TOKEN, ENGINE = 8778, "cr", "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "cr"
PROMPTS = ["01-alley-rain", "06-fish-market", "07-portrait-grief"]
FRAMES = [ROOT / "bench" / "inpaint" / "source.png", ROOT / "bench" / "angles" / "03.jpg", ROOT / "bench" / "angles" / "07.jpg"]
DRAFT, THUMB = (960, 544), (896, 512)
BARS = {"warm_distilled_s": 60.0, "warm_base_s": 180.0, "peak_gb": 14.5, "keep_at_0_3": 0.8}
BASELINES = ["klein-9b", "flux2-dev-fp8mixed"]


def api(method: str, path: str, body=None, raw: bool = False, timeout: float = 600):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class VramSampler:
    """The engine's VRAM in use (total − free from /system_stats), sampled every 0.5 s; `window()` gives the peak since `mark()`."""
    def __init__(self) -> None:
        self.peak = 0.0
        self.stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while not self.stop:
            try:
                with urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2) as r:
                    d = json.loads(r.read())["devices"][0]
                self.peak = max(self.peak, (d["vram_total"] - d["vram_free"]) / 2**30)
            except Exception:
                pass
            time.sleep(0.5)

    def mark(self) -> None:
        self.peak = 0.0

    def window(self) -> float:
        return round(self.peak, 2)


def wait_jobs(ids: list[str], timeout_s: float = 3600) -> list[dict]:
    t0, last = time.time(), ""
    while time.time() - t0 < timeout_s:
        jobs = {j["id"]: j for j in api("GET", "/jobs")["items"]}
        mine = [jobs[i] for i in ids if i in jobs]
        if mine and all(j["status"] in ("done", "failed", "cancelled") for j in mine):
            return mine
        run = next((j for j in mine if j["status"] == "running"), None)
        msg = f"{run.get('progress_text')} {round((run.get('progress') or 0) * 100)}%" if run else "queued"
        if msg != last:
            log(f"    … {msg}")
            last = msg
        time.sleep(1.0)
    raise TimeoutError(ids)


def asset_image(proj: Path, asset_id: str) -> Image.Image:
    a = api("GET", f"/assets/{asset_id}")
    return Image.open(proj / a["path"]).convert("RGB")


def sane(img: Image.Image, size: tuple[int, int]) -> bool:
    arr = np.asarray(img, dtype=np.float32)
    return bool(img.size == size and arr.mean() > 3 and arr.std() > 4 and np.isfinite(arr).all())


def layout(img: Image.Image) -> np.ndarray:
    v = np.asarray(img.convert("L").resize((32, 32), Image.BILINEAR), dtype=np.float32).ravel()
    return (v - v.mean()) / (v.std() + 1e-6)


def layout_sim(a: Image.Image, b: Image.Image) -> float:
    return round(float(np.mean(layout(a) * layout(b))), 3)


def lab8(img: Image.Image) -> np.ndarray:
    return np.asarray(img.resize((8, 8), Image.BILINEAR).convert("LAB"), dtype=np.float32).reshape(-1, 3)


def variety(imgs: list[Image.Image]) -> dict:
    pairs = list(itertools.combinations(range(len(imgs)), 2))
    lay = [1 - layout_sim(imgs[i], imgs[j]) for i, j in pairs]
    col = [float(np.mean(np.linalg.norm(lab8(imgs[i]) - lab8(imgs[j]), axis=1))) for i, j in pairs]
    return {"layout_distance": round(float(np.mean(lay)), 3), "colour_distance": round(float(np.mean(col)), 2), "n": len(imgs)}


def t2i_recipe(model_id: str, prompt: str, seed: int, size: tuple[int, int]) -> dict:
    tree = json.loads((ROOT / "bench" / "t2i" / f"{prompt}.json").read_text(encoding="utf-8"))
    return {"kind": "t2i", "model_id": model_id, "prompt_mode": "json", "prompt_json": tree, "width": size[0], "height": size[1], "seeds": [seed]}


def run_t2i(recipe: dict) -> dict:
    j = api("POST", "/jobs", {"recipe": recipe})["jobs"][0]
    return wait_jobs([j["id"]])[0]


def restart_engine() -> None:
    """A cold engine for the next model (its weights may still sit in the OS file cache — the cold figure is load + sampling)."""
    api("POST", "/engine/restart", {}, timeout=300)
    t0 = time.time()
    while time.time() - t0 < 300:
        if api("GET", "/engine").get("responding"):
            return
        time.sleep(1.0)


def t2i_part(models: list[str], check, row: dict, proj: Path, vram: VramSampler, caps: dict) -> None:
    out = OUT / "t2i"
    out.mkdir(parents=True, exist_ok=True)
    for mid in models:
        spec = caps["models"][mid]
        restart_engine()
        times, peaks = [], []
        for i, (prompt, seed) in enumerate(itertools.product(PROMPTS, (1, 2))):
            vram.mark()
            j = run_t2i(t2i_recipe(mid, prompt, seed, DRAFT))
            ok = j["status"] == "done"
            check(ok, f"{mid} {prompt} s{seed}: {j['status']} {j.get('error') or ''}")
            if not ok:
                continue
            img = asset_image(proj, j["result"]["asset_ids"][0])
            img.save(out / f"{mid}_{prompt}_s{seed}.png")
            check(sane(img, DRAFT), f"{mid} {prompt} s{seed}: {img.size}, not black or flat")
            times.append(float(j["wall_s"]))
            peaks.append(vram.window())
            log(f"  {mid} {prompt} s{seed}: {j['wall_s']} s{' (cold)' if i == 0 else ''}, peak {peaks[-1]} GB")
        if not times:
            continue
        warm = round(float(np.median(times[1:])) if len(times) > 1 else times[0], 1)
        bar = BARS["warm_distilled_s"] if spec["distilled"] else BARS["warm_base_s"]
        check(warm <= bar, f"{mid}: warm {warm} s (bar ≤ {bar} s), cold {times[0]} s")
        check(max(peaks) <= BARS["peak_gb"], f"{mid}: peak VRAM {max(peaks)} GB (bar ≤ {BARS['peak_gb']} GB)")
        row.setdefault("t2i", {})[mid] = {"cold_s": times[0], "warm_s": warm, "peak_gb": max(peaks), "times": times}


def variety_part(models: list[str], check, row: dict, proj: Path, caps: dict) -> None:
    out = OUT / "variety"
    out.mkdir(parents=True, exist_ok=True)
    for mid in models + [b for b in BASELINES if b in caps["models"]]:
        imgs = []
        for seed in range(1, 9):
            j = run_t2i(t2i_recipe(mid, PROMPTS[0], seed, THUMB))
            if j["status"] != "done":
                check(False, f"variety {mid} s{seed}: {j['status']} {j.get('error') or ''}")
                continue
            img = asset_image(proj, j["result"]["asset_ids"][0])
            img.save(out / f"{mid}_s{seed}.png")
            imgs.append(img)
        if len(imgs) >= 2:
            v = variety(imgs)
            row.setdefault("variety", {})[mid] = v
            log(f"  variety {mid}: {v}")


def i2i_part(models: list[str], check, row: dict, proj: Path, vram: VramSampler) -> None:
    out = OUT / "i2i"
    out.mkdir(parents=True, exist_ok=True)
    imported = api("POST", "/assets/import", {"paths": [str(p) for p in FRAMES]})["items"]
    sources = [Image.open(p).convert("RGB") for p in FRAMES]
    for mid in models:
        res: dict = {}
        restart_engine()
        for k, (a_, src) in enumerate(zip(imported, sources)):
            for s in ((0.3, 0.55, 0.75) if k == 0 else (0.55,)):
                # a fresh document per job: Refine reads the *visible* composite, and an earlier result layer would be the next job's input
                d = api("POST", "/documents", {"from_asset": a_["id"], "name": f"cr-{mid}-{k}-{s}"})
                vram.mark()
                recipe = {"kind": "i2i", "model_id": mid, "source": "visible", "strength": s, "prompt_text": "", "seeds": [1]}
                jobs = api("POST", f"/documents/{d['id']}/ai", {"recipe": recipe})["jobs"]
                j = wait_jobs([x["id"] for x in jobs])[0]
                ok = j["status"] == "done" and (j.get("result") or {}).get("layers")
                check(bool(ok), f"refine {mid} frame {k} @ {s}: {j['status']} {j.get('error') or ''}")
                if not ok:
                    continue
                lid = j["result"]["layers"][0]
                import io
                img = Image.open(io.BytesIO(api("GET", f"/documents/{d['id']}/layers/{lid}/pixels", raw=True))).convert("RGB").resize(src.size)
                img.save(out / f"{mid}_f{k}_{s}.png")
                sim = layout_sim(src, img)
                res[f"f{k}@{s}"] = {"layout_sim": sim, "wall_s": j["wall_s"], "peak_gb": vram.window()}
                log(f"  refine {mid} frame {k} @ {s}: layout {sim}, {j['wall_s']} s, peak {vram.window()} GB")
        keep = res.get("f0@0.3", {}).get("layout_sim")
        check(keep is not None and keep >= BARS["keep_at_0_3"], f"{mid}: strength 0.3 keeps the composition (layout {keep}, bar ≥ {BARS['keep_at_0_3']})")
        row.setdefault("i2i", {})[mid] = res


def turbo_part(check, row: dict, caps: dict) -> None:
    """Krea 2 Turbo's partial denoise: the I2I graph compiled with a spec copy that has i2i on, sent to the engine directly."""
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from e12_angles import Engine
    from loom2.engine import graphs
    from loom2.models import registry
    from loom2.recipes import I2I
    from loom2.roster import Roster
    turbo = next(m for m, c in caps["models"].items() if c["family"] == "krea2" and c["distilled"])
    spec = registry.SPECS[turbo]
    registry.SPECS[turbo] = spec.model_copy(update={"recipes": spec.recipes.model_copy(update={"i2i": True})})
    try:
        eng = Engine(ENGINE)
        name = eng.upload(FRAMES[0])
        src = Image.open(FRAMES[0]).convert("RGB")
        roster = Roster(Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")), []).scan()
        res = {}
        for s in (0.3, 0.55):
            c = graphs.build_i2i(I2I(document_id="d", model_id=turbo, strength=s), roster, 1, "loom2/cr-turbo", name, *src.size)
            h, wall, _ = eng.run(c.graph)
            img = eng.image(h, c.output_node).resize(src.size)
            img.save(OUT / f"turbo_i2i_{s}.png")
            res[str(s)] = {"layout_sim": layout_sim(src, img), "wall_s": round(wall, 1), "sane": sane(img, src.size)}
            log(f"  turbo i2i @ {s}: {res[str(s)]}")
        row["turbo_i2i"] = res
        check(all(r["sane"] for r in res.values()), "Krea 2 Turbo partial denoise returns sane images (the author judges the look)")
    finally:
        registry.SPECS[turbo] = spec


def krea_size_part(check, row: dict, proj: Path, caps: dict) -> None:
    turbo = next(m for m, c in caps["models"].items() if c["family"] == "krea2" and c["distilled"])
    out = OUT / "krea-size"
    out.mkdir(parents=True, exist_ok=True)
    for size in (DRAFT, (1280, 720)):
        j = run_t2i(t2i_recipe(turbo, PROMPTS[0], 1, size))
        check(j["status"] == "done", f"krea size {size}: {j['status']}")
        if j["status"] == "done":
            asset_image(proj, j["result"]["asset_ids"][0]).save(out / f"{size[0]}x{size[1]}.png")
            row.setdefault("krea_size", {})[f"{size[0]}x{size[1]}"] = j["wall_s"]


def zimage_dtype_part(check, row: dict, proj: Path, vram: VramSampler, caps: dict) -> None:
    """Z-Image bf16 at `default` vs cast to fp8_e4m3fn in UNETLoader (04 §6): the peak, the warm time, the images for the author's look."""
    z = next(m for m, c in caps["models"].items() if c["family"] == "zimage")
    out = OUT / "zimage-dtype"
    out.mkdir(parents=True, exist_ok=True)
    for dtype in ("default", "fp8_e4m3fn"):
        restart_engine()
        times, peaks = [], []
        for prompt in PROMPTS:
            vram.mark()
            j = run_t2i({**t2i_recipe(z, prompt, 1, DRAFT), "weight_dtype": dtype})
            check(j["status"] == "done", f"z-image {dtype} {prompt}: {j['status']} {j.get('error') or ''}")
            if j["status"] != "done":
                continue
            asset_image(proj, j["result"]["asset_ids"][0]).save(out / f"{dtype}_{prompt}.png")
            times.append(float(j["wall_s"]))
            peaks.append(vram.window())
        row.setdefault("zimage_dtype", {})[dtype] = {"times": times, "peak_gb": max(peaks) if peaks else None}
        log(f"  z-image dtype {dtype}: times {times}, peak {max(peaks) if peaks else None} GB")


def krea_te_part(check, row: dict, proj: Path, vram: VramSampler, caps: dict) -> None:
    """Krea 2 Raw on new prompts with its encoder on the GPU (swapped against the 13 GB transformer) vs on the CPU (the transformer stays)."""
    raw = next(m for m, c in caps["models"].items() if c["family"] == "krea2" and not c["distilled"])
    for dev in ("default", "cpu"):
        restart_engine()
        times, peaks = [], []
        for prompt in PROMPTS:                                                   # three different prompts: every job encodes anew
            vram.mark()
            j = run_t2i({**t2i_recipe(raw, prompt, 1, DRAFT), "te_device": dev})
            check(j["status"] == "done", f"krea raw te {dev} {prompt}: {j['status']} {j.get('error') or ''}")
            if j["status"] == "done":
                times.append(float(j["wall_s"]))
                peaks.append(vram.window())
        row.setdefault("krea_te", {})[dev] = {"times": times, "peak_gb": max(peaks) if peaks else None}
        log(f"  krea raw te {dev}: times {times}, peak {max(peaks) if peaks else None} GB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="t2i,variety,i2i,turbo,krea-size")
    ap.add_argument("--models", default="", help="comma-separated model ids (default: every D89 model)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)")
        return 2
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="loom2-cr-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full"})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"),
                            env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    log(f"orchestrator on {PORT}, state {tmp}")
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "parts": a.parts}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    vram = VramSampler()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:
                time.sleep(0.3)
        proj = tmp / "proj"
        api("POST", "/project", {"path": str(proj), "name": "CR", "size_cap_gb": 60})
        api("POST", "/queue/unpause", {})
        caps = api("GET", "/capabilities")
        wave = [m for m, c in caps["models"].items() if c["family"] in ("krea2", "zimage", "chroma", "sd3")]
        if a.models:
            wave = [m for m in wave if m in a.models.split(",")]
        for m in wave:
            c = caps["models"][m]
            check(c["health"] in ("present", "verified"), f"{m}: offered, weights {c['health']}")
        gen = [m for m in wave if caps["models"][m]["recipes"]["t2i"]]
        ref = [m for m in wave if caps["models"][m]["recipes"]["i2i"]]
        row["models"] = {"t2i": gen, "i2i": ref}
        if "t2i" in a.parts:
            t2i_part(gen, check, row, proj, vram, caps)
        if "variety" in a.parts:
            variety_part(gen, check, row, proj, caps)
        if "i2i" in a.parts:
            i2i_part(ref, check, row, proj, vram)
        if "turbo" in a.parts:
            turbo_part(check, row, caps)
        if "krea-te" in a.parts:
            krea_te_part(check, row, proj, vram, caps)
        if "zimage-dtype" in a.parts:
            zimage_dtype_part(check, row, proj, vram, caps)
        if "krea-size" in a.parts:
            krea_size_part(check, row, proj, caps)
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
