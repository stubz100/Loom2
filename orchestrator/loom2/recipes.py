"""Typed recipes (06 §3d): what the UI submits and what the compiler turns into an engine graph. Recipes carry
roster ids, never file paths, and every generative recipe has `loras` (D25: empty in MVP).

M3 implements T2I (09 §9): the prompt travels as a BFL tree / raw JSON / plain text; the compiler serialises
it per model (JSON for dev, prose for Klein) and the manifest records the exact string sent. The other kinds
are declared so the API and the queue carry them; their compilers arrive with their milestones.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from .models import registry


def _default(kind: str) -> Any:
    """D65: a recipe's default model comes from the registry (the spec whose `recipes.default_for` names the kind)."""
    return Field(default_factory=lambda: registry.default_model(kind), description=f"roster id; default: the registry's {kind} model (D65)")

PromptMode = Literal["tree", "json", "text"]
# The pinned engine's own enums (ComfyUI v0.39.0 `comfy.samplers.KSampler.SAMPLERS` / `SCHEDULERS` — unchanged since v0.38.2 — captured in
# tests/fixtures/object_info.json). `/capabilities` prefers the live engine's lists; "flux2" is loom2's name for the
# Flux2Scheduler sigmas (resolution-shifted, BFL's schedule) through SamplerCustomAdvanced instead of KSampler.
SAMPLERS = ["euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp", "heun", "heunpp2", "exp_heun_2_x0", "exp_heun_2_x0_sde", "dpm_2",
            "dpm_2_ancestral", "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_2s_ancestral_cfg_pp", "dpmpp_sde", "dpmpp_sde_gpu",
            "dpmpp_2m", "dpmpp_2m_cfg_pp", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_2m_sde_heun", "dpmpp_2m_sde_heun_gpu", "dpmpp_3m_sde",
            "dpmpp_3m_sde_gpu", "ddpm", "lcm", "ipndm", "ipndm_v", "deis", "cfgpp_ud10_ab", "res_multistep", "res_multistep_cfg_pp",
            "res_multistep_ancestral", "res_multistep_ancestral_cfg_pp", "gradient_estimation", "gradient_estimation_cfg_pp", "er_sde", "seeds_2",
            "seeds_3", "sa_solver", "sa_solver_pece", "ddim", "uni_pc", "uni_pc_bh2"]
SCHEDULERS = ["simple", "sgm_uniform", "karras", "exponential", "ddim_uniform", "beta", "normal", "linear_quadratic", "kl_optimal"]
FLUX2_SCHEDULE = "flux2"
# D65: a size or frame count off the model's grid is snapped down (the default — never more VRAM than asked, D18), snapped up, or
# refused with a 422 that names the field and the two values allowed around it
SizePolicy = Literal["snap_down", "snap_up", "error"]
WEIGHT_DTYPES = ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"]       # UNETLoader.weight_dtype
TE_DEVICES = ["default", "cpu"]                                                 # CLIPLoader.device


class LoraRef(BaseModel):
    model_id: str
    strength: float = 1.0


class RefImage(BaseModel):
    asset_id: str | None = None                   # catalogue asset …
    blob: str | None = None                       # … or an uploaded blob (sha256)
    note: str | None = None                       # D73: what the image shows — serialised into the prompt per model family
    mention: str | None = None                    # D73: the group id of the @mention that added it (mentions.py)


class Mention(BaseModel):
    """D73: an @mention of an album group. The client sends the id (and the name it shows); the server resolves it into references and
    stamps the group's revision and the asset ids it gave — a stamped mention is not resolved again."""
    group_id: str
    name: str | None = None
    revision: int | None = None
    asset_ids: list[str] = Field(default_factory=list)


class T2I(BaseModel):
    kind: Literal["t2i"] = "t2i"
    model_id: str = _default("t2i")
    prompt_mode: PromptMode = "json"              # which of the three carries the prompt
    prompt_json: dict[str, Any] | None = None     # the BFL tree (04 §3c) — used by tree and json modes
    prompt_text: str = ""                         # plain prompt (text mode) or an extra lead sentence for Klein
    negative: str = ""                            # honoured by CFG-capable variants only (Klein base)
    width: int = 960
    height: int = 544
    size_policy: SizePolicy = "snap_down"
    steps: int | None = None                      # None = the model preset (dev 20, Klein 4, Turbo 8)
    guidance: float | None = None                 # None = the model preset
    cfg: float | None = None                      # None = the model preset (1.0 distilled / 3.5 base)
    sampler: str | None = None                    # None = preset (euler); 09 §3b offers res_multistep
    scheduler: str | None = None                  # None = preset (simple)
    seeds: list[int] = Field(default_factory=lambda: [0])
    turbo: bool = False                           # dev: Turbo LoRA 8-step preset
    turbo_strength: float = Field(1.0, ge=0.0, le=2.0)   # LoraLoaderModelOnly.strength_model for the Turbo LoRA
    # ComfyUI configuration surfaced in M3+ (2026-10-06 audit): None = the model preset's value
    weight_dtype: str | None = None               # UNETLoader.weight_dtype (fp8_e4m3fn_fast is the speed candidate on gfx1201)
    te_device: str | None = None                  # CLIPLoader.device: "cpu" saves VRAM, costs ≈ 170 s per new prompt (E0)
    te_id: str | None = None                      # text encoder override: the preset's encoder or one of /capabilities.te_alternates (a .gguf loads through CLIPLoaderGGUF)
    base_shift: float | None = Field(None, ge=0.0, le=100.0)   # ModelSamplingFlux: both None = the model's own shift (FLUX.2 2.02)
    max_shift: float | None = Field(None, ge=0.0, le=100.0)
    tiled_vae: bool = False                       # VAEDecodeTiled instead of VAEDecode (Full tier headroom, D13 "tiled VAE")
    tile_size: int = Field(512, ge=64, le=4096)
    loras: list[LoraRef] = Field(default_factory=list)
    refs: list[RefImage] = Field(default_factory=list)   # reference images (FLUX.2 unified editing)
    ref_max_px: int = 1024                        # references are downscaled to fit this square by default
    mentions: list[Mention] = Field(default_factory=list)   # D73: @mentioned groups ("@hero walks into @tavern")
    tier: str | None = None


class I2I(BaseModel):
    """Refine (10 §4): partial-denoise img2img over the visible composite, the active layer or the selection crop.
    Distilled Klein cannot partial-denoise (04 §4), so the model is Klein base or dev."""
    kind: Literal["i2i"] = "i2i"
    model_id: str = _default("i2i")
    document_id: str = ""
    source: Literal["visible", "active", "selection"] = "visible"
    layer_id: str | None = None                   # for source == active
    prompt_text: str = ""
    strength: float = Field(0.3, ge=0.0, le=1.0)  # denoise (schedule semantics exact)
    steps: int | None = Field(None, ge=1, le=200)
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)
    margin_pct: int = Field(25, ge=0, le=200)     # selection source: context ring
    feather: int = Field(8, ge=0, le=256)         # selection source: paste-back feather
    match_colour: bool = False                    # D48: undo the refine's colour drift — the result's Lab statistics mapped onto the plate's
                                                  # (on the context ring for a selection, over the whole image / layer otherwise)
    te_device: str | None = None                  # CLIPLoader.device: "cpu" keeps the 8 GB encoder out of VRAM (2026-10-07 DynamicVRAM measurements)
    te_id: str | None = None                      # text encoder override: the preset's encoder or one of /capabilities.te_alternates (a .gguf loads through CLIPLoaderGGUF)


class Inpaint(BaseModel):
    """Inpaint / outpaint (10 §4, D7): Fill (Klein + LanPaint), Fill-Match (Klein ICM), Fill Hero (dev + LanPaint),
    Remove (Klein ICM with the hole neutralised), Outpaint (LanPaint on an edge-padded canvas). The region comes
    from the document's selection (uploaded by the editor) unless the mode is outpaint."""
    kind: Literal["inpaint"] = "inpaint"
    model_id: str = _default("inpaint")           # fill / outpaint run it; fill_hero runs the hero spec; ICM modes need a distilled model
    mode: Literal["fill", "fill_match", "fill_hero", "remove", "outpaint", "quick_remove"] = "fill"   # D62: quick_remove = CPU content-aware fill, no engine
    document_id: str = ""
    prompt_text: str = ""
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)
    # bounds (B4): region maths run on a worker thread the queue cannot interrupt, so every size knob is capped
    margin_pct: int = Field(25, ge=0, le=200)     # context ring around the mask (% of its longer side)
    min_size: int = Field(1024, ge=0, le=4096)    # auto-upscale small regions to ≥ this on the longer side
    max_pixels: int = Field(1_048_576, ge=65_536, le=4_194_304)   # cap on the engine image (≈ 1 MP; VRAM headroom on 16 GB, TDR 2026-10-05)
    feather: int = Field(8, ge=0, le=256)         # paste-back feather on the result's layer mask (px)
    expand: int = Field(0, ge=0, le=256)          # grow the mask before sampling (px)
    blend: Literal["feather", "seamless"] = "feather"   # D47: seamless = Poisson-clone onto the plate inside the feathered edge
    prefill: bool = False                         # D62: Remove — the hole pre-filled by content-aware fill (the reference instead of mid grey)
    prompt_mode: Literal["image_first", "prompt_first"] = "image_first"   # LanPaint (E8b: prompt_first λ 8)
    outpaint: dict[str, Annotated[int, Field(ge=0, le=4096)]] | None = None   # {left, top, right, bottom} for mode == outpaint
    image_blob: str | None = None                 # 10 §13 shape kept for blob-fed callers; unused with document_id
    mask_blob: str | None = None
    te_device: str | None = None                  # CLIPLoader.device (see I2I)
    te_id: str | None = None                      # text encoder override: the preset's encoder or one of /capabilities.te_alternates (a .gguf loads through CLIPLoaderGGUF)


class Upscale(BaseModel):
    """Upscale (10 §4): ESRGAN-class model on the visible composite or the active layer → a Catalogue asset at the
    new size (lineage to the document's source) and, optionally, a 1× "detail" layer in the document. With `refine`
    the upscaled image is re-sampled tile by tile at low strength (Klein base / dev; Ultimate-SD-Upscale pattern)."""
    kind: Literal["upscale"] = "upscale"
    model_id: str = _default("upscale")
    document_id: str = ""
    source: Literal["visible", "active"] = "visible"
    layer_id: str | None = None
    as_layer: bool = True
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)
    refine: bool = False                          # tiled refine after the model upscale (10 §4: Klein base, tile 1024, overlap 128, strength 0.25)
    refine_model_id: str = _default("i2i")
    strength: float = Field(0.25, ge=0.05, le=0.8)
    tile: int = Field(1024, ge=256, le=2048)
    overlap: int = Field(128, ge=0, le=512)
    steps: int | None = Field(None, ge=1, le=100)
    prompt_text: str = ""
    te_device: str | None = None                  # CLIPLoader.device for the refine's encoder (see I2I)
    te_id: str | None = None                      # text encoder override: the preset's encoder or one of /capabilities.te_alternates (a .gguf loads through CLIPLoaderGGUF)


class RefineEdge(BaseModel):
    """D45 Refine Edge (Photoshop's Select and Mask units). Defaults = matting.DEFAULTS, published in /capabilities.refine_edge (T8)."""
    radius: float = Field(10.0, ge=0, le=64)          # edge band, px (0 = no image-guided step)
    smart_radius: bool = True                          # adapt the band to the transition width the image shows
    smooth: float = Field(0.0, ge=0, le=100)
    feather: float = Field(0.0, ge=0, le=64)           # px (Gaussian σ = feather / 2)
    contrast: float = Field(0.0, ge=0, le=100)
    shift_edge: float = Field(0.0, ge=-100, le=100)    # % of max(radius, 4 px)


class Segment(BaseModel):
    """AI Select (10 §4, D7 masks): a mask from the visible composite becomes (part of) the document's selection.
    `subject` = BiRefNet matte through the core background-removal nodes; `text` / `points` / `box` = SAM 3
    (core `SAM3_Detect` on the sam3.pt checkpoint). Coordinates are document pixels; the queue scales them."""
    kind: Literal["segment"] = "segment"
    model_id: str = _default("segment")           # the subject matte, or SAM 3 (the mode picks the model that runs)
    document_id: str = ""
    mode: Literal["subject", "text", "points", "box"] = "subject"
    text: str = ""
    points: list[dict[str, int]] = Field(default_factory=list)   # {x, y, label}: label 1 = include, 0 = exclude
    box: list[int] | None = None                  # [x0, y0, x1, y1]
    threshold: float = Field(0.5, ge=0.0, le=1.0)
    refine_iterations: int = Field(2, ge=0, le=5)
    op: Literal["replace", "add", "subtract", "intersect"] = "replace"   # how the mask joins the current selection
    expand: int = Field(0, ge=-256, le=256)       # grow (> 0) or shrink (< 0) the mask, px
    feather: int = Field(0, ge=0, le=256)
    edge_refine: RefineEdge | None = None         # D45: refine the joined selection against the document composite afterwards
    max_size: int = Field(1024, ge=256, le=2048)  # engine image longer side (both models work at 1024)
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)


class Beat(BaseModel):
    """LTX keyframe guide (11 §3b): the asset is encoded as a guide at `frame` with `strength`."""
    frame: int = Field(ge=0, le=1000)
    asset_id: str
    strength: float = Field(1.0, ge=0.1, le=1.0)


class I2V(BaseModel):
    """Image-to-video (11 §10; D8 Wan 2.2 I2V-A14B fp8 experts + Lightning, FLF on the same weights; D9 LTX-2.3 distilled
    fp8 with keyframe beats). Sizes and frame counts snap to the model's rule in the compiler (Wan ×16 and 4n+1,
    LTX ×32 and 8n+1); `graphs.i2v_params` shows the UI what will run."""
    kind: Literal["i2v"] = "i2v"
    model_id: str = _default("i2v")               # Wan 2.2 or LTX-2.3 (the registry's video specs)
    start_asset: str
    end_asset: str | None = None                  # first/last-frame mode
    prompt_text: str = ""
    negative: str | None = None                   # None = the model's stock negative (Wan: the official list; LTX: a short one)
    frames: int = Field(81, ge=9, le=257)
    fps: int = Field(16, ge=8, le=48)
    width: int = Field(832, ge=128, le=1920)
    height: int = Field(480, ge=128, le=1920)
    size_policy: SizePolicy = "snap_down"     # D65: width, height and frames off the model's grid
    preset: Literal["draft", "motion", "quality"] = "draft"   # Wan: Lightning 2+2 / undistilled high + distilled low / 10+10; LTX: 8 / 12 / 20 steps
    steps: int | None = Field(None, ge=1, le=60)  # overrides the preset's step count
    cfg: float | None = Field(None, ge=1.0, le=12.0)          # Wan high expert CFG (motion / quality); the distilled paths ignore it
    shift: float | None = Field(None, ge=0.5, le=12.0)
    beats: list[Beat] = Field(default_factory=list)           # LTX only
    seeds: list[int] = Field(default_factory=lambda: [0])
    loras: list[LoraRef] = Field(default_factory=list)


MOVES = ("left45", "right45", "topdown", "closeup", "wide")
Move = Literal["left45", "right45", "topdown", "closeup", "wide"]


class Reangle(BaseModel):
    """P14 (D82): a new viewpoint of an asset. E12 (D77) decided the pair: the rotations through dx8152's angles LoRA on Qwen-Image-Edit
    2509, the framing moves (top-down, close-up, wide) through Klein 9B with a strict-reference prompt; `auto` picks by move from the
    specs' `recipes.reangle_moves`. The result is an asset next to the source (lineage `reangle`)."""
    kind: Literal["reangle"] = "reangle"
    asset_id: str
    move: Move
    method: Literal["auto", "angles_lora", "klein_prompt"] = "auto"
    prompt_text: str = ""                         # an extra sentence after the move's instruction (what the scene is, what to keep)
    seeds: list[int] = Field(default_factory=lambda: [0])
    te_id: str | None = None                      # Klein's encoder override (D31); the angles LoRA has one encoder

    @property
    def model_id(self) -> str:
        """The model the resolved method runs under `full`; the job code asks `reangle_model_id(recipe, variant)` (under `open` the
        framing moves run Klein 4B — Klein 9B is flux-nc, D26)."""
        return reangle_model_id(self)


def reangle_method(recipe: Reangle, variant: str = "full") -> str:
    """`auto` → the first offered spec (by `order`) whose `reangle_moves` lists the move; an explicit method runs any move."""
    if recipe.method != "auto":
        return recipe.method
    for spec in registry.reangle_specs():
        if registry.offered(spec, variant) and recipe.move in spec.recipes.reangle_moves:
            return spec.recipes.reangle or "angles_lora"
    return "klein_prompt"


def reangle_model_id(recipe: Reangle, variant: str = "full") -> str:
    method = reangle_method(recipe, variant)
    for spec in registry.reangle_specs():
        if spec.recipes.reangle == method and registry.offered(spec, variant):
            return spec.id
    raise ValueError(f"no model this build offers implements the angles method {method!r}")


Recipe = Annotated[Union[T2I, I2I, Inpaint, Upscale, Segment, I2V, Reangle], Field(discriminator="kind")]
AnyRecipe = T2I | I2I | Inpaint | Upscale | Segment | I2V | Reangle


class RecipeEnvelope(BaseModel):
    recipe: Recipe


def parse_recipe(data: dict) -> AnyRecipe:
    return RecipeEnvelope.model_validate({"recipe": data}).recipe


def inpaint_model_id(recipe: Inpaint, variant: str = "full") -> str:
    """The transformer an inpaint mode actually runs (10 §4): Fill Hero is dev; Fill-Match and Remove need a distilled Klein
    (ICM), falling back to Klein 9B — or to Klein 4B under the `open` variant (C3, D26)."""
    if recipe.mode == "fill_hero":
        return registry.hero_model()
    if recipe.mode in ("fill_match", "remove"):
        spec = registry.get(recipe.model_id)
        if spec is not None and recipe.mode in spec.recipes.inpaint:
            return recipe.model_id
        return registry.icm_model(variant)                # D65: the spec marked as the variant's ICM fallback
    return recipe.model_id


def warm_group(recipe: AnyRecipe, variant: str = "full") -> str:
    """Scheduling hint: jobs sharing a warm group run back to back so the engine keeps the weights resident."""
    if isinstance(recipe, Inpaint):
        if recipe.mode == "quick_remove":
            return "cpu"                             # D62: no weights at all
        return inpaint_model_id(recipe, variant)   # C10: the model that runs, not the one the panel named
    if isinstance(recipe, Upscale) and recipe.refine:
        return recipe.refine_model_id            # the big model decides the swap, not the 70 MB upscaler
    if isinstance(recipe, Reangle):
        return reangle_model_id(recipe, variant)   # P14: the model the move's method runs in this build
    return recipe.model_id
