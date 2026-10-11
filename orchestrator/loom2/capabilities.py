"""`GET /capabilities` (07 §3d, T8): what the panels may offer — per-model presets, encoder options, video rules, the engine's live
enums, tiers. D65: generated from the model registry (`models/specs/*.toml`) and the roster; the keys of the first release are kept,
and every model gains `recipes` / `inputs` / `geometry` blocks the panels gate their controls on.
"""
from __future__ import annotations

from .engine.graphs import te_alternates, te_label, te_options
from .models import registry
from .models.spec import ModelSpec
from .recipes import FLUX2_SCHEDULE, SAMPLERS, SCHEDULERS, TE_DEVICES, WEIGHT_DTYPES
from .roster import ROSTER_BY_ID
from .services import Services
from . import matting, native
from .tools import facesim

RECIPES = ["t2i", "inpaint", "i2i", "upscale", "segment", "i2v"]
SHIFT_NODE_DEFAULTS = {"base": 0.5, "max": 1.15}                 # ModelSamplingFlux's own defaults
TILE_SIZE_DEFAULT = 512


def _by_family(specs: list[ModelSpec]) -> dict[str, ModelSpec]:
    """The first spec of each family (its geometry stands for the family's tiers)."""
    out: dict[str, ModelSpec] = {}
    for s in specs:
        out.setdefault(s.family, s)
    return out


def image_tiers() -> dict[str, dict[str, list[int]]]:
    """{tier: {family: [w, h]}} — Generate's Thumb / Draft / Full sizes per family."""
    out: dict[str, dict[str, list[int]]] = {}
    for fam, s in _by_family(registry.image_specs()).items():
        for tier, wh in s.geometry.tiers.items():
            out.setdefault(tier, {})[fam] = list(wh)
    return out


def i2v_sizes() -> dict:
    """{"tiers": {draft: {family: [w, h]}, hd: …}, "portrait": {family: …}, "square": {family: …}} — Animate's size presets."""
    out: dict = {"tiers": {}}
    for fam, s in _by_family(registry.video_specs()).items():
        for tier, wh in s.geometry.tiers.items():
            (out["tiers"].setdefault(tier, {}) if tier in ("draft", "hd") else out.setdefault(tier, {}))[fam] = list(wh)
    return out


def advanced() -> dict:
    """Generate · Advanced: the model shift per family (or per id for a single-model family, the first release's keys)."""
    fams: dict[str, list[ModelSpec]] = {}
    for s in registry.image_specs():
        fams.setdefault(s.family, []).append(s)
    shift = {(group[0].id if len(group) == 1 else fam): group[0].sampling.model_shift for fam, group in fams.items() if group[0].sampling.model_shift is not None}
    return {"model_shift": shift, "shift_node_defaults": SHIFT_NODE_DEFAULTS, "tile_size_default": TILE_SIZE_DEFAULT, "flux2_schedule": FLUX2_SCHEDULE}


def capabilities(svc: Services) -> dict:
    variant = svc.app.settings.variant
    live = svc.queue.engine_enum if svc.queue else (lambda cls, key: None)      # the running engine's own enums when it has answered
    return {"recipes": RECIPES, "i2v": {"models": _i2v_models(svc, variant), **i2v_sizes()}, "models": _image_models(svc, variant),
            "tools": _tools(svc, variant),
            "defaults": {kind: registry.default_model(kind, variant) for kind in RECIPES},
            "facesim": {"available": facesim.available(svc.app.settings.models_root), "dir": str(facesim.weights_dir(svc.app.settings.models_root))},
            "variant": variant, "vram_budget_gb": svc.app.settings.vram_budget_gb,
            "samplers": live("KSampler", "sampler_name") or SAMPLERS, "schedulers": (live("KSampler", "scheduler") or SCHEDULERS) + [FLUX2_SCHEDULE],
            "weight_dtypes": live("UNETLoader", "weight_dtype") or WEIGHT_DTYPES, "te_devices": TE_DEVICES, "te_alternates": te_alternates(),
            "advanced": advanced(), "tiers": image_tiers(), "refine_edge": matting.capabilities(),
            "content_aware": native.capabilities()}                            # D62: Quick Remove, the Remove pre-fill, Spot Healing


def _offered(spec: ModelSpec, variant: str) -> bool:
    return registry.offered(spec, variant)


def _blocks(spec: ModelSpec) -> dict:
    return {"recipes": spec.recipes.model_dump(), "inputs": spec.inputs.model_dump(), "geometry": spec.geometry.model_dump(),
            "short": spec.short or spec.label.split(" · ")[0], "hint": spec.hint, "order": spec.order}


def _image_models(svc: Services, variant: str) -> dict:
    models = {}
    for spec in registry.image_specs():
        if not _offered(spec, variant):
            continue
        e, sm = ROSTER_BY_ID[spec.id], spec.sampling
        r = svc.roster.resolve(spec.id)
        te_default = spec.roles.te.default if spec.roles.te else None
        models[spec.id] = {"family": spec.family, "label": spec.label, "health": r.health, "steps": sm.steps, "guidance": sm.guidance, "cfg": sm.cfg,
                           "distilled": sm.distilled, "turbo": sm.turbo is not None, "turbo_steps": sm.turbo.steps if sm.turbo else 8, "json_prompt": sm.json_prompt,
                           "max_refs": spec.inputs.refs_max, "sampler": sm.sampler, "scheduler": sm.scheduler, "vram_gb": spec.estimates.vram_gb,
                           "wired": spec.wired, "license": e.license, "variants": e.variants,
                           "cfg_fixed": sm.cfg_fixed, "cfg_note": sm.cfg_note, "model_shift": sm.model_shift,
                           # D31: the encoder that runs by default and the alternates a recipe may name in `te_id` (the panels' picker)
                           "te_id": te_default,
                           "te_options": [{"id": t, "label": te_label(t) or ROSTER_BY_ID[t].name, "name": ROSTER_BY_ID[t].name, "health": svc.roster.resolve(t).health,
                                           "approx_gb": ROSTER_BY_ID[t].approx_gb, "gguf": ROSTER_BY_ID[t].name.lower().endswith(".gguf"), "default": t == te_default}
                                          for t in te_options(spec)],
                           **_blocks(spec)}
    return models


def _i2v_models(svc: Services, variant: str) -> dict:
    out = {}
    for spec in registry.video_specs():
        if not _offered(spec, variant):                          # C3: LTX-2.3 is community-licensed, full only
            continue
        e, geo, video = ROSTER_BY_ID[spec.id], spec.geometry, spec.video
        assert video is not None
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        out[spec.id] = {"family": spec.family, "label": spec.label, "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                        "missing": missing, "fps": geo.fps, "frames": geo.frames, "frame_step": geo.frame_step, "size_mult": geo.size_mult, "size": list(geo.size or []),
                        "presets": {k: p.label for k, p in video.presets.items()}, "beats": spec.recipes.beats, "flf": spec.recipes.flf,
                        "preset_params": {k: p.model_dump() for k, p in video.presets.items()},
                        "vram_gb": spec.estimates.vram_gb, "license": e.license, "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1),
                        **_blocks(spec)}
    return out


def _tools(svc: Services, variant: str) -> dict:
    """D65: the Edit tools (upscalers, AI Select) with their health — the panels list these instead of naming ids."""
    out = {}
    for spec in registry.SPECS.values():
        if not (spec.recipes.upscale_factor or spec.recipes.segment) or not _offered(spec, variant):
            continue
        out[spec.id] = {"family": spec.family, "label": spec.label, "graph": spec.graph, "health": svc.roster.resolve(spec.id).health,
                        "vram_gb": spec.estimates.vram_gb, "license": ROSTER_BY_ID[spec.id].license, **_blocks(spec)}
    return out
