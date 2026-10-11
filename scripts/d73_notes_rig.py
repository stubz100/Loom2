"""D73 rig check (ArtCraft P12): do reference notes help a model keep two references apart?

Two reference stills are made first (Klein 9B): the bench's heroine (red braids, freckles, green hooded wool cloak, brass compass) and its
grey-bearded captain, each alone on a plain background. Then two bench prompts that put both in one frame (02 captain's cabin, 08 storm
deck) run with both references — once without notes and once with a note per reference ("Image 1 shows …") — on Klein 9B (prose
notes) and, for 02, on dev Turbo (the JSON `references` section). Same seeds for both arms. The contact sheet (one row per prompt × model:
the two references, then no-notes seeds A B, then notes seeds A B) is judged on the bench's identity axis: is each character the one in
its reference, or are they swapped or blended?

  orchestrator/.venv/Scripts/python.exe scripts/d73_notes_rig.py [--projects F:/loom2-projects] [--port 8768] [--skip-dev]
Writes engine/spikes/out/d73/sheet.png and appends a JSON line to engine/spikes/out/d73/runs.jsonl.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from m1_acceptance import Orch, check, port_busy  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "d73"
KLEIN, DEV = "klein-9b", "flux2-dev-fp8mixed"
SEEDS = [20261011, 20261012]
W, H = 640, 352
HEROINE = ("a young woman with long red braids and freckles, wearing a green hooded wool cloak, holding a brass compass, waist-up portrait, "
           "plain light grey studio background, soft even light")
CAPTAIN = ("a grey-bearded sea captain with a weathered face, navy wool coat with brass buttons and a peaked cap, waist-up portrait, "
           "plain light grey studio background, soft even light")
NOTES = ["the young woman with red braids, freckles and the green hooded cloak", "the grey-bearded sea captain in the navy coat and peaked cap"]


def run_job(o: Orch, recipe: dict, timeout: float = 900) -> dict:
    j = o.http.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]   # type: ignore[union-attr]
    return o.wait_job(j["id"], {"done", "failed", "cancelled"}, timeout)


def image_of(o: Orch, asset_id: str) -> Image.Image:
    r = o.http.get(f"/assets/{asset_id}/file")                               # type: ignore[union-attr]
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8768)
    ap.add_argument("--engine-port", type=int, default=8188)
    ap.add_argument("--skip-dev", action="store_true")
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    state, project = Path(a.projects) / f"_state-d73-{stamp}", Path(a.projects) / f"d73-notes-{stamp}"
    if port_busy(a.engine_port):
        print("engine port busy — wait for the running job to finish"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    o = Orch(state, a.port).start()
    rows: list[tuple[str, list[Image.Image]]] = []
    timings: dict[str, list[float]] = {}
    try:
        check("project created", o.http.post("/project", json={"path": str(project), "name": "D73 notes", "size_cap_gb": 20}).status_code == 200)  # type: ignore[union-attr]
        refs = []
        for name, text in (("heroine", HEROINE), ("captain", CAPTAIN)):
            j = run_job(o, {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "text", "prompt_text": text, "width": 576, "height": 576, "seeds": [7]})
            check(f"reference still: {name}", j["status"] == "done", f"{j['status']} {j.get('wall_s')} s {j.get('error') or ''}"[:160])
            refs.append(j["result"]["asset_ids"][0])
        ref_imgs = [image_of(o, r) for r in refs]
        cases = [("02 cabin", "02-captain-cabin.json", KLEIN), ("08 storm deck", "08-storm-deck.json", KLEIN)]
        if not a.skip_dev:
            cases.append(("02 cabin", "02-captain-cabin.json", DEV))
        for label, bench, model in cases:
            tree = json.loads((REPO / "bench" / "t2i" / bench).read_text(encoding="utf-8"))
            cells = list(ref_imgs)
            for arm in ("plain", "notes"):
                refs_in = [{"asset_id": r, **({"note": n} if arm == "notes" else {})} for r, n in zip(refs, NOTES)]
                for seed in SEEDS:
                    recipe = {"kind": "t2i", "model_id": model, "prompt_mode": "tree", "prompt_json": tree, "refs": refs_in, "width": W, "height": H, "seeds": [seed],
                              **({"turbo": True} if model == DEV else {})}
                    pv = o.http.post("/recipes/preview", json={"recipe": recipe}).json()   # type: ignore[union-attr]
                    if arm == "notes":
                        check(f"{label} {model}: the notes are in the prompt", pv["ref_notes"] == 2 and ("Image 1 shows" in pv["serialized_prompt"] or '"references"' in pv["serialized_prompt"]))
                    j = run_job(o, recipe)
                    ok = j["status"] == "done"
                    check(f"{label} {model} {arm} seed {seed}", ok, f"{j.get('wall_s')} s {j.get('error') or ''}"[:120])
                    timings.setdefault(f"{model} {arm}", []).append(float(j.get("wall_s") or 0))
                    cells.append(image_of(o, j["result"]["asset_ids"][0]) if ok else Image.new("RGB", (W, H), (60, 0, 0)))
            rows.append((f"{label} · {model}", cells))
    finally:
        o.stop()
    # the sheet: per row, two square references, then plain A B, notes A B
    th = 220
    cw = [th, th] + [int(th * W / H)] * 4
    sheet = Image.new("RGB", (sum(cw) + 7 * 8, 28 + len(rows) * (th + 30)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    heads = ["ref 1 (heroine)", "ref 2 (captain)", "no notes · A", "no notes · B", "notes · A", "notes · B"]
    x = 8
    for w, h in zip(cw, heads):
        d.text((x, 8), h, fill=(220, 220, 220)); x += w + 8
    for r, (label, cells) in enumerate(rows):
        y = 28 + r * (th + 30)
        d.text((8, y), label, fill=(240, 180, 60))
        x = 8
        for w, im in zip(cw, cells):
            sheet.paste(im.resize((w, th)), (x, y + 18)); x += w + 8
    sheet.save(OUT / "sheet.png")
    line = {"stamp": stamp, "seeds": SEEDS, "size": [W, H], "timings_s": {k: [round(v, 1) for v in vs] for k, vs in timings.items()}, "rows": [r for r, _ in rows]}
    with (OUT / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print(json.dumps(line))
    print(f"sheet: {OUT / 'sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
