"""Typed recipes (06 §3d): what the UI submits and what the compiler turns into an engine graph. Recipes carry
roster ids, never file paths, and every generative recipe has `loras` (D25: empty in MVP).

M1 implements T2I; the other kinds are declared so the API and the queue carry them, and the compiler raises
`NotImplementedError` until their milestone (M5 inpaint/refine, M6 video).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class LoraRef(BaseModel):
    model_id: str
    strength: float = 1.0


class T2I(BaseModel):
    kind: Literal["t2i"] = "t2i"
    model_id: str = "flux2-dev-fp8mixed"
    prompt_text: str = ""
    prompt_json: dict[str, Any] | None = None     # BFL JSON prompt (dev); flattened to prose for Klein
    negative: str = ""
    width: int = 960
    height: int = 544
    steps: int | None = None                      # None = the model preset (dev 20, Klein 4, Turbo 8)
    guidance: float | None = None                 # None = the model preset
    cfg: float = 1.0
    seeds: list[int] = Field(default_factory=lambda: [0])
    turbo: bool = False                           # dev: Turbo LoRA 8-step preset
    loras: list[LoraRef] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)  # asset ids used as reference images (Klein edit path, later)
    tier: str | None = None


class I2I(BaseModel):
    kind: Literal["i2i"] = "i2i"
    model_id: str
    source_asset: str
    prompt_text: str = ""
    strength: float = 0.3
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)


class Inpaint(BaseModel):
    kind: Literal["inpaint"] = "inpaint"
    model_id: str = "klein-9b"
    mode: Literal["fill", "fill_match", "fill_hero", "remove"] = "fill"
    image_blob: str                               # sha256 of the uploaded region PNG
    mask_blob: str
    prompt_text: str = ""
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)


class I2V(BaseModel):
    kind: Literal["i2v"] = "i2v"
    model_id: str = "wan22-i2v-high-fp8"
    start_asset: str
    end_asset: str | None = None
    prompt_text: str = ""
    frames: int = 81
    fps: int = 16
    width: int = 832
    height: int = 480
    preset: Literal["draft", "motion", "quality"] = "draft"
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)


Recipe = Annotated[Union[T2I, I2I, Inpaint, I2V], Field(discriminator="kind")]


class RecipeEnvelope(BaseModel):
    recipe: Recipe


def parse_recipe(data: dict) -> T2I | I2I | Inpaint | I2V:
    return RecipeEnvelope.model_validate({"recipe": data}).recipe


def warm_group(recipe: T2I | I2I | Inpaint | I2V) -> str:
    """Scheduling hint: jobs sharing a warm group run back to back so the engine keeps the weights resident."""
    return recipe.model_id
