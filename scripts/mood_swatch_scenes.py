"""D92 follow-up: which scene lets the eight mood swatches look different? (The author: the four dark moods — tense, melancholic, eerie,
lonely — are hard to tell apart on "an empty street corner, {value} mood".)

A temporary orchestrator (its own state, the default sample model — `/capabilities.defaults.swatch`, Klein 4B, D91 — at its swatch size)
opens a scratch project and, per candidate scene, sets Settings › Samples' mood scene (`PUT /settings`) and makes the eight built-in moods
through the real route (`POST /preset-icons/make`, run now) on the pack's seed and two more. Per scene and seed the variety among the
eight and among the four dark ones (D89's pixel proxies: mean pairwise layout distance = 1 − the correlation of 32 × 32 greyscale
thumbnails, colour = mean ΔE of 8 × 8 Lab) and the nearest pair; per scene the means over the seeds. A contact sheet per seed (rows the
scenes, columns the moods) goes to engine/spikes/out/mood/sheet_s<seed>.png, a JSON line to engine/spikes/out/mood/results.jsonl. The
app's own state is not touched (installing the chosen scene's swatches is `scripts/swatch_pack.py --only "mood=…;…"` after the default
moved).

The layout proxy z-normalises each thumbnail, which turns the faint differences between near-black swatches into large distances (two
dark street corners that look the same score as far apart as a dark and a bright one), so two structural measures are added: 1 − SSIM
on 128² greyscale (local means, contrasts and structure; 7 × 7 windows) and the mean absolute luminance difference (0–255) — both
reported for the eight and for the four dark ones. `--rescore` recomputes every score from the PNGs a run left in the output folder.

    orchestrator/.venv/Scripts/python.exe scripts/mood_swatch_scenes.py [--seeds 90,91,92] [--rescore]
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
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "orchestrator"))

import cr_acceptance as cr  # noqa: E402  (the API helpers, the VRAM sampler, the pixel proxies)

cr.PORT, cr.TOKEN = 8783, "mood"
OUT = ROOT / "engine" / "spikes" / "out" / "mood"
MOODS = ["tense", "melancholic", "hopeful", "eerie", "serene", "triumphant", "lonely", "playful"]   # library_seed.json's moods
DARK = ["tense", "melancholic", "eerie", "lonely"]
SCENES = {
    "corner": "an empty street corner, {value} mood",                                                    # the default before (D90)
    "face": "close-up portrait of a person's face and shoulders, {value} mood, the expression and the light show it",
    "room": "a single person in a sparse room by a window, full figure, {value} mood, the posture and the light show it",
    "landscape": "a wide open landscape with a road under a big sky, {value} mood, the weather and the light show it",
    "quay": "a lone figure on a harbour quay, wide shot, {value} mood, the weather, the light and the posture show it",
}
api, log = cr.api, cr.log


def _box(a: np.ndarray, k: int = 7) -> np.ndarray:
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def ssim(a: Image.Image, b: Image.Image) -> float:
    """Mean SSIM of two images as 128² greyscale (7 × 7 box windows, the usual constants for 0–255)."""
    x, y = (np.asarray(i.convert("L").resize((128, 128), Image.BILINEAR), dtype=np.float64) for i in (a, b))
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = _box(x), _box(y)
    vx, vy, cxy = _box(x * x) - mx * mx, _box(y * y) - my * my, _box(x * y) - mx * my
    return float(np.mean(((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))))


def structure(imgs: list[Image.Image]) -> tuple[float, float]:
    """Mean pairwise 1 − SSIM and mean absolute luminance difference (32², 0–255)."""
    pairs = list(itertools.combinations(imgs, 2))
    lum = lambda i: np.asarray(i.convert("L").resize((32, 32), Image.BILINEAR), dtype=np.float64)  # noqa: E731
    return (round(float(np.mean([1 - ssim(a, b) for a, b in pairs])), 3), round(float(np.mean([np.abs(lum(a) - lum(b)).mean() for a, b in pairs])), 1))


def scores(imgs: dict[str, Image.Image]) -> dict:
    """The variety among all eight and the four dark ones, and the nearest pair of the eight (layout and colour together)."""
    allv, dark = cr.variety([imgs[m] for m in MOODS]), cr.variety([imgs[m] for m in DARK])
    pair = []
    for a, b in itertools.combinations(MOODS, 2):
        lay = 1 - cr.layout_sim(imgs[a], imgs[b])
        col = float(np.mean(np.linalg.norm(cr.lab8(imgs[a]) - cr.lab8(imgs[b]), axis=1)))
        pair.append((round(lay, 3), round(col, 1), f"{a}~{b}"))
    near_l = min(pair, key=lambda t: t[0])
    near_c = min(pair, key=lambda t: t[1])
    (all_ssim, all_lum), (dark_ssim, dark_lum) = structure([imgs[m] for m in MOODS]), structure([imgs[m] for m in DARK])
    near_s = min(((round(1 - ssim(imgs[a], imgs[b]), 3), f"{a}~{b}") for a, b in itertools.combinations(MOODS, 2)), key=lambda t: t[0])
    return {"all_layout": allv["layout_distance"], "all_colour": allv["colour_distance"], "dark_layout": dark["layout_distance"],
            "dark_colour": dark["colour_distance"], "nearest_layout": near_l, "nearest_colour": near_c,
            "all_1-ssim": all_ssim, "dark_1-ssim": dark_ssim, "all_lum": all_lum, "dark_lum": dark_lum, "nearest_1-ssim": near_s}


KEYS = ("all_layout", "all_colour", "dark_layout", "dark_colour", "all_1-ssim", "dark_1-ssim", "all_lum", "dark_lum")


def rescore(seeds: list[int], names: list[str]) -> dict:
    """Every score again from the PNGs a run left (no engine)."""
    out: dict = {}
    for n in names:
        per = [scores({m: Image.open(OUT / f"{n}_{m}_s{seed}.png").convert("RGB") for m in MOODS}) for seed in seeds]
        out[n] = {k: round(float(np.mean([x[k] for x in per])), 3) for k in KEYS} | {"nearest_1-ssim": [x["nearest_1-ssim"] for x in per]}
    return out


def sheet(rows: dict[str, dict[str, Image.Image]], path: Path, cell: int = 150) -> None:
    lab = 92
    s = Image.new("RGB", (lab + len(MOODS) * cell, 18 + len(rows) * cell), (24, 24, 24))
    d = ImageDraw.Draw(s)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    for c, m in enumerate(MOODS):
        d.text((lab + c * cell + 4, 3), m + (" *" if m in DARK else ""), fill=(240, 180, 60) if m in DARK else (220, 220, 220), font=font)
    for r, (name, imgs) in enumerate(rows.items()):
        d.text((4, 18 + r * cell + cell // 2 - 6), name, fill=(220, 220, 220), font=font)
        for c, m in enumerate(MOODS):
            if m in imgs:
                s.paste(imgs[m].resize((cell - 4, cell - 4)), (lab + c * cell + 2, 18 + r * cell + 2))
    s.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="90,91,92")
    ap.add_argument("--scenes", default=",".join(SCENES))
    ap.add_argument("--rescore", action="store_true", help="the scores again from the saved PNGs (no engine)")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",") if x]
    names = [x for x in a.scenes.split(",") if x]
    if a.rescore:
        res = rescore(seeds, names)
        print(json.dumps(res, indent=1))
        (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M"), "rescore": res, "seeds": seeds}) + "\n")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://{cr.ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it first")
        return 2
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="loom2-mood-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full"})
    env = {**os.environ, "LOOM2_TOKEN": cr.TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(cr.PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"),
                            env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "seeds": seeds, "scenes": {n: SCENES[n] for n in names}}
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
        api("POST", "/project", {"path": str(proj), "name": "Mood scenes", "size_cap_gb": 20})
        api("POST", "/queue/unpause", {})
        caps = api("GET", "/capabilities")
        model = next(m for m in caps["sample_models"] if m["default"])
        row["model"], row["px"] = model["id"], model["swatch_px"]
        log(f"{len(names)} scenes × {len(MOODS)} moods × {len(seeds)} seeds on {model['id']} at {model['swatch_px']}²")
        vram.mark()
        per: dict[str, list[dict]] = {n: [] for n in names}
        times: list[float] = []
        for seed in seeds:
            rows: dict[str, dict[str, Image.Image]] = {}
            for n in names:
                s = api("PUT", "/settings", {"samples": {"swatch_prompts": {"mood": SCENES[n]}}})
                if s["samples"]["swatch_prompts"]["mood"] != SCENES[n]:
                    failures.append(f"{n}: the scene was not taken")
                made = api("POST", "/preset-icons/make", {"items": [{"field": "mood", "value": m} for m in MOODS], "stage": False, "seed": seed})
                jobs = cr.wait_jobs([j["id"] for j in made["jobs"]])
                imgs = {}
                for m, j in zip(MOODS, jobs):
                    if j["status"] != "done":
                        failures.append(f"{n} {m} s{seed}: {j['status']} {j.get('error') or ''}")
                        continue
                    if j["recipe"]["prompt_text"] != SCENES[n].replace("{value}", m):
                        failures.append(f"{n} {m}: the job ran {j['recipe']['prompt_text']!r}")
                    times.append(float(j["wall_s"]))
                    im = cr.asset_image(proj, j["result"]["asset_ids"][0])
                    im.save(OUT / f"{n}_{m}_s{seed}.png")
                    imgs[m] = im
                rows[n] = imgs
                if len(imgs) == len(MOODS):
                    sc = scores(imgs)
                    per[n].append(sc)
                    log(f"  s{seed} {n}: {sc}")
            sheet(rows, OUT / f"sheet_s{seed}.png")
        summary = {}
        for n, scs in per.items():
            if scs:
                summary[n] = {k: round(float(np.mean([s[k] for s in scs])), 3) for k in KEYS}
                summary[n]["nearest"] = [s["nearest_layout"] for s in scs]
        row |= {"summary": summary, "per_seed": per, "per_job_s": round(sum(times) / len(times), 2) if times else None, "peak_gb": vram.window()}
    except Exception as e:  # noqa: BLE001
        failures.append(f"exception: {type(e).__name__}: {e}")
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
    print(json.dumps({k: v for k, v in row.items() if k != "per_seed"}, indent=1, default=str))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
