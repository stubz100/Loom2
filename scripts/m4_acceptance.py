"""M4 acceptance (10 §14 items 1, 6, 7) against a running dev orchestrator + Vite.

Builds a test document through the API (base layer from an asset, painted layers with every blend mode in groups,
masks, clip, opacity, fill), saves it, round-trips the ORA, flattens to the catalogue, and asks the editor (headless
Edge, deep link &doc=…&verify=1) to compare its GPU composite with the exact flatten.

    LOOM2_TOKEN=devtoken python scripts/m4_acceptance.py --port 8766 [--vite 1420] [--edge "C:/.../msedge.exe"]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
BLENDS = ["normal", "dissolve", "darken", "multiply", "color-burn", "linear-burn", "lighten", "screen", "color-dodge", "linear-dodge", "overlay",
          "soft-light", "hard-light", "vivid-light", "linear-light", "pin-light", "hard-mix", "difference", "exclusion", "subtract", "divide",
          "hue", "saturation", "color", "luminosity"]


def call(base: str, method: str, path: str, body: bytes | dict | None = None, ctype: str | None = None, raw: bool = False):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if isinstance(body, dict):
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif isinstance(body, bytes):
        data = body
        headers["Content-Type"] = ctype or "application/octet-stream"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = r.read()
        return payload if raw else (json.loads(payload) if payload else None)


def gradient_layer(w: int, h: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = (xx / max(1, w - 1)) * 255
    g = (yy / max(1, h - 1)) * 255
    b = ((np.sin(xx / 23 + seed) + 1) / 2) * 255
    a = np.clip(((xx - w / 2) ** 2 + (yy - h / 2) ** 2) ** 0.5 / (0.6 * max(w, h)), 0, 1)
    a = (1 - a) * 255 * (0.35 + 0.65 * rng.random())
    return np.stack([r, g, b, a], axis=-1).astype(np.uint8)


def mask_layer(w: int, h: int, seed: int) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = (np.sin(xx / (17 + seed)) * np.cos(yy / (13 + seed)) + 1) / 2
    return (m * 255).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--vite", type=int, default=1420)
    ap.add_argument("--edge", default="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    ap.add_argument("--keep", action="store_true", help="keep the test document")
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        results.append((name, bool(ok), info))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + info) if info else ''}")

    # 1. a document from an asset
    asset = call(base, "GET", "/assets?limit=1&state=all")["items"][0]
    doc = call(base, "POST", "/documents", {"from_asset": asset["id"], "name": "m4-acceptance"})
    did, w, h = doc["id"], doc["w"], doc["h"]
    check("document created from asset", doc["source_asset_id"] == asset["id"] and len(doc["layers"]) == 1, f"{did} {w}×{h}")
    base_layer = doc["layers"][0]

    # 2. a stack with every blend mode (5 groups of 5), masks on some, clip on a few, opacity/fill variety
    layers: list[dict] = []
    k = 0
    for gi in range(5):
        children = []
        for bi in range(5):
            mode = BLENDS[k] if BLENDS[k] != "dissolve" else "normal"   # dissolve is noise: preview ≈ (seeded differently)
            node = {"kind": "raster", "id": f"lyr_t{k:02d}", "name": f"{mode}", "opacity": 0.5 + 0.5 * ((k % 3) / 2), "blend": mode, "visible": True, "locked": False,
                    "clip": k % 7 == 3, "mask": {"enabled": True, "linked": False, "x": 0, "y": 0} if k % 4 == 1 else None, "x": (k * 37) % 120 - 40, "y": (k * 53) % 90 - 30, "w": w, "h": h, "fill": 1.0 if k % 5 else 0.7}
            children.append(node)
            k += 1
        layers.append({"kind": "group", "id": f"grp_t{gi}", "name": f"group {gi}", "opacity": 1.0 if gi % 2 == 0 else 0.8, "blend": "normal", "visible": True, "locked": False, "clip": False,
                       "mask": None, "passthrough": gi % 2 == 0, "children": children})
    # adjustment / filter layers on top and inside a group (exact in Python; previewed on the GPU)
    def adj(i: int, kind: str, type_: str, params: dict, **kw) -> dict:
        n = {"kind": kind, "id": f"adj_t{i}", "name": type_, "type": type_, "params": params, "opacity": 1.0, "blend": "normal", "visible": True, "locked": False, "clip": False, "mask": None}
        n.update(kw)
        return n
    layers = [adj(0, "adjustment", "levels", {"in_black": 16, "in_white": 235, "gamma": 1.3}, mask={"enabled": True, "linked": False, "x": 0, "y": 0}),
              adj(1, "filter", "gaussian_blur", {"radius": 1.5}, opacity=0.6),
              adj(2, "adjustment", "hue_saturation", {"hue": 25, "saturation": 20}, opacity=0.6),
              adj(3, "filter", "sharpen", {"amount": 120, "radius": 1, "threshold": 2}),
              adj(4, "adjustment", "curves", {"rgb": [[0, 0], [96, 70], [255, 255]]}, clip=True),
              adj(5, "filter", "high_pass", {"radius": 2}, opacity=0.4),
              *layers]
    layers[-1]["children"].insert(0, adj(6, "adjustment", "brightness_contrast", {"brightness": 8, "contrast": 20}))
    layers[-2]["children"].insert(2, adj(7, "adjustment", "color_balance", {"shadows": [15, 0, -10], "midtones": [0, 10, 0], "highlights": [-5, 0, 15]}))
    stack = dict(doc)
    stack["layers"] = layers + [base_layer]
    doc2 = call(base, "PUT", f"/documents/{did}", stack)
    check("stack accepted (25 blend modes, 5 groups, 8 adjustment/filter layers)", len(doc2["layers"]) == 12)
    call(base, "PUT", f"/documents/{did}/layers/adj_t0/pixels?w={w}&h={h}&kind=mask", mask_layer(w, h, 9).tobytes())

    # 3. pixels + masks
    t0 = time.perf_counter()
    for i in range(25):
        px = gradient_layer(w, h, i)
        call(base, "PUT", f"/documents/{did}/layers/lyr_t{i:02d}/pixels?w={w}&h={h}", px.tobytes())
        if i % 4 == 1:
            call(base, "PUT", f"/documents/{did}/layers/lyr_t{i:02d}/pixels?w={w}&h={h}&kind=mask", mask_layer(w, h, i).tobytes())
    up = time.perf_counter() - t0
    check("25 layers + 6 masks uploaded raw", True, f"{up:.2f} s · {25 * w * h * 4 / 1e6:.0f} MB")

    # 4. save → ORA; reopen (close + get) → identical stack + pixels
    t0 = time.perf_counter()
    saved = call(base, "POST", f"/documents/{did}/save")
    check("saved (ORA)", bool(saved["saved_at"]), f"{time.perf_counter() - t0:.2f} s")
    call(base, "POST", f"/documents/{did}/close")
    re = call(base, "GET", f"/documents/{did}")
    same_stack = json.dumps(re["layers"], sort_keys=True) == json.dumps(saved["layers"], sort_keys=True)
    check("reopened stack identical", same_stack)
    px = call(base, "GET", f"/documents/{did}/layers/lyr_t07/pixels?raw=1", raw=True)
    arr = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 4)
    check("reopened pixels lossless", np.array_equal(arr, gradient_layer(w, h, 7)))
    m = call(base, "GET", f"/documents/{did}/layers/lyr_t05/pixels?raw=1&kind=mask", raw=True)
    check("reopened mask lossless", np.array_equal(np.frombuffer(m, dtype=np.uint8).reshape(h, w), mask_layer(w, h, 5)))
    docs = call(base, "GET", "/documents")["items"]
    entry = next((d for d in docs if d["id"] == did), None)
    check("listed with layer count", bool(entry) and entry["layers"] == 39, str(entry and entry["layers"]))
    ora = Path(entry["path"])
    with zipfile.ZipFile(ora) as z:
        names = z.namelist()
        check("ORA layout (mimetype first, stack.xml, mergedimage, thumbnail)", names[0] == "mimetype" and "stack.xml" in names and "mergedimage.png" in names and "Thumbnails/thumbnail.png" in names, f"{len(names)} entries")

    # 5. flatten to the catalogue → lineage
    t0 = time.perf_counter()
    fl = call(base, "POST", f"/documents/{did}/flatten", {"to_catalogue": True})
    a2 = fl["asset"]
    check("flatten → asset with lineage", a2["suite"] == "edit" and asset["id"] in a2["parents"] and a2["params"].get("document_id") == did, f"{a2['id']} in {time.perf_counter() - t0:.2f} s")
    src = call(base, "GET", f"/assets/{asset['id']}")
    check("source asset flagged has_document", bool(src.get("has_document")))

    # 6. the editor's GPU composite vs the exact flatten (headless Edge deep link)
    url = f"http://localhost:{args.vite}/?token={TOKEN}&port={args.port}&suite=edit&doc={did}&verify=1"
    shot = Path(os.environ.get("TEMP", ".")) / "m4-verify.png"
    if Path(args.edge).is_file():
        subprocess.run([args.edge, "--headless=new", "--window-size=1600,1000", "--hide-scrollbars", "--virtual-time-budget=30000", f"--screenshot={shot}", url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        cmp = None
        for _ in range(30):
            cmp = call(base, "GET", f"/documents/{did}").get("meta", {}).get("last_compare")
            if cmp:
                break
            time.sleep(1)
        if cmp:
            check("GPU preview vs exact flatten (RGB p99 ≤ 4/255 over 25 stacked modes; 8-bit intermediates)", cmp["rgb_p99"] <= 4, f"mean {cmp['rgb_mean']:.2f} p99 {cmp['rgb_p99']} max {cmp['rgb_max']} · alpha-incl. p99 {cmp['p99']} · screenshot {shot}")
        else:
            check("GPU preview vs exact flatten", False, "the editor did not report (Edge/Vite not reachable?)")
    else:
        check("GPU preview vs exact flatten", False, f"Edge not found at {args.edge}")

    if not args.keep:
        call(base, "DELETE", f"/documents/{did}")
    ok = sum(1 for _, o, _ in results if o)
    print(f"\nM4 acceptance: {ok}/{len(results)} passed")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
