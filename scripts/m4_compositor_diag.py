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
    if which in ("modes", "all"):
        for m in BLENDS:
            run(f"blend {m}", [node(0, blend=m)], {"lyr_d0": g0})


if __name__ == "__main__":
    main()
