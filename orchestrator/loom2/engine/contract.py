"""Contract checks between loom2's graph builders and the pinned ComfyUI's `/object_info` (06 §3b, §9).

- `check_graph(object_info, graph)` → list of problems: unknown node class, missing required input, enum value
  not offered, link to a node id that does not exist, link output index out of range.
- `resolve_names(object_info, graph)` → rewrites file-name inputs to the exact enum string the engine lists
  (ComfyUI shows mounted sub-folders with the OS separator, so `t5xxl.safetensors` may be `t5\\t5xxl.safetensors`),
  matching by basename. Returns the substitutions made.

The same functions run offline against the captured fixture (unit tests) and online against the live engine
(rig tests), so a ComfyUI version bump fails in CI, not at the user's first click.
"""
from __future__ import annotations

from pathlib import PurePath
from typing import Any

NAME_INPUTS = {"unet_name", "clip_name", "clip_name1", "clip_name2", "clip_name3", "vae_name", "lora_name", "image",
               "ckpt_name", "control_net_name", "model_name", "upscale_model_name", "style_model_name", "clip_vision_name", "video"}


def _spec_lists(node_info: dict) -> tuple[dict, dict]:
    inp = node_info.get("input", {})
    return inp.get("required", {}) or {}, inp.get("optional", {}) or {}


def _is_link(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def resolve_names(object_info: dict, graph: dict) -> list[str]:
    notes: list[str] = []
    for nid, node in graph.items():
        info = object_info.get(node.get("class_type", ""))
        if not info:
            continue
        req, opt = _spec_lists(info)
        for key, val in list(node.get("inputs", {}).items()):
            if key not in NAME_INPUTS or not isinstance(val, str):
                continue
            spec = req.get(key) or opt.get(key)
            if not spec or not isinstance(spec[0], list):
                continue
            options = spec[0]
            if val in options:
                continue
            base = PurePath(val).name
            matches = [o for o in options if isinstance(o, str) and PurePath(o).name == base]
            if len(matches) == 1:
                node["inputs"][key] = matches[0]
                notes.append(f"{nid}.{key}: {val!r} → {matches[0]!r}")
    return notes


def check_graph(object_info: dict, graph: dict) -> list[str]:
    problems: list[str] = []
    for nid, node in graph.items():
        cls = node.get("class_type")
        info = object_info.get(cls or "")
        if info is None:
            problems.append(f"{nid}: unknown node class {cls!r}")
            continue
        req, opt = _spec_lists(info)
        inputs = node.get("inputs", {})
        for key, spec in req.items():
            if key not in inputs:
                problems.append(f"{nid} ({cls}): required '{key}' missing")
        for key, val in inputs.items():
            spec = req.get(key) or opt.get(key)
            if spec is None:
                if key not in ("hidden",):
                    problems.append(f"{nid} ({cls}): input '{key}' not accepted")
                continue
            if _is_link(val):
                src_id, out_idx = val
                src = graph.get(src_id)
                if src is None:
                    problems.append(f"{nid} ({cls}): '{key}' links to missing node {src_id!r}")
                    continue
                src_info = object_info.get(src.get("class_type", ""))
                outs = (src_info or {}).get("output", [])
                if src_info and out_idx >= len(outs):
                    problems.append(f"{nid} ({cls}): '{key}' links to output {out_idx} of {src['class_type']} which has {len(outs)}")
                continue
            kind = spec[0]
            if isinstance(kind, list):
                if val not in kind:
                    shown = ", ".join(repr(k) for k in kind[:6]) + (" …" if len(kind) > 6 else "")
                    problems.append(f"{nid} ({cls}): '{key}'={val!r} not in enum [{shown}]")
            elif kind == "INT" and not (isinstance(val, int) and not isinstance(val, bool)):
                problems.append(f"{nid} ({cls}): '{key}' expects INT, got {type(val).__name__}")
            elif kind == "FLOAT" and not isinstance(val, (int, float)):
                problems.append(f"{nid} ({cls}): '{key}' expects FLOAT, got {type(val).__name__}")
            elif kind == "STRING" and not isinstance(val, str):
                problems.append(f"{nid} ({cls}): '{key}' expects STRING, got {type(val).__name__}")
            elif kind == "BOOLEAN" and not isinstance(val, bool):
                problems.append(f"{nid} ({cls}): '{key}' expects BOOLEAN, got {type(val).__name__}")
    return problems


def node_signature(object_info: dict, cls: str) -> str:
    info = object_info.get(cls)
    if not info:
        return f"{cls}: <unknown>"
    req, opt = _spec_lists(info)

    def fmt(spec: list) -> str:
        kind = spec[0]
        if isinstance(kind, list):
            return f"enum[{len(kind)}]"
        d = (spec[1] or {}).get("default") if len(spec) > 1 and isinstance(spec[1], dict) else None
        return f"{kind}" + (f"={d!r}" if d is not None else "")

    r = ", ".join(f"{k}:{fmt(v)}" for k, v in req.items())
    o = ", ".join(f"{k}:{fmt(v)}" for k, v in opt.items())
    return f"{cls}  REQ[{r}]  OPT[{o}] -> {info.get('output')}"
