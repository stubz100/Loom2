"""Story (17, D85): the workspace's records under `story/`.

SY0 — the world (L1: logline, synopsis, styles, the spine's beats, the Flow's variables) and the style a generation carries.
SY1 — profiles (L2: a character, place or prop with versions; a version's reference set *is* an album group, its candidates another),
      the coverage vocabulary and presets that `Expand` plans into one T2I job per cell, and the profile mentions behind `@name`.
SY2 — shots (L3: a shot with versions; a version points at a stage camera and / or a clip, records its takes and owns one finalized clip —
      the gate is the project format's size; loom R62 / R166).
SY3 — the flow (L4: one flat graph of nodes — one file per node, a rebuildable `graph.json` index of positions, edges and the start
      (loom R74 / R139); a Dialogue or Shot node binds a shot as its sole owner (loom R146); validation is a list, play is the client's).

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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fsio import atomic_write_json, new_id, read_json, read_json_or, utc_now
from .models import registry
from .body import Body
from .origin import JobOrigin
from .shot_recipe import RecipeRun, ShotRecipe, add_run, default_template, stamps_for, step_of

if TYPE_CHECKING:
    from .catalogue import Catalogue
    from .groups import GroupStore
    from .recipes import T2I
    from .workspace import Workspace

WORLD_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = 2                         # D93 (B4): 2 — a version holds a sheet (appearance, outfit, colours, marks) and a label, not one stub
SHOT_SCHEMA_VERSION = 1
FLOW_SCHEMA_VERSION = 1
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ProfileClass = Literal["character", "place", "prop"]
VersionState = Literal["open", "final"]


class StaleWorld(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class VersionLocked(ValueError):
    """D93 (A2): a final profile version refuses new images (→ 423 with the reason)."""


class StaleProfile(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class StaleShot(ValueError):
    """The client's change is based on an older revision (→ 409)."""


class StaleFlow(ValueError):
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
class SheetColour(BaseModel):
    """D93 (B4): a colour bound to what it colours ("#C0392B" + "rain jacket") — the way Generate's Tree prompt binds colours (a hex code
    in front of its object); one without an object is kept on the sheet but not sent (a palette alone is weak)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    object: str = Field("", max_length=80)


SHEET_FIELDS = ("appearance", "outfit", "colours", "marks", "body")


class ProfileVersion(BaseModel):
    """One version of a profile (loom §3.4): its reference set is an album group (`group_id`), its expansion candidates another; `open`
    is editable and expandable, `final` locks the group and the fields (a retake is a new version). `trigger` and `lora` wait for the
    LoRA wave (D25). D93 (B4): the version holds a character sheet — appearance (the look), outfit, bound colours and marks — composed into
    the clause a mention and a linked subject carry (`compose_sheet`); a version is a costume, an age or a look, named by its `label`.
    Schema 1 had one free-text `stub`: it is read as the appearance (the file is rewritten at the next save)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    label: str = Field("", max_length=40)             # D93 (B5): "rain gear", "winter" — the version chip's words; its id when blank
    state: VersionState = "open"
    group_id: str
    candidates_group_id: str | None = None
    hero_asset_id: str | None = None
    appearance: str = Field("", max_length=1000)      # the look: face, hair, build (schema 1's stub)
    outfit: str = Field("", max_length=400)           # the default clothes; a shot may wear another (SubjectShot.outfit)
    colours: list[SheetColour] = Field(default_factory=list, max_length=12)
    marks: str = Field("", max_length=400)            # distinguishing features: a scar, a tattoo, glasses
    trigger: str | None = None
    lora: str | None = None
    body: Body | None = None                      # CA0: a character's body for its Stage dummy (None = the default adult); places and props have none
    anim_ref_asset_id: str | None = None          # CA0 (01 step 2): the animation reference — full body, A-pose, 16:9, plain ground (a prop: alone, ¾ view)
    anim_ref_back_asset_id: str | None = None     # CA0: its optional back view (a shot that starts with the character turned away)
    body_fit_from: str | None = None              # CA1b (D104): the animation reference the body was last fitted to (an asset id); None = by hand
    anim_test_clip_id: str | None = None          # CA0: the last test animation of the reference (a turn on the spot, Wan Animate) — a clip id
    model_asset_id: str | None = None             # D110 (PS2): a prop version's 3D model (a Catalogue mesh, image → mesh, stood upright)
    model_from: str | None = None                 # D110: the image it was made from (an asset id); another reference now marks it stale
    derived_from: str | None = None
    created_at: str = Field(default_factory=utc_now)
    locked_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_stub(cls, data: Any) -> Any:
        """Schema 1 (and a client still sending `stub`): the stub is the appearance; the label defaults to the id."""
        if isinstance(data, dict):
            data = dict(data)
            stub = data.pop("stub", None)
            if isinstance(stub, str) and "appearance" not in data:
                data["appearance"] = stub
            if not str(data.get("label") or "").strip():
                data["label"] = data.get("id") or ""
        return data

    @property
    def stub(self) -> str:
        """The clause a mention of this version carries (loom R112) — since D93 (B4) the composed sheet."""
        return compose_sheet(self)


def _clause(s: str | None) -> str:
    return (s or "").strip().strip(",;").rstrip(".").strip()


_WORN = re.compile(r"(?i)^(wearing|in|dressed|clad)\b")


def compose_sheet(v: ProfileVersion, shot: Any = None, name: str = "", cls: str = "character") -> str:
    """D93 (B4) the composition rule — one clause, its parts joined by ", ": the appearance; the outfit (this shot's when it has one, else
    the sheet's; "wearing …" unless it says so itself); the bound colours as "<HEX> <object>" (those without an object are not sent); the
    marks; this shot's line. Empty → the name (the model then sees only the name, and the card says so). The shared cases in
    tests/fixtures/sheet_compose.json hold the client's copy (frontend generate/sheet.ts) to the same rule. D93 (C6): a place or a prop
    wears nothing — its outfit (the sheet's or a shot's) is not sent; the appearance is its look, the colours and marks apply."""
    worn = cls == "character"
    outfit = (_clause(getattr(shot, "outfit", "") if shot is not None else "") or _clause(v.outfit)) if worn else ""
    colours = ", ".join(f"{c.hex.upper()} {_clause(c.object)}" for c in v.colours if _clause(c.object))
    parts = [_clause(v.appearance), outfit if not outfit or _WORN.match(outfit) else f"wearing {outfit}", colours, _clause(v.marks),
             _clause(getattr(shot, "note", "") if shot is not None else "")]
    return ", ".join(p for p in parts if p) or name.strip()


class Profile(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = PROFILE_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("prf"))
    name: str
    cls: ProfileClass = "character"
    current: str
    versions: list[ProfileVersion] = Field(default_factory=list)
    voice_id: str | None = None                   # CN2: the character's voice (story/voices/) — the Flow's lines of this speaker take it
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def _migrate(cls, data: Any) -> Any:
        """D93 (B4): a schema-1 record reads as schema 2 (each version's stub → its appearance, ProfileVersion._from_stub); nothing is written
        by a read — the next save writes the new shape."""
        if isinstance(data, dict) and int(data.get("schema_version") or 1) < PROFILE_SCHEMA_VERSION:
            data = {**data, "schema_version": PROFILE_SCHEMA_VERSION}
        return data

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
    if p.cls != "character" and any(v.body is not None for v in p.versions):
        raise ValueError("only a character has a body (CA0) — a place or a prop has none")
    if p.cls != "prop" and any(v.model_asset_id is not None for v in p.versions):
        raise ValueError("only a prop has a 3D model (D110) — a character has its body, a place its set")


# ---- shots (SY2, 17 §3c) ------------------------------------------------------------------------------------------------------------
class ShotTake(BaseModel):
    """Something tried for a shot version: an image (a stage-shot result, a Catalogue image) or a clip; the version picks one of each."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: Literal["image", "clip"]
    id: str
    at: str = Field(default_factory=utc_now)


class ShotVersion(BaseModel):
    """One version of a shot (loom R62): where it is made (a stage camera, or nothing — a clip from Animate), the frame and the one clip it
    owns, every take tried; `final` fixes the clip the Flow and the Episode bind (one per version, loom R166). `stage_revision` is the
    stage's revision when the frame or clip was taken — a later edit of the stage makes the version stale (advisory)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    state: VersionState = "open"
    stage_id: str | None = None
    camera_id: str | None = None
    stage_revision: int | None = None
    frame_asset_id: str | None = None
    clip_id: str | None = None
    takes: list[ShotTake] = Field(default_factory=list)
    derived_from: str | None = None
    created_at: str = Field(default_factory=utc_now)
    finalized_at: str | None = None
    recipe: ShotRecipe | None = None              # RC0 (D96, 05 §4): the steps that made the frame and the clip, their runs and stamps (shot_recipe.py)


class Shot(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = SHOT_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("sht"))
    name: str
    owner_node: str | None = None                 # loom R146: exactly one Flow node owns a shot; None = unbound (SY3 binds)
    current: str
    versions: list[ShotVersion] = Field(default_factory=list)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def version(self, vid: str | None = None) -> ShotVersion:
        want = vid or self.current
        v = next((x for x in self.versions if x.id == want), None)
        if v is None:
            raise KeyError(f"shot {self.id} has no version {want}")
        return v


def check_shot(s: Shot) -> None:
    if not s.name.strip():
        raise ValueError("a shot needs a name")
    ids = [v.id for v in s.versions]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("a shot has at least one version and their ids are unique")
    if s.current not in ids:
        raise ValueError(f"current version {s.current} is not one of the versions")
    for v in s.versions:
        if (v.stage_id is None) != (v.camera_id is None):
            raise ValueError(f"version {v.id}: a stage source names both the stage and the camera")


FORMAT_GRID = 32                                  # the video models' size grids (Wan ×16, LTX ×32, 11 §3c): a Full clip is 1920×1088 or 1920×1056


def below_format(clip_w: int, clip_h: int, fmt_w: int, fmt_h: int) -> bool:
    """A clip smaller than the project format beyond the video models' grid (11 §3c: LTX Full is 1920×1088 → 1080, the export crops) —
    D125: a delivery note of the export's checklist, not a reason to refuse *Mark final*."""
    return abs(clip_w - fmt_w) > FORMAT_GRID or abs(clip_h - fmt_h) > FORMAT_GRID


def finalize_reason(v: ShotVersion, clip_w: int | None, clip_h: int | None, fmt_w: int, fmt_h: int) -> str | None:
    """Why the version cannot be marked final, or None. D125 (#6): approval is the author's decision at any size — the version needs its
    clip, and a clip below the project format is the export checklist's note (`below_format`), not a refusal: no video route renders the
    format (Wan HD 1280×720, LTX HD 1280×704, finals at the pose-driven model's size), so the old size gate left nothing to approve. fps
    is conformed at export (D27). `fmt_w` / `fmt_h` stay in the signature for the callers."""
    del fmt_w, fmt_h
    if v.state == "final":
        return None
    if not v.clip_id:
        return "no clip yet — Make clip ▸, then use a take as its clip"
    if clip_w is None or clip_h is None:
        return f"clip {v.clip_id} is gone"
    return None


# ---- the flow (SY3, 17 §3d) ----------------------------------------------------------------------------------------------------------
NodeType = Literal["start", "hub", "dialogue", "choice", "condition", "action", "shot", "jump", "comment"]
NODE_TYPES: tuple[str, ...] = ("start", "hub", "dialogue", "choice", "condition", "action", "shot", "jump", "comment")
VISUAL_TYPES = ("dialogue", "shot")                # the nodes that bind a shot (loom R134)
VISUAL_LABEL = {"dialogue": "Dialogue", "shot": "Shot"}   # D125 (#4): the name of an untitled visual node's shot
FLOW_PORTS = ("out", "then", "else")               # plus "opt:<option id>" on a Choice


class FlowLine(BaseModel):
    """One line of a Dialogue node: the speaker is a profile (its mention), the text the line (loom R152: the subtitles come from these)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    speaker: str | None = None
    text: str = ""
    audio_asset_id: str | None = None             # CN2 (19 §3b): the spoken line — an audio asset, set by the tts job
    audio_text: str | None = None                 # the text it was spoken from (≠ text: stale — voice it again)


class FlowOption(BaseModel):
    """A Choice's option: its own out-port (`opt:<id>`), an optional requirement on a variable, the variables it sets (loom R135)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str = Field(default_factory=lambda: new_id("opt"))
    label: str = ""
    require: dict[str, Any] | None = None          # {var, value}
    set: list[dict[str, Any]] = Field(default_factory=list)   # [{var, value}]


class FlowCondition(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    var: str = ""
    op: Literal["eq", "ne"] = "eq"
    value: bool | str = True


class FlowNode(BaseModel):
    """One node of the flow, one file (loom R139). The fields a type uses: Dialogue `lines` (+ a bound shot), Shot a bound shot, Choice
    `options`, Condition `cond`, Action `set`, Jump `target`, Comment `text`; Start and Hub carry a title. `shot_id` / `shot_version`
    are set by binding only (loom R146: sole ownership)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = FLOW_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("node"))
    type: NodeType = "dialogue"
    title: str = ""
    lines: list[FlowLine] = Field(default_factory=list)
    options: list[FlowOption] = Field(default_factory=list)
    cond: FlowCondition | None = None
    set: list[dict[str, Any]] = Field(default_factory=list)
    target: str | None = None
    text: str = ""
    shot_id: str | None = None
    shot_version: str | None = None
    board_group_id: str | None = None             # D90 (02 §4.2): the node's board — an album group (references, mood, places); its cover on the card
    place_id: str | None = None                   # D93 (C7): where — a Cast place (Dialogue / Shot nodes); Make frame links Generate's scene to it
    speaker_versions: dict[str, str] = Field(default_factory=dict)   # D93 follow-up: a speaker's pinned version (profile id → version id); absent = current — Make frame uses it unless the shot's stage binds another
    colour: str | None = None
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class FlowEdge(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True, populate_by_name=True)
    from_: str = Field(alias="from")
    port: str = "out"
    to: str


class FlowPlacement(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    x: float = 0.0
    y: float = 0.0


class FlowGraph(BaseModel):
    """The thin index (loom R139): where the nodes sit, the edges, the start — rebuilt from the node files when missing or disagreeing."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = FLOW_SCHEMA_VERSION
    nodes: list[FlowPlacement] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    start: str | None = None
    revision: int = 0
    updated_at: str = Field(default_factory=utc_now)


def node_ports(n: FlowNode) -> list[str]:
    """The out-ports a node offers: a Choice one per option, a Condition then / else, a Jump and a Comment none, the rest one."""
    if n.type == "choice":
        return [f"opt:{o.id}" for o in n.options]
    if n.type == "condition":
        return ["then", "else"]
    if n.type in ("jump", "comment"):
        return []
    return ["out"]


def validate_flow(graph: FlowGraph, nodes: dict[str, FlowNode], variables: list[str], shots: dict[str, Shot] | None = None) -> list[dict[str, Any]]:
    """Advisory problems (17 §3d): no Start / several, a Choice without options, a dangling edge or Jump, an edge from a port the node
    does not have, an unreachable node, a visual node without a shot or with a non-final version, a variable nobody declared."""
    out: list[dict[str, Any]] = []
    starts = [n for n in nodes.values() if n.type == "start"]
    if not starts:
        out.append({"code": "no_start", "node_id": None, "message": "no Start node — the play has nowhere to begin"})
    elif len(starts) > 1:
        for n in starts[1:]:
            out.append({"code": "many_starts", "node_id": n.id, "message": "a second Start — one flow has one entry"})
    for e in graph.edges:
        if e.from_ not in nodes or e.to not in nodes:
            out.append({"code": "dangling_edge", "node_id": e.from_ if e.from_ in nodes else None, "message": f"an edge to or from a node that is gone ({e.from_} → {e.to})"})
        elif e.port not in node_ports(nodes[e.from_]):
            out.append({"code": "bad_port", "node_id": e.from_, "message": f"{nodes[e.from_].title or e.from_}: no port {e.port!r}"})
    for n in nodes.values():
        if n.type == "choice" and not n.options:
            out.append({"code": "no_options", "node_id": n.id, "message": f"{n.title or 'a Choice'} has no options"})
        if n.type == "jump" and (not n.target or n.target not in nodes):
            out.append({"code": "dangling_jump", "node_id": n.id, "message": f"{n.title or 'a Jump'} points at nothing"})
        if n.type == "condition" and n.cond and n.cond.var and n.cond.var not in variables:
            out.append({"code": "unknown_var", "node_id": n.id, "message": f"{n.title or 'a Condition'} reads {n.cond.var!r}, not a World variable"})
        for s in n.set:
            if s.get("var") and s["var"] not in variables:
                out.append({"code": "unknown_var", "node_id": n.id, "message": f"{n.title or n.type} sets {s['var']!r}, not a World variable"})
        for o in n.options:
            if o.require and o.require.get("var") and o.require["var"] not in variables:
                out.append({"code": "unknown_var", "node_id": n.id, "message": f"option {o.label!r} requires {o.require['var']!r}, not a World variable"})
            for s in o.set:
                if s.get("var") and s["var"] not in variables:
                    out.append({"code": "unknown_var", "node_id": n.id, "message": f"option {o.label!r} sets {s['var']!r}, not a World variable"})
        if n.type in VISUAL_TYPES:
            if not n.shot_id:
                out.append({"code": "no_shot", "node_id": n.id, "message": f"{n.title or n.type} has no shot — bind or spawn one"})
            elif shots is not None:
                sh = shots.get(n.shot_id)
                if sh is None:
                    out.append({"code": "shot_gone", "node_id": n.id, "message": f"{n.title or n.type}: its shot {n.shot_id} is gone"})
                else:
                    try:
                        v = sh.version(n.shot_version)
                        if v.state != "final":
                            out.append({"code": "shot_open", "node_id": n.id, "message": f"{n.title or n.type}: {sh.name} {v.id} is not final yet (advisory)"})
                    except KeyError:
                        out.append({"code": "shot_gone", "node_id": n.id, "message": f"{n.title or n.type}: {sh.name} has no version {n.shot_version}"})
    # reachability from the start (Jumps count as edges; Comments are never reached and never flagged)
    if starts:
        seen: set[str] = set()
        todo = [starts[0].id]
        while todo:
            cur = todo.pop()
            if cur in seen or cur not in nodes:
                continue
            seen.add(cur)
            for e in graph.edges:
                if e.from_ == cur and e.to in nodes:
                    todo.append(e.to)
            if nodes[cur].type == "jump" and nodes[cur].target in nodes:
                todo.append(nodes[cur].target)   # type: ignore[arg-type]
        for n in nodes.values():
            if n.id not in seen and n.type != "comment":
                out.append({"code": "unreachable", "node_id": n.id, "message": f"{n.title or n.type} cannot be reached from the Start"})
    return out


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
    stub = compose_sheet(version, name=profile.name)                    # D93 (B4): the version's sheet, composed
    for cell in preset_cells(preset):
        for s in range(max(1, int(seeds_per_cell))):
            c = {**cell, "take": (cell["take"] - 1) * max(1, int(seeds_per_cell)) + s + 1}
            recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": f"{stub}. {cell_sentence(c)}.",
                      "width": width, "height": height, "seeds": [0], "refs": [{"asset_id": version.hero_asset_id, "note": profile.name}],
                      "style_id": style_id, "tier": tier}
            origin = {"suite": "story", "surface": "expand", "ref": profile.id, "payload": {"version": version.id, "cell": c, "group_id": group_id, "preset": preset}}
            out.append((recipe, origin))
    return out


BODY_FIT_SURFACE = "body_fit"                    # CA1b (D104): origin.surface of a keypoints job that fits a version's body; payload {version}


def body_fit_origin(pid: str, vid: str) -> JobOrigin:
    return JobOrigin(suite="story", surface=BODY_FIT_SURFACE, ref=pid, payload={"version": vid})


PROP_MODEL_SURFACE = "prop_model"              # D110 (PS2): origin.surface of an image → mesh job made for a prop version; payload {version, from}


def prop_model_origin(pid: str, vid: str, source: str) -> JobOrigin:
    return JobOrigin(suite="story", surface=PROP_MODEL_SURFACE, ref=pid, payload={"version": vid, "from": source})


def model_source(v: ProfileVersion) -> str | None:
    """D110: the image a prop's model is made from — its animation reference (the prop alone, a three-quarter view), else its hero."""
    return v.anim_ref_asset_id or v.hero_asset_id


ANIM_REF_SURFACE = "anim_ref"                    # CA0: origin.surface of an animation-reference job; payload {version, side, group_id}
AnimRefSide = Literal["front", "back"]


def anim_ref_sentence(cls: str, side: str) -> str:
    """CA0 (01 step 2, §10): what an animation reference shows — for a character the whole figure in a neutral A-pose (arms a little away
    from the body, so they do not merge with the torso), centred and padded in the 16:9 frame on a plain ground, the back view the same
    from behind; for a prop the object alone in a three-quarter view."""
    if cls == "prop":
        return ("The object alone, a three-quarter view, the whole object visible and centred with space around it, "
                "on a plain light grey studio background, soft even light, no other objects, no text.")
    view = "seen from directly behind, the back of the figure" if side == "back" else "facing the camera, front view"
    return (f"Full-body character reference, {view}, standing in a neutral A-pose with the arms held a little away from the body and the "
            "feet slightly apart, the whole figure from the top of the head to the feet visible and centred with space around it, "
            "on a plain light grey studio background, soft even light, no props, no other people, no text.")


def plan_anim_ref(profile: Profile, version: ProfileVersion, side: str, variant: str, *, width: int, height: int, count: int, group_id: str,
                  style_id: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """CA0: the T2I jobs that make a version's animation reference — the clay-reference model (as Expand: Klein 9B under `full`, 4B under
    `open`), the version's sheet composed (its colours bound) and its reference set as an @mention (pinned to the version, so its LoRA rides
    along and RC0 stamps it), the reference sentence, one seed each. The results land on the version's candidates page; the first becomes
    the reference while the version has none (the finisher)."""
    if profile.cls == "place":
        raise ValueError("a place has no animation reference — characters and props have one")
    if side == "back" and profile.cls != "character":
        raise ValueError("only a character has a back view")
    spec = expand_spec(variant)
    if spec is None:
        raise ValueError("no model in this build makes an animation reference")
    sheet = compose_sheet(version, name=profile.name, cls=profile.cls)
    lead = f"{sheet}. " if sheet else f"{profile.name}. "
    out = []
    for i in range(max(1, min(4, int(count)))):
        recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": lead + anim_ref_sentence(profile.cls, side),
                  "width": width, "height": height, "seeds": [i], "style_id": style_id, "tier": "draft",
                  "mentions": [{"group_id": "", "name": profile.name, "profile_id": profile.id, "version": version.id}]}
        origin = {"suite": "story", "surface": ANIM_REF_SURFACE, "ref": profile.id, "payload": {"version": version.id, "side": side, "group_id": group_id}}
        out.append((recipe, origin))
    return out


# ---- the store · shots (SY2) ----------------------------------------------------------------------------------------------------------
class _ShotMixin:
    """StoryStore's shot records (kept beside the profiles; one file per shot)."""

    dir: Path

    def shot_path(self, sid: str) -> Path:
        return self.dir / "shots" / f"{sid}.json"

    def shot(self, sid: str) -> Shot | None:
        p = self.shot_path(sid)
        return Shot.model_validate(read_json(p)) if p.is_file() else None

    def shots(self) -> list[Shot]:
        d = self.dir / "shots"
        if not d.is_dir():
            return []
        out = [Shot.model_validate(read_json(p)) for p in d.glob("sht_*.json")]
        return sorted(out, key=lambda s: s.updated_at, reverse=True)

    def save_shot(self, s: Shot) -> None:
        (self.dir / "shots").mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.shot_path(s.id), s.model_dump())

    def create_shot(self, name: str, *, stage_id: str | None = None, camera_id: str | None = None, stage_revision: int | None = None,
                    clip_id: str | None = None, frame_asset_id: str | None = None) -> Shot:
        """A shot with version 1 pointing at a stage camera and / or holding a clip or a frame (each given one is also its first take)."""
        name = name.strip()
        if not name:
            raise ValueError("a shot needs a name")
        takes = [ShotTake(kind="image", id=frame_asset_id)] if frame_asset_id else []
        if clip_id:
            takes.append(ShotTake(kind="clip", id=clip_id))
        v = ShotVersion(id="v1", stage_id=stage_id, camera_id=camera_id, stage_revision=stage_revision if stage_id else None, frame_asset_id=frame_asset_id, clip_id=clip_id, takes=takes)
        s = Shot(name=name, current="v1", versions=[v])
        check_shot(s)
        self.save_shot(s)
        return s

    def patch_shot(self, sid: str, data: dict[str, Any]) -> Shot:
        """Name, owner node, the current version, and an open version's frame / clip from a client body based on `revision` (409 when stale)."""
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleShot(f"the shot is at revision {cur.revision}, the change is based on {base} — reload it first")
        versions = [v.model_copy() for v in cur.versions]
        for patch in data.get("versions") or []:
            v = next((x for x in versions if x.id == patch.get("id")), None)
            if v is None:
                raise ValueError(f"no version {patch.get('id')!r}")
            if v.state != "open" and any(k in patch for k in ("frame_asset_id", "clip_id", "stage_id", "camera_id")):
                raise ValueError(f"version {v.id} is final — its frame and clip are fixed; make a new version")
            for k in ("frame_asset_id", "clip_id", "stage_id", "camera_id", "stage_revision"):
                if k in patch:
                    setattr(v, k, patch[k])
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in ("name", "current", "owner_node")}, "versions": [v.model_dump() for v in versions],
                  "id": sid, "schema_version": SHOT_SCHEMA_VERSION, "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        s = Shot.model_validate(merged)
        check_shot(s)
        self.save_shot(s)
        return s

    def set_source(self, sid: str, vid: str, stage_id: str | None, camera_id: str | None, stage_revision: int | None) -> Shot:
        """D125 (S11): an open version pointed at a stage camera (*Link a stage camera…*, *Block it on a stage…*, Animate's *Use this camera
        for <shot>*), or at none; its stills and clips then come back by the camera (record_stage_result). The recipe's default template
        follows the source (RC0: `stage` for a stage camera's shot) unless one was chosen."""
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        v = cur.version(vid)
        if v.state != "open":
            raise ValueError(f"{cur.name} {vid} is final — make a new version to change its source")
        if (stage_id is None) != (camera_id is None):
            raise ValueError("a stage source names both the stage and the camera")
        upd = {"stage_id": stage_id, "camera_id": camera_id, "stage_revision": stage_revision if stage_id else None}
        versions = [x.model_copy(update=upd) if x.id == vid else x for x in cur.versions]
        s = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_shot(s)
        return s

    def new_shot_version(self, sid: str) -> Shot:
        """A copy of the current version's pointers (the source, the frame and the clip — no files, no takes), open, now the current one."""
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        src = cur.version()
        n = max(int(v.id[1:]) for v in cur.versions if v.id[1:].isdigit()) + 1
        v = ShotVersion(id=f"v{n}", stage_id=src.stage_id, camera_id=src.camera_id, stage_revision=src.stage_revision, frame_asset_id=src.frame_asset_id,
                        clip_id=src.clip_id, derived_from=src.id, recipe=src.recipe.model_copy(deep=True) if src.recipe else None)   # RC0: the plan and its history carry over
        s = cur.model_copy(update={"versions": [*cur.versions, v], "current": v.id, "revision": cur.revision + 1, "updated_at": utc_now()})
        check_shot(s)
        self.save_shot(s)
        return s

    def add_take(self, sid: str, vid: str, kind: str, ref_id: str, *, use: bool | None = None, stage_revision: int | None = None) -> Shot:
        """Record a take on an open version; `use` makes it the frame or the clip (None: only when that slot is still empty)."""
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        v = cur.version(vid)
        if v.state != "open":
            raise ValueError(f"version {vid} is final")
        if kind not in ("image", "clip"):
            raise ValueError("a take is an image or a clip")
        takes = [t for t in v.takes if not (t.kind == kind and t.id == ref_id)] + [ShotTake(kind=kind, id=ref_id)]   # type: ignore[arg-type]
        upd: dict[str, Any] = {"takes": takes}
        slot = "frame_asset_id" if kind == "image" else "clip_id"
        if use or (use is None and getattr(v, slot) is None):
            upd[slot] = ref_id
            if stage_revision is not None:
                upd["stage_revision"] = stage_revision
        versions = [x.model_copy(update=upd) if x.id == vid else x for x in cur.versions]
        s = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_shot(s)
        return s

    def record_run(self, sid: str, vid: str, recipe: dict[str, Any], *, outputs: list[str], job_id: str | None, seconds: float | None,
                   stage_id: str | None = None, stage_revision: int | None = None) -> Shot | None:
        """RC0 (D96): a job's run on the version's step for it — the resolved recipe, its stamps, its outputs and its wall time. None when the
        version is final or no step takes the job's kind (nothing recorded)."""
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        v = cur.version(vid)
        where = step_of(recipe, v.frame_asset_id)
        if v.state != "open" or where is None:
            return None
        stamps = stamps_for(recipe, frame_asset_id=v.frame_asset_id, stage_id=stage_id, stage_revision=stage_revision, story=self)
        run = RecipeRun(job_id=job_id, kind=str(recipe.get("kind") or "?"), settings=recipe, stamps=stamps, outputs=outputs,
                        seconds=round(seconds, 1) if seconds is not None else None)
        r = add_run(v.recipe, default_template(v.stage_id), where[0], where[1], run)
        versions = [x.model_copy(update={"recipe": r}) if x.id == vid else x for x in cur.versions]
        s = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_shot(s)
        return s

    def set_template(self, sid: str, vid: str, template: str) -> Shot:
        """RC0: the version's recipe follows another template (its runs stay)."""
        from .shot_recipe import TEMPLATES
        if template not in TEMPLATES:
            raise ValueError(f"no recipe template {template!r}")
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        v = cur.version(vid)
        r = (v.recipe or ShotRecipe()).model_copy(update={"template": template})
        versions = [x.model_copy(update={"recipe": r}) if x.id == vid else x for x in cur.versions]
        s = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_shot(s)
        return s

    def finalize_shot(self, sid: str, vid: str, clip_size: tuple[int, int] | None, fmt: tuple[int, int]) -> Shot:
        cur = self.shot(sid)
        if cur is None:
            raise KeyError(sid)
        v = cur.version(vid)
        if v.state == "final":
            return cur
        why = finalize_reason(v, clip_size[0] if clip_size else None, clip_size[1] if clip_size else None, fmt[0], fmt[1])
        if why:
            raise ValueError(why)
        versions = [x.model_copy(update={"state": "final", "finalized_at": utc_now()}) if x.id == vid else x for x in cur.versions]
        s = cur.model_copy(update={"versions": versions, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_shot(s)
        return s

    def delete_shot(self, sid: str) -> bool:
        p = self.shot_path(sid)
        if not p.is_file():
            return False
        p.unlink()
        return True

    def record_stage_result(self, stage_id: str, camera_id: str, kind: str, ref_id: str, stage_revision: int | None,
                            run: dict[str, Any] | None = None, skip: str | None = None, use: bool | None = None) -> list[Shot]:
        """A stage camera's result (ST3's frame, ST4's clip) becomes a take of every shot whose current open version points at that
        camera — and its frame / clip when that slot is still empty (17 §3c: ST4's "Story L3 link"). RC0: with `run` ({recipe, job_id,
        seconds}), the job is recorded on the version's recipe too. `use` False: a take that never fills the slot by itself (a final's
        assembly, D125)."""
        out = []
        for s in self.shots():
            v = s.version()
            if v.state == "open" and v.stage_id == stage_id and v.camera_id == camera_id and s.id != skip:   # skip: the shot the job was made for records it itself
                s = self.add_take(s.id, v.id, kind, ref_id, use=use, stage_revision=stage_revision)
                if run is not None:
                    s = self.record_run(s.id, v.id, run["recipe"], outputs=[ref_id], job_id=run.get("job_id"), seconds=run.get("seconds"),
                                        stage_id=stage_id, stage_revision=stage_revision) or s
                out.append(s)
        return out


# ---- Cast readiness (D125 S5, proto01_UIcomp 04 §3.3) ----------------------------------------------------------------------------
class CastUse(BaseModel):
    """A shot that uses a Cast profile: how (a Dialogue line's speaker, the node's place, a stage figure or a mesh bound to it) and the
    route of its current version (the recipe template), which say what the shot needs from the profile's version (Cast's readiness row)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    shot_id: str
    name: str
    version: str
    route: str
    how: list[Literal["speaker", "place", "figure", "prop"]]


def cast_uses(shots: list[Shot], nodes: dict[str, FlowNode], stages: dict[str, Any]) -> dict[str, list[CastUse]]:
    """Every profile's uses, by the shots' current versions: the node that binds the shot (its lines' speakers, its place) and the version's
    stage (a visible object bound to a profile — a figure, else a prop's mesh). `stages` maps a stage id to its record."""
    by_shot = {n.shot_id: n for n in nodes.values() if n.shot_id}
    out: dict[str, list[CastUse]] = {}
    for s in shots:
        v = s.version()
        how: dict[str, set[str]] = {}
        n = by_shot.get(s.id) or (nodes.get(s.owner_node) if s.owner_node else None)
        if n is not None:
            for line in n.lines:
                if line.speaker:
                    how.setdefault(line.speaker, set()).add("speaker")
            if n.place_id:
                how.setdefault(n.place_id, set()).add("place")
        st = stages.get(v.stage_id) if v.stage_id else None
        for o in getattr(st, "objects", []) or []:
            if o.profile_id and o.visible:
                how.setdefault(o.profile_id, set()).add("figure" if o.kind == "mannequin" else "prop")
        route = (v.recipe.template if v.recipe else None) or default_template(v.stage_id)
        for pid, h in how.items():
            out.setdefault(pid, []).append(CastUse(shot_id=s.id, name=s.name, version=v.id, route=route, how=sorted(h)))   # type: ignore[arg-type]
    return out


# ---- makers in context (D90, 02 §5) ----------------------------------------------------------------------------------------------
FOR_SHOT = "for_shot"                             # origin.surface of a job made for a shot version ("Make frame ▸" / "Make clip ▸"); payload {shot_id, version}


def for_shot_target(payload: dict[str, Any] | None) -> tuple[str, str] | None:
    """The shot and version a for-shot origin names, or None when its payload does not."""
    p = payload or {}
    sid, vid = p.get("shot_id"), p.get("version")
    return (sid, vid) if isinstance(sid, str) and sid and isinstance(vid, str) and vid else None


def check_for_shot(store: StoryStore, payload: dict[str, Any] | None) -> Shot:
    """At submit: the results of a for-shot job become takes of an open version — the shot and the version exist, the version is open."""
    t = for_shot_target(payload)
    if t is None:
        raise ValueError("a job made for a shot names the shot and its version (origin.payload {shot_id, version})")
    s = store.shot(t[0])
    if s is None:
        raise ValueError(f"shot {t[0]} does not exist")
    try:
        v = s.version(t[1])
    except KeyError as e:
        raise ValueError(str(e.args[0])) from None
    if v.state != "open":
        raise ValueError(f"{s.name} {v.id} is final — its frame and clip are fixed; make a new version for more takes")
    return s


# ---- the store ---------------------------------------------------------------------------------------------------------------------
class _FlowMixin:
    """StoryStore's flow records: one file per node under `story/flow/nodes/`, the index `story/flow/graph.json`."""

    dir: Path

    @property
    def flow_dir(self) -> Path:
        return self.dir / "flow"

    def node_path(self, nid: str) -> Path:
        return self.flow_dir / "nodes" / f"{nid}.json"

    def flow_node(self, nid: str) -> FlowNode | None:
        p = self.node_path(nid)
        return FlowNode.model_validate(read_json(p)) if p.is_file() else None

    def flow_nodes(self) -> dict[str, FlowNode]:
        d = self.flow_dir / "nodes"
        if not d.is_dir():
            return {}
        out = {}
        for p in d.glob("node_*.json"):
            n = FlowNode.model_validate(read_json(p))
            out[n.id] = n
        return out

    def save_node(self, n: FlowNode) -> None:
        (self.flow_dir / "nodes").mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.node_path(n.id), n.model_dump())

    def save_graph(self, g: FlowGraph) -> None:
        self.flow_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.flow_dir / "graph.json", g.model_dump(by_alias=True))

    def flow_graph(self, nodes: dict[str, FlowNode] | None = None) -> FlowGraph:
        """The index, made to agree with the node files: a node without a placement gets one (laid out in a row after the others), a
        placement or edge of a gone node is dropped, the start is the first Start node when the index names none that exists."""
        nodes = self.flow_nodes() if nodes is None else nodes
        p = self.flow_dir / "graph.json"
        g = FlowGraph.model_validate(read_json_or(p, {}))
        known = {pl.id for pl in g.nodes}
        placements = [pl for pl in g.nodes if pl.id in nodes]
        changed = len(placements) != len(g.nodes)
        for i, nid in enumerate(sorted(n for n in nodes if n not in known)):
            placements.append(FlowPlacement(id=nid, x=40.0 + 220.0 * (len(placements) % 6), y=40.0 + 140.0 * (len(placements) // 6)))
            changed = True
        edges = [e for e in g.edges if e.from_ in nodes and e.to in nodes]
        changed = changed or len(edges) != len(g.edges)
        start = g.start if g.start in nodes and nodes[g.start].type == "start" else next((n.id for n in sorted(nodes.values(), key=lambda n: n.created_at) if n.type == "start"), None)
        changed = changed or start != g.start
        if changed:
            g = g.model_copy(update={"nodes": placements, "edges": edges, "start": start, "revision": g.revision + (1 if p.is_file() else 0), "updated_at": utc_now()})
            self.save_graph(g)
        return g

    def create_node(self, type_: str, title: str = "", x: float = 0.0, y: float = 0.0, *, with_shot: bool = True, **fields: Any) -> FlowNode:
        """A node and its placement. D125 (#4): a Dialogue or Shot node is made with its shot — named after the node, owned by it
        (`with_shot` False: none, for a shot bound later)."""
        if type_ not in NODE_TYPES:
            raise ValueError(f"unknown node type {type_!r}; one of {', '.join(NODE_TYPES)}")
        fields = {k: v for k, v in fields.items() if k in ("lines", "options", "cond", "set", "target", "text", "colour")}
        n = FlowNode(type=type_, title=title.strip() or {"start": "Start", "hub": "Hub", "comment": "Note"}.get(type_, ""), **fields)
        g = self.flow_graph()                                        # before the file exists, so the index does not place it twice
        self.save_node(n)
        g = g.model_copy(update={"nodes": [*[p for p in g.nodes if p.id != n.id], FlowPlacement(id=n.id, x=x, y=y)], "start": g.start or (n.id if type_ == "start" else None),
                                 "revision": g.revision + 1, "updated_at": utc_now()})
        self.save_graph(g)
        if type_ in VISUAL_TYPES and with_shot:
            n = self._own_shot(n)
        return n

    def _own_shot(self, n: FlowNode) -> FlowNode:
        """D125 (#4): a new shot owned by the visual node, named after it."""
        sh = self.create_shot(n.title.strip() or VISUAL_LABEL[n.type])      # type: ignore[attr-defined]
        n, _ = self.bind_shot(n.id, sh.id)
        return n

    def patch_node(self, nid: str, data: dict[str, Any]) -> FlowNode:
        """A node's own fields from a client body based on `revision` (409 when stale); the bound shot changes through bind / unbind only."""
        cur = self.flow_node(nid)
        if cur is None:
            raise KeyError(nid)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleFlow(f"the node is at revision {cur.revision}, the change is based on {base} — reload it first")
        keep = ("type", "title", "lines", "options", "cond", "set", "target", "text", "colour", "board_group_id", "place_id", "speaker_versions")
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in keep}, "id": nid, "schema_version": FLOW_SCHEMA_VERSION,
                  "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        n = FlowNode.model_validate(merged)
        if "lines" in data:                                             # CN2: a client that did not see the tts job's stamp keeps it on a line whose text it left alone
            for i, ln in enumerate(n.lines):
                if i < len(cur.lines) and ln.audio_asset_id is None and cur.lines[i].audio_asset_id and cur.lines[i].text == ln.text:
                    ln.audio_asset_id, ln.audio_text = cur.lines[i].audio_asset_id, cur.lines[i].audio_text
        if n.type not in NODE_TYPES:
            raise ValueError(f"unknown node type {n.type!r}")
        self.save_node(n)
        g = self.flow_graph()                                        # the start may move with the type; an edge from a port that is gone goes too
        edges = [e for e in g.edges if e.from_ != nid or e.port in node_ports(n)]
        if len(edges) != len(g.edges):
            self.save_graph(g.model_copy(update={"edges": edges, "revision": g.revision + 1, "updated_at": utc_now()}))
        if n.type in VISUAL_TYPES and n.shot_id and n.title != cur.title:   # D125 (#4): the shot follows the node's title until renamed by hand
            sh = self.shot(n.shot_id)                                # type: ignore[attr-defined]
            if sh is not None and sh.owner_node == nid and sh.name == (cur.title.strip() or VISUAL_LABEL.get(cur.type, "")) and (n.title.strip() or VISUAL_LABEL[n.type]):
                self.patch_shot(sh.id, {"name": n.title.strip() or VISUAL_LABEL[n.type]})   # type: ignore[attr-defined]
        if n.type in VISUAL_TYPES and not n.shot_id and cur.type not in VISUAL_TYPES:   # turned visual: it gets its shot
            n = self._own_shot(n)
        return n

    def set_line_audio(self, nid: str, index: int, asset_id: str | None, text: str | None) -> FlowNode:
        """CN2: the tts job's stamp on a line (the audio asset and the text it spoke) — server-side, no revision bump: the line's words are
        the client's, the voice is the job's (patch_node keeps the stamp a client did not see)."""
        cur = self.flow_node(nid)
        if cur is None:
            raise KeyError(nid)
        if not 0 <= index < len(cur.lines):
            raise KeyError(f"{nid} has no line {index}")
        lines = [ln.model_copy() for ln in cur.lines]
        lines[index].audio_asset_id, lines[index].audio_text = asset_id, text
        n = cur.model_copy(update={"lines": lines, "updated_at": utc_now()})
        self.save_node(n)
        return n

    def clear_voice(self, vid: str) -> list[Profile]:
        """CN2: a deleted voice leaves every profile that had it."""
        out = []
        for p in self.profiles():
            if p.voice_id == vid:
                out.append(self.patch_profile(p.id, {"voice_id": None}))
        return out

    def delete_node(self, nid: str, delete_shot: bool = False) -> Shot | None:
        """The node file goes, its placement and edges with it; its shot is released (not deleted) and returned — D125 (#4): or deleted too
        with `delete_shot` (its files stay in the Catalogue), and None returned."""
        cur = self.flow_node(nid)
        if cur is None:
            raise KeyError(nid)
        released = None
        if cur.shot_id:
            sh = self.shot(cur.shot_id)                           # type: ignore[attr-defined]
            if sh is not None and sh.owner_node == nid:
                if delete_shot:
                    self.delete_shot(sh.id)                       # type: ignore[attr-defined]
                else:
                    released = self.patch_shot(sh.id, {"owner_node": None})   # type: ignore[attr-defined]
        self.node_path(nid).unlink()
        self.flow_graph()
        return released

    def put_graph(self, data: dict[str, Any]) -> FlowGraph:
        """Positions, edges and the start from a client body based on `revision` (409 when stale); edges must join existing nodes on
        ports they offer."""
        nodes = self.flow_nodes()
        cur = self.flow_graph(nodes)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleFlow(f"the graph is at revision {cur.revision}, the change is based on {base} — reload it first")
        placements = [FlowPlacement.model_validate(p) for p in data.get("nodes", [pl.model_dump() for pl in cur.nodes])]
        placements = [p for p in placements if p.id in nodes]
        for nid in nodes:
            if not any(p.id == nid for p in placements):
                placements.append(next((p for p in cur.nodes if p.id == nid), FlowPlacement(id=nid)))
        edges = [FlowEdge.model_validate(e) for e in data.get("edges", [e.model_dump(by_alias=True) for e in cur.edges])]
        for e in edges:
            if e.from_ not in nodes or e.to not in nodes:
                raise ValueError(f"edge {e.from_} → {e.to}: a node is missing")
            if e.port not in node_ports(nodes[e.from_]):
                raise ValueError(f"edge from {e.from_}: no port {e.port!r}")
        seen: set[tuple[str, str]] = set()
        kept: list[FlowEdge] = []
        for e in edges:                                           # one edge per out-port (a port leads to one node)
            if (e.from_, e.port) in seen:
                continue
            seen.add((e.from_, e.port))
            kept.append(e)
        start = data.get("start", cur.start)
        if start is not None and (start not in nodes or nodes[start].type != "start"):
            raise ValueError("the start must be a Start node")
        g = cur.model_copy(update={"nodes": placements, "edges": kept, "start": start, "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_graph(g)
        return g

    def bind_shot(self, nid: str, shot_id: str, version: str | None = None) -> tuple[FlowNode, Shot]:
        """A visual node takes a shot as its sole owner (loom R146): an unbound shot, or re-selecting a version of its own."""
        n = self.flow_node(nid)
        if n is None:
            raise KeyError(nid)
        if n.type not in VISUAL_TYPES:
            raise ValueError(f"a {n.type} node does not bind a shot")
        sh = self.shot(shot_id)                                   # type: ignore[attr-defined]
        if sh is None:
            raise KeyError(shot_id)
        if sh.owner_node and sh.owner_node != nid:
            raise ValueError(f"{sh.name} is owned by another node — duplicate it into a new shot (loom R23 / R146)")
        v = sh.version(version)
        if n.shot_id and n.shot_id != shot_id:
            old = self.shot(n.shot_id)                            # type: ignore[attr-defined]
            if old is not None and old.owner_node == nid:
                self.patch_shot(old.id, {"owner_node": None})     # type: ignore[attr-defined]
        if sh.owner_node != nid:
            sh = self.patch_shot(sh.id, {"owner_node": nid})      # type: ignore[attr-defined]
        n = n.model_copy(update={"shot_id": shot_id, "shot_version": v.id, "revision": n.revision + 1, "updated_at": utc_now()})
        self.save_node(n)
        return n, sh

    def unbind_shot(self, nid: str) -> tuple[FlowNode, Shot | None]:
        n = self.flow_node(nid)
        if n is None:
            raise KeyError(nid)
        released = None
        if n.shot_id:
            sh = self.shot(n.shot_id)                             # type: ignore[attr-defined]
            if sh is not None and sh.owner_node == nid:
                released = self.patch_shot(sh.id, {"owner_node": None})   # type: ignore[attr-defined]
        n = n.model_copy(update={"shot_id": None, "shot_version": None, "revision": n.revision + 1, "updated_at": utc_now()})
        self.save_node(n)
        return n, released


class StoryStore(_ShotMixin, _FlowMixin):
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

    def create_profile(self, name: str, cls: ProfileClass, groups: GroupStore, hero_asset_id: str | None = None, stub: str = "", **sheet: Any) -> Profile:
        """A profile with version 1: its reference set is a new album group named after it; the hero (when given) moves onto that page
        as its cover and first reference. D93 (B4): `sheet` holds the version's appearance / outfit / colours / marks / label; `stub` is
        the appearance (the schema-1 word, still taken)."""
        name = name.strip()
        if not name:
            raise ValueError("a profile needs a name")
        fields = {k: x for k, x in sheet.items() if k in (*SHEET_FIELDS, "label") and x is not None}
        fields.setdefault("appearance", stub.strip())                    # D93 (A9): empty by default — the name alone describes nothing
        ProfileVersion.model_validate({"id": "v1", "group_id": "-", **fields})   # a bad colour is refused before the group is made
        g = groups.create(f"{name} · v1")
        if hero_asset_id:
            groups.move([("asset", hero_asset_id)], g.id)
            groups.update(g.id, cover_id=hero_asset_id)
        v = ProfileVersion.model_validate({"id": "v1", "group_id": g.id, "hero_asset_id": hero_asset_id, **fields})
        p = Profile(name=name, cls=cls, current="v1", versions=[v])
        check_profile(p)
        self.save_profile(p)
        return p

    def patch_profile(self, pid: str, data: dict[str, Any]) -> Profile:
        """Name, class, the current version, and an open version's sheet / hero from a client body based on `revision` (409 when stale).
        D93 (B4): a version's sheet fields (`stub` is taken as the appearance) are read-only once it is final; its label is not (a name, not
        the look)."""
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
            patch = {("appearance" if k == "stub" else k): x for k, x in patch.items()}
            if v.state != "open" and any(k in patch for k in (*SHEET_FIELDS, "hero_asset_id")):
                raise ValueError(f"version {v.id} is locked — its fields are read-only; make a new version")
            i = versions.index(v)
            versions[i] = ProfileVersion.model_validate({**v.model_dump(), **{k: patch[k] for k in (*SHEET_FIELDS, "hero_asset_id", "label") if k in patch}})
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in ("name", "cls", "current", "voice_id")}, "versions": [v.model_dump() for v in versions],
                  "id": pid, "schema_version": PROFILE_SCHEMA_VERSION, "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        p = Profile.model_validate(merged)
        check_profile(p)
        self.save_profile(p)
        return p

    def set_anim_ref(self, pid: str, vid: str, side: str, asset_id: str | None, *, only_if_empty: bool = False) -> Profile | None:
        """CA0: a version's animation reference (front) or back view — the author's pick, or the first result of a make (`only_if_empty`).
        No revision guard and a final version takes it too, like its LoRA: the reference is the version's product, not an edit of its sheet.
        None when `only_if_empty` and the slot is taken."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        field = "anim_ref_back_asset_id" if side == "back" else "anim_ref_asset_id"
        versions = [v.model_copy() for v in cur.versions]
        v = next((x for x in versions if x.id == vid), None)
        if v is None:
            raise KeyError(f"no version {vid!r}")
        if only_if_empty and getattr(v, field):
            return None
        if side == "back" and cur.cls != "character":
            raise ValueError("only a character has a back view")
        setattr(v, field, asset_id)
        p = Profile.model_validate({**cur.model_dump(), "versions": [x.model_dump() for x in versions], "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def set_model(self, pid: str, vid: str, asset_id: str | None, source: str | None) -> Profile:
        """D110 (PS2): a prop version's 3D model and the image it was made from (None clears both). A product of the version like its
        animation reference: no revision guard, a final version takes it too."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        if cur.cls != "prop":
            raise ValueError("only a prop has a 3D model")
        versions = [v.model_copy() for v in cur.versions]
        v = next((x for x in versions if x.id == vid), None)
        if v is None:
            raise KeyError(f"no version {vid!r}")
        v.model_asset_id, v.model_from = asset_id, (source if asset_id else None)
        p = Profile.model_validate({**cur.model_dump(), "versions": [x.model_dump() for x in versions], "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def set_fitted_body(self, pid: str, vid: str, body: Body, asset_id: str) -> Profile:
        """CA1b (D104): the version's body fitted to its animation reference (SDPose's proportions). Like the reference itself, a product of the
        version (no revision guard, a final version too)."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        versions = [v.model_copy() for v in cur.versions]
        v = next((x for x in versions if x.id == vid), None)
        if v is None:
            raise KeyError(f"no version {vid!r}")
        v.body, v.body_fit_from = body, asset_id
        p = Profile.model_validate({**cur.model_dump(), "versions": [x.model_dump() for x in versions], "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def set_anim_test(self, pid: str, vid: str, clip_id: str | None) -> Profile:
        """CA0: the version's latest test animation (a clip). No revision guard, a final version too (a product, like its reference)."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        versions = [v.model_copy() for v in cur.versions]
        v = next((x for x in versions if x.id == vid), None)
        if v is None:
            raise KeyError(f"no version {vid!r}")
        v.anim_test_clip_id = clip_id
        p = Profile.model_validate({**cur.model_dump(), "versions": [x.model_dump() for x in versions], "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def version_of_album(self, gid: str) -> tuple[Profile, ProfileVersion] | None:
        """D122: the Cast version whose reference set is this album page, if any (an album trained on goes to its version)."""
        for p in self.profiles():
            for v in p.versions:
                if v.group_id == gid:
                    return p, v
        return None

    def set_version_lora(self, pid: str, vid: str, lora: str | None, trigger: str | None) -> Profile:
        """LT2: the trainer's promotion (and a delete's clearing) — server-side, no revision guard; a locked version takes it too (the LoRA is
        the version's product, not an edit of its reference set)."""
        cur = self.profile(pid)
        if cur is None:
            raise KeyError(pid)
        versions = [v.model_copy() for v in cur.versions]
        v = next((x for x in versions if x.id == vid), None)
        if v is None:
            raise KeyError(f"no version {vid!r}")
        v.lora, v.trigger = lora, trigger
        p = Profile.model_validate({**cur.model_dump(), "versions": [x.model_dump() for x in versions], "revision": cur.revision + 1, "updated_at": utc_now()})
        self.save_profile(p)
        return p

    def clear_lora(self, lid: str) -> list[Profile]:
        """Every version pointing at a deleted LoRA loses its slot (the trigger stays — a retrain reuses it)."""
        out = []
        for p in self.profiles():
            if any(v.lora == lid for v in p.versions):
                for v in p.versions:
                    if v.lora == lid:
                        out.append(self.set_version_lora(p.id, v.id, None, v.trigger))
        return out

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
        v = ProfileVersion.model_validate({**src.model_dump(include=set(SHEET_FIELDS)), "id": f"v{n}", "group_id": g.id,   # D93 (B4): the sheet copied, a label of its own
                                           "hero_asset_id": g.cover_id if src.hero_asset_id else None, "derived_from": src.id})
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

    def ensure_candidates(self, pid: str, vid: str | None, groups: GroupStore) -> tuple[Profile, str, bool]:
        """The version's candidates page — made on first use (Expand, a casting run from Generate, "as a candidate"): (profile, its id, made)."""
        p = self.profile(pid)
        if p is None:
            raise KeyError(pid)
        v = p.version(vid)
        if v.candidates_group_id and v.candidates_group_id in groups.groups:
            return p, v.candidates_group_id, False
        gid = groups.create(f"{p.name} · {v.id} · candidates").id
        return self.set_candidates(pid, v.id, gid), gid, True

    def add_assets(self, pid: str, vid: str | None, ids: list[str], role: Literal["hero", "reference", "candidate"], groups: GroupStore,
                   cat: Catalogue) -> dict[str, Any]:
        """D93 (A2) "Add to character ▸": images into a version — the hero (it joins the reference set as its cover), the reference set or the
        candidates page. An image from Unprocessed or from this version's own candidates page moves; one that lives on any other page (an
        album page, another profile's set) is copied and the original stays where it is — said in the reply, never taken silently. A final
        version refuses (VersionLocked)."""
        p = self.profile(pid)
        if p is None:
            raise KeyError(pid)
        v = p.version(vid)
        if v.state != "open":
            raise VersionLocked(f"{p.name} {v.id} is final — its look is fixed; make a new version to add to it")
        if not ids:
            raise ValueError("no images given")
        if role == "hero" and len(ids) != 1:
            raise ValueError("one image is the hero")
        for aid in ids:
            r = cat.get(aid)
            if r is None or r.trashed_at is not None or r.kind != "image":
                raise ValueError(f"{aid} is not an image in the Catalogue")
        made = False
        if role == "candidate":
            p, target, made = self.ensure_candidates(pid, v.id, groups)
            v = p.version(v.id)
        else:
            target = v.group_id
        own = {v.candidates_group_id} - {None, target}
        out, moved, copied, already = [], [], {}, []
        for aid in dict.fromkeys(ids):
            where = groups.parent.get(("asset", aid))
            if where == target:
                already.append(aid); out.append(aid)
            elif where is None or where in own:
                groups.move([("asset", aid)], target)
                moved.append(aid); out.append(aid)
            else:
                dup = cat.duplicate(aid)
                if dup is None:
                    raise ValueError(f"{aid} could not be copied")
                groups.move([("asset", dup.id)], target)
                copied[aid] = dup.id; out.append(dup.id)
        if role == "hero":
            groups.update(target, cover_id=out[0])
            versions = [x.model_copy(update={"hero_asset_id": out[0]}) if x.id == v.id else x for x in p.versions]
            p = p.model_copy(update={"versions": versions, "revision": p.revision + 1, "updated_at": utc_now()})
            self.save_profile(p)
        return {"profile": p, "group_id": target, "role": role, "asset_ids": out, "moved": moved, "copied": copied, "already": already, "made_page": made}

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
