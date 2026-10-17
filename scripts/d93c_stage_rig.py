"""D93 (C8) rig check: do Stage figures bound to Cast characters keep the two people apart in a rendered frame?

Phase A's scratch project (`d93-bind-20261017-131210`: Mara and Ines, a hero and two more looks each, sheets that give a role, not a look) is
copied to a new scratch project (the original is not touched) and opened in a fresh orchestrator. A stage is made through the API with two
figures and a camera, and ST3's clay and pose passes of the acceptance blocking (engine/spikes/out/st/passes: a walking figure on the left,
a pointing one on the right) are uploaded as its passes (`PUT /blobs`, `POST /stages/{id}/passes`). Then the method that takes references
(clay — `caps.stage.methods[*].max_refs` > 0; Klein 9B, three references after the pass) renders the camera with the same seeds in three
arms: `none` — no binding, the figures said in the prompt by their words only (what the Render tab did before C8); `off` — the figures bound
(their references in the deck, D73's sentence per image, "figure 1 is Mara, a courier" without a range); `on` — bound with ranges
("figure 1 is Mara (reference images 2–3), a courier"). The figures are bound in the stage document too (`profile_id`), as the Inspector
binds them.

Identity per result (FaceSim, ArcFace on the CPU): the two largest faces, left to right — the left is Mara's place, the right Ines's; `own`
= cosine to its character's hero, `cross` = to the other's; *right* when both are nearer their own hero, *swapped* when the pair's cross
sum beats its own. Reported per arm: mean own / cross, margin, right / swapped counts, two-face count, wall time; the engine's peak VRAM.

  orchestrator/.venv/Scripts/python.exe scripts/d93c_stage_rig.py [--source F:/loom2-projects/d93-bind-20261017-131210] [--seeds 6]
Writes engine/spikes/out/d93c/sheet.jpg and appends a JSON line to engine/spikes/out/d93c/runs.jsonl.

The exact-pose method (`--method refcontrol --sheet sheet_refcontrol.jpg`; Klein base 9B + the RefControl pose LoRA, the pose pass as
image 1): it takes one reference (`max_refs` 1), so the binding fits figure 1's first image only (image 2) and figure 2 is said by its
words. `none` there needs a reference too (the method refuses none) — Mara's hero in the deck, as the Render tab took it before C8.
Per side (left = Mara, right = Ines) the mean own / cross is reported as well.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from d93_bind_rig import Vram, faces, image_of, run_job  # noqa: E402
from m1_acceptance import Orch, check, port_busy  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "d93c"
PASSES = REPO / "engine" / "spikes" / "out" / "st" / "passes"
W, H = 1280, 720                                        # the Render tab's Draft (720 lines at 16:9)
SCENE = "a dim harbour warehouse at dusk, a wooden crate, warm lamplight, cinematic film still, 35 mm"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="F:/loom2-projects/d93-bind-20261017-131210")
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--engine-port", type=int, default=8188)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--arms", default="none,off,on")
    ap.add_argument("--method", default="", help="a Stage method (caps.stage.methods); default: the first that takes ≥ 2 references (clay)")
    ap.add_argument("--sheet", default="sheet.jpg")
    a = ap.parse_args()
    arms_run = [x for x in a.arms.split(",") if x]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = f"d93c-stage-{a.method}-{stamp}" if a.method else f"d93c-stage-{stamp}"
    state, project = Path(a.projects) / f"_state-{tag}", Path(a.projects) / tag
    if port_busy(a.engine_port):
        print("engine port busy — stop the running engine first"); return 2
    shutil.copytree(a.source, project)                                                   # a scratch copy: phase A's project stays as it was
    OUT.mkdir(parents=True, exist_ok=True)
    fs = FaceSim("F:/loom2-models")
    seeds = [20261017 + i for i in range(a.seeds)]
    o = Orch(state, a.port).start()
    vram = Vram(a.engine_port)
    rows: dict[str, list[dict]] = {k: [] for k in arms_run}
    prompts: dict[str, str] = {}
    timings: dict[str, list[float]] = {k: [] for k in arms_run}
    heroes: list[Image.Image] = []
    method = None
    try:
        r = o.http.post("/project/open", json={"path": str(project)})   # type: ignore[union-attr]
        check("the scratch copy opened", r.status_code == 200, r.text[:120])
        profs = {p["name"]: p for p in o.http.get("/story/profiles").json()["items"]}   # type: ignore[union-attr]
        mara, ines = profs["Mara"], profs["Ines"]
        for p in (mara, ines):
            heroes.append(image_of(o, p["versions"][0]["hero_asset_id"]))
        caps = o.http.get("/capabilities").json()["stage"]["methods"]   # type: ignore[union-attr]
        method = a.method or next(m for m, c in caps.items() if (c.get("max_refs") or 0) >= 2 and c.get("health") != "missing")
        check(f"{method}: weights {caps[method].get('health')}", caps[method].get("health") in ("present", "verified"), json.dumps(caps[method].get("missing")))
        check(f"the method that takes references: {method} ({caps[method]['model_id']}, {caps[method]['max_refs']} references)", True)
        st = o.http.post("/stages", json={"name": "D93 C8"}).json()   # type: ignore[union-attr]
        doc = {**st, "objects": [{"id": "fig_left", "kind": "mannequin", "name": "Figure 1", "preset": "adult", "transform": {"pos": [-1.2, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
                                  "pose": {"preset": "walk", "joints": {}}, "profile_id": mara["id"]},
                                 {"id": "fig_right", "kind": "mannequin", "name": "Figure 2", "preset": "adult", "transform": {"pos": [1.2, 0, 0], "rot": [0, -30, 0], "scale": [1, 1, 1]},
                                  "pose": {"preset": "point", "joints": {}}, "profile_id": ines["id"]}],
               "cameras": [{"id": "cam_1", "name": "Camera 1", "pos": [0, 1.5, 5], "target": [0, 1, 0], "roll": 0, "focal_mm": 35, "sensor_mm": 36}], "active_camera": "cam_1"}
        r = o.http.put(f"/stages/{st['id']}", json=doc)   # type: ignore[union-attr]
        check("the stage with two figures bound (profile_id)", r.status_code == 200 and [x["profile_id"] for x in r.json()["objects"]] == [mara["id"], ines["id"]], r.text[:160])
        st = r.json()
        shas = {}
        for name in ("clay", "pose"):
            data = (PASSES / f"{name}.png").read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            o.http.put(f"/blobs/{sha}", content=data)   # type: ignore[union-attr]
            shas[name] = sha
        r = o.http.post(f"/stages/{st['id']}/passes", json={"camera_id": "cam_1", "revision": st["revision"], "size": {"w": W, "h": H}, "passes": shas})   # type: ignore[union-attr]
        check("ST3's passes uploaded as this stage's", r.status_code == 200, r.text[:120])
        passes = r.json()["passes"][-1]["assets"]
        hero_emb = []
        for name, im in zip(("Mara", "Ines"), heroes):
            f = faces(fs, im)
            check(f"{name}: a face in the hero", len(f) >= 1)
            hero_emb.append(f[0][1] if f else None)
        figures = [{"profile_id": mara["id"], "figure": "fig_left"}, {"profile_id": ines["id"], "figure": "fig_right"}]
        words = "From left to right in image 1: figure 1 is Mara, a courier; figure 2 is Ines, a lighthouse keeper."
        base = {"kind": "stage_shot", "stage_id": st["id"], "camera_id": "cam_1", "passes": passes, "method": method, "width": W, "height": H}
        room = int(caps[method]["max_refs"])
        deck = [{"asset_id": mara["versions"][0]["hero_asset_id"]}] if room == 1 else []   # exact pose refuses no reference: none takes Mara's hero
        recipes = {"none": {**base, "prompt_text": f"{words} {SCENE}", "refs": deck},
                   "off": {**base, "prompt_text": SCENE, "mentions": figures, "bind_refs": False},
                   "on": {**base, "prompt_text": SCENE, "mentions": figures, "bind_refs": True}}
        for arm in arms_run:
            pv = o.http.post("/recipes/preview", json={"recipe": recipes[arm]}).json()   # type: ignore[union-attr]
            prompts[arm] = pv["params"]["prompt"]
            if arm == "on" and room == 1:
                check("on: figure 1 names its one image, figure 2 its words", "figure 1 is Mara (reference image 2)" in prompts[arm] and "figure 2 is Ines, " in prompts[arm], prompts[arm][-260:])
                check("on: the one slot is figure 1's", [x.get("figure") for x in pv["params"]["ref_list"]] == [1], json.dumps(pv["params"]["ref_list"]))
            elif arm == "on":
                check("on: each figure names its range", "figure 1 is Mara (reference images 2–3)" in prompts[arm] and "figure 2 is Ines (reference image 4)" in prompts[arm], prompts[arm][-260:])
                check("on: the deck says which slots are a figure's", [x["figure"] for x in pv["params"]["ref_list"]] == [1, 1, 2], json.dumps(pv["params"]["ref_list"]))
            elif arm == "off" and room == 1:
                check("off: no range (exact pose says no per-image sentence)", "(reference image" not in prompts[arm] and "figure 1 is Mara" in prompts[arm], prompts[arm][-260:])
            elif arm == "off":
                check("off: D73's sentences, no range", "Image 2 shows Mara" in prompts[arm] and "(reference image" not in prompts[arm])
            for seed in seeds:
                j = run_job(o, {**recipes[arm], "seeds": [seed]})
                ok = j["status"] == "done"
                check(f"{arm} seed {seed}", ok, f"{j.get('wall_s')} s {j.get('error') or ''}"[:120])
                timings[arm].append(float(j.get("wall_s") or 0))
                im = image_of(o, j["result"]["asset_ids"][0]) if ok else Image.new("RGB", (W, H), (60, 0, 0))
                fl = faces(fs, im) if ok else []
                row: dict = {"seed": seed, "faces": len(fl), "image": im}
                if len(fl) >= 2 and all(e is not None for e in hero_emb):
                    left, right = fl[0][1], fl[-1][1]
                    own = [FaceSim.similarity(left, hero_emb[0]), FaceSim.similarity(right, hero_emb[1])]
                    cross = [FaceSim.similarity(left, hero_emb[1]), FaceSim.similarity(right, hero_emb[0])]
                    row.update(own=[round(x, 3) for x in own], cross=[round(x, 3) for x in cross], right=own[0] > cross[0] and own[1] > cross[1], swapped=sum(cross) > sum(own))
                rows[arm].append(row)
    finally:
        vram.stop = True
        o.stop()

    def summary(rs: list[dict]) -> dict:
        m = [r for r in rs if "own" in r]
        own = [x for r in m for x in r["own"]]
        cross = [x for r in m for x in r["cross"]]
        side = lambda key, k: round(float(np.mean([r[key][k] for r in m])), 3) if m else None  # noqa: E731
        return {"n": len(rs), "two_faces": len(m), "own_mean": round(float(np.mean(own)), 3) if own else None, "cross_mean": round(float(np.mean(cross)), 3) if cross else None,
                "margin": round(float(np.mean(own) - np.mean(cross)), 3) if own else None, "right": sum(1 for r in m if r["right"]), "swapped": sum(1 for r in m if r["swapped"]),
                "own_left": side("own", 0), "cross_left": side("cross", 0), "own_right": side("own", 1), "cross_right": side("cross", 1),
                "faces": [r["faces"] for r in rs], "per_seed": [{k: v for k, v in r.items() if k != "image"} for r in rs]}

    res = {arm: summary(rs) for arm, rs in rows.items()}
    th = 180
    tw = int(th * W / H)
    n = max(len(r) for r in rows.values())
    sheet = Image.new("RGB", (8 + max(3 * (th + 8) + tw, n * (tw + 8)), 8 + (len(rows) + 1) * (th + 30)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for k, im in enumerate(heroes):
        sheet.paste(im.resize((th, th)), (8 + k * (th + 8), 26)); d.text((8 + k * (th + 8), 8), f"hero · {('Mara', 'Ines')[k]}", fill=(220, 220, 220))
    pname = "pose" if method == "refcontrol" else "clay"
    clay = Image.open(PASSES / f"{pname}.png").convert("RGB")
    sheet.paste(clay.resize((tw, th)), (8 + 2 * (th + 8), 26)); d.text((8 + 2 * (th + 8), 8), f"{pname} pass · figure 1 left, figure 2 right", fill=(220, 220, 220))
    for r_, arm in enumerate(rows):
        y = 8 + (r_ + 1) * (th + 30)
        s = res[arm]
        d.text((8, y), f"{arm} · own {s['own_mean']} cross {s['cross_mean']} · right {s['right']}/{s['two_faces']} · {round(float(np.mean(timings[arm] or [0])), 1)} s", fill=(240, 180, 60))
        for c, row in enumerate(rows[arm]):
            sheet.paste(row["image"].resize((tw, th)), (8 + c * (tw + 8), y + 18))
    sheet.save(OUT / a.sheet, quality=88)
    line = {"stamp": stamp, "project": str(project), "method": method, "seeds": seeds, "size": [W, H], "vram_peak_gb": round(vram.peak, 2),
            "timings_s": {k: [round(v, 1) for v in vs] for k, vs in timings.items()}, "prompts": prompts, "result": res}
    with (OUT / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in line.items() if k != "result"} | {"result": {arm: {k: v for k, v in s.items() if k != "per_seed"} for arm, s in res.items()}}, ensure_ascii=False, indent=1))
    print(f"sheet: {OUT / a.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
