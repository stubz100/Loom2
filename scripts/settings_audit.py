"""D60 (PC25, T8 "display == reality"): every Settings field, recipe field and /capabilities parameter must reach the code that runs.

A static scan (no engine, no network): a recipe field counts as read when the job code — the queue, the engine's graph builders, the
AI edit helpers and the CPU kernels they call — reads it from an object of that model: an attribute on a name the job code binds the
model to (`recipe.steps`, `l.model_id` for a LoRA, `b.frame` for a beat — RECEIVERS) or `getattr(recipe, "steps"`. A bare name (a
function parameter `steps=`, a dict key `"steps"`) does not count (R7). Fields several recipes share by name (`te_id`) are told apart
only by their receiver, not by type — a static scan cannot follow isinstance branches. A Settings field when any orchestrator module but config.py names it as an attribute; a /capabilities key when it is
mapped below to the recipe fields or settings it feeds (then those must be read) or listed as informational. Fields the UI owns, or
that exist for compatibility, go in ALLOW with the reason. Exit 1 on anything unread and unexplained.

    orchestrator/.venv/Scripts/python.exe scripts/settings_audit.py [-v]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "orchestrator" / "loom2"
sys.path.insert(0, str(ROOT / "orchestrator"))

from pydantic import BaseModel  # noqa: E402

from loom2 import config, recipes  # noqa: E402

# the code path that runs jobs (recipe fields must be read here)
JOB_CODE = ["queue.py", "engine/graphs.py", "engine/client.py", "engine/supervisor.py", "edit_ai.py", "matting.py", "poisson.py", "tone.py", "maskops.py", "clips.py"]

# /capabilities keys → what they parameterise ("recipe:Model.field", "settings:field") or None for informational keys
CAPABILITIES: dict[str, list[str] | None] = {
    "recipes": None,                                   # which recipe kinds exist (the union in recipes.py)
    "i2v": ["recipe:I2V.model_id", "recipe:I2V.width", "recipe:I2V.height", "recipe:I2V.frames", "recipe:I2V.fps"],
    "models": ["recipe:T2I.model_id", "recipe:T2I.steps", "recipe:T2I.guidance", "recipe:T2I.cfg", "recipe:T2I.turbo", "recipe:T2I.sampler", "recipe:T2I.scheduler", "recipe:T2I.te_id"],
    "facesim": None,                                   # whether the face-similarity weights are installed (a panel badge)
    "variant": ["settings:variant"],
    "vram_budget_gb": ["settings:vram_budget_gb"],
    "samplers": ["recipe:T2I.sampler"],
    "schedulers": ["recipe:T2I.scheduler"],
    "weight_dtypes": ["recipe:T2I.weight_dtype"],
    "te_devices": ["recipe:T2I.te_device", "recipe:I2I.te_device", "recipe:Inpaint.te_device", "recipe:Upscale.te_device"],
    "te_alternates": ["recipe:T2I.te_id", "recipe:I2I.te_id", "recipe:Inpaint.te_id", "recipe:Upscale.te_id"],
    "advanced": ["recipe:T2I.base_shift", "recipe:T2I.max_shift", "recipe:T2I.tile_size"],
    "tiers": ["recipe:T2I.tier"],
    "refine_edge": ["recipe:RefineEdge.radius"],
    "content_aware": ["recipe:Inpaint.mode", "recipe:Inpaint.prefill"],     # D62: Quick Remove, the Remove pre-fill
}

# fields that are not read by the job code on purpose — each with its reason
ALLOW: dict[str, str] = {
    "*.kind": "the recipe union's discriminator (pydantic picks the model with it)",
    "RefImage.note": "a user note shown in the panel; never sent to the engine",
    "Inpaint.image_blob": "10 §13 blob-fed request shape kept for compatibility; unused when document_id is given",
    "Inpaint.mask_blob": "10 §13 blob-fed request shape kept for compatibility; unused when document_id is given",
    "Settings.schema_version": "the record's own version (fsio)",
    "Settings.mounted_model_trees": "read by the roster when it resolves weights",
    "T2I.tier": "the panel's tier label (recorded with the recipe); width / height carry the size the engine runs",
    "RecipeEnvelope.recipe": "the union's wrapper: recipes.parse_recipe unwraps it before any job code sees the recipe",
    "Settings.h3_licence_confirmed": "a UI gate (D17): Animate offers MiniMax H3 only once the author confirms the licence application",
}


def _sources(files: list[str]) -> str:
    out = []
    for f in files:
        p = PKG / f
        if p.is_file():
            out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)


def _models() -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for name in dir(recipes):
        obj = getattr(recipes, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == recipes.__name__:
            found[name] = obj
    return found


# R7: the names the job code binds each recipe model to (a field read is an attribute on one of them), and the files it is read in
RECIPE_VARS = ("recipe", "early")                                   # the top-level recipes (queue._run_one, the graph builders)
RECEIVERS: dict[str, tuple[tuple[str, ...], list[str] | None]] = {
    "LoraRef": (("l", "ref"), None),                                # `for l in recipe.loras`, graphs._lora_chain `for ref in loras`
    "RefImage": (("ref", "r"), None),                               # queue: `for ref in recipe.refs`, the parents list `r.asset_id`
    "Beat": (("b",), None),                                         # `for b in recipe.beats`
    # D45: matting.params_from copies the fields by name (getattr) into matting.RefineParams; the kernels read them there
    "RefineEdge": (("params", "self"), ["matting.py"]),
}


def read_in(text: str, field: str, receivers: tuple[str, ...] = RECIPE_VARS) -> bool:
    """True when `text` reads `field` from one of `receivers`: `recipe.field` or `getattr(recipe, "field"`. A bare name — a function
    parameter `field=`, a dict key `"field"` — does not count (R7)."""
    names = "|".join(re.escape(r) for r in receivers)
    return bool(re.search(rf"(?<![\w.])(?:{names})\.{field}\b|\bgetattr\(\s*(?:{names})\s*,\s*[\"']{field}[\"']", text))


def main() -> int:
    verbose = "-v" in sys.argv
    job = _sources(JOB_CODE)
    every = "\n".join(p.read_text(encoding="utf-8") for p in PKG.rglob("*.py") if p.name != "config.py")
    problems: list[str] = []
    checked = 0
    # recipes
    models = _models()
    for mname, model in sorted(models.items()):
        for field in model.model_fields:
            key = f"{mname}.{field}"
            if key in ALLOW or f"*.{field}" in ALLOW:
                continue
            checked += 1
            receivers, files = RECEIVERS.get(mname, (RECIPE_VARS, None))
            if not read_in(_sources(files) if files else job, field, receivers):
                where = ", ".join(files or JOB_CODE)
                problems.append(f"recipe field {key} is never read from a {mname} object ({' / '.join(r + '.' for r in receivers)}) by the job code ({where})")
            elif verbose:
                print(f"ok   {key}")
    # settings (the app's and the engine's)
    for mname, model in (("Settings", config.Settings), ("EngineSettings", config.EngineSettings)):
        for field in model.model_fields:
            key = f"{mname}.{field}"
            if key in ALLOW or field == "engine":
                continue
            checked += 1
            if not re.search(rf"(\.{field}\b|[\"']{field}[\"'])", every):   # an attribute, or getattr / a key
                problems.append(f"setting {key} is never read outside config.py")
            elif verbose:
                print(f"ok   {key}")
    # capabilities: every key the route returns is mapped or informational, and what it maps to is a real field
    src = (PKG / "capabilities.py").read_text(encoding="utf-8")
    body = src[src.index("def capabilities("):src.index("def _image_models(")]
    keys: set[str] = set()
    depth = 0
    for m in re.finditer(r'[{}]|"([a-z_0-9]+)":', body.split("return {", 1)[1]):   # the returned dict's own keys, not nested ones
        if m.group(0) == "{":
            depth += 1
        elif m.group(0) == "}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0:
            keys.add(m.group(1))
    for k in sorted(keys):
        checked += 1
        if k not in CAPABILITIES:
            problems.append(f"/capabilities key {k!r} is neither mapped to the fields it feeds nor marked informational (CAPABILITIES in this script)")
            continue
        for target in CAPABILITIES[k] or []:
            kind, ref = target.split(":", 1)
            if kind == "recipe":
                m, f = ref.split(".")
                if m not in models or f not in models[m].model_fields:
                    problems.append(f"/capabilities {k!r} maps to {ref}, which is not a recipe field")
            elif ref not in config.Settings.model_fields:
                problems.append(f"/capabilities {k!r} maps to settings {ref}, which is not a setting")
        if verbose:
            print(f"ok   /capabilities {k} → {CAPABILITIES[k] or 'informational'}")
    for p in problems:
        print("FAIL", p)
    print(f"settings_audit: {checked} fields and parameters, {len(problems)} problem(s); {len(ALLOW)} allowed with a reason")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
