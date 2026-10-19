"""CA1 (D94, proto01_animate 01 step 5, 02 §5): the motion library's files — the CC0 starter set that ships (Quaternius' Universal Animation
Library 1 and 2, glb) and the author's **local motion folder** (Settings › Motion; their own downloads such as Mixamo FBX, never bundled,
never in CI, never in tests — Mixamo's Additional Terms §1). The orchestrator only lists and serves the files; the client loads them with
three.js (GLTFLoader, FBXLoader), lists their clips and retargets them onto the Stage figure (frontend/src/suites/stage/motion/)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

MotionSource = Literal["starter", "local"]
STARTER_EXT = (".glb",)                            # the starter set's Godot / Unreal-Godot exports (its fbx copies are the same clips)
LOCAL_EXT = (".glb", ".gltf", ".fbx")
SKIP_DIRS = {"_downloads", "__MACOSX"}


class MotionFile(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    name: str                                      # the file's name without its extension
    source: MotionSource
    rel: str                                       # the path inside its folder (shown; never a full path)
    ext: str
    bytes: int
    licence: str


def starter_dir(models_root: str, configured: str) -> Path:
    return Path(configured) if configured else Path(models_root) / "motion"


def _id(source: str, rel: str) -> str:
    return "mot_" + hashlib.sha1(f"{source}:{rel}".encode("utf-8")).hexdigest()[:12]


def scan(starter: Path | None, local: Path | None) -> list[MotionFile]:
    """Every motion file of the two folders, the starter set first, each list by path. A missing folder lists nothing."""
    out: list[MotionFile] = []
    for source, root, exts, licence in (("starter", starter, STARTER_EXT, "CC0 1.0 (Quaternius)"),
                                        ("local", local, LOCAL_EXT, "your own files — used in your films, never bundled or used to train AI")):
        if root is None or not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in exts or any(part in SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            rel = p.relative_to(root).as_posix()
            out.append(MotionFile(id=_id(source, rel), name=p.stem, source=source, rel=rel, ext=p.suffix.lower().lstrip("."), bytes=p.stat().st_size,
                                  licence=licence))
    return out


def resolve(file_id: str, starter: Path | None, local: Path | None) -> Path | None:
    """The file behind an id from `scan`, or None (ids are recomputed: a renamed file gets a new one)."""
    for f in scan(starter, local):
        if f.id == file_id:
            root = starter if f.source == "starter" else local
            return (root / f.rel) if root else None
    return None
