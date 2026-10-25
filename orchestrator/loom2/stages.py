"""Stages (P13 / ST1, 16 §12): a 3D blocking as a document `stages/<id>.json` — objects (figures, sets, props, image planes, meshes)
with transforms and poses, cameras in photographic units (focal mm on a 36 mm sensor), keyframes (ST4) and the passes rendered from
a camera (ST3) — assets by id, never embedded. Writes go through fsio; `revision` guards a PUT like a document's stack (409 on a
stale base). The frontend's engine (suites/stage/) renders from this document and never keeps project data of its own.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .body import Body
from .fsio import atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

STAGE_SCHEMA_VERSION = 3                           # 2 (D108): a set is architecture; schema 1's set blocks are read as props;
                                                   # 3 (proto01_UIcast CS1, S3): a figure's body is of the adult dummy (body.rebase_body)
# D108: the blocks schema 1's set presets carried, now props of their own — (size w h d, foot x y z) in the set's frame (builders.ts)
SET_BLOCKS_V1: dict[str, list[tuple[tuple[float, float, float], tuple[float, float, float]]]] = {
    "room": [((1.2, 0.8, 0.8), (1.9, 0.0, -1.8)), ((0.45, 0.48, 0.45), (0.0, 0.0, 0.0))],
    "street": [((1.0, 2.2, 0.4), (-3.2, 0.0, -2.0))],
}
Kind = Literal["mannequin", "set", "prop", "plane", "mesh", "light"]


def _level(obj: "StageObject", cam: "StageCamera | None", relief_path: Path | None) -> None:
    """SC3d: a picture set laid level by the floor fitted to its relief (`relief.frame_of_glb`, at the lift the engine gives it) — the set
    turned and raised (its transform), its picture camera where the picture was taken in that frame (pitched and, SC3f, rolled as the
    photograph's camera was); without a relief, too little floor or too steep a one, as it came (the floor's lift alone). SC3e: the camera looks at the
    distance whose depth pass holds the picture's depths (`relief.subject_distance`; 1 m when the relief cannot say)."""
    from .relief import frame_of_glb
    level, subject = frame_of_glb(relief_path, -(obj.floor_y if obj.floor_y is not None else -1.0)) if relief_path is not None else (None, None)
    obj.transform = Transform(pos=list(level["pos"]), rot=list(level["rot"]), scale=[1.0, 1.0, 1.0]) if level else Transform()
    obj.level = {k: level[k] for k in ("pitch_deg", "roll_deg")} | {"residual": level["fit"]["residual"]} if level else None
    if cam is None:
        return
    if level:
        cam.pos, cam.target, cam.roll = list(level["camera"]["pos"]), list(level["camera"]["target"]), float(level["camera"].get("roll", 0.0))
    d = subject or 1.0
    fwd = [t - q for t, q in zip(cam.target, cam.pos)]
    n = math.sqrt(sum(v * v for v in fwd)) or 1.0
    cam.target = [round(q + v / n * d, 4) for q, v in zip(cam.pos, fwd)]


class StaleStage(ValueError):
    """A PUT based on an older revision than the document's (the API answers 409; the client reloads and re-applies)."""


class Transform(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    pos: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rot: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])      # degrees, yaw pitch roll as the Inspector shows them (Y X Z)
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])


PinEnd = Literal["r_hand", "l_hand", "r_foot", "l_foot"]


class Pose(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    preset: str | None = None
    joints: dict[str, list[float]] = Field(default_factory=dict)         # joint name → [x, y, z] degrees (ST2 edits them; ST1 keeps presets)
    extra: dict[str, list[float]] = Field(default_factory=dict)          # CA1: the Detailed level's own bones (fingers, wrists, feet …) → [x, y, z] degrees on their rest
    ground: float = 0.0                            # AP1 (D141): the root dropped this much (metres; < 0 raises it) so the pose stands on its feet
    # AP1b: the pose editor's pins — a hand or a foot held at [x, y, z] metres in the figure's own space while the rest of the pose changes
    # (frontend motion/contact.ts)
    pins: dict[PinEnd, Annotated[list[float], Field(min_length=3, max_length=3)]] = Field(default_factory=dict)


class LightSpec(BaseModel):
    """D110 (PS4): a light of the 3D scene — a sun from the object's position towards `target`, its strength, colour, the softness of its
    shadow's edge and whether it casts one (the first three that do). A light object without one shines as E23c's key did (2.3, white,
    hard shadows, aimed a metre above the origin), so earlier stages keep their look."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    intensity: float = Field(2.3, ge=0.0, le=20.0)
    colour: str = Field("#ffffff", pattern=r"^#[0-9A-Fa-f]{6}$")
    softness: float = Field(0.3, ge=0.0, le=1.0)     # 0 = a hard edge; 1 = the softest the shadow map gives
    shadows: bool = True
    target: list[float] = Field(default_factory=lambda: [0.0, 1.0, 0.0])


class SetThing(BaseModel):
    """D123 (SC3c-2): a thing the author picked on a picture set's picture — SAM 3's points and the mask they found (a Catalogue `mask`
    asset at the picture's size), the relief and floor it was picked on (the placement reads them), and what was made of it (SC3c-3)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    id: str = Field(default_factory=lambda: new_id("thg"))
    name: str
    mask_asset_id: str
    points: list[dict[str, int]] = Field(default_factory=list)   # {x, y, label}: picture pixels; label 1 = the thing, 0 = not it
    relief_asset_id: str | None = None             # the set's relief when it was picked (the original picture's point map)
    floor_y: float | None = None                   # the set's floor then (its relief's frame → the stage's)
    mesh_asset_id: str | None = None               # SC3c-3: its Pixal3D model
    object_id: str | None = None                   # SC3c-3: the prop it stands as on the stage
    placed: Transform | None = None                # SC3f: the transform the prop was stood with (a rebuild re-stands it while it still has it)


SetKind = Literal["room", "street", "corridor", "ground"]


class SetFace(BaseModel):
    """CW6 (04 §2): a built set's face, baked — its texture (a Catalogue image, the face straight on) and its texel size."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    texture_asset_id: str | None = None
    texel_m: float = Field(0.01, gt=0.0, le=1.0)
    mask_asset_id: str | None = None               # what the pictures never saw well (the Fill's selection)


class SourceCamera(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    pos: list[float]
    target: list[float]
    roll: float = 0.0
    focal_mm: float = 35.0
    sensor_mm: float = 36.0


class SetSource(BaseModel):
    """CW6: a picture a built set was skinned from, and the camera it was matched to (in the set's frame)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    asset_id: str
    camera: SourceCamera
    made_at: str = Field(default_factory=utc_now)


class PlaceSet(BaseModel):
    """CW6 (04 §2): a place's set — a room, a street, a corridor or open ground, its sizes and parts (frontend placeSet.ts lays its faces
    out), its baked faces and the pictures they came from."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: SetKind = "room"
    sizes: dict[str, float] = Field(default_factory=dict)
    parts: dict[str, bool] = Field(default_factory=dict)
    faces: list[SetFace] = Field(default_factory=list)
    sources: list[SetSource] = Field(default_factory=list)


class StageObject(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    kind: Kind
    name: str
    preset: str | None = None                      # mannequin: adult | child; set (architecture only, D108): room | street | deck | empty; prop: crate | stool | table | pole | block
    asset_id: str | None = None                    # plane: the Catalogue image; mesh: the GLB asset (P18)
    transform: Transform = Field(default_factory=Transform)
    parent: str | None = None
    parent_joint: Literal["r_hand", "l_hand"] | None = None   # D129 (HP1): held — `parent` is the figure, the transform is local to that hand
    locked: bool = False
    visible: bool = True
    colour_id: int = 0                             # the object-ID mask colour (ST3)
    pose: Pose | None = None                       # figures
    billboard: bool = True                         # planes face the camera
    profile_id: str | None = None                  # D93 (C8): a figure bound to a Cast character — its references and sheet go into the frame; D110 (PS3): a mesh bound to a Cast prop (its model follows the version)
    version: str | None = None                     # D93 (C8): the character's version (a costume) the figure wears; None = the current one (a prop's version for a mesh)
    body: Body | None = None                       # CA0: the bound version's body, copied when bound and kept in step by the client (None = the preset's dummy)
    detail: Literal["male", "female"] | None = None   # CA1: the Detailed level — the starter set's skinned mannequin follows the figure; U18 (CS1): every
                                                      # figure has one (a stored None reads as ♀, the Simple dummy retired); other kinds None
    shadow_proxy: str | None = None                # E23d (D105): a mesh asset shaped like the character, bound to the figure, that casts its shadow
    path: list[list[float]] | None = None          # CA1: the figure's floor path, [x, z] points clicked on the floor (a library clip walks it)
    light: LightSpec | None = None                 # D110 (PS4): a light object's settings (None = E23c's key)
    lens_deg: float | None = None                  # SC3 (D120): an image set (preset `image`, asset_id the relief): the picture's horizontal field of view
    plate_asset_id: str | None = None              # SC3: the picture the relief was made from (the plate at the picture's camera)
    floor_y: float | None = None                   # SC3: where the relief's floor sits under the picture's camera (metres, negative); the set is raised by it
    plate_camera_id: str | None = None             # SC3: the camera that took the picture, added with the set
    level: dict[str, float] | None = None          # SC3d: how the picture set was laid level (pitch, the sideways tilt left, the fit's residual)
    things: list[SetThing] = Field(default_factory=list)   # D123 (SC3c): the things the author picked on the picture
    things_document_id: str | None = None          # D123: the set's own document (its picture), where SAM 3 finds them and the plate is cleaned
    height_m: float | None = Field(None, gt=0.0, le=100.0)   # CW4: a mesh's model scaled to this height (metres); None = the GLB's own size
    place_set: PlaceSet | None = None              # CW6: a built set (kind set, preset `built`): its kind, sizes, parts and baked faces


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


Purpose = Literal["stage", "bench", "lineup"]


class StageBound(BaseModel):
    """D142: the Cast version a bench stage is for."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    profile_id: str
    version: str


class Stage(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = STAGE_SCHEMA_VERSION
    id: str
    name: str = "Stage"
    purpose: Purpose = "stage"                     # D142: a stage, a Cast version's bench, or the line-up (CW5) — the last two stay out of the pickers
    bound: StageBound | None = None                # D142: a bench's Cast version
    size: dict[str, int] = Field(default_factory=lambda: {"w": 1920, "h": 1080, "fps": 24})   # from the project format (D18)
    objects: list[StageObject] = Field(default_factory=list)
    cameras: list[StageCamera] = Field(default_factory=list)
    active_camera: str | None = None
    keyframes: dict[str, Any] = Field(default_factory=lambda: {"camera": {}, "objects": {}})  # ST4
    range: StageRange = Field(default_factory=StageRange)
    passes: list[dict[str, Any]] = Field(default_factory=list)                                 # ST3: {camera_id, revision, size, assets, keypoints, legend, rendered_at}
    ambient: float | None = Field(None, ge=0.0, le=5.0)                                        # D110 (PS4): the sky light's strength; None = 0.85 with lights, 1.1 without
    group_id: str | None = None                                                                # ST3: the album page the passes and shots are placed on (server-set)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


REFERENCE_HEIGHT_M = 1.75                         # CW4: the figure a prop's bench and the line-up stand beside it for scale


def bench_objects(profile: Any, v: Any) -> tuple[list[StageObject], float]:
    """D142: what a bench holds — a character's figure bound to the version (its body, shell, mannequin), or a prop's model bound to it at its
    height with an unbound 1.75 m figure beside it; and the height to frame."""
    if profile.cls == "character":
        h = v.body.height_m if v.body else REFERENCE_HEIGHT_M
        fig = StageObject(id=new_id("fig"), kind="mannequin", name=profile.name, preset="adult", profile_id=profile.id, version=v.id, body=v.body,
                          detail=(v.body.figure if v.body else "female"), shadow_proxy=v.shell_asset_id, pose=Pose(preset="stand"), colour_id=1)
        return [fig], h
    if profile.cls == "prop":
        if not v.model_asset_id:
            raise ValueError("the prop has no 3D model yet — make or import it first, then its bench shows it at its height")
        h = float(v.height_m or 1.0)
        mesh = StageObject(id=new_id("mesh"), kind="mesh", name=profile.name, asset_id=v.model_asset_id, profile_id=profile.id, version=v.id,
                           height_m=h, colour_id=1)
        ref = StageObject(id=new_id("fig"), kind="mannequin", name="1.75 m for scale", preset="adult", detail="female", pose=Pose(preset="stand"),
                          transform=Transform(pos=[round(-0.6 - 0.25 * h, 3), 0.0, 0.0]), colour_id=2)
        return [mesh, ref], max(h, REFERENCE_HEIGHT_M)
    raise ValueError("a place's bench comes with the set builder (CW6) — a character or a prop has one now")


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """Read a stored document at the current schema. 1 → 2 (D108): each room or street set gives its blocks to the stage as `block` props
    where they stood (the set's position, yaw and scale applied; Stage's transforms are world ones), so an old shot keeps its look.
    2 → 3 (CS1, S3): each figure's body reads as the adult dummy's (body.rebase_body), every point where it was; (U18) a figure without a
    Detailed mannequin gets the ♀ one."""
    v = int(raw.get("schema_version", 1))
    if v >= STAGE_SCHEMA_VERSION:
        return raw
    if v < 2:
        raw = _migrate_sets(raw)
    from .body import rebase_body

    def figure(o: dict[str, Any]) -> dict[str, Any]:
        if isinstance(o.get("body"), dict):
            o = {**o, "body": rebase_body(o["body"])}
        if o.get("kind") == "mannequin" and not o.get("detail"):
            o = {**o, "detail": "female"}                          # U18: the Simple dummy retired — every figure the Detailed mannequin
        return o
    objs = [figure(o) if isinstance(o, dict) else o for o in (raw.get("objects") or [])]
    return {**raw, "objects": objs, "schema_version": STAGE_SCHEMA_VERSION}


def _migrate_sets(raw: dict[str, Any]) -> dict[str, Any]:
    """1 → 2 (D108): the set blocks as props."""
    objs = list(raw.get("objects") or [])
    used = {int(o.get("colour_id", 0)) for o in objs}
    ids = {o.get("id") for o in objs}
    for o in list(objs):
        if o.get("kind") != "set" or o.get("preset") not in SET_BLOCKS_V1:
            continue
        tf = o.get("transform") or {}
        pos, rot, scl = tf.get("pos", [0, 0, 0]), tf.get("rot", [0, 0, 0]), tf.get("scale", [1, 1, 1])
        yaw = math.radians(float(rot[1]))
        for n, (size, foot) in enumerate(SET_BLOCKS_V1[o["preset"]], 1):
            x, y, z = foot[0] * scl[0], foot[1] * scl[1], foot[2] * scl[2]
            wx, wz = x * math.cos(yaw) + z * math.sin(yaw), -x * math.sin(yaw) + z * math.cos(yaw)
            colour = next(c for c in range(1, 256) if c not in used)
            used.add(colour)
            bid = f"prop_{o['id']}_{n}"
            while bid in ids:
                bid += "_"
            ids.add(bid)
            objs.append({"id": bid, "kind": "prop", "name": f"{o.get('name') or 'Set'} block {n}", "preset": "block",
                         "transform": {"pos": [pos[0] + wx, pos[1] + y, pos[2] + wz], "rot": [0.0, float(rot[1]), 0.0],
                                       "scale": [size[0] * scl[0], size[1] * scl[1], size[2] * scl[2]]},
                         "locked": bool(o.get("locked", False)), "visible": bool(o.get("visible", True)), "colour_id": colour})
    return {**raw, "objects": objs, "schema_version": 2}


def check(st: Stage) -> None:
    """The invariants a saved document keeps: unique ids, parents that exist and never cycle, the active camera present, a 36 mm
    sensor is the default but any positive one is allowed, focal lengths in the lens range."""
    for o in st.objects:
        if o.kind == "set" and o.preset == "built" and o.place_set is None:
            raise ValueError(f"object {o.id}: a built set needs its place_set (CW6)")
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
        if o.light is not None and (o.kind != "light" or len(o.light.target) != 3):
            raise ValueError(f"object {o.id}: light settings belong to a light, aimed at an [x, y, z] point")   # D110 (PS4)
        if o.parent_joint is not None and (o.parent is None or by[o.parent].kind != "mannequin" or o.kind not in ("mesh", "prop", "plane")):
            raise ValueError(f"object {o.id}: a held thing is a prop (a 3D model, a stand-in or an image plane) in a figure's hand")   # D129 (HP1)
        if o.profile_id is not None and o.kind not in ("mannequin", "mesh"):
            raise ValueError(f"object {o.id}: only a figure (to a character) or a 3D model (to a prop) is bound")   # D93 (C8), D110 (PS3)
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
        return Stage.model_validate(migrate(read_json(p))) if p.is_file() else None

    def list(self) -> list[Stage]:
        out = [Stage.model_validate(migrate(read_json(p))) for p in self.dir.glob("stg_*.json")]
        return sorted(out, key=lambda t: t.updated_at, reverse=True)

    def save(self, st: Stage) -> None:
        atomic_write_json(self.path(st.id), st.model_dump())

    def bench(self, profile: Any, version_id: str, size: dict[str, int] | None = None) -> tuple[Stage, bool]:
        """D142: a Cast version's bench — made once and kept (the author's camera and light stay): a character's figure bound to it, or a
        prop's model at its height with a 1.75 m figure beside it for scale. (stage, made now)."""
        for st in self.list():
            if st.purpose == "bench" and st.bound is not None and st.bound.profile_id == profile.id and st.bound.version == version_id:
                return st, False
        v = profile.version(version_id)
        objects, h = bench_objects(profile, v)
        d = max(1.2, h * 2.0)
        cam = StageCamera(id=new_id("cam"), name="Bench camera", pos=[round(d * 0.3, 3), round(h * 0.6, 3), round(d, 3)], target=[0.0, round(h * 0.5, 3), 0.0])
        st = Stage(id=new_id("stg"), name=f"Bench · {profile.name} {v.id}", purpose="bench", bound=StageBound(profile_id=profile.id, version=v.id),
                   size=size or {"w": 1920, "h": 1080, "fps": 24}, objects=objects, cameras=[cam], active_camera=cam.id)
        check(st)
        self.save(st)
        return st, True

    def lineup(self, entries: list[dict[str, Any]], size: dict[str, int] | None = None) -> Stage:
        """CW5 (02 §7): the line-up — the characters and props picked side by side on a neutral floor before a wall with 0.5 m marks,
        one camera framing them; the project's one line-up stage, made again each time (*Send to a stage ▸* keeps what should stay).
        `entries`: {name, kind: figure|mesh, profile_id?, version?, body?, shell?, asset_id?, height_m?} in order, left to right."""
        objects: list[StageObject] = []
        x, tallest, gap = 0.0, REFERENCE_HEIGHT_M, 0.35
        widths = []
        for e in entries:
            if e["kind"] == "figure":
                body = e.get("body")
                h = float((body or {}).get("height_m") or REFERENCE_HEIGHT_M) if isinstance(body, dict) else (body.height_m if body else REFERENCE_HEIGHT_M)
                widths.append(0.55 * h / REFERENCE_HEIGHT_M + gap)
            else:
                h = float(e.get("height_m") or 1.0)
                widths.append(max(0.5, 0.7 * h) + gap)
            tallest = max(tallest, h)
        total = sum(widths)
        x = -total / 2
        for k, (e, w) in enumerate(zip(entries, widths)):
            at = Transform(pos=[round(x + w / 2, 3), 0.0, 0.0])
            x += w
            if e["kind"] == "figure":
                body = e.get("body")
                fig = body if body is None or isinstance(body, Body) else Body.model_validate(body)
                objects.append(StageObject(id=new_id("fig"), kind="mannequin", name=e["name"], preset="adult", profile_id=e.get("profile_id"),
                                           version=e.get("version"), body=fig, detail=(fig.figure if fig else "female"), shadow_proxy=e.get("shell"),
                                           pose=Pose(preset="stand"), transform=at, colour_id=(k % 12) + 1))
            else:
                objects.append(StageObject(id=new_id("mesh"), kind="mesh", name=e["name"], asset_id=e["asset_id"], profile_id=e.get("profile_id"),
                                           version=e.get("version"), height_m=float(e.get("height_m") or 1.0), transform=at, colour_id=(k % 12) + 1))
        wall = StageObject(id=new_id("set"), kind="set", name="Line-up (0.5 m marks)", preset="lineup", locked=True,
                           transform=Transform(scale=[round(max(0.35, (total + 1.5) / 8.0), 3), 1.0, 1.0]))   # the wall as wide as the row (8 m at 1)
        d = max(2.5, total * 0.95, tallest * 2.0)
        cam = StageCamera(id=new_id("cam"), name="Line-up camera", pos=[0.0, round(tallest * 0.6, 3), round(d, 3)], target=[0.0, round(tallest * 0.5, 3), 0.0])
        cur = next((s for s in self.list() if s.purpose == "lineup"), None)
        st = Stage(id=cur.id if cur else new_id("stg"), name="Line-up", purpose="lineup", size=size or {"w": 1920, "h": 1080, "fps": 24},
                   objects=[wall, *objects], cameras=[cam], active_camera=cam.id, revision=(cur.revision + 1) if cur else 0,
                   created_at=cur.created_at if cur else utc_now())
        check(st)
        self.save(st)
        return st

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
        keep = ("name", "size", "objects", "cameras", "active_camera", "keyframes", "range", "passes", "ambient")
        merged = {**cur.model_dump(), **{k: v for k, v in data.items() if k in keep}, "id": st_id, "schema_version": STAGE_SCHEMA_VERSION,
                  "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        st = Stage.model_validate(merged)
        check(st)
        self.save(st)
        return st

    def add_image_set(self, st_id: str, asset_id: str, plate_id: str, lens_deg: float | None, floor_y: float | None, relief_path: Path | None = None) -> Stage:
        """SC3 (D120): the relief as a locked set standing on the floor (raised by the floor's depth under the picture's camera) and the
        picture's camera at that height looking down −Z with the lens, made the active one — the shot the picture already is."""
        from .relief import DEFAULT_LENS_DEG, focal_mm_for
        st = self.get(st_id)
        if st is None:
            raise KeyError(st_id)
        lens = float(lens_deg) if lens_deg else DEFAULT_LENS_DEG
        floor = float(floor_y) if floor_y is not None and -4.0 <= floor_y <= -0.05 else -1.0
        n = sum(1 for o in st.objects if o.kind == "set" and o.preset == "image") + 1
        suffix = f" {n}" if n > 1 else ""
        cam = StageCamera(id=new_id("cam"), name=f"Picture camera{suffix}", pos=[0.0, round(-floor, 3), 0.0], target=[0.0, round(-floor, 3), -1.0],
                          focal_mm=focal_mm_for(lens), sensor_mm=36.0)
        obj = StageObject(id=new_id("set"), kind="set", name=f"Picture set{suffix}", preset="image", asset_id=asset_id, plate_asset_id=plate_id,
                          lens_deg=round(lens, 2), floor_y=round(floor, 3), plate_camera_id=cam.id, locked=True, colour_id=(len(st.objects) % 12) + 1)
        _level(obj, cam, relief_path)
        st.objects.append(obj)
        st.cameras.append(cam)
        st.active_camera = cam.id
        st.revision += 1
        st.updated_at = utc_now()
        check(st)
        self.save(st)
        return st

    def replace_image_set(self, st_id: str, set_id: str, asset_id: str, lens_deg: float | None, floor_y: float | None, plate_id: str | None = None,
                          relief_path: Path | None = None) -> Stage:
        """SC3b (D120): a picture set rebuilt in place — a corrected lens gives a new relief: the set takes it, its lens and its floor, and its
        picture camera goes back to where the picture was taken (the floor's height, looking down −Z, the new lens). The old relief stays in
        the Catalogue. KeyError for a missing stage or set; ValueError for an object that is not a picture set."""
        from .relief import DEFAULT_LENS_DEG, focal_mm_for
        st = self.get(st_id)
        if st is None:
            raise KeyError(st_id)
        obj = next((o for o in st.objects if o.id == set_id), None)
        if obj is None:
            raise KeyError(set_id)
        if obj.kind != "set" or obj.preset != "image":
            raise ValueError(f"{set_id} is not a picture set")
        lens = float(lens_deg) if lens_deg else (obj.lens_deg or DEFAULT_LENS_DEG)
        floor = float(floor_y) if floor_y is not None and -4.0 <= floor_y <= -0.05 else (obj.floor_y if obj.floor_y is not None else -1.0)
        obj.asset_id, obj.lens_deg, obj.floor_y = asset_id, round(lens, 2), round(floor, 3)
        if plate_id:                                                                # D123 (SC3c-3): rebuilt from the clean plate — the set's picture now
            obj.plate_asset_id = plate_id
        else:                                                                       # D123: the same picture at a corrected lens — the things not made yet
            for t in obj.things:                                                    # are stood on the new relief (the clean plate's has no things in it)
                if not t.mesh_asset_id:
                    t.relief_asset_id, t.floor_y = asset_id, obj.floor_y
        cam = next((c for c in st.cameras if c.id == obj.plate_camera_id), None)
        if cam is not None:
            cam.pos, cam.target, cam.focal_mm, cam.roll = [0.0, round(-floor, 3), 0.0], [0.0, round(-floor, 3), -1.0], focal_mm_for(lens), 0.0
        _level(obj, cam, relief_path)
        st.revision += 1
        st.updated_at = utc_now()
        check(st)
        self.save(st)
        return st

    def picture_set(self, st_id: str, set_id: str) -> tuple[Stage, StageObject]:
        """D123: a stage and one of its picture sets — KeyError for a missing stage or set, ValueError for an object that is not one."""
        st = self.get(st_id)
        if st is None:
            raise KeyError(st_id)
        obj = next((o for o in st.objects if o.id == set_id), None)
        if obj is None:
            raise KeyError(set_id)
        if obj.kind != "set" or obj.preset != "image":
            raise ValueError(f"{set_id} is not a picture set")
        return st, obj

    def edit_picture_set(self, st_id: str, set_id: str, fn: Any) -> Stage:
        """D123: a server-side change to a picture set (`fn(stage, set)`), saved at a new revision (the client reloads)."""
        st, obj = self.picture_set(st_id, set_id)
        fn(st, obj)
        st.revision += 1
        st.updated_at = utc_now()
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
