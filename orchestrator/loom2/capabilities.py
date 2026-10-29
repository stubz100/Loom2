"""`GET /capabilities` (07 §3d, T8): what the panels may offer — per-model presets, encoder options, video rules, the engine's live
enums, tiers. D65: generated from the model registry (`models/specs/*.toml`) and the roster; the keys of the first release are kept,
and every model gains `recipes` / `inputs` / `geometry` blocks the panels gate their controls on.
"""
from __future__ import annotations

from .engine.graphs import STAGE_HINTS, stage_pass_for, te_alternates, te_label, te_options
from .engine.image_families import family
from .models import registry
from .models.spec import ModelSpec
from .recipes import FLUX2_SCHEDULE, MOVES, SAMPLERS, SCHEDULERS, STAGE_PASSES, TE_DEVICES, WEIGHT_DTYPES, Reangle, reangle_method
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
    """{tier: {family | model_id: [w, h]}} — Generate's Thumb / Draft / Full sizes: per model (V16: `krea2-raw`'s Full is 1344×768, the
    turbo's 1920×1088 — the family's first spec stood for both) and, keyed by the family, its first spec's as before."""
    out: dict[str, dict[str, list[int]]] = {}
    for fam, s in _by_family(registry.image_specs()).items():
        for tier, wh in s.geometry.tiers.items():
            out.setdefault(tier, {})[fam] = list(wh)
    for s in registry.image_specs():
        for tier, wh in s.geometry.tiers.items():
            out.setdefault(tier, {})[s.id] = list(wh)
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
            "defaults": {kind: registry.default_model(kind, variant) for kind in [*RECIPES, "swatch"]},   # D90 (02 §6.3): + the preset swatch pack's t2i model
            "sample_models": _sample_models(svc, variant),                       # D91: Settings › Samples › Sample model
            "facesim": {"available": facesim.available(svc.app.settings.models_root), "dir": str(facesim.weights_dir(svc.app.settings.models_root))},
            "variant": variant, "vram_budget_gb": svc.app.settings.vram_budget_gb,
            "samplers": live("KSampler", "sampler_name") or SAMPLERS, "schedulers": (live("KSampler", "scheduler") or SCHEDULERS) + [FLUX2_SCHEDULE],
            "weight_dtypes": live("UNETLoader", "weight_dtype") or WEIGHT_DTYPES, "te_devices": TE_DEVICES, "te_alternates": te_alternates(),
            "advanced": advanced(), "tiers": image_tiers(), "refine_edge": matting.capabilities(),
            "content_aware": native.capabilities(),                            # D62: Quick Remove, the Remove pre-fill, Spot Healing
            "reangle": _reangle(svc, variant),                                 # P14 (D82): the Angle tab's moves and methods
            "instruct": _instruct(svc, variant),                               # D151: the AI tab's edit by instruction
            "stage": _stage(svc, variant),                                     # P13 ST3 (D78): the Shot tab's methods and passes
            "mesh": _mesh(svc, variant), "story": _story(svc, variant), "train": _train(svc, variant), "voice": _voice(svc, variant), "experimental": _experimental(svc, variant), "cut": _cut(svc)}   # LT2 (D86): the LoRA trainer                                       # P18 (D84): image → mesh props


def _sample_models(svc: Services, variant: str) -> list[dict]:
    """D91: the sample models this build offers — the default swatch model first, then by order — with the health of every weight each
    loads (the picker marks a missing one "not fetched") and the square sizes it renders the style sample and a swatch at."""
    default = registry.default_model("swatch", variant)
    out = []
    for spec in registry.sample_specs(variant):
        healths = {x: svc.roster.resolve(x).health for x in spec.weights()}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        out.append({"id": spec.id, "label": spec.label, "short": spec.short or spec.label, "default": spec.id == default,
                    "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"), "missing": missing,
                    "style_px": spec.geometry.sample_px.style, "swatch_px": spec.geometry.sample_px.swatch, "license": ROSTER_BY_ID[spec.id].license,
                    "seconds": spec.estimates.base_seconds})
    return out


def _reangle(svc: Services, variant: str) -> dict:
    """The angles verb (P14): every move, the methods with the model each runs, its health, measured seconds and the moves it is good for,
    and what `auto` picks per move — the Angle tab shows the method and its time before the job is queued."""
    methods = {}
    for spec in registry.reangle_specs():                             # by order: the first offered spec of a method is the one that runs
        if not spec.recipes.reangle or not _offered(spec, variant) or spec.recipes.reangle in methods:
            continue
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        methods[spec.recipes.reangle] = {"model_id": spec.id, "label": spec.label, "short": spec.short or spec.label, "hint": spec.hint,
                                         "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                                         "missing": missing, "seconds": spec.estimates.base_seconds, "moves": list(spec.recipes.reangle_moves),
                                         "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
    auto = {}
    for move in MOVES:
        try:
            auto[move] = reangle_method(Reangle(asset_id="x", move=move), variant)  # type: ignore[arg-type]
        except ValueError:
            continue
    return {"moves": list(MOVES), "methods": methods, "auto": auto}


def _stage(svc: Services, variant: str) -> dict:
    """Stage → image (P13 ST3): each method with the model it runs in this build, its health, E10's measured seconds (or none), the
    pass it takes as image 1 and how many references follow — the Shot tab shows the method and its time before the job is queued."""
    methods = {}
    for spec in registry.stage_specs():                               # by order: the first offered spec of a method is the one that runs
        m = spec.recipes.stage
        if not m or not _offered(spec, variant) or m in methods:
            continue
        needs = spec.weights() + ([spec.recipes.stage_lora] if spec.recipes.stage_lora else [])
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        methods[m] = {"model_id": spec.id, "label": spec.label, "short": spec.short or spec.label, "hint": STAGE_HINTS.get(m),
                      "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                      "missing": missing, "seconds": spec.recipes.stage_seconds, "measured": spec.recipes.stage_seconds is not None,
                      "image1": stage_pass_for(m), "max_refs": 1 if m == "refcontrol" else max(0, spec.inputs.refs_max - 1),
                      "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
    clip = None
    for spec in registry.video_specs():                               # ST4 (D76): the first offered video model with an IC-LoRA animates the stage
        if not spec.recipes.guide_lora or not _offered(spec, variant):
            continue
        needs = [*spec.weights(), spec.recipes.guide_lora]
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        clip = {"model_id": spec.id, "label": spec.label, "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                "missing": missing, "seconds": spec.recipes.guide_seconds, "kinds": ["depth", "pose"], "fps": spec.geometry.fps, "frame_step": spec.geometry.frame_step,
                "size_mult": spec.recipes.guide_size_mult or spec.geometry.size_mult,
                "size": list(spec.geometry.size or []), "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
        break
    animate = None
    for spec in registry.animate_specs():                             # CN4 (D87, E19): the pose-driven clip method
        if not _offered(spec, variant):
            continue
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        animate = {"model_id": spec.id, "label": spec.label, "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                   "missing": missing, "seconds": spec.recipes.guide_seconds, "kinds": ["pose"], "fps": spec.geometry.fps, "frame_step": spec.geometry.frame_step,
                   "size": list(spec.geometry.size or []), "frames_max": spec.geometry.frames, "figures_max": spec.recipes.guide_figures,
                   "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
        break
    return {"methods": methods, "passes": list(STAGE_PASSES), "default": "clay" if "clay" in methods else (next(iter(methods)) if methods else None), "clip": clip,
            "animate": animate}


def _story(svc: Services, variant: str) -> dict:
    """Story (17 §3b, D85): the model Expand runs on in this build (D78's clay model: it takes the hero as a reference), its health and warm
    seconds — the Cast tab says the cost before the jobs are queued — the presets with their cell counts and the coverage vocabulary."""
    from .story import ANGLES, EXPRESSIONS, PRESETS, SHOTS, expand_spec, preset_cells
    presets = {k: {"label": v["label"], "hint": v["hint"], "cells": len(preset_cells(k)),
                   "plan": [{"shot": c["shot"], "angle": c["angle"], "expression": c["expression"]} for c in preset_cells(k) if c["take"] == 1]}   # D115: the cells, once each
               for k, v in PRESETS.items()}
    coverage = {"shots": [s for s, _ in SHOTS], "angles": [a for a, _ in ANGLES], "expressions": EXPRESSIONS,
                "phrases": {"shots": dict(SHOTS), "angles": dict(ANGLES)}}                                              # D115: the words a cell puts in the prompt
    spec = expand_spec(variant)
    if spec is None:
        return {"model_id": None, "label": None, "short": None, "health": "unavailable", "missing": [], "seconds": None, "presets": presets, "coverage": coverage}
    needs = spec.weights()
    healths = {x: svc.roster.resolve(x).health for x in needs}
    missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
    return {"model_id": spec.id, "label": spec.label, "short": spec.short or spec.label,
            "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"), "missing": missing,
            "seconds": spec.recipes.stage_seconds if spec.recipes.stage_seconds is not None else spec.estimates.base_seconds,
            "presets": presets, "coverage": coverage}


def _train(svc: Services, variant: str) -> dict:
    """LT2 (18 §4): the trainer's bases (specs with `recipes.train`, offered under the variant) with E16's figures and health, whether the
    venv is there, and the ranges the Cast dialog offers — T8: the dialog shows exactly what the job will run."""
    from .trainer import MIN_REFS, trainer_available
    bases = []
    for spec in registry.image_specs():
        tr = spec.recipes.train
        if tr is None or not _offered(spec, variant):
            continue
        bases.append({"model_id": spec.id, "label": spec.label, "offload": tr.offload, "vram_gb": tr.vram_gb, "s_per_it": tr.s_per_it,
                      "health": svc.roster.resolve(spec.id).health})
    why = trainer_available(svc.app.settings)
    return {"available": why is None and any(b["health"] in ("present", "verified") for b in bases), "why": why, "bases": bases,
            "steps": {"min": 100, "max": 5000, "default": 1000}, "ranks": [8, 16, 32], "resolutions": [512, 768], "lr": 1e-4, "min_refs": MIN_REFS}


def _voice(svc: Services, variant: str) -> dict:
    """CN2 (19 §3b): whether the TTS runner can run, the tiers with E20's figures and whether their models are cached (a first run fetches
    them), the draft tier's voices, the languages, the pace range — T8: the Inspector offers exactly what the job runs."""
    from .voices import CLONING_LANGUAGES, DRAFT_LANGUAGES, DRAFT_VOICES, RATES, REFERENCE_S, model_cached, voices_available
    s = svc.app.settings
    why = voices_available(s)
    return {"available": why is None, "why": why,
            "draft": {"model": s.voices.draft_model, "cached": model_cached(s, s.voices.draft_model), "languages": DRAFT_LANGUAGES, "voices": DRAFT_VOICES, **RATES["draft"]},
            "cloning": {"model": s.voices.cloning_model, "cached": model_cached(s, s.voices.cloning_model), "languages": CLONING_LANGUAGES,
                        "reference_s": list(REFERENCE_S), **RATES["cloning"]},
            "speed": {"min": 0.5, "max": 2.0, "default": 1.0}}


EXTEND_CAVEAT = ("experimental (E17): the join is seamless on LTX, but the character's face is not kept across it when they leave the middle "
                 "of the frame; Wan continues from the last frame (a visible seam is possible)")
LIPSYNC_CAVEAT = ("experimental (E18): English lines only, up to 4.8 s; the lips follow most English lines (sync 0.5–0.7) but not every one; "
                  "≈ 16 min a line at Draft, ≈ 9 min at Fast — staged by default")


def _cut(svc: Services) -> dict:
    """U7c (06 §3, rule 5): the cut editor's facts and ranges — the editor kept its own copies of the strip's and the grade's."""
    from .config import STRIP_GAIN_DB, STRIP_PAN, STRIP_VOLUME_DB, STRIP_WIDTH
    from .cuts import GRADE_PARAMS
    from .final_assembly import rife_binary
    fc, host = getattr(svc, "filmcraft", None), getattr(svc, "vsthost", None)
    return {"available": bool(fc is not None and fc.available()), "vst": bool(host is not None and host.available()), "conform": rife_binary() is not None,
            "strip": {"gain_db": STRIP_GAIN_DB, "volume_db": STRIP_VOLUME_DB, "pan": STRIP_PAN, "width": STRIP_WIDTH}, "grade": dict(GRADE_PARAMS)}


def _experimental(svc: Services, variant: str) -> dict:
    """D88: extend and lip-sync, shipped as experimental with E17 / E18's measured caveats (T8: the UI shows what was measured)."""
    models = {s.id: int(s.recipes.extend_lead) for s in registry.video_specs() if s.recipes.extend_lead and _offered(s, variant)}
    lip: dict = {"available": False, "why": "no lip-sync model in this build", "caveat": LIPSYNC_CAVEAT}
    for spec in registry.lipsync_specs():
        if not _offered(spec, variant):
            continue
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        presets = {k: {"label": p.label, "steps": p.steps, "seconds": p.seconds} for k, p in (spec.video.presets.items() if spec.video else [])}
        fps, frames = spec.geometry.fps or 16, spec.geometry.frames or 77
        lip = {"available": not missing, "why": f"weights missing: {', '.join(missing)} — Models › Fetch" if missing else None, "model_id": spec.id,
               "label": spec.label, "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
               "missing": missing, "presets": presets, "frames_max": frames, "fps": fps, "seconds_max": round(frames / fps, 2),
               "languages": spec.recipes.lipsync_languages, "caveat": LIPSYNC_CAVEAT}
        break
    return {"extend": {"models": models, "caveat": EXTEND_CAVEAT}, "lipsync": lip, "mouth_model": _mouth_model(svc)}


def _mouth_model(svc: Services) -> dict:
    """D118 (AE4d): whether the lip-sync model (LatentSync 1.5 in its own venv, tools/lipsync) can redraw a face pass's mouth — `full` only
    (the weights are OpenRAIL++), E29b's measured pace."""
    from .lipsync import SECONDS_PER_77, lipsync_available
    s = svc.app.settings
    why = lipsync_available(s)
    return {"available": why is None, "why": why, "steps": s.lipsync.steps, "guidance": s.lipsync.guidance, "seconds_per_77": SECONDS_PER_77,
            "licence": "LatentSync 1.5 — the code Apache-2.0, the weights OpenRAIL++ (the full variant only)"}


def _mesh(svc: Services, variant: str) -> dict:
    """Image → mesh (P18): the model that makes props in this build (none under `open` while DINOv3 keeps it full-only), its health, E14's warm
    and cold seconds — shown before the job is queued — the resolutions and the face count."""
    for spec in registry.mesh_specs():
        if not _offered(spec, variant):
            continue
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        return {"model_id": spec.id, "label": spec.label, "short": spec.short or spec.label, "hint": spec.hint,
                "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"), "missing": missing,
                "seconds": spec.estimates.base_seconds, "cold_seconds": spec.estimates.cold_seconds, "resolutions": [1024, 1536], "faces": 50000,
                "licences": {x: ROSTER_BY_ID[x].license for x in needs}, "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
    return {"model_id": None, "label": None, "short": None, "hint": None, "health": "unavailable", "missing": [], "seconds": None, "cold_seconds": None,
            "resolutions": [], "faces": 50000, "licences": {}, "approx_gb": 0.0,
            "why": "no image → mesh model is offered in this build (DINOv3's licence keeps Pixal3D full-only, D17 / D26)" if variant == "open" else "no image → mesh spec"}


def _offered(spec: ModelSpec, variant: str) -> bool:
    return registry.offered(spec, variant)


def _blocks(spec: ModelSpec) -> dict:
    return {"recipes": spec.recipes.model_dump(), "inputs": spec.inputs.model_dump(), "geometry": spec.geometry.model_dump(),
            "short": spec.short or spec.label.split(" · ")[0], "hint": spec.hint, "order": spec.order}


def _instruct(svc: Services, variant: str) -> dict:
    """D151: the edit-by-instruction models this build offers — the default first — with the health of every weight each loads, E12's
    measured seconds and the size; the AI tab's Instruct operation picks from them."""
    models = {}
    for spec in registry.instruct_specs():
        if not _offered(spec, variant):
            continue
        needs = spec.weights()
        healths = {x: svc.roster.resolve(x).health for x in needs}
        missing = [ROSTER_BY_ID[x].name for x, hh in healths.items() if hh in ("missing", "retired")]
        models[spec.id] = {"label": spec.label, "short": spec.short or spec.label, "hint": spec.hint, "license": ROSTER_BY_ID[spec.id].license,
                           "health": "missing" if missing else ("verified" if all(h == "verified" for h in healths.values()) else "present"),
                           "missing": missing, "seconds": spec.estimates.base_seconds, "vram_gb": spec.estimates.vram_gb,
                           "approx_gb": round(sum((ROSTER_BY_ID[x].approx_gb or 0) for x in needs), 1)}
    default = next((i for i in models), None)
    try:
        default = registry.default_model("instruct", variant)
    except Exception:  # noqa: BLE001  (no spec offered under this variant)
        pass
    return {"models": models, "default": default if default in models else next(iter(models), None)}


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
                           "wired": spec.wired, "license": e.license, "variants": e.variants, "base": spec.base or spec.family,   # LT2: the adapter base it takes LoRAs for
                           "cfg_fixed": sm.cfg_fixed, "cfg_note": sm.cfg_note, "model_shift": sm.model_shift,
                           # D89: guidance is a control only where the graph has FluxGuidance; tiled refine and the Edit graphs stay on the FLUX.2 family
                           "guidance_node": family(spec).flux_guidance, "tiled_refine": spec.recipes.i2i and spec.graph in registry.FLUX_GRAPHS,
                           "flux_shift": family(spec).flux_shift,                    # D90 (B12): ModelSamplingFlux in the graph — Advanced shows base / max shift only then
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
