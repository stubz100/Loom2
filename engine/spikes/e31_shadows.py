"""Spike E31 (D124): how to find the shadow a picked thing casts in its picture, so the clean plate takes it too.

bench/sets/room.jpg (the SC3 rigs' room: a crate, a table, a small and a big block, the light from the window on the left). Each thing is
picked as the author picks it (SAM 3 points, the SC3c rig's clicks). Two ways to its shadow:
  (S) SAM 3's *shadow* concept on the whole picture (the text prompt at two thresholds, and as "shadow on the floor"), each thing keeping the
      parts that touch it within its reach;
  (P) `set_things.shadows_of`: the surface beside each thing darker than the same surface lit around it and of its colour, grown out from
      the thing, below its top, on the side away from the light (all the things weighed together: one light, one side; CPU).
Then the clean plate three ways on three documents of the picture — the things alone (SC3c), with S's shadows, with P's — each the app's
Fill under the masks grown 14 px. Sheets: the masks over the picture, the three clean plates; numbers in result.json. One GPU job at a
time (D97); the engine stopped at the end.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e31_shadows.py
Outputs under engine/spikes/out/e31/ (git-ignored).
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
from m1_acceptance import Orch  # noqa: E402
from loom2 import set_things  # noqa: E402
from loom2.config import AppState  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = REPO / "engine" / "spikes" / "out" / "e31"
MODELS = Path("F:/loom2-models")
PORT = 8784
PICTURE = REPO / "bench" / "sets" / "room.jpg"
THINGS = {"Crate": [(325, 490)], "Table": [(790, 455), (722, 540)], "Small block": [(640, 590)], "Big block": [(1070, 480)]}
SAM_PROMPTS = [("shadow", 0.5), ("shadow", 0.3), ("shadow on the floor", 0.4)]


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rig.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def attached(region: np.ndarray, thing: np.ndarray, others: np.ndarray) -> np.ndarray:
    """The parts of a found region that touch the thing, within its reach (S's arm, the same reach as P's)."""
    xs = np.nonzero(thing.any(axis=0))[0]
    reach = int(np.clip(set_things.SHADOW_REACH * (xs.max() - xs.min() + 1), 12, thing.shape[1] // 6))
    k = 4                                                                            # at a quarter size: quick
    small = lambda m: np.asarray(Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).resize((m.shape[1] // k, m.shape[0] // k))) > 127  # noqa: E731
    t, r, z = small(thing), small(region), set_things._grow(small(thing), reach // k)
    g = set_things._grow(t, 1) & r & z
    while True:
        n = set_things._grow(g, 1) & r & z
        if (n == g).all():
            break
        g = n
    big = np.asarray(Image.fromarray(np.where(g, 255, 0).astype(np.uint8)).resize(thing.shape[::-1])) > 127
    return big & ~thing & ~others


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rig.log").unlink(missing_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    shutil.rmtree(OUT / "_proj", ignore_errors=True)
    AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full"})
    o = Orch(state, PORT).start(timeout=180)
    result: dict = {"things": {}, "sam": {}, "fills": {}}
    try:
        h = o.http
        assert h.post("/project", json={"path": str(OUT / "_proj"), "name": "E31", "size_cap_gb": 10}).status_code == 200
        pic = h.post("/assets/import", json={"paths": [str(PICTURE)]}).json()["items"][0]
        rgb = np.asarray(Image.open(PICTURE).convert("RGB"))
        H, W = rgb.shape[:2]

        def document() -> str:
            return h.post("/documents", json={"from_asset": pic["id"]}).json()["id"]

        def run(recipe: dict, what: str, timeout: float = 900) -> dict:
            t0 = time.time()
            jid = h.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]["id"]
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=timeout)
            log(f"{what}: {j['status']} in {time.time() - t0:.1f} s")
            if j["status"] != "done":
                raise SystemExit(f"{what} {j['status']}: {j.get('error')}")
            return j

        def selection(doc: str) -> np.ndarray:
            r = h.get(f"/documents/{doc}/selection")
            return np.frombuffer(r.content, np.uint8).reshape(H, W) > 127 if r.status_code == 200 else np.zeros((H, W), bool)

        doc = document()
        masks: dict[str, np.ndarray] = {}
        for name, pts in THINGS.items():
            run({"kind": "segment", "document_id": doc, "mode": "points", "points": [{"x": x, "y": y, "label": 1} for x, y in pts], "op": "replace"}, f"find {name}", 600)
            masks[name] = selection(doc)
            log(f"  {name}: {masks[name].mean() * 100:.2f} % of the picture")
        sam: dict[str, np.ndarray] = {}
        for text, thr in SAM_PROMPTS:
            t0 = time.time()
            run({"kind": "segment", "document_id": doc, "mode": "text", "text": text, "threshold": thr, "op": "replace"}, f"SAM 3 '{text}' at {thr}", 600)
            sam[f"{text}@{thr}"] = selection(doc)
            result["sam"][f"{text}@{thr}"] = {"coverage": round(float(sam[f'{text}@{thr}'].mean()), 4), "s": round(time.time() - t0, 1)}
            log(f"  '{text}' at {thr}: {sam[f'{text}@{thr}'].mean() * 100:.2f} % of the picture")
        every = np.zeros((H, W), bool)
        for m in masks.values():
            every |= m
        best_sam = max(sam, key=lambda k: sam[k].mean())                              # the most generous reading, for the attached arm
        shadows: dict[str, dict[str, np.ndarray]] = {"S": {}, "P": {}}
        t0 = time.time()
        found = set_things.shadows_of(rgb, list(masks.values()))
        p_s = time.time() - t0
        result["P_s"] = round(p_s, 2)
        for (name, m), sh in zip(masks.items(), found):
            others = every & ~m
            shadows["P"][name] = sh
            Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).save(OUT / f"mask_{name.replace(' ', '_')}.png")
            shadows["S"][name] = attached(sam[best_sam], m, others)
            result["things"][name] = {"mask": round(float(m.mean()), 4), "P": round(float(shadows["P"][name].mean()), 4), "P_s": round(p_s, 2),
                                      "S": round(float(shadows["S"][name].mean()), 4)}
            log(f"  {name}: its shadow P {shadows['P'][name].mean() * 100:.2f} % ({p_s:.2f} s), S ({best_sam}) {shadows['S'][name].mean() * 100:.2f} %")
        # the masks over the picture: the things blue, SAM's raw shadow red (left), S's attached red and P's green (middle, right)
        def tint(base: np.ndarray, layers: list[tuple[np.ndarray, tuple[int, int, int]]]) -> Image.Image:
            im = base.astype(np.float32).copy()
            for m, c in layers:
                im[m] = im[m] * 0.45 + np.array(c, np.float32) * 0.55
            return Image.fromarray(im.clip(0, 255).astype(np.uint8))
        s_all = np.zeros((H, W), bool)
        p_all = np.zeros((H, W), bool)
        for name in masks:
            s_all |= shadows["S"][name]
            p_all |= shadows["P"][name]
        panels = [tint(rgb, [(every, (40, 90, 255)), (sam[best_sam] & ~every, (255, 40, 40))]), tint(rgb, [(every, (40, 90, 255)), (s_all, (255, 40, 40))]),
                  tint(rgb, [(every, (40, 90, 255)), (p_all, (40, 220, 60))])]
        tw = 640
        th = round(tw * H / W)
        sheet = Image.new("RGB", (tw * 3 + 8, th + 26), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        for i, (p, label) in enumerate(zip(panels, [f"SAM 3 '{best_sam}' (red)", "S: its parts touching a thing", "P: shadow_of (green)"])):
            sheet.paste(p.resize((tw, th), Image.LANCZOS), (i * (tw + 4), 26))
            d.text((i * (tw + 4) + 6, 6), label, fill=(230, 230, 230))
        sheet.save(OUT / "masks.jpg", quality=88)
        # the clean plate three ways
        arms = {"things": every, "S": every | s_all, "P": every | p_all}
        plates = {}
        for arm, region in arms.items():
            dd = document()
            grown = set_things._grow(region, set_things.CLEAN_GROW)
            sel = np.where(grown, 255, 0).astype(np.uint8)
            assert h.put(f"/documents/{dd}/selection?w={W}&h={H}", content=sel.tobytes(), headers={"Content-Type": "application/octet-stream"}).status_code == 200
            t0 = time.time()
            run({"kind": "inpaint", "mode": "fill", "document_id": dd, "prompt_text": set_things.CLEAN_PROMPT}, f"the clean plate ({arm})")
            png = h.post(f"/documents/{dd}/export", json={"format": "png"}).content
            plates[arm] = Image.open(io.BytesIO(png)).convert("RGB")
            plates[arm].save(OUT / f"clean_{arm}.png")
            result["fills"][arm] = {"coverage": round(float(grown.mean()), 4), "s": round(time.time() - t0, 1)}
        sheet = Image.new("RGB", (tw * 2 + 4, th * 2 + 4 + 52), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        for i, (im, label) in enumerate([(Image.fromarray(rgb), "the picture"), (plates["things"], "clean: the things alone (SC3c)"),
                                          (plates["S"], "clean: + S's shadows"), (plates["P"], "clean: + P's shadows")]):
            x, y = (i % 2) * (tw + 4), (i // 2) * (th + 30)
            sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 26))
            d.text((x + 6, y + 6), label, fill=(230, 230, 230))
        sheet.save(OUT / "clean.jpg", quality=88)
        for f in ("masks.jpg", "clean.jpg"):
            shutil.copyfile(OUT / f, REPO / ".docs" / "proto01_animate" / "img" / f"25-e31-{f}")
        h.post("/engine/stop", timeout=60)
        log("the engine stopped; sheets masks.jpg and clean.jpg (also proto01_animate/img/25-e31-*)")
    finally:
        (OUT / "result.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
