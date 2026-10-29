"""D111 (PS5): the final shot — make one from a finished Stage scene (its layers' passes uploaded as blobs), list, read, a pass frame, delete."""
from __future__ import annotations

import asyncio
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..compositions import Composition, CompositionStore
from ..effectcraft import EffectCraftError
from ..finals import LAYER_PASSES, Final, FinalLayer, FinalStore
from ..recipes import RenderSettings
from ..schemas import Deleted
from ..stages import StageStore
from .deps import Svc

router = APIRouter(tags=["finals"])


class FinalLayerIn(BaseModel):
    id: str
    kind: str
    name: str
    object_id: str | None = None
    method: str | None = None                      # None = the kind's default (finals.DEFAULT_METHOD)
    profile_id: str | None = None
    version: str | None = None
    passes: dict[str, list[str]]                   # pass name → the frames' blob ids (sha256), in order
    keypoints: list[Any] | None = None             # a figure's per-frame keypoints (Stage's COCO-18 for that figure)
    body: dict[str, Any] | None = None             # CS3: a figure's body as its guide was drawn
    body_hashes: list[str] = Field(default_factory=list)   # CS3: per frame, the hash of the body the guide was drawn with


class FinalCreate(BaseModel):
    name: str = "Final"
    stage_id: str
    camera_id: str
    stage_revision: int
    range: dict[str, int]
    rate: int = 16
    size: dict[str, int]
    frames: int
    shot_id: str | None = None
    shot_version: str | None = None                # D125 (A1): the version it is made for; None: the shot's current one
    layers: list[FinalLayerIn] = Field(default_factory=list)


class FinalList(BaseModel):
    items: list[Final]


def _blob(ws, sha: str):
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise HTTPException(422, f"{sha[:16]}…: a blob id is a lowercase sha256")
    p = ws.temp_dir / "blobs" / sha
    if not p.is_file():
        raise HTTPException(422, f"blob {sha[:12]}… was not uploaded (PUT /blobs/{{sha}} first)")
    return p


def _reconcile(svc, store: FinalStore, f: Final) -> Final:
    """A layer at work whose last job failed or was cancelled is failed too (the job's error on it) — the queue cannot tell the final."""
    if svc.queue is None:
        return f
    for x in f.layers:
        if x.status in ("queued", "running") and x.job_ids:
            j = svc.queue.jobs.get(x.job_ids[-1])
            if j is not None and j.status in ("failed", "cancelled"):
                f = store.update_layer(f.id, x.id, status="failed", error=j.error or f"its job was {j.status}")
    return f


@router.post("/finals", response_model=Final)
async def final_create(svc: Svc, body: FinalCreate):
    """PS5a: a final from the scene's layers — the record and each layer's passes (Stage's renders at the shot's rate) on disk. SC3e: on a
    stage with a picture set the plate is that picture (method `picture`: Stage renders it through the relief), not a Klein still."""
    from ..finals import DEFAULT_METHOD, built_plate, picture_plate
    ws, _, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, body.stage_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if body.camera_id not in [c.id for c in st.cameras]:
        raise HTTPException(422, f"camera {body.camera_id} is not in the stage")
    for x in body.layers:
        if x.kind not in LAYER_PASSES:
            raise HTTPException(422, f"layer {x.id}: a layer is a plate, a figure, a prop or the shadows")
    if body.shot_id:                                                       # D125 (A1): made for a Story shot — its open version takes the final's clips
        from ..story import StoryStore
        shot = await asyncio.to_thread(StoryStore(ws).shot, body.shot_id)
        if shot is None:
            raise HTTPException(422, f"shot {body.shot_id} not found")
        v = next((x for x in shot.versions if x.id == (body.shot_version or shot.current)), None)
        if v is None:
            raise HTTPException(422, f"{shot.name} has no version {body.shot_version}")
        if v.state != "open":
            raise HTTPException(422, f"{shot.name} {v.id} is final — make a new version for another take")
        body = body.model_copy(update={"shot_version": v.id})
    passes = {x.id: {name: [_blob(ws, sha) for sha in shas] for name, shas in x.passes.items()} for x in body.layers}
    keypoints = {x.id: x.keypoints for x in body.layers if x.keypoints is not None}
    method = DEFAULT_METHOD | ({"plate": "picture"} if picture_plate(st) else {"plate": "set"} if built_plate(st) else {})   # CW7: a built set's plate is the set
    pick = {x.id: method[x.kind] if x.kind == "plate" and method["plate"] in ("picture", "set") else x.method or method[x.kind] for x in body.layers}   # CA3: the client's plate method, a picture or built set's first
    data = body.model_dump(exclude={"layers"}) | {"layers": [FinalLayer(id=x.id, kind=x.kind, name=x.name, object_id=x.object_id, method=pick[x.id],  # type: ignore[arg-type]
                                                                        profile_id=x.profile_id, version=x.version, body=x.body, body_hashes=x.body_hashes).model_dump() for x in body.layers]}
    from ..shot_graph import stage_stamps
    data["stamps"] = stage_stamps(st, body.camera_id)                        # RC1: an edit marks only the layers it touches
    try:
        f = await asyncio.to_thread(FinalStore(ws).create, data, passes, keypoints)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if f.shot_id and f.shot_version:                                     # RC1: a version made by a final shot is on the clay route
        from ..story import StoryStore
        store = StoryStore(ws)
        shot = await asyncio.to_thread(store.shot, f.shot_id)
        v = next((x for x in shot.versions if x.id == f.shot_version), None) if shot else None
        if v is not None and not (v.recipe and v.recipe.template):
            clay = "clay2" if sum(1 for x in f.layers if x.kind == "figure") > 1 else "clay1"
            await asyncio.to_thread(store.set_template, f.shot_id, f.shot_version, clay)
            svc.hub.broadcast("story.changed", {"kind": "shot", "id": f.shot_id, "revision": 0})
    svc.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
    return f.model_dump()


@router.get("/finals", response_model=FinalList)
async def finals_list(svc: Svc, stage_id: str | None = None):
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    finals = await asyncio.to_thread(store.list, stage_id)
    return {"items": [(await asyncio.to_thread(_reconcile, svc, store, f)).model_dump() for f in finals]}


@router.get("/finals/{fid}", response_model=Final)
async def final_get(svc: Svc, fid: str):
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    return (await asyncio.to_thread(_reconcile, svc, store, f)).model_dump()


@router.get("/finals/{fid}/layers/{lid}/{name}/{n}")
async def final_frame(svc: Svc, fid: str, lid: str, name: str, n: int):
    """A layer's pass (or own) frame as PNG — the panel's previews."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None or not any(x.id == lid for x in f.layers):
        raise HTTPException(404, "final or layer not found")
    if not name.replace("_", "").isalnum():
        raise HTTPException(422, "a pass name is a word")
    p = store.pass_dir(fid, lid, name) / f"{n:04d}.png"
    if not p.is_file():
        raise HTTPException(404, "no such frame")
    return FileResponse(p, media_type="image/png")


class PlateBody(BaseModel):
    prompt_text: str = ""                          # what the place is; the lead (no people, no objects) goes first
    refs: list[dict[str, Any]] = Field(default_factory=list)   # the reference deck (a place's images, the World style's sample)
    seed: int = 0


class PlateQueued(BaseModel):
    job_id: str
    pass_asset_id: str
    scene_plate: str | None = None                 # O4 (D130): the scene's first plate, put first among the still's references


def _scene_plate(ws, f: Final) -> str | None:
    """O4 (D130, RC2f): the scene's first plate — a Shot in a scene takes the plate still of the first Shot before it in the scene (the
    Flow's order) that has one, so a scene's Shots are one place; None outside a scene or for the scene's first Shot."""
    from ..story import StoryStore
    if not f.shot_id:
        return None
    story = StoryStore(ws)
    nodes = story.flow_nodes()
    for sc in story.scenes():
        shots = [nodes[nid].shot_id for nid in sc["node_ids"] if nid in nodes and nodes[nid].shot_id]
        if f.shot_id not in shots:
            continue
        finals = FinalStore(ws).list()                                      # the newest first: a Shot's plate made again replaces its first
        for sid in shots[:shots.index(f.shot_id)]:
            for x in finals:
                plate = next((y for y in x.layers if y.id == "plate"), None)
                if x.shot_id == sid and x.id != f.id and plate is not None and plate.still_asset_id:
                    return plate.still_asset_id
        return None
    return None


@router.post("/finals/{fid}/plate", response_model=PlateQueued)
async def final_plate(svc: Svc, fid: str, body: PlateBody):
    """PS5b: the plate's still — the bare set's lit clay at frame 0 (from the final's plate pass) as a Stage shot's image 1 (Klein, the clay
    method), the lead first so the model draws no people or objects (they are layers). Stage then projects it along the camera path."""
    from ..finals import FINAL_PLATE_SURFACE, PLATE_LEAD, plate_method_check
    from ..models import registry
    from ..origin import JobOrigin
    ws, cat, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    plate = next(x for x in f.layers if x.id == "plate")
    if plate.method in ("picture", "set"):                                                   # SC3e, CW7
        raise HTTPException(422, "the plate is the set's picture or the built set: Stage renders it (no Klein still)")
    if plate.method == "generated":                                                          # CA3: refused now, not after the still
        try:
            plate_method_check("generated", f.frames)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not any(s.recipes.guide_lora and registry.offered(s, svc.app.settings.variant) for s in registry.video_specs()):
            raise HTTPException(422, "no video model with a depth guide in this build (LTX-2.3 and its IC-LoRA) — project the plate (its row's right-click)")
    src = store.pass_dir(fid, "plate", "clay") / "0000.png"
    if not src.is_file():
        raise HTTPException(422, "the plate's clay pass is missing")
    rec = await asyncio.to_thread(cat.ingest_file, src, kind="image", move=False, suite="stage", lineage_kind="stage-pass",
                                  origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=fid), params={"final_id": fid, "pass": "clay", "stage_id": f.stage_id})
    rec = await asyncio.to_thread(cat.make_thumbs, rec, src)
    svc.hub.broadcast("asset.created", rec.model_dump())
    fmt = ws.load().format
    h = 720
    w = max(64, round(h * fmt.width / fmt.height / 16) * 16)
    first = await asyncio.to_thread(_scene_plate, ws, f)                    # O4: the scene's first plate leads the references
    refs = ([{"asset_id": first, "note": "the same place as this picture: its walls, floor, light and materials"}] if first else []) + \
        [r for r in body.refs if r.get("asset_id") != first]
    recipe = {"kind": "stage_shot", "stage_id": f.stage_id, "camera_id": f.camera_id, "passes": {"clay": rec.id}, "method": "clay", "empty": True,
              "prompt_text": f"{PLATE_LEAD} {body.prompt_text.strip()}".strip(), "refs": refs, "seeds": [body.seed], "width": w, "height": h}
    try:
        jobs = svc.queue.submit(recipe, origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=fid, payload={"prompt": body.prompt_text.strip()}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.add_job, fid, "plate", jobs[0].id, status="queued", error=None, clip_id=None, frames_done=0,
                                prompt=body.prompt_text.strip(), keys=[])
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id, "pass_asset_id": rec.id, "scene_plate": first}


class PlateMethodBody(BaseModel):
    method: Literal["projected", "filled", "generated"]
    prompt_text: str = ""                          # what the place is (the Shot tab's prompt): a still already made is generated along the path with it


@router.put("/finals/{fid}/layers/plate/method", response_model=Final)
async def final_plate_method(svc: Svc, fid: str, body: PlateMethodBody):
    """CA3 (D130): the plate projected (PS5b: the still cast along the path by Stage, no GPU job) or generated along the path (LTX-2.3 from the
    still on the bare set's depth). A still already made is kept: projected, Stage projects it when the stage is open; generated, its clip is
    queued now. Without a still the method waits for *Make the plate*."""
    from ..engine.finishers import queue_plate_path
    from ..finals import plate_method_check
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    f = await asyncio.to_thread(_reconcile, svc, store, f)
    plate = next(x for x in f.layers if x.id == "plate")
    if plate.method in ("picture", "set"):
        raise HTTPException(422, "the plate is the set's picture (SC3e) or the built set (CW7): it is neither projected nor generated")
    if plate.status in ("queued", "running") and not (plate.status == "running" and plate.method in ("projected", "filled") and plate.still_asset_id
                                                       and not any(k.get("asset_id") is None for k in plate.keys)):
        raise HTTPException(409, "the plate is being made — wait for it, or cancel its job")
    try:
        plate_method_check(body.method, f.frames)
    except ValueError as e:
        raise HTTPException(422, str(e))
    still = plate.still_asset_id
    f = await asyncio.to_thread(store.update_layer, fid, "plate", method=body.method, error=None, clip_id=None, keys=[],
                                **({"prompt": body.prompt_text.strip()} if body.prompt_text.strip() else {}),      # PF1: the place the Fills continue
                                **({"status": "running", "frames_done": 0} if still and body.method in ("projected", "filled") else {} if still else {"status": "passes"}))
    if still and body.method == "generated":
        if svc.queue is None:
            raise HTTPException(409, "no queue")
        try:
            await queue_plate_path(svc.queue, fid, still, body.prompt_text)
        except ValueError as e:
            f = await asyncio.to_thread(store.update_layer, fid, "plate", method=plate.method)
            raise HTTPException(422, str(e))
        await svc.queue.flush()
        f = await asyncio.to_thread(store.get, fid)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


class HealBody(BaseModel):
    heal: bool


@router.put("/finals/{fid}/layers/plate/heal", response_model=Final)
async def final_plate_heal(svc: Svc, fid: str, body: HealBody):
    """PF1 (Q29): the filled plate's in-between heal on or off — kept on the layer; Stage heals the frames between keyframes when it is on
    (the next time it fills the plate: *Project and fill* again)."""
    ws, _, _ = svc.require_project()
    try:
        f = await asyncio.to_thread(FinalStore(ws).update_layer, fid, "plate", heal=body.heal)
    except KeyError:
        raise HTTPException(404, "final not found")
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


class KeyBody(BaseModel):
    frame: int = Field(ge=1)
    image: str                                     # the keyframe's projected composite (a blob's sha256, PNG at the still's size)
    mask: str                                      # its bad pixels (a blob's sha256, PNG: white = fill)
    heal: bool = False                             # a heal keyframe (Q29) rather than a placed one


@router.post("/finals/{fid}/plate/keys", response_model=Final)
async def final_plate_key(svc: Svc, fid: str, body: KeyBody):
    """PF1 (D135): a filled plate's keyframe — Stage's projection of the keyframes before it into this frame's view, and the pixels none of
    them saw well. The composite becomes an Edit document with those pixels as its selection, and its Fill (Klein, expand 48, feather 32,
    one seed for the plate, the place's surfaces as the prompt) is queued; its finisher flattens the document into the keyframe. A
    keyframe with almost nothing to fill (< 0.2 %) is the composite itself."""
    import numpy as np
    from PIL import Image

    from ..finals import FINAL_PLATE_KEY_SURFACE, KEY_FILL_MIN, plate_fill_prompt
    from ..models import registry
    from ..origin import JobOrigin
    ws, cat, q = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    plate = next(x for x in f.layers if x.id == "plate")
    if plate.method != "filled":
        raise HTTPException(422, "the plate is not projected and filled — pick *Project and fill* on its row")
    if not plate.still_asset_id:
        raise HTTPException(422, "the plate has no still yet")
    if body.frame >= f.frames:
        raise HTTPException(422, f"a keyframe is one of the final's frames 1–{f.frames - 1}")
    image, mask_png = _blob(ws, body.image), _blob(ws, body.mask)

    def prepare() -> tuple[Any, np.ndarray]:
        rec = cat.ingest_file(image, kind="image", move=False, suite="stage", lineage_kind="stage-pass", parents=[plate.still_asset_id],
                              params={"final_id": fid, "pass": "plate-key", "frame": body.frame, "heal": body.heal})
        rec = cat.make_thumbs(rec)
        with Image.open(mask_png) as m:
            mask = np.asarray(m.convert("L")) > 127
        return rec, mask
    rec, mask = await asyncio.to_thread(prepare)
    svc.hub.broadcast("asset.created", rec.model_dump())
    if mask.shape != (rec.h, rec.w):
        raise HTTPException(422, f"the mask ({mask.shape[1]}×{mask.shape[0]}) is not the keyframe's size ({rec.w}×{rec.h})")
    share = float(mask.mean())
    key: dict[str, Any] = {"frame": body.frame, "asset_id": rec.id, "filled": round(share, 4), "job_id": None, "heal": body.heal}
    if share >= KEY_FILL_MIN:
        docs = svc.require_documents()

        def document() -> Any:
            with Image.open(cat.abs_path(rec)) as im:
                base = np.asarray(im.convert("RGBA"))
            od = docs.create(f"{f.name} · plate key {body.frame}", int(base.shape[1]), int(base.shape[0]), "transparent", rec.id, base)
            od.selection = np.where(mask, 255, 0).astype(np.uint8)
            od.doc.has_selection = True
            od.dirty = True
            od.save()
            return od
        od = await asyncio.to_thread(document)
        seed = plate.seed or secrets.randbelow(2**31 - 2) + 1
        try:
            job = q.submit({"kind": "inpaint", "mode": "fill", "model_id": registry.default_model("inpaint", svc.app.settings.variant),   # Klein 4B under `open` (D26)
                            "document_id": od.doc.id, "prompt_text": plate_fill_prompt(plate.prompt), "seeds": [seed], "expand": 48, "feather": 32},
                           origin=JobOrigin(suite="stage", surface=FINAL_PLATE_KEY_SURFACE, ref=fid, payload={"frame": body.frame, "document_id": od.doc.id}))[0]
        except ValueError as e:
            raise HTTPException(422, str(e))
        await q.flush()
        key.update(asset_id=None, job_id=job.id)
        await asyncio.to_thread(store.add_job, fid, "plate", job.id, seed=seed, status="running", error=None)
    f = await asyncio.to_thread(store.set_key, fid, key)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


class FramesBody(BaseModel):
    frames: list[str]                              # the layer's own frames' blob ids (sha256), one per frame of the final


@router.put("/finals/{fid}/layers/{lid}/frames", response_model=Final)
async def final_layer_frames(svc: Svc, fid: str, lid: str, body: FramesBody):
    """A layer's own sequence made by the client (PS5b: the projected plate; SC3e: the picture plate, its still stamped as the stage's
    picture — the lineage the assembled shot carries) — stored as its `frames/`; the layer is done."""
    from ..finals import built_plate, picture_plate
    ws, _, _ = svc.require_project()
    files = [_blob(ws, sha) for sha in body.frames]
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f is not None else None
    still = None
    if layer is not None and layer.method in ("picture", "set"):
        st = await asyncio.to_thread(StageStore(ws).get, f.stage_id)
        still = (picture_plate(st) if layer.method == "picture" else built_plate(st)) if st is not None else None   # CW7: the built set's picture stamped as the still
        if still is None:
            raise HTTPException(422, "the stage has no picture set any more: the plate cannot be its picture" if layer.method == "picture"
                                else "the stage has no built set with baked faces any more: the plate cannot be the set")
    try:
        f = await asyncio.to_thread(store.set_frames, fid, lid, files, "done", still)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


class RunBody(BaseModel):
    seed: int | None = None                        # None: the layer's seed (the first run 0; a re-take passes another)
    from_batch: int = Field(0, ge=0)               # CA5: re-take from this batch on (the batches before it kept; a new seed unless one is given)
    stage: bool = False                            # CA4: staged in the queue (released by Run staged — an overnight start), not queued


class RunQueued(BaseModel):
    job_id: str
    batches: int
    reference_asset_id: str
    placed: bool                                   # the reference stands where the figure starts (else padded, centred)


@router.post("/finals/{fid}/layers/{lid}/run", response_model=RunQueued)
async def final_layer_run(svc: Svc, fid: str, lid: str, body: RunBody):
    """PS5c: perform a character layer — its figure's character (the bound Cast version's animation reference) placed where the figure
    starts (E23c: no ghost), Wan Animate Move on the layer's pose sequence in 77-frame batches (E23a W1), each batch queuing the next.
    A run again is a re-take of this layer alone."""
    from ..catalogue import Catalogue  # noqa: F401  (typing)
    from ..finals import FINAL_LAYER_SURFACE, CHARACTER_TAIL, character_recipe, place_reference, plan_batches
    from ..origin import JobOrigin
    from ..story import StoryStore, compose_sheet
    from ..models import registry
    ws, cat, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f else None
    if f is None or layer is None:
        raise HTTPException(404, "final or layer not found")
    if layer.kind != "figure":
        raise HTTPException(422, "only a character layer is performed (the plate is projected, a prop rendered)")
    if layer.status in ("queued", "running") and layer.batches:
        raise HTTPException(409, "the layer is being performed — wait for it, or cancel its job")
    p = await asyncio.to_thread(StoryStore(ws).profile, layer.profile_id) if layer.profile_id else None
    if p is None:
        raise HTTPException(422, f"bind {layer.name} to a character first (Animate's Inspector): its animation reference performs the layer")
    try:
        v = p.version(layer.version)
    except KeyError as e:
        raise HTTPException(422, str(e))
    if not v.anim_ref_asset_id:
        raise HTTPException(422, f"{p.name} has no animation reference yet — make it in Story · Cast")
    spec = next((s for s in registry.animate_specs() if registry.offered(s, svc.app.settings.variant)), None)
    if spec is None:
        raise HTTPException(422, "no pose-driven model in this build")
    ref = cat.get(v.anim_ref_asset_id)
    if ref is None:
        raise HTTPException(422, "the animation reference is missing from the Catalogue")
    if body.from_batch:                                                      # CA5: re-take from a batch on, the batches before it kept
        return await _retake_from(svc, store, f, layer, body, spec.id, f"{p.name}, {compose_sheet(v, name=p.name)}, {CHARACTER_TAIL}", v.anim_ref_asset_id)
    w, h = f.size["w"], f.size["h"]
    folder = store.folder(fid) / lid
    kp = (await asyncio.to_thread(store.keypoints, fid, lid) or [None])[0]
    placed_png = folder / "reference.png"
    try:
        placed = await asyncio.to_thread(place_reference, cat.abs_path(ref), kp, w, h, placed_png)
    except ValueError:                                                        # no plain ground to key the character off: CN4's padded reference
        placed = False
    if placed:
        rec = await asyncio.to_thread(cat.ingest_file, placed_png, kind="image", move=False, suite="stage", lineage_kind="stage-pass", parents=[ref.id],
                                      origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid), params={"final_id": fid, "layer": lid, "pass": "reference"})
        rec = await asyncio.to_thread(cat.make_thumbs, rec, placed_png)
        svc.hub.broadcast("asset.created", rec.model_dump())
        ref_id = rec.id
    else:
        ref_id = ref.id                                                       # the figure is not whole at the start: CN4's padded reference
    g = await _guide_video(cat, store, f, lid)
    seed = layer.seed if body.seed is None else body.seed
    layer.reference_asset_id, layer.guide_asset_id, layer.seed = ref_id, g.id, seed
    plan = plan_batches(f.frames)
    prompt = f"{p.name}, {compose_sheet(v, name=p.name)}, {CHARACTER_TAIL}"
    try:
        jobs = svc.queue.submit(character_recipe(f, layer, spec.id, prompt, plan[0], None), stage=body.stage,
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid, payload={"layer": lid, "batch": 0, "batches": len(plan), "prompt": prompt}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.add_job, fid, lid, jobs[0].id, status="queued", error=None, seed=seed, reference_asset_id=ref_id, guide_asset_id=g.id,
                                batches=[{"k": 0, "job_id": jobs[0].id, "clip_id": None}], frames_done=0)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id, "batches": len(plan), "reference_asset_id": ref_id, "placed": placed}


async def _guide_video(cat, store: FinalStore, f: Final, lid: str):
    """PS5c: a character layer's pose pass as one video in the Catalogue (lineage stage-pass) — Wan Animate's guide."""
    from ..finals import FINAL_LAYER_SURFACE
    from ..origin import JobOrigin
    from ..stages import encode_guide
    pose = sorted(store.pass_dir(f.id, lid, "pose").glob("*.png"))
    guide_mp4 = store.folder(f.id) / lid / "pose.mp4"
    await asyncio.to_thread(encode_guide, pose, guide_mp4, f.rate)
    g = await asyncio.to_thread(cat.ingest_file, guide_mp4, kind="video", move=False, suite="stage", lineage_kind="stage-pass",
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id), params={"final_id": f.id, "layer": lid, "pass": "pose-sequence"},
                                frames=len(pose), fps=float(f.rate), w=f.size["w"], h=f.size["h"])
    return await asyncio.to_thread(cat.make_thumbs, g, pose[0])


class PassesBody(BaseModel):
    passes: dict[str, list[str]]                   # pass name → the frames' blob ids (sha256), in order: the pose and the depth
    keypoints: list[Any] | None = None
    body: dict[str, Any] | None = None             # the figure's body as the guide was drawn now
    body_hashes: list[str] = Field(default_factory=list)


@router.put("/finals/{fid}/layers/{lid}/passes", response_model=Final)
async def final_layer_passes(svc: Svc, fid: str, lid: str, body: PassesBody):
    """CS3 (proto01_UIcast 06 §2.10, D136 U19): a character layer's passes drawn again by Stage — the skeleton changed. They replace the old
    ones, and a performed layer's guide video is encoded again: a re-take from a batch then performs the new guide (*Apply from a frame…*:
    the frames before the skeleton key unchanged), a run performs all of it (*Re-render with the new skeleton*)."""
    ws, cat, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f else None
    if f is None or layer is None:
        raise HTTPException(404, "final or layer not found")
    if layer.status in ("queued", "running"):
        raise HTTPException(409, "the layer is being performed — wait for it, or cancel its job")
    files = {name: [_blob(ws, sha) for sha in shas] for name, shas in body.passes.items()}
    try:
        f = await asyncio.to_thread(store.set_passes, fid, lid, files, body.keypoints, body.body, body.body_hashes)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if layer.guide_asset_id:
        g = await _guide_video(cat, store, f, lid)
        f = await asyncio.to_thread(store.update_layer, fid, lid, guide_asset_id=g.id)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


async def _retake_from(svc, store: FinalStore, f: Final, layer: FinalLayer, body: RunBody, model_id: str, prompt: str, anim_ref: str | None) -> dict:
    """CA5 (02 §3): batch k and the ones after it again with a new seed — batch k continues the kept batch k−1's clip (its last frames
    carried, W1) on the layer's placed reference and pose guide; each finisher queues the next, the last stitches every batch and mattes."""
    from ..finals import FINAL_LAYER_SURFACE, character_recipe, plan_batches
    from ..origin import JobOrigin
    k = body.from_batch
    plan = plan_batches(f.frames)
    kept = [dict(b) for b in layer.batches[:k]]
    if k >= len(plan):
        raise HTTPException(422, f"{layer.name} has {len(plan)} batch{'es' if len(plan) != 1 else ''}")
    if len(kept) < k or not all(b.get("clip_id") for b in kept) or not layer.reference_asset_id or not layer.guide_asset_id:
        raise HTTPException(422, f"batch {k + 1} is re-taken after the batches before it are made")
    seed = layer.seed + 1 if body.seed is None else body.seed
    redo = layer.model_copy(update={"seed": seed})
    try:
        jobs = svc.queue.submit(character_recipe(f, redo, model_id, prompt, plan[k], kept[-1]["clip_id"]), stage=body.stage,
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id, payload={"layer": layer.id, "batch": k, "batches": len(plan), "prompt": prompt}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f2 = await asyncio.to_thread(store.add_job, f.id, layer.id, jobs[0].id, status="queued", error=None, seed=seed, frames_done=0,
                                 batches=[*kept, {"k": k, "job_id": jobs[0].id, "clip_id": None}])
    svc.hub.broadcast("final.updated", {"id": f.id, "revision": f2.revision})
    return {"job_id": jobs[0].id, "batches": len(plan), "reference_asset_id": layer.reference_asset_id, "placed": layer.reference_asset_id != anim_ref}


class PlanBatch(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    k: int
    frames: int                                    # the batch's frames (the carried 5 included after the first)
    covers: list[int]                              # the final's frames it adds: [first, last]
    state: Literal["done", "running", "queued", "staged", "failed", "owed"]
    job_id: str | None = None
    clip_id: str | None = None
    seconds: float | None = None                   # its wall time when done, else its cost


class PlanLayer(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    name: str
    seed: int
    batches: list[PlanBatch]
    seconds_owed: float


class FinalPlan(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    final_id: str
    layers: list[PlanLayer]
    seconds_owed: float
    source: str                                    # where the cost comes from: this final's batches measured, else the queue's estimate


@router.get("/finals/{fid}/plan", response_model=FinalPlan)
async def final_plan(svc: Svc, fid: str):
    """CA4 (02 §3, proto01_animate 31 §4): the character layers' batches — the frames each adds, each one's state, its time when done, else
    its cost: the mean of this final's measured batches scaled by frames, else the queue's estimate (D60: what the job would run) — and the
    shot's total still owed."""
    from ..finals import CARRY, character_recipe, plan_batches
    from ..models import registry
    from ..recipes import parse_recipe
    ws, _, _ = svc.require_project()
    f = await asyncio.to_thread(FinalStore(ws).get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    plan = plan_batches(f.frames)
    jobs = svc.queue.jobs if svc.queue else {}
    figures = [x for x in f.layers if x.kind == "figure"]
    measured = [(jobs[b["job_id"]].wall_s, plan[b["k"]]["frames"]) for x in figures for b in x.batches
                if b.get("clip_id") and b.get("job_id") in jobs and jobs[b["job_id"]].wall_s and b["k"] < len(plan)]
    per_frame = sum(s for s, _ in measured) / sum(n for _, n in measured) if measured else None
    spec = next((s for s in registry.animate_specs() if registry.offered(s, svc.app.settings.variant)), None)

    def cost(b: dict[str, int]) -> float | None:
        if per_frame is not None:
            return round(per_frame * b["frames"], 1)
        if spec is None or svc.queue is None:
            return None
        probe = figures[0].model_copy(update={"reference_asset_id": "ast_plan", "guide_asset_id": "ast_plan"})
        try:
            return svc.queue.estimate(parse_recipe(character_recipe(f, probe, spec.id, "", b, None))).get("seconds")
        except Exception:                                                     # noqa: BLE001 — a cost is advice, never a failure
            return None
    out, owed_all = [], 0.0
    for x in figures:
        rows, owed = [], 0.0
        for k, b in enumerate(plan):
            covers = [b["offset"], min(f.frames, b["offset"] + b["frames"] - (CARRY if k else 0)) - 1]   # a later batch: its carried 5 come before its offset
            have = x.batches[k] if k < len(x.batches) else None
            j = jobs.get(have["job_id"]) if have and have.get("job_id") else None
            state = "done" if have and have.get("clip_id") else (j.status if j is not None and j.status in ("running", "queued", "staged", "failed") else "owed")
            secs = j.wall_s if state == "done" and j is not None and j.wall_s else cost(b)
            if state != "done" and secs:
                owed += secs
            rows.append(PlanBatch(k=k, frames=b["frames"], covers=covers, state=state, job_id=have.get("job_id") if have else None,   # type: ignore[arg-type]
                                  clip_id=have.get("clip_id") if have else None, seconds=round(secs, 1) if secs else None))
        out.append(PlanLayer(id=x.id, name=x.name, seed=x.seed, batches=rows, seconds_owed=round(owed, 1)))
        owed_all += owed
    src = f"measured: {len(measured)} batch{'es' if len(measured) != 1 else ''} of this final" if per_frame is not None else "the queue's estimate"
    return FinalPlan(final_id=fid, layers=out, seconds_owed=round(owed_all, 1), source=src).model_dump()


class MatteBody(BaseModel):
    text: str = "person"                           # what SAM 3 looks for in the layer's frames


class PassBody(BaseModel):
    """D118 (AE4a): a pass on the layer — the preset and its strength; a seed given is a re-run with another. AE4c: `face` and `lipsync`
    (the strength unused)."""
    preset: Literal["cleanup", "creative", "face", "lipsync"] = "cleanup"
    strength: float = Field(0.10, ge=0.02, le=0.9)
    seed: int | None = None
    mouth: Literal["head", "model"] = "head"       # AE4d (lipsync): the S2V talking head drives the mouth, or the lip-sync model redraws it
    scope: Literal["layer", "below"] = "layer"     # AE4e: this layer's frames, or the stack from this layer down (a processing layer)


class SourceBody(BaseModel):
    take: str | None = None                        # the take the layer shows; None: its original frames


class FinalAndComposition(BaseModel):
    final: Final
    composition: Composition | None = None


class FinalLine(BaseModel):
    """D118 (AE4b): a voiced line of the shot's Dialogue nodes, with the final's layer its speaker's character performs (None: none)."""
    node_id: str
    index: int
    speaker: str | None = None
    speaker_name: str | None = None
    text: str = ""
    audio_asset_id: str
    duration_s: float | None = None
    layer_id: str | None = None


class FinalLines(BaseModel):
    items: list[FinalLine]


class AudioBody(BaseModel):
    asset_id: str                                  # the line's audio asset
    layer_id: str | None = None                    # the final's layer the line belongs to
    node_id: str | None = None
    index: int | None = None
    t: float = 0.0                                 # where the line starts in the shot (seconds)


class JobQueued(BaseModel):
    job_id: str


@router.post("/finals/{fid}/layers/{lid}/matte", response_model=JobQueued)
async def final_layer_matte(svc: Svc, fid: str, lid: str, body: MatteBody):
    """PS5d: matte a performed character layer again (SAM 3 by text on its frames) — it runs by itself after the layer's last batch."""
    from ..finals import FINAL_LAYER_SURFACE
    from ..origin import JobOrigin
    ws, _, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f else None
    if f is None or layer is None:
        raise HTTPException(404, "final or layer not found")
    if layer.kind != "figure" or layer.frames_done != f.frames:
        raise HTTPException(422, "a performed character layer is matted")
    try:
        from ..recipes import matte_mode
        jobs = svc.queue.submit({"kind": "matte_sequence", "final_id": fid, "layer_id": lid, "text": body.text, "mode": matte_mode(svc.app.settings.variant)},
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid, payload={"layer": lid, "matte": True}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.add_job, fid, lid, jobs[0].id, status="running", error=None)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id}


@router.post("/finals/{fid}/layers/{lid}/pass", response_model=JobQueued)
async def final_layer_pass(svc: Svc, fid: str, lid: str, body: PassBody):
    """D118 (AE4a): a pass on the layer's frames — Clean up (Wan 2.2's low-noise expert at a low strength) or Creative (LTX-2.3 locked to
    the layer's depth) — as a GPU job; its result becomes a take the layer shows. A character layer or the plate (a prop's RGBA comes later).
    AE4c: Face and Lip-sync on a character layer with keypoints and a matte — a chain of jobs (the talking head per line window for
    Lip-sync, then Wan Animate on the head crop in batches), the last of which pastes the heads back and records the take."""
    from ..finals import FINAL_LAYER_SURFACE
    from ..models import registry
    from ..origin import JobOrigin
    ws, _, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f else None
    if f is None or layer is None:
        raise HTTPException(404, "final or layer not found")
    if body.scope == "below":                                         # AE4e: the stack from this layer down — any layer the composition has
        if body.preset in ("face", "lipsync"):
            raise HTTPException(422, "the face pass runs on a character layer, not over the stack below")
        c0 = await asyncio.to_thread(CompositionStore(ws).get, f)
        if c0 is None or not any(cl.id == lid and cl.kind != "processing" for cl in c0.layers):
            raise HTTPException(422, "make the composition first (Open in Final): the pass over the stack below renders it")
    elif layer.kind not in ("figure", "plate"):
        raise HTTPException(422, "a pass runs on a character layer or the plate for now")
    elif layer.frames_done != f.frames:
        raise HTTPException(422, f"{layer.name} has no frames yet — make the layer first")
    variant = svc.app.settings.variant
    seed = layer.seed if body.seed is None else body.seed
    recipe: dict[str, Any] = {"kind": "layer_pass", "final_id": fid, "layer_id": lid, "preset": body.preset, "strength": body.strength, "seeds": [seed], "scope": body.scope}
    payload: dict[str, Any] = {"layer": lid, "pass": body.preset, "strength": body.strength, "scope": body.scope}
    if body.preset in ("face", "lipsync"):                                # AE4c (E29b): the head as its own layer, in steps
        from ..fsio import new_id
        if layer.kind != "figure":
            raise HTTPException(422, "the face pass renders a character's head: run it on a character layer")
        if not layer.keypoints:
            raise HTTPException(422, f"{layer.name} has no keypoints — the face pass tracks the head from the Stage's")
        if len(list(store.pass_dir(fid, lid, "matte").glob("*.png"))) != f.frames:
            raise HTTPException(422, f"{layer.name} has no matte yet — matte it first")
        animate = next((s for s in registry.animate_specs() if registry.offered(s, variant)), None)
        if animate is None:
            raise HTTPException(422, "no pose-driven model in this build")
        model_id, stage = animate.id, "head"
        if body.preset == "lipsync":
            cs = CompositionStore(ws)
            c = await asyncio.to_thread(cs.get, f)
            lines = [t for t in (await asyncio.to_thread(cs.audio_timing, f, c) if c else []) if t.get("final_layer") == lid]
            if not lines:
                raise HTTPException(422, f"attach a line to {layer.name} first (Layers › Attach a line…) — Lip-sync follows the lines on the layer")
            if body.mouth == "model":                                     # AE4d: the lip-sync model on the rendered heads — no talking head first
                from ..lipsync import lipsync_available
                why = lipsync_available(svc.app.settings)
                if why:
                    raise HTTPException(422, why)
            else:
                s2v = next((s for s in registry.lipsync_specs() if registry.offered(s, variant)), None)
                if s2v is None:
                    raise HTTPException(422, "no lip-sync model in this build")
                model_id, stage = s2v.id, "face_video"
        await asyncio.to_thread(store.sweep_unfinished, fid, lid)
        take_id = new_id("take")
        recipe |= {"model_id": model_id, "step": {"take_id": take_id, "stage": stage, "k": 0}, "mouth": body.mouth if body.preset == "lipsync" else "head"}
        payload["take"], payload["mouth"] = take_id, body.mouth
    else:
        graph = "wan22" if body.preset == "cleanup" else "ltx23"
        spec = next((s for s in registry.video_specs() if s.graph == graph and registry.offered(s, variant) and (graph != "ltx23" or s.recipes.guide_lora)), None)
        if spec is None:
            raise HTTPException(422, f"the {body.preset} pass's model is not in this build")
        recipe["model_id"] = spec.id
    try:
        jobs = svc.queue.submit(recipe, origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid, payload=payload))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.add_job, fid, lid, jobs[0].id)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id}


@router.delete("/finals/{fid}/processing/{pid}", response_model=FinalAndComposition)
async def final_processing_remove(svc: Svc, fid: str, pid: str):
    """D118 (AE4e): a processing layer dropped from the final (its frames too); the composition takes its layer out."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    try:
        f = await asyncio.to_thread(store.remove_processing, fid, pid)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    cs = CompositionStore(ws)
    c = await asyncio.to_thread(cs.get, f)
    if c is not None:
        try:
            c = await asyncio.to_thread(cs.sync_sources, f, svc.effectcraft)
        except EffectCraftError as e:
            raise _ec_error(e)
        except (KeyError, ValueError) as e:
            raise HTTPException(422, str(e))
    return {"final": f.model_dump(), "composition": c.model_dump() if c else None}


@router.post("/finals/{fid}/layers/{lid}/source", response_model=FinalAndComposition)
async def final_layer_source(svc: Svc, fid: str, lid: str, body: SourceBody):
    """D118: the take the layer shows (None: its original frames); the composition, when there is one, swaps the layer's footage."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    try:
        f = await asyncio.to_thread(store.set_source, fid, lid, body.take)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    cs = CompositionStore(ws)
    c = await asyncio.to_thread(cs.get, f)
    if c is not None and any(x.id == lid for x in c.layers):
        try:
            c = await asyncio.to_thread(cs.set_source, f, svc.effectcraft, lid, body.take)
        except EffectCraftError as e:
            raise _ec_error(e)
        except (KeyError, ValueError) as e:
            raise HTTPException(422, str(e))
    return {"final": f.model_dump(), "composition": c.model_dump() if c else None}


@router.delete("/finals/{fid}/layers/{lid}/takes/{take}", response_model=FinalAndComposition)
async def final_layer_take_delete(svc: Svc, fid: str, lid: str, take: str):
    """D118: a take dropped; the layer falls back to its original frames when it showed this one (the composition follows)."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    before = await asyncio.to_thread(store.get, fid)
    was = next((x.source for x in before.layers if x.id == lid), None) if before else None
    try:
        f = await asyncio.to_thread(store.remove_take, fid, lid, take)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    cs = CompositionStore(ws)
    c = await asyncio.to_thread(cs.get, f)
    if c is not None and was == take and any(x.id == lid for x in c.layers):
        try:
            c = await asyncio.to_thread(cs.set_source, f, svc.effectcraft, lid, None)
        except EffectCraftError as e:
            raise _ec_error(e)
    return {"final": f.model_dump(), "composition": c.model_dump() if c else None}


@router.post("/finals/{fid}/assemble", response_model=JobQueued)
async def final_assemble(svc: Svc, fid: str):
    """PS5e: composite the final's layers into the shot (a CPU job): the plate under Stage's shadows, the props and the characters in
    depth order, each character on her shadow (D107); a clip, and a take on the Story shot it was made for."""
    from ..final_assembly import check_ready
    from ..origin import JobOrigin
    ws, _, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    missing = await asyncio.to_thread(check_ready, store, f)
    if missing:
        raise HTTPException(422, "not ready: " + "; ".join(missing))
    try:
        jobs = svc.queue.submit({"kind": "assemble_final", "final_id": fid}, origin=JobOrigin(suite="stage", surface="final_assemble", ref=fid))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    return {"job_id": jobs[0].id}


@router.delete("/finals/{fid}", response_model=Deleted)
async def final_delete(svc: Svc, fid: str):
    """V43: the final's live jobs are cancelled (its layers' and every job made for it) and the EffectCraft session lets go of its
    composition before the folder goes."""
    ws, _, _ = svc.require_project()
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    if svc.queue is not None:
        mine = {j for x in f.layers for j in x.job_ids} | {j.id for j in svc.queue.jobs.values() if j.origin is not None and j.origin.ref == fid}
        for jid in sorted(mine):
            if svc.queue.job_live(jid):
                await svc.queue.cancel(jid)
    await asyncio.to_thread(svc.effectcraft.release, CompositionStore(ws).ecproj(fid))
    if not await asyncio.to_thread(store.delete, fid):
        raise HTTPException(404, "final not found")
    svc.hub.broadcast("final.updated", {"id": fid, "revision": -1})
    return {"deleted": fid}


# ---- AE1 (proto01_animate 20 §2, D114): the composition — the editable shot, an EffectCraft project beside the final ----------------
class CompositionCommand(BaseModel):
    id: str                                        # an EffectCraft engine command (layer.setBlendMode, layer.addMask, edit.undo …)
    params: dict[str, Any] = Field(default_factory=dict)


class CompositionProperty(BaseModel):
    layer: str | int                               # EffectCraft's layer id or name
    path: str                                      # transform/position, transform/opacity, effects/#1/blurriness …
    value: Any
    time: float | None = None                      # with a time: a keyframe there


class CompositionResult(BaseModel):
    result: Any
    composition: Composition


class MaskFromContent(BaseModel):
    """D116: a mask traced from the layer's visible content at `t`; with `follow`, keyed on every frame of the shot."""
    t: float = 0.0
    follow: bool = True
    tolerance: float = Field(1.5, ge=0.1, le=64.0)     # pixels: no point of the outline is farther than this from the polygon
    max_points: int = Field(160, ge=8, le=1000)


def _ec_error(e: EffectCraftError) -> HTTPException:
    return HTTPException(503 if "not built" in str(e) else 422, str(e))


async def _final_for_composition(svc, fid: str) -> tuple[CompositionStore, Final]:
    ws, _, _ = svc.require_project()
    f = await asyncio.to_thread(FinalStore(ws).get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    return CompositionStore(ws), f


@router.post("/finals/{fid}/composition", response_model=Composition)
async def composition_make(svc: Svc, fid: str):
    """The final's composition written from its layers and the assembly's result through the EffectCraft session — made, or made again
    from the layers (the edits dropped)."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        return (await asyncio.to_thread(cs.make, f, svc.effectcraft)).model_dump()
    except ValueError as e:
        raise HTTPException(409, str(e))
    except EffectCraftError as e:
        raise _ec_error(e)


@router.get("/finals/{fid}/composition", response_model=Composition)
async def composition_get(svc: Svc, fid: str):
    cs, f = await _final_for_composition(svc, fid)
    c = await asyncio.to_thread(cs.get, f)
    if c is None:
        raise HTTPException(404, "the final has no composition yet")
    return c.model_dump()


@router.post("/finals/{fid}/composition/command", response_model=CompositionResult)
async def composition_command(svc: Svc, fid: str, body: CompositionCommand):
    """One engine command on the composition, saved; the engine's refusal comes back as 422 with its message."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        result, c = await asyncio.to_thread(cs.command, f, svc.effectcraft, body.id, body.params)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
    return {"result": result, "composition": c.model_dump()}


@router.post("/finals/{fid}/composition/property", response_model=CompositionResult)
async def composition_property(svc: Svc, fid: str, body: CompositionProperty):
    """A layer's property set (or keyed at `time`), saved."""
    cs, f = await _final_for_composition(svc, fid)
    args: dict[str, Any] = {"layer": body.layer, "path": body.path, "value": body.value}
    if body.time is not None:
        args["time"] = body.time
    try:
        result, c = await asyncio.to_thread(cs.set_property, f, svc.effectcraft, args)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
    return {"result": result, "composition": c.model_dump()}


@router.get("/finals/{fid}/composition/frame")
async def composition_frame(svc: Svc, fid: str, t: float = 0.0, side: int = 0, before: bool = False):
    """A frame of the composition at `t` seconds as PNG, its longest side `side` (0: full size) — the viewer's preview (AP1 thin);
    `before` (AE3): the same frame with every effect off, nothing saved."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        png = await asyncio.to_thread(cs.frame, f, svc.effectcraft, t, max(0, side), before)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.put("/finals/{fid}/render", response_model=Final)
async def final_render_settings(svc: Svc, fid: str, body: RenderSettings):
    """AE5: the finished shot's render settings and output modules (the next render uses them; the final's revision stays)."""
    ws, _, _ = svc.require_project()
    try:
        f = await asyncio.to_thread(FinalStore(ws).set_render, fid, body)
    except KeyError:
        raise HTTPException(404, "final not found")
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


@router.post("/finals/{fid}/composition/render", response_model=JobQueued)
async def composition_render(svc: Svc, fid: str):
    """The finished shot: the composition rendered by `effectcraft-cli render` as a CPU job — a clip that becomes the final's clip and a
    take on its Story shot."""
    from ..origin import JobOrigin
    cs, f = await _final_for_composition(svc, fid)
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    if await asyncio.to_thread(cs.get, f) is None:
        raise HTTPException(404, "the final has no composition yet")
    try:
        jobs = svc.queue.submit({"kind": "comp_render", "final_id": fid, "settings": f.render.model_dump()}, origin=JobOrigin(suite="stage", surface="comp_render", ref=fid))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    return {"job_id": jobs[0].id}


# ---- AE2 (proto01_animate 20 §2): the editor reads the composition's structure; several commands as one edit -----------------------
class CompositionBatch(BaseModel):
    steps: list[CompositionCommand]


class CompositionLayers(BaseModel):
    items: list[dict[str, Any]]


def _lid(lid: str) -> str | int:
    return int(lid) if lid.isdigit() else lid


@router.post("/finals/{fid}/composition/batch", response_model=CompositionResult)
async def composition_batch(svc: Svc, fid: str, body: CompositionBatch):
    """Several engine commands as one edit (one save, one revision; the first refusal stops it, 422 with the engine's message)."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        result, c = await asyncio.to_thread(cs.batch, f, svc.effectcraft, [s.model_dump() for s in body.steps])
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
    return {"result": result, "composition": c.model_dump()}


@router.get("/finals/{fid}/composition/layers", response_model=CompositionLayers)
async def composition_layers(svc: Svc, fid: str):
    """The composition's layers, top to bottom, as the engine reports them."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        return {"items": await asyncio.to_thread(cs.layers, f, svc.effectcraft)}
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)


@router.get("/finals/{fid}/composition/layers/{lid}", response_model=dict[str, Any])
async def composition_layer(svc: Svc, fid: str, lid: str, tree: bool = False):
    """One layer (its id or name): the header and the flat property list (path, type, value, keys) — or, with `tree`, the property tree
    (groups with their uids: the masks with their mode and inverted, AE2c)."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        return await asyncio.to_thread(cs.layer, f, svc.effectcraft, _lid(lid), not tree)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)


@router.get("/finals/{fid}/composition/layers/{lid}/property", response_model=dict[str, Any])
async def composition_property_get(svc: Svc, fid: str, lid: str, path: str, t: float | None = None):
    """One property of a layer: its value at `t`, whether it is animated, its keyframes."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        return await asyncio.to_thread(cs.prop, f, svc.effectcraft, _lid(lid), path, t)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)


@router.post("/finals/{fid}/composition/layers/{lid}/mask_from_content", response_model=CompositionResult)
async def composition_mask_from_content(svc: Svc, fid: str, lid: str, body: MaskFromContent):
    """D116: a new mask on the layer traced from what is visible on it — a character's matte, a prop's alpha, the shadows — at the frame
    under `t`; with `follow` (the default) the path is keyed on every frame of the shot so the mask follows. The result says the mask's
    uid, its points and the frames keyed. 422 when the layer has nothing to trace (the plate; an empty frame)."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        result, c = await asyncio.to_thread(cs.mask_from_content, f, svc.effectcraft, _lid(lid), body.t, body.follow, body.tolerance, body.max_points)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except EffectCraftError as e:
        raise _ec_error(e)
    return {"result": result, "composition": c.model_dump()}


@router.get("/finals/{fid}/lines", response_model=FinalLines)
async def final_lines(svc: Svc, fid: str):
    """D118 (AE4b): the voiced lines of the Dialogue nodes bound to the final's Story shot, each with the layer its speaker performs. D125
    (A1): a final made without one reads the shots whose current version points at its stage and camera (where its takes go)."""
    from ..story import StoryStore, has_lines
    ws, cat, _ = svc.require_project()
    f = await asyncio.to_thread(FinalStore(ws).get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    store = StoryStore(ws)
    if f.shot_id:
        shots = {f.shot_id}
    else:
        shots = {s.id for s in await asyncio.to_thread(store.shots) if s.version().stage_id == f.stage_id and s.version().camera_id == f.camera_id}
    if not shots:
        return {"items": []}
    nodes = await asyncio.to_thread(store.flow_nodes)
    items = []
    for n in sorted(nodes.values(), key=lambda x: x.id):
        if not has_lines(n) or n.shot_id not in shots:                 # U2 (G5): a Shot with lines
            continue
        for i, ln in enumerate(n.lines):
            if not ln.audio_asset_id:
                continue
            a = await asyncio.to_thread(cat.get, ln.audio_asset_id)
            p = await asyncio.to_thread(store.profile, ln.speaker) if ln.speaker else None
            layer = next((x.id for x in f.layers if x.kind == "figure" and ln.speaker and x.profile_id == ln.speaker), None)
            items.append({"node_id": n.id, "index": i, "speaker": ln.speaker, "speaker_name": p.name if p else None, "text": ln.text, "audio_asset_id": ln.audio_asset_id,
                          "duration_s": a.duration_s if a else None, "layer_id": layer})
    return {"items": items}


@router.post("/finals/{fid}/composition/audio", response_model=Composition)
async def composition_audio_add(svc: Svc, fid: str, body: AudioBody):
    """D118 (AE4b): a line attached as an audio layer of the composition at `t`, bound to the character's layer."""
    from ..story import StoryStore
    cs, f = await _final_for_composition(svc, fid)
    _, cat, _ = svc.require_project()
    a = await asyncio.to_thread(cat.get, body.asset_id)
    if a is None or a.kind != "audio":
        raise HTTPException(422, "the asset is not an audio asset")
    if body.layer_id is not None and not any(x.id == body.layer_id for x in f.layers):
        raise HTTPException(404, f"the final has no layer {body.layer_id}")
    text, speaker, speaker_name = "", None, None
    if body.node_id is not None:
        n = await asyncio.to_thread(StoryStore(svc.ws).flow_node, body.node_id)
        if n is not None and body.index is not None and 0 <= body.index < len(n.lines):
            text, speaker = n.lines[body.index].text, n.lines[body.index].speaker
            p = await asyncio.to_thread(StoryStore(svc.ws).profile, speaker) if speaker else None
            speaker_name = p.name if p else None
    who = speaker_name or next((x.name for x in f.layers if x.id == body.layer_id), None) or "line"
    name = f"{who} · {(text or a.prompt_text or 'line')[:28]}"
    meta = {"final_layer": body.layer_id, "asset_id": body.asset_id, "node_id": body.node_id, "index": body.index, "speaker": speaker, "text": text, "duration_s": a.duration_s}
    try:
        c = await asyncio.to_thread(cs.add_audio, f, svc.effectcraft, cat.abs_path(a), meta, body.t, name)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except EffectCraftError as e:
        raise _ec_error(e)
    return c.model_dump()


@router.delete("/finals/{fid}/composition/audio/{layer}", response_model=Composition)
async def composition_audio_remove(svc: Svc, fid: str, layer: int):
    """D118 (AE4b): the audio layer taken out of the composition."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        c = await asyncio.to_thread(cs.remove_audio, f, svc.effectcraft, layer)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
    return c.model_dump()


@router.post("/finals/{fid}/composition/sync", response_model=Composition)
async def composition_sync(svc: Svc, fid: str):
    """D118: every layer whose source moved on the final (a pass landed) swapped in the composition — the Final level calls it when a
    pass's job lands."""
    cs, f = await _final_for_composition(svc, fid)
    if await asyncio.to_thread(cs.get, f) is None:
        raise HTTPException(404, "the final has no composition yet")
    try:
        c = await asyncio.to_thread(cs.sync_sources, f, svc.effectcraft)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except EffectCraftError as e:
        raise _ec_error(e)
    return c.model_dump()


@router.get("/finals/{fid}/composition/effects", response_model=CompositionLayers)
async def composition_effects(svc: Svc, fid: str, names: str = ""):
    """AE3: the engine's definitions of the effects named (comma-separated): id, category, GPU, the parameters with their types, defaults,
    ranges and options — the Effects section's tiles and dials come from here (T8)."""
    cs, f = await _final_for_composition(svc, fid)
    try:
        return {"items": await asyncio.to_thread(cs.effect_defs, f, svc.effectcraft, names.split(","))}
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except EffectCraftError as e:
        raise _ec_error(e)
