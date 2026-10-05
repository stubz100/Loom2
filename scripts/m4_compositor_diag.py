"""Pinpoint GPU-vs-exact compositor differences (10 §14 item 1): one small document per variant, compared through
the editor (headless Edge, deep link &doc=…&verify=1, result read back from doc.meta.last_compare).

    LOOM2_TOKEN=devtoken python scripts/m4_compositor_diag.py [struct|combo|modes|all]   (dev orchestrator 8766 + Vite 1420)

Reference numbers 2026-10-05 (RGB p99 in 1/255): every variant ≤ 1, divide ≤ 4, dissolve is noise by design.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m4_acceptance import BLENDS, TOKEN, call, gradient_layer, mask_layer  # noqa: E402

BASE = f"http://127.0.0.1:{os.environ.get('LOOM2_PORT', '8766')}"
VITE = os.environ.get("LOOM2_VITE", "1420")
EDGE = os.environ.get("LOOM2_EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


def node(i: int, **kw) -> dict:
    n = {"kind": "raster", "id": f"lyr_d{i}", "name": kw.get("name", f"d{i}"), "opacity": 1.0, "blend": "normal", "visible": True, "locked": False, "clip": False, "mask": None,
         "x": 0, "y": 0, "fill": 1.0}
    n.update(kw)
    return n


def group(children: list[dict], **kw) -> dict:
    g = {"kind": "group", "id": "grp_d", "name": "g", "opacity": 1.0, "blend": "normal", "visible": True, "locked": False, "clip": False, "mask": None, "passthrough": True, "children": children}
    g.update(kw)
    return g


def run(name: str, layers: list[dict], pixels: dict[str, np.ndarray], masks: dict[str, np.ndarray] | None = None) -> dict | None:
    asset = call(BASE, "GET", "/assets?limit=1&state=all")["items"][0]
    doc = call(BASE, "POST", "/documents", {"from_asset": asset["id"], "name": f"diag {name}"})
    did, w, h = doc["id"], doc["w"], doc["h"]
    stack = dict(doc)
    stack["layers"] = layers + [doc["layers"][0]]
    for n in layers:
        for c in n.get("children", []) or []:
            c.setdefault("w", w); c.setdefault("h", h)
        if n["kind"] == "raster":
            n.setdefault("w", w); n.setdefault("h", h)
    call(BASE, "PUT", f"/documents/{did}", stack)
    for lid, px in pixels.items():
        call(BASE, "PUT", f"/documents/{did}/layers/{lid}/pixels?w={px.shape[1]}&h={px.shape[0]}", px.tobytes())
    for lid, m in (masks or {}).items():
        call(BASE, "PUT", f"/documents/{did}/layers/{lid}/pixels?w={m.shape[1]}&h={m.shape[0]}&kind=mask", m.tobytes())
    call(BASE, "POST", f"/documents/{did}/save")
    url = f"http://localhost:{VITE}/?token={TOKEN}&port={BASE.rsplit(':', 1)[1]}&suite=edit&doc={did}&verify=1"
    subprocess.run([EDGE, "--headless=new", "--window-size=1400,900", "--virtual-time-budget=30000", f"--screenshot={os.environ.get('TEMP', '.')}/diag-{name}.png", url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    cmp = None
    for _ in range(20):
        cmp = call(BASE, "GET", f"/documents/{did}").get("meta", {}).get("last_compare")
        if cmp:
            break
        time.sleep(1)
    print(f"{name:30s} " + (f"rgb mean {cmp['rgb_mean']:6.2f}  p99 {cmp['rgb_p99']:5.1f}  max {cmp['rgb_max']:5.1f}   alpha-incl p99 {cmp['p99']:5.1f}" if cmp else "no report"))
    call(BASE, "DELETE", f"/documents/{did}")
    return cmp


def main() -> None:
    w, h = 960, 544
    g0, g1, g2 = gradient_layer(w, h, 0), gradient_layer(w, h, 1), gradient_layer(w, h, 2)
    m1 = {"lyr_d0": mask_layer(w, h, 1)}
    which = sys.argv[1] if len(sys.argv) > 1 else "struct"
    if which in ("struct", "all"):
        run("base only", [], {})
        run("normal 100%", [node(0)], {"lyr_d0": g0})
        run("normal 50%", [node(0, opacity=0.5)], {"lyr_d0": g0})
        run("normal fill 70%", [node(0, fill=0.7)], {"lyr_d0": g0})
        run("offset 40,30", [node(0, x=40, y=30)], {"lyr_d0": g0})
        run("mask unlinked", [node(0, mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {"lyr_d0": g0}, m1)
        run("mask + offset", [node(0, x=40, y=30, mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {"lyr_d0": g0}, m1)
        run("two normal", [node(1, opacity=0.6), node(0)], {"lyr_d0": g0, "lyr_d1": g1})
        run("group pass-through", [group([node(1, opacity=0.6), node(0)])], {"lyr_d0": g0, "lyr_d1": g1})
        run("group isolated 80%", [group([node(1, opacity=0.6), node(0)], opacity=0.8, passthrough=False)], {"lyr_d0": g0, "lyr_d1": g1})
        run("group isolated multiply", [group([node(1, opacity=0.6), node(0)], blend="multiply", passthrough=False)], {"lyr_d0": g0, "lyr_d1": g1})
    if which in ("combo", "all"):
        run("mask + multiply", [node(0, blend="multiply", mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {"lyr_d0": g0}, m1)
        run("mask + multiply + offset", [node(0, blend="multiply", x=40, y=30, mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {"lyr_d0": g0}, m1)
        run("mask + hard-light 75%", [node(0, blend="hard-light", opacity=0.75, mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {"lyr_d0": g0}, m1)
        run("two multiply stacked", [node(1, blend="multiply"), node(0, blend="multiply")], {"lyr_d0": g0, "lyr_d1": g1})
        run("three screen stacked", [node(2, blend="screen"), node(1, blend="screen"), node(0, blend="screen")], {"lyr_d0": g0, "lyr_d1": g1, "lyr_d2": g2})
        run("neg offset -40,-30", [node(0, x=-40, y=-30, blend="overlay")], {"lyr_d0": g0})
        run("clip over hole", [node(1, blend="multiply", clip=True), node(0, x=200, y=100)], {"lyr_d0": g0, "lyr_d1": g1})
        run("clip inside pass-through grp", [group([node(1, blend="multiply", clip=True), node(0, x=200, y=100)])], {"lyr_d0": g0, "lyr_d1": g1})
        run("clip inside isolated grp", [group([node(1, blend="multiply", clip=True), node(0, x=200, y=100)], opacity=0.8)], {"lyr_d0": g0, "lyr_d1": g1})
        run("one multiply in isolated grp", [group([node(0, blend="multiply")], opacity=0.8)], {"lyr_d0": g0})
        run("blends inside isolated grp", [group([node(1, blend="screen", opacity=0.75), node(0, blend="multiply")], opacity=0.8)], {"lyr_d0": g0, "lyr_d1": g1})
        run("isolated grp + offsets", [group([node(1, blend="screen", x=-40, y=-30), node(0, blend="multiply", x=37, y=53)], opacity=0.8)], {"lyr_d0": g0, "lyr_d1": g1})
        run("isolated grp blend+mask child", [group([node(1, blend="screen"), node(0, blend="multiply", mask={"enabled": True, "linked": False, "x": 0, "y": 0})], opacity=0.8)], {"lyr_d0": g0, "lyr_d1": g1}, m1)
        run("two isolated grps", [group([node(1, blend="screen")], opacity=0.8), {**group([node(0, blend="multiply")], opacity=0.8), "id": "grp_e"}], {"lyr_d0": g0, "lyr_d1": g1})
    if which in ("adjust", "all"):
        def adj(i: int, kind: str, type_: str, params: dict, **kw) -> dict:
            n = {"kind": kind, "id": f"adj_d{i}", "name": type_, "type": type_, "params": params, "opacity": 1.0, "blend": "normal", "visible": True, "locked": False, "clip": False, "mask": None}
            n.update(kw)
            return n
        run("levels", [adj(0, "adjustment", "levels", {"in_black": 20, "in_white": 230, "gamma": 1.4, "out_black": 10, "out_white": 250})], {})
        run("curves", [adj(0, "adjustment", "curves", {"rgb": [[0, 0], [64, 40], [192, 220], [255, 255]], "r": [[0, 0], [255, 200]]})], {})
        run("hue_saturation", [adj(0, "adjustment", "hue_saturation", {"hue": 40, "saturation": 30, "lightness": -10})], {})
        run("color_balance", [adj(0, "adjustment", "color_balance", {"shadows": [20, -10, 0], "midtones": [0, 15, -20], "highlights": [-10, 0, 25]})], {})
        run("brightness_contrast", [adj(0, "adjustment", "brightness_contrast", {"brightness": 12, "contrast": 25})], {})
        run("exposure", [adj(0, "adjustment", "exposure", {"exposure": 0.7, "offset": -0.05, "gamma": 1.2})], {})
        run("black_white", [adj(0, "adjustment", "black_white", {"r": 30, "g": 50, "b": 20})], {})
        run("invert", [adj(0, "adjustment", "invert", {})], {})
        run("levels 50% masked", [adj(0, "adjustment", "levels", {"gamma": 0.6}, opacity=0.5, mask={"enabled": True, "linked": False, "x": 0, "y": 0})], {}, {"adj_d0": mask_layer(w, h, 3)})
        run("invert clip over hole", [adj(1, "adjustment", "invert", {}, clip=True), node(0, x=200, y=100)], {"lyr_d0": g0})
        run("adjust over layer w/ holes", [adj(1, "adjustment", "invert", {}), node(0, x=200, y=100)], {"lyr_d0": g0})
        run("hue_sat inside isolated grp", [group([adj(1, "adjustment", "hue_saturation", {"hue": 90}), node(0, blend="multiply")], opacity=0.8)], {"lyr_d0": g0})
        run("blur 1.5", [adj(0, "filter", "gaussian_blur", {"radius": 1.5})], {})
        run("blur 3", [adj(0, "filter", "gaussian_blur", {"radius": 3})], {})
        run("blur 8 (strided ≈)", [adj(0, "filter", "gaussian_blur", {"radius": 8})], {})
        run("blur over layer w/ holes", [adj(1, "filter", "gaussian_blur", {"radius": 2}), node(0, x=200, y=100)], {"lyr_d0": g0})
        run("sharpen", [adj(0, "filter", "sharpen", {"amount": 150, "radius": 1, "threshold": 4})], {})
        run("high_pass", [adj(0, "filter", "high_pass", {"radius": 3})], {})
        run("noise (≈)", [adj(0, "filter", "noise", {"amount": 10, "seed": 3})], {})
    if which in ("modes", "all"):
        for m in BLENDS:
            run(f"blend {m}", [node(0, blend=m)], {"lyr_d0": g0})


if __name__ == "__main__":
    main()
