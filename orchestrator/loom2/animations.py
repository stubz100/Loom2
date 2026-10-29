"""U5 (D157 G9; proto01_UI2 04 §3.2, 06 §2.4): animation templates — a stretch of a figure's motion saved in the stage's own key format
on the shared mannequin rig (re-based to frame 0 and its start position, the Detailed bones and the pins kept), so it applies to any
figure as a clip block (`BlockSource.kind == "template"`). A template is the project's (`stages/animations.json`, revision-guarded like
the poses); *Save to my library* copies it into the app's state (`<state>/animations/<id>.json`), so it is the author's in every project
(Q4). The motion library lists both as *Mine*."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, plain_name, read_json_or, unlink, utc_now

ANIMATIONS_SCHEMA_VERSION = 1


class AnimationFrom(BaseModel):
    """Where a template was saved from (lineage)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    stage_id: str | None = None
    object_id: str | None = None
    start: int = 0
    end: int = 0


class AnimationTemplate(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = ANIMATIONS_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("anm"))
    name: str
    rig: Literal["mannequin"] = "mannequin"
    frames: int = Field(..., ge=1, le=100_000)      # its length (keys run 0 … frames − 1)
    fps: int = Field(24, ge=1, le=240)
    hip: float = Field(0.91, gt=0.2, le=2.0)       # the hip height (m) of the figure it was saved from — a figure's root is scaled by its own over this
    keys: list[dict[str, Any]] = Field(default_factory=list)   # ObjectKey[] (anim.ts): frame, ease, transform, pose
    source: AnimationFrom = Field(default_factory=AnimationFrom)
    created_at: str = Field(default_factory=utc_now)


class AnimationBook(BaseModel):
    """`stages/animations.json`."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = ANIMATIONS_SCHEMA_VERSION
    revision: int = 0
    items: list[AnimationTemplate] = Field(default_factory=list)


class StaleAnimations(ValueError):
    pass


def check_template(t: AnimationTemplate) -> None:
    if not t.name.strip():
        raise ValueError("an animation needs a name")
    if not t.keys:
        raise ValueError(f"{t.name}: an animation has at least one key")
    for k in t.keys:
        f = k.get("frame") if isinstance(k, dict) else None
        if not isinstance(f, (int, float)) or not 0 <= f < t.frames or not isinstance(k.get("transform"), dict):
            raise ValueError(f"{t.name}: each key has a frame in 0 … {t.frames - 1} and a transform")


class AnimationStore:
    def __init__(self, stages_dir: Path, state_dir: Path) -> None:
        self.path = Path(stages_dir) / "animations.json"
        self.lib = Path(state_dir) / "animations"

    def book(self) -> AnimationBook:
        return AnimationBook.model_validate(read_json_or(self.path, {}))

    def put(self, revision: int, items: list[AnimationTemplate]) -> AnimationBook:
        """The project's templates replaced (the client sends the revision it read: 409 when they changed meanwhile)."""
        cur = self.book()
        if revision != cur.revision:
            raise StaleAnimations(f"the animations are at revision {cur.revision}, the change is based on {revision} — reload them first")
        if len({t.id for t in items}) != len(items):
            raise ValueError("animation ids are unique")
        for t in items:
            check_template(t)
        out = AnimationBook(revision=cur.revision + 1, items=items)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, out.model_dump())
        return out

    def library(self) -> list[AnimationTemplate]:
        """The author's library, every project's (newest first)."""
        if not self.lib.is_dir():
            return []
        out = []
        for p in self.lib.glob("anm_*.json"):
            raw = read_json_or(p, None)
            if isinstance(raw, dict):
                try:
                    out.append(AnimationTemplate.model_validate(raw))
                except ValueError:
                    continue
        return sorted(out, key=lambda t: t.created_at, reverse=True)

    def to_library(self, aid: str) -> AnimationTemplate:
        """*Save to my library*: a copy of the project's template in the app's state (KeyError: no such template)."""
        t = next((x for x in self.book().items if x.id == aid), None)
        if t is None:
            raise KeyError(aid)
        self.lib.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.lib / f"{plain_name(t.id)}.json", t.model_dump())
        return t

    def from_library_remove(self, aid: str) -> None:
        p = self.lib / f"{plain_name(aid)}.json"
        if not p.is_file():
            raise KeyError(aid)
        unlink(p)
