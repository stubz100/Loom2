"""Spike E54 (M13; journal 2026-10-31 21:07): a side reference for a character seen in profile — on E47's copy of the market walk, through
the app's routes, alone on the GPU.

    make:     Mira's side A-pose by Build's own A-pose recipe (plan_anim_ref's: Klein, the sheet, the version mentioned), the side sentence,
              two seeds at 1280 × 720 → engine/spikes/out/e54/side_<seed>.png
    perform:  a copy of Final 5, Mira's layer performed again through POST /finals/{fid}/layers/{lid}/run with the version's animation
              reference set to the chosen side A-pose (in the store, the orchestrator stopped; restored after) — the prompt, guide, window
              and seed are Final 5's (arm F); frames 10, 32, 60 of F and S side by side → sheet.jpg

    orchestrator/.venv/Scripts/python.exe engine/spikes/e54_side.py make
    orchestrator/.venv/Scripts/python.exe engine/spikes/e54_side.py perform <side asset id> [--mirror]
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
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PROJECT, STATE  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e54"
PORT, TOKEN = 8766, "devtoken"
MIRA, VID, LAYER, F5 = "prf_74eda982", "v1", "fig_mira0001", "fin_d5ce3248"
FRONT = "ast_75b85ff9"
SIDE_SENTENCE = ("Full-body character reference, seen from the side in profile, facing left, standing in a neutral A-pose with both arms held "
                 "straight a little away from the body, the feet slightly apart, the whole figure from the top of the head to the feet visible "
                 "and centred with space around it, the hair and anything that hangs behind fully visible, on a plain light grey studio "
                 "background, soft even light, no props, no other people, no text.")
SEEDS = (54, 55)
SAMPLE = (10, 32, 60)


def orchestrator(log_path: Path) -> tuple[subprocess.Popen, httpx.Client]:
    log = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state", str(STATE),
                             "--project", str(PROJECT)], cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    for _ in range(120):
        try:
            api.get("/project").raise_for_status()
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return proc, api


def stop(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=30)
    except Exception:  # noqa: BLE001
        proc.kill()


def wait(api: httpx.Client, jid: str) -> dict:
    while True:
        j = api.get(f"/jobs/{jid}").json()
        if j["status"] not in ("queued", "running", "staged"):
            return j
        time.sleep(4)


def make() -> int:
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore, compose_sheet, expand_spec
    from loom2.workspace import Workspace
    ws = Workspace(PROJECT)
    p = StoryStore(ws).profile(MIRA)
    v = p.version(VID)
    sheet = compose_sheet(v, name=p.name, cls=p.cls)
    spec = expand_spec("full")
    proc, api = orchestrator(OUT / "orchestrator.log")
    res = {}
    try:
        for seed in SEEDS:
            t0 = time.time()
            recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": f"{sheet}. {SIDE_SENTENCE}", "width": 1280, "height": 720,
                      "seeds": [seed], "tier": "draft", "mentions": [{"group_id": "", "name": p.name, "profile_id": p.id, "version": VID}]}
            r = api.post("/jobs", json={"recipe": recipe})
            r.raise_for_status()
            j = wait(api, r.json()["jobs"][0]["id"])
            print(f"side {seed}: {j['status']} in {round(time.time() - t0)} s {j.get('error') or ''}", flush=True)
            aid = (j.get("result") or {}).get("asset_ids", [None])[0]
            if aid:
                cat = Catalogue(ws)
                Image.open(cat.abs_path(cat.get(aid))).convert("RGB").save(OUT / f"side_{seed}.png")
                res[seed] = {"asset": aid, "seconds": round(time.time() - t0)}
        api.post("/engine/stop")
    finally:
        stop(proc)
    (OUT / "make.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


def perform(side_asset: str, mirror: bool) -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.fsio import new_id
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    ws = Workspace(PROJECT)
    cat, store, finals = Catalogue(ws), StoryStore(ws), FinalStore(ws)
    if mirror:                                                                 # the side A-pose turned to face the way the layer walks
        src = Image.open(cat.abs_path(cat.get(side_asset))).convert("RGB")
        m = OUT / "side_mirrored.png"
        ImageOps.mirror(src).save(m)
        side_asset = cat.make_thumbs(cat.ingest_file(m, kind="image", move=False, suite="story", parents=[side_asset], params={"spike": "E54", "mirrored": True})).id
    fid = new_id("fin")                                                        # a copy of Final 5: arm S
    shutil.copytree(finals.folder(F5), finals.folder(fid))
    rec = json.loads(finals.path(fid).read_text(encoding="utf-8"))
    rec.update(id=fid, name="E54 (S) side reference", assembly=None, assembled_at=None, clip_id=None)
    finals.path(fid).write_text(json.dumps(rec, indent=1), encoding="utf-8")
    store.set_anim_ref(MIRA, VID, "front", side_asset)                         # the side A-pose stands in for the front for this run
    res: dict = {"final": fid, "side_asset": side_asset}
    try:
        proc, api = orchestrator(OUT / "orchestrator.log")
        try:
            t0 = time.time()
            r = api.post(f"/finals/{fid}/layers/{LAYER}/run", json={"seed": 0})
            print("run:", r.status_code, r.text[:300], flush=True)
            r.raise_for_status()
            res["run"] = r.json()
            while True:
                f = api.get(f"/finals/{fid}").json()
                lay = next(x for x in f["layers"] if x["id"] == LAYER)
                if lay["status"] not in ("queued", "running"):
                    break
                time.sleep(6)
            res["status"], res["seconds"], res["error"] = lay["status"], round(time.time() - t0), lay.get("error")
            print("performed:", lay["status"], res["seconds"], "s", lay.get("error") or "", flush=True)
            api.post("/engine/stop")
        finally:
            stop(proc)
    finally:
        store.set_anim_ref(MIRA, VID, "front", FRONT)                          # restored
    (OUT / "perform.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    def frames(f_id: str) -> list[Path]:
        d = finals.folder(f_id) / LAYER
        w = sorted((d / "window" / "frames").glob("*.png"))
        return w if w else sorted((d / "frames").glob("*.png"))
    fa, fb = frames(F5), frames(fid)
    tw, th = 300, 530
    sheet = Image.new("RGB", (tw * len(SAMPLE) * 2, th + 20), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(SAMPLE):
        for j, (name, fr) in enumerate((("F front", fa), ("S side", fb))):
            if k < len(fr):
                im = Image.open(fr[k]).convert("RGB")
                im.thumbnail((tw, th))
                x = (i * 2 + j) * tw
                sheet.paste(im, (x, 20))
                d.text((x + 4, 4), f"{name} · frame {k}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=88)
    print(json.dumps(res), flush=True)
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "make":
        return make()
    if len(sys.argv) > 2 and sys.argv[1] == "perform":
        return perform(sys.argv[2], "--mirror" in sys.argv)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
