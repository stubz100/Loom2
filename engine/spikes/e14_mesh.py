"""E14 image → mesh spike (ArtCraft 08 §7, D74): props from a cut-out on AMD 16 GB.

The graph is ComfyUI's own template `3d_pixal3d_trellis2_image_to_model.json` (core nodes: MoGe FOV, BiRefNet cut-out, DINOv3
conditioning, TRELLIS.2 structure → shape → upsample → texture, remesh, decimate, unwrap, bake), converted to API format against the
engine's /object_info (engine/spikes/ui_to_api.py), with: our image in, the method switch (TRELLIS.2 or Pixal3D — the template's own
PrimitiveBoolean), the upsample target at 1024 and DecimateMesh at 50 000 faces (08's bar). Hunyuan3D stays excluded (D17).
Inputs: five frozen prop stills in bench/mesh/ (Klein 9B, plain background; `sources`).
Pass bars (08 §7): no OOM at 1024; warm ≤ 120 s, cold ≤ 300 s; ≤ 50k faces after DecimateMesh; silhouette IoU ≥ 0.85; a plausible
back ≥ 3/5 (sheets).
Scoring (`score`): the GLBs are rendered in Edge by frontend/e2e/spikes/e14.run.mjs (spikes.html#e14, Vite dev on 1420) — four lit
turntable views for the sheets, the silhouette at four yaws, the triangle count — and each prop's own BiRefNet cut-out (the template's
node) is the silhouette the best yaw is compared with, after a uniform scale and centre alignment (the shape, not the camera).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e14_mesh.py sources | run [--methods trellis2,pixal3d] [--props 01,...] [--res 1024] | score [--no-render]
(08's "512 then 1024" is not available: engine 0.39's Trellis2UpsampleStage floors target_resolution at 1024 — a lower --res is refused in node_errors.)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine, klein_t2i  # noqa: E402
from ui_to_api import convert  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "engine" / ".venv" / "Lib" / "site-packages" / "comfyui_workflow_templates_json" / "templates" / "3d_pixal3d_trellis2_image_to_model.json"
BENCH = REPO / "bench" / "mesh"
OUT = REPO / "engine" / "spikes" / "out" / "e14"
VIEWS = OUT / "views"
RESULTS = OUT / "results.jsonl"
ENGINE_OUT = REPO / "engine" / "comfyui_out"                                 # scripts/engine-start.ps1 --output-directory
PROPS = {
    "01": "a polished brass ship's compass with a hinged lid, open", "02": "an old iron ship's lantern with a glass chimney and a ring handle",
    "03": "a weathered wooden sea chest with iron bands and a padlock", "04": "a wooden ship's steering wheel with eight spokes and brass hub",
    "05": "a small wooden rowing boat with two oars resting inside",
}
LEAD = "Product photograph of a single object, centred, the whole object in frame, three-quarter view, soft studio light, plain light grey background: "
YAWS = tuple(range(0, 360, 45))                                           # silhouette candidates (the renderer's, frontend/src/spikes/e14Mesh.ts):
PITCHES = (0, 25, 45)                                                     # three-quarter views and elevations — the generator's canonical frame is not known


def graph(image_name: str, method: str, oi: dict, tag: str, res: int = 1024) -> tuple[dict, str]:
    wf = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    g = convert(wf, oi)
    by = {v["class_type"]: k for k, v in g.items()}
    g["122"]["inputs"]["image"] = image_name                               # LoadImage
    g["316"]["inputs"]["value"] = method == "trellis2"                      # the template's switch: True = TRELLIS.2, False = Pixal3D
    for k, v in g.items():
        if v["class_type"] == "Trellis2UpsampleStage":
            v["inputs"]["target_resolution"] = res                          # 08 §7: "512 then 1024"
        if v["class_type"] == "DecimateMesh":
            v["inputs"]["target_face_count"] = 50000
        if v["class_type"] == "LoadBackgroundRemovalModel":
            v["inputs"]["bg_removal_name"] = "BiRefNet-general.safetensors"     # the BiRefNet loom2 already holds (the template names birefnet.safetensors)
        if v["class_type"] == "Save3DAdvanced":
            v["inputs"]["filename_prefix"] = f"e14/{tag}"
    return g, by["Save3DAdvanced"]


def mask_graph(image_name: str) -> dict:
    """The template's own cut-out (BiRefNet) as a mask image — the silhouette a mesh is scored against."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}},
        "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": "e14/mask"}},
    }


def bbox(m: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def iou_aligned(src: np.ndarray, sil: np.ndarray) -> float:
    """IoU of the cut-out and a rendered silhouette after a uniform scale (the mean of the two bounding-box ratios) and centre
    alignment — the object's shape, not the camera the generator assumed. A squashed or stretched mesh still scores low."""
    a, b = bbox(src), bbox(sil)
    if a is None or b is None:
        return 0.0
    s = ((a[2] - a[0]) / (b[2] - b[0]) + (a[3] - a[1]) / (b[3] - b[1])) / 2
    w, h = max(1, round((b[2] - b[0]) * s)), max(1, round((b[3] - b[1]) * s))
    r = np.asarray(Image.fromarray((sil[b[1]:b[3], b[0]:b[2]] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 127
    x0, y0 = round((a[0] + a[2]) / 2 - w / 2), round((a[1] + a[3]) / 2 - h / 2)
    on = np.zeros(src.shape, dtype=bool)
    xs, ys = slice(max(0, x0), min(src.shape[1], x0 + w)), slice(max(0, y0), min(src.shape[0], y0 + h))
    on[ys, xs] = r[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return float((src & on).sum() / max(1, (src | on).sum()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["sources", "run", "score"])
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--methods", default="trellis2,pixal3d")
    ap.add_argument("--props", default=",".join(PROPS))
    ap.add_argument("--res", type=int, default=1024, help="upsample target; a run below 1024 is scored as its own method (<method>_<res>)")
    ap.add_argument("--no-render", action="store_true", help="score from the views already in out/e14/views/")
    a = ap.parse_args()
    eng = Engine(a.server)
    if a.step == "sources":
        BENCH.mkdir(parents=True, exist_ok=True)
        for pid, what in PROPS.items():
            h, _, ex = eng.run(klein_t2i(LEAD + what + ".", 20261014))
            eng.image(h, "10").save(BENCH / f"{pid}.jpg", quality=92)
            print(f"prop {pid} {ex:.1f} s")
        (BENCH / "props.json").write_text(json.dumps({"made_by": "engine/spikes/e14_mesh.py sources", "model": "flux-2-klein-9b", "seed": 20261014,
                                                      "lead": LEAD, "props": PROPS}, indent=1) + "\n", encoding="utf-8")
        return 0
    if a.step == "run":
        oi = eng.http.get("/object_info", timeout=120).json()
        OUT.mkdir(parents=True, exist_ok=True)
        for m in a.methods.split(","):
            mname = m if a.res == 1024 else f"{m}_{a.res}"
            first = True
            for pid in a.props.split(","):
                name = eng.upload(BENCH / f"{pid}.jpg")
                tag = f"{mname}_{pid}"
                try:
                    g, save = graph(name, m, oi, tag, a.res)
                    h, wall, ex = eng.run(g, timeout=3600)
                    status = h.get("status", {})
                    if status.get("status_str") != "success":
                        raise RuntimeError(json.dumps(status.get("messages", [])[-1:])[:600])
                    files = [f for o in h["outputs"].values() for key in ("3d", "result", "meshes", "files") for f in (o.get(key) or []) if isinstance(f, dict)]
                    row = {"method": mname, "prop": pid, "ok": True, "exec_s": round(ex, 1), "wall_s": round(wall, 1), "cold": first, "files": files[:4], "save_node": save}
                except Exception as e:  # noqa: BLE001 — an OOM is a result
                    row = {"method": mname, "prop": pid, "ok": False, "error": str(e)[:600], "cold": first}
                first = False
                row["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with RESULTS.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"[{mname} {pid}] {row.get('exec_s', row.get('error'))}")
        return 0
    # score
    rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {(r["method"], r["prop"]): r for r in rows}
    meshes = [{"tag": f"{m}_{p}", "path": str(ENGINE_OUT / f.get("subfolder", "") / f["filename"])}
              for (m, p), r in sorted(latest.items()) if r.get("ok") for f in r["files"][:1] if f["filename"].endswith(".glb")]
    (OUT / "meshes.json").write_text(json.dumps(meshes, indent=1), encoding="utf-8")
    if not a.no_render:
        subprocess.run(["node", "e2e/spikes/e14.run.mjs"], cwd=REPO / "frontend", check=True, shell=sys.platform == "win32")
    views = json.loads((VIEWS / "views.json").read_text(encoding="utf-8"))
    masks: dict[str, np.ndarray] = {}
    for pid in sorted({p for (_, p) in latest}):
        h, _, _ = eng.run(mask_graph(eng.upload(BENCH / f"{pid}.jpg")))
        masks[pid] = np.asarray(eng.image(h, "5").convert("L")) > 127
    summary: dict = {}
    for (m, pid), r in sorted(latest.items()):
        tag = f"{m}_{pid}"
        d = summary.setdefault(m, {"iou": [], "faces": [], "warm": [], "cold": [], "failed": 0})
        v = views.get(tag)
        if not r.get("ok") or not v or v.get("error"):
            r.update(iou=None, faces=None)
            d["failed"] += 1
            continue
        best = max((iou_aligned(masks[pid], np.asarray(Image.open(VIEWS / f"{tag}_sil_{yaw}_{pitch}.png").convert("L")) > 127), f"{yaw}/{pitch}")
                   for yaw in YAWS for pitch in PITCHES)
        r.update(iou=round(best[0], 3), iou_view=best[1], faces=v["faces"])
        d["iou"].append(r["iou"]); d["faces"].append(v["faces"])
        (d["cold"] if r["cold"] else d["warm"]).append(r["exec_s"])
    for m, d in summary.items():
        w = float(np.median(d["warm"])) if d["warm"] else float("nan")
        print(f"{m}: IoU per prop {d['iou']} (≥ 0.85: {sum(1 for x in d['iou'] if x >= 0.85)}/{len(d['iou'])}) · triangles {d['faces']}"
              f" (≤ 50k: {sum(1 for f in d['faces'] if f <= 50000)}/{len(d['faces'])}) · warm {w:.1f} s · cold {d['cold']} · failed {d['failed']}")
    (OUT / "scored.json").write_text(json.dumps(list(latest.values()), indent=1), encoding="utf-8")
    for m in summary:                                                    # sheet: rows = props; columns = source, front, right, back, left
        pids = sorted(p for (mm, p) in latest if mm == m)
        tw = 256
        sheet = Image.new("RGB", (40 + 5 * (tw + 4), len(pids) * (tw + 4)), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for i, pid in enumerate(pids):
            dr.text((4, i * (tw + 4) + tw // 2), pid, fill=(240, 180, 60))
            cells = [BENCH / f"{pid}.jpg"] + [VIEWS / f"{m}_{pid}_{k}.png" for k in ("front", "right", "back", "left")]
            for j, p in enumerate(cells):
                if p.is_file():
                    im = Image.open(p).convert("RGB"); im.thumbnail((tw, tw)); sheet.paste(im, (40 + j * (tw + 4), i * (tw + 4)))
        sheet.save(OUT / f"sheet_{m}.jpg", quality=84)
    print(f"sheets: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
