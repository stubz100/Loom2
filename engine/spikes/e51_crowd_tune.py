"""Spike E51 (D173's crowd content; journal 2026-10-31 15:25): the crowd's two steps through the jobs API on E47's copy — the right stall
front 3.2–14.4 m (the texture crop at 1088×480, E49's), Klein I2I 0.6 with `match_colour` (D48) on two seeds (41, 42), then from each start
the first = last frame loop on the default I2V model, Draft (C) and Motion (CM). Each clip's frames are tone-locked as the product does
(engine/tone.lock_loop, on copies) before they are measured: the people's motion (the mean step between frames over the lower 60 %), the
start's colour distance from the crop (mean ΔE, Lab), the seam; sheets. Outputs under engine/spikes/out/e51/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e51_crowd_tune.py
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
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from d173_rig import WORDS  # noqa: E402
from e47_faces import PID, PROJECT, STATE, VID  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e51"
PORT, TOKEN = 8766, "devtoken"
FACE, FROM, TO = "facade_right", 3.2, 14.4
SEEDS = (41, 42)
PRESETS = {"C": "draft", "CM": "motion"}


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.engine.tone import lock_loop
    from loom2.models import registry
    from loom2.place_sets import CROWD_FPS, CROWD_FRAMES, CROWD_STRENGTH, crowd_prompts, crowd_size
    from loom2.story import StoryStore
    from loom2.tone import srgb_to_lab
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    face = next(f for f in StoryStore(ws).profile(PID).version(VID).place_set.faces if f.id == FACE)
    tex = Image.open(cat.abs_path(cat.get(face.texture_asset_id))).convert("RGB")
    w, h = crowd_size(TO - FROM, tex.height * face.texel_m)
    crop = tex.crop((round(FROM / face.texel_m), 0, round(TO / face.texel_m), tex.height)).resize((w, h), Image.Resampling.LANCZOS)
    crop.save(OUT / "crop.png")
    start_words, motion_words = crowd_prompts(FACE, face.material, WORDS)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "size": [w, h], "arms": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(STATE), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def run(recipe: dict, label: str) -> dict:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": recipe})
        r.raise_for_status()
        jid = r.json()["jobs"][0]["id"]
        while True:
            j = api.get(f"/jobs/{jid}").json()
            if j["status"] not in ("queued", "running", "staged"):
                break
            time.sleep(4)
        print(f"{label}: {j['status']} in {round(time.time() - t0)} s {j.get('error') or ''}", flush=True)
        if j["status"] != "done":
            raise RuntimeError(f"{label}: {j.get('error')}")
        return {"seconds": round(time.time() - t0), "result": j.get("result") or {}}

    clips: dict[str, list[Path]] = {}
    starts: dict[int, Image.Image] = {}
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        crop_id = api.post("/assets/import", json={"paths": [str(OUT / "crop.png")]}).json()["items"][0]["id"]
        model = registry.default_model("i2v", "full")
        for seed in SEEDS:
            doc = api.post("/documents", json={"from_asset": crop_id, "name": f"E51 start {seed}"}).json()["id"]
            s = run({"kind": "i2i", "document_id": doc, "source": "visible", "prompt_text": start_words, "strength": CROWD_STRENGTH, "match_colour": True,
                     "seeds": [seed]}, f"start {seed}")
            r = api.post(f"/documents/{doc}/flatten", json={"to_catalogue": True, "name": f"E51 start {seed}"})
            r.raise_for_status()
            start = r.json()["asset"]["id"]
            starts[seed] = Image.open(cat.abs_path(cat.get(start))).convert("RGB")
            starts[seed].save(OUT / f"start_{seed}.png")
            results["arms"][f"start {seed}"] = {"seconds": s["seconds"]}
            for arm, preset in PRESETS.items():
                c = run({"kind": "i2v", "model_id": model, "start_asset": start, "end_asset": start, "prompt_text": motion_words, "frames": CROWD_FRAMES,
                         "fps": CROWD_FPS, "width": w, "height": h, "preset": preset, "seeds": [seed]}, f"{arm} {seed}")
                rec = json.loads((PROJECT / "clips" / c["result"]["clip_id"] / "clip.json").read_text(encoding="utf-8"))
                d = OUT / f"{arm}_{seed}"
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir()
                paths = []
                for p in sorted((PROJECT / rec["master_dir"]).glob("*.png")):
                    shutil.copyfile(p, d / p.name)
                    paths.append(d / p.name)
                results["arms"][f"{arm} {seed}"] = {"seconds": c["seconds"], "clip_id": c["result"]["clip_id"], "lock": lock_loop(paths)}
                clips[f"{arm} {seed}"] = paths
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    lab_crop = srgb_to_lab(np.asarray(crop, dtype=np.float64) / 255.0)
    for seed, im in starts.items():
        lab = srgb_to_lab(np.asarray(im.resize(crop.size), dtype=np.float64) / 255.0)
        results["arms"][f"start {seed}"]["dE_mean"] = round(float(np.sqrt(((lab.reshape(-1, 3).mean(0) - lab_crop.reshape(-1, 3).mean(0)) ** 2).sum())), 2)
    for key, paths in clips.items():
        fr = [np.asarray(Image.open(p).convert("RGB"), dtype=np.float64) for p in paths]
        lo = int(fr[0].shape[0] * 0.4)
        steps = [float(np.abs(fr[k + 1][lo:] - fr[k][lo:]).mean()) for k in range(len(fr) - 1)]
        results["arms"][key]["motion_mean"] = round(float(np.mean(steps)), 2)
        results["arms"][key]["motion_max"] = round(float(np.max(steps)), 2)
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    keys = list(clips)
    sheet = Image.new("RGB", (394 * 4, 168 * len(keys)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for r_, key in enumerate(keys):
        for j, k in enumerate((0, 20, 40, 60)):
            sheet.paste(Image.open(clips[key][k]).convert("RGB").crop((300, 120, 1088, 420)).resize((394, 150)), (j * 394, r_ * 168 + 18))
            dr.text((j * 394 + 4, r_ * 168 + 3), f"{key} · frame {k} · motion {results['arms'][key]['motion_mean']}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=86)
    st = Image.new("RGB", (544 * 3, 240), (20, 20, 20))
    st.paste(crop.resize((544, 240)), (0, 0))
    for i, (seed, im) in enumerate(starts.items()):
        st.paste(im.resize((544, 240)), (544 * (i + 1), 0))
    st.save(OUT / "starts.jpg", quality=86)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("seconds", "motion_mean", "motion_max", "dE_mean", "lock")} for k, v in results["arms"].items()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
