"""E33 (D128, proto01_animate 31 §1): `open`'s image → 3D — TripoSR (MIT; DINO ViT-B/16, Apache 2.0) on E14's five bench props, scored as
E14 scored Pixal3D and TRELLIS.2 (silhouette IoU against each prop's BiRefNet cut-out at the best of 8 yaws × 3 elevations after a uniform
scale and centre alignment, triangles, seconds, peak VRAM) plus the colour: the median colour of the lit front view against the cut-out's
(ΔE, Lab). TRELLIS (v1) is not run: its sparse convolution, rasterisers and octree renderer are CUDA builds and its ROCm path is MI300
under Linux (setup.sh) — no build for an RX 9070 XT under Windows.

TripoSR runs from its checkout in engine/tools/e33/TripoSR (pinned commit below) in its own venv (engine/tools/e33/.venv: Python 3.11,
the engine's ROCm torch — as voices / lip-sync); torchmcubes (a C++ build) is replaced by PyMCubes behind its name.

    engine/tools/e33/.venv/Scripts/python.exe engine/spikes/e33_mesh.py fetch                # the downloads (TripoSR, DINO, rembg's u2net)
    engine/tools/e33/.venv/Scripts/python.exe engine/spikes/e33_mesh.py run [--res 256]      # the engine stopped (one GPU job at a time, D97)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e33_mesh.py score                     # the engine running (BiRefNet), Vite on 1420
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import types
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
TSR = REPO / "engine" / "tools" / "e33" / "TripoSR"
PIN = "107cefdc244c39106fa830359024f6a2f1c78871"                          # VAST-AI-Research/TripoSR, 2026-06-04
BENCH = REPO / "bench" / "mesh"
OUT = REPO / "engine" / "spikes" / "out" / "e33"
E14 = REPO / "engine" / "spikes" / "out" / "e14"
FACES = 50_000


def _homes() -> None:
    """Every download in one folder that goes with the spike's verdict (house rule 1): the Hugging Face cache (TripoSR, DINO) and rembg's."""
    import os
    os.environ.setdefault("HF_HOME", str(REPO / "engine" / "tools" / "e33" / "hf"))
    os.environ.setdefault("U2NET_HOME", str(REPO / "engine" / "tools" / "e33" / "u2net"))


def _mcubes_as_torchmcubes() -> None:
    """torchmcubes' `marching_cubes(volume, threshold)` from PyMCubes: vertices in the volume's index order reversed (x, y, z = the last
    axis first), as torchmcubes returns them (TripoSR flips them back)."""
    import mcubes
    import torch

    def marching_cubes(vol: "torch.Tensor", thresh: float):
        v, f = mcubes.marching_cubes(vol.detach().cpu().numpy().astype(np.float32), float(thresh))
        return torch.from_numpy(np.ascontiguousarray(v[:, ::-1]).astype(np.float32)), torch.from_numpy(f.astype(np.int64))
    sys.modules["torchmcubes"] = types.SimpleNamespace(marching_cubes=marching_cubes)


def run(res: int) -> None:
    _homes()
    import rembg
    import torch
    import trimesh
    _mcubes_as_torchmcubes()
    sys.path.insert(0, str(TSR))
    from tsr.system import TSR as Model
    from tsr.utils import remove_background, resize_foreground, to_gradio_3d_orientation
    OUT.mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    model = Model.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(8192)
    model.to(dev)
    load_s = time.time() - t0
    session = rembg.new_session()
    rows = []
    for i, src in enumerate(sorted(BENCH.glob("*.jpg"))):
        pid = src.stem
        torch.cuda.reset_peak_memory_stats() if dev == "cuda" else None
        t1 = time.time()
        im = remove_background(Image.open(src), session)
        im = resize_foreground(im, 0.85)
        a = np.asarray(im).astype(np.float32) / 255.0
        a = a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5             # TripoSR's own preprocessing: grey behind the cut-out
        im = Image.fromarray((a * 255.0).astype(np.uint8))
        with torch.no_grad():
            codes = model([im], device=dev)
            mesh = model.extract_mesh(codes, True, resolution=res)[0]
        mesh = trimesh.Trimesh(mesh.vertices, mesh.faces, vertex_colors=mesh.visual.vertex_colors, process=True)
        raw = int(len(mesh.faces))
        if raw > FACES:                                                    # E14's bar: ≤ 50k after decimation (Pixal3D's graph decimates too)
            small = mesh.simplify_quadric_decimation(face_count=FACES)
            _, near = mesh.kdtree.query(small.vertices)                    # the colours carried over by the nearest vertex
            mesh = trimesh.Trimesh(small.vertices, small.faces, vertex_colors=mesh.visual.vertex_colors[near], process=True)
        mesh.fix_normals()
        mesh = to_gradio_3d_orientation(mesh)                              # TripoSR's own viewer turns its z-up mesh y-up (glTF's)
        out = OUT / f"triposr_{pid}.glb"
        mesh.export(out)
        rows.append({"method": "triposr", "prop": pid, "ok": True, "path": str(out), "exec_s": round(time.time() - t1, 2), "cold": i == 0,
                     "load_s": round(load_s, 1) if i == 0 else None, "faces": int(len(mesh.faces)), "raw_faces": raw,
                     "peak_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2) if dev == "cuda" else None, "device": dev, "res": res})
        print(rows[-1], flush=True)
    (OUT / "runs.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def lab_median(rgb: np.ndarray) -> np.ndarray:
    sys.path.insert(0, str(REPO / "orchestrator"))
    from loom2.finals import to_lab
    return np.median(to_lab(rgb.reshape(-1, 1, 3)).reshape(-1, 3), axis=0)


def score() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e12_angles import Engine
    from e14_mesh import PITCHES, YAWS, iou_aligned, mask_graph
    runs = json.loads((OUT / "runs.json").read_text(encoding="utf-8"))
    pix = {m["tag"]: m["path"] for m in json.loads((E14 / "meshes.json").read_text(encoding="utf-8")) if m["tag"].startswith(("pixal3d_", "trellis2_"))}
    meshes = [{"tag": f"triposr_{r['prop']}", "path": r["path"]} for r in runs] + [{"tag": t, "path": p} for t, p in sorted(pix.items()) if Path(p).is_file()]
    (OUT / "meshes.json").write_text(json.dumps(meshes, indent=1), encoding="utf-8")
    import os
    subprocess.run(["node", "e2e/spikes/e14.run.mjs"], cwd=REPO / "frontend", check=True, shell=sys.platform == "win32", env={**os.environ, "E14_OUT": "e33"})
    views = json.loads((OUT / "views" / "views.json").read_text(encoding="utf-8"))
    eng = Engine("127.0.0.1:8188")
    masks, photos = {}, {}
    for r in runs:
        pid = r["prop"]
        h, _, _ = eng.run(mask_graph(eng.upload(BENCH / f"{pid}.jpg")))
        masks[pid] = np.asarray(eng.image(h, "5").convert("L")) > 127
        photos[pid] = np.asarray(Image.open(BENCH / f"{pid}.jpg").convert("RGB").resize(masks[pid].shape[::-1]))
    e14 = {(r["method"], r["prop"]): r for r in json.loads((E14 / "scored.json").read_text(encoding="utf-8"))}
    table = {}
    for m in ("triposr", "pixal3d", "trellis2"):
        d = table.setdefault(m, {"iou": [], "faces": [], "colour_de": [], "warm": [], "cold": [], "peak_gb": []})
        for pid in sorted(masks):
            tag = f"{m}_{pid}"
            v = views.get(tag)
            if not v or v.get("error"):
                continue
            best = max((iou_aligned(masks[pid], np.asarray(Image.open(OUT / "views" / f"{tag}_sil_{y}_{p}.png").convert("L")) > 127), f"{y}/{p}") for y in YAWS for p in PITCHES)
            front = np.asarray(Image.open(OUT / "views" / f"{tag}_front.png").convert("RGBA"))
            on = front[..., 3] > 127 if front[..., 3].min() < 255 else np.abs(front[..., :3].astype(int) - front[0, 0, :3].astype(int)).sum(-1) > 24
            de = float(np.linalg.norm(lab_median(front[..., :3][on]) - lab_median(photos[pid][masks[pid]]))) if on.any() else None
            d["iou"].append(round(best[0], 3)); d["faces"].append(v["faces"]); d["colour_de"].append(round(de, 1) if de is not None else None)
            r = next((x for x in runs if x["prop"] == pid), None) if m == "triposr" else e14.get((m, pid))
            if r:
                (d["cold"] if r.get("cold") else d["warm"]).append(r.get("exec_s"))
                if r.get("peak_gb"):
                    d["peak_gb"].append(r["peak_gb"])
    for m, d in table.items():
        print(f"{m}: IoU {d['iou']} (≥ 0.85: {sum(1 for x in d['iou'] if x >= 0.85)}/{len(d['iou'])}) · triangles {d['faces']} · colour ΔE {d['colour_de']}"
              f" · warm {np.median(d['warm']) if d['warm'] else '-'} s · cold {d['cold']} · peak {max(d['peak_gb']) if d['peak_gb'] else '-'} GB")
    (OUT / "scored.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
    tw = 220                                                             # sheet: rows = props; source, then each method's front / right / back
    sheet = Image.new("RGB", (40 + 10 * (tw + 4), len(masks) * (tw + 4) + 20), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for j, lab in enumerate(["source", "TripoSR front", "right", "back", "Pixal3D front", "right", "back", "TRELLIS.2 front", "right", "back"]):
        dr.text((40 + j * (tw + 4) + 4, 4), lab, fill=(220, 220, 220))
    for i, pid in enumerate(sorted(masks)):
        dr.text((4, 20 + i * (tw + 4) + tw // 2), pid, fill=(240, 180, 60))
        cells = [BENCH / f"{pid}.jpg"] + [OUT / "views" / f"{m}_{pid}_{k}.png" for m in ("triposr", "pixal3d", "trellis2") for k in ("front", "right", "back")]
        for j, p in enumerate(cells):
            if p.is_file():
                im = Image.open(p).convert("RGB"); im.thumbnail((tw, tw)); sheet.paste(im, (40 + j * (tw + 4), 20 + i * (tw + 4)))
    sheet.save(OUT / "sheet.jpg", quality=84)
    print(f"sheet: {OUT / 'sheet.jpg'}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["fetch", "run", "score"])
    ap.add_argument("--res", type=int, default=256)
    a = ap.parse_args()
    if a.what == "fetch":                                                  # the downloads alone (no GPU): the weights and rembg's model
        _homes()
        from huggingface_hub import snapshot_download
        import rembg
        for repo in ("stabilityai/TripoSR", "facebook/dino-vitb16"):
            print(repo, snapshot_download(repo))
        rembg.new_session()
        return 0
    run(a.res) if a.what == "run" else score()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
