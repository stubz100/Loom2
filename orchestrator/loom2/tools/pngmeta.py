"""Parse generation metadata from imported images (08 §3a): ComfyUI `prompt`/`workflow` PNG chunks and
A1111-style `parameters` text, plus EXIF ImageDescription when present. Returns what the catalogue stores:
prompt_text, prompt_json, seed, model name and a params dict; anything missing stays None.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

A1111_RE = re.compile(r"^(?P<prompt>.*?)(?:\nNegative prompt: (?P<neg>.*?))?\n(?P<kv>(?:[A-Za-z ]+: [^,\n]+(?:, )?)+)\s*$", re.S)


def _from_comfy(prompt_graph: dict) -> dict[str, Any]:
    texts, seed, model, steps = [], None, None, None
    for node in prompt_graph.values():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        inp = node.get("inputs", {}) or {}
        if cls == "CLIPTextEncode" and isinstance(inp.get("text"), str) and inp["text"].strip():
            texts.append(inp["text"].strip())
        if cls in ("KSampler", "KSamplerAdvanced"):
            seed = inp.get("seed", inp.get("noise_seed", seed))
            steps = inp.get("steps", steps)
        if cls in ("UNETLoader", "UnetLoaderGGUF", "CheckpointLoaderSimple"):
            model = inp.get("unet_name") or inp.get("ckpt_name") or model
    out: dict[str, Any] = {"source": "comfyui", "prompt_text": max(texts, key=len) if texts else None, "seed": seed, "steps": steps, "model": model}
    try:
        if out["prompt_text"] and out["prompt_text"].lstrip().startswith("{"):
            out["prompt_json"] = json.loads(out["prompt_text"])
    except ValueError:
        pass
    return out


def _from_a1111(text: str) -> dict[str, Any]:
    m = A1111_RE.match(text.strip())
    if not m:
        return {"source": "a1111", "prompt_text": text.strip()[:4000]}
    kv = {}
    for part in re.split(r", (?=[A-Za-z ]+: )", m.group("kv") or ""):
        if ": " in part:
            k, v = part.split(": ", 1)
            kv[k.strip().lower()] = v.strip()
    seed = kv.get("seed")
    return {"source": "a1111", "prompt_text": m.group("prompt").strip(), "negative": (m.group("neg") or "").strip() or None,
            "seed": int(seed) if seed and seed.isdigit() else None, "steps": int(kv["steps"]) if kv.get("steps", "").isdigit() else None,
            "model": kv.get("model") or kv.get("model hash"), "sampler": kv.get("sampler"), "cfg": kv.get("cfg scale"), "size": kv.get("size")}


def parse_image_metadata(path: Path) -> dict[str, Any]:
    """Best-effort: returns {} when nothing is recognised; never raises on odd files."""
    try:
        with Image.open(path) as im:
            info = dict(im.info or {})
            w, h = im.size
    except Exception:
        return {}
    out: dict[str, Any] = {"w": w, "h": h}
    if isinstance(info.get("prompt"), str):
        try:
            out.update(_from_comfy(json.loads(info["prompt"])))
            out["comfy_workflow_present"] = isinstance(info.get("workflow"), str)
            return out
        except ValueError:
            pass
    if isinstance(info.get("parameters"), str):
        out.update(_from_a1111(info["parameters"]))
        return out
    desc = info.get("Description") or info.get("ImageDescription")
    if isinstance(desc, str) and desc.strip():
        out.update({"source": "description", "prompt_text": desc.strip()[:4000]})
    return out
