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
CROWD_START_SURFACE = "set_crowd_start"          # D173: a face's crowd — the start's refine (i2i on a document); payload {version, face, from_m, to_m, words, seed, size}
CROWD_SURFACE = "set_crowd"                      # D173: the crowd's loop (i2v, first = last frame); the same payload and the start picture
EYE_HEIGHT_M = 1.6                               # D143: the camera's height a fit is scaled by unless the author gives one
TEXEL_BY_KIND = {"room": 0.01, "corridor": 0.02, "street": 0.04, "ground": 0.04}   # D143 (stage/setBake.ts TEXEL_BY_KIND)
UNSEEN_COS = 0.05                                # D133 / E38: a texel seen at a cosine under this is unseen
COARSE_TEXELS = 2.0                              # … or seen through a picture pixel over two texels wide
RATIO_SCALE = 8.0                                # the coverage's green × this = the picture's pixel in texels (setBake.ts COVERAGE_RATIO_SCALE)
FILL_MIN = 0.002                                 # PF1: a face with less to fill is left as baked
FACADE_COS = 0.7                                 # D170 (E46): a street's fronts stand out from their face (stalls, steps, awnings); seen more
                                                 # than 45° off square they lie on it sheared, so they go to Fill as unseen (stage/setBake.ts)
VERTICAL_PARTS = ("wall", "facade", "end", "backdrop")   # D173: the faces a crowd can stand along
CROWD_MAX_ASPECT = 2.7                           # D173: a stretch at most this many times the face's height (E49: 11.2 × 4.96 m at 1088 × 480)
CROWD_MIN_ASPECT = 0.5
CROWD_PIXELS = 520_000                           # ≈ E49's 1088 × 480
CROWD_FRAMES, CROWD_FPS = 81, 16
CROWD_STRENGTH = 0.6                             # E49b: the refine that puts people in without moving the face far
CROWD_PEOPLE = "people walking left and right along it, seen in profile, some stopping to look, nobody facing the camera"
CROWD_MOTION = "people walk left and right along it, seen in profile; nobody walks toward the camera"
ROOM_FACES = ("floor", "ceiling", "wall")        # a room's or a corridor's faces: filled plain (E38: a Fill invents windows on a wall)
GROUND_FACES = ("floor", "road", "pavement")     # D172 (E48): what is walked on — outside a room, filled from above
GROUND_COS = 0.35                                # D172: what stands on the ground lies on it as a smear when seen at a slant (stage/setBake.ts)
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
    the backdrop are continued as the rest (an alley's walls are building fronts, their windows belong). Klein paints the scene its words
    describe, so a facade is "a flat elevation of" its material (D170, E46) and the ground outside a room "a flat plan view of" it,
    without the place's words (D172, E48)."""
    named = (material or "").strip().rstrip(".")
    what = named or face_noun(fid)
    if fid.split("_")[0] == "facade":                                       # D170 (E46): the elevation first, or Klein paints the place's view down it
        what = what if what[1:2].isupper() else what[:1].lower() + what[1:]
        lead = (f"A flat elevation of {what}, seen square on — no perspective, no vanishing point, no floor and no ceiling in view: continued "
                "seamlessly as the rest of it, the same materials and pattern, the same light, no people.")
        place = (place or "").strip().rstrip(".")
        return f"{lead} The place: {place}." if place and not named else lead
    if kind != "room" and fid.split("_")[0] in GROUND_FACES:              # D172 (E48): from above, the floor continued, never the place's view
        what = what if what[1:2].isupper() else what[:1].lower() + what[1:]
        return (f"A flat plan view of {what}, seen from directly above — no perspective, no walls, no ceiling, no people: continued seamlessly "
                "as the rest of it, the same materials and pattern, the same light.")
    what = what[0].upper() + what[1:]
    if kind == "room" and fid.split("_")[0] in ROOM_FACES:
        lead = f"{what}, seen straight on: its surface continued plain and even, nothing on it and nothing in front of it — no window, no door, no picture, no furniture, no people — the same light."
    else:
        lead = f"{what}, seen straight on: continued seamlessly as the rest of it, the same materials and pattern, the same light, no people."
    place = (place or "").strip().rstrip(".")
    return f"{lead} The place: {place}." if place and not named else lead


def unseen_cos(fid: str, kind: str = "room") -> float:
    """The cosine under which a face's texel counts as unseen: a facade's FACADE_COS (D170), the ground's outside a room GROUND_COS (D172),
    any other face's UNSEEN_COS."""
    part = fid.split("_")[0]
    if part == "facade":
        return FACADE_COS
    return GROUND_COS if kind != "room" and part in GROUND_FACES else UNSEEN_COS


def fill_mask(cov: np.ndarray, unseen: float = UNSEEN_COS) -> np.ndarray:
    """The texels a face's Fill takes, from its coverage (RGB bytes): unseen (a cosine under `unseen`, unseen_cos), or seen through a pixel
    over two texels wide."""
    c = cov.astype(np.float32) / 255.0
    return (c[..., 0] < unseen) | (c[..., 1] * RATIO_SCALE > COARSE_TEXELS)


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
            mask = fill_mask(np.asarray(im.convert("RGB")), unseen_cos(fid, ps.kind))
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


# ---- D173: a crowd along a face ---------------------------------------------------------------------------------------------------
def crowd_size(width_m: float, height_m: float) -> tuple[int, int]:
    """D173: the loop's size for a stretch — ≈ CROWD_PIXELS at the stretch's aspect, on Wan's ×16 grid. Raises ValueError outside the
    aspects a loop holds (E49: 2.27)."""
    if height_m <= 0 or width_m <= 0:
        raise ValueError("the stretch is empty")
    a = width_m / height_m
    if a > CROWD_MAX_ASPECT:
        raise ValueError(f"a crowd covers at most {CROWD_MAX_ASPECT:g}× the face's height ({CROWD_MAX_ASPECT * height_m:.1f} m on this face) — make two")
    if a < CROWD_MIN_ASPECT:
        raise ValueError(f"a crowd covers at least {CROWD_MIN_ASPECT:g}× the face's height ({CROWD_MIN_ASPECT * height_m:.1f} m on this face)")
    h = max(128, round((CROWD_PIXELS / a) ** 0.5 / 16) * 16)
    return max(128, round(a * h / 16) * 16), h


def crowd_prompts(fid: str, material: str, words: str) -> tuple[str, str]:
    """D173: the start's words (the face as an elevation with its people, E49b) and the loop's (their motion, the camera held)."""
    what = (material or "").strip().rstrip(".") or face_noun(fid)
    what = what if what[1:2].isupper() else what[:1].lower() + what[1:]
    people = (words or "").strip().rstrip(".") or CROWD_PEOPLE
    start = f"A flat elevation of {what}, seen square on: {people}, seen from the side at eye level, even light, no perspective."
    motion = (words or "").strip().rstrip(".") or CROWD_MOTION
    return start, f"{motion}; a static locked-off camera."


class CrowdPlan(NamedTuple):
    pid: str
    vid: str
    fid: str
    recipe: dict[str, Any]
    origin: JobOrigin


def prepare_crowd(q: Any, pid: str, vid: str, fid: str, from_m: float, to_m: float, words: str = "", seed: int | None = None) -> CrowdPlan:
    """D173: a face's crowd, its first step — the face's texture over the stretch scaled to the loop's size, a document refined by Klein
    with the people in (E49b). File and pixel work — a worker thread's. Raises ValueError when the face cannot take one."""
    from PIL import Image

    from .models import registry
    from .story import StoryStore
    if q.documents is None:
        raise ValueError("the Edit documents are not open")
    p = StoryStore(q.ws).profile(pid)
    if p is None:
        raise KeyError(pid)
    ps = p.version(vid).place_set
    face = next((f for f in ps.faces if f.id == fid), None) if ps is not None else None
    if face is None:
        raise KeyError(f"the set has no face {fid!r}")
    if fid.split("_")[0] not in VERTICAL_PARTS:
        raise ValueError("a crowd stands along a wall, a street's fronts or its end — not on the ground or a ceiling")
    if face.crowd is not None and face.crowd.status == "making" and face.crowd.job_id and q.job_live(face.crowd.job_id):
        raise ValueError("the face's crowd is being made — wait for it, or stop its job")
    rec = q.catalogue.get(face.texture_asset_id) if face.texture_asset_id else None
    if rec is None:
        raise ValueError("the face has no texture yet — bake the set first")
    with Image.open(q.catalogue.abs_path(rec)) as im:
        tex = im.convert("RGB")
    width_m, height_m = tex.width * face.texel_m, tex.height * face.texel_m
    from_m, to_m = max(0.0, float(from_m)), min(width_m, float(to_m))
    if to_m - from_m < 0.5:
        raise ValueError(f"the stretch is inside the face's 0–{width_m:.1f} m and at least 0.5 m long")
    w, h = crowd_size(to_m - from_m, height_m)
    x0, x1 = round(from_m / face.texel_m), max(round(from_m / face.texel_m) + 1, round(to_m / face.texel_m))
    crop = tex.crop((x0, 0, x1, tex.height)).resize((w, h), Image.LANCZOS)
    rgba = np.dstack([np.asarray(crop), np.full((h, w), 255, np.uint8)])
    od = q.documents.create(f"{p.name} · crowd · {fid}", w, h, "transparent", rec.id, rgba)
    od.save()
    seed = seed or secrets.randbelow(2**31 - 2) + 1
    start, _ = crowd_prompts(fid, face.material, words)
    recipe = {"kind": "i2i", "model_id": registry.default_model("i2i", q.app.settings.variant), "document_id": od.doc.id, "source": "visible",
              "prompt_text": start, "strength": CROWD_STRENGTH, "match_colour": True, "seeds": [seed]}   # E51: the face's own colours kept (ΔE 0.01)
    origin = JobOrigin(suite="story", surface=CROWD_START_SURFACE, ref=pid,
                       payload={"version": vid, "face": fid, "from_m": round(from_m, 3), "to_m": round(to_m, 3), "words": words, "seed": seed,
                                "size": [w, h], "document_id": od.doc.id})
    return CrowdPlan(pid, vid, fid, recipe, origin)


async def _staged(q: Any, recipe: dict[str, Any], origin: JobOrigin, pid: str, vid: str, fid: str, crowd: dict[str, Any]) -> Any:
    """Fill's pattern (V21 / V22): submitted staged, the face names the job, then released — the job never runs before its marker is on disk."""
    from .stages import SetCrowd
    from .story import StoryStore
    job = q.submit(recipe, stage=True, origin=origin)[0]
    if job.status != "staged":
        raise ValueError(job.error or "the crowd was refused")
    try:
        p = await asyncio.to_thread(StoryStore(q.ws).update_face, pid, vid, fid, crowd=SetCrowd(**crowd, status="making", job_id=job.id, error=None))
    except Exception:
        await q.cancel(job.id)
        raise
    q.release(job.id)
    q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    return job


async def queue_crowd(q: Any, pid: str, vid: str, fid: str, from_m: float, to_m: float, words: str = "", seed: int | None = None) -> Any:
    """*Crowd ▶*: the start's refine prepared on a thread and submitted on the loop; the face's crowd is *making* from now on."""
    plan = await asyncio.to_thread(prepare_crowd, q, pid, vid, fid, from_m, to_m, words, seed)
    pl = plan.origin.payload
    return await _staged(q, plan.recipe, plan.origin, pid, vid, fid, {"from_m": pl["from_m"], "to_m": pl["to_m"], "words": words})


def crowd_start_landed(q: Any, job: Any, od: Any) -> str | None:
    """D173: the start's refine landed on its document — flattened, it is the loop's start picture (lineage `set-crowd` ← the face's
    texture); the document closes. None (and the crowd failed) when it cannot be read."""
    from PIL import Image

    from .fsio import new_id
    pid, pl = str(job.origin.ref or ""), job.origin.payload or {}
    try:
        merged = od.flatten()
        path = q.ws.temp_dir / "set_crowds" / f"{new_id('scrowd')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(merged[..., :3]).save(path, "PNG")
        rec = q.catalogue.ingest_file(path, kind="image", move=True, job_id=job.id, suite="story", lineage_kind="set-crowd",
                                      parents=[od.doc.source_asset_id] if od.doc.source_asset_id else [],
                                      params={"profile_id": pid, "version": pl.get("version"), "face": pl.get("face"), "from_m": pl.get("from_m"), "to_m": pl.get("to_m")},
                                      origin=job.origin)
        rec = q.catalogue.make_thumbs(rec)
        q.hub.broadcast("asset.created", rec.model_dump())
        job.result["asset_ids"] = [rec.id]
        if q.documents is not None:
            q.documents.close(od.doc.id)
        return rec.id
    except Exception as e:  # noqa: BLE001
        crowd_failed(q, job, f"its start could not be read: {e}")
        return None


async def queue_crowd_loop(q: Any, job: Any, start_id: str) -> None:
    """D173: the loop from the start picture back to it (the default I2V model, first = last frame, E49c), staged on the face."""
    from .models import registry
    pid, pl = str(job.origin.ref or ""), dict(job.origin.payload or {})
    vid, fid = str(pl.get("version") or ""), str(pl.get("face") or "")
    try:
        model = registry.default_model("i2v", q.app.settings.variant)
        spec = registry.get(model)
        if spec is None or not spec.recipes.flf:
            raise ValueError("no video model in this build runs from a first to a last frame")
        from .story import StoryStore
        p = StoryStore(q.ws).profile(pid)
        face = next((f for f in p.version(vid).place_set.faces if f.id == fid), None) if p is not None and p.version(vid).place_set else None
        if face is None or face.crowd is None or face.crowd.job_id != job.id:
            job.log_tail.append(f"the set's {fid}: its crowd was removed or made again meanwhile")
            return
        _, motion = crowd_prompts(fid, face.material, str(pl.get("words") or ""))
        w, h = pl.get("size") or [1088, 480]
        recipe = {"kind": "i2v", "model_id": model, "start_asset": start_id, "end_asset": start_id, "prompt_text": motion, "frames": CROWD_FRAMES,
                  "fps": CROWD_FPS, "width": int(w), "height": int(h), "preset": "draft", "seeds": [int(pl.get("seed") or 0)]}
        origin = JobOrigin(suite="story", surface=CROWD_SURFACE, ref=pid, payload={**pl, "start_asset_id": start_id})
        nxt = await _staged(q, recipe, origin, pid, vid, fid, {"from_m": face.crowd.from_m, "to_m": face.crowd.to_m, "words": face.crowd.words})
        job.result["next_job_id"] = nxt.id
        job.log_tail.append(f"the set's {fid}: the crowd's loop queued ({nxt.id})")
    except Exception as e:  # noqa: BLE001
        crowd_failed(q, job, str(e))


def crowd_landed(q: Any, job: Any, clip: Any) -> None:
    """D173: the loop landed (its tone locked and its seam faded by the finisher) — the face plays it. A crowd removed or made again
    meanwhile keeps what it has. Never raises."""
    from .stages import SetCrowd
    from .story import StoryStore
    pid, pl = str(job.origin.ref or ""), job.origin.payload or {}
    vid, fid = str(pl.get("version") or ""), str(pl.get("face") or "")
    try:
        store = StoryStore(q.ws)
        p = store.profile(pid)
        face = next((f for f in p.version(vid).place_set.faces if f.id == fid), None) if p is not None and p.version(vid).place_set else None
        if face is None or face.crowd is None or face.crowd.job_id != job.id:
            job.log_tail.append(f"the set's {fid}: its crowd was removed or made again meanwhile; {clip.id} not used")
            return
        c = face.crowd.model_dump() | {"status": "done", "job_id": None, "error": None, "clip_id": clip.id, "asset_id": clip.asset_id,
                                        "frames": clip.frames, "fps": clip.fps}
        p = store.update_face(pid, vid, fid, crowd=SetCrowd(**c))
        job.log_tail.append(f"the set's {fid}: a crowd over {face.crowd.from_m}–{face.crowd.to_m} m ({clip.id})")
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the set's {fid}: the crowd landed but {e}")


def crowd_failed(q: Any, job: Any, msg: str) -> None:
    """D173: a step of a face's crowd failed or was cancelled — the crowd says so (the author makes it again or removes it). Never raises."""
    from .stages import SetCrowd
    from .story import StoryStore
    try:
        pid, pl = str(job.origin.ref or ""), job.origin.payload or {}
        vid, fid = str(pl.get("version") or ""), str(pl.get("face") or "")
        store = StoryStore(q.ws)
        p = store.profile(pid)
        face = next((f for f in p.version(vid).place_set.faces if f.id == fid), None) if p is not None and p.version(vid).place_set else None
        if face is None or face.crowd is None or face.crowd.job_id != job.id:
            return
        p = store.update_face(pid, vid, fid, crowd=SetCrowd(**(face.crowd.model_dump() | {"status": "failed", "job_id": None, "error": msg})))
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision, "error": f"The set's {fid}: the crowd {msg}"})
    except Exception:  # noqa: BLE001
        pass
