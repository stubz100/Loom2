"""Stages (P13 / ST1, 16 §12): a 3D blocking as a document `stages/<id>.json` — objects (figures, sets, props, image planes, meshes)
with transforms and poses, cameras in photographic units (focal mm on a 36 mm sensor), keyframes (ST4) and the passes rendered from
a camera (ST3) — assets by id, never embedded. Writes go through fsio; `revision` guards a PUT like a document's stack (409 on a
stale base). The frontend's engine (suites/stage/) renders from this document and never keeps project data of its own.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

STAGE_SCHEMA_VERSION = 1
Kind = Literal["mannequin", "set", "prop", "plane", "mesh", "light"]


class StaleStage(ValueError):
    """A PUT based on an older revision than the document's (the API answers 409; the client reloads and re-applies)."""


class Transform(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    pos: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rot: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])      # degrees, yaw pitch roll as the Inspector shows them (Y X Z)
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])


class Pose(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    preset: str | None = None
    joints: dict[str, list[float]] = Field(default_factory=dict)         # joint name → [x, y, z] degrees (ST2 edits them; ST1 keeps presets)


class StageObject(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    kind: Kind
    name: str
    preset: str | None = None                      # mannequin: adult | child; set: room | street | deck | empty; prop: crate | stool | …
    asset_id: str | None = None                    # plane: the Catalogue image; mesh: the GLB asset (P18)
    transform: Transform = Field(default_factory=Transform)
    parent: str | None = None
    locked: bool = False
    visible: bool = True
    colour_id: int = 0                             # the object-ID mask colour (ST3)
    pose: Pose | None = None                       # figures
    billboard: bool = True                         # planes face the camera


class StageCamera(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    name: str = "Camera"
    pos: list[float] = Field(default_factory=lambda: [0.0, 1.5, 4.0])
    target: list[float] = Field(default_factory=lambda: [0.0, 1.0, 0.0])
    roll: float = 0.0
    focal_mm: float = 35.0
    sensor_mm: float = 36.0                        # D81: full-frame horizontal


class StageRange(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    start: int = 0
    end: int = 120


class Stage(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = STAGE_SCHEMA_VERSION
    id: str
    name: str = "Stage"
    size: dict[str, int] = Field(default_factory=lambda: {"w": 1920, "h": 1080, "fps": 24})   # from the project format (D18)
    objects: list[StageObject] = Field(default_factory=list)
    cameras: list[StageCamera] = Field(default_factory=list)
    active_camera: str | None = None
    keyframes: dict[str, Any] = Field(default_factory=lambda: {"camera": {}, "objects": {}})  # ST4
    range: StageRange = Field(default_factory=StageRange)
    passes: list[dict[str, Any]] = Field(default_factory=list)                                 # ST3: {camera_id, revision, size, assets, keypoints, legend, rendered_at}
    group_id: str | None = None                                                                # ST3: the album page the passes and shots are placed on (server-set)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


def check(st: Stage) -> None:
    """The invariants a saved document keeps: unique ids, parents that exist and never cycle, the active camera present, a 36 mm
    sensor is the default but any positive one is allowed, focal lengths in the lens range."""
    ids = [o.id for o in st.objects]
    if len(set(ids)) != len(ids):
        raise ValueError("object ids must be unique")
    by = {o.id: o for o in st.objects}
    for o in st.objects:
        seen = {o.id}
        p = o.parent
        while p:
            if p not in by:
                raise ValueError(f"object {o.id}: parent {p} is not in the stage")
            if p in seen:
                raise ValueError(f"object {o.id}: parents form a cycle")
            seen.add(p)
            p = by[p].parent
        if len(o.transform.pos) != 3 or len(o.transform.rot) != 3 or len(o.transform.scale) != 3:
            raise ValueError(f"object {o.id}: a transform has three components each")
    cids = [c.id for c in st.cameras]
    if len(set(cids)) != len(cids):
        raise ValueError("camera ids must be unique")
    if st.active_camera is not None and st.active_camera not in cids:
        raise ValueError(f"active camera {st.active_camera} is not in the stage")
    for c in st.cameras:
        if not (4.0 <= c.focal_mm <= 1200.0) or c.sensor_mm <= 0:
            raise ValueError(f"camera {c.id}: focal {c.focal_mm} mm on a {c.sensor_mm} mm sensor is out of range")
    if st.size.get("w", 0) <= 0 or st.size.get("h", 0) <= 0 or st.size.get("fps", 0) <= 0:
        raise ValueError("size needs positive w, h and fps")


class StageStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.stages_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, st_id: str) -> Path:
        return self.dir / f"{st_id}.json"

    def get(self, st_id: str) -> Stage | None:
        p = self.path(st_id)
        return Stage.model_validate(read_json(p)) if p.is_file() else None

    def list(self) -> list[Stage]:
        out = [Stage.model_validate(read_json(p)) for p in self.dir.glob("stg_*.json")]
        return sorted(out, key=lambda t: t.updated_at, reverse=True)

    def save(self, st: Stage) -> None:
        atomic_write_json(self.path(st.id), st.model_dump())

    def create(self, name: str = "Stage", size: dict[str, int] | None = None) -> Stage:
        """A new stage with one camera (35 mm, eye level) looking at the origin — a shot is always framed by something."""
        cam = StageCamera(id=new_id("cam"), name="Camera 1")
        st = Stage(id=new_id("stg"), name=name.strip() or "Stage", size=size or {"w": 1920, "h": 1080, "fps": 24}, cameras=[cam], active_camera=cam.id)
        self.save(st)
        return st

    def put(self, st_id: str, data: dict[str, Any]) -> Stage:
        """Replace the document from a client body based on `revision` (409 when stale); id, schema and timestamps are the server's."""
        cur = self.get(st_id)
        if cur is None:
            raise KeyError(st_id)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleStage(f"the stage is at revision {cur.revision}, the change is based on {base} — reload it first")
        keep = ("name", "size", "objects", "cameras", "active_camera", "keyframes", "range", "passes")
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in keep}, "id": st_id, "schema_version": STAGE_SCHEMA_VERSION,
                  "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        st = Stage.model_validate(merged)
        check(st)
        self.save(st)
        return st

    def set_passes(self, st_id: str, entry: dict[str, Any], group_id: str | None) -> Stage:
        """ST3: record the passes rendered for one camera (replacing that camera's earlier entry) and the stage's album page; a server-side
        change, so the revision moves — the client takes the returned document."""
        cur = self.get(st_id)
        if cur is None:
            raise KeyError(st_id)
        passes = [p for p in cur.passes if p.get("camera_id") != entry.get("camera_id")] + [entry]
        st = cur.model_copy(update={"passes": passes, "group_id": group_id or cur.group_id, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save(st)
        return st

    def set_guide(self, st_id: str, camera_id: str, kind: str, guide: dict[str, Any], group_id: str | None) -> Stage:
        """ST4: record a camera's rendered pass sequence under its passes entry (`guides[kind]`), making the entry when the stills were
        never rendered; the revision moves like set_passes."""
        cur = self.get(st_id)
        if cur is None:
            raise KeyError(st_id)
        passes = [dict(p) for p in cur.passes]
        entry = next((p for p in passes if p.get("camera_id") == camera_id), None)
        if entry is None:
            entry = {"camera_id": camera_id, "revision": guide.get("revision", cur.revision), "size": guide.get("size"), "assets": {}, "keypoints": [], "legend": {}}
            passes.append(entry)
        entry.setdefault("guides", {})[kind] = guide
        st = cur.model_copy(update={"passes": passes, "group_id": group_id or cur.group_id, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save(st)
        return st

    def delete(self, st_id: str) -> bool:
        p = self.path(st_id)
        if not p.is_file():
            return False
        p.unlink()
        return True


def encode_guide(frames: list[Path], out: Path, fps: int) -> None:
    """ST4: the per-frame PNGs as one near-lossless h264 (crf 10, yuv420p — the E11 guide encoding); odd sizes lose a row / column."""
    import av
    import numpy as np
    from PIL import Image

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.mp4")
    with Image.open(frames[0]) as im:
        w, h = im.size
    w, h = w - w % 2, h - h % 2
    with av.open(str(tmp), "w", format="mp4", options={"movflags": "+faststart"}) as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
        stream.options = {"crf": "10", "preset": "veryfast", "g": "24"}
        for i, f in enumerate(frames):
            with Image.open(f) as im:
                arr = np.ascontiguousarray(np.asarray(im.convert("RGB"))[:h, :w])
            vf = av.VideoFrame.from_ndarray(arr, format="rgb24")
            vf.pts = i
            for pkt in stream.encode(vf):
                container.mux(pkt)
        for pkt in stream.encode():
            container.mux(pkt)
    tmp.replace(out)
