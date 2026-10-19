"""CA1b (D104) acceptance on the rig, through the app's API: E23b's two characters (Mara, Ines — their animation references in
engine/spikes/out/e23b/refs/) as Cast profiles, each version's body fitted by the app's `keypoints` job (SDPose wholebody + RT-DETR on the
engine, one GPU job at a time). Writes engine/spikes/out/ca1b/bodies.json (the fitted bodies) and targets.json (the references' ratios, the
fit's report), which `scripts/ca1b_skeleton_check.py --bodies … --targets …` then holds Stage's skeleton to (±10 %).

`--part look` (after E23b's Move shot was made again with these bodies, `LOOM2_E23B_OUT=engine/spikes/out/ca1b/e23b_fit
LOOM2_E23B_BODIES=…/bodies.json e23b_layers.py stage | run | score`): SDPose on the characters' Move layers where they stand, the
proportions against the references as E23b measured them (journal 2026-10-19 17:10), and a before | after video and sheet for the
author (E23b's first Move shot against this one, the same seed).

Needs port 8188 free (the orchestrator launches the engine).

    orchestrator/.venv/Scripts/python.exe scripts/ca1b_acceptance.py [--part fit|look]
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from m1_acceptance import Orch, port_busy  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ca1b"
REFS = ROOT / "engine" / "spikes" / "out" / "e23b" / "refs"
PORT = 8789
CAST = {"Mara": "mara.png", "Ines": "ines.png"}


def look() -> int:
    import numpy as np
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    import e23a_joins as A
    from e10_stage import sdpose_graph
    from e23b_proportions import ratios
    before, after = ROOT / "engine" / "spikes" / "out" / "e23b", OUT / "e23b_fit"
    frames = {"fig_m": ("Mara", (110, 140, 160)), "fig_i": ("Ines", (0, 8, 16))}
    targets = json.loads((OUT / "targets.json").read_text(encoding="utf-8"))
    rows: dict = {}
    with A.Session() as x:
        for tag, base in (("before", before), ("after", after)):
            for fid, (name, idx) in frames.items():
                acc = []
                for i in idx:
                    hp, _, _ = x.e.run(sdpose_graph(x.e.upload(base / "runs" / "M_s20261021" / fid / "chain" / f"{i:04d}.png")))
                    people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                    if people:
                        p = max(people, key=lambda q: sum(q["pose_keypoints_2d"][2::3]))
                        r = ratios(p["pose_keypoints_2d"], [p.get("hand_left_keypoints_2d"), p.get("hand_right_keypoints_2d")], p.get("foot_keypoints_2d"))
                        if r:
                            acc.append(r)
                rows[f"{name} {tag}"] = {k: round(float(np.median([a[k] for a in acc if k in a])), 3) for k in acc[0]} if acc else None
    for k, v in rows.items():
        print(f"{k:14s}", v)
    # before | after, the same seed: compare.mp4 (24 fps after RIFE) and a sheet of a frame a second
    b24 = sorted((before / "runs" / "M_s20261021" / "rife24").glob("*.png"))
    a24 = sorted((after / "runs" / "M_s20261021" / "rife24").glob("*.png"))
    n = min(len(b24), len(a24))
    tw, th = A.W // 2, A.H // 2
    grid = []
    for i in range(n):
        im = Image.new("RGB", (tw * 2, th), (0, 0, 0))
        for c, (lab, seq) in enumerate((("before: the default dummy", b24), ("after: fitted to the references (CA1b)", a24))):
            im.paste(A.label(Image.open(seq[i]).convert("RGB").resize((tw, th), Image.LANCZOS), f"{lab} · {i / 24:.2f} s"), (c * tw, 0))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    cw, ch = 208, 120
    sheet = Image.new("RGB", (8 + 11 * (cw + 2), 8 + 2 * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for r_, (lab, base) in enumerate((("before", before), ("after", after))):
        merged = sorted((base / "runs" / "M_s20261021" / "merged").glob("*.png"))
        dr.text((8, 8 + r_ * (ch + 18)), lab, fill=(230, 230, 230))
        for c in range(11):
            sheet.paste(Image.open(merged[min(len(merged) - 1, c * 16)]).convert("RGB").resize((cw, ch), Image.LANCZOS), (8 + c * (cw + 2), 22 + r_ * (ch + 18)))
    sheet.save(OUT / "sheet.jpg", quality=90)
    (OUT / "look.json").write_text(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M"), "rows": rows, "targets": targets}, indent=1), encoding="utf-8")
    print(f"compare: {OUT / 'compare.mp4'} · sheet: {OUT / 'sheet.jpg'}")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["fit", "look"], default="fit")
    if ap.parse_args().part == "look":
        return look()
    from loom2.config import AppState
    import os
    if port_busy(8188):
        print("the engine port is busy — one GPU job at a time"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-ca1b-fit-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8188}})
    o = Orch(tmp / "state", PORT).start()
    bodies, targets, rows, failures = {}, {}, [], []
    try:
        assert o.http.post("/project", json={"path": str(tmp / "proj"), "name": "CA1b", "size_cap_gb": 20}).status_code == 200
        for name, file in CAST.items():
            ref = o.http.post("/assets/import", json={"paths": [str(REFS / file)]}).json()["items"][0]["id"]
            p = o.http.post("/story/profiles", json={"name": name, "cls": "character", "appearance": name}).json()
            o.http.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "asset_id": ref})
            t0 = time.time()
            r = o.http.post(f"/story/profiles/{p['id']}/versions/v1/body/fit", timeout=60)
            if r.status_code != 200:
                failures.append(f"{name}: {r.status_code} {r.text[:200]}"); continue
            jid = r.json()["job_id"]
            while True:
                j = next((x for x in o.http.get("/jobs").json()["items"] if x["id"] == jid), None)
                if j and j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(1.0)
            if j["status"] != "done":
                failures.append(f"{name}: the fit job {j['status']} ({j.get('error')})"); continue
            v = o.http.get(f"/story/profiles/{p['id']}").json()["versions"][0]
            bodies[name] = v["body"]
            targets[name] = {k: x["reference"] for k, x in j["result"]["fit"].items()}
            rows.append({"name": name, "wall_s": round(time.time() - t0, 1), "job_wall_s": j.get("wall_s"), "people": len(j["result"]["people"]),
                         "body": {k: v["body"][k] for k in ("neck", "torso", "shoulders", "arms", "legs", "hands")}, "fit": j["result"]["fit"],
                         "fitted_from": v["body_fit_from"] == ref})
            print(name, rows[-1])
    finally:
        try:
            o.http.post("/engine/stop", timeout=120); o.http.post("/shutdown", timeout=30)
        except Exception:
            pass
        time.sleep(2)
        if o.proc and o.proc.poll() is None:
            o.proc.kill()
    (OUT / "bodies.json").write_text(json.dumps(bodies, indent=1), encoding="utf-8")
    (OUT / "targets.json").write_text(json.dumps(targets, indent=1), encoding="utf-8")
    with (OUT / "acceptance.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M"), "rows": rows, "failures": failures}) + "\n")
    for x in failures:
        print("FAIL", x)
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
