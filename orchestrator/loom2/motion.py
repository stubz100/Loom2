"""CA1 (D94, proto01_animate 01 step 5, 02 §5): the motion library's files — the CC0 starter set that ships (Quaternius' Universal Animation
Library 1 and 2, glb) and the author's **local motion folder** (Settings › Motion; their own downloads such as Mixamo FBX, never bundled,
never in CI, never in tests — Mixamo's Additional Terms §1). The orchestrator only lists and serves the files; the client loads them with
three.js (GLTFLoader, FBXLoader), lists their clips and retargets them onto the Stage figure (frontend/src/suites/stage/motion/)."""
from __future__ import annotations

import hashlib
import time
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


_INDEX: dict[tuple[str, str], tuple[float, dict[str, Path]]] = {}
INDEX_TTL_S = 10.0                                 # review K91: a library's clips are fetched in a burst — one scan serves the burst


def resolve(file_id: str, starter: Path | None, local: Path | None) -> Path | None:
    """The file behind an id from `scan`, or None (ids are recomputed: a renamed file gets a new one). Review K91: every GET walked both
    folders; the id → path map is kept for a few seconds (a miss rescans at once, so a file just added is found)."""
    key = (str(starter or ""), str(local or ""))
    at, index = _INDEX.get(key, (0.0, {}))
    if file_id not in index or time.monotonic() - at > INDEX_TTL_S:
        index = {f.id: ((starter if f.source == "starter" else local) / f.rel) for f in scan(starter, local)   # type: ignore[operator]
                 if (starter if f.source == "starter" else local) is not None}
        _INDEX[key] = (time.monotonic(), index)
    return index.get(file_id)
