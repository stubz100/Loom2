"""D123 (SC3c, proto01_animate 25 §3): the things of a picture set — picked by the author on the picture, one at a time.

A picture set has its own Edit document (its picture as the one layer, `StageObject.things_document_id`): a click on the picture is a SAM 3
point prompt (`segment`, mode `points`, op `replace`) on that document, so the mask lands as its selection and the client draws it; *keep*
reads the selection back as a Catalogue `mask` asset (lineage `set-thing` ← the picture) and the set records the thing with the relief and
floor it was picked on — what SC3c-3's placement reads. Nothing is cut or modelled that the author did not pick (D123).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .fsio import new_id
from .stages import SetThing, Stage, StageObject, StageStore

FIND_SURFACE = "set_thing_find"
CLEAN_SURFACE = "set_clean"                        # SC3c-3: the plate cleaned under the things (a Fill on the set's document)
REBUILD_SURFACE = "set_rebuild"                    # SC3c-3: the relief rebuilt from the clean plate
MODEL_SURFACE = "set_thing_model"                  # SC3c-3: a thing's Pixal3D model, placed when it lands
CLEAN_GROW = 14                                    # E28b: the removal mask is the things grown 14 px (their soft edges and contact shadows)
CLEAN_PROMPT = ("the same place with nothing standing in it: the floor, the walls and the background continue where the things were, "
                "the same light")


def check_points(points: list[dict[str, Any]], w: int, h: int) -> list[dict[str, int]]:
    """Points on the picture ({x, y, label}: pixels, label 1 = the thing, 0 = not it) — inside it, at least one on the thing."""
    out = []
    for p in points:
        x, y, label = int(p["x"]), int(p["y"]), int(p.get("label", 1))
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"the point ({x}, {y}) is outside the picture ({w}×{h})")
        out.append({"x": x, "y": y, "label": 1 if label else 0})
    if not any(p["label"] == 1 for p in out):
        raise ValueError("click the thing on the picture (at least one point on it)")
    return out


def ensure_document(store: StageStore, documents: Any, catalogue: Any, st_id: str, set_id: str) -> Any:
    """The set's own document (made from its picture the first time; made again when it was deleted)."""
    _, obj = store.picture_set(st_id, set_id)
    if obj.things_document_id:
        try:
            return documents.get(obj.things_document_id)
        except Exception:  # noqa: BLE001 — closed for good or deleted: a new one from the picture
            pass
    a = catalogue.get(obj.plate_asset_id) if obj.plate_asset_id else None
    if a is None:
        raise ValueError("the set's picture is not in the Catalogue")
    with Image.open(catalogue.abs_path(a)) as im:
        base = np.asarray(im.convert("RGBA"))
    od = documents.create(f"{obj.name} · things", int(base.shape[1]), int(base.shape[0]), "transparent", a.id, base)
    store.edit_picture_set(st_id, set_id, lambda _st, o: setattr(o, "things_document_id", od.doc.id))
    return od


def keep_thing(store: StageStore, documents: Any, catalogue: Any, st_id: str, set_id: str, name: str,
               points: list[dict[str, int]]) -> tuple[Stage, SetThing, Any]:
    """The mask the last find left on the set's document, kept as a thing: a `mask` asset at the picture's size and the set's record."""
    _, obj = store.picture_set(st_id, set_id)
    if not obj.things_document_id:
        raise ValueError("find the thing on the picture first (a click on it)")
    od = documents.get(obj.things_document_id)
    sel = od.selection
    if sel is None or not (sel > 127).any():
        raise ValueError("nothing is found yet — click the thing on the picture")
    mask = np.where(sel > 127, 255, 0).astype(np.uint8)
    tmp = catalogue.ws.temp_dir / "things" / f"{new_id('msk')}.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, "L").save(tmp, "PNG")
    label = name.strip() or f"Thing {len(obj.things) + 1}"
    rec = catalogue.ingest_file(tmp, kind="mask", move=True, suite="stage", parents=[obj.plate_asset_id] if obj.plate_asset_id else [],
                                lineage_kind="set-thing", prompt_text=label,
                                params={"stage_id": st_id, "set_id": set_id, "thing": label, "points": points, "coverage": round(float(mask.mean() / 255), 4)})
    rec = catalogue.make_thumbs(rec)
    thing = SetThing(name=label, mask_asset_id=rec.id, points=points, relief_asset_id=obj.asset_id, floor_y=obj.floor_y)
    st = store.edit_picture_set(st_id, set_id, lambda _st, o: o.things.append(thing))
    return st, thing, rec


def rename_thing(store: StageStore, st_id: str, set_id: str, thing_id: str, name: str) -> Stage:
    if not name.strip():
        raise ValueError("a thing needs a name")

    def fn(_st: Stage, o: Any) -> None:
        t = next((t for t in o.things if t.id == thing_id), None)
        if t is None:
            raise KeyError(thing_id)
        t.name = name.strip()
    return store.edit_picture_set(st_id, set_id, fn)


def remove_thing(store: StageStore, st_id: str, set_id: str, thing_id: str) -> Stage:
    """The thing leaves the set's list (its mask stays in the Catalogue; a prop made of it stays on the stage)."""
    def fn(_st: Stage, o: Any) -> None:
        if not any(t.id == thing_id for t in o.things):
            raise KeyError(thing_id)
        o.things = [t for t in o.things if t.id != thing_id]
    return store.edit_picture_set(st_id, set_id, fn)


# ---- SC3c-3: make the things ------------------------------------------------------------------------------------------------------
def _mask(catalogue: Any, asset_id: str) -> np.ndarray:
    a = catalogue.get(asset_id)
    if a is None:
        raise ValueError(f"the mask {asset_id} is not in the Catalogue")
    with Image.open(catalogue.abs_path(a)) as im:
        return np.asarray(im.convert("L")) > 127


def union_mask(catalogue: Any, things: list[SetThing], grow: int = 0) -> np.ndarray:
    """Every thing's mask at once, grown by `grow` px (the plate is cleaned under it)."""
    out = None
    for t in things:
        m = _mask(catalogue, t.mask_asset_id)
        out = m if out is None else (out | m)
    if out is None:
        raise ValueError("no things to clean under")
    if grow > 0:
        out = np.asarray(Image.fromarray(np.where(out, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * grow + 1))) > 127
    return out


SHADOW_RATIO = 0.72                                # D124: a shadow is the surface at most this bright against the same surface lit around it
SHADOW_SIDE = 1.5                                  # D124 (E31): one side's dark this many times the other's tells where the light comes from
SHADOW_REACH = 0.9                                 # D124: how far a thing's shadow may reach from it, a share of the thing's width
SHADOW_SCALE = 640                                 # the search runs on the picture this wide (the masks come back at the picture's size)
SHADOW_CHROMA = 0.12                               # D124: a shadow keeps the colour of the surface it falls on, warmed by the light it bounces (the rig's block: 0.074 off the lit floor; the table against the wall: 0.40)


def _grow(m: np.ndarray, px: int) -> np.ndarray:
    """A mask grown by `px` (3×3 steps: a square reach, cheap at any size)."""
    img = Image.fromarray(np.where(m, 255, 0).astype(np.uint8))
    for _ in range(max(0, px)):
        img = img.filter(ImageFilter.MaxFilter(3))
    return np.asarray(img) > 127


def _box(a: np.ndarray, r: int) -> np.ndarray:
    """The mean over a (2r+1)² window (an integral image; the window shrinks at the edges)."""
    h, w = a.shape
    c = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    y0, y1 = np.clip(np.arange(h) - r, 0, h), np.clip(np.arange(h) + r + 1, 0, h)
    x0, x1 = np.clip(np.arange(w) - r, 0, w), np.clip(np.arange(w) + r + 1, 0, w)
    s = c[y1][:, x1] - c[y0][:, x1] - c[y1][:, x0] + c[y0][:, x0]
    return s / ((y1 - y0)[:, None] * (x1 - x0)[None, :])


def _reach(seed: np.ndarray, within: np.ndarray) -> np.ndarray:
    """Everything in `within` connected to `seed` (a morphological reconstruction by 3×3 steps)."""
    grown = seed & within
    while True:
        nxt = _grow(grown, 1) & within
        if (nxt == grown).all():
            return grown
        grown = nxt


def shadows_of(rgb: np.ndarray, masks: list[np.ndarray]) -> list[np.ndarray]:
    """D124: the shadow each picked thing casts in its picture — the surface beside it darker than the same surface lit around it (at
    most SHADOW_RATIO of the local level, the things left out of that level) and of its colour (within SHADOW_CHROMA of the local
    chromaticity: a dark thing of another colour is no shadow), grown out from the thing itself through such pixels and no farther than
    SHADOW_REACH of its width and never above its own top (a shadow lies below the thing that casts it, in a picture taken from above the
    floor); thin dark lines (the seams between boards) are no shadow, nor are a mask's stray specks seeds. **One light, one side** (E31): the things' shadows are weighed together, the dark beside
    each thing to its left against the dark to its right; when one side outweighs the other SHADOW_SIDE times, the parts on the lighter
    side are shade, not cast shadow (the corner under a window), and are dropped — the part under a thing always stays. One boolean mask
    per thing at the picture's size, without any of the things in it."""
    if not masks:
        return []
    H, W = masks[0].shape
    k = SHADOW_SCALE / W if W > SHADOW_SCALE else 1.0
    w, h = max(1, round(W * k)), max(1, round(H * k))
    small = lambda m: np.asarray(Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 127  # noqa: E731
    opened = lambda m, n: np.asarray(Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).filter(ImageFilter.MinFilter(n)).filter(ImageFilter.MaxFilter(n))) > 127  # noqa: E731
    lin = (np.asarray(Image.fromarray(rgb).resize((w, h), Image.BOX), np.float32) / 255.0)
    lin = np.where(lin <= 0.04045, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
    logy = np.log(np.maximum(1e-4, lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)))
    chroma = lin[..., :2] / np.maximum(1e-4, lin.sum(axis=2, keepdims=True))   # r and g of the linear chromaticity
    every_full = np.logical_or.reduce(masks)
    out = _grow(small(every_full), 2)
    r = max(4, w // 24)                                                          # the surface's own level: its mean around, the things out
    keep = (~out).astype(np.float32)
    norm = np.maximum(1e-3, _box(keep, r))
    level = np.maximum(_box(logy * keep, r) / norm, _box(logy * keep, 2 * r) / np.maximum(1e-3, _box(keep, 2 * r)))   # the brighter of two reaches:
    dark = level - logy                                                          # inside a wide shadow the near mean is the shadow itself
    tone = np.stack([_box(chroma[..., i] * keep, r) / norm for i in range(2)], axis=-1)
    cand = opened((dark > -np.log(SHADOW_RATIO)) & (np.abs(chroma - tone).max(axis=-1) < SHADOW_CHROMA) & ~out, 3)
    cols, rows = np.arange(w)[None, :], np.arange(h)[:, None]
    found: list[tuple[np.ndarray, np.ndarray, np.ndarray] | None] = []           # per thing: its region, the region's left and right parts
    weight = {"left": 0.0, "right": 0.0}
    for m in masks:
        thing = opened(small(m), 3)
        xs = np.nonzero(thing)[1]
        if not len(xs):
            found.append(None)
            continue
        x0, x1 = float(np.percentile(xs, 2)), float(np.percentile(xs, 98))    # robust: SAM's stray specks do not widen it
        top = float(np.percentile(np.nonzero(thing)[0], 2))
        zone = _grow(thing, int(np.clip(SHADOW_REACH * (x1 - x0 + 1), 6, w // 6))) & (rows >= top)
        region = _reach(_grow(thing, 4) & cand & zone, cand & zone)           # out from the thing (past the things' own 2 px) through the dark
        left, right = region & (cols < x0), region & (cols > x1)
        weight["left"] += float(dark[left].sum())
        weight["right"] += float(dark[right].sum())
        found.append((region, left, right))
    lit = None                                                                   # the side the light comes from: its parts are shade
    if weight["right"] > SHADOW_SIDE * weight["left"]:
        lit = "left"
    elif weight["left"] > SHADOW_SIDE * weight["right"]:
        lit = "right"
    res = []
    for f in found:
        if f is None or not f[0].any():
            res.append(np.zeros((H, W), bool))
            continue
        region, left, right = f
        if lit:
            region = region & ~(left if lit == "left" else right)
        big = np.asarray(Image.fromarray(np.where(_grow(region, 1), 255, 0).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
        res.append(big & ~every_full)
    return res


def cutout(catalogue: Any, plate_id: str, mask: np.ndarray, margin: float = 0.12) -> Path:
    """A thing alone on white, cropped around its mask with a margin — what Pixal3D's template cuts out again (BiRefNet) and models."""
    a = catalogue.get(plate_id)
    if a is None:
        raise ValueError("the set's picture is not in the Catalogue")
    with Image.open(catalogue.abs_path(a)) as im:
        rgb = np.asarray(im.convert("RGB"))
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("the thing's mask is empty")
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    pad = int(max(16, margin * max(x1 - x0, y1 - y0)))
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(rgb.shape[1], x1 + pad), min(rgb.shape[0], y1 + pad)
    out = np.full_like(rgb, 255)
    out[mask] = rgb[mask]
    path = catalogue.ws.temp_dir / "things" / f"{new_id('cut')}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out[y0:y1, x0:x1]).save(path, "PNG")
    return path


def shadow_masks(od: Any, catalogue: Any, todo: list[SetThing]) -> list[np.ndarray]:
    """D124: the shadows of the things to make, found together (one light, one side) on the set's document as the author sees it."""
    masks = [_mask(catalogue, t.mask_asset_id) for t in todo]
    rgb = np.ascontiguousarray(od.flatten()[..., :3])
    if any(m.shape != rgb.shape[:2] for m in masks):
        raise ValueError(f"the masks do not fit the set's document ({rgb.shape[1]}×{rgb.shape[0]})")
    return shadows_of(rgb, masks)


def things_shadows(store: StageStore, documents: Any, catalogue: Any, st_id: str, set_id: str) -> np.ndarray:
    """D124 (on a worker thread): the shadows *Make the things* would clean with the things not yet made, as one mask — what the things
    sheet shows before the Make. Empty when every thing is made."""
    _, obj = store.picture_set(st_id, set_id)
    todo = [t for t in obj.things if not t.mesh_asset_id]
    od = ensure_document(store, documents, catalogue, st_id, set_id)
    if not todo:
        return np.zeros((od.doc.h, od.doc.w), bool)
    return np.logical_or.reduce(shadow_masks(od, catalogue, todo))


def prepare_make(store: StageStore, documents: Any, catalogue: Any, st_id: str, set_id: str, variant: str) -> dict[str, Any]:
    """D123 (on a worker thread): the things not yet made — their union and (D124) their shadows, grown, as the set's document's
    selection (the region the Fill cleans) and each one's cut-out as a Catalogue image. The caller queues the jobs on the loop (the queue
    is not thread-safe)."""
    from .models import registry
    _, obj = store.picture_set(st_id, set_id)
    todo = [t for t in obj.things if not t.mesh_asset_id]
    if not todo:
        raise ValueError("every thing is made — pick a thing on the picture first")
    try:
        spec = registry.get(registry.default_model("mesh", variant))
    except ValueError:                                                              # no model makes meshes in this variant
        spec = None
    if spec is None or not registry.offered(spec, variant):
        raise ValueError(f"the things' 3D models need Pixal3D, which the {variant} variant does not carry (D17 / D26)")
    od = ensure_document(store, documents, catalogue, st_id, set_id)
    things = union_mask(catalogue, todo)
    if things.shape != (od.doc.h, od.doc.w):
        raise ValueError(f"the masks ({things.shape[1]}×{things.shape[0]}) do not fit the set's document ({od.doc.w}×{od.doc.h})")
    shadows = np.logical_or.reduce(shadow_masks(od, catalogue, todo))          # D124: the clean takes their shadows too
    union = np.asarray(Image.fromarray(np.where(things | shadows, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * CLEAN_GROW + 1))) > 127
    od.selection = np.where(union, 255, 0).astype(np.uint8)
    od.doc.has_selection = True
    od.dirty = True
    od.save()
    cutouts = []
    for t in todo:
        path = cutout(catalogue, obj.plate_asset_id, _mask(catalogue, t.mask_asset_id))
        rec = catalogue.ingest_file(path, kind="image", move=True, suite="stage", parents=[obj.plate_asset_id] if obj.plate_asset_id else [],
                                    lineage_kind="set-thing-cutout", prompt_text=t.name, params={"stage_id": st_id, "set_id": set_id, "thing_id": t.id})
        cutouts.append((t.id, catalogue.make_thumbs(rec)))
    return {"document_id": od.doc.id, "cutouts": cutouts, "coverage": round(float(union.mean()), 4), "shadows": round(float(shadows.mean()), 4)}


def clean_plate(q: Any, job: Any, od: Any) -> dict[str, Any]:
    """The Fill landed on the set's document (on a worker thread): its visible composite is the clean plate → a Catalogue image (lineage
    `clean-plate` ← the picture). The caller queues the relief's rebuild from it."""
    st_id, set_id = str(job.origin.ref or ""), str((job.origin.payload or {}).get("set_id") or "")
    _, obj = StageStore(q.ws).picture_set(st_id, set_id)
    merged = od.flatten()
    path = q.ws.temp_dir / "things" / f"{new_id('cln')}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(merged[..., :3]).save(path, "PNG")
    rec = q.catalogue.ingest_file(path, kind="image", move=True, job_id=job.id, suite="stage", parents=[obj.plate_asset_id] if obj.plate_asset_id else [],
                                  lineage_kind="clean-plate", params={"stage_id": st_id, "set_id": set_id, "things": [t.id for t in obj.things]}, origin=job.origin)
    return {"asset": q.catalogue.make_thumbs(rec), "stage_id": st_id, "set_id": set_id, "lens_deg": obj.lens_deg}


def model_bounds(glb: Path) -> tuple[np.ndarray, np.ndarray]:
    """A GLB's extent as the engine sees it: every vertex carried through its nodes' transforms (D109's upright turn is a node rotation, so
    the vertices alone would miss it; SC3d: the accessors' boxes turned would overstate it — a Pixal3D crate's 0.80 m width read 1.13) —
    the box the engine centres and stands on the floor (three's precise box)."""
    from .relief import accessor, glb_read
    from .tools.upright import quat_to_matrix
    doc, binary = glb_read(glb)
    nodes = doc.get("nodes", [])

    def local(nd: dict) -> np.ndarray:
        if "matrix" in nd:
            return np.asarray(nd["matrix"], float).reshape(4, 4).T                       # glTF matrices are column-major
        m = np.eye(4)
        r = quat_to_matrix(nd["rotation"]) if "rotation" in nd else np.eye(3)
        m[:3, :3] = r @ np.diag(nd.get("scale", [1.0, 1.0, 1.0]))
        m[:3, 3] = nd.get("translation", [0.0, 0.0, 0.0])
        return m

    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)

    def walk(i: int, parent: np.ndarray) -> None:
        nonlocal lo, hi
        nd = nodes[i]
        m = parent @ local(nd)
        if "mesh" in nd:
            for prim in doc["meshes"][nd["mesh"]].get("primitives", []):
                acc = doc["accessors"][prim["attributes"]["POSITION"]]
                if "bufferView" in acc:
                    v = accessor(doc, binary, prim["attributes"]["POSITION"])
                elif "min" in acc and "max" in acc:                              # compressed (no plain view): its box's corners
                    c0, c1 = acc["min"], acc["max"]
                    v = np.array([[x, y, z] for x in (c0[0], c1[0]) for y in (c0[1], c1[1]) for z in (c0[2], c1[2])], float)
                else:
                    continue
                if not len(v):
                    continue
                w = v @ m[:3, :3].T + m[:3, 3]
                lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
        for c in nd.get("children", []):
            walk(c, m)

    scene = doc.get("scenes", [{}])[doc.get("scene", 0)] if doc.get("scenes") else {"nodes": list(range(len(nodes)))}
    for i in scene.get("nodes", []):
        walk(i, np.eye(4))
    if not np.isfinite(lo).all():
        raise ValueError("the model has no extent")
    return lo, hi


def footprint(relief: Path, mask: np.ndarray, others: np.ndarray, floor_y: float | None) -> dict[str, float]:
    """E30's reading (D120): the thing's front edge on the relief — the mask's lowest rows' points in the picture's point map (the relief's
    vertices by their UVs), on the floor fitted to the picture's lowest rows outside every thing (`relief.floor_fit`, the plane the set is
    laid level by; a thing's own lowest pixels float a few centimetres), and the edge's width there. In the relief's frame (the picture
    camera at the origin looking down −Z)."""
    from .relief import floor_fit, glb_read, mesh_arrays
    doc, binary = glb_read(relief)
    pos, uv, _ = mesh_arrays(doc, binary)
    if uv is None:
        raise ValueError("the relief carries no UVs to find the thing on")
    H, W = mask.shape
    px = np.clip((uv[:, 0] * W).astype(int), 0, W - 1)
    py = np.clip((uv[:, 1] * H).astype(int), 0, H - 1)
    ok = np.isfinite(pos).all(axis=1)
    plane = floor_fit(pos, uv, keep=~others[py, px])                     # SC3d: the levelling's own fit, the things left out
    if plane:
        floor_at = lambda x, z: float(plane["a"] * x + plane["b"] * z + plane["c"])  # noqa: E731
    else:
        level = float(floor_y if floor_y is not None else np.percentile(pos[ok, 1], 2))
        floor_at = lambda x, z: level  # noqa: E731
    eroded = np.asarray(Image.fromarray(np.where(mask, 255, 0).astype(np.uint8)).filter(ImageFilter.MinFilter(7))) > 127
    inside = ok & eroded[py, px]
    if inside.sum() < 50:
        inside = ok & mask[py, px]
    if inside.sum() < 20:
        raise ValueError(f"only {int(inside.sum())} relief points under the thing — too small to stand it on the relief")
    p, rows = pos[inside], py[inside]
    bottom = rows >= np.percentile(rows, 92)
    fx, fz = float(np.median(p[bottom, 0])), float(np.median(p[bottom, 2]))
    fy = floor_at(fx, fz)
    width = float(np.percentile(p[bottom, 0], 95) - np.percentile(p[bottom, 0], 5))
    height = float(np.percentile(p[:, 1], 97)) - fy
    return {"x": fx, "y": fy, "z": fz, "width": max(0.05, width), "height": max(0.05, height), "points": int(inside.sum()), "floor": plane}


def carried(foot: dict[str, Any], dst: dict) -> dict[str, Any]:
    """SC3d: a footprint read on the relief the thing was picked on, carried to the set's relief as it is now (the clean plate's): one
    camera and one lens, so the two differ by MoGe's scale — the ratio of the camera's heights over their floors — and the edge lands on
    the new relief's floor. (Read on the clean plate's relief instead, the rows where the thing stood show what the Fill painted there —
    the floor behind it, or the foot of a wall — and the thing goes back: the rig's crate by 0.45 m.)"""
    from .relief import floor_height
    k = floor_height(dst) / floor_height(foot["floor"])
    x, z = foot["x"] * k, foot["z"] * k
    return foot | {"x": x, "y": dst["a"] * x + dst["b"] * z + dst["c"], "z": z, "width": foot["width"] * k, "height": foot["height"] * k,
                   "floor": dst, "carried": k}


def placement(foot: dict[str, float], lo: np.ndarray, hi: np.ndarray, floor_y: float | None, level: dict | None = None) -> dict[str, Any]:
    """The stage transform of the model: scaled to the front edge's width, its front at the edge, standing on the floor there. The engine
    centres a mesh on its own footprint and stands it on y = 0; the set is raised by −floor_y and (SC3d) laid level, so the front edge goes
    through the set's own transform (`relief.to_stage`); the turn is about x, so the stage's −z is still away from the picture camera."""
    from .relief import to_stage
    size = hi - lo
    s = foot["width"] / max(1e-6, float(size[0]))
    lift = -(floor_y if floor_y is not None else -1.0)
    edge = to_stage([foot["x"], foot["y"], foot["z"]], lift, level)
    return {"pos": [round(float(edge[0]), 4), round(float(edge[1]), 4), round(float(edge[2]) - float(size[2]) * s / 2, 4)], "rot": [0.0, 0.0, 0.0],
            "scale": [round(s, 4)] * 3}


def stand(catalogue: Any, obj: StageObject, t: SetThing, mesh_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """A thing's model on the stage: its footprint read on the relief it was picked on (its own front edge), carried to the set's relief
    as it is now (SC3d: the clean plate's, once the rebuild landed — MoGe reads one room at slightly different scales from the picture
    and its clean plate, and the prop stands in the frame of the set on the stage), then through the set's lift and levelling. Returns
    the footprint and the transform."""
    from .relief import floor_of_glb, levelling
    cur = catalogue.get(obj.asset_id) if obj.asset_id else None
    mesh = catalogue.get(mesh_id)
    if cur is None or mesh is None:
        raise ValueError("the set's relief, or the model, is not in the Catalogue")
    own = catalogue.get(t.relief_asset_id) if t.relief_asset_id and t.relief_asset_id != cur.id else None
    mask = _mask(catalogue, t.mask_asset_id)
    others = union_mask(catalogue, obj.things)
    cpath = catalogue.abs_path(cur)
    dst = floor_of_glb(cpath)
    foot = footprint(catalogue.abs_path(own), mask, others, t.floor_y) if own is not None else None
    if foot is not None and foot["floor"] and dst:
        foot = carried(foot, dst)
    else:                                                                   # picked on this relief, or a floor missing on either
        foot = footprint(cpath, mask, others, obj.floor_y)
    lift = -(obj.floor_y if obj.floor_y is not None else -1.0)
    level = levelling(dst, lift) if obj.level and dst else None             # the set's own levelling (the store's, from the same fit)
    lo, hi = model_bounds(catalogue.abs_path(mesh))
    return foot, placement(foot, lo, hi, obj.floor_y, level)


def model_landed(q: Any, job: Any, mesh_id: str) -> None:
    """A thing's Pixal3D model landed: stood where the thing stood (`stand`), a mesh on the stage, the thing marked made. Never the job's
    failure: the model stays in the Catalogue and the library either way."""
    st_id, payload = str(job.origin.ref or ""), job.origin.payload or {}
    set_id, thing_id = str(payload.get("set_id") or ""), str(payload.get("thing_id") or "")
    store = StageStore(q.ws)
    try:
        _, obj = store.picture_set(st_id, set_id)
        t = next((x for x in obj.things if x.id == thing_id), None)
        if t is None:
            raise KeyError(thing_id)
        foot, tf = stand(q.catalogue, obj, t, mesh_id)
        oid = new_id("msh")

        def fn(st: Any, o: Any) -> None:
            st.objects.append(StageObject(id=oid, kind="mesh", name=t.name, asset_id=mesh_id, transform=tf, colour_id=(len(st.objects) % 12) + 1))
            for x in o.things:
                if x.id == thing_id:
                    x.mesh_asset_id, x.object_id = mesh_id, oid
        st = store.edit_picture_set(st_id, set_id, fn)
        job.result.update({"stage_id": st_id, "object_id": oid, "footprint": {k: round(v, 3) for k, v in foot.items() if isinstance(v, (int, float))},
                           "transform": tf})
        job.log_tail.append(f"{t.name} stood on the relief at x {foot['x']:.2f} z {foot['z']:.2f} (the floor {foot['y']:.2f}), {foot['width']:.2f} m wide, "
                            f"scale {tf['scale'][0]}" + (f" (read where it was picked, carried ×{foot['carried']:.3f})" if "carried" in foot else ""))
        q.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the model was not placed on the stage: {e}")
        q.hub.broadcast("stage.updated", {"id": st_id, "revision": 0, "error": f"{e}"})
