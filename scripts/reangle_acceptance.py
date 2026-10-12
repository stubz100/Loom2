"""P14 (D82) acceptance: E12's bars reproduced through the app (ArtCraft 08 §9 P14). Against a running dev orchestrator with the real
engine (`scripts/dev.ps1 -Browser`, port 8766, token devtoken).

Imports the ten frozen E12 sources (bench/angles/NN.jpg) and submits a `Reangle` job per move (method `auto`, one seed) through
`POST /jobs`; for every job: the method and model the server resolved to, the job's wall time, the result asset (lineage `reangle`,
parent = the source), ArcFace identity source → result (loom2.tools.facesim, evaluation only); a contact sheet per move and
engine/spikes/out/reangle/results.jsonl. Bars (08 §7 E12, D77): warm ≤ 60 s (A ≈ 32, Klein ≈ 6), cold ≤ 180 s, identity ≥ 0.5 median;
the correct move is judged on the sheets (A rotations ≥ 7/10, Klein framing 9 / 10 / 9 in E12).

    LOOM2_TOKEN=devtoken orchestrator/.venv/Scripts/python.exe scripts/reangle_acceptance.py --port 8766 [--sources 01,02] [--moves left45,wide]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(REPO / "engine" / "spikes"))
from loom2.tools.facesim import FaceSim, available  # noqa: E402

BENCH = REPO / "bench" / "angles"
OUT = REPO / "engine" / "spikes" / "out" / "reangle"
RESULTS = OUT / "results.jsonl"
MODELS_ROOT = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
MOVES = ["left45", "right45", "topdown", "closeup", "wide"]


def call(base: str, method: str, path: str, body=None, raw: bool = False):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8"))


def wait_job(base: str, jid: str, timeout_s: float = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = call(base, "GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1.0)
    raise TimeoutError(jid)


def largest_face(fs: FaceSim, img: Image.Image) -> np.ndarray | None:
    a = np.asarray(img.convert("RGB"))
    faces = fs.detect(a)
    if not faces:
        return None
    f = max(faces, key=lambda x: x.area)
    return fs.embed(a, f.kps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--sources", default="01,02,03,04,05,06,07,08,09,10")
    ap.add_argument("--moves", default=",".join(MOVES))
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    OUT.mkdir(parents=True, exist_ok=True)
    fs = FaceSim(MODELS_ROOT) if available(MODELS_ROOT) else None
    caps = call(base, "GET", "/capabilities")
    print("reangle capabilities:", json.dumps(caps["reangle"]["auto"]), {k: (v["model_id"], v["health"]) for k, v in caps["reangle"]["methods"].items()})
    sources = a.sources.split(",")
    imported = {}
    for sid in sources:
        items = call(base, "POST", "/assets/import", {"paths": [str(BENCH / f"{sid}.jpg")]})["items"]
        imported[sid] = items[0]["id"]
    ref = {sid: (largest_face(fs, Image.open(BENCH / f"{sid}.jpg")) if fs else None) for sid in sources}
    rows = []
    first_by_method: dict[str, bool] = {}
    for move in a.moves.split(","):
        for sid in sources:
            recipe = {"kind": "reangle", "asset_id": imported[sid], "move": move, "method": "auto", "seeds": [20261012]}
            pv = call(base, "POST", "/recipes/preview", {"recipe": recipe})
            method = pv["params"]["method"]
            t0 = time.time()
            job = call(base, "POST", "/jobs", {"recipe": recipe, "origin": {"suite": "generate", "surface": "angle"}})["jobs"][0]
            j = wait_job(base, job["id"])
            wall = time.time() - t0
            row = {"move": move, "source": sid, "method": method, "model_id": pv["params"]["model_id"], "status": j["status"], "wall_s": round(wall, 1),
                   "cold": not first_by_method.get(method, False), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
            first_by_method[method] = True
            if j["status"] == "done" and j.get("result", {}).get("asset_ids"):
                aid = j["result"]["asset_ids"][0]
                asset = call(base, "GET", f"/assets/{aid}")
                png = call(base, "GET", f"/assets/{aid}/file", raw=True)
                img = Image.open(io.BytesIO(png)).convert("RGB")
                img.save(OUT / f"{move}_{sid}_{method}.jpg", quality=90)
                row["asset_id"] = aid
                row["parents"] = list(asset.get("parents", []))
                row["lineage"] = [e.get("kind") for e in call(base, "GET", f"/lineage/{aid}").get("parents", [])]
                if fs and ref[sid] is not None:
                    e = largest_face(fs, img)
                    row["identity"] = None if e is None else round(float(FaceSim.similarity(ref[sid], e)), 3)
            else:
                row["error"] = (j.get("log_tail") or [""])[-1][:300]
            rows.append(row)
            with RESULTS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"[{move} {sid}] {method} {row['status']} {wall:.1f} s identity {row.get('identity')}")
    # summary and sheets
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["method"], []).append(r)
    for m, rs in by.items():
        warm = [r["wall_s"] for r in rs if not r["cold"] and r["status"] == "done"]
        cold = [r["wall_s"] for r in rs if r["cold"]]
        ids = [r["identity"] for r in rs if r.get("identity") is not None]
        print(f"{m}: done {sum(1 for r in rs if r['status'] == 'done')}/{len(rs)} · warm median {np.median(warm) if warm else float('nan'):.1f} s (bar 60) · cold {cold} (bar 180)"
              f" · identity median {np.median(ids) if ids else float('nan'):.3f} over {len(ids)} ({sum(1 for x in ids if x >= 0.5)} ≥ 0.5) · lineage ok "
              f"{sum(1 for r in rs if r.get('lineage') == ['reangle'])}/{len(rs)}")
    for move in a.moves.split(","):
        tw, th = 384, 216
        sheet = Image.new("RGB", (40 + 2 * (tw + 4), len(sources) * (th + 4)), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for i, sid in enumerate(sources):
            dr.text((4, i * (th + 4) + th // 2), sid, fill=(240, 180, 60))
            r = next((x for x in rows if x["move"] == move and x["source"] == sid), None)
            cells = [BENCH / f"{sid}.jpg"] + ([OUT / f"{move}_{sid}_{r['method']}.jpg"] if r and r.get("asset_id") else [])
            for j, p in enumerate(cells):
                if p.is_file():
                    im = Image.open(p).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (40 + j * (tw + 4), i * (th + 4)))
        sheet.save(OUT / f"sheet_{move}.jpg", quality=84)
    print(f"sheets: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
