"""D65 (ArtCraft P1): what loom2 knows about a model, as data. One `ModelSpec` per model id, loaded from `specs/*.toml`.

Licence and variants are not here: they come from the roster entry of the same id (one source, D17 / D26). Builders stay code (one per
`graph`); a spec carries only the values and flags they read.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Graph = Literal["flux2", "klein", "wan22", "ltx23", "esrgan", "matte", "sam", "qwen_edit"]      # the builder: image, video, upscaler, subject matte, SAM


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextEncoders(Strict):
    default: str                                   # roster id the preset loads
    alternates: list[str] = []                     # D31: encoders a recipe may name in `te_id` instead
    labels: dict[str, str] = {}                    # the panels' hint per encoder id


class Turbo(Strict):
    lora: str                                      # roster id of the distillation LoRA (dev: Flux2TurboComfyv2)
    steps: int = 8


class Roles(Strict):
    te: TextEncoders | None = None
    vae: str | None = None
    extra: dict[str, str] = {}                     # video: low_expert, lightning_high / _low, projection, audio_vae


class Sampling(Strict):
    steps: int = 20
    guidance: float = 4.0
    cfg: float = 1.0
    sampler: str = "euler"
    scheduler: str = "simple"
    weight_dtype: str = "default"
    distilled: bool = False                        # distilled Klein: fixed steps, CFG 1, no negative, no partial denoise
    json_prompt: bool = True                       # dev takes the BFL JSON verbatim; Klein wants prose
    turbo: Turbo | None = None
    edit_steps: int | None = None                  # steps in the Edit graphs (LanPaint fill, refine) when they differ from `steps` (dev: 8 with Turbo)
    edit_guidance: float | None = None             # guidance in the LanPaint fill when it differs from `guidance`
    edit_negative: Literal["zero_out", "text"] = "text"   # refine / tiled refine negative: ConditioningZeroOut (dev) or a short text
    model_shift: float | None = None               # the model's constant shift (shown in Generate · Advanced)
    cfg_fixed: bool = False                        # CFG stays at `cfg` although the model is not distilled (dev is guidance-distilled)
    cfg_note: str | None = None                    # why, or how to use it — the panel's hint next to CFG


class Recipes(Strict):
    default_for: list[str] = []                    # recipe kinds whose default model this is (t2i, i2i, inpaint, upscale, segment, i2v)
    t2i: bool = False
    i2i: bool = False                              # partial denoise (refine, tiled refine): base and dev models
    inpaint: list[str] = []                        # modes this model runs (fill, fill_match, remove, outpaint)
    inpaint_hero: bool = False                     # Fill Hero runs this model, whatever the panel named
    icm_default: list[str] = []                    # variants where this is the ICM fallback (Fill-Match / Remove on a model that cannot)
    upscale_factor: int | None = None
    segment: list[str] = []                        # AI Select modes (subject · text · points · box)
    i2v: bool = False
    flf: bool = False                              # first + last frame
    beats: bool = False                            # keyframes in between
    reangle: str | None = None                     # P14 (D82): the angles method this model implements — angles_lora | klein_prompt
    reangle_moves: list[str] = []                  # the moves it is good for (E12 ≥ 7/10): auto picks the first model listing the move


class RefsSuggest(Strict):
    at: int                                        # from this many reference images …
    model: str                                     # … suggest this model instead
    why: str


class Inputs(Strict):
    refs_max: int = 0
    refs_suggest: RefsSuggest | None = None


class Geometry(Strict):
    size_mult: int = 16
    frame_step: int | None = None                  # video: 4n+1 / 8n+1
    fps: int | None = None
    frames: int | None = None
    size: list[int] | None = None                  # video: the Draft size
    tiers: dict[str, list[int]] = {}               # image: thumb / draft / full; video: draft / hd / portrait / square


class VideoPreset(Strict):
    label: str
    steps: int
    split: int | None = None                       # Wan: the high expert runs [0, split), the low [split, steps)
    cfg_high: float | None = None
    cfg_low: float | None = None
    shift: float | None = None
    lora_high: bool = False
    lora_low: bool = False
    seconds: float | None = None                   # baseline at the Draft tier (E4 / E5 spikes)


class Video(Strict):
    label: str
    negative: str
    presets: dict[str, VideoPreset]


class Estimates(Strict):
    vram_gb: float = 12.0                          # admission check (measured peaks)
    base_seconds: float | None = None              # one image at 960×544 (E0 / E8 spikes)
    turbo_seconds: float | None = None
    doc_seconds: float | None = None               # one Edit candidate, warm, incl. the model swap (D64)
    tile_seconds: float | None = None              # one 1024² tile of a tiled refine


class ModelSpec(Strict):
    id: str                                        # the roster id of the main weight
    family: str
    label: str
    short: str | None = None                       # the panels' compact name (job rows, clip cards)
    hint: str | None = None                        # one line on the model card
    order: int = 100                               # position in the panels' model lists
    graph: Graph                                   # names the builder
    wired: bool = True                             # offered by the panels
    disabled_reason: str | None = None
    roles: Roles = Field(default_factory=Roles)
    sampling: Sampling = Field(default_factory=Sampling)
    recipes: Recipes = Field(default_factory=Recipes)
    inputs: Inputs = Field(default_factory=Inputs)
    geometry: Geometry = Field(default_factory=Geometry)
    estimates: Estimates = Field(default_factory=Estimates)
    video: Video | None = None

    def weights(self, te_id: str | None = None, turbo: bool = False) -> list[str]:
        """Every roster id this model loads (the open-variant gate, missing weights): the transformer, its encoder, VAE, the Turbo
        LoRA when used, and the video extras."""
        ids = [self.id]
        if self.roles.te:
            ids.append(te_id if te_id in self.roles.te.alternates else self.roles.te.default)
        if self.roles.vae:
            ids.append(self.roles.vae)
        if turbo and self.sampling.turbo:
            ids.append(self.sampling.turbo.lora)
        ids += list(self.roles.extra.values())
        return list(dict.fromkeys(ids))
