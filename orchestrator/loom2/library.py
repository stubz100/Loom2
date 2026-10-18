"""D92 (wave UI7): the project's World library and its saved panels.

**The library** — every reusable piece of a Generate prompt (a lighting, a mood, a lens, a scene, a negative …) is an entry of the project's
Story · World: `{id, field, name, text}` in `story/library.json` with a `schema_version` and a `revision` the client sends back on every
change (409 when stale, like the world). Generate's preset tiles read it; World is where an entry is written. A project's library is
**seeded the first time it is read**: the built-in vocabulary (`library_seed.json` — the one source, the frontend's glyph test reads it
too) plus the author's app-wide presets (`<state>/snippets.json`, the pre-D92 "yours" presets — merged at the seed, so nothing is lost and
nothing is merged twice). An entry's picture is the app-state swatch of its field + text (`preset_icons.py`, unchanged); `group_id` is
room for a picture album later.

**Saved panels** — Generate's whole-panel templates (`generate/presets.json`, 09 §3e) gain a record shape (`schema_version`) and a picture:
`thumb_asset_id`, the panel's most recent result — sent by the client when it saves one, and set by the finisher when a job made from an
applied panel lands (its origin payload names it as `saved_panel`).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json_or, utc_now

LIBRARY_SCHEMA_VERSION = 1
PANELS_SCHEMA_VERSION = 1
SEED_PATH = Path(__file__).with_name("library_seed.json")
# The prompt fields an entry belongs to (Generate's FieldKey, fieldPresets.ts). `subject.description` is not seeded — a subject is a Cast
# character now (D92) — but the author's own description presets are kept.
FIELDS: tuple[str, ...] = ("scene", "subject.description", "subject.position", "subject.action", "subject.pose", "style", "lighting", "mood", "background",
                           "composition", "camera.angle", "camera.lens", "camera.depth_of_field", "camera.f-number", "camera.distance", "text", "negative")
_lock = threading.Lock()                          # the routes run in threads: a first read seeds once, changes apply one at a time


class StaleLibrary(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class LibraryEntry(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    id: str = Field(default_factory=lambda: new_id("lib"))
    field: str
    name: str
    text: str                                     # the words the field takes (the swatch key is field + text)
    source: Literal["builtin", "snippet", "user"] = "user"
    group_id: str | None = None                   # a picture album (a later slice); the picture is the app-state swatch today


class Library(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = LIBRARY_SCHEMA_VERSION
    entries: list[LibraryEntry] = Field(default_factory=list)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


def seed_entries() -> list[tuple[str, str, str]]:
    """The built-in vocabulary as (field, name, text) in the seed's order."""
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    out = []
    for field, items in data["fields"].items():
        for it in items:
            name, text = (it, it) if isinstance(it, str) else (it[0], it[1])
            out.append((field, name, text))
    return out


def check_library(lib: Library) -> None:
    """Unique ids; a known field, a name and words on every entry; the words once per field (a tile and its picture are field + words)."""
    ids = [e.id for e in lib.entries]
    if len(set(ids)) != len(ids):
        raise ValueError("library entry ids must be unique")
    seen: dict[tuple[str, str], str] = {}
    for e in lib.entries:
        if e.field not in FIELDS:
            raise ValueError(f"{e.field!r} is not a prompt field")
        if not e.name.strip():
            raise ValueError("a library entry needs a name")
        if not e.text.strip():
            raise ValueError("a library entry needs its words")
        k = (e.field, e.text.strip().casefold())
        if k in seen:
            raise ValueError(f"those words are already in the library as “{seen[k]}”")
        seen[k] = e.name


class LibraryStore:
    def __init__(self, story_dir: Path, state_dir: Path | None = None) -> None:
        self.path = Path(story_dir) / "library.json"
        self.state_dir = Path(state_dir) if state_dir else None

    def _seed(self) -> Library:
        entries = [LibraryEntry(field=f, name=n, text=t, source="builtin") for f, n, t in seed_entries()]
        have = {(e.field, e.text.strip().casefold()) for e in entries}
        if self.state_dir is not None:                                           # the author's app-wide presets (pre-D92 snippets), once
            snips = read_json_or(self.state_dir / "snippets.json", {"snippets": []})
            for s in snips.get("snippets", []) if isinstance(snips, dict) else []:
                f, n, t = str(s.get("field", "")), str(s.get("name", "")).strip(), str(s.get("text", "")).strip()
                if f in FIELDS and t and (f, t.casefold()) not in have:
                    entries.append(LibraryEntry(field=f, name=n or t, text=t, source="snippet"))
                    have.add((f, t.casefold()))
        lib = Library(entries=entries)
        check_library(lib)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, lib.model_dump())
        return lib

    def _read(self) -> Library:
        if not self.path.is_file():
            return self._seed()
        return Library.model_validate(read_json_or(self.path, {}))

    def get(self) -> Library:
        """The library, seeded (and written) on its first read."""
        with _lock:
            return self._read()

    def _commit(self, cur: Library, base: int | None, entries: list[LibraryEntry]) -> Library:
        if base is not None and int(base) != cur.revision:
            raise StaleLibrary(f"the library is at revision {cur.revision}, the change is based on {base} — reload it first")
        lib = Library(entries=entries, revision=cur.revision + 1, created_at=cur.created_at, updated_at=utc_now())
        check_library(lib)
        atomic_write_json(self.path, lib.model_dump())
        return lib

    def add(self, field: str, name: str, text: str, *, base: int | None = None, entry_id: str | None = None, at: int | None = None) -> tuple[Library, LibraryEntry]:
        """A new entry (at the end of its field, or at index `at` of the whole list — the Undo of a removal gives its id and place back)."""
        with _lock:
            cur = self._read()
            e = LibraryEntry(field=field, name=(name.strip() or text.strip())[:80], text=text.strip(), **({"id": entry_id} if entry_id else {}))
            entries = list(cur.entries)
            if at is None:
                last = max((i for i, x in enumerate(entries) if x.field == field), default=len(entries) - 1)
                entries.insert(last + 1, e)
            else:
                entries.insert(max(0, min(at, len(entries))), e)
            return self._commit(cur, base, entries), e

    def patch(self, eid: str, data: dict[str, Any]) -> tuple[Library, LibraryEntry]:
        """An entry's name and / or words (World's Inspector is the only place they are written)."""
        with _lock:
            cur = self._read()
            i = next((k for k, x in enumerate(cur.entries) if x.id == eid), None)
            if i is None:
                raise KeyError(eid)
            upd = {k: str(data[k]).strip() for k in ("name", "text") if data.get(k) is not None}
            e = cur.entries[i].model_copy(update=upd)
            entries = [*cur.entries[:i], e, *cur.entries[i + 1:]]
            return self._commit(cur, data.get("revision"), entries), e

    def remove(self, eid: str, base: int | None = None) -> tuple[Library, LibraryEntry, int]:
        with _lock:
            cur = self._read()
            i = next((k for k, x in enumerate(cur.entries) if x.id == eid), None)
            if i is None:
                raise KeyError(eid)
            return self._commit(cur, base, [x for x in cur.entries if x.id != eid]), cur.entries[i], i

    def reorder(self, ids: list[str], base: int | None = None) -> Library:
        """The entries in a new order — `ids` names every entry once."""
        with _lock:
            cur = self._read()
            by = {e.id: e for e in cur.entries}
            if sorted(ids) != sorted(by):
                raise ValueError("a new order names every library entry once")
            return self._commit(cur, base, [by[i] for i in ids])


# ---- saved panels ---------------------------------------------------------------------------------------------------------------------
class SavedPanel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    name: str
    panel: dict[str, Any]                         # Generate's panel as the client holds it (every field of the column)
    saved_at: str = Field(default_factory=utc_now)
    thumb_asset_id: str | None = None             # D92: the panel's most recent result — its picture in Generate and World


class SavedPanels(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = PANELS_SCHEMA_VERSION
    presets: list[SavedPanel] = Field(default_factory=list)
    last: str | None = None


def panels_path(project_dir: Path) -> Path:
    return Path(project_dir) / "generate" / "presets.json"


def read_panels(project_dir: Path) -> SavedPanels:
    return SavedPanels.model_validate(read_json_or(panels_path(project_dir), {}))


def put_panels(project_dir: Path, body: dict[str, Any]) -> SavedPanels:
    """Replace the list as the client sends it; a panel sent without a picture keeps the one the server holds under its name (the finisher
    may have set it while the client's copy was older)."""
    with _lock:
        cur = {p.name: p for p in read_panels(project_dir).presets}
        nxt = SavedPanels.model_validate({**body, "schema_version": PANELS_SCHEMA_VERSION})
        names = [p.name.strip() for p in nxt.presets]
        if any(not n for n in names) or len(set(names)) != len(names):
            raise ValueError("saved panels need distinct names")
        nxt.presets = [p if p.thumb_asset_id or p.name not in cur else p.model_copy(update={"thumb_asset_id": cur[p.name].thumb_asset_id}) for p in nxt.presets]
        if nxt.last is not None and nxt.last not in names:
            nxt.last = None
        panels_path(project_dir).parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(panels_path(project_dir), nxt.model_dump())
        return nxt


def set_panel_thumb(project_dir: Path, name: str, asset_id: str) -> bool:
    """The finisher's half: a job made from the applied panel `name` landed — its first result becomes the panel's picture."""
    with _lock:
        cur = read_panels(project_dir)
        hit = next((p for p in cur.presets if p.name == name), None)
        if hit is None:
            return False
        hit.thumb_asset_id = asset_id
        atomic_write_json(panels_path(project_dir), cur.model_dump())
        return True


# D95 (AN1, UX0 #11): Animate's saved panels — a project record like Image's (they lived in the browser until now; the client imports them
# once). A panel is Animate's form without its frames (start, end, beats); the record keeps whatever fields the client sends.
ANIM_PANELS_SCHEMA_VERSION = 1


class AnimatePanel(BaseModel):
    model_config = ConfigDict(extra="allow", json_schema_serialization_defaults_required=True)   # D38: present in every reply
    name: str
    panel: dict[str, Any] = Field(default_factory=dict)
    saved_at: str = Field(default_factory=utc_now)


class AnimatePanels(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = ANIM_PANELS_SCHEMA_VERSION
    presets: list[AnimatePanel] = Field(default_factory=list)
    last: str | None = None


def animate_panels_path(project_dir: Path) -> Path:
    return Path(project_dir) / "animate" / "presets.json"


def read_animate_panels(project_dir: Path) -> AnimatePanels:
    return AnimatePanels.model_validate(read_json_or(animate_panels_path(project_dir), {}))


def put_animate_panels(project_dir: Path, body: dict[str, Any]) -> AnimatePanels:
    """Replace the list as the client sends it (distinct, non-empty names; `last` one of them or none)."""
    with _lock:
        nxt = AnimatePanels.model_validate({**body, "schema_version": ANIM_PANELS_SCHEMA_VERSION})
        names = [p.name.strip() for p in nxt.presets]
        if any(not n for n in names) or len(set(names)) != len(names):
            raise ValueError("saved panels need distinct names")
        for p in nxt.presets:                                     # the frames never belong to a saved panel
            for k in ("start", "end", "beats"):
                p.panel.pop(k, None)
        if nxt.last is not None and nxt.last not in names:
            nxt.last = None
        animate_panels_path(project_dir).parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(animate_panels_path(project_dir), nxt.model_dump())
        return nxt

