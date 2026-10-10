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
from .groups import GroupRecord
from .queue import JobRecord
from .recipes import RefineEdge
from .roster import RosterEntry
from .workspace import ProjectFormat


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


class Capabilities(Open):
    recipes: list[str]
    i2v: I2vCaps
    models: dict[str, ImageModelCaps]
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


class T2IPreview(Open):
    """`POST /recipes/preview` for a t2i recipe: the effective parameters, the exact serialised prompt, missing weights, ETA."""
    serialized_prompt: str
    prompt_mode: str
    width: int
    height: int
    steps: int
    guidance: float
    cfg: float
    sampler: str
    scheduler: str
    turbo: bool
    distilled: bool
    word_count: int
    token_estimate: int
    refs: int
    max_refs: int
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


class ClipExtracted(Out):
    items: list[AssetRecord]
    clip: ClipRecord


# ---- jobs and queue --------------------------------------------------------------------------------------------------
class JobList(Out):
    items: list[JobRecord]


class JobsSubmitted(Out):
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


class UnlistedFiles(Out):
    items: list[UnlistedFile]


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
                CatalogueChangedEvent, GroupChangedEvent, DocumentChangedEvent, ClipReadyEvent, ClipUpdatedEvent, ModelFetchEvent,
                ProjectOpenedEvent, ProjectClosedEvent, HelloEvent)
EVENT_TYPES = sorted({t for frame in EVENT_FRAMES for t in frame.model_fields["type"].annotation.__args__})
