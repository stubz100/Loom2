"""Typed recipes (06 §3d): what the UI submits and what the compiler turns into an engine graph. Recipes carry
roster ids, never file paths, and every generative recipe has `loras` (D25: empty in MVP).

M3 implements T2I (09 §9): the prompt travels as a BFL tree / raw JSON / plain text; the compiler serialises
it per model (JSON for dev, prose for Klein) and the manifest records the exact string sent. The other kinds
are declared so the API and the queue carry them; their compilers arrive with their milestones.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator

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
    model_id: str                                 # a roster id, `file:<path under a loras folder>` or a trained LoRA's id (LT1 / LT2, 18 §3b)
    strength: float = Field(1.0, ge=0.0, le=2.0)


class RefImage(BaseModel):
    asset_id: str | None = None                   # catalogue asset …
    blob: str | None = None                       # … or an uploaded blob (sha256)
    note: str | None = None                       # D73: what the image shows — serialised into the prompt per model family
    mention: str | None = None                    # D73: the group id of the @mention that added it (mentions.py)


class SubjectShot(BaseModel):
    """D93 (B4): a linked subject's words for this shot only — an outfit in place of the sheet's, and a line after the sheet ("soaked, hood
    up"). The character's sheet itself is read from Cast at submit (story.compose_subject), never copied into the panel."""
    outfit: str = Field("", max_length=400)
    note: str = Field("", max_length=400)


class Mention(BaseModel):
    """D73: an @mention of an album group. The client sends the id (and the name it shows); the server resolves it into references and
    stamps the group's revision and the asset ids it gave — a stamped mention is not resolved again. D85: a Story profile mention names
    the profile (and a version, or its current one); the server swaps the version's reference group in and stamps both — the
    `asset@version` pin of loom R98."""
    group_id: str = ""
    name: str | None = None
    revision: int | None = None
    asset_ids: list[str] = Field(default_factory=list)
    profile_id: str | None = None
    version: str | None = None
    lora: str | None = None                       # LT3 (18 §3f): the version's LoRA the mention added to the slots (stamped)
    lora_available: str | None = None             # LT3: the version's LoRA whether or not it was added (the chip's on / off)
    subject: int | None = Field(None, ge=0)       # D92: the Tree prompt's subject card linked to this profile (its index in prompt_json.subjects) — the link comes back with the recipe
    skipped: int | None = None                    # D93 (A3): the set's images left out for the model's room (stamped; the preview says so)
    shot: SubjectShot | None = None               # D93 (B4): the linked subject's per-shot override (sent by the card, kept with the recipe)
    composed: str | None = None                   # D93 (B4): the description the linked subject carried — the version's sheet + the shot (stamped)
    scene: bool = False                           # D93 (C6): a Cast place linked to the Tree's scene — its sheet (+ `shot.note`) is the scene's text
    held_by: int | None = Field(None, ge=0)       # D93 (C6): a Cast prop held by that subject card ("holding <the prop's clause>"), bound to it
    figure: str | None = None                     # D93 (C8): a Stage figure (its object id) bound to this character — StageShot's figures, left to right


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
    auto_lora: bool = True                        # LT3 (18 §3f): a profile mention adds its version's LoRA + trigger when the model takes it; off = this prompt without
    bind_refs: bool | None = None                 # D93 (A3): each linked subject names its own reference images in the prompt; None = the model's spec (inputs.bind_refs)
    style_id: str | None = None                   # D85: the Story world's style this generation carries (one; None = no style)
    style_text: str | None = None                 # D85: its fragment, stamped at submit by story.resolve_style and appended after the prompt; None = unresolved
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


class ExtendFrom(BaseModel):
    """D88 XE (experimental): continue a clip — its last `lead` frames lead the new one in (LTX: 9 pinned by LTXVAddGuide at frame 0;
    Wan: 1, the start image is its last frame). The new clip records `chained_from` / `overlap`."""
    clip_id: str
    lead: int = Field(9, ge=1, le=33)


class AudioRef(BaseModel):
    """D88 XL (experimental): the spoken line a lip-sync clip follows (an `audio` asset, CN2)."""
    asset_id: str


class Guide(BaseModel):
    """P13 ST4 (D76, 16 §8): a pass sequence (a video asset the Stage rendered — depth by default, pose as the weaker second) that LTX-2.3's
    IC-LoRA Union conditions the whole clip on, from frame 0. The start frame is a Stage shot; the clip keeps lineage to both."""
    asset_id: str
    kind: Literal["depth", "pose"] = "depth"
    strength: float = Field(1.0, ge=0.0, le=1.0)


class AnimateChain(BaseModel):
    """D111 (PS5c, E23a's W1): a pose-driven performance in batches — this batch starts where the previous one ended. The previous batch's
    last `carry` frames continue the motion (`continue_motion`), and the pose guide is read from `offset` on (`video_frame_offset`)."""
    clip_id: str | None = None                    # the previous batch (None: the first batch)
    carry: int = Field(5, ge=1, le=16)
    offset: int = Field(0, ge=0, le=4000)


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
    preset: Literal["draft", "motion", "quality", "fast"] = "draft"   # D88 XL: S2V draft (20) / fast (10); Wan: Lightning 2+2 / undistilled high + distilled low / 10+10; LTX: 8 / 12 / 20 steps
    steps: int | None = Field(None, ge=1, le=60)  # overrides the preset's step count
    cfg: float | None = Field(None, ge=1.0, le=12.0)          # Wan high expert CFG (motion / quality); the distilled paths ignore it
    shift: float | None = Field(None, ge=0.5, le=12.0)
    beats: list[Beat] = Field(default_factory=list)           # LTX only
    guide: Guide | None = None                                # ST4: a Stage pass sequence through the IC-LoRA (LTX only)
    extend_from: ExtendFrom | None = None                     # D88 XE (experimental): continue that clip
    audio: AudioRef | None = None                             # D88 XL (experimental): the line a lip-sync model follows (S2V)
    chain: AnimateChain | None = None                         # D111 (PS5c): Wan Animate in batches (pose-driven models only)
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


STAGE_METHODS = ("clay", "refcontrol")
STAGE_PASSES = ("clay", "depth", "normal", "pose", "mask")


class StageShot(BaseModel):
    """P13 ST3 (D78, 16 §7): a stage camera's blocking rendered as an image. `clay`: Klein 9B with the clay pass as image 1 ("keep image 1's
    camera, framing and poses"), the reference deck as images 2…; `refcontrol`: Klein base 9B + RefControl's pose LoRA, the pose pass as
    image 1 and the first reference as image 2 (D81: the pose pass alone). The passes are `stage-pass` assets uploaded by the client
    (`POST /stages/{id}/passes`); the result lands with lineage `stage-shot` to them and the references."""
    kind: Literal["stage_shot"] = "stage_shot"
    stage_id: str
    camera_id: str
    passes: dict[str, str]                        # pass name → asset id (at least the one the method takes: clay, or pose)
    method: Literal["clay", "refcontrol"] = "clay"
    prompt_text: str = ""                         # what the scene is — after the method's own lead sentence
    refs: list[RefImage] = Field(default_factory=list)   # the reference deck (D73); refcontrol takes the first as image 2
    mentions: list[Mention] = Field(default_factory=list)   # D93 (C8): the figures bound to Cast characters, in screen order left to right (`figure`)
    bind_refs: bool | None = None                 # D93 (C8): each bound figure names its references in the prompt; None = the method's spec
    seeds: list[int] = Field(default_factory=lambda: [0])
    width: int = 1280                             # the project tier (D18: Draft by default)
    height: int = 720
    te_id: str | None = None                      # Klein's encoder override (D31)
    empty: bool = False                           # D111 (PS5b): the bare set, a plate — the lead speaks of the empty space, no mannequins or people

    @property
    def model_id(self) -> str:
        """The model the method runs under `full`; the job code asks `stage_model_id(recipe, variant)` (under `open` clay runs Klein 4B)."""
        return stage_model_id(self)


def stage_spec(method: str, variant: str = "full"):
    """The first offered spec (by `order`) implementing a Stage method, or None."""
    for spec in registry.stage_specs():
        if spec.recipes.stage == method and registry.offered(spec, variant):
            return spec
    return None


def stage_model_id(recipe: StageShot, variant: str = "full") -> str:
    spec = stage_spec(recipe.method, variant)
    if spec is None:
        raise ValueError(f"no model this build offers implements the Stage method {recipe.method!r}")
    return spec.id


class ImageToMesh(BaseModel):
    """P18 (D79 / D84): a textured GLB prop from one image through Pixal3D (ComfyUI's template, frozen as engine/pixal3d_graph.json): the
    cut-out by BiRefNet, DINOv3 conditioning with MoGe's field of view, the structure → shape → upsample → texture stages, remesh, decimate,
    bake. A background job of some minutes (warm ≈ 243 s, cold ≈ 361 s on the rig); the result is a Catalogue asset of kind `mesh` with
    lineage `image-to-mesh` to the source, which the Stage library places as a prop."""
    kind: Literal["image_to_mesh"] = "image_to_mesh"
    asset_id: str
    model_id: str = _default("mesh")
    resolution: Literal[1024, 1536] = 1024        # the upsample stage's target (0.39 floors at 1024; 1536 is the template's own, slower)
    faces: int = Field(50000, ge=2000, le=700000)  # DecimateMesh's target (E14: 46–50k after 50k)
    seeds: list[int] = Field(default_factory=lambda: [0])


class ImageToSet(BaseModel):
    """SC3 (D120, after E30): a picture of a place as a set — MoGe-2's metric point map (the depth model Pixal3D carries, MIT) triangulated
    by the engine into a textured relief with the picture as its texture (`MoGePointMapToMesh`); the camera that took the picture sits at
    the origin looking down −Z. Seconds, not minutes. The result is a Catalogue asset of kind `mesh` (lineage `image-to-set` ← the picture)
    and, when a stage is named, that stage gets the set standing on its floor and the picture's camera (the lens read back from the relief)."""
    kind: Literal["image_to_set"] = "image_to_set"
    asset_id: str                                  # the picture (a Catalogue image)
    model_id: str = _default("set")
    lens_deg: float | None = Field(None, ge=20, le=150)   # the picture's horizontal field of view when known; None = MoGe's own reading (E30: it wobbles)
    relief: Literal["cut", "sheet"] = "cut"        # cut at depth jumps (honest holes behind things) or one sheet (smears instead; a smooth place)
    decimation: int = Field(2, ge=1, le=4)         # the point map's vertex stride (2: a 1280×720 picture is ≈ 230k vertices, 10 MB)
    stage_id: str | None = None                    # the stage the set lands on, with the picture's camera, when the job finishes
    replace_set_id: str | None = None              # SC3b: the picture set this job rebuilds in place (a corrected lens): its relief, lens and floor, its camera following


class Render(BaseModel):
    """P17 (D83) slice 2: a draft render of a sequence — a CPU job (no engine) that becomes a Catalogue clip: every lane tick read from
    the clips' PNG masters, dissolves blended, frames mapped by nearest frame where a clip's rate differs from the lane's (D27: no
    conform here; RIFE at export is post-MVP). Rendered at the first clip's size, at the lane's fps."""
    kind: Literal["render"] = "render"
    timeline_id: str
    seeds: list[int] = Field(default_factory=lambda: [0])
    movie: bool = False                            # RC3 (D96, proto01_animate 29): the finished movie — RIFE-conformed, at the cut's size, the voice lane mixed in, an MP4 in the cut's folder
    delivery: Literal["h264", "prores"] = "h264"   # CE5 (a FilmCraft cut's movie): H.264 to watch (.mp4) or ProRes 422 HQ to finish (.mov)
    burn_captions: bool = False                    # CE5: the caption track burned into the picture
    captions_file: Literal["srt", "vtt"] | None = None   # CE5: the captions written beside the movie


class TrainLora(BaseModel):
    """18 §3c (LT2, D86): a LoRA trained on an album page (D122: every image on it not in the Trash) — a staged job that runs ai-toolkit
    in its own venv with the engine stopped (16 GB first); the adapter lands in the project's registry (story/loras/) and, with a Cast
    version (`profile_id` + `version`), on the version's `lora` + `trigger`. `group_id` None is the version's reference album (a recipe
    queued before D122). `model_id` is the base's roster id (a spec with `recipes.train`; /capabilities.train's bases)."""
    kind: Literal["train_lora"] = "train_lora"
    group_id: str | None = None                   # D122: the album trained on
    profile_id: str | None = None                 # the Cast version the adapter goes to; none for an album's own adapter
    version: str | None = None
    model_id: str
    steps: int = Field(1000, ge=100, le=5000)
    rank: int = Field(16, ge=4, le=128)
    resolution: int = Field(512, ge=256, le=1024)
    lr: float = Field(1e-4, gt=0.0, le=1e-2)
    seed: int = 42
    trigger: str = ""                             # the Cast tab makes one from the profile's name: <slug>_<4 hex>
    name: str = ""                                # the record's name; "<profile> <version>" when empty
    setting: str = ""                             # E16: a setting word appended to every caption, so the background is a captioned thing
    seeds: list[int] = Field(default_factory=lambda: [0])   # one job (the queue's seed loop); the training seed is `seed`


class TtsItem(BaseModel):
    """One line to speak; `node_id` + `index` name the Flow line it lands on (a free line has neither)."""
    text: str
    node_id: str | None = None
    index: int | None = None


class TTS(BaseModel):
    """19 §3b (CN2, D87): lines spoken by one of the project's voices — a CPU job on the draft tier (Kokoro beside a running engine), a GPU
    job on the cloning tier (Qwen3-TTS with the engine stopped, as training is); every line an `audio` asset placed on its Flow line.
    `tier` is stamped from the voice record at submission and checked against it (the queue stops the engine by it)."""
    kind: Literal["tts"] = "tts"
    voice_id: str
    tier: Literal["draft", "cloning"] = "draft"
    language: str = "English"
    speed: float = Field(1.0, ge=0.5, le=2.0)     # the draft tier's pace (Kokoro); the cloning tier speaks at its own
    items: list[TtsItem] = Field(min_length=1)
    seeds: list[int] = Field(default_factory=lambda: [0])   # one job (the queue's seed loop)


class Keypoints(BaseModel):
    """CA1b (D104): the body keypoints of one image (SDPose wholebody on RT-DETR's person boxes) — the measure a figure is fitted to its
    character by. The result is the people found (OpenPose-style JSON) on the job; with origin surface `body_fit` the finisher fits the Cast
    version's body to them."""
    kind: Literal["keypoints"] = "keypoints"
    asset_id: str
    model_id: str = _default("keypoints")


class MatteSequence(BaseModel):
    """D111 (PS5d): a character layer's matte — SAM 3 by text on every frame of its performance (E22 / E23b), or under `open` (SAM 3's
    licence is gated, full only) BiRefNet's subject matte (MIT) — the layer is one character on a plain ground; the masks into the
    layer's `matte/` (the assembly keeps them inside the figure's Stage mask)."""
    kind: Literal["matte_sequence"] = "matte_sequence"
    final_id: str
    layer_id: str
    mode: Literal["text", "subject"] = "text"
    text: str = "person"
    threshold: float = Field(0.4, ge=0.05, le=0.95)
    seeds: list[int] = Field(default_factory=lambda: [0])

    @property
    def model_id(self) -> str:
        """SAM 3 (the spec that runs AI Select by text), or the subject matte."""
        return registry.segment_model(self.mode)


def matte_mode(variant: str) -> Literal["text", "subject"]:
    """D111 (PS5d): SAM 3 by text where this build offers it (E23b's measured route), else the subject matte (`open`)."""
    return "text" if registry.offered(registry.get(registry.segment_model("text")), variant) else "subject"


class AssembleFinal(BaseModel):
    """D111 (PS5e): the final's layers composited into the shot — a CPU job (final_assembly.py) that becomes a clip."""
    kind: Literal["assemble_final"] = "assemble_final"
    final_id: str
    seeds: list[int] = Field(default_factory=lambda: [0])


class RenderSettings(BaseModel):
    """AE5 (03 §AE5): the finished shot's render settings and output modules — EffectCraft's render queue item (quality, resolution, motion
    blur, frame blending, the working colour depth; proxies never used) and what is written: the PNG master always (the take's clip, its
    H.264 proxy beside it), with its alpha kept (straight) or not, and a ProRes 4444 beside it on request. The defaults are AE1's render."""
    quality: Literal["best", "draft"] = "best"
    resolution: Literal["full", "half", "third", "quarter"] = "full"
    motion_blur: Literal["comp", "off"] = "comp"           # as the composition's switches (the layers that ask for it), or off for all
    frame_blending: Literal["comp", "off"] = "comp"
    depth: Literal[8, 16, 32] = 8                          # bits per channel while compositing; the PNG master is 8-bit, the ProRes 12-bit
    alpha: bool = False                                    # the master and the ProRes keep the alpha (where the layers leave the frame open)
    prores: bool = False                                   # a ProRes 4444 beside the master, at the master's rate (24 fps after RIFE at F16)


class CompRender(BaseModel):
    """AE1 (proto01_animate 20 §2, D114): the finished shot — the final's composition rendered by the pinned `effectcraft-cli` (a PNG
    sequence, on the CPU) into a clip: the final's clip, and a take on its Story shot. AE5: with the final's render settings."""
    kind: Literal["comp_render"] = "comp_render"
    final_id: str
    settings: RenderSettings = Field(default_factory=RenderSettings)
    seeds: list[int] = Field(default_factory=lambda: [0])


LayerPassPreset = Literal["cleanup", "creative", "face", "lipsync"]


class PassStep(BaseModel):
    """D118 (AE4c): where a chained pass stands — the face pass is several engine jobs on one take: for Lip-sync the S2V talking head per
    line window (`face_video`, k = the window), then Wan Animate on the head crop in 77-frame batches (`head`, k = the batch); the last
    batch's finisher pastes the heads back and records the take. The route sets the first step; each finisher queues the next."""
    take_id: str
    stage: Literal["face_video", "head", "mouth"] = "head"     # AE4d: `mouth` — the lip-sync model on the rendered heads, the engine stopped
    k: int = Field(0, ge=0, le=400)


class LayerPass(BaseModel):
    """D118 (AE4a): a pass on a final's layer — its frames through a video model, the result a *take* the layer shows as its source (the
    original kept, switchable). `cleanup`: Wan 2.2's low-noise expert over the clip at a low strength (E24 A2 — the author saw the hands
    improve); `creative`: LTX-2.3 locked to the layer's Stage depth (E24 C3 — a repaint, for creative upgrades). AE4c (E29b): `face` — the
    head tracked from the layer's keypoints, rendered at 512² by Wan Animate from the reference's head and the pose crop, matted, pasted
    back grown and feathered (a sharp, recognisable face; `strength` unused); `lipsync` — the face pass with the lines attached to the
    layer: an S2V talking head of the reference per line window as Animate's face video. `model_id` is this step's model (the S2V spec for
    a `face_video` step, else the pass's video model), picked by the route and the finisher for the preset."""
    kind: Literal["layer_pass"] = "layer_pass"
    final_id: str
    layer_id: str
    preset: LayerPassPreset = "cleanup"
    strength: float = Field(0.10, ge=0.02, le=0.9)
    model_id: str
    step: PassStep | None = None                  # AE4c: the face pass's chain position (required for face / lipsync)
    mouth: Literal["head", "model"] = "head"      # AE4d (lipsync): the mouth by the S2V talking head as Animate's face video, or redrawn by the lip-sync model
    scope: Literal["layer", "below"] = "layer"    # AE4e: the layer's own frames, or the stack from this layer down flattened — a processing layer
    seeds: list[int] = Field(default_factory=lambda: [0])

    @model_validator(mode="after")
    def _face_has_step(self) -> "LayerPass":
        if self.preset in ("face", "lipsync") and self.step is None:
            raise ValueError("the face pass runs in steps: give it its first step (the route does)")
        if self.preset not in ("face", "lipsync") and self.step is not None:
            raise ValueError(f"the {self.preset} pass runs in one job: no step")
        if self.scope == "below" and self.preset in ("face", "lipsync"):
            raise ValueError("the face pass runs on a character layer, not over the stack below")
        return self


Recipe = Annotated[Union[T2I, I2I, Inpaint, Upscale, Segment, I2V, Reangle, Render, StageShot, ImageToMesh, ImageToSet, TrainLora, TTS, Keypoints, MatteSequence, AssembleFinal, CompRender, LayerPass],
                   Field(discriminator="kind")]
AnyRecipe = T2I | I2I | Inpaint | Upscale | Segment | I2V | Reangle | Render | StageShot | ImageToMesh | ImageToSet | TrainLora | TTS | Keypoints | MatteSequence | AssembleFinal | CompRender | LayerPass


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
    if isinstance(recipe, StageShot):
        return stage_model_id(recipe, variant)     # ST3: the model the Stage method runs in this build
    if isinstance(recipe, (Render, AssembleFinal, CompRender)):
        return "cpu"                               # P17: the draft render never touches the engine; D111: nor the final's assembly
    if isinstance(recipe, TrainLora):
        return "trainer"                           # LT2: the engine is stopped for it; no weights of the engine's stay warm
    if isinstance(recipe, TTS):
        return "voices"                            # CN2: the runner in its own venv; the cloning tier stops the engine
    return recipe.model_id
