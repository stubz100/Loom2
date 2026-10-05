"""Project workspace (06 §4 `<work disk>/<project>/`): the tree, `project.json`, the project format (D18) and
the disk guard inputs. Weights never live inside a project; outputs, documents, clips, masks and the durable
queue do.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .fsio import StateError, atomic_write_json, free_space_gb, new_id, read_json, utc_now

PROJECT_SCHEMA_VERSION = 1
SUBDIRS = ("assets", "thumbs", "documents", "clips", "masks", "jobs", "jobs/logs", "engine_out", "_temp")
Tier = Literal["thumb", "draft", "hd", "full"]
DEFAULT_SIZE_CAP_GB = 100.0
MIN_SIZE_CAP_GB = 10.0


class ProjectFormat(BaseModel):
    """The target the project finalises to (fixed at creation) and the working tier it defaults to (D18)."""
    aspect: tuple[int, int] = (16, 9)
    width: int = 1920
    height: int = 1080
    fps: int = 24
    default_tier: Tier = "draft"

    @model_validator(mode="after")
    def _geometry_locked(self) -> "ProjectFormat":
        aw, ah = self.aspect
        if aw * self.height != ah * self.width:
            raise ValueError(f"aspect {aw}:{ah} does not match {self.width}×{self.height}")
        if self.fps <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("fps, width and height must be positive")
        return self


class ProjectRecord(BaseModel):
    schema_version: int = PROJECT_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("prj"))
    name: str
    created_at: str = Field(default_factory=utc_now)
    format: ProjectFormat = Field(default_factory=ProjectFormat)
    size_cap_gb: float = DEFAULT_SIZE_CAP_GB
    variant_created_with: str = "full"

    @model_validator(mode="after")
    def _checks(self) -> "ProjectRecord":
        if not self.name.strip():
            raise ValueError("project name must not be empty")
        if self.size_cap_gb < MIN_SIZE_CAP_GB:
            raise ValueError(f"size cap below the {MIN_SIZE_CAP_GB} GB floor")
        return self


class Workspace:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()

    # ---- tree -------------------------------------------------------------------------------------
    @property
    def project_json(self) -> Path: return self.path / "project.json"
    @property
    def catalogue_db(self) -> Path: return self.path / "catalogue.sqlite"
    @property
    def assets_dir(self) -> Path: return self.path / "assets"
    @property
    def thumbs_dir(self) -> Path: return self.path / "thumbs"
    @property
    def documents_dir(self) -> Path: return self.path / "documents"
    @property
    def clips_dir(self) -> Path: return self.path / "clips"
    @property
    def masks_dir(self) -> Path: return self.path / "masks"
    @property
    def jobs_dir(self) -> Path: return self.path / "jobs"
    @property
    def logs_dir(self) -> Path: return self.path / "jobs" / "logs"
    @property
    def queue_path(self) -> Path: return self.path / "jobs" / "queue.json"
    @property
    def engine_out_dir(self) -> Path: return self.path / "engine_out"
    @property
    def temp_dir(self) -> Path: return self.path / "_temp"

    def asset_path(self, asset_id: str, ext: str, when: datetime | None = None) -> Path:
        month = (when or datetime.now()).strftime("%Y-%m")
        return self.assets_dir / month / f"{asset_id}.{ext.lstrip('.')}"

    def manifest_path_for(self, asset_file: Path) -> Path:
        return asset_file.with_suffix(".json")

    def thumb_path(self, asset_id: str, size: int) -> Path:
        return self.thumbs_dir / asset_id / f"{size}.webp"

    def job_log_path(self, job_id: str) -> Path:
        return self.logs_dir / f"{job_id}.log"

    def ensure_tree(self) -> None:
        for sub in SUBDIRS:
            (self.path / sub).mkdir(parents=True, exist_ok=True)

    # ---- lifecycle --------------------------------------------------------------------------------
    @classmethod
    def create(cls, dest: Path, *, name: str, fmt: ProjectFormat | dict | None = None,
               size_cap_gb: float = DEFAULT_SIZE_CAP_GB, variant: str = "full") -> "Workspace":
        dest = Path(dest).resolve()
        if dest.exists():
            if not dest.is_dir():
                raise StateError(f"destination is not a directory: {dest}")
            if any(dest.iterdir()):
                raise StateError(f"destination folder is not empty: {dest}")
        free = free_space_gb(dest)
        if free < size_cap_gb:
            raise StateError(f"insufficient free space: {free:.1f} GB < size cap {size_cap_gb} GB")
        try:
            record = ProjectRecord(name=name, format=ProjectFormat.model_validate(fmt) if fmt else ProjectFormat(),
                                   size_cap_gb=size_cap_gb, variant_created_with=variant)
        except ValueError as e:
            raise StateError(str(e)) from e
        ws = cls(dest)
        ws.ensure_tree()
        atomic_write_json(ws.project_json, record.model_dump())
        return ws

    @classmethod
    def open(cls, path: Path) -> "Workspace":
        ws = cls(path)
        if not ws.project_json.is_file():
            raise StateError(f"not a loom2 project (no project.json): {ws.path}")
        ws.load()
        ws.ensure_tree()
        return ws

    def load(self) -> ProjectRecord:
        try:
            return ProjectRecord.model_validate(read_json(self.project_json))
        except ValueError as e:
            raise StateError(f"invalid project.json: {e}") from e

    def save(self, record: ProjectRecord) -> None:
        atomic_write_json(self.project_json, record.model_dump())

    def info(self) -> dict:
        rec = self.load()
        return {
            "open": True, "path": str(self.path), "id": rec.id, "name": rec.name,
            "format": rec.format.model_dump(), "size_cap_gb": rec.size_cap_gb,
            "free_space_gb": round(free_space_gb(self.path), 1), "created_at": rec.created_at,
        }
