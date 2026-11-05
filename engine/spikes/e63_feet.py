"""E63 (RG2b, D188 F5): does Wan Animate follow the guide's rolling feet? The second half of engine/spikes/e63_feet.cjs: the two takes of
Nora's layer on Followed's shot 1 — the one of 2026-11-04 (the old guide: the feet carried flat on the shins) and the one made today (the
guide's heels and toes rolling with the clip) — read by SDPose without person boxes (the product's compiled graph, sent to the engine
directly, as E62 a2), every other frame. Each foot's lift is measured in the picture: the heel's height above its own big toe, over the
leg's length (hip → ankle) — what a heel strike (toe up), a flat stance and a push-off (heel up) change most from the camera's side. For
each take the guide's lift (its stored wholebody keypoints, the feet left first) beside what Wan drew: the correlation over the frames,
the range, and a contact sheet of the feet at the guide's extremes.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e63_feet.py read     # SDPose on both takes (the engine running, the queue idle)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e63_feet.py measure  # the numbers and the sheet, to out/e63/
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("LOOM2_BASE", "http://127.0.0.1:8766")
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
PROJECT = Path(os.environ.get("E63_PROJECT", "F:/loom2-projects/propo02-followed"))
OUT = Path(__file__).resolve().parent / "out" / "e63"
OUT.mkdir(parents=True, exist_ok=True)
STEP = 2
OLD = ("fin_3dfcdecf", "fig_7pe3mq4s")                                     # 2026-11-04 02:02, before RG2b


def api(method: str, path: str) -> dict:
    req = urllib.request.Request(BASE + path, method=method, headers={"X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def engine_port() -> int:
    return int(api("GET", "/engine")["port"])


def engine_run(graph: dict, timeout: float = 600) -> dict:
    port = engine_port()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/prompt", data=json.dumps({"prompt": graph}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pid = json.loads(r.read())["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/history/{pid}", timeout=30) as r:
            h = json.loads(r.read())
        if pid in h and h[pid].get("outputs"):
            return h[pid]
        if pid in h and h[pid].get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(h[pid]["status"])[:800])
        time.sleep(0.3)
    raise TimeoutError(pid)


def engine_upload(img: Image.Image, name: str) -> str:
    buf = io.BytesIO(); img.save(buf, "PNG")
    boundary = "----e63" + str(int(time.time() * 1000))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"http://127.0.0.1:{engine_port()}/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def takes() -> dict[str, Path]:
    run = json.loads((OUT / "run.json").read_text(encoding="utf-8"))
    return {"old": PROJECT / "finals" / OLD[0] / OLD[1], "new": PROJECT / "finals" / run["final"] / run["layer"]}


def read() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orchestrator"))
    from loom2.roster import ROSTER_BY_ID
    sdpose = ROSTER_BY_ID["sdpose-wholebody"].name
    for tag, d in takes().items():
        cache = OUT / f"{tag}_sdpose.json"
        got = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
        frames = sorted((d / "frames").glob("*.png"))
        for i in range(0, len(frames), STEP):
            if str(i) in got:
                continue
            name = engine_upload(Image.open(frames[i]).convert("RGB"), f"e63-{tag}-{i:04d}.png")
            g = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": sdpose}}, "3": {"class_type": "LoadImage", "inputs": {"image": name}},
                 "5": {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["1", 0], "vae": ["1", 2], "image": ["3", 0], "batch_size": 1}},
                 "6": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}}}
            out = next(iter(engine_run(g)["outputs"].values()))
            fr = json.loads((out.get("text") or ["[]"])[0])
            fr = (fr[0] if isinstance(fr, list) and fr else fr) or {}
            got[str(i)] = fr.get("people") or []
            if i % 20 == 0:
                print(tag, i, len(got[str(i)]), "people", flush=True)
                cache.write_text(json.dumps(got), encoding="utf-8")
        cache.write_text(json.dumps(got), encoding="utf-8")
        print(tag, "read", len(got), "frames")


def guide(d: Path) -> tuple[list, list]:
    k = json.loads((d / "keypoints.json").read_text(encoding="utf-8"))
    return k["frames"], k["wholebody"]


def lift(heel: np.ndarray, toe: np.ndarray, leg: float) -> float:
    """The heel's height above its big toe in the picture (y grows down), over the leg's length: + heel up (push-off), − toe up (strike)."""
    return float((toe[1] - heel[1]) / max(leg, 1.0))


def feet_of_person(p: dict) -> list[tuple[np.ndarray, np.ndarray]] | None:
    f = np.array(p.get("foot_keypoints_2d") or [], float).reshape(-1, 3)
    if len(f) < 6:
        return None
    return [(f[2], f[0]), (f[5], f[3])]                                     # (heel, big toe): COCO-WholeBody's feet, the left first


def measure() -> None:
    rows: dict[str, dict] = {}
    for tag, d in takes().items():
        body, wb = guide(d)
        sd = json.loads((OUT / f"{tag}_sdpose.json").read_text(encoding="utf-8"))
        g_l, o_l, idx = [], [], []
        for si, people in sd.items():
            i = int(si)
            b = np.array(body[i], float)
            hip = (b[8][:2] + b[11][:2]) / 2
            leg = float(np.linalg.norm(b[8][:2] - b[10][:2]) + np.linalg.norm(b[11][:2] - b[13][:2])) / 2
            gf = np.array(wb[i]["feet"], float)
            gfeet = [(gf[2], gf[0]), (gf[5], gf[3])]
            # the person SDPose read nearest the guide's hips
            best, bd = None, 1e9
            for p in people:
                pp = np.array(p.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
                if len(pp) < 14 or pp[8][2] < 0.3 or pp[11][2] < 0.3:
                    continue
                dd = float(np.linalg.norm((pp[8][:2] + pp[11][:2]) / 2 - hip))
                if dd < bd:
                    best, bd = p, dd
            if best is None or bd > leg:
                continue
            of = feet_of_person(best)
            if of is None:
                continue
            for gh, gt in gfeet:                                            # each guide foot matched to the nearer read foot (left / right swaps)
                k = min(range(2), key=lambda j: float(np.linalg.norm(of[j][0][:2] - gh[:2])))
                oh, ot = of[k]
                if min(oh[2], ot[2]) < 0.3 or float(np.linalg.norm(oh[:2] - gh[:2])) > 0.35 * leg:
                    continue
                g_l.append(lift(gh, gt, leg)); o_l.append(lift(oh, ot, leg)); idx.append(i)
        g, o = np.array(g_l), np.array(o_l)
        r = float(np.corrcoef(g, o)[0, 1]) if len(g) > 3 and g.std() > 1e-6 and o.std() > 1e-6 else float("nan")
        rows[tag] = {"samples": len(g), "r": round(r, 3), "guide_range": [round(float(np.percentile(g, 5)), 3), round(float(np.percentile(g, 95)), 3)],
                     "drawn_range": [round(float(np.percentile(o, 5)), 3), round(float(np.percentile(o, 95)), 3)], "guide_sd": round(float(g.std()), 4),
                     "drawn_sd": round(float(o.std()), 4), "mean_abs_diff": round(float(np.abs(g - o).mean()), 4),
                     "frames": idx, "guide": [round(x, 4) for x in g_l], "drawn": [round(x, 4) for x in o_l]}
        print(tag, {k: v for k, v in rows[tag].items() if k not in ("frames", "guide", "drawn")})
    (OUT / "measure.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    sheet(rows)


def sheet(rows: dict) -> None:
    """The feet at the new guide's three most heel-up and three most toe-up frames: the guide's pose pass, the old take, the new take."""
    t = takes()
    new = rows["new"]
    order = sorted(range(len(new["guide"])), key=lambda k: new["guide"][k])
    pick = sorted({new["frames"][k] for k in order[:3] + order[-3:]})
    body, _ = guide(t["new"])
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    cell = 200
    out = Image.new("RGB", (cell * 3, cell * len(pick) + 24), (20, 20, 24))
    dr = ImageDraw.Draw(out)
    for c, lab in enumerate(["the guide (today)", "old take (flat guide)", "new take (rolling guide)"]):
        dr.text((c * cell + 6, 4), lab, fill=(255, 210, 80), font=font)
    for r_, i in enumerate(pick):
        b = np.array(body[i], float)
        ank = (b[10][:2] + b[13][:2]) / 2
        leg = float(np.linalg.norm(b[8][:2] - b[10][:2]))
        half = max(40.0, 0.55 * leg)
        box = (int(ank[0] - half), int(ank[1] - half * 1.1), int(ank[0] + half), int(ank[1] + half * 0.9))
        for c, img in enumerate([t["new"] / "pose" / f"{i:04d}.png", t["old"] / "frames" / f"{i:04d}.png", t["new"] / "frames" / f"{i:04d}.png"]):
            if img.is_file():
                out.paste(Image.open(img).convert("RGB").crop(box).resize((cell, cell)), (c * cell, 24 + r_ * cell))
        dr.text((4, 24 + r_ * cell + 4), f"f{i}", fill=(255, 255, 255), font=font)
    out.save(OUT / "feet_sheet.png")
    print("sheet", OUT / "feet_sheet.png", pick)


if __name__ == "__main__":
    {"read": read, "measure": measure}[sys.argv[1]]()
