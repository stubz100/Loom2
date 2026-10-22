"""D111 (PS5): the final shot — make one from a finished Stage scene (its layers' passes uploaded as blobs), list, read, a pass frame, delete."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from typing import Literal

from pydantic import BaseModel, Field

from ..compositions import Composition, CompositionStore
from ..effectcraft import EffectCraftError
from ..finals import LAYER_PASSES, Final, FinalLayer, FinalStore
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
    """PS5a: a final from the scene's layers — the record and each layer's passes (Stage's renders at the shot's rate) on disk."""
    from ..finals import DEFAULT_METHOD
    ws, _, _ = svc.require_project()
    st = await asyncio.to_thread(StageStore(ws).get, body.stage_id)
    if st is None:
        raise HTTPException(404, "stage not found")
    if body.camera_id not in [c.id for c in st.cameras]:
        raise HTTPException(422, f"camera {body.camera_id} is not in the stage")
    for x in body.layers:
        if x.kind not in LAYER_PASSES:
            raise HTTPException(422, f"layer {x.id}: a layer is a plate, a figure, a prop or the shadows")
    passes = {x.id: {name: [_blob(ws, sha) for sha in shas] for name, shas in x.passes.items()} for x in body.layers}
    keypoints = {x.id: x.keypoints for x in body.layers if x.keypoints is not None}
    data = body.model_dump(exclude={"layers"}) | {"layers": [FinalLayer(id=x.id, kind=x.kind, name=x.name, object_id=x.object_id, method=x.method or DEFAULT_METHOD[x.kind],  # type: ignore[arg-type]
                                                                        profile_id=x.profile_id, version=x.version).model_dump() for x in body.layers]}
    try:
        f = await asyncio.to_thread(FinalStore(ws).create, data, passes, keypoints)
    except ValueError as e:
        raise HTTPException(422, str(e))
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


@router.post("/finals/{fid}/plate", response_model=PlateQueued)
async def final_plate(svc: Svc, fid: str, body: PlateBody):
    """PS5b: the plate's still — the bare set's lit clay at frame 0 (from the final's plate pass) as a Stage shot's image 1 (Klein, the clay
    method), the lead first so the model draws no people or objects (they are layers). Stage then projects it along the camera path."""
    from ..finals import FINAL_PLATE_SURFACE, PLATE_LEAD
    from ..origin import JobOrigin
    ws, cat, _ = svc.require_project()
    if svc.queue is None:
        raise HTTPException(409, "no queue")
    store = FinalStore(ws)
    f = await asyncio.to_thread(store.get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
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
    recipe = {"kind": "stage_shot", "stage_id": f.stage_id, "camera_id": f.camera_id, "passes": {"clay": rec.id}, "method": "clay", "empty": True,
              "prompt_text": f"{PLATE_LEAD} {body.prompt_text.strip()}".strip(), "refs": body.refs, "seeds": [body.seed], "width": w, "height": h}
    try:
        jobs = svc.queue.submit(recipe, origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=fid))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.update_layer, fid, "plate", status="queued", error=None, job_ids=[*next(x for x in f.layers if x.id == "plate").job_ids, jobs[0].id])
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id, "pass_asset_id": rec.id}


class FramesBody(BaseModel):
    frames: list[str]                              # the layer's own frames' blob ids (sha256), one per frame of the final


@router.put("/finals/{fid}/layers/{lid}/frames", response_model=Final)
async def final_layer_frames(svc: Svc, fid: str, lid: str, body: FramesBody):
    """A layer's own sequence made by the client (PS5b: the projected plate) — stored as its `frames/`; the layer is done."""
    ws, _, _ = svc.require_project()
    files = [_blob(ws, sha) for sha in body.frames]
    try:
        f = await asyncio.to_thread(FinalStore(ws).set_frames, fid, lid, files)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return f.model_dump()


class RunBody(BaseModel):
    seed: int | None = None                        # None: the layer's seed (the first run 0; a re-take passes another)


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
    from ..stages import encode_guide
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
    pose = sorted(store.pass_dir(fid, lid, "pose").glob("*.png"))
    guide_mp4 = folder / "pose.mp4"
    await asyncio.to_thread(encode_guide, pose, guide_mp4, f.rate)
    g = await asyncio.to_thread(cat.ingest_file, guide_mp4, kind="video", move=False, suite="stage", lineage_kind="stage-pass",
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid), params={"final_id": fid, "layer": lid, "pass": "pose-sequence"},
                                frames=len(pose), fps=float(f.rate), w=w, h=h)
    g = await asyncio.to_thread(cat.make_thumbs, g, pose[0])
    seed = layer.seed if body.seed is None else body.seed
    layer.reference_asset_id, layer.guide_asset_id, layer.seed = ref_id, g.id, seed
    plan = plan_batches(f.frames)
    prompt = f"{p.name}, {compose_sheet(v, name=p.name)}, {CHARACTER_TAIL}"
    try:
        jobs = svc.queue.submit(character_recipe(f, layer, spec.id, prompt, plan[0], None),
                                origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=fid, payload={"layer": lid, "batch": 0, "batches": len(plan), "prompt": prompt}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    await svc.queue.flush()
    f = await asyncio.to_thread(store.update_layer, fid, lid, status="queued", error=None, seed=seed, reference_asset_id=ref_id, guide_asset_id=g.id,
                                batches=[{"k": 0, "job_id": jobs[0].id, "clip_id": None}], job_ids=[*layer.job_ids, jobs[0].id], frames_done=0)
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id, "batches": len(plan), "reference_asset_id": ref_id, "placed": placed}


class MatteBody(BaseModel):
    text: str = "person"                           # what SAM 3 looks for in the layer's frames


class PassBody(BaseModel):
    """D118 (AE4a): a pass on the layer — the preset and its strength; a seed given is a re-run with another. AE4c: `face` and `lipsync`
    (the strength unused)."""
    preset: Literal["cleanup", "creative", "face", "lipsync"] = "cleanup"
    strength: float = Field(0.10, ge=0.02, le=0.9)
    seed: int | None = None
    mouth: Literal["head", "model"] = "head"       # AE4d (lipsync): the S2V talking head drives the mouth, or the lip-sync model redraws it


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
    f = await asyncio.to_thread(store.update_layer, fid, lid, status="running", error=None, job_ids=[*layer.job_ids, jobs[0].id])
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
    if layer.kind not in ("figure", "plate"):
        raise HTTPException(422, "a pass runs on a character layer or the plate for now")
    if layer.frames_done != f.frames:
        raise HTTPException(422, f"{layer.name} has no frames yet — make the layer first")
    variant = svc.app.settings.variant
    seed = layer.seed if body.seed is None else body.seed
    recipe: dict[str, Any] = {"kind": "layer_pass", "final_id": fid, "layer_id": lid, "preset": body.preset, "strength": body.strength, "seeds": [seed]}
    payload: dict[str, Any] = {"layer": lid, "pass": body.preset, "strength": body.strength}
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
    f = await asyncio.to_thread(store.update_layer, fid, lid, job_ids=[*layer.job_ids, jobs[0].id])
    svc.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    return {"job_id": jobs[0].id}


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
    ws, _, _ = svc.require_project()
    if not await asyncio.to_thread(FinalStore(ws).delete, fid):
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
        jobs = svc.queue.submit({"kind": "comp_render", "final_id": fid}, origin=JobOrigin(suite="stage", surface="comp_render", ref=fid))
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
    """D118 (AE4b): the voiced lines of the Dialogue nodes bound to the final's Story shot, each with the layer its speaker performs."""
    from ..story import StoryStore
    ws, cat, _ = svc.require_project()
    f = await asyncio.to_thread(FinalStore(ws).get, fid)
    if f is None:
        raise HTTPException(404, "final not found")
    if not f.shot_id:
        return {"items": []}
    store = StoryStore(ws)
    nodes = await asyncio.to_thread(store.flow_nodes)
    items = []
    for n in sorted(nodes.values(), key=lambda x: x.id):
        if n.type != "dialogue" or n.shot_id != f.shot_id:
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
