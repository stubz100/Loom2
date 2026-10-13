"""Story (17, D85): the workspace's records under `story/`.

SY0 — the world (L1: logline, synopsis, styles, the spine's beats, the Flow's variables) and the style a generation carries.
SY1 — profiles (L2: a character, place or prop with versions; a version's reference set *is* an album group, its candidates another),
      the coverage vocabulary and presets that `Expand` plans into one T2I job per cell, and the profile mentions behind `@name`.
Shots (SY2) and the flow (SY3) join here.

A record is one JSON file written through fsio (temp → fsync → replace) with a `schema_version` and a `revision` the client sends back
on every replace (409 when stale, like documents and stages). Records are read on demand (small files), never cached across requests.

Styles (loom R104 as amended, 02 §7 lesson 7): a generation names one style by id; at submit (and preview) `resolve_style` stamps the
style's fragment on the recipe as `style_text`, and the graph builder appends it after the prompt — so the manifest records both the
id and the exact text that ran, and re-running a stored recipe uses the text it was made with, not today's fragment.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json, read_json_or, utc_now
from .models import registry

if TYPE_CHECKING:
    from .groups import GroupStore
    from .recipes import T2I
    from .workspace import Workspace

WORLD_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = 1
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ProfileClass = Literal["character", "place", "prop"]
VersionState = Literal["open", "final"]


class StaleWorld(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class StaleProfile(ValueError):
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


# ---- profiles (SY1, 17 §3b) ----------------------------------------------------------------------------------------------------
class ProfileVersion(BaseModel):
    """One version of a profile (loom §3.4): its reference set is an album group (`group_id`), its expansion candidates another; `open`
    is editable and expandable, `final` locks the group and the fields (a retake is a new version). `trigger` and `lora` wait for the
    LoRA wave (D25)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    state: VersionState = "open"
    group_id: str
    candidates_group_id: str | None = None
    hero_asset_id: str | None = None
    stub: str = ""                                   # the clause a mention carries into a prompt (loom R112)
    trigger: str | None = None
    lora: str | None = None
    derived_from: str | None = None
    created_at: str = Field(default_factory=utc_now)
    locked_at: str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = PROFILE_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("prf"))
    name: str
    cls: ProfileClass = "character"
    current: str
    versions: list[ProfileVersion] = Field(default_factory=list)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def version(self, vid: str | None = None) -> ProfileVersion:
        want = vid or self.current
        v = next((x for x in self.versions if x.id == want), None)
        if v is None:
            raise KeyError(f"profile {self.id} has no version {want}")
        return v


def check_profile(p: Profile) -> None:
    if not p.name.strip():
        raise ValueError("a profile needs a name")
    ids = [v.id for v in p.versions]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("a profile has at least one version and their ids are unique")
    if p.current not in ids:
        raise ValueError(f"current version {p.current} is not one of the versions")


# ---- coverage (loom kb-loom-p1 §7.1) ---------------------------------------------------------------------------------------------
SHOTS: list[tuple[str, str]] = [("close-up", "a close-up of the face"), ("portrait", "a head-and-shoulders portrait"),
                                ("waist-up", "a waist-up medium shot"), ("full-body", "a full-body shot")]
ANGLES: list[tuple[str, str]] = [("front", "seen from the front"), ("three-quarter left", "a three-quarter view from the left"),
                                 ("three-quarter right", "a three-quarter view from the right"), ("profile left", "in profile from the left"),
                                 ("profile right", "in profile from the right"), ("back", "seen from behind")]
EXPRESSIONS: list[str] = ["neutral", "smile", "serious", "sad", "surprised"]
_SHOT = dict(SHOTS)
_ANGLE = dict(ANGLES)
_A = [a for a, _ in ANGLES]
FRONT3 = _A[:3]                                   # front and the two three-quarters
FRONT5 = _A[:5]                                   # … and the two profiles

# a preset is rows of (shot, angles, expressions, seeds); its cells are the product (loom R111: matched to how much detail the asset needs)
PRESETS: dict[str, dict[str, Any]] = {
    "comprehensive": {"label": "Comprehensive", "hint": "every cell, several seeds — a main character", "rows": [
        ("close-up", FRONT5, EXPRESSIONS, 1), ("close-up", FRONT3, ["neutral", "smile", "serious"], 1),
        ("portrait", FRONT5, EXPRESSIONS, 1), ("waist-up", _A, ["neutral", "smile", "serious"], 1), ("full-body", _A, ["neutral"], 2)]},
    "full": {"label": "Full coverage", "hint": "the default for a main or supporting character", "rows": [
        ("close-up", FRONT3, ["neutral", "smile", "serious"], 1), ("close-up", _A[3:5], ["neutral"], 1),
        ("portrait", _A[:4], ["neutral", "smile"], 1), ("portrait", ["front"], ["sad", "surprised"], 1),
        ("waist-up", _A, ["neutral"], 1), ("waist-up", FRONT3, ["smile"], 1), ("full-body", [*FRONT3, "back"], ["neutral"], 1),
        ("close-up", ["front"], ["neutral"], 2)]},
    "portrait": {"label": "Portrait-heavy", "hint": "dialogue-led characters: faces and expressions", "rows": [
        ("close-up", FRONT5, EXPRESSIONS, 1), ("portrait", FRONT3, ["neutral"], 1), ("waist-up", ["front"], ["neutral"], 1)]},
    "fullbody": {"label": "Full-body / outfit", "hint": "costume and proportions", "rows": [
        ("full-body", _A, ["neutral"], 2), ("waist-up", _A, ["neutral", "smile", "serious"], 1), ("portrait", _A, ["neutral"], 1),
        ("close-up", FRONT3, ["neutral", "smile"], 1)]},
    "npc": {"label": "NPC-lite", "hint": "a bit part: enough to recognise", "rows": [
        ("close-up", FRONT3, ["neutral", "smile"], 1), ("portrait", FRONT3, ["neutral"], 1), ("waist-up", FRONT5, ["neutral"], 1),
        ("full-body", [*FRONT3, "back"], ["neutral"], 1)]},
}


def preset_cells(preset: str) -> list[dict[str, Any]]:
    """The cells of a preset in order: `{shot, angle, expression, take}` — `take` numbers the seeds of one cell."""
    rows = PRESETS.get(preset)
    if rows is None:
        raise ValueError(f"unknown preset {preset!r}; one of {', '.join(PRESETS)}")
    out = []
    for shot, angles, expressions, seeds in rows["rows"]:
        for a in angles:
            for e in expressions:
                for t in range(seeds):
                    out.append({"shot": shot, "angle": a, "expression": e, "take": t + 1})
    return out


def cell_sentence(cell: dict[str, Any]) -> str:
    """What a cell asks for, as the prompt's sentence: 'a waist-up medium shot, a three-quarter view from the left, neutral expression'."""
    return f"{_SHOT.get(cell['shot'], cell['shot'])}, {_ANGLE.get(cell['angle'], cell['angle'])}, {cell['expression']} expression"


def expand_spec(variant: str):
    """The model Expand runs on in this build: the one that renders a stage's clay reference (D78 — Klein 9B under `full`, 4B under `open`,
    measured at 12 s warm) — it takes the hero as a reference and renders the same person; failing that, the variant's t2i default."""
    for spec in registry.stage_specs():
        if spec.recipes.stage == "clay" and registry.offered(spec, variant):
            return spec
    return registry.get(registry.default_model("t2i"))


def plan_expand(profile: Profile, version: ProfileVersion, preset: str, variant: str, *, seeds_per_cell: int = 1, width: int, height: int,
                style_id: str | None = None, tier: str | None = None, group_id: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """One T2I recipe per cell (× seeds), each with the hero as reference 1 and the cell's sentence after the stub, and the job origin that
    places the result on the candidates group and records the cell (17 §3b). The style is resolved by the queue like any submit."""
    if version.state != "open":
        raise ValueError(f"version {version.id} is locked — expand a new version")
    if not version.hero_asset_id:
        raise ValueError("the version has no hero image yet — make one the hero first")
    spec = expand_spec(variant)
    if spec is None:
        raise ValueError("no model to expand with in this build")
    out = []
    stub = (version.stub or profile.name).strip().rstrip(".")
    for cell in preset_cells(preset):
        for s in range(max(1, int(seeds_per_cell))):
            c = {**cell, "take": (cell["take"] - 1) * max(1, int(seeds_per_cell)) + s + 1}
            recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": f"{stub}. {cell_sentence(c)}.",
                      "width": width, "height": height, "seeds": [0], "refs": [{"asset_id": version.hero_asset_id, "note": profile.name}],
                      "style_id": style_id, "tier": tier}
            origin = {"suite": "story", "surface": "expand", "ref": profile.id, "payload": {"version": version.id, "cell": c, "group_id": group_id, "preset": preset}}
            out.append((recipe, origin))
    return out


# ---- the store ---------------------------------------------------------------------------------------------------------------------
class StoryStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.story_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir = self.dir / "profiles"

    # -- world --
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

    # -- profiles --
    def profile_path(self, pid: str) -> Path:
        return self.profiles_dir / f"{pid}.json"

    def profile(self, pid: str) -> Profile | None:
        p = self.profile_path(pid)
        return Profile.model_validate(read_json(p)) if p.is_file() else None

    def profiles(self) -> list[Profile]:
        if not self.profiles_dir.is_dir():
            return []
        out = [Profile.model_validate(read_json(p)) for p in self.profiles_dir.glob("prf_*.json")]
        return sorted(out, key=lambda p: p.updated_at, reverse=True)

    def save_profile(self, p: Profile) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.profile_path(p.id), p.model_dump())

    def create_profile(self, name: str, cls: ProfileClass, groups: GroupStore, hero_asset_id: str | None = None, stub: str = "") -> Profile:
        """A profile with version 1: its reference set is a new album group named after it; the hero (when given) moves onto that page
        as its cover and first reference."""
        name = name.strip()
        if not name:
            raise ValueError("a profile needs a name")
        g = groups.create(f"{name} · v1")
        if hero_asset_id:
            groups.move([("asset", hero_asset_id)], g.id)
            groups.update(g.id, cover_id=hero_asset_id)
        v = ProfileVersion(id="v1", group_id=g.id, hero_asset_id=hero_asset_id, stub=stub.strip() or name)
        p = Profile(name=name, cls=cls, current="v1", versions=[v])
        check_profile(p)
        self.save_profile(p)
        return p

    def patch_profile(self, pid: str, data: dict[str, Any]) -> Profile:
        """Name, class, the current version, and an open version's stub / hero from a client body based on `revision` (409 when stale)."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleProfile(f"the profile is at revision {cur.revision}, the change is based on {base} — reload it first")
        versions = [v.model_copy() for v in cur.versions]
        for patch in data.get("versions") or []:
            v = next((x for x in versions if x.id == patch.get("id")), None)
            if v is None:
                raise ValueError(f"no version {patch.get('id')!r}")
            if v.state != "open" and any(k in patch for k in ("stub", "hero_asset_id")):
                raise ValueError(f"version {v.id} is locked — its fields are read-only; make a new version")
            for k in ("stub", "hero_asset_id"):
                if k in patch:
                    setattr(v, k, patch[k])
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in ("name", "cls", "current")}, "versions": [v.model_dump() for v in versions],
                  "id": pid, "schema_version": PROFILE_SCHEMA_VERSION, "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        p = Profile.model_validate(merged)
        check_profile(p)
        self.save_profile(p)
        return p

    def new_version(self, pid: str, groups: GroupStore) -> Profile:
        """A full copy of the current version (loom R53 / R58): the reference set duplicated (its assets copied — an asset lives on one page,
        D34), the fields copied, `derived_from` stamped; the copy becomes the current version, open."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        src = cur.version()
        n = max(int(v.id[1:]) for v in cur.versions if v.id[1:].isdigit()) + 1
        g = groups.duplicate_group(src.group_id)
        groups.update(g.id, name=f"{cur.name} · v{n}")
        g = groups.groups[g.id]
        v = ProfileVersion(id=f"v{n}", group_id=g.id, hero_asset_id=g.cover_id if src.hero_asset_id else None, stub=src.stub, trigger=None, lora=None,
                           derived_from=src.id)
        p = cur.model_copy(update={"versions": [*cur.versions, v], "current": v.id, "revision": cur.revision + 1, "updated_at": utc_now()})
        check_profile(p)
        self.save_profile(p)
        return p

    def lock_version(self, pid: str, vid: str, groups: GroupStore) -> Profile:
        """The version becomes final: its reference group is locked (every mutation route answers 423), its fields read-only; mentions keep
        resolving to it."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        v = cur.version(vid)
        if v.state == "final":
            return cur
        if not v.hero_asset_id:
            raise ValueError("a version without a hero cannot be locked")
        groups.set_locked(v.group_id, True)
        versions = [x.model_copy(update={"state": "final", "locked_at": utc_now()}) if x.id == vid else x for x in cur.versions]
        p = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def set_candidates(self, pid: str, vid: str, group_id: str) -> Profile:
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        versions = [x.model_copy(update={"candidates_group_id": group_id}) if x.id == vid else x for x in cur.versions]
        p = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def delete_profile(self, pid: str, groups: GroupStore | None = None) -> bool:
        """The record goes; its groups and images stay in the album (unlocked again)."""
        p = self.profile(pid)
        if p is None:
            return False
        if groups is not None:
            for v in p.versions:
                if v.group_id in groups.groups and groups.groups[v.group_id].locked:
                    groups.set_locked(v.group_id, False)
        self.profile_path(pid).unlink()
        return True


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
