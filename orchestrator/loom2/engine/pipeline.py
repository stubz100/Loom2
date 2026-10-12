"""D64 (ArtCraft P2): a recipe runs as plan → finalize → submit.

- `plan(recipe, variant, history)` is pure — no I/O, no engine: the effective parameters, what the job needs (references, a
  document region, video frames), the weights it loads, the warm group, the VRAM and time estimates. `/recipes/preview` returns it
  for every kind; the queue's admission reads the same numbers.
- `finalize(job, recipe, q)` does the I/O: references fitted and uploaded, the document region cropped and uploaded, the i2v frames
  uploaded, a fresh object_info, then the compile and its contract check. It raises `JobCancelled` between steps when a cancel arrived.
- `preview_problems(recipe, roster, object_info, variant)` compiles with placeholder inputs against the engine's last object_info, so
  the panel shows contract problems (a missing node, a weight the engine cannot see) before anything is submitted.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from .. import native
from ..documents import RasterLayer
from ..edit_ai import RegionPlan, crop_inputs, dilate, layer_plan, outpaint_inputs, outpaint_plan, plan_region, whole_plan
from ..recipes import I2I, I2V, T2I, Inpaint, Reangle, Segment, Upscale, reangle_method, reangle_model_id, warm_group
from ..models import registry
from ..roster import Roster
from .graphs import (kept_refs, CompileError, Compiled, compile_recipe, doc_estimate_seconds, effective_params, estimate_i2v_seconds, estimate_seconds,
                     estimate_vram_gb, i2v_params, reangle_prompt, recipe_weights)

if TYPE_CHECKING:
    from ..queue import JobQueue, JobRecord

AnyRecipe = T2I | I2I | Inpaint | Upscale | Segment | I2V
DOCUMENT_KINDS = (Inpaint, I2I, Upscale, Segment)


class JobCancelled(Exception):
    """A cancel arrived while the job was preparing (engine start, uploads, region crop) — B5."""


# ---- plan (pure) ------------------------------------------------------------------------------------------------------------------
@dataclass
class Plan:
    kind: str
    model_id: str | None
    engine: bool                          # False: runs on the CPU, the engine is never started (Quick Remove)
    warm_group: str
    vram_gb: float
    estimate: dict[str, Any]              # {seconds, source} per image / clip / candidate
    params: dict[str, Any]                # effective parameters (t2i, i2v) or the recipe's settings that shape the run
    needs: list[str]                      # "refs" · "document" · "frames"
    weights: list[str]                    # every roster id it loads (the open-variant gate, the missing-weights list)
    count: int                            # jobs one submission makes (one per seed)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan(recipe: AnyRecipe, variant: str = "full", history: list[dict] | None = None) -> Plan:
    """Raises CompileError for parameters no graph accepts (an unsupported size, a beat past the clip)."""
    quick = isinstance(recipe, Inpaint) and recipe.mode == "quick_remove"
    needs: list[str] = []
    if getattr(recipe, "refs", None):
        needs.append("refs")
    if isinstance(recipe, DOCUMENT_KINDS):
        needs.append("document")
    if isinstance(recipe, I2V):
        needs.append("frames")
    if isinstance(recipe, Reangle):
        needs.append("source")
    if isinstance(recipe, T2I):
        params = effective_params(recipe)
        est = estimate_seconds(recipe, history)
    elif isinstance(recipe, I2V):
        params = i2v_params(recipe)
        est = estimate_i2v_seconds(recipe)
    elif isinstance(recipe, Reangle):                                 # P14 (D82): the method `auto` resolved to in this build, and its measured time
        try:
            mid = reangle_model_id(recipe, variant)
        except ValueError as e:
            raise CompileError(str(e)) from e
        spec = registry.get(mid)
        params = {"move": recipe.move, "method": reangle_method(recipe, variant), "model_id": mid, "prompt": reangle_prompt(recipe, variant),
                  "label": spec.label if spec else mid}
        est = {"seconds": spec.estimates.base_seconds if spec else None, "source": "baseline (E12 2026-10-12, warm)"}
    else:
        keep = ("mode", "model_id", "source", "strength", "margin_pct", "min_size", "feather", "expand", "blend", "refine", "refine_model_id", "as_layer", "op", "max_size")
        params = {k: v for k, v in recipe.model_dump().items() if k in keep}
        est = doc_estimate_seconds(recipe, variant)
    return Plan(kind=recipe.kind, model_id=None if quick else getattr(recipe, "model_id", None), engine=not quick,
                warm_group=warm_group(recipe, variant), vram_gb=estimate_vram_gb(recipe, variant), estimate=est, params=params, needs=needs,
                weights=recipe_weights(recipe, variant), count=len(getattr(recipe, "seeds", None) or [0]))


def _placeholder_image(object_info: dict) -> str:
    """An image name the engine already lists (its LoadImage enum), so the preview's compile passes the enum check."""
    try:
        names = list(object_info["LoadImage"]["input"]["required"]["image"][0])
    except (KeyError, IndexError, TypeError):
        names = []
    return names[0] if names else "loom2-preview.png"


def placeholder_inputs(recipe: AnyRecipe, object_info: dict) -> dict[str, Any]:
    """Inputs shaped like finalize()'s for the preview's compile."""
    img = _placeholder_image(object_info)
    if isinstance(recipe, I2V):
        return {"start": img, "end": img if recipe.end_asset else None, "beats": {b.asset_id: img for b in recipe.beats}}
    if isinstance(recipe, DOCUMENT_KINDS):
        return {"image": img, "mask": img, "w": 1024, "h": 576, "points": [], "box": None}
    if isinstance(recipe, Reangle):
        return {"image": img, "w": 1024, "h": 576}
    return {}


def preview_problems(recipe: AnyRecipe, roster: Roster, object_info: dict | None, variant: str = "full") -> list[str] | None:
    """The contract problems a submission would hit, or None before the engine has answered once (no object_info to check against)."""
    if not object_info:
        return None
    if isinstance(recipe, Inpaint) and recipe.mode == "quick_remove":
        return []
    img = _placeholder_image(object_info)
    refs = {(r.asset_id or r.blob or ""): img for r in getattr(recipe, "refs", []) or []}
    try:
        c = compile_recipe(recipe, roster, object_info, 1, "loom2/preview", ref_files=refs or None, inputs=placeholder_inputs(recipe, object_info) or None,
                           variant=variant)
    except (CompileError, KeyError, ValueError) as e:
        return [str(e)]
    return c.problems


# ---- finalize (I/O) ---------------------------------------------------------------------------------------------------------------
@dataclass
class Submission:
    compiled: Compiled
    inputs: dict[str, Any] = field(default_factory=dict)     # the document region plan, the uploaded names, the alpha / context arrays


async def finalize(job: JobRecord, recipe: AnyRecipe, q: JobQueue) -> Submission:
    """Everything between a started engine and a graph ready to queue. Raises JobCancelled, ValueError (a missing reference, an
    empty selection) or CompileError."""
    object_info = await q.object_info_fresh()
    ref_files: dict[str, str] = {}
    refs = getattr(recipe, "refs", []) or []
    if isinstance(recipe, T2I) and (spec := registry.get(recipe.model_id)):
        refs = kept_refs(recipe, spec)                                 # D73: references over the model's limit are not uploaded (preview says so)
    for ref in refs:
        key = ref.asset_id or ref.blob or ""
        src = None
        if ref.asset_id:
            a = q.catalogue.get(ref.asset_id)
            src = q.catalogue.abs_path(a) if a else None
        elif ref.blob:
            src = q.ws.temp_dir / "blobs" / ref.blob
        if not src or not Path(src).is_file():
            raise ValueError(f"reference image {key} is missing")
        fitted = await asyncio.to_thread(fit_reference, q, Path(src), int(getattr(recipe, "ref_max_px", 0) or 0), key)
        ref_files[key] = await q.engine.client.upload_image(fitted)   # top level: LoadImage's enum ignores sub-folders
    if ref_files:                                                      # uploaded names appear in LoadImage's enum only after a refresh (E8)
        object_info = await q.object_info_refresh()
    q.check_cancel(job)
    inputs: dict[str, Any] = {}
    if isinstance(recipe, DOCUMENT_KINDS):                             # M5: crops of the document go in through /upload/image
        q.progress(job, "preparing region")
        inputs = await prepare_document(job, recipe, q)
        object_info = await q.object_info_refresh()
        q.check_cancel(job)
    if isinstance(recipe, I2V):                                        # M6: start / end / beat frames go in through /upload/image
        q.progress(job, "uploading frames")
        inputs = await prepare_i2v(job, recipe, q)
        object_info = await q.object_info_refresh()
        q.check_cancel(job)
    if isinstance(recipe, Reangle):                                    # P14: the source asset goes in through /upload/image
        q.progress(job, "uploading source")
        inputs = await prepare_reangle(job, recipe, q)
        object_info = await q.object_info_refresh()
        q.check_cancel(job)
    compiled = compile_recipe(recipe, q.roster, object_info, job.seed, out_prefix=f"loom2/{job.id}", ref_files=ref_files, inputs=inputs or None,
                              variant=q.app.settings.variant)
    return Submission(compiled=compiled, inputs=inputs)


def fit_reference(q: JobQueue, src: Path, max_px: int, key: str) -> Path:
    """References are downscaled to ≤ max_px² before upload (09 §3d); PNG so the engine's LoadImage is exact."""
    out_dir = q.ws.temp_dir / "refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"loom2ref-{key[:24]}.png"                         # unique in the engine's input dir
    with Image.open(src) as im:
        im = im.convert("RGB")
        if max_px and (im.width > max_px or im.height > max_px):
            im.thumbnail((max_px, max_px), Image.LANCZOS)
        im.save(out, "PNG")
    return out


# ---- M5 document jobs (10 §4, D7): the region in ----------------------------------------------------------------------------------
async def prepare_document(job: JobRecord, recipe: Inpaint | I2I | Upscale | Segment, q: JobQueue) -> dict[str, Any]:
    """Crop/scale the document's composite (and mask) for the engine, upload them and keep the plan (edit_ai)."""
    if q.documents is None:
        raise ValueError("documents are not available (no project open)")
    od = await asyncio.to_thread(q.documents.get, recipe.document_id)
    tmp = q.ws.temp_dir / "ai" / job.id
    tmp.mkdir(parents=True, exist_ok=True)
    # B3: candidates of one batch are alternatives — the engine must not see the candidate layers already pasted back
    exclude = {f"grp_{job.batch_id or job.id}"}

    def work() -> dict[str, Any]:
        comp = od.flatten(exclude=exclude)
        out: dict[str, Any] = {}
        if isinstance(recipe, Inpaint):
            if recipe.mode == "outpaint":
                plan = outpaint_plan(od.doc.w, od.doc.h, recipe.outpaint or {}, max_pixels=recipe.max_pixels)
                if plan.w == od.doc.w and plan.h == od.doc.h:
                    raise ValueError("outpaint needs at least one side to grow")
                img, msk, strips = outpaint_inputs(comp, plan)
                out["alpha_mask"] = strips
            else:
                sel = od.selection
                if sel is None or not sel.any():
                    raise ValueError("inpaint needs a selection (the region to repaint)")
                mask = dilate(sel, recipe.expand) if recipe.expand else sel
                plan = plan_region(mask, od.doc.w, od.doc.h, recipe.margin_pct, recipe.min_size, max_pixels=recipe.max_pixels)
                if plan is None:
                    raise ValueError("the selection is empty")
                img, msk = crop_inputs(comp, mask, plan)
                if recipe.mode == "remove" and recipe.prefill:      # D62: the hole content-aware filled before the engine sees it
                    if not native.available():
                        raise ValueError("the content-aware pre-fill needs the native extension (uv sync --project orchestrator --extra native)")
                    img = native.content_aware_fill(img, np.asarray(msk) > 127, seed=job.seed or 1)
                    job.log_tail.append("hole pre-filled by content-aware fill (CPU)")
                out["alpha_mask"] = mask
                out["context"] = np.ascontiguousarray(comp[plan.y:plan.y + plan.h, plan.x:plan.x + plan.w, :3])   # D47 / D48: the plate
            Image.fromarray(img, "RGB").save(tmp / "image.png")
            Image.fromarray(msk, "L").save(tmp / "mask.png")          # type: ignore[arg-type]
            out["mask_path"] = tmp / "mask.png"
        elif isinstance(recipe, Segment):
            # AI Select reads the whole visible composite at ≤ max_size; prompts are scaled into engine pixels
            plan = whole_plan(od.doc.w, od.doc.h, max_size=recipe.max_size)
            img, _ = crop_inputs(comp, None, plan)
            sx, sy = plan.ew / od.doc.w, plan.eh / od.doc.h
            out["points"] = [{"x": int(round(p["x"] * sx)), "y": int(round(p["y"] * sy)), "label": int(p.get("label", 1))} for p in recipe.points]
            out["box"] = [int(round(recipe.box[0] * sx)), int(round(recipe.box[1] * sy)), int(round(recipe.box[2] * sx)), int(round(recipe.box[3] * sy))] if recipe.box else None
            out["alpha_mask"] = None
            Image.fromarray(img, "RGB").save(tmp / "image.png")
        elif isinstance(recipe, I2I):
            if recipe.source == "active":
                node = od.doc.find(recipe.layer_id or "")
                px = od.pixels.get(recipe.layer_id or "")
                if node is None or px is None or not isinstance(node, RasterLayer):
                    raise ValueError("refine on the active layer needs a raster layer with pixels")
                plan = layer_plan(node.x, node.y, int(px.shape[1]), int(px.shape[0]))
                img = np.ascontiguousarray(px[..., :3])
                if (plan.ew, plan.eh) != (plan.w, plan.h):
                    img = np.asarray(Image.fromarray(img).resize((plan.ew, plan.eh), Image.Resampling.LANCZOS))
                out["alpha_mask"] = np.ascontiguousarray(px[..., 3])
                out["context"] = np.ascontiguousarray(px[..., :3])                # D48: the layer as it was
            elif recipe.source == "selection":
                sel = od.selection
                if sel is None or not sel.any():
                    raise ValueError("refine on the selection needs a selection")
                plan = plan_region(sel, od.doc.w, od.doc.h, recipe.margin_pct, 0)
                if plan is None:
                    raise ValueError("the selection is empty")
                img, _ = crop_inputs(comp, None, plan)
                out["alpha_mask"] = sel
                out["context"] = np.ascontiguousarray(comp[plan.y:plan.y + plan.h, plan.x:plan.x + plan.w, :3])
            else:
                plan = whole_plan(od.doc.w, od.doc.h)
                img, _ = crop_inputs(comp, None, plan)
                out["alpha_mask"] = None
                out["context"] = np.ascontiguousarray(comp[..., :3])
            Image.fromarray(img, "RGB").save(tmp / "image.png")
        else:
            if recipe.source == "active":
                node = od.doc.find(recipe.layer_id or "")
                px = od.pixels.get(recipe.layer_id or "")
                if node is None or px is None or not isinstance(node, RasterLayer):
                    raise ValueError("upscale of the active layer needs a raster layer with pixels")
                plan = layer_plan(node.x, node.y, int(px.shape[1]), int(px.shape[0]), max_size=0)
                Image.fromarray(px, "RGBA").save(tmp / "image.png")
                out["alpha_mask"] = np.ascontiguousarray(px[..., 3])         # C4: the engine returns RGB; the layer keeps its alpha
            else:
                plan = whole_plan(od.doc.w, od.doc.h, max_size=0)
                Image.fromarray(comp, "RGBA").save(tmp / "image.png")
                out["alpha_mask"] = np.ascontiguousarray(comp[..., 3])
        out["plan"] = plan
        out["image_path"] = tmp / "image.png"
        return out

    inputs = await asyncio.wait_for(asyncio.to_thread(work), 300.0)      # B4: region preparation is bounded too
    plan: RegionPlan = inputs["plan"]
    inputs["image"] = await q.engine.client.upload_image(inputs["image_path"])
    if inputs.get("mask_path"):
        inputs["mask"] = await q.engine.client.upload_image(inputs["mask_path"])
    inputs["w"], inputs["h"] = plan.ew, plan.eh
    job.result["region"] = plan.to_dict()
    job.log_tail.append(f"region {plan.w}×{plan.h} at {plan.x},{plan.y} → engine {plan.ew}×{plan.eh} (×{plan.scale:.2f})")
    return inputs


# ---- M6 video jobs (11 §10): the frames in ----------------------------------------------------------------------------------------
async def prepare_reangle(job: JobRecord, recipe: Reangle, q: JobQueue) -> dict[str, Any]:
    """Upload the source asset as PNG (≤ 2048 px, the angles graph scales to 1 MP itself) and report its size for Klein's output latent."""
    a = q.catalogue.get(recipe.asset_id)
    src = q.catalogue.abs_path(a) if a else None
    if not src or not Path(src).is_file():
        raise ValueError(f"the source image ({recipe.asset_id}) is missing from the Catalogue")
    fitted = await asyncio.to_thread(fit_reference, q, Path(src), 2048, f"angle-{recipe.asset_id}")
    with Image.open(fitted) as im:
        w, h = im.size
    name = await q.engine.client.upload_image(fitted)
    job.log_tail.append(f"source uploaded: {w}×{h}, move {recipe.move}, method {reangle_method(recipe, q.app.settings.variant)}")
    return {"image": name, "w": w, "h": h}


async def prepare_i2v(job: JobRecord, recipe: I2V, q: JobQueue) -> dict[str, Any]:
    """Upload the start, end and beat frames as PNG (the graph's ImageScale fits them to the clip size)."""
    names: dict[str, Any] = {"beats": {}}

    async def up(asset_id: str, what: str) -> str:
        a = q.catalogue.get(asset_id)
        src = q.catalogue.abs_path(a) if a else None
        if not src or not Path(src).is_file():
            raise ValueError(f"the {what} frame ({asset_id}) is missing from the Catalogue")
        fitted = await asyncio.to_thread(fit_reference, q, Path(src), 0, f"i2v-{asset_id}")
        return await q.engine.client.upload_image(fitted)

    names["start"] = await up(recipe.start_asset, "start")
    names["end"] = await up(recipe.end_asset, "end") if recipe.end_asset else None
    for b in recipe.beats:
        names["beats"][b.asset_id] = await up(b.asset_id, f"beat {b.frame}")
    job.log_tail.append("frames uploaded: start" + (", end" if names["end"] else "") + (f", {len(recipe.beats)} beat(s)" if recipe.beats else ""))
    return names


def wall_since(t0: float) -> float:
    return round(time.time() - t0, 1)
