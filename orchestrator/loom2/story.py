"""Story (17, D85): the workspace's records under `story/` — SY0 brings the world (L1: logline, synopsis, styles, the spine's beats,
the Flow's variables) and the style a generation carries. Profiles (SY1), shots (SY2) and the flow (SY3) join here.

A record is one JSON file written through fsio (temp → fsync → replace) with a `schema_version` and a `revision` the client sends back
on every replace (409 when stale, like documents and stages). The world is read on demand (a small file), never cached across requests.

Styles (loom R104 as amended, 02 §7 lesson 7): a generation names one style by id; at submit (and preview) `resolve_style` stamps the
style's fragment on the recipe as `style_text`, and the graph builder appends it after the prompt — so the manifest records both the
id and the exact text that ran, and re-running a stored recipe uses the text it was made with, not today's fragment.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json_or, utc_now

if TYPE_CHECKING:
    from .recipes import T2I
    from .workspace import Workspace

WORLD_SCHEMA_VERSION = 1
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StaleWorld(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class StoryStyle(BaseModel):
    """One style of the world: the fragment a generation appends (17 §3a); `group_id` is a reference album (a later slice)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    id: str = Field(default_factory=lambda: new_id("sty"))
    name: str
    fragment: str = ""                              # appended after the prompt, one style per generation
    group_id: str | None = None                     # an album group of reference images (optional; a later slice mentions it)


class StoryBeat(BaseModel):
    """One line of the spine (loom L1 "story spine"): a Flow node is made from it by hand, never synced (loom R55)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str = Field(default_factory=lambda: new_id("beat"))
    title: str
    line: str = ""


class StoryVariable(BaseModel):
    """A Flow variable (loom R135: bool or enum flags, nothing more in v1); conditions and actions read them by name."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    name: str
    type: Literal["bool", "enum"] = "bool"
    values: list[str] = Field(default_factory=list)   # enum only
    default: bool | str = False


class World(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = WORLD_SCHEMA_VERSION
    logline: str = ""
    synopsis: str = ""
    styles: list[StoryStyle] = Field(default_factory=list)
    default_style: str | None = None                # a style id Generate preselects (none = no style)
    spine: list[StoryBeat] = Field(default_factory=list)
    variables: list[StoryVariable] = Field(default_factory=list)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


def check_world(w: World) -> None:
    """The invariants a saved world keeps: unique style ids and names, unique beat ids, variable names that are identifiers and unique,
    enum variables with values and a default among them, the default style present."""
    ids = [s.id for s in w.styles]
    if len(set(ids)) != len(ids):
        raise ValueError("style ids must be unique")
    names = [s.name.strip().lower() for s in w.styles]
    if any(not n for n in names):
        raise ValueError("a style needs a name")
    if len(set(names)) != len(names):
        raise ValueError("style names must be unique")
    if w.default_style is not None and w.default_style not in ids:
        raise ValueError(f"default style {w.default_style} is not one of the styles")
    bids = [b.id for b in w.spine]
    if len(set(bids)) != len(bids):
        raise ValueError("beat ids must be unique")
    vnames = [v.name for v in w.variables]
    if len(set(vnames)) != len(vnames):
        raise ValueError("variable names must be unique")
    for v in w.variables:
        if not _NAME.match(v.name):
            raise ValueError(f"variable {v.name!r}: a name is letters, digits and underscores, not starting with a digit")
        if v.type == "enum":
            if not v.values or len(set(v.values)) != len(v.values) or any(not x.strip() for x in v.values):
                raise ValueError(f"variable {v.name}: an enum needs distinct, non-empty values")
            if not isinstance(v.default, str) or v.default not in v.values:
                raise ValueError(f"variable {v.name}: the default must be one of its values")
        elif not isinstance(v.default, bool):
            raise ValueError(f"variable {v.name}: a bool's default is true or false")


class StoryStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.story_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def world_path(self) -> Path:
        return self.dir / "world.json"

    def world(self) -> World:
        """The world; an empty one at revision 0 until the first save (nothing is written by a read)."""
        return World.model_validate(read_json_or(self.world_path, {}))

    def put_world(self, data: dict[str, Any]) -> World:
        """Replace the world from a client body based on `revision` (409 when stale); schema and timestamps are the server's."""
        cur = self.world()
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleWorld(f"the world is at revision {cur.revision}, the change is based on {base} — reload it first")
        keep = ("logline", "synopsis", "styles", "default_style", "spine", "variables")
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in keep}, "schema_version": WORLD_SCHEMA_VERSION,
                  "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        w = World.model_validate(merged)
        check_world(w)
        atomic_write_json(self.world_path, w.model_dump())
        return w

    def style(self, style_id: str) -> StoryStyle | None:
        return next((s for s in self.world().styles if s.id == style_id), None)


def resolve_style(recipe: T2I, store: StoryStore | None) -> T2I:
    """The recipe with its style's fragment stamped as `style_text` (D85); without a style, or already stamped, it is returned unchanged."""
    if not recipe.style_id or recipe.style_text is not None:
        return recipe
    if store is None:
        raise ValueError("a style needs an open project")
    s = store.style(recipe.style_id)
    if s is None:
        raise ValueError(f"style {recipe.style_id} does not exist")
    return recipe.model_copy(update={"style_text": s.fragment.strip()})
