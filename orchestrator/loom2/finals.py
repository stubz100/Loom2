"""D111 (PS5, proto01_animate 16): the final shot — a finished Stage scene split into layers and made into the shot. A **final** is a record
`finals/<id>/final.json` with one layer per entity of the scene (the plate, each bound figure, each prop, the shadows) and, beside it, each
layer's passes as PNG sequences at the shot's rate (`finals/<id>/<layer>/<pass>/0000.png …`), rendered by Stage (the client) and uploaded
as content-addressed blobs. Later steps add each layer's own frames (PS5b–c), its mattes (PS5d) and the assembly (PS5e) to the same tree.
Files are truth: the record is written through fsio with its schema version; the folders are the layers.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

FINAL_SCHEMA_VERSION = 1
FINAL_PLATE_SURFACE = "final_plate"               # PS5b: origin.surface of the plate's Stage shot; ref = the final's id
PLATE_LEAD = "The room is empty: there are no people and no objects in it, only the bare walls and floor."   # E28: a plate without the lead grew people
LayerKind = Literal["plate", "figure", "prop", "shadows"]
LayerMethod = Literal["projected", "move", "rendered", "drawn", "stage"]
LayerStatus = Literal["passes", "queued", "running", "done", "failed"]
MAX_FRAMES = 721                                   # 30 s at 24 fps (D96: ≈ 30 s a Shot, a warning beyond)
# the passes each kind of layer brings from Stage (PS5a); a pass with one frame is a still (the plate's frame-0 render)
LAYER_PASSES: dict[str, tuple[str, ...]] = {
    "plate": ("depth", "clay"),                    # the bare set through every frame's camera (its depth: the masks' base; its lit clay: the shadows' base)
    "figure": ("pose", "depth"),                   # the figure alone (with the set): the pose guide, and its depth (its mask against the bare set's)
    "prop": ("beauty", "depth"),                   # the prop alone (with the set): its 3D model rendered (R1), and its depth
    "shadows": ("clay",),                          # everything, lit: the shadows over the bare set's lit clay
}
DEFAULT_METHOD: dict[str, str] = {"plate": "projected", "figure": "move", "prop": "rendered", "shadows": "stage"}


class FinalLayer(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    kind: LayerKind
    name: str
    object_id: str | None = None                   # the Stage object (a figure, a prop); None for the plate and the shadows
    method: LayerMethod
    profile_id: str | None = None                  # a figure's character or a prop's Cast prop (D93, D110), and its version
    version: str | None = None
    passes: dict[str, int] = Field(default_factory=dict)       # pass name → frames on disk
    keypoints: bool = False                        # a figure's per-frame COCO-18 keypoints are in keypoints.json (PS5c: where it starts; D107: its soles)
    status: LayerStatus = "passes"
    error: str | None = None
    still_asset_id: str | None = None              # PS5b: the plate's still (a Klein Stage shot of the bare set at frame 0)
    frames_done: int = 0                           # the layer's own sequence on disk (`frames/`): the projected plate, a character's performance …
    job_ids: list[str] = Field(default_factory=list)   # the jobs that made (or make) the layer


class Final(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = FINAL_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("fin"))
    name: str = "Final"
    stage_id: str
    camera_id: str
    stage_revision: int
    range: dict[str, int]                          # the Stage frames (24 fps) it covers: {start, end}
    rate: Literal[16, 24] = 16                     # D102: F16 (RIFE to 24 at the end) or F24
    size: dict[str, int]                           # the layers' size: {w, h} (the pose-driven model's, Draft first, D18)
    frames: int                                    # frames per sequence at the rate
    shot_id: str | None = None                     # the Story shot it is made for (its take lands there, PS5e)
    layers: list[FinalLayer] = Field(default_factory=list)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


def frames_at(start: int, end: int, rate: int) -> list[float]:
    """The Stage times (in 24 fps frames) a final samples: every frame at F24, every 1.5th at F16 (D102: the motion resampled, not cut)."""
    if end < start:
        return []
    step = 24 / rate
    n = int((end - start) / step + 1e-6) + 1
    return [round(start + i * step, 4) for i in range(n)]


def check(f: Final) -> None:
    if not 2 <= f.frames <= MAX_FRAMES:
        raise ValueError(f"a final has 2 to {MAX_FRAMES} frames (it has {f.frames})")
    if f.size.get("w", 0) < 64 or f.size.get("h", 0) < 64:
        raise ValueError("the layers' size is at least 64 × 64")
    ids = [x.id for x in f.layers]
    if len(set(ids)) != len(ids):
        raise ValueError("layer ids must be unique")
    for kind in ("plate", "shadows"):
        if sum(1 for x in f.layers if x.kind == kind) != 1:
            raise ValueError(f"a final has one {kind} layer")
    for x in f.layers:
        if x.kind in ("figure", "prop") and not x.object_id:
            raise ValueError(f"layer {x.id}: a {x.kind} layer names its Stage object")
        for name in LAYER_PASSES[x.kind]:
            if x.passes.get(name) not in (f.frames,):
                raise ValueError(f"layer {x.id}: its {name} pass has {x.passes.get(name, 0)} frames, the final {f.frames}")


class FinalStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.path / "finals"
        self.dir.mkdir(parents=True, exist_ok=True)

    def folder(self, fid: str) -> Path:
        return self.dir / fid

    def path(self, fid: str) -> Path:
        return self.folder(fid) / "final.json"

    def pass_dir(self, fid: str, layer: str, name: str) -> Path:
        return self.folder(fid) / layer / name

    def get(self, fid: str) -> Final | None:
        p = self.path(fid)
        return Final.model_validate(read_json(p)) if p.is_file() else None

    def list(self, stage_id: str | None = None) -> list[Final]:
        out = [Final.model_validate(read_json(p)) for p in self.dir.glob("fin_*/final.json")]
        return sorted([f for f in out if stage_id is None or f.stage_id == stage_id], key=lambda f: f.created_at, reverse=True)

    def save(self, f: Final) -> None:
        atomic_write_json(self.path(f.id), f.model_dump())

    def create(self, data: dict[str, Any], passes: dict[str, dict[str, list[Path]]], keypoints: dict[str, Any]) -> Final:
        """A final from its record and, per layer and pass, the frame files (blobs, in order; one file may stand for many frames — a still
        camera's identical renders). The folders are written first, the record last: a failed copy leaves no record."""
        f = Final.model_validate({**data, "id": new_id("fin"), "schema_version": FINAL_SCHEMA_VERSION, "revision": 0, "created_at": utc_now(), "updated_at": utc_now()})
        for x in f.layers:
            x.passes = {name: len(files) for name, files in passes.get(x.id, {}).items()}
            x.keypoints = x.id in keypoints
        check(f)
        try:
            for x in f.layers:
                for name, files in passes.get(x.id, {}).items():
                    d = self.pass_dir(f.id, x.id, name)
                    d.mkdir(parents=True, exist_ok=True)
                    for i, src in enumerate(files):
                        shutil.copyfile(src, d / f"{i:04d}.png")
                if x.id in keypoints:
                    atomic_write_json(self.folder(f.id) / x.id / "keypoints.json", {"schema_version": 1, "frames": keypoints[x.id]})
            self.save(f)
        except Exception:
            shutil.rmtree(self.folder(f.id), ignore_errors=True)
            raise
        return f

    def update_layer(self, fid: str, lid: str, **patch: Any) -> Final:
        """One layer's fields changed (its status, still, jobs, frames done); the record's revision moves."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        for k, v in patch.items():
            setattr(layer, k, v)
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    def set_frames(self, fid: str, lid: str, files: list[Path]) -> Final:
        """A layer's own sequence (`frames/`), one file per frame at the final's count; the layer is done."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        if len(files) != f.frames:
            raise ValueError(f"the layer's frames are {len(files)}, the final has {f.frames}")
        d = self.pass_dir(fid, lid, "frames")
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        for i, src in enumerate(files):
            shutil.copyfile(src, d / f"{i:04d}.png")
        return self.update_layer(fid, lid, frames_done=len(files), status="done", error=None)

    def delete(self, fid: str) -> bool:
        d = self.folder(fid)
        if not (d / "final.json").is_file():
            return False
        shutil.rmtree(d)
        return True
