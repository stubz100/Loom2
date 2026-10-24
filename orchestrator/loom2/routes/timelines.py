"""Sequences (P17 / D83): the single-lane timeline documents — list, create, read, replace (409 on a stale revision), delete, and the
EDL / FCPXML exports written from the document for Resolve (14 R151 / R152). CE1 (D126 #2): with FilmCraft built, a cut is a FilmCraft
project written through the session (`_store`). CE2 (proto01_animate 30 §12): a FilmCraft cut's tracks, the editor's edits as FilmCraft
commands, placing a Catalogue clip, picture or sound, *Update* in place and the viewer's frames."""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..clips import ClipStore
from ..origin import JobOrigin
from ..schemas import Deleted, JobsSubmitted, TimelineExported, TimelineList
from ..cuts import CutTracks
from ..timelines import StaleTimeline, Timeline, TimelineStore
from .deps import Svc

router = APIRouter(tags=["timelines"])


class TimelineCreate(BaseModel):
    name: str = "Sequence"
    fps: int | None = None                        # default: the project format's (D18: 24)
    w: int | None = None
    h: int | None = None


class TimelineExport(BaseModel):
    format: Literal["edl", "fcpxml", "srt", "resolve"]   # 17 §3e (D85): .srt from the lane clips' Dialogue lines, markers with the FCPXML; D125 (S14): resolve = all three and markers.txt in one folder


def _store(svc, ws, cat=None) -> TimelineStore:
    """The cuts' store with the FilmCraft session's writer (CE1): changes go into a cut's project when FilmCraft is built."""
    from ..cuts import Cuts
    name_of, _, audio_of = _story_lookup(ws, cat)
    return TimelineStore(ws, Cuts(ws, svc.filmcraft, audio_of, name_of))


@router.get("/timelines", response_model=TimelineList)
async def timelines_list(svc: Svc):
    ws, _, _ = svc.require_project()
    return {"items": [t.model_dump(by_alias=True) for t in await asyncio.to_thread(TimelineStore(ws).list)]}


@router.post("/timelines", response_model=Timeline, response_model_by_alias=True)
async def timeline_create(svc: Svc, body: TimelineCreate):
    ws, cat, _ = svc.require_project()
    fmt = ws.load().format
    try:
        tl = await asyncio.to_thread(_store(svc, ws, cat).create, body.name, body.fps or fmt.fps, body.w or fmt.width, body.h or fmt.height)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    svc.hub.broadcast("timeline.updated", {"id": tl.id, "revision": tl.revision})
    return tl.model_dump(by_alias=True)


@router.get("/timelines/{tl_id}", response_model=Timeline, response_model_by_alias=True)
async def timeline_get(svc: Svc, tl_id: str):
    ws, _, _ = svc.require_project()
    tl = await asyncio.to_thread(TimelineStore(ws).get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    return tl.model_dump(by_alias=True)


@router.put("/timelines/{tl_id}", response_model=Timeline, response_model_by_alias=True)
async def timeline_put(svc: Svc, tl_id: str, body: dict):
    """Replace the document from a body based on its `revision`; every clip must be in the project and its `out` within the clip's frames."""
    ws, cat, _ = svc.require_project()
    store, clips = _store(svc, ws, cat), ClipStore(ws)
    recs = {c.id: c for c in await asyncio.to_thread(clips.list)}
    try:
        tl = await asyncio.to_thread(store.put, tl_id, body, {k: c.frames for k, c in recs.items()}, recs)
    except KeyError:
        raise HTTPException(404, "sequence not found")
    except StaleTimeline as e:
        raise HTTPException(409, str(e))
    except (ValueError, RuntimeError) as e:                       # CE1: FilmCraft's refusal (FilmCraftError) or a cut it cannot change
        raise HTTPException(422, str(e))
    svc.hub.broadcast("timeline.updated", {"id": tl.id, "revision": tl.revision})
    return tl.model_dump(by_alias=True)


@router.delete("/timelines/{tl_id}", response_model=Deleted)
async def timeline_delete(svc: Svc, tl_id: str):
    ws, cat, _ = svc.require_project()
    if not await asyncio.to_thread(_store(svc, ws, cat).delete, tl_id):
        raise HTTPException(404, "sequence not found")
    svc.hub.broadcast("timeline.deleted", {"id": tl_id})
    return {"deleted": tl_id}


class TimelineRender(BaseModel):
    movie: bool = False                            # RC3 (proto01_animate 29): the movie (conformed, the cut's size, the voice lane, an MP4) instead of the draft


@router.post("/timelines/{tl_id}/render", response_model=JobsSubmitted)
async def timeline_render(svc: Svc, tl_id: str, body: TimelineRender | None = None):
    """P17: the draft render as a CPU job (no engine) — the result is a Catalogue clip with lineage to every clip on the lane. RC3: `movie`
    renders the finished movie instead — an MP4 with the voice lane in the cut's folder and a Catalogue video."""
    ws, _, queue = svc.require_project()
    store, clips = TimelineStore(ws), ClipStore(ws)
    tl = await asyncio.to_thread(store.get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    if not tl.clips:
        raise HTTPException(422, "the sequence is empty")
    recs = {c.id for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise HTTPException(422, f"clips missing from the project: {', '.join(missing)}")
    try:
        jobs = queue.submit({"kind": "render", "timeline_id": tl_id, "movie": bool(body and body.movie)}, origin=JobOrigin(suite="animate", surface="sequence", ref=tl_id))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/timelines/{tl_id}/export", response_model=TimelineExported)
async def timeline_export(svc: Svc, tl_id: str, body: TimelineExport):
    ws, cat, _ = svc.require_project()
    store, clips = _store(svc, ws, cat), ClipStore(ws)                 # CE2: a FilmCraft cut exports through FilmCraft
    tl = await asyncio.to_thread(store.get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    recs = {c.id: c for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise HTTPException(422, f"clips missing from the project: {', '.join(missing)}")
    try:
        names, lines, audio = await asyncio.to_thread(_story_lookup, ws, cat)
        path, text = await asyncio.to_thread(store.export, tl, body.format, recs, names, lines, audio)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if tl.file:                                                     # CE2: a FilmCraft cut's spoken lines are A1's clips
        from ..cuts import lines as cut_lines
        from ..cuts import read
        cues = len(await asyncio.to_thread(lambda: cut_lines(read(ws.timelines_dir / tl.id / tl.file)))) if body.format in ("fcpxml", "edl", "resolve") else 0
    else:
        cues = sum(1 for c in tl.clips for cue in audio(c) if cue) if body.format in ("fcpxml", "edl", "resolve") else 0     # CN2: the audio lane's spoken lines
    return {"format": body.format, "path": path.relative_to(ws.path).as_posix(), "text": text, "audio": cues}


def _story_lookup(ws, cat=None):
    """17 §3e: see `timelines.story_lookup` (RC3: the movie render reads the same lines and voices)."""
    from ..timelines import story_lookup
    return story_lookup(ws, cat)


# ---- CE2: the editor on a FilmCraft cut ------------------------------------------------------------------------------------------
class CutStep(BaseModel):
    id: str                                        # a FilmCraft command the editor may run (cuts.EDIT_COMMANDS) or loom2.removeTransition
    params: dict[str, Any] = Field(default_factory=dict)


class CutEdit(BaseModel):
    revision: int | None = None                    # the cut's revision the edit is based on (409 when it moved)
    steps: list[CutStep]


class CutPlace(BaseModel):
    revision: int | None = None
    clip_id: str | None = None                     # a loom2 clip (a take; with the shot it stands for when it comes from the Shots bin) …
    shot_id: str | None = None
    shot_version: str | None = None
    node_id: str | None = None
    asset_id: str | None = None                    # … or a Catalogue picture, sound or video
    track: str | int = "V2"                        # "V1" … "A3", or a track's id
    frame: float = 0.0                             # where it starts, in the cut's frames
    insert: bool = False


class CutReplace(BaseModel):
    revision: int | None = None
    clip: int                                      # the track's clip (FilmCraft's id) that plays another take
    clip_id: str                                   # the take
    shot_id: str | None = None
    shot_version: str | None = None
    node_id: str | None = None


class CutEdited(BaseModel):
    timeline: Timeline
    tracks: CutTracks
    results: list[Any] = Field(default_factory=list)


def _cut_tracks(ws, tl: Timeline) -> CutTracks:
    """The cut's tracks with how many changes it can undo and redo (its project's snapshots)."""
    from ..cuts import read, tracks
    p = ws.timelines_dir / tl.id / tl.file
    n = {w: len(list((p.parent / "history" / w).glob("*.fcproj"))) for w in ("undo", "redo")}
    return tracks(read(p)).model_copy(update=n)


def _cut_edited(svc, ws, store: TimelineStore, tl_id: str, results: list[Any]) -> dict:
    tl = store.touch(tl_id)
    svc.hub.broadcast("timeline.updated", {"id": tl.id, "revision": tl.revision})
    return {"timeline": tl.model_dump(by_alias=True), "tracks": _cut_tracks(ws, tl).model_dump(by_alias=True), "results": results}


async def _cut_call(svc, tl_id: str, base: int | None, fn) -> dict:
    """Run an editor's change on a FilmCraft cut: the base revision checked first, FilmCraft's refusal answered as it is (422)."""
    from ..cuts import CutError
    ws, cat, _ = svc.require_project()
    store = _store(svc, ws, cat)
    try:
        tl = await asyncio.to_thread(store.based, tl_id, base)
        if not tl.file:
            raise CutError("this cut is not a FilmCraft project yet (it becomes one on its first change)")
        results = await asyncio.to_thread(fn, store, tl, ws, cat)
        return await asyncio.to_thread(_cut_edited, svc, ws, store, tl_id, results)
    except KeyError:
        raise HTTPException(404, "sequence not found")
    except StaleTimeline as e:
        raise HTTPException(409, str(e))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))


@router.get("/timelines/{tl_id}/tracks", response_model=CutTracks, response_model_by_alias=True)
async def timeline_tracks(svc: Svc, tl_id: str):
    """CE2: a FilmCraft cut's every track (its clips with their media and loom2's links, the transitions), read from its project."""
    ws, _, _ = svc.require_project()
    tl = await asyncio.to_thread(TimelineStore(ws).get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    if not tl.file:
        raise HTTPException(422, "this cut is not a FilmCraft project yet (it becomes one on its first change)")
    return (await asyncio.to_thread(_cut_tracks, ws, tl)).model_dump(by_alias=True)


@router.post("/timelines/{tl_id}/edit", response_model=CutEdited, response_model_by_alias=True)
async def timeline_edit(svc: Svc, tl_id: str, body: CutEdit):
    """CE2: the editor's change as FilmCraft commands (move, trim, roll, slip, slide, razor, ripple delete, speed, freeze, transitions, a
    track's name / lock / mute, tracks added, undo / redo), run in the session in order and saved."""
    return await _cut_call(svc, tl_id, body.revision, lambda store, tl, ws, cat: store.cuts.edit(tl, [s.model_dump() for s in body.steps]))


@router.post("/timelines/{tl_id}/place", response_model=CutEdited, response_model_by_alias=True)
async def timeline_place(svc: Svc, tl_id: str, body: CutPlace):
    """CE2: a loom2 clip or a Catalogue picture, sound or video on a track at a frame (imported once into the cut's project, with its link)."""
    def run(store, tl, ws, cat):
        from ..cuts import CutError
        recs = {c.id: c for c in ClipStore(ws).list()}
        clip_id = body.clip_id
        if not clip_id and body.asset_id:
            clip_id = next((c.id for c in recs.values() if c.asset_id == body.asset_id), None)   # a clip's video is the clip (its master)
        if clip_id:
            if clip_id not in recs:
                raise CutError(f"clip {clip_id} is not in the project")
            return [store.cuts.place(tl, {"clip_id": clip_id, "record": recs[clip_id], "shot_id": body.shot_id, "shot_version": body.shot_version,
                                          "node_id": body.node_id}, body.track, body.frame, body.insert)]
        a = cat.get(body.asset_id) if body.asset_id else None
        if a is None:
            raise CutError("place needs a clip or a Catalogue asset that exists")
        return [store.cuts.place(tl, {"asset_id": a.id, "path": str(ws.path / a.path), "kind": a.kind}, body.track, body.frame, body.insert)]
    return await _cut_call(svc, tl_id, body.revision, run)


@router.post("/timelines/{tl_id}/replace", response_model=CutEdited, response_model_by_alias=True)
async def timeline_replace(svc: Svc, tl_id: str, body: CutReplace):
    """CE2 (*Update*, D125 S13, on a FilmCraft cut): the track's clip plays another take in place — its start and length kept."""
    def run(store, tl, ws, cat):
        from ..cuts import CutError
        rec = ClipStore(ws).get(body.clip_id)
        if rec is None:
            raise CutError(f"clip {body.clip_id} is not in the project")
        return [store.cuts.replace(tl, body.clip, (body.clip_id, body.shot_id or "", body.shot_version or "", body.node_id or ""), rec)]
    return await _cut_call(svc, tl_id, body.revision, run)


class CutUndo(BaseModel):
    revision: int | None = None


@router.post("/timelines/{tl_id}/undo", response_model=CutEdited, response_model_by_alias=True)
async def timeline_undo(svc: Svc, tl_id: str, body: CutUndo):
    """CE2: the cut as it was before its last change (its project's snapshot; any change, Assemble included, is one step)."""
    return await _cut_call(svc, tl_id, body.revision, lambda store, tl, ws, cat: [store.cuts.undo(tl)])


@router.post("/timelines/{tl_id}/redo", response_model=CutEdited, response_model_by_alias=True)
async def timeline_redo(svc: Svc, tl_id: str, body: CutUndo):
    """CE2: the change undone last, made again."""
    return await _cut_call(svc, tl_id, body.revision, lambda store, tl, ws, cat: [store.cuts.undo(tl, redo=True)])


@router.get("/timelines/{tl_id}/frame")
async def timeline_frame(svc: Svc, tl_id: str, t: float = 0.0, side: int = 960):
    """CE2: the cut's frame at `t` seconds as PNG from FilmCraft's session, its longest side `side` — the Episode's viewer."""
    from ..cuts import CutError
    ws, cat, _ = svc.require_project()
    store = _store(svc, ws, cat)
    tl = await asyncio.to_thread(store.get, tl_id)
    if tl is None:
        raise HTTPException(404, "sequence not found")
    try:
        png = await asyncio.to_thread(store.cuts.frame, tl, max(0.0, t), max(16, min(4096, side)))
    except (CutError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
