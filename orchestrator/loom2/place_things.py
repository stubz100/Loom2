"""D180 (W60): a part of a built set that moves — the ferry painted into the pier's backdrop could not sail.

A thing is picked on the place's set picture as SC3's things are on a picture set (D123): SAM 3's point prompts on the picture's own
document, the mask kept. Kept, it is cut out (its pixels, the mask as alpha: the card) and stood where the picture shows it — the ray from
the set picture's camera through the bottom centre of its mask meets the set's floor (y = 0 in the set's frame), and its width and height
are its pixels at that distance. It is then a card, or (E56: the pier's ferry came out a recognisable boat) a 3D model made from its
cut-out by the app's image → 3D; Clay places either as an object of its own (frontend placeThings.ts), so it can be keyed. The set picture
can be cleaned under the things (a Fill) so the faces baked again show what was behind them, their Fills kept.
"""
from __future__ import annotations

import asyncio
import math
import re
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .fsio import new_id
from .origin import JobOrigin
from .stages import PlaceSet, PlaceThing, SourceCamera

FIND_SURFACE = "place_thing_find"
MODEL_SURFACE = "place_thing_model"                # payload {version, thing}
CLEAN_SURFACE = "place_things_clean"               # payload {version}
FAR_M = 40.0                                       # a thing whose bottom is above the horizon stands this far out along its ray
CLEAN_GROW = 14                                    # as SC3's (E28b): the mask grown over the thing's soft edge and its contact shadow
CLEAN_SAME = 8.0                                   # E58: a clean whose things' pixels moved less than this (mean, of 255) painted them back
THIN_STEP = 25                                     # E57: a thin part stands 25+ grey levels off its 9 px median (the ferry's mast against the fog)
THIN_REACH = 0.4                                   # E57: within this share of the thing's height of SAM 3's mask (16 px at least)


def _place_set(store: Any, pid: str, vid: str) -> tuple[Any, PlaceSet]:
    p = store.profile(pid)
    if p is None:
        raise KeyError(pid)
    v = p.version(vid)
    if v.place_set is None or not v.place_set.sources:
        raise ValueError("the place has no set yet — Build the set ▶ first")
    return p, v.place_set


def _put(store: Any, pid: str, vid: str, fn: Any) -> Any:
    """The version's set changed in place by `fn(ps)` (read again, so a Fill or a bake meanwhile stays). Review K91: read, changed and
    written under the story's lock (a Fill landing between the read and the write was lost)."""
    from .story import _LOCK
    with _LOCK:
        p, ps = _place_set(store, pid, vid)
        ps = ps.model_copy(deep=True)
        fn(ps)
        return store.set_place_set(pid, vid, ps)


def picture_of(ps: PlaceSet) -> str:
    return ps.sources[0].asset_id


def ensure_document(store: Any, documents: Any, catalogue: Any, pid: str, vid: str) -> Any:
    """The set picture's own document (made the first time; made again when it was deleted)."""
    _, ps = _place_set(store, pid, vid)
    if ps.things_document_id:
        try:
            return documents.get(ps.things_document_id)
        except Exception:  # noqa: BLE001 — closed for good or deleted: a new one from the picture
            pass
    a = catalogue.get(picture_of(ps))
    if a is None:
        raise ValueError("the set picture is not in the Catalogue")
    with Image.open(catalogue.abs_path(a)) as im:
        base = np.asarray(im.convert("RGBA"))
    od = documents.create("set picture · things", int(base.shape[1]), int(base.shape[0]), "transparent", a.id, base)
    _put(store, pid, vid, lambda x: setattr(x, "things_document_id", od.doc.id))
    return od


def ray(cam: SourceCamera, w: int, h: int, px: float, py: float) -> tuple[np.ndarray, np.ndarray, float]:
    """The ray from the set picture's camera through a picture pixel (the set's frame): its origin, its unit direction, and the metres a
    pixel spans per metre of depth along the camera's axis (the sensor is the frame's width, as Stage's cameras)."""
    o, t = np.asarray(cam.pos, float), np.asarray(cam.target, float)
    f = (t - o) / max(1e-9, float(np.linalg.norm(t - o)))
    r = np.cross(f, [0.0, 1.0, 0.0])
    r = r / max(1e-9, float(np.linalg.norm(r)))
    u = np.cross(r, f)
    roll = math.radians(float(getattr(cam, "roll", 0.0) or 0.0))          # K: the camera's roll as the engine applies it (rotateZ after the look-at)
    if roll:
        c, s_ = math.cos(roll), math.sin(roll)
        r, u = c * r + s_ * u, -s_ * r + c * u
    tan_x = (cam.sensor_mm / 2) / cam.focal_mm
    nx, ny = (px / w - 0.5) * 2, (0.5 - py / h) * 2
    d = f + r * nx * tan_x + u * ny * tan_x * (h / w)
    return o, d / float(np.linalg.norm(d)), 2 * tan_x / w


def stand(cam: SourceCamera, mask: np.ndarray) -> dict[str, Any]:
    """Where a thing stands, from its mask on the set picture: its bottom centre's ray meets the floor (y = 0), else it stands FAR_M out;
    its width and height are its pixels at that depth; it is turned to face the camera."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("the thing's mask is empty")
    bottom = ys >= np.percentile(ys, 97)
    px, py = float(np.median(xs[bottom])), float(ys.max())
    o, d, per_px = ray(cam, w, h, px, py)
    if d[1] < -1e-3 and o[1] > 0:
        dist = -o[1] / d[1]
    else:
        dist = FAR_M
    base = o + d * dist
    base[1] = 0.0
    f = np.asarray(cam.target, float) - o
    depth = float(np.dot(base - o, f / max(1e-9, float(np.linalg.norm(f)))))
    width = (int(xs.max()) - int(xs.min()) + 1) * per_px * depth
    height = (int(ys.max()) - int(ys.min()) + 1) * per_px * depth
    yaw = math.degrees(math.atan2(o[0] - base[0], o[2] - base[2]))
    return {"base": [round(float(x), 3) for x in base], "width_m": round(width, 3), "height_m": round(height, 3), "yaw_deg": round(yaw, 2)}


def _mine(pid: str, vid: str) -> JobOrigin:
    """W57: what is made for a place's things belongs to the place's version (its Bin page), not to no page."""
    return JobOrigin(suite="story", surface="place_thing", ref=pid, payload={"version": vid})


def card(catalogue: Any, picture_id: str, mask: np.ndarray, origin: JobOrigin | None = None) -> Any:
    """The thing's card: its pixels with the mask as alpha, cropped to it (lineage `place-thing` ← the picture)."""
    a = catalogue.get(picture_id)
    with Image.open(catalogue.abs_path(a)) as im:
        rgb = np.asarray(im.convert("RGB"))
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    rgba = np.dstack([rgb, np.where(mask, 255, 0).astype(np.uint8)])[y0:y1, x0:x1]
    path = catalogue.ws.temp_dir / "things" / f"{new_id('card')}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path, "PNG")
    rec = catalogue.ingest_file(path, kind="image", move=True, suite="story", parents=[picture_id], lineage_kind="place-thing", origin=origin)
    return catalogue.make_thumbs(rec)


def keep(store: Any, documents: Any, catalogue: Any, pid: str, vid: str, name: str, points: list[dict[str, int]]) -> tuple[Any, PlaceThing, list[Any]]:
    """The mask the last find left on the set picture's document, kept as a thing — what the clicks touch, with its thin parts (E57): the
    mask (a `mask` asset), its card, where it stands."""
    _, ps = _place_set(store, pid, vid)
    if not ps.things_document_id:
        raise ValueError("find the thing on the set picture first (a click on it)")
    od = documents.get(ps.things_document_id)
    sel = od.selection
    if sel is None or not (sel > 127).any():
        raise ValueError("nothing is found yet — click the thing on the set picture")
    mask = clicked(sel > 127, points)
    with Image.open(catalogue.abs_path(catalogue.get(picture_of(ps)))) as im:
        rgb = np.asarray(im.convert("RGB"))
    if rgb.shape[:2] == mask.shape:
        mask = thin_parts(rgb, mask)
    tmp = catalogue.ws.temp_dir / "things" / f"{new_id('msk')}.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").save(tmp, "PNG")
    label = name.strip() or f"Thing {len(ps.things) + 1}"
    mrec = catalogue.make_thumbs(catalogue.ingest_file(tmp, kind="mask", move=True, suite="story", parents=[picture_of(ps)], lineage_kind="place-thing",
                                                       prompt_text=label, params={"profile_id": pid, "version": vid, "thing": label, "points": points},
                                                       origin=_mine(pid, vid)))
    crec = card(catalogue, picture_of(ps), mask, _mine(pid, vid))
    t = PlaceThing(name=label, mask_asset_id=mrec.id, card_asset_id=crec.id, points=points, **stand(ps.sources[0].camera, mask))
    p = _put(store, pid, vid, lambda x: x.things.append(t))
    return p, t, [mrec, crec]


def clicked(mask: np.ndarray, points: list[dict[str, int]]) -> np.ndarray:
    """The part of SAM 3's mask the author clicked: what is connected to the points on the thing (SAM 3 leaves stray specks — the rig's
    ferry had some over the sky, and its width read 2.6× too wide); the whole mask when no point falls on it."""
    from .set_things import _reach
    seed = np.zeros_like(mask)
    h, w = mask.shape
    for p in points:
        if int(p.get("label", 1)) == 1 and 0 <= int(p["y"]) < h and 0 <= int(p["x"]) < w:
            y, x = int(p["y"]), int(p["x"])
            seed[max(0, y - 3):y + 4, max(0, x - 3):x + 4] = True
    seed &= mask
    return _reach(seed, mask) if seed.any() else mask


def thin_parts(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """What SAM 3 leaves out of a thing (E57): its thin parts — a mast, a yard, an aerial, 2–3 px at the set picture's size, which a click
    on them does not add — as the pixels standing THIN_STEP off their 9 px median that are connected to the mask, within THIN_REACH of
    the thing's height of it. Left out, the clean leaves the mast standing and the Fill paints a ferry back around it."""
    from .set_things import _grow, _reach
    grey = rgb.astype(np.float32).mean(2)
    med = np.asarray(Image.fromarray(grey.astype(np.uint8)).filter(ImageFilter.MedianFilter(9))).astype(np.float32)
    thin = np.abs(grey - med) > THIN_STEP
    ys = np.nonzero(mask)[0]
    near = _grow(mask, max(16, int(THIN_REACH * (int(ys.max()) - int(ys.min()) + 1))))
    return mask | _reach(_grow(mask, 1) & thin, (thin | mask) & near)


def thing_of(ps: PlaceSet, tid: str) -> PlaceThing:
    t = next((x for x in ps.things if x.id == tid), None)
    if t is None:
        raise KeyError(f"no thing {tid!r}")
    return t


def remove(store: Any, pid: str, vid: str, tid: str) -> Any:
    _, ps = _place_set(store, pid, vid)
    thing_of(ps, tid)
    return _put(store, pid, vid, lambda x: setattr(x, "things", [t for t in x.things if t.id != tid]))


def _mask(catalogue: Any, t: PlaceThing) -> np.ndarray:
    with Image.open(catalogue.abs_path(catalogue.get(t.mask_asset_id))) as im:
        return np.asarray(im.convert("L")) > 127


def _picked_on(catalogue: Any, ps: PlaceSet, t: PlaceThing) -> str:
    """The picture a thing was picked on (its mask's parent): the set picture as it was, the thing still in it once the picture is cleaned."""
    m = catalogue.get(t.mask_asset_id)
    return m.parents[0] if m is not None and m.parents else picture_of(ps)


def _model_source(q: Any, store: Any, catalogue: Any, pid: str, vid: str, tid: str) -> Any:
    from .set_things import cutout
    _, ps = _place_set(store, pid, vid)
    t = thing_of(ps, tid)
    if t.mesh_job_id and q.job_live(t.mesh_job_id):
        raise ValueError(f"{t.name}'s 3D model is being made")
    return catalogue.ingest_file(cutout(catalogue, _picked_on(catalogue, ps, t), _mask(catalogue, t)), kind="image", move=True, suite="story",
                                 parents=[t.card_asset_id], lineage_kind="place-thing", origin=_mine(pid, vid))


async def _staged(q: Any, store: Any, pid: str, vid: str, recipe: dict[str, Any], origin: JobOrigin, mark: Any) -> Any:
    """V21's order (place_sets.start_fill): submitted on the loop *staged*, the set marked by `mark(ps, job_id)`, then released — the job
    never lands before its marker is on disk; a set gone meanwhile cancels it."""
    job = q.submit(recipe, stage=True, origin=origin)[0]
    if job.status != "staged":
        raise ValueError(job.error or "the job was refused")
    try:
        await asyncio.to_thread(_put, store, pid, vid, lambda x: mark(x, job.id))
    except Exception:
        await q.cancel(job.id)
        raise
    q.release(job.id)
    return job


async def model_job(q: Any, store: Any, catalogue: Any, pid: str, vid: str, tid: str) -> Any:
    """The thing's 3D model queued: its cut-out on white (as SC3's, which Pixal3D's template cuts out again) by the app's image → 3D — cut
    from the picture it was picked on (a cleaned set picture no longer shows it)."""
    src = await asyncio.to_thread(_model_source, q, store, catalogue, pid, vid, tid)
    from .bins import home_now
    await asyncio.to_thread(home_now, q.groups, q.ws, src)
    return await _staged(q, store, pid, vid, {"kind": "image_to_mesh", "asset_id": src.id},
                         JobOrigin(suite="story", surface=MODEL_SURFACE, ref=pid, payload={"version": vid, "thing": tid}),
                         lambda x, jid: setattr(thing_of(x, tid), "mesh_job_id", jid))


def model_landed(q: Any, job: Any, mesh_id: str) -> Any | None:
    """A thing's model landed: its mesh on the thing (a thing removed meanwhile keeps nothing)."""
    from .story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    vid, tid = str(payload.get("version") or ""), str(payload.get("thing") or "")
    store = StoryStore(q.ws)
    try:
        _, ps = _place_set(store, pid, vid)
        thing_of(ps, tid)
    except (KeyError, ValueError):
        return None

    def put(x: PlaceSet) -> None:
        t = thing_of(x, tid)
        t.mesh_asset_id, t.mesh_job_id = mesh_id, None
    return _put(store, pid, vid, put)


def model_failed(q: Any, job: Any) -> None:
    from .story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    vid, tid = str(payload.get("version") or ""), str(payload.get("thing") or "")
    try:
        _put(StoryStore(q.ws), pid, vid, lambda x: setattr(thing_of(x, tid), "mesh_job_id", None))
    except (KeyError, ValueError):
        pass


def clean_prompt(names: list[str]) -> str:
    """E58: the clean's words are an instruction naming what goes — Klein reads a Fill's words as an edit of the picture it is shown: a
    prompt asking for "the same" place gave the ferry back untouched (three seeds of three), the clean's first prompt on one seed of
    seven; "Remove the ferry: …" took it out on all three, that seed among them."""
    def one(n: str) -> str:
        n = n.strip()
        if not n or re.fullmatch(r"Thing \d+", n):
            return "thing"
        return n if n[1:2].isupper() else n[:1].lower() + n[1:]
    words = list(dict.fromkeys(one(n) for n in names)) or ["thing"]
    if words == ["thing"] and len(names) > 1:
        words = ["things"]
    what = " and ".join(f"the {w}" for w in words) if len(words) < 3 else ", ".join(f"the {w}" for w in words[:-1]) + f" and the {words[-1]}"
    it = "it" if len(names) <= 1 and words != ["things"] else "them"
    return f"Remove {what}: only what was behind {it} remains — the water, the ground and the background continued, the same light."


def prepare_clean(store: Any, documents: Any, catalogue: Any, pid: str, vid: str, live: Any) -> dict[str, Any]:
    """The clean under the things (on a worker thread): the things not cleaned yet, their masks' union grown CLEAN_GROW px (their soft edges
    and contact shadows, E28b), as the selection of the set picture's document — what the clean's Fill takes. Every thing cleaned: *Clean
    again* — all of them, on a new document of the picture before any clean (another seed, where a shape was painted in a thing's place)."""
    _, ps = _place_set(store, pid, vid)
    if ps.clean_job_id and live(ps.clean_job_id):
        raise ValueError("the set picture is being cleaned")
    if any(f.fill_job_id and live(f.fill_job_id) for f in ps.faces):
        raise ValueError("the set's Fill is running — wait for it, or stop its job, before cleaning the picture")
    if not ps.things:
        raise ValueError("nothing to clean: pick a thing that moves on the set picture first")
    todo = [t for t in ps.things if not t.cleaned]
    if todo:
        od = ensure_document(store, documents, catalogue, pid, vid)
    else:
        todo = list(ps.things)
        root = catalogue.get(_root(catalogue, picture_of(ps)))
        if root is None:
            raise ValueError("the set picture before its clean is not in the Catalogue")
        with Image.open(catalogue.abs_path(root)) as im:
            base = np.asarray(im.convert("RGBA"))
        od = documents.create("set picture · things", int(base.shape[1]), int(base.shape[0]), "transparent", root.id, base)
        _put(store, pid, vid, lambda x: setattr(x, "things_document_id", od.doc.id))
    union = np.zeros((od.doc.h, od.doc.w), bool)
    for t in todo:
        m = _mask(catalogue, t)
        if m.shape != union.shape:
            raise ValueError(f"{t.name}'s mask ({m.shape[1]}×{m.shape[0]}) does not fit the set picture ({od.doc.w}×{od.doc.h})")
        union |= m
    grown = np.asarray(Image.fromarray(np.where(union, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * CLEAN_GROW + 1))) > 127
    od.selection = np.where(grown, 255, 0).astype(np.uint8)
    od.doc.has_selection = True
    od.dirty = True
    od.save()
    return {"document_id": od.doc.id, "things": [t.id for t in todo], "names": [t.name for t in todo], "picture": picture_of(ps),
            "coverage": round(float(grown.mean()), 4)}


async def clean_job(q: Any, store: Any, documents: Any, catalogue: Any, pid: str, vid: str) -> tuple[Any, dict[str, Any]]:
    """The set picture cleaned under its things: a Fill on its document (as SC3's clean plate; E57: on the ferry's whole mask Fill left fog
    and water where Remove painted a boathouse and content-aware fill smeared a roof), its words an instruction naming them (E58); the
    landing makes the cleaned picture the set's, and the faces are baked from it again (keeping their Fills)."""
    from .place_sets import set_model
    prep = await asyncio.to_thread(prepare_clean, store, documents, catalogue, pid, vid, q.job_live)
    _, ps = await asyncio.to_thread(_place_set, store, pid, vid)
    recipe = {"kind": "inpaint", "mode": "fill", "model_id": set_model(ps, q.app.settings.variant),   # D186: the set's card
              "document_id": prep["document_id"], "prompt_text": clean_prompt(prep["names"]), "feather": 8}
    origin = JobOrigin(suite="story", surface=CLEAN_SURFACE, ref=pid, payload={"version": vid, "things": prep["things"], "picture": prep["picture"]})
    return await _staged(q, store, pid, vid, recipe, origin, lambda x, jid: setattr(x, "clean_job_id", jid)), prep


def clean_landed(q: Any, job: Any, od: Any) -> Any | None:
    """The clean landed on the set picture's document (on a worker thread): its visible composite is the cleaned picture (lineage
    `clean-plate` ← the picture), the set's picture from now on; its things are marked cleaned, and the bake is due again (`keep_fills_key`:
    a bake for the same set and camera keeps the faces' Fills). A set fitted to another picture meanwhile keeps its own; a clean that
    painted the things back (E58: their pixels moved under CLEAN_SAME) is not used and says so (*Clean* again tries another seed)."""
    from .story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    vid, was, tids = str(payload.get("version") or ""), str(payload.get("picture") or ""), {str(x) for x in payload.get("things") or []}
    store = StoryStore(q.ws)
    try:
        _, ps = _place_set(store, pid, vid)
    except (KeyError, ValueError):
        job.log_tail.append("the place's set is gone; the clean is not used")
        return None
    if picture_of(ps) != was:
        job.log_tail.append("the set was fitted to another picture meanwhile; the clean is not used")
        return clean_failed(q, job)
    merged = od.flatten()
    moved = same_as_picked(q.catalogue, ps, tids, merged)
    if moved is not None and moved < CLEAN_SAME:
        why = f"the clean painted the things back (their pixels moved {moved:.1f} of 255) — Clean again ▶ tries another seed"
        job.log_tail.append(why)
        p = clean_failed(q, job)
        if p is not None:
            q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision, "error": f"The set picture: {why}"})
        return None
    path = q.ws.temp_dir / "things" / f"{new_id('cln')}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(merged[..., :3])).save(path, "PNG")
    rec = q.catalogue.make_thumbs(q.catalogue.ingest_file(path, kind="image", move=True, job_id=job.id, suite="story", parents=[was], lineage_kind="clean-plate",
                                                          params={"profile_id": pid, "version": vid, "things": sorted(tids)}, origin=job.origin))
    q.hub.broadcast("asset.created", rec.model_dump())
    job.result["asset_ids"] = [rec.id]

    def put(x: PlaceSet) -> None:
        x.sources[0].asset_id = rec.id
        for t in x.things:
            t.cleaned = t.cleaned or t.id in tids
        if x.clean_job_id == job.id:
            x.clean_job_id = None
        if x.baked_key is not None:
            x.keep_fills_key, x.baked_key = x.baked_key, None
    p = _put(store, pid, vid, put)
    job.log_tail.append(f"the set picture cleaned under {len(tids)} thing{'s' if len(tids) != 1 else ''} ({rec.id}); the faces are baked from it again")
    return p


def same_as_picked(catalogue: Any, ps: PlaceSet, tids: set[str], merged: np.ndarray) -> float | None:
    """How far a clean moved its things' pixels from the picture each was picked on (the mean over their masks, of 255); None when none
    can be read."""
    diffs, n = 0.0, 0
    for t in ps.things:
        if t.id not in tids:
            continue
        try:
            m = _mask(catalogue, t)
            with Image.open(catalogue.abs_path(catalogue.get(_picked_on(catalogue, ps, t)))) as im:
                was = np.asarray(im.convert("RGB")).astype(np.int16)
        except Exception:  # noqa: BLE001 — a mask or a picture gone from the Catalogue
            continue
        if m.shape != merged.shape[:2] or was.shape[:2] != m.shape:
            continue
        diffs += float(np.abs(was[m] - merged[..., :3][m].astype(np.int16)).sum()) / 3
        n += int(m.sum())
    return diffs / n if n else None


def clean_failed(q: Any, job: Any) -> Any | None:
    """The clean failed, was cancelled or is not used: the set lets go of it. Never raises."""
    from .story import StoryStore
    pid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("version") or "")
    try:
        return _put(StoryStore(q.ws), pid, vid, lambda x: setattr(x, "clean_job_id", None if x.clean_job_id == job.id else x.clean_job_id))
    except (KeyError, ValueError):
        return None


def keep_fill(filled: np.ndarray, bake: np.ndarray, cov: np.ndarray, fid: str, kind: str) -> np.ndarray:
    """A face baked again from the cleaned picture keeps its Fill: the new bake where the picture sees it well (the thing gone from it), the
    Fill where the Fill painted (`fill_mask` of the coverage) and wherever the bake is unseen."""
    from .place_sets import fill_mask, unseen_cos
    out = np.ascontiguousarray(bake[..., :3]).copy()
    take = fill_mask(cov, unseen_cos(fid, kind)) | (bake[..., 3] < 255)
    out[take] = filled[..., :3][take]
    return out


def _root(catalogue: Any, aid: str) -> str:
    """The picture a cleaned set picture was cleaned from (through every clean)."""
    a = catalogue.get(aid)
    while a is not None and a.lineage_kind == "clean-plate" and a.parents:
        aid = a.parents[0]
        a = catalogue.get(aid)
    return aid


def restand(catalogue: Any, keep: PlaceSet | None, new: PlaceSet) -> PlaceSet:
    """A set fitted again keeps the things picked on the picture it was fitted to (cleaned or not), each stood again under the new camera;
    none is cleaned from the picture it now has (the things' document is made again from it). A thing picked on another picture goes."""
    if keep is None or not keep.things or not new.sources:
        return new
    cam, root, things = new.sources[0].camera, _root(catalogue, picture_of(new)), []
    for t in keep.things:
        try:
            if _root(catalogue, _picked_on(catalogue, keep, t)) != root:
                continue
            things.append(t.model_copy(update={**stand(cam, _mask(catalogue, t)), "cleaned": False}))
        except Exception:  # noqa: BLE001 — a mask gone from the Catalogue: the thing goes with it
            continue
    return new.model_copy(update={"things": things})
