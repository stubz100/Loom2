"""D180 (W60): a part of a built set that moves — the ferry painted into the pier's backdrop could not sail.

A thing is picked on the place's set picture as SC3's things are on a picture set (D123): SAM 3's point prompts on the picture's own
document, the mask kept. Kept, it is cut out (its pixels, the mask as alpha: the card) and stood where the picture shows it — the ray from
the set picture's camera through the bottom centre of its mask meets the set's floor (y = 0 in the set's frame), and its width and height
are its pixels at that distance. It is then a card, or (E56: the pier's ferry came out a recognisable boat) a 3D model made from its
cut-out by the app's image → 3D; Clay places either as an object of its own (frontend placeThings.ts), so it can be keyed. The set picture
can be cleaned under the things (a Fill) so the faces baked again show what was behind them.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image

from .fsio import new_id
from .origin import JobOrigin
from .stages import PlaceSet, PlaceThing, SourceCamera

FIND_SURFACE = "place_thing_find"
MODEL_SURFACE = "place_thing_model"                # payload {version, thing}
CLEAN_SURFACE = "place_things_clean"               # payload {version}
FAR_M = 40.0                                       # a thing whose bottom is above the horizon stands this far out along its ray
CLEAN_GROW = 14                                    # as SC3's (E28b): the mask grown over the thing's soft edge and its contact shadow
CLEAN_PROMPT = ("the same place with the thing gone: the water, the ground and the background continue where it was, the same light")


def _place_set(store: Any, pid: str, vid: str) -> tuple[Any, PlaceSet]:
    p = store.profile(pid)
    if p is None:
        raise KeyError(pid)
    v = p.version(vid)
    if v.place_set is None or not v.place_set.sources:
        raise ValueError("the place has no set yet — Build the set ▶ first")
    return p, v.place_set


def _put(store: Any, pid: str, vid: str, fn: Any) -> Any:
    """The version's set changed in place by `fn(ps)` (read again, so a Fill or a bake meanwhile stays)."""
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


def card(catalogue: Any, picture_id: str, mask: np.ndarray) -> Any:
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
    rec = catalogue.ingest_file(path, kind="image", move=True, suite="story", parents=[picture_id], lineage_kind="place-thing")
    return catalogue.make_thumbs(rec)


def keep(store: Any, documents: Any, catalogue: Any, pid: str, vid: str, name: str, points: list[dict[str, int]]) -> tuple[Any, PlaceThing, list[Any]]:
    """The mask the last find left on the set picture's document, kept as a thing: the mask (a `mask` asset), its card, where it stands."""
    _, ps = _place_set(store, pid, vid)
    if not ps.things_document_id:
        raise ValueError("find the thing on the set picture first (a click on it)")
    od = documents.get(ps.things_document_id)
    sel = od.selection
    if sel is None or not (sel > 127).any():
        raise ValueError("nothing is found yet — click the thing on the set picture")
    mask = clicked(sel > 127, points)
    tmp = catalogue.ws.temp_dir / "things" / f"{new_id('msk')}.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").save(tmp, "PNG")
    label = name.strip() or f"Thing {len(ps.things) + 1}"
    mrec = catalogue.make_thumbs(catalogue.ingest_file(tmp, kind="mask", move=True, suite="story", parents=[picture_of(ps)], lineage_kind="place-thing",
                                                       prompt_text=label, params={"profile_id": pid, "version": vid, "thing": label, "points": points}))
    crec = card(catalogue, picture_of(ps), mask)
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


def thing_of(ps: PlaceSet, tid: str) -> PlaceThing:
    t = next((x for x in ps.things if x.id == tid), None)
    if t is None:
        raise KeyError(f"no thing {tid!r}")
    return t


def remove(store: Any, pid: str, vid: str, tid: str) -> Any:
    _, ps = _place_set(store, pid, vid)
    thing_of(ps, tid)
    return _put(store, pid, vid, lambda x: setattr(x, "things", [t for t in x.things if t.id != tid]))


def model_job(q: Any, store: Any, catalogue: Any, pid: str, vid: str, tid: str) -> Any:
    """The thing's 3D model queued: its cut-out on white (as SC3's, which Pixal3D's template cuts out again) by the app's image → 3D."""
    from .set_things import cutout
    _, ps = _place_set(store, pid, vid)
    t = thing_of(ps, tid)
    if t.mesh_job_id and q.job_live(t.mesh_job_id):
        raise ValueError(f"{t.name}'s 3D model is being made")
    with Image.open(catalogue.abs_path(catalogue.get(t.mask_asset_id))) as im:
        mask = np.asarray(im.convert("L")) > 127
    src = catalogue.ingest_file(cutout(catalogue, picture_of(ps), mask), kind="image", move=True, suite="story", parents=[t.card_asset_id],
                                lineage_kind="place-thing")
    job = q.submit({"kind": "image_to_mesh", "asset_id": src.id},
                   origin=JobOrigin(suite="story", surface=MODEL_SURFACE, ref=pid, payload={"version": vid, "thing": tid}))[0]
    _put(store, pid, vid, lambda x: setattr(thing_of(x, tid), "mesh_job_id", job.id))
    return job


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
