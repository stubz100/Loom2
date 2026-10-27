"""Stages (P13 / ST1, 16 §12): the 3D blocking documents — list, create (one camera, the project's size and fps), read, replace
(409 on a stale revision), delete. ST3: the passes a camera rendered become `stage-pass` assets on the stage's album page. Shots (ST4) join here."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..fsio import atomic_write_json, read_json_or, utc_now
from ..stages import encode_guide
from ..origin import JobOrigin
from ..recipes import STAGE_PASSES
from ..schemas import Deleted, StageList
from ..stages import Stage, StageStore, StaleStage
from .. import set_things
from .deps import Svc

router = APIRouter(tags=["stages"])


class StageCreate(BaseModel):
    name: str = "Stage"


@router.get("/stages", response_model=StageList)
async def stages_list(svc: Svc, purpose: Literal["stage", "bench", "lineup", "all"] = "stage"):
    """The project's stages — D142: the stages proper by default; a Cast version's bench and the line-up only when asked for."""
    ws, _, _ = svc.require_project()
    return {"items": [s.model_dump() for s in await asyncio.to_thread(StageStore(ws).list) if purpose == "all" or s.purpose == purpose]}


class BenchOpen(BaseModel):
    profile_id: str
    version: str | None = None                    # None: the current version


class BenchOut(BaseModel):
    stage: Stage
    made: bool


@router.post("/stages/bench", response_model=BenchOut)
async def stage_bench(svc: Svc, body: BenchOpen):
    """D142: a Cast version's bench — Clay opened for it: the bench stage made once (a character's figure bound to the version; a prop's model
    at its height beside a 1.75 m figure) and kept, so the camera and light the author set stay."""
    from ..story import StoryStore
    ws, _, _ = svc.require_project()
    p = await asyncio.to_thread(StoryStore(ws).profile, body.profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    try:
        v = p.version(body.version)
    except KeyError as e:
        raise HTTPException(404, str(e))
    fmt = ws.load().format
    try:
        st, made = await asyncio.to_thread(StageStore(ws).bench, p, v.id, {"w": fmt.width, "h": fmt.height, "fps": fmt.fps})
    except ValueError as e:
        raise HTTPException(422, str(e))
    if made:
        svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return {"stage": st.model_dump(), "made": made}


@router.post("/stages", response_model=Stage)
async def stage_create(svc: Svc, body: StageCreate):
    ws, _, _ = svc.require_project()
    fmt = ws.load().format
    st = await asyncio.to_thread(StageStore(ws).create, body.name, {"w": fmt.width, "h": fmt.height, "fps": fmt.fps})
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


class LineupItem(BaseModel):
    """One thing in the line-up: a Cast version (a character or a prop; its current version when none is named) or an idea (its variant in
    focus, else the one named)."""
    profile_id: str | None = None
    version: str | None = None
    idea_id: str | None = None
    variant_id: str | None = None


class LineupBody(BaseModel):
    items: list[LineupItem] = Field(..., min_length=1, max_length=12)


@router.post("/stages/lineup", response_model=Stage)
async def stage_lineup(svc: Svc, body: LineupBody):
    """CW5 (02 §7): the line-up — Cast's characters and props, and ideas with clay, side by side at their sizes before 0.5 m marks; Clay
    opens on it (D142). A Cast version stands bound (its body and shell, or its model at its height, follow Cast); an idea's figure is its
    variant's clay (free). An idea without clay, a prop without a model, and a place are left out (and named)."""
    from ..ideas import IdeaStore, focus_variant
    from ..story import StoryStore
    ws, _, _ = svc.require_project()
    stories, ideas = StoryStore(ws), IdeaStore(ws)

    def plan() -> tuple[list[dict[str, Any]], list[str]]:
        out: list[dict[str, Any]] = []
        skipped: list[str] = []
        for it in body.items:
            if it.profile_id:
                p = stories.profile(it.profile_id)
                if p is None:
                    raise KeyError(it.profile_id)
                v = p.version(it.version)
                if p.cls == "character":
                    out.append({"kind": "figure", "name": p.name, "profile_id": p.id, "version": v.id, "body": v.body, "shell": v.shell_asset_id})
                elif p.cls == "prop" and v.model_asset_id:
                    out.append({"kind": "mesh", "name": p.name, "profile_id": p.id, "version": v.id, "asset_id": v.model_asset_id, "height_m": v.height_m})
                else:
                    skipped.append(p.name)
            elif it.idea_id:
                i = ideas.get(it.idea_id)
                if i is None:
                    raise KeyError(it.idea_id)
                var = i.variant(it.variant_id) if it.variant_id else focus_variant(i)
                clay = var.clay if var else None
                if i.cls == "character" and clay is not None and clay.body is not None:
                    out.append({"kind": "figure", "name": i.name, "body": clay.body, "shell": clay.shell_asset_id})
                elif i.cls == "prop" and clay is not None and clay.model_asset_id:      # CW3: an idea's prop (Prototype ▸ on a mesh)
                    out.append({"kind": "mesh", "name": i.name, "asset_id": clay.model_asset_id, "height_m": clay.height_m})
                else:
                    skipped.append(i.name)
        return out, skipped

    try:
        entries, skipped = await asyncio.to_thread(plan)
    except KeyError as e:
        raise HTTPException(404, f"no profile, version, idea or variant {e.args[0]!r}")
    if not entries:
        raise HTTPException(422, "nothing to line up: " + ", ".join(skipped) + " — a character needs its clay (Make the clay ▶), a prop its 3D model")
    fmt = ws.load().format
    st = await asyncio.to_thread(StageStore(ws).lineup, entries, {"w": fmt.width, "h": fmt.height, "fps": fmt.fps})
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


POSES_SCHEMA_VERSION = 1


class PoseLibrary(BaseModel):
    """ST2: the project's saved poses — name → {preset?, joints {joint: [x, y, z] degrees}} — kept as `stages/poses.json`. V28: a
    `schema_version` like every record, and a `revision` the client sends back (409 when the library changed meanwhile — a second
    window's save is not lost under the first's)."""
    schema_version: int = POSES_SCHEMA_VERSION
    revision: int = 0
    poses: dict[str, dict] = {}


def _poses_read(p: Path) -> PoseLibrary:
    return PoseLibrary.model_validate(read_json_or(p, {"poses": {}}))


@router.get("/stages/poses", response_model=PoseLibrary)
async def poses_get(svc: Svc):
    ws, _, _ = svc.require_project()
    return (await asyncio.to_thread(_poses_read, ws.stages_dir / "poses.json")).model_dump()


@router.put("/stages/poses", response_model=PoseLibrary)
async def poses_put(svc: Svc, body: PoseLibrary):
    ws, _, _ = svc.require_project()
    for name, pose in body.poses.items():
        joints = pose.get("joints", {}) if isinstance(pose, dict) else None
        if not name.strip() or not isinstance(joints, dict) or any(not (isinstance(v, list) and len(v) == 3) for v in joints.values()):
            raise HTTPException(422, f"pose {name!r}: joints are {{name: [x, y, z]}} in degrees")
    p = ws.stages_dir / "poses.json"

    def write() -> PoseLibrary:
        cur = _poses_read(p)
        if body.revision != cur.revision:
            raise StaleStage(f"the poses are at revision {cur.revision}, the change is based on {body.revision} — reload them first")
        out = PoseLibrary(schema_version=POSES_SCHEMA_VERSION, revision=cur.revision + 1, poses=body.poses)
        atomic_write_json(p, out.model_dump())
        return out
    try:
        return (await asyncio.to_thread(write)).model_dump()
    except StaleStage as e:
        raise HTTPException(409, str(e))



@router.get("/stages/{st_id}", response_model=Stage)
async def stage_get(svc: Svc, st_id: str):
    ws, _, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    return st.model_dump()


@router.put("/stages/{st_id}", response_model=Stage)
async def stage_put(svc: Svc, st_id: str, body: dict):
    ws, _, _ = svc.require_project()
    try:
        st = await asyncio.to_thread(StageStore(ws).put, st_id, body)
    except KeyError:
        raise HTTPException(404, "stage not found")
    except StaleStage as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


class PassesUpload(BaseModel):
    """ST3 (16 §7): the passes the client rendered for one camera — each a PNG already put through `PUT /blobs/{sha}` — with the COCO-18
    keypoints behind the pose pass and the mask pass's colour legend."""
    camera_id: str
    revision: int                                 # the document revision the passes were rendered from (staleness is judged against it)
    size: dict[str, int]                          # {w, h} they were rendered at
    passes: dict[str, str]                        # pass name → blob sha256
    keypoints: list[Any] = []                     # per figure: 18 × [x, y, visible] in `size` pixels
    legend: dict[str, Any] = {}                   # mask colour → object id / name


class ImageSetBody(BaseModel):
    """SC3 (D120): a set from a Catalogue image — MoGe's relief of the picture, the picture's camera beside it."""
    asset_id: str
    lens_deg: float | None = Field(None, ge=20, le=150, description="the picture's horizontal field of view in degrees when known; None = MoGe's own reading")
    relief: Literal["cut", "sheet"] | None = Field(None, description="cut at depth jumps or one sheet; None = cut, or the rebuilt set's own")
    replace_set_id: str | None = Field(None, description="SC3b: rebuild this picture set in place (a corrected lens) instead of adding one")


class ImageSetQueued(BaseModel):
    job_id: str


IMAGE_SET_SURFACE = "image_set"


@router.post("/stages/{st_id}/image-set", response_model=ImageSetQueued)
async def stage_image_set(svc: Svc, st_id: str, body: ImageSetBody):
    """SC3 (D120): queue the image → set job for this stage; when it finishes the stage gets the relief as a locked set standing on its
    floor and the picture's camera (active) — `stage.updated` says so. 422 when the asset is not a Catalogue image."""
    ws, catalogue, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    a = catalogue.get(body.asset_id)
    if a is None or a.kind != "image":
        raise HTTPException(422, "a set is made from a Catalogue image")
    relief = body.relief or "cut"
    if body.replace_set_id:                                                       # SC3b: a rebuild — the set must be a picture set of this stage
        obj = next((o for o in st.objects if o.id == body.replace_set_id), None)
        if obj is None or obj.kind != "set" or obj.preset != "image":
            raise HTTPException(422, f"{body.replace_set_id} is not a picture set of this stage")
        old = catalogue.get(obj.asset_id) if obj.asset_id else None
        relief = body.relief or ((old.params.get("recipe") or {}).get("relief") if old else None) or "cut"
    try:
        jobs = svc.queue.submit({"kind": "image_to_set", "asset_id": body.asset_id, "lens_deg": body.lens_deg, "relief": relief, "stage_id": st_id,
                                 "replace_set_id": body.replace_set_id},
                                origin=JobOrigin(suite="stage", surface=IMAGE_SET_SURFACE, ref=st_id, payload={"asset_id": body.asset_id}))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"job_id": jobs[0].id}


# ---- D123 (SC3c-2): the things of a picture set, picked on its picture ------------------------------------------------------------
class ThingPoint(BaseModel):
    x: int
    y: int
    label: int = Field(1, ge=0, le=1, description="1 = on the thing, 0 = not it")


class ThingFindBody(BaseModel):
    points: list[ThingPoint] = Field(min_length=1, max_length=32)


class ThingFound(BaseModel):
    job_id: str
    document_id: str


class ThingKeepBody(BaseModel):
    name: str = ""
    points: list[ThingPoint] = Field(default_factory=list, max_length=32)


class ThingPatch(BaseModel):
    name: str


def _things_error(e: Exception) -> HTTPException:
    return HTTPException(404, f"not found: {e}") if isinstance(e, KeyError) else HTTPException(422, str(e))


@router.post("/stages/{st_id}/sets/{set_id}/things/find", response_model=ThingFound)
async def stage_thing_find(svc: Svc, st_id: str, set_id: str, body: ThingFindBody):
    """D123: SAM 3's point prompts on the set's own document (made from its picture the first time); the mask lands as that document's
    selection, which the client reads (`GET /documents/{id}/selection`) and draws on the picture. 404 / 422 as the stage, set and points are."""
    ws, catalogue, q = svc.require_project()
    store = StageStore(ws)
    try:
        od = await asyncio.to_thread(set_things.ensure_document, store, svc.require_documents(), catalogue, st_id, set_id)
        points = set_things.check_points([p.model_dump() for p in body.points], od.doc.w, od.doc.h)
        jobs = q.submit({"kind": "segment", "mode": "points", "points": points, "op": "replace", "document_id": od.doc.id},
                        origin=JobOrigin(suite="stage", surface=set_things.FIND_SURFACE, ref=st_id, payload={"set_id": set_id}))
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    return {"job_id": jobs[0].id, "document_id": od.doc.id}


@router.post("/stages/{st_id}/sets/{set_id}/things", response_model=Stage)
async def stage_thing_keep(svc: Svc, st_id: str, set_id: str, body: ThingKeepBody):
    """D123: the mask the last find left, kept as a thing of the set (a `mask` asset, lineage `set-thing` ← the picture)."""
    ws, catalogue, _ = svc.require_project()
    try:
        st, _, rec = await asyncio.to_thread(set_things.keep_thing, StageStore(ws), svc.require_documents(), catalogue, st_id, set_id, body.name,
                                             [p.model_dump() for p in body.points])
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    svc.hub.broadcast("asset.created", rec.model_dump())
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


class ThingModelJob(BaseModel):
    thing_id: str
    cutout_id: str


class ThingsMade(BaseModel):
    clean_job_id: str
    models: list[ThingModelJob]
    shadows: float = 0.0                           # D124: the share of the picture the things' shadows add to the clean


@router.get("/stages/{st_id}/sets/{set_id}/things/shadows")
async def stage_things_shadows(svc: Svc, st_id: str, set_id: str):
    """D124: the shadows *Make the things* would clean with the things not yet made — raw grey bytes at the picture's size (w·h, 255 a
    shadow), what the things sheet draws before the Make. All zero when every thing is made."""
    ws, catalogue, _ = svc.require_project()
    try:
        m = await asyncio.to_thread(set_things.things_shadows, StageStore(ws), svc.require_documents(), catalogue, st_id, set_id)
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    return Response(content=np.where(m, 255, 0).astype(np.uint8).tobytes(), media_type="application/octet-stream",
                    headers={"X-Loom-Width": str(m.shape[1]), "X-Loom-Height": str(m.shape[0]), "Cache-Control": "no-store"})


@router.post("/stages/{st_id}/sets/{set_id}/things/make", response_model=ThingsMade)
async def stage_things_make(svc: Svc, st_id: str, set_id: str):
    """D123 (SC3c-3): the things not yet made — the plate cleaned under them all and (D124) their shadows (a Fill on the set's document); when it lands, the relief is
    rebuilt from the clean plate at the set's lens and then a Pixal3D model is queued for each one's cut-out (stood on the relief at its
    footprint when it lands) — the rebuild first, so the clean set shows within a minute or two and the models follow. The jobs take their
    turns through the queue (D97). 422 with the reason: nothing to make, Pixal3D not in the variant."""
    ws, catalogue, q = svc.require_project()
    try:
        prep = await asyncio.to_thread(set_things.prepare_make, StageStore(ws), svc.require_documents(), catalogue, st_id, set_id, svc.app.settings.variant)
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    for _, rec in prep["cutouts"]:
        svc.hub.broadcast("asset.created", rec.model_dump())

    def origin(surface: str, extra: dict | None = None) -> JobOrigin:
        return JobOrigin(suite="stage", surface=surface, ref=st_id, payload={"set_id": set_id, **(extra or {})})
    models = [{"thing_id": tid, "cutout_id": rec.id} for tid, rec in prep["cutouts"]]
    try:
        clean = q.submit({"kind": "inpaint", "mode": "fill", "document_id": prep["document_id"], "prompt_text": set_things.CLEAN_PROMPT, "feather": 8},
                         origin=origin(set_things.CLEAN_SURFACE, {"cutouts": models}))[0]
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"clean_job_id": clean.id, "models": models, "shadows": prep["shadows"]}


@router.patch("/stages/{st_id}/sets/{set_id}/things/{thing_id}", response_model=Stage)
async def stage_thing_rename(svc: Svc, st_id: str, set_id: str, thing_id: str, body: ThingPatch):
    ws, _, _ = svc.require_project()
    try:
        st = await asyncio.to_thread(set_things.rename_thing, StageStore(ws), st_id, set_id, thing_id, body.name)
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


@router.delete("/stages/{st_id}/sets/{set_id}/things/{thing_id}", response_model=Stage)
async def stage_thing_remove(svc: Svc, st_id: str, set_id: str, thing_id: str):
    """The thing leaves the list; its mask stays in the Catalogue and a prop made of it stays on the stage."""
    ws, _, _ = svc.require_project()
    try:
        st = await asyncio.to_thread(set_things.remove_thing, StageStore(ws), st_id, set_id, thing_id)
    except (KeyError, ValueError) as e:
        raise _things_error(e) from e
    svc.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    return st.model_dump()


@router.post("/stages/{st_id}/passes", response_model=Stage)
async def stage_passes(svc: Svc, st_id: str, body: PassesUpload):
    """Each pass becomes an asset (`lineage_kind = stage-pass`, suite stage, `params {stage_id, camera_id, revision, pass, size}`, the
    keypoints on the pose pass, the legend on the mask pass) placed on the stage's album page (made on first use, D34); the document
    records them for the camera and comes back at its new revision."""
    ws, catalogue, _ = svc.require_project()
    groups = svc.require_groups()
    store = StageStore(ws)
    st = await asyncio.to_thread(store.get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if not any(c.id == body.camera_id for c in st.cameras):
        raise HTTPException(422, f"camera {body.camera_id!r} is not in the stage")
    bad = [k for k in body.passes if k not in STAGE_PASSES]
    if bad or not body.passes:
        raise HTTPException(422, f"passes are {', '.join(STAGE_PASSES)}; got {sorted(body.passes) or 'none'}")
    files = {}
    for name, sha in body.passes.items():
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise HTTPException(422, f"pass {name}: a blob id is a lowercase sha256")
        p = ws.temp_dir / "blobs" / sha
        if not p.is_file():
            raise HTTPException(422, f"pass {name}: blob {sha[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
        files[name] = p
    gid = st.group_id if st.group_id and st.group_id in groups.groups else None
    if gid is None:
        gid = (await asyncio.to_thread(groups.create, f"Stage · {st.name}")).id
    origin = JobOrigin(suite="stage", surface="passes", ref=st_id, payload={"camera_id": body.camera_id})
    assets: dict[str, str] = {}
    for name, p in files.items():
        params = {"stage_id": st_id, "camera_id": body.camera_id, "revision": body.revision, "pass": name, "size": body.size}
        if name == "pose":
            params["keypoints"] = body.keypoints
        if name == "mask":
            params["legend"] = body.legend
        rec = await asyncio.to_thread(catalogue.ingest_file, p, kind="image", move=False, suite="stage", lineage_kind="stage-pass", origin=origin, params=params,
                                      prompt_text=f"{st.name} · {name} pass")
        rec = await asyncio.to_thread(catalogue.make_thumbs, rec)
        svc.hub.broadcast("asset.created", rec.model_dump())
        assets[name] = rec.id
    await asyncio.to_thread(groups.move, [("asset", a) for a in assets.values()], gid)
    entry = {"camera_id": body.camera_id, "revision": body.revision, "size": body.size, "assets": assets, "keypoints": body.keypoints, "legend": body.legend,
             "rendered_at": utc_now()}
    st2 = await asyncio.to_thread(store.set_passes, st_id, entry, gid)
    svc.hub.broadcast("stage.updated", {"id": st2.id, "revision": st2.revision})
    return st2.model_dump()


class GuideUpload(BaseModel):
    """ST4 (16 §8): a pass rendered per frame of the range — each frame a PNG put through `PUT /blobs/{sha}`, in order — with the
    per-frame COCO-18 keypoints (for the rig's scoring)."""
    camera_id: str
    revision: int
    kind: str = "depth"                           # depth | pose
    fps: int = 24
    size: dict[str, int]
    range: dict[str, int]                         # {start, end} of the document's frames the sequence covers
    frames: list[str]                             # blob sha256 per frame
    keypoints: list[Any] = []                     # per frame: per figure 18 × [x, y, visible]


@router.post("/stages/{st_id}/guide", response_model=Stage)
async def stage_guide(svc: Svc, st_id: str, body: GuideUpload):
    """The frames become one video asset (h264 near-lossless, `kind = video`, suite stage, `lineage_kind = stage-pass`, `params {stage_id,
    camera_id, revision, pass: "<kind>-sequence", frames, fps, size, range, keypoints}`) on the stage's album page; the document records
    it under the camera's passes entry (`guides[kind]`) and comes back at its new revision."""
    ws, catalogue, _ = svc.require_project()
    groups = svc.require_groups()
    store = StageStore(ws)
    st = await asyncio.to_thread(store.get, st_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if not any(c.id == body.camera_id for c in st.cameras):
        raise HTTPException(422, f"camera {body.camera_id!r} is not in the stage")
    if body.kind not in ("depth", "pose"):
        raise HTTPException(422, "a guide is the depth or the pose sequence")
    if len(body.frames) < 2:
        raise HTTPException(422, "a sequence needs at least two frames")
    if body.fps < 1 or body.fps > 60:
        raise HTTPException(422, "fps is 1–60")
    paths = []
    for i, sha in enumerate(body.frames):
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise HTTPException(422, f"frame {i}: a blob id is a lowercase sha256")
        p = ws.temp_dir / "blobs" / sha
        if not p.is_file():
            raise HTTPException(422, f"frame {i}: blob {sha[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
        paths.append(p)
    gid = st.group_id if st.group_id and st.group_id in groups.groups else None
    if gid is None:
        gid = (await asyncio.to_thread(groups.create, f"Stage · {st.name}")).id
    out_dir = ws.stages_dir / st_id / "guides"
    out = out_dir / f"{body.camera_id}-{body.kind}-r{body.revision}.mp4"
    await asyncio.to_thread(encode_guide, paths, out, body.fps)
    origin = JobOrigin(suite="stage", surface="guide", ref=st_id, payload={"camera_id": body.camera_id, "kind": body.kind})
    params = {"stage_id": st_id, "camera_id": body.camera_id, "revision": body.revision, "pass": f"{body.kind}-sequence", "frames": len(paths), "fps": body.fps,
              "size": body.size, "range": body.range, "keypoints": body.keypoints}
    rec = await asyncio.to_thread(catalogue.ingest_file, out, kind="video", in_place=True, suite="stage", lineage_kind="stage-pass", origin=origin, params=params,
                                  prompt_text=f"{st.name} · {body.kind} sequence", frames=len(paths), fps=float(body.fps), w=int(body.size.get("w", 0)) or None,
                                  h=int(body.size.get("h", 0)) or None)
    rec = await asyncio.to_thread(catalogue.make_thumbs, rec, paths[0])
    svc.hub.broadcast("asset.created", rec.model_dump())
    await asyncio.to_thread(groups.move, [("asset", rec.id)], gid)
    guide = {"asset_id": rec.id, "frames": len(paths), "fps": body.fps, "size": body.size, "range": body.range, "revision": body.revision, "rendered_at": utc_now()}
    st2 = await asyncio.to_thread(store.set_guide, st_id, body.camera_id, body.kind, guide, gid)
    svc.hub.broadcast("stage.updated", {"id": st2.id, "revision": st2.revision})
    return st2.model_dump()


@router.delete("/stages/{st_id}", response_model=Deleted)
async def stage_delete(svc: Svc, st_id: str):
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(StageStore(ws).delete, st_id):
        raise HTTPException(404, "stage not found")
    svc.hub.broadcast("stage.deleted", {"id": st_id})
    return {"deleted": st_id}
