"""E12 angles spike (ArtCraft 08 §7, D74): a new viewpoint of an existing image, locally, on 16 GB.

Moves (5): rotate 45° left, rotate 45° right, top-down, close-up, wide — each over the 10 frozen sources in bench/angles/.
Methods:
  qwen_angles   A · Qwen-Image-Edit 2509 fp8 + the Multiple-angles LoRA (dx8152) + Lightning 4-step · TextEncodeQwenImageEditPlus · the
                LoRA's own Chinese camera instructions
  klein_prompt  C · FLUX.2 Klein 9B · the source as ReferenceLatent + an English camera instruction · 4 steps
  (B · Qwen-Image-Edit 2511 Q4_K_M + fal's Multiple-Angles LoRA and D · DA3 depth → mesh → re-render → fill come after A / C are read)
Pass bars (08 §7): the correct move ≥ 7/10 per move (judged on the sheets); ArcFace identity ≥ 0.5 where the source has a face
(evaluation only); warm ≤ 60 s, cold ≤ 180 s.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e12_angles.py sources         # once: bench/angles/NN.jpg from bench/t2i (Klein 9B)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e12_angles.py run [--methods qwen_angles,klein_prompt] [--moves ...] [--sources 01,...]
  orchestrator/.venv/Scripts/python.exe engine/spikes/e12_angles.py score            # identity + timing summary, contact sheets per move
The engine must be running (scripts/engine-start.ps1, 127.0.0.1:8188).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
from loom2.engine.graphs import _te_loader, flatten_json_prompt  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim, available  # noqa: E402

BENCH_T2I = REPO / "bench" / "t2i"
BENCH = REPO / "bench" / "angles"
OUT = REPO / "engine" / "spikes" / "out" / "e12"
RESULTS = OUT / "results.jsonl"
MODELS_ROOT = Path("F:/loom2-models")
ROSTER = Roster(MODELS_ROOT, [], "full").scan()                           # D80: F:/loom2-models only (D: is a backup drive)


def klein_te(model_id: str = "klein-9b") -> dict:
    """The text-encoder loader loom2's own Klein presets run (D31: the Qwen3-8B Q4_K_M GGUF, resident beside the transformer).
    Resolved through the registry and roster so a spike cannot drift from the app: the first chain hard-coded the 8.7 GB fp8 alternate,
    which does not fit beside a 9B transformer and streamed both from RAM (493 s a scene for Klein base)."""
    spec = registry.SPECS[model_id]
    return _te_loader(ROSTER.require(spec.roles.te.default)[1], None)
SRC_W, SRC_H, SRC_SEED = 1024, 576, 20261011

# move → (the angles LoRA's instruction, an English instruction for prompt-only methods)
MOVES: dict[str, tuple[str, str]] = {
    "left45": ("将镜头向左旋转45度", "Rotate the camera 45 degrees to the left around the subject, showing the scene from that new side angle."),
    "right45": ("将镜头向右旋转45度", "Rotate the camera 45 degrees to the right around the subject, showing the scene from that new side angle."),
    "topdown": ("将镜头转为俯视", "Move the camera high above and look straight down at the scene: a top-down overhead view."),
    "closeup": ("将镜头转为特写镜头", "Move the camera in to a close-up of the main subject's face and shoulders."),
    "wide": ("将镜头转为广角镜头", "Pull the camera back to a wide-angle shot that shows much more of the surroundings."),
}
KEEP = " Keep the same characters, faces, clothing, lighting, colours and setting."
# fal's 2511 LoRA: `<sks> [azimuth] [elevation] [distance]` over 8 azimuths × 4 elevations × 3 distances (its model card); "top-down" is
# its highest elevation (high-angle, 60°)
FAL: dict[str, str] = {
    "left45": "<sks> front-left quarter view eye-level shot medium shot", "right45": "<sks> front-right quarter view eye-level shot medium shot",
    "topdown": "<sks> front view high-angle shot medium shot", "closeup": "<sks> front view eye-level shot close-up",
    "wide": "<sks> front view eye-level shot wide shot",
}
METHODS = ["qwen_angles", "klein_prompt", "qwen2511_angles", "klein_prompt2", "dev_angles"]


class Engine:
    def __init__(self, server: str) -> None:
        self.server = server
        self.http = httpx.Client(base_url=f"http://{server}", timeout=120)
        self.client_id = uuid.uuid4().hex

    def upload(self, path: Path) -> str:
        r = self.http.post("/upload/image", files={"image": (path.name, path.read_bytes(), "image/png")}, data={"overwrite": "true", "type": "input"})
        r.raise_for_status()
        j = r.json()
        return (j.get("subfolder") + "/" if j.get("subfolder") else "") + j["name"]

    def run(self, graph: dict, timeout: float = 1800) -> tuple[dict, float, float]:
        """Queue, wait; (history entry, wall seconds, engine execution seconds from the status messages)."""
        t0 = time.time()
        r = self.http.post("/prompt", json={"prompt": graph, "client_id": self.client_id})
        if r.status_code != 200:
            raise RuntimeError(f"prompt refused: {r.text[:600]}")
        if r.json().get("node_errors"):                                  # the engine still runs the outputs that validated — not a result
            raise RuntimeError(f"prompt partly invalid: {json.dumps(r.json()['node_errors'])[:600]}")
        pid = r.json()["prompt_id"]
        while time.time() - t0 < timeout:
            h = self.http.get(f"/history/{pid}").json().get(pid)
            if h and h.get("status", {}).get("completed") is not None:
                msgs = {m[0]: m[1] for m in h["status"].get("messages", [])}
                start, end = msgs.get("execution_start", {}).get("timestamp"), (msgs.get("execution_success") or msgs.get("execution_error") or {}).get("timestamp")
                return h, time.time() - t0, ((end - start) / 1000 if start and end else time.time() - t0)
            time.sleep(0.5)
        raise TimeoutError(pid)

    def image(self, h: dict, node: str) -> Image.Image:
        o = h["outputs"][node]["images"][0]
        r = self.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        return Image.open(io.BytesIO(r.content)).convert("RGB")


# ---------------------------------------------------------------- graphs
def flux2_loaders(g: dict, unet: str) -> None:
    g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "fp8_e4m3fn"}}
    g["2"] = klein_te()
    g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}


def klein_t2i(prompt: str, seed: int) -> dict:
    g: dict = {}
    flux2_loaders(g, "flux-2-klein-9b.safetensors")
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}}
    g["7"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": SRC_W, "height": SRC_H, "batch_size": 1}}
    g["8"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                   "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "denoise": 1.0}}
    g["9"] = {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}}
    g["10"] = {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "e12/src"}}
    return g


def qwen_angles(image_name: str, move: str, seed: int) -> dict:
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1.0}},
        "41": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["4", 0], "lora_name": "Qwen-Edit-2509-Multiple-angles.safetensors", "strength_model": 1.0}},
        "5": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["41", 0], "shift": 3.0}},
        "6": {"class_type": "CFGNorm", "inputs": {"model": ["5", 0], "strength": 1.0}},
        "100": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "20": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["100", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 8}},
    }
    g["7"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": MOVES[move][0], "vae": ["3", 0], "image1": ["20", 0]}}
    g["8"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": "", "vae": ["3", 0], "image1": ["20", 0]}}
    g["9"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["20", 0], "vae": ["3", 0]}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["6", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["7", 0], "negative": ["8", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"e12/qwen_{move}"}}
    return g


def klein_prompt(image_name: str, move: str, seed: int) -> dict:
    g: dict = {}
    flux2_loaders(g, "flux-2-klein-9b.safetensors")
    g["100"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": MOVES[move][1] + KEEP, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
    g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": SRC_W, "height": SRC_H, "batch_size": 1}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["8", 0], "negative": ["6", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"e12/klein_{move}"}}
    return g


SHEET = ("Using the input image as the strict visual reference, create {view} of the same subject. Preserve the exact identity, proportions, "
         "silhouette, materials, colours, clothing, markings and design language from the input image. Preserve the same expression, pose, "
         "posture, gesture and object positions; the subject stays in the same moment, only viewed from {angle}. Photorealistic, same subject, "
         "same pose, same setting and lighting, only the viewing angle changes.")
VIEWS2: dict[str, tuple[str, str]] = {
    "left45": ("a 45-degree front three-quarter view from the subject's left", "a front three-quarter angle 45 degrees to the left, eye-level"),
    "right45": ("a 45-degree front three-quarter view from the subject's right", "a front three-quarter angle 45 degrees to the right, eye-level"),
    "topdown": ("a high-angle top-down view", "directly above, looking straight down"),
    "closeup": ("a close-up detail view of the main subject's face and shoulders", "close up"),
    "wide": ("a wide shot showing the whole scene around the subject", "far back, a wide angle"),
}


def klein_prompt2(image_name: str, move: str, seed: int) -> dict:
    """C2 · method C with the prompt shape of the Civitai "Flux Klein 4B/9B Multiple Angles" character-sheet workflow (nikhilprasanth, 2026-05;
    native nodes, no LoRA): a strict-reference lead, the view named twice, "only the viewing angle changes" — the author's web-search follow-up."""
    g = klein_prompt(image_name, move, seed)
    g["5"]["inputs"]["text"] = SHEET.format(view=VIEWS2[move][0], angle=VIEWS2[move][1])
    g["12"]["inputs"]["filename_prefix"] = f"e12/klein2_{move}"
    return g


def dev_angles(image_name: str, move: str, seed: int) -> dict:
    """D2 · FLUX.2 dev fp8 + the Turbo LoRA (8 steps, the app's dev preset: euler / simple, guidance 4, CFG 1) + lovis93's fal-trained
    Multi-Angles LoRA v2 (72 positions, the same <sks> vocabulary as fal's 2511 LoRA) at 0.9, the source as ReferenceLatent — the only angles
    LoRA for a FLUX.2 model loom2 already runs (the author's web-search follow-up, 2026-10-12). dev is `full` only (flux-nc)."""
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "Flux2TurboComfyv2.safetensors", "strength_model": 1.0}},
        "41": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["4", 0], "lora_name": "flux-multi-angles-v2-72poses-comfy.safetensors", "strength_model": 0.9}},
        "100": {"class_type": "LoadImage", "inputs": {"image": image_name}},
    }
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": FAL[move], "clip": ["2", 0]}}
    g["7"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["100", 0], "vae": ["3", 0]}}
    g["8"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
    g["6"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["8", 0], "guidance": 4.0}}
    g["60"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}}
    g["9"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": SRC_W, "height": SRC_H, "batch_size": 1}}
    g["10"] = {"class_type": "KSampler", "inputs": {"model": ["41", 0], "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["6", 0], "negative": ["60", 0], "latent_image": ["9", 0], "denoise": 1.0}}
    g["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    g["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"e12/dev_{move}"}}
    return g


def qwen2511_angles(image_name: str, move: str, seed: int) -> dict:
    """B · Qwen-Image-Edit 2511 Q4_K_M (ComfyUI-GGUF) + lightx2v's 4-step LoRA + fal's angles LoRA at 0.9 (its card's starting point)."""
    g = qwen_angles(image_name, move, seed)
    g["1"] = {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "qwen-image-edit-2511-Q4_K_M.gguf"}}
    g["4"]["inputs"]["lora_name"] = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
    g["41"]["inputs"].update(lora_name="qwen-image-edit-2511-multiple-angles-lora.safetensors", strength_model=0.9)
    g["7"]["inputs"]["prompt"] = FAL[move]
    # ComfyUI's own 2511 template: the reference latents go in with `index_timestep_zero` on both conditionings, and shift 3.1 — without
    # them the first smoke image came back nearly unchanged (2026-10-11)
    g["71"] = {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["7", 0], "reference_latents_method": "index_timestep_zero"}}
    g["81"] = {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["8", 0], "reference_latents_method": "index_timestep_zero"}}
    g["10"]["inputs"].update(positive=["71", 0], negative=["81", 0])
    g["5"]["inputs"]["shift"] = 3.1
    g["12"]["inputs"]["filename_prefix"] = f"e12/q2511_{move}"
    return g


BUILD = {"qwen_angles": (qwen_angles, "12"), "klein_prompt": (klein_prompt, "12"), "qwen2511_angles": (qwen2511_angles, "12"),
         "klein_prompt2": (klein_prompt2, "12"), "dev_angles": (dev_angles, "12")}


# ---------------------------------------------------------------- steps
def make_sources(eng: Engine) -> None:
    BENCH.mkdir(parents=True, exist_ok=True)
    meta = []
    for f in sorted(BENCH_T2I.glob("[0-9][0-9]-*.json"))[:10]:
        nid = f.name[:2]
        prose = flatten_json_prompt(json.loads(f.read_text(encoding="utf-8")))
        h, wall, ex = eng.run(klein_t2i(prose, SRC_SEED))
        eng.image(h, "10").save(BENCH / f"{nid}.jpg", quality=92)
        meta.append({"id": nid, "bench": f.name, "model": "flux-2-klein-9b", "seed": SRC_SEED, "size": [SRC_W, SRC_H], "exec_s": round(ex, 1)})
        print(f"source {nid} ({f.name}) {ex:.1f} s")
    (BENCH / "sources.json").write_text(json.dumps({"made_by": "engine/spikes/e12_angles.py sources", "sources": meta}, indent=2) + "\n", encoding="utf-8")


def run(eng: Engine, methods: list[str], moves: list[str], sources: list[str], seed: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    uploaded = {s: eng.upload(BENCH / f"{s}.jpg") for s in sources}
    for m in methods:
        build, out_node = BUILD[m]
        first = True
        for mv in moves:
            for s in sources:
                h, wall, ex = eng.run(build(uploaded[s], mv, seed))
                img = eng.image(h, out_node)
                path = OUT / m / mv / f"{s}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                img.save(path, quality=92)
                row = {"method": m, "move": mv, "source": s, "exec_s": round(ex, 1), "wall_s": round(wall, 1), "cold": first, "size": list(img.size), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
                first = False
                with RESULTS.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"[{m} {mv} {s}] {ex:.1f} s{' (cold)' if row['cold'] else ''}")


def largest_face_embedding(fs: FaceSim, img: Image.Image) -> np.ndarray | None:
    a = np.asarray(img.convert("RGB"))
    faces = fs.detect(a)
    if not faces:
        return None
    f = max(faces, key=lambda x: x.area)
    return fs.embed(a, f.kps)


def score() -> None:
    rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest: dict[tuple, dict] = {}
    for r in rows:
        latest[(r["method"], r["move"], r["source"])] = r
    fs = FaceSim(MODELS_ROOT) if available(MODELS_ROOT) else None
    ref = {s.stem: (largest_face_embedding(fs, Image.open(s)) if fs else None) for s in sorted(BENCH.glob("[0-9][0-9].jpg"))}
    summary: dict = {}
    for (m, mv, s), r in sorted(latest.items()):
        p = OUT / m / mv / f"{s}.jpg"
        ident = None
        if fs and ref.get(s) is not None and p.is_file():
            e = largest_face_embedding(fs, Image.open(p))
            ident = None if e is None else round(FaceSim.similarity(ref[s], e), 3)
        d = summary.setdefault(m, {"warm_s": [], "cold_s": [], "identity": [], "no_face_after": 0, "faces_in_source": 0})
        (d["cold_s"] if r["cold"] else d["warm_s"]).append(r["exec_s"])
        if ref.get(s) is not None:
            d["faces_in_source"] += 1
            if ident is None:
                d["no_face_after"] += 1
            else:
                d["identity"].append(ident)
        r["identity"] = ident
    for m, d in summary.items():
        w, idn = sorted(d["warm_s"]), d["identity"]
        print(f"{m}: warm median {w[len(w) // 2] if w else '-'} s (max {max(w) if w else '-'}), cold {d['cold_s']}; identity median "
              f"{sorted(idn)[len(idn) // 2] if idn else '-'} over {len(idn)} faces (≥ 0.5: {sum(1 for x in idn if x >= 0.5)}), face lost {d['no_face_after']}/{d['faces_in_source']}")
    # sheets: one per move — rows = sources, columns = source + each method
    methods = sorted({m for (m, _, _) in latest})
    for mv in MOVES:
        cells = [(s.stem, [Image.open(s)] + [Image.open(OUT / m / mv / f"{s.stem}.jpg") if (OUT / m / mv / f"{s.stem}.jpg").is_file() else Image.new("RGB", (64, 36), (60, 0, 0)) for m in methods])
                 for s in sorted(BENCH.glob("[0-9][0-9].jpg"))]
        if not any((OUT / m / mv).is_dir() for m in methods):
            continue
        tw, th = 384, 216
        sheet = Image.new("RGB", (40 + (tw + 8) * (1 + len(methods)), 24 + len(cells) * (th + 8)), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for j, head in enumerate(["source"] + methods):
            dr.text((40 + j * (tw + 8), 6), f"{head} · {mv}" if j else head, fill=(230, 230, 230))
        for i, (sid, ims) in enumerate(cells):
            y = 24 + i * (th + 8)
            dr.text((8, y + th // 2), sid, fill=(240, 180, 60))
            for j, im in enumerate(ims):
                im = im.copy(); im.thumbnail((tw, th))
                sheet.paste(im, (40 + j * (tw + 8), y))
        sheet.save(OUT / f"sheet_{mv}.jpg", quality=88)
    (OUT / "scored.json").write_text(json.dumps(list(latest.values()), indent=1), encoding="utf-8")
    print(f"sheets: {OUT}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["sources", "run", "score"])
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--moves", default=",".join(MOVES))
    ap.add_argument("--sources", default="")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    if a.step == "score":
        score(); return 0
    eng = Engine(a.server)
    stats = eng.http.get("/system_stats").json()
    print(f"engine {stats['system'].get('comfyui_version')} · {stats['devices'][0]['name']}")
    if a.step == "sources":
        make_sources(eng); return 0
    srcs = a.sources.split(",") if a.sources else sorted(p.stem for p in BENCH.glob("[0-9][0-9].jpg"))
    run(eng, a.methods.split(","), a.moves.split(","), srcs, a.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
