"""LoRA slots (09 §3b, D25 → 18 §3b / §3e, LT1): the adapters a recipe may carry in its `loras[]`, where they come from, and the fit
check at submission — T8: the list the pickers show (`GET /loras`) is exactly what the worker loads.

A `LoraRef.model_id` is one of
  - a roster id (`role="lora"`): the entry's `base` names the model it fits, its `preset` the mechanism that already applies it (the Turbo
    toggle, the Lightning presets, the angles method, the Stage pose LoRA, the IC-LoRA guide) — those never go in a slot, their toggle owns them;
  - `file:<path under a loras folder>`: a file on disk no roster entry claims (the author's own LoRAs, E16's adapters under `loras/e16/`) — its
    family is not declared, so it is offered to every model with that said and the engine's log names the keys it cannot load;
  - `lora-…` (LT2): a LoRA the project trained, with the base the training recorded.
The engine's loader takes the file's name relative to the loras folder; ComfyUI lists a subfolder's file with the OS separator and
`contract.resolve_names` matches the basename, so the chain hands over the relative path with "/" and the contract check settles it.
"""
from __future__ import annotations

from typing import Any

from .models import registry
from .recipes import LoraRef
from .roster import ROSTER, ROSTER_BY_ID, Roster, RosterEntry

FILE_PREFIX = "file:"
MAX_SLOTS = 4
PRESET_OWNERS = {"turbo": "the Turbo toggle", "lightning": "the Lightning preset", "angles": "the angles method", "stage": "the Stage pose method",
                 "guide": "the guided clip"}


def model_base(model_id: str | None) -> str | None:
    """The adapter base a model takes LoRAs for: the spec's `base`, else its family (klein-4b and klein-base-4b share one; 9B, base-9B and KV another)."""
    spec = registry.get(model_id)
    if spec is None:
        return None
    return spec.base or spec.family


def base_label(base: str | None) -> str:
    """A base's name for a sentence: the label of the first model (by the panels' order) that takes it — D65: no model name in code."""
    if not base:
        return "any model"
    specs = sorted((s for s in registry.SPECS.values() if (s.base or s.family) == base), key=lambda s: s.order)
    return specs[0].label if specs else base


def is_file(model_id: str) -> bool:
    return model_id.startswith(FILE_PREFIX)


def _file_rel(model_id: str) -> str:
    return model_id[len(FILE_PREFIX):].replace("\\", "/").strip("/")


def _entry_fits(entry: RosterEntry, base: str | None) -> bool:
    return (entry.base or entry.family) == base


def lora_options(roster: Roster, model_id: str, variant: str | None = "full") -> list[dict[str, Any]]:
    """What the slots may hold for this model, trained first (LT2), then the roster's free LoRAs, then the files on disk; the ones that do
    not fit stay in the list with `fits: false` and the sentence, so the panel can say why. Preset-owned entries are left out."""
    base = model_base(model_id)
    out: list[dict[str, Any]] = []
    for e in ROSTER:
        if e.role != "lora" or e.retired or e.preset:
            continue
        r = roster.resolve(e.id)
        if variant == "open" and "open" not in e.variants:
            continue
        fits = _entry_fits(e, base)
        out.append({"id": e.id, "label": f"{e.name.rsplit('.', 1)[0]} · {base_label(e.base or e.family)}", "source": "roster", "base": e.base or e.family,
                    "fits": fits and r.path is not None, "why": None if fits and r.path else (f"{r.health} on disk" if fits else f"trained for {base_label(e.base or e.family)}"),
                    "name": e.name, "size": r.size, "license": e.license, "health": r.health, "preset": None, "strength": 1.0})
    for f in roster.lora_files():
        open_ok = variant != "open"
        out.append({"id": FILE_PREFIX + f["rel"], "label": f"{f['rel'].rsplit('.', 1)[0]} · file", "source": "file", "base": None,
                    "fits": open_ok, "why": "licence unknown — a file on disk is not offered under the open variant (D26)" if not open_ok else "family not declared by the file — the engine's log names the keys it cannot load",
                    "name": f["name"], "size": f["size"], "license": None, "health": "present", "preset": None, "strength": 1.0})
    return out


def lora_name(roster: Roster, model_id: str) -> str:
    """The loader's `lora_name`: a roster LoRA's file name, a file's path relative to its loras folder (with "/"; the contract check
    matches the engine's listing). Raises FileNotFoundError when the file is not on disk."""
    if is_file(model_id):
        rel = _file_rel(model_id)
        if not any(f["rel"] == rel for f in roster.lora_files()):
            raise FileNotFoundError(f"LoRA file {rel!r} is not in a loras folder")
        return rel
    _, name = roster.require(model_id)
    return name


def check_loras(roster: Roster, loras: list[LoraRef], model_id: str, variant: str | None = "full") -> None:
    """B11 for the slots: every problem is a sentence at submission (HTTP 422), never minutes later on the engine."""
    if len(loras) > MAX_SLOTS:
        raise ValueError(f"{len(loras)} LoRAs: at most {MAX_SLOTS} slots")
    seen: set[str] = set()
    base = model_base(model_id)
    spec = registry.get(model_id)
    for ref in loras:
        mid = ref.model_id
        if mid in seen:
            raise ValueError(f"LoRA {mid!r} is in two slots")
        seen.add(mid)
        if not (0.0 <= float(ref.strength) <= 2.0):
            raise ValueError(f"LoRA {mid!r}: strength {ref.strength} is outside 0–2")
        if is_file(mid):
            if variant == "open":
                raise ValueError(f"LoRA file {_file_rel(mid)!r}: licence unknown — not offered under the open variant (D26)")
            lora_name(roster, mid)                                   # FileNotFoundError when it left the disk
            continue
        e = ROSTER_BY_ID.get(mid)
        if e is None or e.role != "lora":
            raise ValueError(f"unknown model id {mid!r} in a LoRA slot")                 # the wording every unknown id gets (B11)
        if e.preset:
            raise ValueError(f"{e.name} is {PRESET_OWNERS.get(e.preset, 'a preset')}'s LoRA — it is not a slot")
        if not _entry_fits(e, base):
            raise ValueError(f"{e.name} was trained for {base_label(e.base or e.family)}; this job runs {spec.label if spec else model_id}")
        if variant == "open" and "open" not in e.variants:
            raise ValueError(f"{mid!r} ({e.license}) is not part of the open variant (D26)")
        roster.require(mid)                                          # FileNotFoundError: missing on disk


def check_recipe_loras(roster: Roster, recipe: Any, variant: str | None = "full") -> None:
    """The slots of any recipe against the model that will run it (an Inpaint's model is the mode's, not the panel's); every problem a
    ValueError — the queue answers 422 at submission, the preview the same sentence."""
    loras = getattr(recipe, "loras", None) or []
    if not loras:
        return
    from .engine.graphs import inpaint_model_id                           # graphs imports this module's lora_name lazily; no cycle
    from .recipes import Inpaint
    ran = inpaint_model_id(recipe, variant) if isinstance(recipe, Inpaint) else recipe.model_id
    try:
        check_loras(roster, loras, ran, variant)
    except FileNotFoundError as e:
        raise ValueError(str(e))


def lora_names_listed(object_info: dict, names: list[str]) -> bool:
    """Whether the engine's last `/object_info` lists every name (by basename — ComfyUI prints a subfolder's file with the OS separator)."""
    try:
        options = object_info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0]
    except (KeyError, TypeError, IndexError):
        return True                                                   # no enum to check against: the contract check decides
    if not isinstance(options, list):
        return True
    listed = {str(o).replace("\\", "/").rsplit("/", 1)[-1] for o in options}
    return all(n.replace("\\", "/").rsplit("/", 1)[-1] in listed for n in names)
