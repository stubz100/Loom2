"""Clips (06 §4/§5, 11 §10): a rendered video lives in `clips/<clp_id>/` as a **PNG master** (`master/%06d.png`, the exact
frames the engine decoded), an **h264 proxy** (`proxy.mp4`, GOP 6 so Mediabunny seeks any frame in ≈ 10 ms — E6) and
`clip.json`. The proxy is also the Catalogue asset (kind `video`, indexed in place); frame harvesting copies master
frames into the Catalogue as images with `frame-extract` lineage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from .fsio import atomic_move, atomic_write_json, new_id, read_json_or, utc_now
from .workspace import Workspace

# D38: beats and the FaceSim result stay plain dicts at runtime (stored as written); their JSON schemas type them for the frontend.
BEATS_SCHEMA = {"type": "array", "items": {"type": "object", "title": "ClipBeat", "required": ["frame", "asset_id", "strength"],
                                           "properties": {"frame": {"type": "integer"}, "asset_id": {"type": "string"}, "strength": {"type": "number"}}}}
IDENTITY_SCHEMA = {"anyOf": [{"type": "object", "title": "ClipIdentity", "required": ["status"], "additionalProperties": True, "properties": {
    "status": {"type": "string"}, "sampled": {"type": "integer"}, "with_face": {"type": "integer"}, "reference_faces": {"type": "integer"},
    "mean": {"type": "number"}, "min": {"type": "number"}, "min_frame": {"type": "integer"}, "model": {"type": "string"}, "scale": {"type": "string"},
    "per_frame": {"type": "array", "items": {"type": "object", "required": ["frame", "sim", "faces"], "properties": {
        "frame": {"type": "integer"}, "sim": {"anyOf": [{"type": "number"}, {"type": "null"}]}, "faces": {"type": "integer"}}}}}}, {"type": "null"}]}


class ClipRecord(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    schema_version: int = 1
    id: str
    created_at: str = Field(default_factory=utc_now)
    job_id: str | None = None
    batch_id: str | None = None
    asset_id: str | None = None                   # the proxy's Catalogue asset once indexed
    model_id: str
    preset: str = "draft"
    prompt: str = ""
    seed: int = 0
    frames: int
    fps: int
    w: int
    h: int
    start_asset_id: str
    end_asset_id: str | None = None
    beats: Annotated[list[dict[str, Any]], WithJsonSchema(BEATS_SCHEMA)] = Field(default_factory=list)
    master_dir: str                               # project-relative
    proxy_path: str | None = None                 # project-relative, set once encoded
    proxy_bytes: int = 0
    extracted_asset_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    timings: dict[str, Any] = Field(default_factory=dict)
    identity: Annotated[dict[str, Any] | None, WithJsonSchema(IDENTITY_SCHEMA)] = None       # FaceSim advisory (tools/facesim.py), filled after the proxy


class ClipStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws

    def dir(self, clip_id: str) -> Path:
        return self.ws.clips_dir / clip_id

    def json_path(self, clip_id: str) -> Path:
        return self.dir(clip_id) / "clip.json"

    def frame_path(self, clip_id: str, n: int) -> Path:
        return self.dir(clip_id) / "master" / f"{n:06d}.png"

    def get(self, clip_id: str) -> ClipRecord | None:
        data = read_json_or(self.json_path(clip_id), None)
        return ClipRecord.model_validate(data) if data else None

    def list(self) -> list[ClipRecord]:
        out: list[ClipRecord] = []
        if not self.ws.clips_dir.is_dir():
            return out
        for d in self.ws.clips_dir.iterdir():
            rec = self.get(d.name) if d.is_dir() else None
            if rec:
                out.append(rec)
        out.sort(key=lambda r: r.created_at, reverse=True)
        return out

    def save(self, rec: ClipRecord) -> None:
        atomic_write_json(self.json_path(rec.id), rec.model_dump())

    def create(self, frames: list[Path], **fields: Any) -> ClipRecord:
        """Move the engine's decoded frames (in order) into a new clip's master; the size comes from the first frame."""
        from PIL import Image

        if not frames:
            raise ValueError("a clip needs at least one frame")
        clip_id = fields.pop("id", None) or new_id("clp")
        master = self.dir(clip_id) / "master"
        master.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(frames):
            atomic_move(Path(src), master / f"{i:06d}.png")
        with Image.open(master / "000000.png") as im:
            w, h = im.size
        rec = ClipRecord(id=clip_id, frames=len(frames), w=w, h=h, master_dir=master.relative_to(self.ws.path).as_posix(), **fields)
        self.save(rec)
        return rec

    def encode_proxy(self, rec: ClipRecord, *, gop: int = 6, crf: int = 18) -> ClipRecord:
        """h264 yuv420p proxy from the master: a short, fixed GOP keeps random-access decode cheap (E6: GOP 6 ≈ 10 ms
        per seek in Mediabunny); odd sizes lose their last row/column (yuv420p needs even dimensions)."""
        import av
        from PIL import Image

        d = self.dir(rec.id)
        tmp, out = d / "proxy.tmp.mp4", d / "proxy.mp4"
        w, h = rec.w - rec.w % 2, rec.h - rec.h % 2
        with av.open(str(tmp), "w", format="mp4", options={"movflags": "+faststart"}) as container:
            stream = container.add_stream("libx264", rate=rec.fps)
            stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
            stream.options = {"crf": str(crf), "preset": "medium", "g": str(gop), "keyint_min": str(gop), "sc_threshold": "0"}
            for i in range(rec.frames):
                with Image.open(self.frame_path(rec.id, i)) as im:
                    arr = np.ascontiguousarray(np.asarray(im.convert("RGB"))[:h, :w])
                for pkt in stream.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                    container.mux(pkt)
            for pkt in stream.encode():
                container.mux(pkt)
        tmp.replace(out)
        rec.proxy_path = out.relative_to(self.ws.path).as_posix()
        rec.proxy_bytes = out.stat().st_size
        self.save(rec)
        return rec

    def delete(self, clip_id: str) -> bool:
        import shutil

        d = self.dir(clip_id)
        if not d.is_dir():
            return False
        shutil.rmtree(d, ignore_errors=True)
        return True


def compute_identity(models_root: Path | str, store: ClipStore, rec: ClipRecord, reference: Path | None) -> dict[str, Any]:
    """FaceSim across the clip: the start frame (or master frame 0) is the reference; ≤ 12 frames are sampled (11 §11 item 6)."""
    from PIL import Image

    from .tools import facesim

    if not facesim.available(models_root):
        return {"status": "weights missing — scripts/fetch_facesim.py", "sampled": 0, "with_face": 0}
    ref_path = reference if reference and Path(reference).is_file() else store.frame_path(rec.id, 0)
    ref = np.asarray(Image.open(ref_path).convert("RGB"))
    frames = [store.frame_path(rec.id, i) for i in range(rec.frames)]
    return facesim.clip_identity(facesim.FaceSim(models_root), ref, frames)
