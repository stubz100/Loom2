"""M5 Edit AI acceptance (10 §14 items 3, 4 and 5, 12 §6) against a running dev orchestrator with the real engine.

Imports the frozen E8 bench source, opens it as a document, feeds the bench masks as the document's selection and
runs the editor's AI recipes through `POST /documents/{id}/ai`: Fill, Fill-Match and Remove on task 01 (crates),
Fill on task 02 (cloak), Outpaint right 240 (task 04), Refine 0.25 on the visible composite, Upscale when the
weights are present; then slice 2 (2026-10-06): AI Select — BiRefNet subject matte and SAM 3 text / point — scored
against the bench boxes, task 03 (background swap on the inverted matte: the subject must stay untouched), and the
tiled refine upscale. Each generative result must come back as a layer with the recipe attached; contact sheets of
the candidates (crop region, original on the left) land in engine/spikes/out/m5/ for scoring by eye (04 §6).

    LOOM2_TOKEN=devtoken python scripts/m5_acceptance.py --port 8766 [--hero] [--candidates 2]
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
BENCH = REPO / "bench" / "inpaint"
OUT = REPO / "engine" / "spikes" / "out" / "m5"
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")


def call(base: str, method: str, path: str, body=None, raw: bool = False, ctype: str | None = None):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body); headers["Content-Type"] = ctype or "application/octet-stream"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        payload = r.read()
        return payload if raw else (json.loads(payload) if payload else None)


def wait_jobs(base: str, ids: list[str], timeout_s: float) -> list[dict]:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout_s:
        jobs = {j["id"]: j for j in call(base, "GET", "/jobs")["items"]}
        mine = [jobs[i] for i in ids if i in jobs]
        if mine and all(j["status"] in ("done", "failed", "cancelled") for j in mine):
            return mine
        run = next((j for j in mine if j["status"] == "running"), None)
        msg = f"{run['progress_text']} {round(run['progress'] * 100)}%" if run else "queued"
        if msg != last:
            print(f"      … {msg}", flush=True); last = msg
        time.sleep(2)
    raise TimeoutError("jobs did not finish in time")


def layer_png(base: str, did: str, lid: str) -> Image.Image:
    raw = call(base, "GET", f"/documents/{did}/layers/{lid}/pixels", raw=True)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def sheet(name: str, original: Image.Image, results: list[tuple[str, Image.Image]], region: dict | None) -> Path:
    """Original crop on the left, candidates composited over it on the right."""
    if region:
        box = (region["x"], region["y"], region["x"] + region["w"], region["y"] + region["h"])
        orig = original.crop(box)
    else:
        box = (0, 0, original.width, original.height); orig = original
    cells = [("original", orig)]
    for label, layer in results:
        comp = original.copy()
        comp.alpha_composite(layer, (region["x"], region["y"]) if region else (0, 0))
        cells.append((label, comp.crop(box)))
    cw = min(480, orig.width); scale = cw / orig.width; ch = int(orig.height * scale)
    out = Image.new("RGB", (len(cells) * (cw + 8) + 8, ch + 28), (24, 24, 24))
    d = ImageDraw.Draw(out)
    for i, (label, im) in enumerate(cells):
        x = 8 + i * (cw + 8)
        out.paste(im.convert("RGB").resize((cw, ch), Image.Resampling.LANCZOS), (x, 22))
        d.text((x, 4), label, fill=(230, 230, 230))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    out.save(p)
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--hero", action="store_true", help="also run Fill Hero (dev + LanPaint, ≈ 5 min per candidate)")
    ap.add_argument("--candidates", type=int, default=2)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        results.append((name, bool(ok), info))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + info) if info else ''}", flush=True)

    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    tasks = {t["id"][:2]: t for t in spec["tasks"]}
    src = (BENCH / spec["source"]).resolve()
    original = Image.open(src).convert("RGBA")
    W, H = original.size

    imported = call(base, "POST", "/assets/import", {"paths": [str(src)]})["items"]
    check("bench source imported", len(imported) == 1, imported[0]["id"] if imported else "")
    doc = call(base, "POST", "/documents", {"from_asset": imported[0]["id"], "name": "m5-acceptance"})
    did = doc["id"]
    check("document created", doc["w"] == W and doc["h"] == H, f"{did} {W}×{H}")
    call(base, "POST", "/queue/unpause")

    def selection(task_id: str) -> None:
        m = np.asarray(Image.open(BENCH / "masks" / f"{tasks[task_id]['id']}.png").convert("L").resize((W, H)))
        call(base, "PUT", f"/documents/{did}/selection?w={W}&h={H}", m.tobytes())

    def run(name: str, recipe: dict, timeout_s: float = 1500, layers_expected: bool = True) -> tuple[list[dict], dict | None]:
        t0 = time.time()
        jobs = call(base, "POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"]
        print(f"    {name}: {len(jobs)} job(s) queued", flush=True)
        done = wait_jobs(base, [j["id"] for j in jobs], timeout_s)
        ok = all(j["status"] == "done" for j in done)
        if not layers_expected:
            info = " · ".join(f"{j['wall_s']} s" for j in done) + ("" if ok else " · " + "; ".join(str(j.get("error")) for j in done if j["status"] != "done"))
            check(f"{name}: job done", ok, info)
            return done, call(base, "GET", f"/documents/{did}")
        lids = [l for j in done for l in (j["result"].get("layers") or [])]
        d = call(base, "GET", f"/documents/{did}")
        nodes = {}
        def walk(ns):
            for n in ns:
                nodes[n["id"]] = n
                walk(n.get("children") or [])
        walk(d["layers"])
        layers = [nodes[l] for l in lids if l in nodes]
        wall = round(time.time() - t0, 1)
        info = f"{len(layers)} layer(s) in {wall} s · " + " · ".join(f"{j['wall_s']} s" for j in done)
        if not ok:
            info += " · " + "; ".join(str(j.get("error")) for j in done if j["status"] != "done")
        check(f"{name}: candidates returned as layers with recipes", ok and len(layers) == len(jobs) and all(l.get("recipe", {}).get("seed") is not None for l in layers), info)
        region = done[0]["result"].get("region") if done else None
        if layers:
            ims = [(f"{l['name']} · seed {l['recipe'].get('seed')}", layer_png(base, did, l["id"])) for l in layers]
            base_img = Image.open(io.BytesIO(call(base, "GET", f"/assets/{imported[0]['id']}/file", raw=True))).convert("RGBA")
            if d["w"] != base_img.width or d["h"] != base_img.height:
                padded = Image.new("RGBA", (d["w"], d["h"]), (0, 0, 0, 0)); padded.paste(base_img, (region["x"] * -1 if region and region["x"] < 0 else 0, 0)); base_img = padded
            p = sheet(name, base_img, ims, region if region and region["w"] < d["w"] else None)
            print(f"      sheet → {p}", flush=True)
        return done, d

    seeds = list(range(20261005, 20261005 + a.candidates))
    selection("01")
    run("fill (Klein + LanPaint) · 01 crates", {"kind": "inpaint", "mode": "fill", "prompt_text": tasks["01"]["prompt"], "seeds": seeds})
    run("fill_match (Klein ICM) · 01 crates", {"kind": "inpaint", "mode": "fill_match", "prompt_text": tasks["01"]["prompt"], "seeds": seeds[:1]})
    run("remove (ICM hole) · 01 crates", {"kind": "inpaint", "mode": "remove", "prompt_text": "empty wet cobblestone alley floor and a grimy brick wall", "seeds": seeds[:1]})
    selection("02")
    run("fill · 02 cloak", {"kind": "inpaint", "mode": "fill", "prompt_text": tasks["02"]["prompt"], "seeds": seeds})
    if a.hero:
        run("fill_hero (dev + LanPaint) · 02 cloak", {"kind": "inpaint", "mode": "fill_hero", "prompt_text": tasks["02"]["prompt"], "seeds": seeds[:1]}, timeout_s=2400)
    selection("05")
    run("fill · 05 face", {"kind": "inpaint", "mode": "fill", "prompt_text": tasks["05"]["prompt"], "seeds": seeds[:1]})
    call(base, "PUT", f"/documents/{did}/selection", b"")
    _, d = run("outpaint right 240 (LanPaint)", {"kind": "inpaint", "mode": "outpaint", "outpaint": {"right": 240}, "prompt_text": tasks["04"]["prompt"], "seeds": seeds[:1]})
    check("outpaint grew the document", d["w"] == W + 240 and d["h"] == H, f"{d['w']}×{d['h']}")
    run("refine 0.25 (Klein base) · visible", {"kind": "i2i", "model_id": "klein-base-9b", "source": "visible", "strength": 0.25, "prompt_text": "", "seeds": seeds[:1]})
    models = {m["id"]: m for m in call(base, "GET", "/models")["items"]}
    if models.get("realesrgan-x2", {}).get("health") in ("present", "verified"):
        done, _ = run("upscale ×2 (Real-ESRGAN)", {"kind": "upscale", "model_id": "realesrgan-x2", "source": "visible", "as_layer": True, "seeds": [0]})
        check("upscale produced a Catalogue asset", bool(done and done[0]["result"].get("asset_ids")), str(done[0]["result"].get("asset_ids") if done else ""))
    else:
        print("  [skip] upscale: realesrgan-x2 not fetched (Models → fetch)")
    # ---- slice 2 (2026-10-06): AI Select, task 03, tiled refine ---------------------------------------------------
    d = call(base, "GET", f"/documents/{did}")
    DW, DH = d["w"], d["h"]

    def get_selection() -> np.ndarray | None:
        try:
            raw = call(base, "GET", f"/documents/{did}/selection", raw=True)
        except Exception:
            return None
        return np.frombuffer(raw, dtype=np.uint8).reshape((DH, DW))

    def box_mean(sel: np.ndarray, box: list[int]) -> float:
        x0, y0, x1, y1 = box
        return float(sel[y0:y1, x0:x1].mean() / 255.0)

    box_subject = tasks["02"]["mask"]["boxes"][0]        # the cloak box: mostly figure
    box_crates = tasks["01"]["mask"]["boxes"][0]         # the crates: no figure
    face_box = tasks["05"]["mask"]["boxes"][0]

    def score_matte(name: str, sel: np.ndarray | None) -> None:
        if sel is None:
            check(f"{name}: selection present", False, "GET /selection returned nothing"); return
        cov, subj, crates, face = float(sel.mean() / 255), box_mean(sel, box_subject), box_mean(sel, box_crates), box_mean(sel, face_box)
        check(f"{name}: matte covers the figure (face + cloak), not the crates", face > 0.6 and subj > 0.35 and crates < 0.15 and 0.05 < cov < 0.6,
              f"face {face:.2f} · cloak box {subj:.2f} · crates box {crates:.2f} · canvas {cov:.2f}")

    if models.get("birefnet", {}).get("health") in ("present", "verified"):
        call(base, "PUT", f"/documents/{did}/selection", b"")
        run("AI select · subject (BiRefNet)", {"kind": "segment", "model_id": "birefnet", "mode": "subject", "feather": 2, "seeds": [0]}, layers_expected=False)
        matte = get_selection()
        score_matte("BiRefNet subject", matte)
        if matte is not None:
            # bench task 03: background swap — fill everything but the subject; the subject must come back untouched (alpha 0 there)
            inv = (255 - matte).astype(np.uint8)
            call(base, "PUT", f"/documents/{did}/selection?w={DW}&h={DH}", inv.tobytes())
            done, d2 = run("fill · 03 background swap (inverted matte)", {"kind": "inpaint", "mode": "fill", "prompt_text": tasks["03"]["prompt"], "feather": 6, "margin_pct": 0, "seeds": seeds[:1]})
            lids = [l for j in done for l in (j["result"].get("layers") or [])]
            if lids and done[0]["result"].get("region"):
                layer = layer_png(base, did, lids[0]); reg = done[0]["result"]["region"]
                full = Image.new("RGBA", (DW, DH), (0, 0, 0, 0)); full.paste(layer, (reg["x"], reg["y"]))
                alpha = np.asarray(full)[..., 3]                 # not `a`: that is the argparse namespace (the summary reads a.keep)
                inside = float(alpha[matte > 200].mean() / 255) if (matte > 200).any() else 1.0
                outside = float(alpha[matte < 30].mean() / 255) if (matte < 30).any() else 0.0
                check("03: subject preserved (layer alpha ≈ 0 on the matte), background repainted", inside < 0.08 and outside > 0.85, f"alpha on subject {inside:.3f} · on background {outside:.3f}")
    else:
        print("  [skip] AI select · subject: birefnet not fetched (Models → fetch)")
    if models.get("sam3", {}).get("health") in ("present", "verified"):
        call(base, "PUT", f"/documents/{did}/selection", b"")
        run("AI select · SAM 3 text", {"kind": "segment", "model_id": "sam3", "mode": "text", "text": "the young woman in the hooded cloak", "seeds": [0]}, layers_expected=False)
        score_matte("SAM 3 text", get_selection())
        cx, cy = (face_box[0] + face_box[2]) // 2, (face_box[1] + face_box[3]) // 2
        run("AI select · SAM 3 point (face) added to the selection", {"kind": "segment", "model_id": "sam3", "mode": "points", "points": [{"x": cx, "y": cy, "label": 1}], "op": "add", "seeds": [0]}, layers_expected=False)
        sel = get_selection()
        check("SAM 3 point: the face is selected", sel is not None and box_mean(sel, face_box) > 0.5, f"face {box_mean(sel, face_box):.2f}" if sel is not None else "no selection")
        # C32 (2026-10-07): box mode wired the preview IMAGE instead of the BOUNDING_BOX output; the engine must accept the graph
        call(base, "PUT", f"/documents/{did}/selection", b"")
        run("AI select · SAM 3 box (the cloak box)", {"kind": "segment", "model_id": "sam3", "mode": "box", "box": box_subject, "seeds": [0]}, layers_expected=False)
        sel = get_selection()
        check("SAM 3 box: the boxed figure is selected, the crates are not", sel is not None and box_mean(sel, box_subject) > 0.35 and box_mean(sel, box_crates) < 0.15,
              f"cloak box {box_mean(sel, box_subject):.2f} · crates box {box_mean(sel, box_crates):.2f}" if sel is not None else "no selection")
    else:
        print("  [skip] AI select · SAM 3: sam3.pt not found (mounted sam3/ folder)")
    if models.get("realesrgan-x2", {}).get("health") in ("present", "verified") and models.get("klein-base-9b", {}).get("health") in ("present", "verified"):
        call(base, "PUT", f"/documents/{did}/selection", b"")
        done, _ = run("upscale ×2 + tiled refine (Klein base, tile 1024 / 128, strength 0.25)", {"kind": "upscale", "model_id": "realesrgan-x2", "source": "visible", "as_layer": False,
                                                                                               "refine": True, "refine_model_id": "klein-base-9b", "strength": 0.25, "tile": 1024, "overlap": 128,
                                                                                               "prompt_text": tasks["01"]["prompt"], "seeds": [20261006]}, timeout_s=1800, layers_expected=False)
        aid = (done[0]["result"].get("asset_ids") or [None])[0] if done else None
        arow = call(base, "GET", f"/assets/{aid}") if aid else None            # not `a`: that is the argparse namespace
        check("tiled refine produced the 2× asset", bool(arow) and arow["w"] == 2 * DW and arow["h"] == 2 * DH, f"{arow['w']}×{arow['h']} · tiles {done[0]['result'].get('compiled', {}).get('tiles')}" if arow else "no asset")
    else:
        print("  [skip] tiled refine: realesrgan-x2 or klein-base-9b not present")

    saved = call(base, "GET", "/documents")["items"]
    me = next((x for x in saved if x["id"] == did), None)
    check("document saved after each result (ORA on disk)", bool(me and me["saved_at"]), str(me and me["layers"]) + " nodes")
    if not a.keep:
        call(base, "DELETE", f"/documents/{did}")
    ok = sum(1 for _, o, _ in results if o)
    print(f"\nM5 acceptance: {ok}/{len(results)} passed")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
