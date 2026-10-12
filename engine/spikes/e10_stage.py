"""E10 Stage → image spike (ArtCraft 08 §7, D74): which conditioning makes a posed 3D blocking come out right on 16 GB?

Inputs: the passes of bench/stage/scenes.json rendered by frontend/e2e/spikes/e10.run.mjs into engine/spikes/out/e10/passes/
(<id>_{clay,depth,normal,pose}.png + keypoints.json, the ground truth).
Methods (each with its plain T2I baseline for the timing bar):
  klein_clay        1 · Klein 9B · the clay render as ReferenceLatent + "keep image 1's camera, framing and poses" · 4 steps   (base: klein_plain)
  base_refcontrol   2 · Klein base 9B + RefControl pose LoRA v2 (0.9) · image 1 = the pose map, image 2 = the heroine reference
                     (bench/angles/07.jpg) · trigger "apply pose from image 1 with reference from image 2" · 30 steps, CFG 4   (base: base_plain)
  zimage_depth      3 · Z-Image Turbo + Fun ControlNet Union 2.1 lite on the depth pass (ModelPatchLoader + ZImageFunControlnet) · 8 steps
  zimage_pose       3 · the same on the pose map
  zimage_depth_kr   3 · zimage_depth, then Klein base 9B I2I at 0.5 (the plan's "then Klein I2I 0.4–0.6")   (base for all three: zimage_plain)
Pass bars (08 §7): pose PCK@0.1 ≥ 0.8 (core SDPoseKeypointExtractor on the result vs the rendered keypoints); depth Spearman ≥ 0.85
(DA3-BASE on the result vs the rendered disparity); warm ≤ 1.5 × the method's plain T2I; no OOM; blind "same blocking" ≥ 8/10 (sheets).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e10_stage.py run [--methods ...] [--scenes 01,...]
  orchestrator/.venv/Scripts/python.exe engine/spikes/e10_stage.py score       # PCK, Spearman, timings, sheets
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine, flux2_loaders, klein_te  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PASSES = REPO / "engine" / "spikes" / "out" / "e10" / "passes"
OUT = REPO / "engine" / "spikes" / "out" / "e10"
RESULTS = OUT / "results.jsonl"
HEROINE = REPO / "bench" / "angles" / "07.jpg"
W, H, SEED = 1024, 576, 20261012
CLAY_LEAD = ("Image 1 is a grey clay blocking of this exact shot. Render it as a finished cinematic still: keep image 1's camera, framing, "
             "composition, and every figure's pose, position and size exactly; replace the clay with the real scene. ")
NEG = "blurry, low quality, deformed, extra limbs, text, watermark"
ZIMAGE_VAE = "flux1\\ae.safetensors"          # the FLUX.1 ae in the mounted D: tree (same sha256 as Z-Image's own)


def save(g: dict, node: str, prefix: str) -> None:
    g["90"] = {"class_type": "SaveImage", "inputs": {"images": [node, 0], "filename_prefix": prefix}}


def klein_plain(prompt: str, seed: int, **_) -> dict:
    g: dict = {}
    flux2_loaders(g, "flux-2-klein-9b.safetensors")
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}}
    g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    save(g, "11", "e10/klein_plain")
    return g


def klein_clay(prompt: str, seed: int, up: dict, **_) -> dict:
    g = klein_plain(CLAY_LEAD + prompt, seed)
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": up["clay"]}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
    g["10"]["inputs"]["positive"] = ["8", 0]
    save(g, "11", "e10/klein_clay")
    return g


def klein_clay_pose(prompt: str, seed: int, up: dict, **_) -> dict:
    """Method 1 with the pose map as a second reference: the clay keeps the blocking, the skeleton is meant to pin the limbs (PCK)."""
    g = klein_clay(prompt, seed, up)
    g["5"]["inputs"]["text"] = CLAY_LEAD + "Image 2 is the OpenPose skeleton of the same figures in the same frame: match every figure's limbs to it. " + prompt
    g["101"] = {"class_type": "LoadImage", "inputs": {"image": up["pose"]}}
    g["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["101", 0], "vae": ["3", 0]}}
    g["13"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["12", 0]}}
    g["10"]["inputs"]["positive"] = ["13", 0]
    save(g, "11", "e10/klein_clay_pose")
    return g


def base_plain(prompt: str, seed: int, steps: int = 30, **_) -> dict:
    g: dict = {}
    flux2_loaders(g, "flux-2-klein-base-9b.safetensors")
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}}
    g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": steps, "cfg": 4.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    save(g, "11", "e10/base_plain")
    return g


def base_refcontrol(prompt: str, seed: int, up: dict, **_) -> dict:
    g = base_plain("apply pose from image 1 with reference from image 2. " + prompt, seed)
    g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "refcontrol_v2_poses.safetensors", "strength_model": 0.9}}
    g["10"]["inputs"]["model"] = ["4", 0]
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": up["pose"]}}
    g["101"] = {"class_type": "LoadImage", "inputs": {"image": up["heroine"]}}
    g["102"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["101", 0], "upscale_method": "lanczos", "megapixels": 0.6, "resolution_steps": 16}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["71"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["102", 0], "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}        # image 1: the pose map
    g["81"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["71", 0]}}      # image 2: the reference
    g["10"]["inputs"]["positive"] = ["81", 0]
    save(g, "11", "e10/base_refcontrol")
    return g


def zimage_plain(prompt: str, seed: int, **_) -> dict:
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": ZIMAGE_VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
        "9": {"class_type": "EmptySD3LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
    }
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "res_multistep", "scheduler": "simple",
                                                    "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    save(g, "11", "e10/zimage_plain")
    return g


def zimage_cn(prompt: str, seed: int, up: dict, control: str = "depth", strength: float = 0.8, **_) -> dict:
    g = zimage_plain(prompt, seed)
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": up[control]}}
    g["20"] = {"class_type": "ModelPatchLoader", "inputs": {"name": "Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors"}}
    g["21"] = {"class_type": "ZImageFunControlnet", "inputs": {"model": ["4", 0], "model_patch": ["20", 0], "vae": ["3", 0], "strength": strength, "image": ["100", 0]}}
    g["10"]["inputs"]["model"] = ["21", 0]
    save(g, "11", f"e10/zimage_{control}")
    return g


def zimage_depth_kr(prompt: str, seed: int, up: dict, **_) -> dict:
    g = zimage_cn(prompt, seed, up, "depth")
    # then Klein base 9B, partial denoise 0.5 over the Z-Image result (distilled Klein cannot partial-denoise, 04 §4)
    g["31"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-base-9b.safetensors", "weight_dtype": "fp8_e4m3fn"}}
    g["32"] = klein_te("klein-base-9b")
    g["33"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}
    g["35"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["32", 0]}}
    g["36"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["32", 0]}}
    g["37"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["33", 0]}}
    g["38"] = {"class_type": "KSampler", "inputs": {"model": ["31", 0], "seed": seed, "steps": 20, "cfg": 4.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["35", 0], "negative": ["36", 0], "latent_image": ["37", 0], "denoise": 0.5}}
    g["39"] = {"class_type": "VAEDecode", "inputs": {"samples": ["38", 0], "vae": ["33", 0]}}
    save(g, "39", "e10/zimage_depth_kr")
    return g


METHODS = {
    "klein_plain": klein_plain, "klein_clay": klein_clay, "klein_clay_pose": klein_clay_pose, "base_plain": base_plain, "base_refcontrol": base_refcontrol,
    "zimage_plain": zimage_plain, "zimage_depth": lambda **k: zimage_cn(control="depth", **k), "zimage_pose": lambda **k: zimage_cn(control="pose", **k),
    "zimage_depth_kr": zimage_depth_kr,
}
BASELINE = {"klein_clay": "klein_plain", "klein_clay_pose": "klein_plain", "base_refcontrol": "base_plain", "zimage_depth": "zimage_plain", "zimage_pose": "zimage_plain", "zimage_depth_kr": "zimage_plain"}


def run(eng: Engine, methods: list[str], scenes: list[str]) -> None:
    gt = json.loads((PASSES / "keypoints.json").read_text(encoding="utf-8"))["scenes"]
    heroine = eng.upload(HEROINE)
    for m in methods:
        first = True
        for sid in scenes:
            up = {k: eng.upload(PASSES / f"{sid}_{k}.png") for k in ("clay", "depth", "pose")}
            up["heroine"] = heroine
            try:
                h, wall, ex = eng.run(METHODS[m](prompt=gt[sid]["prompt"], seed=SEED, up=up))
                img = eng.image(h, "90")
                path = OUT / m / f"{sid}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                img.save(path, quality=92)
                row = {"method": m, "scene": sid, "exec_s": round(ex, 1), "wall_s": round(wall, 1), "cold": first, "ok": True}
            except Exception as e:  # noqa: BLE001 — an OOM or a refused graph is a result too
                row = {"method": m, "scene": sid, "ok": False, "error": str(e)[:400], "cold": first}
            row["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            first = False
            with RESULTS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"[{m} {sid}] {row.get('exec_s', row.get('error'))}{' (cold)' if row['cold'] else ''}")


# ---------------------------------------------------------------- scoring
def sdpose_graph(image_name: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "4": {"class_type": "RTDETR_detect", "inputs": {"model": ["2", 0], "image": ["3", 0], "threshold": 0.4, "class_name": "person", "max_detections": 6}},
        "5": {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["1", 0], "vae": ["1", 2], "image": ["3", 0], "batch_size": 1, "bboxes": ["4", 0]}},
        "6": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}},
    }


def da3_graph(image_name: str) -> dict:
    return {
        "1": {"class_type": "LoadDA3Model", "inputs": {"model_name": "depth_anything_3_base.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "DA3Inference", "inputs": {"da3_model": ["1", 0], "image": ["2", 0], "resolution": 504, "resize_method": "upper_bound_resize", "mode": "mono"}},
        "4": {"class_type": "DA3Render", "inputs": {"da3_geometry": ["3", 0], "output": "depth", "output.normalization": "min_max", "output.apply_sky_clip": False}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": "e10/da3"}},
    }


def pck(gt_figs: list, people: list, alpha: float = 0.1) -> tuple[int, int]:
    """Correct / visible ground-truth keypoints; each figure matched to the detected person closest over their shared points."""
    preds = [np.array(p["pose_keypoints_2d"], dtype=float).reshape(-1, 3) for p in people]
    hit = total = 0
    used: set[int] = set()
    for fig in gt_figs:
        g = np.array(fig, dtype=float)
        vis = g[:, 2] > 0
        if vis.sum() < 2:
            continue
        span = max(np.ptp(g[vis, 0]), np.ptp(g[vis, 1]))
        thr = alpha * span
        best, bi = None, -1
        for k, p in enumerate(preds):
            if k in used:
                continue
            ok = vis & (p[:, 2] >= 0.3)
            if ok.sum() == 0:
                continue
            d = np.linalg.norm(p[ok, :2] - g[ok, :2], axis=1).mean()
            if best is None or d < best:
                best, bi = d, k
        total += int(vis.sum())
        if bi >= 0:
            used.add(bi)
            p = preds[bi]
            ok = vis & (p[:, 2] >= 0.3)
            hit += int((np.linalg.norm(p[ok, :2] - g[ok, :2], axis=1) <= thr).sum())
    return hit, total


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = a.ravel().argsort().argsort().astype(float), b.ravel().argsort().argsort().astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    return float((ra * rb).sum() / np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))


def gray_small(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L").resize((256, 144), Image.BILINEAR), dtype=float)


def score(eng: Engine) -> None:
    gt = json.loads((PASSES / "keypoints.json").read_text(encoding="utf-8"))["scenes"]
    rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {(r["method"], r["scene"]): r for r in rows}
    gtd = {sid: gray_small(Image.open(PASSES / f"{sid}_depth.png")) for sid in gt}
    sanity = []                                                         # DA3 on the clay render itself: the ceiling of the depth metric
    for sid in gt:
        h, _, _ = eng.run(da3_graph(eng.upload(PASSES / f"{sid}_clay.png")))
        sanity.append(spearman(gtd[sid], gray_small(eng.image(h, "5"))))
    sign = 1.0 if np.median(sanity) >= 0 else -1.0                      # DA3's "depth" may run far-bright; our pass is near-bright
    print(f"depth metric ceiling (DA3 on the clay renders): median rho {sign * np.median(sanity):.3f}")
    summary: dict = {}
    for (m, sid), r in sorted(latest.items()):
        if not r.get("ok"):
            continue
        name = eng.upload(OUT / m / f"{sid}.jpg")
        hp, _, _ = eng.run(sdpose_graph(name))
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        hit, tot = pck(gt[sid]["figures"], people)
        hd, _, _ = eng.run(da3_graph(name))
        rho = sign * spearman(gtd[sid], gray_small(eng.image(hd, "5")))
        r.update(pck_hit=hit, pck_total=tot, pck=round(hit / tot, 3) if tot else None, depth_rho=round(rho, 3))
        d = summary.setdefault(m, {"hit": 0, "tot": 0, "rho": [], "warm": [], "cold": [], "fail": 0})
        d["hit"] += hit; d["tot"] += tot; d["rho"].append(rho)
        (d["cold"] if r["cold"] else d["warm"]).append(r["exec_s"])
    fails = {}
    for r in latest.values():
        if not r.get("ok"):
            fails[r["method"]] = fails.get(r["method"], 0) + 1
    base_warm = {m: float(np.median(d["warm"])) for m, d in summary.items() if d["warm"]}
    for m, d in summary.items():
        w = float(np.median(d["warm"])) if d["warm"] else float("nan")
        b = base_warm.get(BASELINE.get(m, ""), float("nan"))
        print(f"{m}: PCK@0.1 {d['hit'] / max(1, d['tot']):.3f} ({d['hit']}/{d['tot']}) · depth rho median {np.median(d['rho']):.3f} · warm {w:.1f} s"
              f"{f' = {w / b:.2f}× its plain T2I' if m in BASELINE and b == b else ''} · cold {d['cold']} · failed {fails.get(m, 0)}")
    (OUT / "scored.json").write_text(json.dumps(list(latest.values()), indent=1), encoding="utf-8")
    # sheet: rows = scenes; columns = clay, pose, then every scored method
    methods = [m for m in METHODS if m in summary and not m.endswith("_plain")]
    tw, th = 320, 180
    sheet = Image.new("RGB", (40 + (tw + 6) * (2 + len(methods)), 22 + len(gt) * (th + 6)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for j, head in enumerate(["clay", "pose"] + methods):
        dr.text((40 + j * (tw + 6), 5), head, fill=(230, 230, 230))
    for i, sid in enumerate(sorted(gt)):
        y = 22 + i * (th + 6)
        dr.text((8, y + th // 2), sid, fill=(240, 180, 60))
        cells = [PASSES / f"{sid}_clay.png", PASSES / f"{sid}_pose.png"] + [OUT / m / f"{sid}.jpg" for m in methods]
        for j, p in enumerate(cells):
            if p.is_file():
                im = Image.open(p).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (40 + j * (tw + 6), y))
    sheet.save(OUT / "sheet.jpg", quality=86)
    print(f"sheet: {OUT / 'sheet.jpg'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["run", "score"])
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--scenes", default="")
    a = ap.parse_args()
    eng = Engine(a.server)
    if a.step == "score":
        score(eng); return 0
    scenes = a.scenes.split(",") if a.scenes else sorted(json.loads((PASSES / "keypoints.json").read_text(encoding="utf-8"))["scenes"])
    run(eng, a.methods.split(","), scenes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
