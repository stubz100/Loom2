"""K1 (the review of 2026-11-06): what the reference squash cost. Every reference image reached ReferenceLatent through
`ImageScale(ref_max_px, ref_max_px, crop disabled)`, which at the pin resizes to exactly that square — D152's hero (1024×576) went in
stretched 1.78× tall. This rig measures the same jobs on the code that squashes (`--label squash`, run before the fix) and on the code that
keeps the aspect (`--label aspect`, after), with FaceSim (ArcFace) against the hero's face:

  fill  — D152's own task: the inpaint bench's face fix (the box around the young woman's face on the alley render) as the AI tab runs it
          (Klein 9B + LanPaint), without the reference and with the hero as reference 1, seeds 1 and 2;
  t2i   — Klein 9B text to image, "the same young woman…" with the hero as reference 1 (an @mention's path, D73), seeds 1 and 2.

    orchestrator/.venv/Scripts/python.exe scripts/k1_refs_rig.py --label squash|aspect [--seeds 1,2]

Results: engine/spikes/out/k1_refs/<label>.json and <label>.jpg (each result, the hero last). One GPU job at a time: it refuses to start
while the engine port is busy, and runs its jobs one after another on its own orchestrator.
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
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]

from edit_refs_rig import HERO, MASK, PORT, SOURCE, TOKEN, api, wait_job  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "k1_refs"
FILL_PROMPT = "the same young woman's face, freckles, calm expression, looking at the viewer, natural eyes, same lighting"
T2I_PROMPT = "portrait of the same young woman, head and shoulders, freckles, calm expression, looking at the viewer, soft window light"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, choices=["squash", "aspect"])
    ap.add_argument("--seeds", default="1,2")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",")]
    import cr_acceptance as cr
    from m1_acceptance import port_busy
    from loom2.config import AppState
    from loom2.tools.facesim import FaceSim
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    models = os.environ.get("LOOM2_MODELS", "F:/loom2-models")
    fs = FaceSim(Path(models))
    hero_img = np.asarray(Image.open(HERO).convert("RGB"))
    hero_emb = fs.embed(hero_img, fs.detect(hero_img)[0].kps)

    def sim(rgb: np.ndarray) -> float | None:
        faces = fs.detect(rgb)
        if not faces:
            return None
        f = max(faces, key=lambda x: x.area)
        return round(FaceSim.similarity(fs.embed(rgb, f.kps), hero_emb), 3)

    tmp = Path(tempfile.mkdtemp(prefix="loom2-k1-"))
    AppState(tmp / "state").update_settings({"models_root": models, "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    res: dict = {"label": a.label, "stamp": time.strftime("%Y-%m-%d %H:%M"), "seeds": seeds, "jobs": []}
    vram = cr.VramSampler()
    source = Image.open(SOURCE).convert("RGBA")
    tiles: list[tuple[str, Image.Image]] = []
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "K1", "size_cap_gb": 20})
        src_id = api("POST", "/assets/import", {"paths": [str(SOURCE)]})["items"][0]["id"]
        hero_id = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
        doc = api("POST", "/documents", {"from_asset": src_id, "name": "face-fix"})
        did, W, H = doc["id"], doc["w"], doc["h"]
        mask = np.asarray(Image.open(MASK).convert("L").resize((W, H), Image.Resampling.NEAREST))
        api("PUT", f"/documents/{did}/selection?w={W}&h={H}", data=np.ascontiguousarray(mask).tobytes())
        vram.mark()
        ref = [{"asset_id": hero_id, "note": "the hero"}]
        for part, with_ref in (("fill", False), ("fill", True), ("t2i", True)):
            for seed in seeds:
                t1 = time.time()
                if part == "fill":
                    recipe = {"kind": "inpaint", "mode": "fill", "prompt_text": FILL_PROMPT, "seeds": [seed], **({"refs": ref} if with_ref else {})}
                    job = api("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]
                else:
                    recipe = {"kind": "t2i", "model_id": "klein-9b", "prompt_mode": "text", "prompt_text": T2I_PROMPT, "seeds": [seed], "width": 1024, "height": 1024, "refs": ref}
                    job = api("POST", "/jobs", {"recipe": recipe})["jobs"][0]
                j = wait_job(job["id"])
                row = {"part": part, "reference": with_ref, "seed": seed, "status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "error": j.get("error")}
                res["jobs"].append(row)
                print(f"{part} {'ref' if with_ref else 'no ref'} s{seed}: {j['status']} {j.get('wall_s')} s {j.get('error') or ''}", flush=True)
                if j["status"] != "done":
                    continue
                if part == "fill":
                    lid = (j.get("result") or {}).get("layers", [None])[0]
                    d = api("GET", f"/documents/{did}")
                    layer = next((n for n in d.get("layers", []) for n in ([n] + (n.get("children") or [])) if n.get("id") == lid), None)
                    im = Image.open(io.BytesIO(api("GET", f"/documents/{did}/layers/{lid}/pixels", raw=True))).convert("RGBA")
                    comp = source.copy()
                    comp.alpha_composite(im, (int(layer["x"]) if layer else 0, int(layer["y"]) if layer else 0))
                    out = comp.convert("RGB")
                else:
                    aid = (j.get("result") or {}).get("asset_ids", [None])[0]
                    out = Image.open(io.BytesIO(api("GET", f"/assets/{aid}/file", raw=True))).convert("RGB")
                row["facesim"] = sim(np.asarray(out))
                tiles.append((f"{part} · {'ref' if with_ref else 'no ref'} · s{seed} · {row['facesim']}", out))
                print(f"     FaceSim to the hero {row['facesim']}", flush=True)
        res["peak_gb"] = vram.window()

        def mean(part: str, with_ref: bool) -> float | None:
            v = [r["facesim"] for r in res["jobs"] if r["part"] == part and r["reference"] == with_ref and r.get("facesim") is not None]
            return round(float(np.mean(v)), 3) if v else None
        res["means"] = {"fill_without": mean("fill", False), "fill_with": mean("fill", True), "t2i_with": mean("t2i", True)}
        tiles.append(("the reference (hero)", Image.open(HERO).convert("RGB")))
        hh = 300
        scaled = [(lbl, im.resize((round(im.width * hh / im.height), hh))) for lbl, im in tiles]
        sheet = Image.new("RGB", (sum(im.width + 8 for _, im in scaled), hh + 18), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        x = 0
        for lbl, im in scaled:
            sheet.paste(im, (x, 18)); dr.text((x + 3, 3), lbl, fill=(230, 230, 230)); x += im.width + 8
        sheet.save(OUT / f"{a.label}.jpg", quality=88)
        (OUT / f"{a.label}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res["means"]), f"peak {res['peak_gb']} GB", flush=True)
        return 0
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
