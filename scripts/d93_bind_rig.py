"""D93 (A3) rig check: does binding each linked subject to its own reference images help a model keep two characters apart?

Two Cast characters are made in a scratch project through the app's own routes: a hero each (a waist-up portrait on Klein 9B KV) and two
more looks made with the hero as the reference, added "into the reference set" (D93 A2's route), so each set holds three images. Their
stubs say a role, not a look ("Mara, a courier"), so the identity can only come from the references. Then one Tree prompt with two
subject cards linked to the two profiles (left / right) runs at Draft with the same seeds in two arms: `bind_refs` off — D73's sentence
per image ("Image 1 shows Mara, a courier.") — and on — the subject names its range ("Mara (reference images 1–2), a courier"). Klein
takes four references, so each set gives two (one left out, said in the preview).

Identity per result (FaceSim, ArcFace on the CPU): the faces found, the left-most is Mara's place and the right-most Ines's; `own` = the
cosine of each to its character's hero, `cross` = to the other's; a result is *swapped* when cross > own for the pair, *right* when both
faces are nearer their own hero. Reported per arm: mean own, mean cross, margin (own − cross), right / swapped counts, faces found.

  orchestrator/.venv/Scripts/python.exe scripts/d93_bind_rig.py [--projects F:/loom2-projects] [--port 8769] [--seeds 6] [--model klein-9b-kv]
Writes engine/spikes/out/d93/sheet.jpg and appends a JSON line to engine/spikes/out/d93/runs.jsonl.

Another model on the same two characters (the owed FLUX.2 dev JSON binding): `--source` copies a project that already holds Mara and Ines
(phase A's) to a new scratch project — the original is not touched — and runs only the two arms there; `--turbo` runs the model's Turbo
preset (Generate's default on dev), `--sheet` names the contact sheet:
  … scripts/d93_bind_rig.py --model flux2-dev-fp8mixed --turbo --source F:/loom2-projects/d93-bind-20261017-131210 --sheet sheet_dev.jpg
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch, check, port_busy  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "d93"
W, H = 960, 544                                         # Draft (D18)
CHARS = [("Mara", "a courier", "a young woman with a short black bob haircut and round glasses, olive skin, a grey wool coat"),
         ("Ines", "a lighthouse keeper", "a woman in her forties with long curly red hair and freckles, pale skin, a yellow oilskin jacket")]
PORTRAIT = "{look}, waist-up portrait, facing the camera, plain light grey studio background, soft even light"
MORE = ["the same woman as in image 1, three-quarter view from the left, waist-up, plain light grey studio background",
        "the same woman as in image 1, close-up portrait, slight smile, plain light grey studio background"]
SCENE = {"scene": "two women standing side by side on a harbour quay at dusk, waist-up, both facing the camera",
         "subjects": [{"description": "Mara, a courier", "position": "left"}, {"description": "Ines, a lighthouse keeper", "position": "right"}],
         "lighting": "warm lamplight, soft", "camera": {"distance": "medium shot", "angle": "eye level"}}


class Vram:
    """The engine's VRAM in use (total − free from /system_stats), sampled every 0.5 s."""
    def __init__(self, port: int) -> None:
        self.peak, self.port, self.stop = 0.0, port, False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while not self.stop:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/system_stats", timeout=2) as r:
                    d = json.loads(r.read())["devices"][0]
                self.peak = max(self.peak, (d["vram_total"] - d["vram_free"]) / 2**30)
            except Exception:
                pass
            time.sleep(0.5)


def run_job(o: Orch, recipe: dict, timeout: float = 1800) -> dict:
    j = o.http.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]   # type: ignore[union-attr]
    return o.wait_job(j["id"], {"done", "failed", "cancelled"}, timeout)


def image_of(o: Orch, asset_id: str) -> Image.Image:
    return Image.open(io.BytesIO(o.http.get(f"/assets/{asset_id}/file").content)).convert("RGB")   # type: ignore[union-attr]


def faces(fs: FaceSim, im: Image.Image) -> list[tuple[float, np.ndarray]]:
    """(centre x, embedding) of the two largest faces found, left to right (a face in the background does not count)."""
    arr = np.asarray(im)
    return sorted(((float((f.bbox[0] + f.bbox[2]) / 2), fs.embed(arr, f.kps)) for f in fs.detect(arr)[:2]), key=lambda t: t[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8769)
    ap.add_argument("--engine-port", type=int, default=8188)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--model", default="klein-9b-kv")
    ap.add_argument("--source", default="", help="a project holding Mara and Ines already: copied, the arms run on the copy")
    ap.add_argument("--turbo", action="store_true", help="the model's Turbo preset (dev: 8 steps)")
    ap.add_argument("--sheet", default="sheet.jpg")
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = f"d93-bind-{a.model}-{stamp}" if a.source else f"d93-bind-{stamp}"
    state, project = Path(a.projects) / f"_state-{tag}", Path(a.projects) / tag
    if port_busy(a.engine_port):
        print("engine port busy — wait for the running job to finish"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    fs = FaceSim("F:/loom2-models")
    seeds = [20261017 + i for i in range(a.seeds)]
    o = Orch(state, a.port).start()
    vram = Vram(a.engine_port)
    arms: dict[str, list[dict]] = {"off": [], "on": []}
    heroes: list[Image.Image] = []
    prompts: dict[str, str] = {}
    timings: dict[str, list[float]] = {"off": [], "on": []}
    try:
        profiles = []
        if a.source:
            shutil.copytree(a.source, project)                                           # a scratch copy: the source project stays as it was
            r = o.http.post("/project/open", json={"path": str(project)})   # type: ignore[union-attr]
            check("the scratch copy opened", r.status_code == 200, r.text[:120])
            profs = {p["name"]: p for p in o.http.get("/story/profiles").json()["items"]}   # type: ignore[union-attr]
            for name, _, _ in CHARS:
                profiles.append(profs[name])
                heroes.append(image_of(o, profs[name]["versions"][0]["hero_asset_id"]))
        else:
            check("project created", o.http.post("/project", json={"path": str(project), "name": "D93 binding", "size_cap_gb": 20}).status_code == 200)   # type: ignore[union-attr]
        for name, role, look in ([] if a.source else CHARS):
            j = run_job(o, {"kind": "t2i", "model_id": a.model, "prompt_mode": "text", "prompt_text": PORTRAIT.format(look=look), "width": 576, "height": 576, "seeds": [11]})
            check(f"{name}: the hero", j["status"] == "done", f"{j.get('wall_s')} s {j.get('error') or ''}"[:120])
            hero = j["result"]["asset_ids"][0]
            p = o.http.post("/story/profiles", json={"name": name, "cls": "character", "hero_asset_id": hero, "stub": f"{name}, {role}"}).json()   # type: ignore[union-attr]
            for k, text in enumerate(MORE):
                j = run_job(o, {"kind": "t2i", "model_id": a.model, "prompt_mode": "text", "prompt_text": text, "refs": [{"asset_id": hero}], "width": 576, "height": 576, "seeds": [21 + k]})
                check(f"{name}: look {k + 2}", j["status"] == "done", f"{j.get('wall_s')} s")
                r = o.http.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": j["result"]["asset_ids"], "role": "reference"})   # type: ignore[union-attr]
                check(f"{name}: look {k + 2} into the reference set (A2)", r.status_code == 200 and r.json()["moved"] == j["result"]["asset_ids"], r.text[:120])
            profiles.append(p)
            heroes.append(image_of(o, hero))
        hero_emb = []
        for name, im in zip([c[0] for c in CHARS], heroes):
            f = faces(fs, im)
            check(f"{name}: a face in the hero", len(f) >= 1)
            hero_emb.append(f[0][1] if f else None)
        mentions = [{"profile_id": p["id"], "name": c[0], "subject": i} for i, (p, c) in enumerate(zip(profiles, CHARS))]
        for arm in ("off", "on"):
            recipe = {"kind": "t2i", "model_id": a.model, "prompt_mode": "tree", "prompt_json": SCENE, "mentions": mentions, "bind_refs": arm == "on", "width": W, "height": H,
                      **({"turbo": True} if a.turbo else {})}
            pv = o.http.post("/recipes/preview", json={"recipe": recipe}).json()   # type: ignore[union-attr]
            prompts[arm] = pv["serialized_prompt"]
            sp = pv["serialized_prompt"]
            if arm == "on":
                refs = [b["refs"] for b in pv["bindings"]]
                check("the preview binds both subjects, each its own contiguous range", len(refs) == 2 and all(r and r == list(range(r[0], r[-1] + 1)) for r in refs)
                      and refs[0][-1] < refs[1][0] and ("Mara (reference image" in sp or '"reference":"reference image' in sp), json.dumps(pv["bindings"])[:240])
                check("what was left out is said", all("skipped" in b for b in pv["bindings"]), json.dumps([b.get("skipped") for b in pv["bindings"]]))
            else:
                check("off: D73's per-image notes, no range", ("Image 1 shows Mara" in sp or '"references"' in sp) and "(reference image" not in sp and '"reference":"reference image' not in sp, sp[-300:])
            for seed in seeds:
                j = run_job(o, {**recipe, "seeds": [seed]})
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
                arms[arm].append(row)
    finally:
        vram.stop = True
        o.stop()

    def summary(rows: list[dict]) -> dict:
        m = [r for r in rows if "own" in r]
        own = [x for r in m for x in r["own"]]
        cross = [x for r in m for x in r["cross"]]
        return {"n": len(rows), "two_faces": len(m), "own_mean": round(float(np.mean(own)), 3) if own else None, "cross_mean": round(float(np.mean(cross)), 3) if cross else None,
                "margin": round(float(np.mean(own) - np.mean(cross)), 3) if own else None, "right": sum(1 for r in m if r["right"]), "swapped": sum(1 for r in m if r["swapped"]),
                "per_seed": [{k: v for k, v in r.items() if k != "image"} for r in rows]}

    res = {arm: summary(rows) for arm, rows in arms.items()}
    # the sheet: the two heroes, then a row per arm
    th = 200
    tw = int(th * W / H)
    n = max(len(r) for r in arms.values())
    sheet = Image.new("RGB", (8 + max(2 * (th + 8), n * (tw + 8)), 8 + 3 * (th + 30)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for k, im in enumerate(heroes):
        sheet.paste(im.resize((th, th)), (8 + k * (th + 8), 26)); d.text((8 + k * (th + 8), 8), f"hero · {CHARS[k][0]}", fill=(220, 220, 220))
    for r, arm in enumerate(("off", "on")):
        y = 8 + (r + 1) * (th + 30)
        d.text((8, y), f"bind_refs {arm} · own {res[arm]['own_mean']} cross {res[arm]['cross_mean']} · right {res[arm]['right']}/{res[arm]['two_faces']}", fill=(240, 180, 60))
        for c, row in enumerate(arms[arm]):
            sheet.paste(row["image"].resize((tw, th)), (8 + c * (tw + 8), y + 18))
    sheet.save(OUT / a.sheet, quality=88)
    line = {"stamp": stamp, "model": a.model, "turbo": a.turbo, "source": a.source, "project": str(project), "seeds": seeds, "size": [W, H], "vram_peak_gb": round(vram.peak, 2),
            "timings_s": {k: [round(v, 1) for v in vs] for k, vs in timings.items()}, "prompts": prompts, "result": res}
    with (OUT / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in line.items() if k != "result"} | {"result": {arm: {k: v for k, v in s.items() if k != "per_seed"} for arm, s in res.items()}}, ensure_ascii=False, indent=1))
    print(f"sheet: {OUT / a.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
