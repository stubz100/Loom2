"""`GET /capabilities` (07 §3d, T8): what the panels may offer — per-model presets, encoder options, video rules, the
engine's live enums, tiers. Built from the presets in `engine/graphs.py` and the roster; P1 (08) replaces the sources with
model specs but keeps this shape.
"""
from __future__ import annotations

from .engine.graphs import I2V_RULES, I2V_WEIGHTS, LTX_STEPS, PRESETS, TE_ALTERNATES, TE_LABELS, VRAM_ESTIMATE_GB, WAN_PRESETS, te_options
from .recipes import FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES
from .roster import ROSTER_BY_ID
from .services import Services
from . import matting, native
from .tools import facesim

RECIPES = ["t2i", "inpaint", "i2i", "upscale", "segment", "i2v"]
I2V_SIZES = {"tiers": {"draft": {"wan22": [832, 480], "ltx23": [1024, 576]}, "hd": {"wan22": [1280, 720], "ltx23": [1280, 704]}},
             "portrait": {"wan22": [480, 832], "ltx23": [576, 1024]}, "square": {"wan22": [640, 640], "ltx23": [640, 640]}}
IMAGE_TIERS = {"thumb": {"flux2": [896, 512], "klein": [896, 512]}, "draft": {"flux2": [960, 544], "klein": [1280, 720]},
               "full": {"flux2": [1920, 1088], "klein": [1920, 1088]}}
ADVANCED = {"model_shift": {"flux2-dev-fp8mixed": 2.02, "klein": 2.02}, "shift_node_defaults": {"base": 0.5, "max": 1.15}, "tile_size_default": 512,
            "flux2_schedule": FLUX2_SCHEDULE}


def capabilities(svc: Services) -> dict:
    variant = svc.app.settings.variant
    live = svc.queue.engine_enum if svc.queue else (lambda cls, key: None)      # the running engine's own enums when it has answered
    return {"recipes": RECIPES, "i2v": {"models": _i2v_models(svc, variant), **I2V_SIZES}, "models": _image_models(svc, variant),
            "facesim": {"available": facesim.available(svc.app.settings.models_root), "dir": str(facesim.weights_dir(svc.app.settings.models_root))},
            "variant": variant, "vram_budget_gb": svc.app.settings.vram_budget_gb,
            "samplers": live("KSampler", "sampler_name") or SAMPLERS, "schedulers": (live("KSampler", "scheduler") or SCHEDULERS) + [FLUX2_SCHEDULE],
            "weight_dtypes": live("UNETLoader", "weight_dtype") or WEIGHT_DTYPES, "te_devices": TE_DEVICES, "te_alternates": TE_ALTERNATES,
            "advanced": ADVANCED, "tiers": IMAGE_TIERS, "refine_edge": matting.capabilities(),
            "content_aware": native.capabilities()}                            # D62: Quick Remove, the Remove pre-fill, Spot Healing


def _image_models(svc: Services, variant: str) -> dict:
    models = {}
    for mid, preset in PRESETS.items():
        e = ROSTER_BY_ID[mid]
        if variant == "open" and "open" not in e.variants:
            continue
        r = svc.roster.resolve(mid)
        models[mid] = {"family": e.family, "label": preset.label, "health": r.health, "steps": preset.steps, "guidance": preset.guidance, "cfg": preset.cfg,
                       "distilled": preset.distilled, "turbo": preset.turbo_lora is not None, "turbo_steps": preset.turbo_steps, "json_prompt": preset.json_prompt,
                       "max_refs": preset.max_refs, "sampler": preset.sampler, "scheduler": preset.scheduler, "vram_gb": VRAM_ESTIMATE_GB.get(mid),
                       "wired": mid == "flux2-dev-fp8mixed" or e.family == "klein", "license": e.license, "variants": e.variants,
                       # D31: the encoder that runs by default and the alternates a recipe may name in `te_id` (the panels' picker)
                       "te_id": preset.te_id,
                       "te_options": [{"id": t, "label": TE_LABELS.get(t, ROSTER_BY_ID[t].name), "name": ROSTER_BY_ID[t].name, "health": svc.roster.resolve(t).health,
                                       "approx_gb": ROSTER_BY_ID[t].approx_gb, "gguf": ROSTER_BY_ID[t].name.lower().endswith(".gguf"), "default": t == preset.te_id}
                                      for t in te_options(preset)]}
    return models


def _i2v_models(svc: Services, variant: str) -> dict:
    out = {}
    for mid, needs in I2V_WEIGHTS.items():
        e = ROSTER_BY_ID[mid]
        if variant == "open" and "open" not in e.variants:        # C3: LTX-2.3 is community-licensed, full only
            continue
        rule = I2V_RULES[e.family]
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        out[mid] = {"family": e.family, "label": rule["label"], "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                    "missing": missing, "fps": rule["fps"], "frames": rule["frames"], "frame_step": rule["frame_step"], "size_mult": rule["size_mult"], "size": list(rule["size"]),
                    "presets": {k: (v.label if e.family == "wan22" else f"{LTX_STEPS[k]} steps") for k, v in WAN_PRESETS.items()}, "beats": e.family == "ltx23", "flf": True,
                    "vram_gb": VRAM_ESTIMATE_GB.get(mid), "license": e.license, "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
    return out
