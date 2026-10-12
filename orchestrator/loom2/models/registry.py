"""D65: the model registry — every `specs/*.toml` (and any folder listed in `LOOM2_MODEL_SPECS`, os.pathsep-separated), validated at
import against the roster. A spec for a weight the roster does not list carries a `weight` table (the roster fields: name, folder,
repo, file, license, variants, approx_gb) and is added to the roster, so a new model is data only (P1's acceptance).

Lookups the builders, recipes, estimates and `/capabilities` use instead of model-id literals live here.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from ..roster import ROSTER, ROSTER_BY_ID, RosterEntry
from .spec import ModelSpec

SPEC_DIR = Path(__file__).parent / "specs"
IMAGE_GRAPHS = ("flux2", "klein")


class RegistryError(ValueError):
    pass


SPECS: dict[str, ModelSpec] = {}


def _spec_files() -> list[Path]:
    files = sorted(SPEC_DIR.glob("*.toml"))
    for d in filter(None, os.environ.get("LOOM2_MODEL_SPECS", "").split(os.pathsep)):
        files += sorted(Path(d).glob("*.toml"))
    return files


def _check(spec: ModelSpec) -> None:
    def known(rid: str, what: str) -> None:
        e = ROSTER_BY_ID.get(rid)
        if e is None:
            raise RegistryError(f"{spec.id}: {what} {rid!r} is not in the roster")
        if e.retired:
            raise RegistryError(f"{spec.id}: {what} {rid!r} is retired ({e.retired})")
    known(spec.id, "model")
    if ROSTER_BY_ID[spec.id].family != spec.family:
        raise RegistryError(f"{spec.id}: family {spec.family!r} differs from the roster's {ROSTER_BY_ID[spec.id].family!r}")
    if spec.roles.te:
        for t in [spec.roles.te.default, *spec.roles.te.alternates]:
            known(t, "text encoder")
    if spec.roles.vae:
        known(spec.roles.vae, "VAE")
    for k, rid in spec.roles.extra.items():
        known(rid, k)
    if spec.sampling.turbo:
        known(spec.sampling.turbo.lora, "Turbo LoRA")
    if spec.recipes.i2v and spec.video is None:
        raise RegistryError(f"{spec.id}: an i2v model needs a [model.video] block (negative, presets)")


def load() -> dict[str, ModelSpec]:
    """(Re)read every spec file into SPECS (in place: modules holding the dict see the new contents)."""
    found: dict[str, ModelSpec] = {}
    for f in _spec_files():
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise RegistryError(f"{f.name}: {e}") from e
        for raw in data.get("model", []):
            raw = dict(raw)
            weight: dict[str, Any] | None = raw.pop("weight", None)
            spec = ModelSpec.model_validate(raw)
            if spec.id in found:
                raise RegistryError(f"{f.name}: model {spec.id!r} is defined twice")
            if weight is not None and spec.id not in ROSTER_BY_ID:
                entry = RosterEntry(id=spec.id, family=spec.family, **weight)
                ROSTER.append(entry)
                ROSTER_BY_ID[spec.id] = entry
            _check(spec)
            found[spec.id] = spec
    SPECS.clear()
    SPECS.update(found)
    return SPECS


# ---- lookups --------------------------------------------------------------------------------------------------------------------
def get(model_id: str | None) -> ModelSpec | None:
    return SPECS.get(model_id or "")


RUNS = {"t2i": lambda s: s.recipes.t2i, "i2i": lambda s: s.recipes.i2i, "inpaint": lambda s: bool(s.recipes.inpaint),
        "upscale": lambda s: s.recipes.upscale_factor is not None, "segment": lambda s: bool(s.recipes.segment), "i2v": lambda s: s.recipes.i2v}


def offered(spec: ModelSpec, variant: str | None) -> bool:
    """Under the open variant only Apache/MIT weights are offered (D26) — the roster entry says which."""
    return variant != "open" or "open" in ROSTER_BY_ID[spec.id].variants


def default_model(kind: str, variant: str | None = None) -> str:
    """The spec named the default for `kind` (recipes.default_for); when the variant does not offer it, the first offered spec (by
    order) that runs the kind — Klein 4B for t2i / inpaint and Klein 4B base for refine under open."""
    for s in SPECS.values():
        if kind in s.recipes.default_for and offered(s, variant):
            return s.id
    runs = RUNS.get(kind, lambda s: False)
    for s in sorted(SPECS.values(), key=lambda x: x.order):
        if runs(s) and offered(s, variant):
            return s.id
    raise RegistryError(f"no spec is the default for {kind!r}")


def reangle_specs() -> list[ModelSpec]:
    """P14 (D82): the specs that implement an angles method, by `order` — `auto` takes the first one listing the move."""
    return sorted((s for s in SPECS.values() if s.recipes.reangle), key=lambda s: s.order)


def image_specs() -> list[ModelSpec]:
    return [s for s in SPECS.values() if s.graph in IMAGE_GRAPHS]


def video_specs() -> list[ModelSpec]:
    return [s for s in SPECS.values() if s.recipes.i2v]


def hero_model() -> str:
    for s in SPECS.values():
        if s.recipes.inpaint_hero:
            return s.id
    raise RegistryError("no spec runs Fill Hero")


def icm_model(variant: str) -> str:
    """The model Fill-Match and Remove fall back to when the panel named one that cannot run ICM (a base model)."""
    for s in SPECS.values():
        if variant in s.recipes.icm_default:
            return s.id
    raise RegistryError(f"no ICM fallback for the {variant!r} variant")


def segment_model(mode: str) -> str:
    for s in SPECS.values():
        if mode in s.recipes.segment:
            return s.id
    raise RegistryError(f"no spec runs AI Select mode {mode!r}")


load()
