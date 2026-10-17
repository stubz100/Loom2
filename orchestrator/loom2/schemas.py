"""Response models for the HTTP API (D38). They exist so `openapi.json` describes what each route returns and the frontend's
`schema.d.ts` types replace the hand-written mirrors in `types.ts`.

Records that already are pydantic models (`AssetRecord`, `JobRecord`, `ClipRecord`, `Document`, `GroupRecord`, `Settings`, …) are
reused. Composite replies that the routes build as dicts get models here with `extra="allow"`: FastAPI filters a response to its
model's fields, so a field added to a dict but not yet to its model still reaches the client instead of vanishing.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, WithJsonSchema

from .catalogue import AssetRecord
from .clips import IDENTITY_SCHEMA, ClipRecord
from .documents import Document
from .timelines import Timeline
from .stages import Stage
from .story import FlowGraph, FlowNode, Profile, Shot
from .library import Library, LibraryEntry
from .groups import GroupRecord
from .queue import JobRecord
from .recipes import RefineEdge
from .roster import RosterEntry
from .workspace import ProjectFormat


from .origin import JobOrigin
from .models.spec import Geometry, Inputs, Recipes, VideoPreset

class Out(BaseModel):
    """A strict reply: every field is always present (required in the schema)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Open(BaseModel):
    """A composite reply: declared fields are typed, any other field passes through, and a field with a default may be absent
    (routes that build these dicts sparsely use `response_model_exclude_unset`, so the reply keeps its shape)."""
    model_config = ConfigDict(extra="allow", json_schema_serialization_defaults_required=False)


# ---- meta ------------------------------------------------------------------------------------------------------------
class HealthInfo(Open):
    ok: bool
    version: str
    project_open: bool
    engine_running: bool
    variant: Literal["full", "open"]
    start_suite: str | None = None
    session_id: str | None = None


class GitInfo(Open):
    sha: str
    dirty: bool
    describe: str | None = None


class ShellBuild(Open):
    version: str
    git_sha: str | None = None
    build_time: str | None = None


class EngineVersion(Open):
    """ComfyUI's `/system_stats` `system` block."""
    comfyui_version: str | None = None
    pytorch_version: str | None = None
    python_version: str | None = None


class EnginePin(Open):
    pin: str | None = None
    running: EngineVersion | None = None


class NodePin(Open):
    name: str
    repo: str
    commit: str
    date: str


class StatePaths(Open):
    state: str
    logs: str
    models_root: str


class VersionInfo(Open):
    app: str
    orchestrator: str
    variant: Literal["full", "open"]
    git: GitInfo | None = None
    shell: ShellBuild | None = None
    engine: EnginePin
    nodes: list[NodePin]
    schemas: dict[str, int]
    paths: StatePaths


class TeOption(Open):
    id: str
    label: str
    name: str
    health: str
    approx_gb: float | None = None
    gguf: bool
    default: bool


class ImageModelCaps(Open):
    family: str
    base: str | None = None                       # LT2 (18 §3b): the adapter base this model takes LoRAs for
    label: str
    health: str
    steps: int
    guidance: float
    cfg: float
    distilled: bool
    turbo: bool
    turbo_steps: int
    json_prompt: bool
    max_refs: int
    sampler: str
    scheduler: str
    vram_gb: float | None = None
    wired: bool
    license: str
    variants: list[str]
    te_id: str | None = None
    te_options: list[TeOption] = []
    recipes: Recipes                               # D65: what the model runs — the panels gate their controls on these
    inputs: Inputs
    geometry: Geometry
    short: str
    hint: str | None = None
    order: int
    cfg_fixed: bool
    cfg_note: str | None = None
    model_shift: float | None = None
    guidance_node: bool                            # D89: FluxGuidance in the graph — the Guidance field is shown only then
    tiled_refine: bool                             # D89: the model refines tiles after an upscale (the FLUX.2 family's i2i models)
    flux_shift: bool                               # D90 (B12): ModelSamplingFlux in the graph — a recipe's base / max shift applies only then


class I2vModelCaps(Open):
    family: str
    label: str
    health: str
    missing: list[str]
    fps: int
    frames: int
    frame_step: int
    size_mult: int
    size: tuple[int, int]
    presets: dict[str, str]
    beats: bool
    flf: bool
    vram_gb: float | None = None
    license: str
    approx_gb: float
    preset_params: dict[str, VideoPreset]
    recipes: Recipes
    inputs: Inputs
    geometry: Geometry
    short: str
    hint: str | None = None
    order: int


class ToolCaps(Open):
    """D65: an Edit tool (an upscaler, an AI Select model) from the registry."""
    family: str
    label: str
    graph: str
    health: str
    vram_gb: float | None = None
    license: str
    recipes: Recipes
    inputs: Inputs
    geometry: Geometry
    short: str
    hint: str | None = None
    order: int


class I2vCaps(Open):
    models: dict[str, I2vModelCaps]
    tiers: dict[str, dict[str, tuple[int, int]]]
    portrait: dict[str, tuple[int, int]]
    square: dict[str, tuple[int, int]]


class FaceSimCaps(Open):
    available: bool
    dir: str


class AdvancedCaps(Open):
    model_shift: dict[str, float]
    shift_node_defaults: dict[str, float]
    tile_size_default: int
    flux2_schedule: str


class RefineEdgeCaps(Open):
    """D45: Refine Edge defaults (what the worker runs when a field is left out) and slider ranges [min, max, step]."""
    defaults: RefineEdge
    ranges: dict[str, list[float]]


class ContentAwareCaps(Open):
    """D62: whether the native extension (PhotoCraft's content-aware fill + PatchMatch) is installed, and the modes it enables."""
    available: bool
    modes: list[str]


class SessionInfo(Out):
    """D67: the per-launch read-only media key (`?k=` on media URLs) and the session id."""
    session_id: str
    media_key: str


class ReangleMethodCaps(Open):
    """P14 (D82): one angles method — the model it runs, its health, measured seconds and the moves it is good for."""
    model_id: str
    label: str
    short: str
    hint: str | None = None
    health: str
    missing: list[str]
    seconds: float | None = None
    moves: list[str]
    approx_gb: float


class ReangleCaps(Open):
    moves: list[str]
    methods: dict[str, ReangleMethodCaps]
    auto: dict[str, str]                           # move → the method `auto` picks


class StageMethodCaps(Open):
    """P13 ST3 (D78): one Stage → image method — the model it runs, its health, E10's seconds, the pass it takes and the references it allows."""
    model_id: str
    label: str
    short: str
    hint: str | None = None
    health: str
    missing: list[str]
    seconds: float | None = None
    measured: bool
    image1: str                                    # the pass that is image 1: clay | pose
    max_refs: int                                  # references after image 1
    approx_gb: float


class StageClipCaps(Open):
    """P13 ST4 (D76): the video model that animates a stage through its IC-LoRA — health, E11's seconds, the guide kinds, its grid."""
    model_id: str
    label: str
    health: str
    missing: list[str]
    seconds: float | None = None
    kinds: list[str]
    fps: int | None = None
    frame_step: int | None = None
    size: list[int]
    approx_gb: float


class StageAnimateCaps(StageClipCaps):
    """CN4: Wan2.2 Animate on the pose pass — one window (`frames_max`), one figure per pass (`figures_max`)."""
    frames_max: int | None = None
    figures_max: int | None = None


class StageCaps(Open):
    methods: dict[str, StageMethodCaps]
    passes: list[str]
    default: str | None = None
    clip: StageClipCaps | None = None
    animate: StageAnimateCaps | None = None        # CN4 (D87, E19): the pose-driven clip method


class StoryPresetCaps(Out):
    label: str
    hint: str
    cells: int


class StoryCaps(Open):
    """17 §3b (D85): the model Expand runs on in this build, its health and warm seconds, the presets with their cell counts, the coverage vocabulary."""
    model_id: str | None = None
    label: str | None = None
    short: str | None = None
    health: str
    missing: list[str]
    seconds: float | None = None
    presets: dict[str, StoryPresetCaps]
    coverage: dict[str, list[str]]


class MeshCaps(Open):
    """P18 (D84): the image → mesh model of this build, or why there is none."""
    model_id: str | None = None
    label: str | None = None
    short: str | None = None
    hint: str | None = None
    health: str
    missing: list[str]
    seconds: float | None = None
    cold_seconds: float | None = None
    resolutions: list[int]
    faces: int
    licences: dict[str, str]
    approx_gb: float
    why: str | None = None


class SampleModelCaps(Open):
    """D91: a model Settings › Samples may pick for the style samples and the preset swatches (the default first)."""
    id: str
    label: str
    short: str
    health: str                                    # every weight it loads: verified · present · missing
    missing: list[str]
    default: bool                                  # the default swatch model (the setting's None)
    style_px: int                                  # the style sample's square size
    swatch_px: int                                 # a preset swatch's square size
    license: str
    seconds: float | None = None                   # the spec's Draft estimate (the rig's warm figure once measured)


class Capabilities(Open):
    recipes: list[str]
    i2v: I2vCaps
    models: dict[str, ImageModelCaps]
    tools: dict[str, ToolCaps]
    defaults: dict[str, str]                       # D65: the default model per recipe kind
    sample_models: list[SampleModelCaps] = []      # D91: Settings › Samples' choices, the default first
    facesim: FaceSimCaps
    variant: str
    vram_budget_gb: float
    samplers: list[str]
    schedulers: list[str]
    weight_dtypes: list[str]
    te_devices: list[str]
    te_alternates: dict[str, list[str]]
    advanced: AdvancedCaps
    tiers: dict[str, dict[str, tuple[int, int]]]
    refine_edge: RefineEdgeCaps
    content_aware: ContentAwareCaps
    reangle: ReangleCaps                           # P14 (D82)
    stage: StageCaps                               # P13 ST3 (D78)
    mesh: MeshCaps                                 # P18 (D84)
    story: StoryCaps | None = None                # 17 (D85): the Cast tab's Expand model and presets
    train: TrainCaps | None = None                # 18 (D86): the LoRA trainer's bases and ranges
    voice: VoiceCaps | None = None                # 19 (D87) CN2: the TTS tiers, their voices and languages
    experimental: ExperimentalCaps | None = None  # D88: extend and lip-sync, marked experimental


class MissingWeight(Open):
    model_id: str
    health: str
    approx_gb: float | None = None


class Estimate(Open):
    seconds: float | None = None
    source: str
    vram_gb: float | None = None
    vram_budget_gb: float | None = None
    vram_fit: Literal["ok", "tight", "over"] | None = None


class RefOut(Out):
    asset_id: str | None = None
    blob: str | None = None
    note: str | None = None
    mention: str | None = None


class MentionOut(Out):
    group_id: str
    name: str | None = None
    revision: int | None = None
    asset_ids: list[str] = []
    profile_id: str | None = None                 # D85: a Story profile mention — the version's group was swapped in
    version: str | None = None
    lora: str | None = None                       # LT3: the version's LoRA the mention added to the slots
    lora_available: str | None = None             # LT3: the version's LoRA, added or not (the chip's on / off)


class T2IPreview(Open):
    """`POST /recipes/preview` for a t2i recipe: the effective parameters, the exact serialised prompt, missing weights, ETA."""
    serialized_prompt: str
    prompt_mode: str
    width: int
    height: int
    steps: int
    guidance: float | None                         # D89: None on a family without FluxGuidance (nothing to show)
    cfg: float
    sampler: str
    scheduler: str
    turbo: bool
    distilled: bool
    word_count: int
    token_estimate: int
    refs: int
    max_refs: int
    refs_dropped: int = 0                         # D73: references over the model's limit — left out, and the panel says so
    ref_notes: int = 0                            # D73: kept references whose note went into the prompt
    ref_list: list[RefOut] = []                   # D73: the kept references in order (explicit, then those the mentions gave)
    mentions: list[MentionOut] = []               # D73: the mentions, resolved and stamped
    style_id: str | None = None                   # D85: the Story style carried, and the fragment appended after the prompt
    style_text: str | None = None
    model_id: str
    te_id: str
    negative_used: bool
    turbo_strength: float | None = None
    weight_dtype: str
    te_device: str
    base_shift: float | None = None
    max_shift: float | None = None
    tiled_vae: bool
    tile_size: int | None = None
    loras: list[dict[str, Any]] = []
    missing: list[MissingWeight]
    estimate: Estimate
    count: int
    problems: list[str] | None = None             # D64: the contract check on placeholder inputs (None before the engine answered once)
    weights: list[str] = []
    warm_group: str | None = None


class I2VPreview(Open):
    """`POST /recipes/preview` for an i2v recipe: snapped size and frames, the preset that runs, missing weights, ETA."""
    family: str
    width: int
    height: int
    frames: int
    fps: int
    steps: int
    label: str
    flf: bool
    beats: int
    missing: list[MissingWeight]
    estimate: Estimate
    count: int
    problems: list[str] | None = None             # D64: the contract check on placeholder inputs (None before the engine answered once)
    weights: list[str] = []
    warm_group: str | None = None


class DocumentPreview(Open):
    """`POST /recipes/preview` for an Edit recipe (inpaint, i2i, upscale, segment — D64): the settings that shape the run, what it needs,
    the weights, ETA and VRAM fit, and the contract problems a submission would hit. The region is read at run time, not here."""
    kind: str
    model_id: str | None = None
    engine: bool
    params: dict[str, Any]
    needs: list[str]
    missing: list[MissingWeight]
    estimate: Estimate
    count: int
    problems: list[str] | None = None             # D64: the contract check on placeholder inputs (None before the engine answered once)
    weights: list[str] = []
    warm_group: str | None = None


# ---- projects --------------------------------------------------------------------------------------------------------
class ProjectInfo(Open):
    open: bool
    path: str | None = None
    id: str | None = None
    name: str | None = None
    format: ProjectFormat | None = None
    size_cap_gb: float | None = None
    free_space_gb: float | None = None
    created_at: str | None = None
    assets: int | None = None
    usage_gb: float | None = None
    jobs_indexed: int | None = None


class Recents(Out):
    last: str | None = None
    recents: list[str]


# ---- assets, lineage, groups -----------------------------------------------------------------------------------------
class AssetList(Out):
    items: list[AssetRecord]


class TagCount(Out):
    tag: str
    count: int


class TagList(Out):
    items: list[TagCount]


class Trashed(Out):
    trashed: list[str]


class Restored(Out):
    restored: list[str]


class Purged(Out):
    purged: int
    ids: list[str]


class IdsReply(Out):
    ids: list[str]


class Deleted(Out):
    deleted: str


class LineageEdge(Open):
    from_id: str
    to_id: str
    via_job: str | None = None
    kind: str


class Lineage(Out):
    id: str
    root_id: str | None = None
    parents: list[LineageEdge]
    children: list[LineageEdge]


class PathStep(Out):
    id: str
    name: str


class Location(Out):
    group_id: str
    path: list[PathStep]


class LineageTree(Out):
    root_id: str
    items: list[AssetRecord]
    edges: list[LineageEdge]
    locations: dict[str, Location | None]


class RebuildReply(Out):
    indexed: int


class GroupSummary(Out):
    id: str
    name: str
    assets: int
    groups: int
    total: int
    cover_ids: list[str]
    revision: int


class AlbumNode(GroupSummary):
    children: list[AlbumNode]


class GroupPage(Out):
    group: GroupRecord
    path: list[PathStep]
    assets: dict[str, AssetRecord]
    groups: dict[str, GroupSummary]


class ChangedGroups(Out):
    changed: list[str]


class GroupDeleted(Out):
    deleted: str
    unprocessed: list[str]


class LayoutReply(Out):
    revision: int


class Ungrouped(Out):
    parent: str


# ---- documents -------------------------------------------------------------------------------------------------------
class DocSummary(Open):
    id: str
    name: str
    w: int | None = None
    h: int | None = None
    saved_at: str | None = None
    source_asset_id: str | None = None
    layers: int
    path: str
    open: bool
    dirty: bool = False


class DocList(Out):
    items: list[DocSummary]


class DocumentPutReply(Document):
    """The stack as stored plus the layers / masks the server has no bytes for (B15)."""
    missing_pixels: list[str]
    missing_masks: list[str]


class PixelsPut(Out):
    layer: str
    kind: Literal["image", "mask"]
    w: int
    h: int


class FlattenedToCatalogue(Out):
    asset: AssetRecord


class FlattenedToFile(Out):
    path: str


class CompareReply(Open):
    mean: float
    p99: float
    max: float
    rgb_mean: float
    rgb_p99: float
    rgb_max: float
    w: int
    h: int
    at: str


class SelectionReply(Out):
    selection: list[int] | None = None


class RefineReply(Out):
    """D45: the refined selection is stored on the document; fetch it with GET /documents/{id}/selection."""
    selection: list[int]
    coverage: float
    ms: int


class Closed(Out):
    closed: str


# ---- clips -----------------------------------------------------------------------------------------------------------
class ClipList(Out):
    items: list[ClipRecord]


class TimelineList(Out):
    """P17 (D83): the project's sequences."""
    items: list[Timeline]


class ProfileList(Out):
    items: list[Profile]


class ShotList(Out):
    items: list[Shot]


class FlowOut(Out):
    """17 §3d: the index and every node."""
    graph: FlowGraph
    nodes: list[FlowNode]


class FlowProblem(Out):
    code: str
    node_id: str | None = None
    message: str


class FlowProblems(Out):
    problems: list[FlowProblem]


class NodeShot(Out):
    """A bind / unbind / spawn: the node and the shot it now owns (or released)."""
    node: FlowNode
    shot: Shot | None = None


class LibraryChange(Out):
    """D92: an entry added or edited — the library at its new revision and the entry."""
    library: Library
    entry: LibraryEntry


class LibraryRemoved(Out):
    """D92: an entry removed — the library at its new revision, the entry and where it stood (the Undo puts it back there)."""
    library: Library
    entry: LibraryEntry
    index: int


class Expanded(Out):
    """17 §3b: the jobs an Expand queued — one per cell, one batch — and the candidates page they land on."""
    batch_id: str
    job_ids: list[str]
    cells: int
    group_id: str
    model_id: str


class Curated(Out):
    kept: list[str]
    rejected: list[str]


class StageList(Out):
    """P13 / ST1 (D81): the project's stages."""
    items: list[Stage]


class TimelineExported(Out):
    """P17: an export written from the sequence document — the file inside the project and its text; `audio` (CN2) the spoken lines the
    FCPXML / EDL carry on their audio lane."""
    format: str
    path: str
    text: str
    audio: int = 0


class ClipExtracted(Out):
    items: list[AssetRecord]
    clip: ClipRecord


# ---- jobs and queue --------------------------------------------------------------------------------------------------
class JobList(Out):
    items: list[JobRecord]


class ExtendQueued(Out):
    """D88 XE (experimental): the continuation's job, its start (the clip's last frame, extracted) and the lead-in it pins."""
    job_id: str
    start_asset_id: str
    lead: int
    model_id: str
    staged: bool


class LipsyncQueued(Out):
    """D88 XL (experimental): the talking clip's job — it lands as a take on the shot version."""
    job_id: str
    model_id: str
    frames: int
    audio_asset_id: str
    image_asset_id: str
    staged: bool
    seconds: float | None = None


class ExperimentalExtendCaps(Open):
    models: dict[str, int]                         # the video models that continue clips → their lead-in frames
    caveat: str


class ExperimentalLipsyncCaps(Open):
    available: bool
    why: str | None = None
    model_id: str | None = None
    label: str | None = None
    health: str | None = None
    missing: list[str] = []
    presets: dict[str, dict[str, Any]] = {}
    frames_max: int | None = None
    fps: int | None = None
    seconds_max: float | None = None
    languages: list[str] = []
    caveat: str


class ExperimentalCaps(Open):
    """D88: features shipped before their bars are met — each with the caveat the UI shows beside its verb."""
    extend: ExperimentalExtendCaps
    lipsync: ExperimentalLipsyncCaps


class JobsSubmitted(Out):
    jobs: list[JobRecord]


class PresetIconPlanned(Out):
    """D90 (02 §6.3): one swatch a make queued — the key its file will have and the job that makes it."""
    key: str
    field: str
    value: str
    job_id: str


class PresetIconsMade(Out):
    batch_id: str | None                           # one batch for a pack of two or more
    items: list[PresetIconPlanned]
    jobs: list[JobRecord]


class Released(Out):
    released: list[str]


class Cancelled(Out):
    cancelled: str


class QueueState(Open):
    paused: bool
    running: str | None = None
    counts: dict[str, int]
    last_warm_group: str | None = None
    resumed_unclean: bool = False
    recovery: list[str] = []


# ---- models, engine, blobs -------------------------------------------------------------------------------------------
class ModelEntry(RosterEntry):
    path: str | None = None
    health: Literal["present", "verified", "missing", "retired"]
    size: int | None = None
    sha256: str | None = None
    source_tree: str | None = None


class FetchState(Open):
    model_id: str
    name: str
    status: str
    error: str | None = None
    bytes_done: int
    bytes_total_est: int
    progress: float | None = None
    elapsed_s: float


class LoraOption(Out):
    """LT1 (18 §3e): one entry of the slots' picker — what the worker would load, and why it would not."""
    id: str                                       # a roster id, `file:<path>` or a trained LoRA's id
    label: str
    source: Literal["roster", "file", "trained"]
    base: str | None = None                       # the model base it fits; None when the file does not declare one
    fits: bool
    why: str | None = None                        # the sentence when it does not fit, or the caveat for a file
    name: str
    size: int | None = None
    license: str | None = None
    health: str | None = None
    preset: str | None = None
    strength: float = 1.0                         # the default strength at use
    trigger: str | None = None                    # LT2: a trained LoRA's trigger word


class LoraRecordOut(Open):
    """LT2 (18 §3a): a trained LoRA of the project."""
    schema_version: int
    id: str
    name: str
    profile_id: str
    version: str
    base: str
    model_id: str
    trigger: str
    steps: int
    rank: int
    resolution: int
    lr: float
    seed: int
    dataset: dict[str, Any]
    job_id: str | None = None
    sha256: str
    size: int
    created_at: str
    measured: dict[str, Any]
    identity: dict[str, Any] | None = None
    previous: list[str]


class LoraRecordList(Out):
    items: list[LoraRecordOut]


class LoraCheckQueued(Out):
    """LT3 (18 §3h): the identity check's jobs — with and without the LoRA, the same seeds and sentences."""
    batch_id: str
    job_ids: list[str]
    model_id: str
    group_id: str


class TrainQueued(Out):
    job_id: str
    trigger: str
    model_id: str
    staged: bool


class TrainBaseCaps(Open):
    model_id: str
    label: str
    offload: bool
    vram_gb: float
    s_per_it: float | None = None
    health: str


class TrainCaps(Open):
    """LT2 (18 §4): whether the trainer can run, the bases and E16's figures, the ranges the Cast dialog offers."""
    available: bool
    why: str | None = None
    bases: list[TrainBaseCaps]
    steps: dict[str, int]
    ranks: list[int]
    resolutions: list[int]
    lr: float
    min_refs: int


class VoiceRecordOut(Open):
    """CN2 (19 §3b): a voice of the project (story/voices/): the draft tier's fixed Kokoro voice, or the cloning tier's reference clip with
    its transcript and the consent note."""
    id: str
    name: str
    tier: str
    voice: str | None = None
    language: str
    reference_asset_id: str | None = None
    reference_text: str = ""
    speaker: str = ""
    consent: str = ""
    created_at: str
    updated_at: str
    measured: dict[str, Any] = {}


class VoiceList(Out):
    items: list[VoiceRecordOut]


class TtsQueued(Out):
    """CN2: the voice jobs of a line or of a node's lines — one job per voice."""
    job_ids: list[str]
    lines: int
    voice_ids: list[str]
    staged: bool


class DraftVoice(Open):
    id: str
    label: str


class VoiceTierCaps(Open):
    model: str
    cached: bool
    languages: list[str]
    rtf: float
    load_s: float
    vram_gb: float
    voices: list[DraftVoice] = []
    reference_s: list[float] = []


class VoiceCaps(Open):
    """CN2 (19 §3b): whether the TTS runner can run, the tiers with E20's figures (and whether their models are cached), the draft voices,
    the languages, the pace range."""
    available: bool
    why: str | None = None
    draft: VoiceTierCaps
    cloning: VoiceTierCaps
    speed: dict[str, float]


class LoraChanged(Open):
    id: str
    profile_id: str | None = None
    version: str | None = None
    deleted: bool = False


class LoraListing(Out):
    model_id: str
    base: str | None = None
    items: list[LoraOption]
    max_slots: int


class ModelListing(Out):
    items: list[ModelEntry]
    models_root: str
    scanned_at: float | None = None
    fetches: dict[str, FetchState]


class UnlistedFile(Out):
    folder: str
    name: str
    path: str
    size: int


class IgnoredFile(UnlistedFile):
    reason: str


class UnlistedFiles(Out):
    items: list[UnlistedFile]
    ignored: list[IgnoredFile] = []               # P18 (D84): files loom2 never suggests, with the licence reason


class ModelScan(Out):
    items: list[ModelEntry]
    unlisted: list[UnlistedFile]


class ModelVerify(Out):
    model_id: str
    sha256: str
    matches_ledger: bool | None = None


class EngineState(Open):
    running: bool
    responding: bool | None = None
    pid: int | None = None
    port: int
    started_at: float | None = None
    uptime_s: float | None = None
    jobs_since_start: int
    restarts: int
    last_error: str | None = None
    log: str | None = None
    version: EngineVersion | None = None
    job_object: bool
    vram_free_gb: float | None = None
    vram_total_gb: float | None = None


class Freed(Out):
    freed: bool


class BlobPut(Out):
    sha256: str
    bytes: int


class ShuttingDown(Out):
    shutting_down: bool


# ---- WebSocket events (/events) -------------------------------------------------------------------------------------
# Not validated at runtime (the hub sends dicts); published as OpenAPI components so the frontend's `applyEvent` is typed.
class JobProgress(Out):
    id: str
    progress: float
    text: str
    node: str | None = None


class IdOnly(Out):
    id: str


class CatalogueChanged(Out):
    purged: int


class GroupChanged(Out):
    ids: list[str]


class DocShift(Open):
    """How far an outpaint grew the canvas to the left and top (the editor moves its layers by it)."""
    left: int
    top: int


class DocumentChanged(Open):
    """Every variant carries `id`; AI results add `job_id`, `batch_id`, `added`, `group`, …; AI Select adds `selection`."""
    id: str
    job_id: str | None = None
    batch_id: str | None = None
    added: list[str] | None = None
    group: str | None = None
    w: int | None = None
    h: int | None = None
    selection: bool | None = None
    coverage: float | None = None
    saved_at: str | None = None
    deleted: bool | None = None
    candidate: int | None = None
    shift: DocShift | None = None
    revision: int | None = None


class ClipReady(Open):
    clip_id: str
    asset_id: str
    job_id: str
    frames: int
    fps: float
    w: int
    h: int
    origin: JobOrigin | None = None                 # D66: Animate plays the clip only when it was asked for from the view on screen


class ClipUpdated(Open):
    clip_id: str
    identity: Annotated[dict[str, Any] | None, WithJsonSchema(IDENTITY_SCHEMA)] = None


class ProjectClosed(Out):
    path: str


class Hello(Out):
    version: str
    recent: list[dict[str, Any]]


class _Frame(Out):
    seq: int
    t: float = 0


class JobEvent(_Frame):
    type: Literal["job.created", "job.updated"]
    data: JobRecord


class JobProgressEvent(_Frame):
    type: Literal["job.progress"]
    data: JobProgress


class JobDeletedEvent(_Frame):
    type: Literal["job.deleted"]
    data: IdOnly


class QueueStateEvent(_Frame):
    type: Literal["queue.state"]
    data: QueueState


class EngineStateEvent(_Frame):
    type: Literal["engine.state"]
    data: EngineState


class VramPressure(Out):
    """D69: a GPU job was admitted while the engine had less free VRAM than its reserve + 1 GB — the UI releases hidden GPU stages."""
    job_id: str
    free_gb: float
    threshold_gb: float


class VramPressureEvent(_Frame):
    type: Literal["engine.vram_pressure"]
    data: VramPressure


class AssetEvent(_Frame):
    type: Literal["asset.created", "asset.updated"]
    data: AssetRecord


class AssetDeletedEvent(_Frame):
    type: Literal["asset.deleted"]
    data: IdOnly


class CatalogueChangedEvent(_Frame):
    type: Literal["catalogue.changed"]
    data: CatalogueChanged


class GroupChangedEvent(_Frame):
    type: Literal["group.changed"]
    data: GroupChanged


class DocumentChangedEvent(_Frame):
    type: Literal["document.changed"]
    data: DocumentChanged


class StoryChanged(Out):
    """17 (D85): a Story record moved on the server (`kind`: world; later profile, shot, node) — open tabs reload it."""
    kind: str
    revision: int
    id: str | None = None


class StoryChangedEvent(_Frame):
    type: Literal["story.changed"]
    data: StoryChanged


class LoraChangedEvent(_Frame):
    type: Literal["lora.changed"]
    data: LoraChanged


class PresetIconsChanged(Open):
    keys: list[str]                                # D90 (02 §6.3): the swatches made again or deleted — refetch `/preset-icons`
    deleted: bool = False


class PresetIconsChangedEvent(_Frame):
    type: Literal["preset_icons.changed"]
    data: PresetIconsChanged


class ClipReadyEvent(_Frame):
    type: Literal["clip.ready"]
    data: ClipReady


class ClipUpdatedEvent(_Frame):
    type: Literal["clip.updated"]
    data: ClipUpdated


class ModelFetchEvent(_Frame):
    type: Literal["model.fetch"]
    data: FetchState


class ProjectOpenedEvent(_Frame):
    type: Literal["project.opened"]
    data: ProjectInfo


class ProjectClosedEvent(_Frame):
    type: Literal["project.closed"]
    data: ProjectClosed


class HelloEvent(_Frame):
    type: Literal["hello"]
    data: Hello


EVENT_FRAMES = (JobEvent, JobProgressEvent, JobDeletedEvent, QueueStateEvent, EngineStateEvent, AssetEvent, AssetDeletedEvent,
                CatalogueChangedEvent, GroupChangedEvent, DocumentChangedEvent, StoryChangedEvent, LoraChangedEvent, ClipReadyEvent, ClipUpdatedEvent, ModelFetchEvent,
                ProjectOpenedEvent, ProjectClosedEvent, HelloEvent, VramPressureEvent, PresetIconsChangedEvent)
EVENT_TYPES = sorted({t for frame in EVENT_FRAMES for t in frame.model_fields["type"].annotation.__args__})
