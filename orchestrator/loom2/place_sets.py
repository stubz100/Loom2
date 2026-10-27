"""proto01_UIcast CW6 (04 §3–4; E38 → D143): a place's set built from its picture.

1. **Fit** — *Build the set ▶* runs MoGe-2 on the place's set picture (an `image_to_set` job on origin `set_fit`); its finisher reads the
   relief as a room, a corridor, a street or open ground (`set_fit.fit_set`), scaled by the camera's height (D143: MoGe's own scale ran
   1.06–2× short; eye level, 1.6 m, unless the author says otherwise), and puts the set on the place's Cast version with the picture as its
   source, the camera it was matched to and what the fit had to assume.
2. **Bake** — the client renders each face straight on with the picture projected onto it (stage/setBake.ts) at the kind's texel and
   uploads the face's texture and its coverage; they become Catalogue images (lineage `set-bake` ← the picture), the faces the version's.
3. **Fill** — what the picture never saw (or saw through pixels over two texels wide) is painted by Klein's Fill, face by face, most seen
   first, each with its material named (D143: the neutral prompt left patches): PF1's route with the face as the frame — an Edit document
   with the bad texels as its selection, the Fill, the document flattened into the face's texture; each landing queues the next face.

The set lives on the version (`ProfileVersion.place_set`); a bench binds it in Clay (D142), CW7 on any stage."""
from __future__ import annotations

import asyncio
import secrets
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

from .origin import JobOrigin
from .stages import PlaceSet, SetFace, SetSource, SourceCamera

SET_FIT_SURFACE = "set_fit"                      # origin.surface of a set's fit (image_to_set); ref = the place, payload {version, from, camera_height_m}
SET_FILL_SURFACE = "set_fill"                    # origin.surface of a face's Fill (inpaint); ref = the place, payload {version, face, rest, seed, document_id}
EYE_HEIGHT_M = 1.6                               # D143: the camera's height a fit is scaled by unless the author gives one
TEXEL_BY_KIND = {"room": 0.01, "corridor": 0.02, "street": 0.04, "ground": 0.04}   # D143 (stage/setBake.ts TEXEL_BY_KIND)
UNSEEN_COS = 0.05                                # D133 / E38: a texel seen at a cosine under this is unseen
COARSE_TEXELS = 2.0                              # … or seen through a picture pixel over two texels wide
RATIO_SCALE = 8.0                                # the coverage's green × this = the picture's pixel in texels (setBake.ts COVERAGE_RATIO_SCALE)
FILL_MIN = 0.002                                 # PF1: a face with less to fill is left as baked
ROOM_FACES = ("floor", "ceiling", "wall")        # a room's or a corridor's faces: filled plain (E38: a Fill invents windows on a wall)
NOUN = {"floor": "the floor", "ceiling": "the ceiling", "wall": "a wall", "road": "the road's surface", "pavement": "the pavement",
        "facade": "the buildings' fronts", "end": "the far end of the street", "backdrop": "the land and the sky in the distance"}


def fit_origin(pid: str, vid: str, source: str, camera_height_m: float) -> JobOrigin:
    return JobOrigin(suite="story", surface=SET_FIT_SURFACE, ref=pid, payload={"version": vid, "from": source, "camera_height_m": camera_height_m})


def set_picture(v: Any) -> str | None:
    """The picture a place's set is fitted to: its set picture (the empty place, its animation-reference slot), else its hero."""
    return v.anim_ref_asset_id or v.hero_asset_id


def place_set_from_fit(f: dict[str, Any], asset_id: str, relief_asset_id: str | None, keep: PlaceSet | None = None) -> PlaceSet:
    """A fit as the version's set: its kind and sizes, the parts as the kind has them (a set fitted again keeps the parts the author turned
    off, and the faces' materials), the picture as its one source with the camera and what the fit assumed; no faces yet (the bake's)."""
    cam = SourceCamera(**f["camera"])
    src = SetSource(asset_id=asset_id, camera=cam, relief_asset_id=relief_asset_id, assumed=list(f.get("assumed") or []), lens_deg=f.get("lens_deg"))
    same = keep is not None and keep.kind == f["kind"]
    materials = {x.id: x.material for x in keep.faces if x.material} if keep is not None else {}
    faces = [SetFace(id=fid, material=m, texel_m=TEXEL_BY_KIND[f["kind"]]) for fid, m in materials.items()] if same else []
    return PlaceSet(kind=f["kind"], sizes=dict(f["sizes"]), parts=dict(keep.parts) if same and keep is not None else {}, faces=faces, sources=[src])


def fit_landed(q: Any, job: Any, relief_asset_id: str, glb: Path) -> None:
    """The relief landed: the set fitted to it and put on the place's version. A picture with too little floor fits nothing — the job says
    why (`result.set_error`) and the version keeps the set it had. Never the job's failure (the relief stays in the Catalogue)."""
    from .relief import glb_read, lens_of, mesh_arrays
    from .set_fit import fit_set
    from .story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    vid, source = str(payload.get("version") or ""), str(payload.get("from") or "")
    h = float(payload.get("camera_height_m") or EYE_HEIGHT_M)
    try:
        doc, binary = glb_read(glb)
        pos, uv, _ = mesh_arrays(doc, binary)
        if uv is None:
            raise ValueError("the relief carries no UVs — the lens cannot be read from it")
        lens = lens_of(pos, uv) or {}
        f = fit_set(pos, uv, lens.get("fov_x"), camera_height_m=h)
        store = StoryStore(q.ws)
        p = store.profile(pid)
        if p is None:
            raise ValueError("the place is gone")
        keep = p.version(vid).place_set
        p = store.set_place_set(pid, vid, place_set_from_fit(f, source, relief_asset_id, keep))
        job.result["set"] = {"kind": f["kind"], "sizes": f["sizes"], "assumed": f["assumed"], "pitch_deg": f["pitch_deg"], "scale": f["scale"]}
        job.log_tail.append(f"the set: a {f['kind']} {', '.join(f'{k} {v} m' for k, v in f['sizes'].items())}; the camera {h} m up, "
                            f"pitched {f['pitch_deg']}°; assumed: {', '.join(f['assumed']) or 'nothing'}")
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    except Exception as e:  # noqa: BLE001
        job.result["set_error"] = str(e)
        job.log_tail.append(f"the set was not fitted: {e}")
        q.hub.broadcast("story.changed", {"kind": "profile", "id": pid, "revision": 0, "error": f"The set: {e}"})


def face_noun(fid: str) -> str:
    return NOUN.get(fid.split("_")[0], "the surface")


def fill_prompt(fid: str, material: str, place: str, kind: str = "room") -> str:
    """D143: a face's Fill prompt. A material named (the author's words) is the whole subject — E38's clean wall named its material and
    nothing else; CW6's rig: the place's words beside it ("a farmhouse kitchen") painted a window and pots onto the kitchen's floor. Without
    one, the face's noun and the place's words. A room's faces are plain (a Fill invents windows on a wall); a corridor's, a street's and
    the backdrop are continued as the rest (an alley's walls are building fronts, their windows belong)."""
    named = (material or "").strip().rstrip(".")
    what = named or face_noun(fid)
    what = what[0].upper() + what[1:]
    if kind == "room" and fid.split("_")[0] in ROOM_FACES:
        lead = f"{what}, seen straight on: its surface continued plain and even, nothing on it and nothing in front of it — no window, no door, no picture, no furniture, no people — the same light."
    else:
        lead = f"{what}, seen straight on: continued seamlessly as the rest of it, the same materials and pattern, the same light, no people."
    place = (place or "").strip().rstrip(".")
    return f"{lead} The place: {place}." if place and not named else lead


def fill_mask(cov: np.ndarray) -> np.ndarray:
    """The texels a face's Fill takes, from its coverage (RGB bytes): unseen, or seen through a pixel over two texels wide."""
    c = cov.astype(np.float32) / 255.0
    return (c[..., 0] < UNSEEN_COS) | (c[..., 1] * RATIO_SCALE > COARSE_TEXELS)


def fill_order(ps: PlaceSet, only: list[str] | None = None) -> list[str]:
    """The faces to fill, the most seen first (D143: a corner's neighbour gives the next its edge): baked, not filled, with something to
    fill; `only` picks some — a face picked by name is filled again from its bake when it already was (another seed)."""
    faces = [f for f in ps.faces if f.baked_asset_id and f.coverage_asset_id and (f.bad or 0.0) >= FILL_MIN and (only is None or f.id in only)
             and (not f.filled or only is not None)]
    return [f.id for f in sorted(faces, key=lambda f: (f.bad or 0.0, f.id))]


class NothingToFill(ValueError):
    """V32: no face of the order wants a Fill — and why: the route's 422 says it (it used to say "the bakes are gone" for a face whose
    mask is under the minimum, with the bakes right there)."""


class FillPlan(NamedTuple):
    """A face's Fill prepared off the loop (V22): its document made from the bake, the recipe and the origin to submit."""
    pid: str
    vid: str
    fid: str
    recipe: dict
    origin: JobOrigin


def prepare_fill(q: Any, pid: str, vid: str, order: list[str], seed: int | None = None, again: bool = False) -> FillPlan | None:
    """The first face of `order` that still wants its Fill (its document made from the bake, its selection the bad texels), the rest carried
    in the origin; None when none does. `again`: a filled face is filled again from its bake. File and pixel work — a worker thread's."""
    from PIL import Image

    from .models import registry
    from .story import StoryStore, compose_sheet
    if q.documents is None:
        raise ValueError("the Edit documents are not open")
    store = StoryStore(q.ws)
    seed = seed or secrets.randbelow(2**31 - 2) + 1
    why: set[str] = set()
    for k, fid in enumerate(order):
        p = store.profile(pid)
        if p is None:
            return None
        v = p.version(vid)
        ps = v.place_set
        face = next((f for f in ps.faces if f.id == fid), None) if ps is not None else None
        if face is None:
            why.add("gone")
            continue
        if face.filled and not again:
            why.add("filled")
            continue
        if not face.baked_asset_id or not face.coverage_asset_id:
            why.add("unbaked")
            continue
        tex_rec, cov_rec = q.catalogue.get(face.baked_asset_id), q.catalogue.get(face.coverage_asset_id)
        if tex_rec is None or cov_rec is None:
            why.add("unbaked")
            continue
        with Image.open(q.catalogue.abs_path(tex_rec)) as im:
            rgba = np.asarray(im.convert("RGBA")).copy()
        with Image.open(q.catalogue.abs_path(cov_rec)) as im:
            mask = fill_mask(np.asarray(im.convert("RGB")))
        if mask.shape != rgba.shape[:2] or float(mask.mean()) < FILL_MIN:
            why.add("small")
            continue
        rgba[rgba[..., 3] < 255, :3] = 128                                      # unseen texels grey before the Fill paints them (E38)
        rgba[..., 3] = 255
        od = q.documents.create(f"{p.name} · set · {fid}", int(rgba.shape[1]), int(rgba.shape[0]), "transparent", tex_rec.id, rgba)
        od.selection = np.where(mask, 255, 0).astype(np.uint8)
        od.doc.has_selection = True
        od.dirty = True
        od.save()
        prompt = fill_prompt(fid, face.material, compose_sheet(v, name=p.name, cls=p.cls), ps.kind)
        recipe = {"kind": "inpaint", "mode": "fill", "model_id": registry.default_model("inpaint", q.app.settings.variant),   # Klein 4B under `open` (D26)
                  "document_id": od.doc.id, "prompt_text": prompt, "seeds": [seed], "expand": 6, "feather": 8}
        origin = JobOrigin(suite="story", surface=SET_FILL_SURFACE, ref=pid,
                           payload={"version": vid, "face": fid, "rest": order[k + 1:], "seed": seed, "document_id": od.doc.id, "again": again})
        return FillPlan(pid, vid, fid, recipe, origin)
    if not why:
        return None
    if why <= {"filled"}:
        raise NothingToFill("nothing to fill: these faces are filled — name a face to fill it again with another seed")
    if why <= {"filled", "small"}:
        raise NothingToFill("nothing to fill: the picture saw these faces well enough (under the Fill's minimum share)")
    if why & {"unbaked"}:
        raise NothingToFill("nothing to fill: the faces' bakes are gone from the Catalogue — bake the set again")
    raise NothingToFill("nothing to fill: the faces are gone from the set — bake the set again")


async def start_fill(q: Any, plan: FillPlan) -> Any:
    """V21 / V22: the Fill is submitted on the loop (the queue is loop-only), *staged* until its face names it, then released — the face
    never names a job that is not there, and the job never runs before its marker is on disk. A job refused at submission (the VRAM
    budget) sets no marker and raises with the reason."""
    from .story import StoryStore
    job = q.submit(plan.recipe, stage=True, origin=plan.origin)[0]
    if job.status != "staged":
        raise ValueError(job.error or "the Fill was refused")
    store = StoryStore(q.ws)
    try:
        p = await asyncio.to_thread(store.update_face, plan.pid, plan.vid, plan.fid, fill_job_id=job.id)
    except Exception:
        await q.cancel(job.id)                                                  # the face is gone meanwhile: the job never runs
        raise
    q.release(job.id)
    q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    return job


async def queue_fill(q: Any, pid: str, vid: str, order: list[str], seed: int | None = None, again: bool = False) -> Any | None:
    """*Fill ▶*'s next job: prepared on a thread, submitted on the loop (`start_fill`); None when no face in `order` wants a Fill."""
    plan = await asyncio.to_thread(prepare_fill, q, pid, vid, order, seed, again)
    return None if plan is None else await start_fill(q, plan)


def fill_landed(q: Any, job: Any, od: Any) -> list[str]:
    """A face's Fill landed on its document: flattened, it is the face's texture (lineage `set-fill` ← the bake); the document closes.
    Returns the faces still to fill (`fill_next` queues the first). A face baked again meanwhile keeps its new bake. Never the job's
    failure — and a landing that fails lets go of its face (V25), so the next *Fill ▶* can take it."""
    from PIL import Image

    from .fsio import new_id
    from .story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    vid, fid = str(payload.get("version") or ""), str(payload.get("face") or "")
    try:
        merged = od.flatten()
        path = q.ws.temp_dir / "set_fills" / f"{new_id('sfill')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(merged[..., :3]).save(path, "PNG")
        rec = q.catalogue.ingest_file(path, kind="image", move=True, job_id=job.id, suite="story", lineage_kind="set-fill",
                                      parents=[od.doc.source_asset_id] if od.doc.source_asset_id else [], params={"profile_id": pid, "version": vid, "face": fid},
                                      origin=job.origin)
        rec = q.catalogue.make_thumbs(rec)
        q.hub.broadcast("asset.created", rec.model_dump())
        job.result["asset_ids"] = [rec.id]
        store = StoryStore(q.ws)
        p = store.profile(pid)
        face = next((f for f in (p.version(vid).place_set.faces if p and p.version(vid).place_set else []) if f.id == fid), None)
        if face is not None and face.fill_job_id == job.id:
            p = store.update_face(pid, vid, fid, texture_asset_id=rec.id, filled=True, fill_job_id=None)
            job.log_tail.append(f"the set's {fid}: filled ({rec.id})")
            q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
        else:
            job.log_tail.append(f"the set's {fid} was baked again meanwhile; {rec.id} not used")
        if q.documents is not None:
            q.documents.close(od.doc.id)
        return [str(x) for x in payload.get("rest") or []]
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the set's {fid}: {e}")
        try:                                                                    # V25: the face is not left waiting on a job that is done
            store = StoryStore(q.ws)
            p = store.profile(pid)
            ps = p.version(vid).place_set if p is not None else None
            if ps is not None and any(f.id == fid and f.fill_job_id == job.id for f in ps.faces):
                p = store.update_face(pid, vid, fid, fill_job_id=None)
                q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision, "error": f"The set's {fid}: the Fill landed but {e}"})
        except Exception:  # noqa: BLE001
            pass
        return []


async def fill_next(q: Any, job: Any, rest: list[str]) -> None:
    """After a landing: the next face's Fill from the landed job's origin (its seed and `again` carried). A refusal is noted on the landed
    job, never its failure."""
    payload = job.origin.payload or {}
    pid, vid = str(job.origin.ref or ""), str(payload.get("version") or "")
    try:
        nxt = await queue_fill(q, pid, vid, rest, int(payload.get("seed") or 0) or None, bool(payload.get("again")))
    except NothingToFill as e:                                                  # V32: the chain's end, said as it is
        job.log_tail.append(f"the set's Fill is done: {e}")
        return
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the next face was not queued: {e}")
        return
    if nxt is not None:
        job.result["next_job_id"] = nxt.id


def fill_failed(q: Any, job: Any, msg: str) -> None:
    """A face's Fill failed or was cancelled: the face waits for the next *Fill ▶* (the faces after it too). Never raises."""
    from .story import StoryStore
    try:
        pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
        vid, fid = str(payload.get("version") or ""), str(payload.get("face") or "")
        store = StoryStore(q.ws)
        p = store.profile(pid)
        ps = p.version(vid).place_set if p is not None else None
        if ps is None or not any(f.id == fid and f.fill_job_id == job.id for f in ps.faces):
            return
        p = store.update_face(pid, vid, fid, fill_job_id=None)
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision, "error": f"The set's {fid}: the Fill {msg}"})
    except Exception:  # noqa: BLE001
        pass
