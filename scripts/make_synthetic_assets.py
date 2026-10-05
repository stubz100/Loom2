"""Synthetic catalogue for the M2 acceptance (08 §9: 10 000 assets scroll smoothly in every group mode).

  orchestrator/.venv/Scripts/python.exe scripts/make_synthetic_assets.py --project F:/loom2-projects/synthetic-10k [--count 10000]

Creates (or opens) the project, writes small PNGs with varied sizes, models, batches, sessions, states,
ratings, tags and lineage chains through the real ingest path (sidecar manifests + index + WebP thumbs), so
the result is indistinguishable from real output for the UI.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))

from PIL import Image  # noqa: E402

from loom2.catalogue import Catalogue  # noqa: E402
from loom2.fsio import new_id  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

MODELS = ["flux2-dev-fp8mixed", "klein-9b", "klein-4b", "klein-base-9b"]
SIZES = [(960, 544), (1280, 720), (1088, 1088), (544, 960), (1920, 1088)]
PROMPTS = ["rain-soaked harbour alley at night, neon sign", "captain's cabin, chart table, lamp", "rooftop at night, moonlit chimneys",
           "fish market crowd, morning light", "portrait, grief, window light", "storm at sea, lightning", "throne room, banners"]
TAGS = ["alley", "harbour", "night", "portrait", "hero", "wip", "ref", "establishing", "closeup"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-thumbs", action="store_true")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    dest = Path(a.project)
    ws = Workspace.open(dest) if (dest / "project.json").exists() else Workspace.create(dest, name="Synthetic 10k", size_cap_gb=20)
    cat = Catalogue(ws, [256, 512], session_id="ses_synth")
    tmp = ws.temp_dir / "synth"
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    made = 0
    sessions = [f"ses_{i:02d}" for i in range(12)]
    roots: list[str] = []
    while made < a.count:
        batch = new_id("bat")
        model = rnd.choice(MODELS)
        prompt = rnd.choice(PROMPTS)
        session = rnd.choice(sessions)
        w, h = rnd.choice(SIZES)
        n = rnd.choice([1, 2, 4, 4, 8])
        for _ in range(min(n, a.count - made)):
            # a tiny PNG with the aspect of the pretend render (the catalogue reads w×h from the file)
            tw, th = (64, max(8, round(64 * h / w))) if w >= h else (max(8, round(64 * w / h)), 64)
            src = tmp / f"{new_id('tmp')}.png"
            Image.new("RGB", (tw, th), (rnd.randrange(40, 220), rnd.randrange(40, 220), rnd.randrange(40, 220))).save(src)
            derived = roots and rnd.random() < 0.15
            parents = [rnd.choice(roots)] if derived else []
            rec = cat.ingest_file(src, kind="image", move=True, job_id=new_id("job"), batch_id=batch, session_id=session, model_id=model, seed=rnd.randrange(1, 2**31),
                                  prompt_text=prompt, prompt_json={"scene": prompt, "camera": rnd.choice(["wide", "medium", "closeup"])} if model.startswith("flux2") else None,
                                  suite="inpaint" if derived else "generate", parents=parents, state=rnd.choice(["none", "none", "none", "keep", "reject"]),
                                  rating=rnd.choice([0, 0, 0, 1, 2, 3, 4, 5]), tags=rnd.sample(TAGS, rnd.choice([0, 0, 1, 2])),
                                  params={"width": w, "height": h, "steps": 20 if model.startswith("flux2") else 4})
            if not a.no_thumbs:
                cat.make_thumbs(rec)
            if not derived and rnd.random() < 0.2:
                roots.append(rec.id)
            made += 1
            if made % 500 == 0:
                print(f"  {made}/{a.count} in {time.time()-t0:.0f} s")
    counts = cat.counts()
    cat.close()
    print(f"done: {made} assets in {time.time()-t0:.0f} s → {ws.path}; counts {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
