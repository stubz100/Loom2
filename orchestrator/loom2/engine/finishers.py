"""D64 (ArtCraft P2): what happens to an engine's outputs, one finisher per kind of result, behind one interface:

    finisher_for(recipe).finish(job, recipe, files, submission, q)

- AssetFinisher — Generate: the files become Catalogue assets (with thumbnails).
- DocumentFinisher — Edit: the result is pasted back as a candidate layer (inpaint, outpaint, refine) or ingested (upscale).
- SelectionFinisher — Edit · AI Select: the engine's mask joins the document's selection.
- ClipFinisher — Animate: the frames become a clip master, a proxy and its Catalogue asset.

`run_quick_remove` is the one job without an engine (D62): it plans, fills on the CPU and pastes back through the same layer code.
The queue's single completion tail (`JobQueue._complete`) runs after any of them.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from PIL import Image

from .. import matting, native
from ..clips import ClipStore, compute_identity
from ..documents import GroupLayer, RasterLayer
from ..edit_ai import RegionPlan, assemble_layer, combine_selection, dilate, mask_from_engine, plan_region
from ..fsio import StateError, new_id
from ..models import registry
from ..recipes import I2I, I2V, ImageToMesh, Inpaint, Reangle, Render, Segment, StageShot, Upscale, stage_model_id
from ..roster import ROSTER_BY_ID
from ..timelines import TimelineStore, at, duration, starts
from ..tools import facesim
from .pipeline import AnyRecipe, Submission


def _parents(recipe: Any) -> list[str]:
    """Lineage: the reference images the job used — the kept ones only (D73: those over the model's limit never reached the engine);
    a new angle's parent is its source (P14); a stage shot's are the pass it took as image 1 and the references that followed (ST3)."""
    if isinstance(recipe, Reangle):
        return [recipe.asset_id]
    if isinstance(recipe, StageShot):
        from .graphs import stage_pass_for, stage_refs
        spec = registry.get(stage_model_id(recipe))
        used = [recipe.passes[k] for k in (stage_pass_for(recipe.method),) if recipe.passes.get(k)]
        return used + [r.asset_id for r in (stage_refs(recipe, spec) if spec else recipe.refs) if r.asset_id]
    refs = getattr(recipe, "refs", []) or []
    spec = registry.get(getattr(recipe, "model_id", "") or "")
    if spec is not None:
        refs = refs[: spec.inputs.refs_max]
    return [r.asset_id for r in refs if getattr(r, "asset_id", None)]

if TYPE_CHECKING:
    from ..queue import JobQueue, JobRecord


def output_path(q: JobQueue, f: dict) -> Path:
    base = q.app.state_dir / "engine_out"
    return base / f["subfolder"] / f["filename"] if f["subfolder"] else base / f["filename"]


class Finisher(Protocol):
    frees_cache: bool                    # drop ComfyUI's cached outputs after this job (document and video jobs)

    async def finish(self, job: JobRecord, recipe: Any, files: list[dict], sub: Submission, q: JobQueue) -> None: ...


class AssetFinisher:
    frees_cache = False

    async def finish(self, job: JobRecord, recipe: Any, files: list[dict], sub: Submission, q: JobQueue) -> None:
        compiled = sub.compiled
        assets = []
        for f in files:
            src = output_path(q, f)
            if not src.is_file():
                job.log_tail.append(f"missing output {src}")
                continue
            payload = (job.origin.payload or {}) if job.origin else {}
            extra = {"coverage_cell": payload["cell"]} if isinstance(payload.get("cell"), dict) else {}        # 17 §3b: the cell an Expand job filled
            rec = await asyncio.to_thread(
                q.catalogue.ingest_file, src, kind="video" if src.suffix.lower() in (".mp4", ".webm", ".mov") else "image", move=True,
                job_id=job.id, batch_id=job.batch_id, suite="stage" if isinstance(recipe, StageShot) else "story" if job.origin and job.origin.suite == "story" else "generate",
                model_id=compiled.summary.get("model_id", getattr(recipe, "model_id", None)), seed=job.seed,
                prompt_text=compiled.serialized_prompt or getattr(recipe, "prompt_text", None), prompt_json=getattr(recipe, "prompt_json", None),
                params=compiled.summary | {"recipe": recipe.model_dump()} | extra, timings={"wall_s": q.wall_s(), "node_s": job.node_times},
                compiled_graph_hash=compiled.graph_hash, variant=job.variant, parents=_parents(recipe),
                origin=job.origin, **({"lineage_kind": "reangle"} if isinstance(recipe, Reangle) else {"lineage_kind": "stage-shot"} if isinstance(recipe, StageShot) else {}))
            assets.append(rec)
            q.hub.broadcast("asset.created", rec.model_dump())
        job.progress_text = "thumbnails"
        for i, rec in enumerate(assets):
            assets[i] = await asyncio.to_thread(q.catalogue.make_thumbs, rec)
            q.hub.broadcast("asset.updated", assets[i].model_dump())
        job.result["asset_ids"] = [a.id for a in assets]
        place = (job.origin.payload or {}).get("group_id") if job.origin else None          # 17 §3b: an Expand's candidates land on the version's page
        if assets and isinstance(place, str) and q.groups is not None and place in q.groups.groups:
            try:
                await asyncio.to_thread(q.groups.move, [("asset", a.id) for a in assets], place)
                q.hub.broadcast("group.changed", {"ids": [place]})
            except Exception as e:                                                          # a locked or deleted page: the results stay in Unprocessed
                job.log_tail.append(f"results not placed on {place}: {e}")


class SelectionFinisher:
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: Segment, files: list[dict], sub: Submission, q: JobQueue) -> None:
        """The mask image → a document-sized selection, joined with the current one per `op`; saved so the ORA keeps it."""
        assert q.documents is not None
        src = output_path(q, files[0])
        if not src.is_file():
            raise ValueError(f"missing output {src}")
        od = await asyncio.to_thread(q.documents.get, recipe.document_id)
        q.progress(job, "paste-back")
        arr = await asyncio.to_thread(lambda: np.asarray(Image.open(src).convert("RGBA")))

        def apply() -> float:
            m = mask_from_engine(arr[..., 0], od.doc.w, od.doc.h, recipe.expand, recipe.feather)
            od.selection = combine_selection(od.selection, m, recipe.op)
            if recipe.edge_refine is not None:                       # D45: soft, image-aware edges against the visible composite
                od.selection = matting.refine(od.selection, od.flatten(), matting.params_from(recipe.edge_refine))
            od.doc.has_selection = True
            od.dirty = True
            od.save()
            return float(od.selection.mean() / 255.0)
        coverage = await asyncio.to_thread(apply)
        job.result["selection"] = {"w": od.doc.w, "h": od.doc.h, "coverage": round(coverage, 4), "op": recipe.op}
        job.log_tail.append(f"selection {recipe.op}: {coverage * 100:.1f} % of the canvas")
        q.hub.broadcast("document.changed", {"id": od.doc.id, "job_id": job.id, "selection": True, "coverage": round(coverage, 4)})


class DocumentFinisher:
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: Inpaint | I2I | Upscale, files: list[dict], sub: Submission, q: JobQueue) -> None:
        """Paste the engine result back as a new layer (or a Catalogue asset for upscale)."""
        assert q.documents is not None
        inputs = sub.inputs
        src = output_path(q, files[0])
        if not src.is_file():
            raise ValueError(f"missing output {src}")
        od = await asyncio.to_thread(q.documents.get, recipe.document_id)
        plan: RegionPlan = inputs["plan"]
        q.progress(job, "paste-back")
        arr = await asyncio.to_thread(lambda: np.asarray(Image.open(src).convert("RGBA")))
        if isinstance(recipe, Upscale):
            parents = [od.doc.source_asset_id] if od.doc.source_asset_id else []
            rec = await asyncio.to_thread(q.catalogue.ingest_file, src, kind="image", move=True, job_id=job.id, batch_id=job.batch_id, suite="edit",
                                          model_id=recipe.model_id, seed=job.seed, params={"recipe": recipe.model_dump(), "document_id": od.doc.id},
                                          timings={"wall_s": q.wall_s(), "node_s": job.node_times}, parents=parents, origin=job.origin)
            rec = await asyncio.to_thread(q.catalogue.make_thumbs, rec)
            q.hub.broadcast("asset.created", rec.model_dump())
            job.result["asset_ids"] = [rec.id]
            if recipe.as_layer:
                factor = max(1, round(arr.shape[1] / max(1, plan.w)))
                rgba = assemble_layer(arr, plan, inputs.get("alpha_mask"), 0)     # C4: back to 1× with the source's alpha
                await add_result_layer(q, job, od, recipe, rgba, plan.x, plan.y, f"upscale ×{factor} at 1×")
            return
        if isinstance(recipe, Inpaint) and recipe.mode == "outpaint":
            p = plan.pad or {}
            left, top = int(p.get("left", 0)), int(p.get("top", 0))
            job.result["shift"] = {"left": left, "top": top}          # C20: the editor shifts its own layers the same way
            for n in od.doc.walk():
                if isinstance(n, RasterLayer):
                    n.x += left; n.y += top
                if n.mask is not None and not n.mask.linked:
                    n.mask.x += left; n.mask.y += top
            old_w, old_h = od.doc.w, od.doc.h
            od.doc.w, od.doc.h = plan.w, plan.h
            if od.selection is not None:
                od.selection = np.pad(od.selection, ((top, plan.h - old_h - top), (left, plan.w - old_w - left)))
            rgba = assemble_layer(arr, plan, inputs.get("alpha_mask"), recipe.feather)
            await add_result_layer(q, job, od, recipe, rgba, 0, 0, "outpaint", as_mask=True)
            return
        feather_px = recipe.feather if isinstance(recipe, Inpaint) or recipe.source == "selection" else 0
        if isinstance(recipe, Inpaint):
            rgba = await asyncio.to_thread(assemble_layer, arr, plan, inputs.get("alpha_mask"), feather_px, inputs.get("context"), recipe.blend)
        else:
            rgba = await asyncio.to_thread(assemble_layer, arr, plan, inputs.get("alpha_mask"), feather_px, inputs.get("context"), "feather",
                                           recipe.match_colour, "ring" if recipe.source == "selection" else "all")
        label = recipe.mode.replace("_", " ") if isinstance(recipe, Inpaint) else f"refine {recipe.strength:.2f}"
        # D47: a paste-back's soft edge is a layer mask (repaintable); a refine of a whole layer keeps the layer's own alpha
        await add_result_layer(q, job, od, recipe, rgba, plan.x, plan.y, label, as_mask=isinstance(recipe, Inpaint) or recipe.source == "selection")


async def add_result_layer(q: Any, job: Any, od: Any, recipe: Inpaint | I2I | Upscale, rgba: np.ndarray, x: int, y: int, label: str, as_mask: bool = False) -> None:
    """Candidates of one batch share a group at the top of the stack; only the first is visible (10 §4 variant strip). With
    `as_mask` (D47) the alpha becomes a linked layer mask over opaque pixels, so the paste-back edge can be repainted."""
    gid = f"grp_{job.batch_id or job.id}"
    group = od.doc.find(gid)
    if not isinstance(group, GroupLayer):
        prompt = str(getattr(recipe, "prompt_text", "") or "")
        group = GroupLayer(id=gid, name=f"AI {label}" + (f": {prompt[:28]}" if prompt else ""), passthrough=True)
        od.doc.layers.insert(0, group)
    n = len(group.children) + 1
    lid = new_id("lyr")
    multi = len(getattr(recipe, "seeds", [0])) > 1
    layer = RasterLayer(id=lid, name=f"candidate {n}" if multi else label, x=int(x), y=int(y), w=int(rgba.shape[1]), h=int(rgba.shape[0]), visible=(n == 1),
                        recipe={**recipe.model_dump(), "seed": job.seed, "job_id": job.id, "batch_id": job.batch_id, "region": job.result.get("region")},
                        lineage_asset_id=od.doc.source_asset_id)
    group.children.append(layer)
    if as_mask:
        mask = np.ascontiguousarray(rgba[..., 3])
        rgba = rgba.copy()
        rgba[..., 3] = 255
        od.set_pixels(lid, np.ascontiguousarray(rgba))
        od.set_mask(lid, mask)
    else:
        od.set_pixels(lid, np.ascontiguousarray(rgba))
    od.dirty = True
    od.doc.revision += 1                                 # C1: a client stack based on the previous revision is now stale
    await asyncio.to_thread(od.save)
    job.result.setdefault("layers", []).append(lid)
    job.result["group"] = gid
    q.hub.broadcast("document.changed", {"id": od.doc.id, "job_id": job.id, "batch_id": job.batch_id, "added": [lid], "group": gid, "w": od.doc.w, "h": od.doc.h, "candidate": n,
                                         "shift": job.result.get("shift"), "revision": od.doc.revision})


class ClipFinisher:
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: I2V, files: list[dict], sub: Submission, q: JobQueue) -> None:
        """The decoded frames become `clips/<id>/master`, the proxy is encoded, and the proxy is the Catalogue asset."""
        compiled = sub.compiled
        paths = [p for p in (output_path(q, f) for f in sorted(files, key=lambda x: x["filename"])) if p.is_file()]
        if not paths:
            raise ValueError("the engine produced no frames")
        clips = ClipStore(q.ws)
        ep = compiled.summary
        q.progress(job, "writing the master")
        rec = await asyncio.to_thread(clips.create, paths, job_id=job.id, batch_id=job.batch_id, model_id=recipe.model_id, preset=recipe.preset, prompt=recipe.prompt_text,
                                      seed=job.seed, fps=int(ep.get("fps", recipe.fps)), start_asset_id=recipe.start_asset, end_asset_id=recipe.end_asset,
                                      beats=[b.model_dump() for b in recipe.beats], params={"recipe": recipe.model_dump(), "compiled": ep | {"graph_hash": compiled.graph_hash}},
                                      timings={"engine_wall_s": q.wall_s(), "node_s": job.node_times})
        q.progress(job, "encoding the proxy")
        rec = await asyncio.to_thread(clips.encode_proxy, rec)
        parents = [recipe.start_asset] + ([recipe.end_asset] if recipe.end_asset else []) + [b.asset_id for b in recipe.beats] + ([recipe.guide.asset_id] if recipe.guide else [])
        parents = list(dict.fromkeys(parents))
        from_stage = bool(job.origin and job.origin.suite == "stage")
        asset = await asyncio.to_thread(q.catalogue.ingest_file, q.ws.path / rec.proxy_path, kind="video", in_place=True, job_id=job.id, batch_id=job.batch_id,
                                        suite="stage" if from_stage else "animate", model_id=recipe.model_id, seed=job.seed, prompt_text=recipe.prompt_text,
                                        **({"lineage_kind": "stage-shot"} if recipe.guide else {}),
                                        params={"clip_id": rec.id, "preset": recipe.preset, "recipe": recipe.model_dump(), **ep},
                                        timings={"wall_s": q.wall_s(), "node_s": job.node_times}, compiled_graph_hash=compiled.graph_hash,
                                        parents=parents, frames=rec.frames, w=rec.w, h=rec.h, variant=job.variant, origin=job.origin)
        asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, clips.frame_path(rec.id, 0))
        rec.asset_id = asset.id
        rec.timings["wall_s"] = q.wall_s()
        clips.save(rec)
        q.hub.broadcast("asset.created", asset.model_dump())
        job.result["asset_ids"] = [asset.id]
        job.result["clip_id"] = rec.id
        job.log_tail.append(f"clip {rec.id}: {rec.frames} frames @ {rec.fps} fps, {rec.w}×{rec.h}, proxy {rec.proxy_bytes / 2**20:.1f} MiB")
        q.hub.broadcast("clip.ready", {"clip_id": rec.id, "asset_id": asset.id, "job_id": job.id, "frames": rec.frames, "fps": rec.fps, "w": rec.w, "h": rec.h,
                                       "origin": job.origin.model_dump() if job.origin else None})
        if facesim.available(q.app.settings.models_root):             # advisory, off the job's critical path
            q.side(identity_task(q, rec.id))


async def identity_task(q: JobQueue, clip_id: str) -> None:
    clips = ClipStore(q.ws)
    rec = clips.get(clip_id)
    if not rec:
        return
    start = q.catalogue.get(rec.start_asset_id)
    ref = q.catalogue.abs_path(start) if start else None
    try:
        result = await asyncio.wait_for(asyncio.to_thread(compute_identity, q.app.settings.models_root, clips, rec, ref), 240)
    except Exception as e:  # noqa: BLE001
        result = {"status": f"error: {type(e).__name__}: {e}", "sampled": 0, "with_face": 0}
    rec = clips.get(clip_id)
    if rec:
        rec.identity = result
        clips.save(rec)
        q.hub.broadcast("clip.updated", {"clip_id": clip_id, "identity": result})


class MeshFinisher:
    """P18 (D84): the GLB becomes a Catalogue asset of kind `mesh` (lineage `image-to-mesh` ← the source, the weights' licences in its params);
    the RenderMesh view saved beside it makes the thumbnail."""
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: ImageToMesh, files: list[dict], sub: Submission, q: JobQueue) -> None:
        from .graphs import recipe_weights
        paths = [output_path(q, f) for f in files]
        glb = next((p for p in paths if p.suffix.lower() in (".glb", ".gltf") and p.is_file()), None)
        view = next((p for p in paths if p.suffix.lower() == ".png" and p.is_file()), None)
        if glb is None:
            raise ValueError("the engine finished but produced no mesh (no .glb among its outputs)")
        compiled = sub.compiled
        licences = {rid: ROSTER_BY_ID[rid].license for rid in recipe_weights(recipe) if rid in ROSTER_BY_ID}
        rec = await asyncio.to_thread(q.catalogue.ingest_file, glb, kind="mesh", move=True, job_id=job.id, batch_id=job.batch_id, suite="generate",
                                      model_id=recipe.model_id, seed=job.seed, prompt_text=None,
                                      params=compiled.summary | {"recipe": recipe.model_dump(), "licences": licences, "format": "glb"},
                                      timings={"wall_s": q.wall_s(), "node_s": job.node_times}, compiled_graph_hash=compiled.graph_hash, variant=job.variant,
                                      parents=[recipe.asset_id], lineage_kind="image-to-mesh", origin=job.origin)
        if view is not None:
            rec = await asyncio.to_thread(q.catalogue.make_thumbs, rec, view)
        q.hub.broadcast("asset.created", rec.model_dump())
        job.result["asset_ids"] = [rec.id]
        job.log_tail.append(f"mesh {rec.id}: {glb.name} ({(rec.bytes or 0) / 2**20:.1f} MiB)" + (" with its view" if view else ", no view for the thumbnail"))


def finisher_for(recipe: AnyRecipe) -> Finisher:
    if isinstance(recipe, ImageToMesh):
        return MeshFinisher()
    if isinstance(recipe, I2V):
        return ClipFinisher()
    if isinstance(recipe, Segment):
        return SelectionFinisher()
    if isinstance(recipe, (Inpaint, I2I, Upscale)):
        return DocumentFinisher()
    fin = AssetFinisher()
    if isinstance(recipe, StageShot) and recipe.method == "refcontrol":
        # ST3 rig (journal 2026-10-13): a second exact-pose shot with the same prompt skips the text encode (ComfyUI's cache), so the
        # 6.8 GB encoder stays resident and the LoRA-patched base 9B streams from RAM — 15.7 s/it instead of 3.3 (474 s against 108).
        # Dropping the cache after the job costs a ~10 s reload from the page cache and keeps the next shot at its measured time.
        fin.frees_cache = True
    return fin


# ---- D62 Quick Remove: no engine -------------------------------------------------------------------------------------------------
async def run_cpu(job: JobRecord, recipe: AnyRecipe, q: JobQueue) -> bool:
    """The jobs that never start the engine (plan().engine is False): Quick Remove (D62) and the sequence draft render (P17)."""
    if isinstance(recipe, Render):
        return await run_render(job, recipe, q)
    if isinstance(recipe, Inpaint):
        return await run_quick_remove(job, recipe, q)
    raise ValueError(f"no CPU path for recipe kind {recipe.kind!r}")


async def run_render(job: JobRecord, recipe: Render, q: JobQueue) -> bool:
    """P17 (D83): the sequence as a Catalogue clip — every lane tick read from the clips' PNG masters (exact, not the proxies), two
    frames blended through a dissolve, frames mapped by nearest frame where a clip's rate differs from the lane's (D27: no conform
    here), at the first clip's size and the lane's fps; then the clip pipeline as for an i2v job (master, proxy, asset, lineage to
    every source clip's asset, `clip.ready`)."""
    store, clips = TimelineStore(q.ws), ClipStore(q.ws)
    tl = await asyncio.to_thread(store.get, recipe.timeline_id)
    if tl is None:
        raise ValueError(f"sequence {recipe.timeline_id} is not in the project")
    recs = {c.id: c for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise ValueError(f"clips missing from the project: {', '.join(missing)}")
    total = duration(tl)
    if total <= 0:
        raise ValueError("the sequence is empty")
    s = starts(tl)
    first = recs[tl.clips[0].clip_id]
    w, h = first.w, first.h
    tmp = q.ws.temp_dir / f"render-{job.id}"
    tmp.mkdir(parents=True, exist_ok=True)
    cache: dict[tuple[str, int], np.ndarray] = {}

    def frame(k: int, local: int) -> np.ndarray:
        rec = recs[tl.clips[k].clip_id]
        key = (rec.id, local)
        arr = cache.get(key)
        if arr is None:
            with Image.open(clips.frame_path(rec.id, local)) as im:
                im = im.convert("RGB")
                if im.size != (w, h):
                    im = im.resize((w, h), Image.LANCZOS)
                arr = np.asarray(im, dtype=np.float32)
            if len(cache) > 8:
                cache.pop(next(iter(cache)))
            cache[key] = arr
        return arr

    def chunk(f0: int, f1: int) -> list[Path]:
        out: list[Path] = []
        for f in range(f0, f1):
            what = at(tl, f, s)
            assert what is not None
            (ka, la), b, mix = what
            img = frame(ka, la)
            if b is not None:
                img = img * (1.0 - mix) + frame(b[0], b[1]) * mix
            p = tmp / f"{f:06d}.png"
            Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8)).save(p)
            out.append(p)
        return out

    paths: list[Path] = []
    t0 = time.time()
    step = max(1, tl.fps)
    for f0 in range(0, total, step):
        q.check_cancel(job)
        q.progress(job, f"rendering {f0}/{total}")
        job.progress = f0 / total
        paths += await asyncio.to_thread(chunk, f0, min(total, f0 + step))
    q.check_cancel(job)
    job.log_tail.append(f"render: {total} frames at {w}×{h} @ {tl.fps} fps in {time.time() - t0:.1f} s (CPU)")
    q.progress(job, "writing the master")
    sources = [recs[c.clip_id] for c in tl.clips]
    parents = list(dict.fromkeys(r.asset_id for r in sources if r.asset_id))
    rec = await asyncio.to_thread(clips.create, paths, job_id=job.id, batch_id=job.batch_id, model_id="sequence", preset="draft", prompt=tl.name,
                                  seed=job.seed, fps=tl.fps, start_asset_id=parents[0] if parents else "", beats=[],
                                  params={"recipe": recipe.model_dump(), "timeline": {"id": tl.id, "name": tl.name, "revision": tl.revision, "clips": [c.model_dump(by_alias=True) for c in tl.clips], "overlaps": tl.overlaps}},
                                  timings={"render_s": round(time.time() - t0, 1)})
    q.progress(job, "encoding the proxy")
    rec = await asyncio.to_thread(clips.encode_proxy, rec)
    asset = await asyncio.to_thread(q.catalogue.ingest_file, q.ws.path / rec.proxy_path, kind="video", in_place=True, job_id=job.id, batch_id=job.batch_id,
                                    suite="animate", model_id="sequence", seed=job.seed, prompt_text=tl.name,
                                    params={"clip_id": rec.id, "preset": "draft", "recipe": recipe.model_dump(), "timeline_id": tl.id, "revision": tl.revision},
                                    timings={"wall_s": q.wall_s()}, parents=parents, lineage_kind="render", frames=rec.frames, w=rec.w, h=rec.h,
                                    variant=job.variant, origin=job.origin)
    asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, clips.frame_path(rec.id, 0))
    rec.asset_id = asset.id
    rec.timings["wall_s"] = q.wall_s()
    clips.save(rec)
    q.hub.broadcast("asset.created", asset.model_dump())
    job.result["asset_ids"] = [asset.id]
    job.result["clip_id"] = rec.id
    job.log_tail.append(f"clip {rec.id}: {rec.frames} frames @ {rec.fps} fps, {rec.w}×{rec.h}, proxy {rec.proxy_bytes / 2**20:.1f} MiB")
    q.hub.broadcast("clip.ready", {"clip_id": rec.id, "asset_id": asset.id, "job_id": job.id, "frames": rec.frames, "fps": rec.fps, "w": rec.w, "h": rec.h,
                                   "origin": job.origin.model_dump() if job.origin else None})
    return True


async def run_quick_remove(job: JobRecord, recipe: Inpaint, q: JobQueue) -> bool:
    """PhotoCraft's content-aware fill of the selection on the CPU, pasted back like the AI modes (a candidate layer with a feathered
    layer mask, seamless optional) — seconds, and no GPU. Returns False when the job ended early (cancelled or failed)."""
    if not native.available():
        raise ValueError("Quick Remove needs the native extension (uv sync --project orchestrator --extra native)")
    if q.documents is None:
        raise ValueError("documents are not available (no project open)")
    od = await asyncio.to_thread(q.documents.get, recipe.document_id)
    exclude = {f"grp_{job.batch_id or job.id}"}
    q.progress(job, "content-aware fill (CPU)")

    def work() -> tuple[np.ndarray, RegionPlan]:
        comp = od.flatten(exclude=exclude)
        sel = od.selection
        if sel is None or not sel.any():
            raise ValueError("Quick Remove needs a selection (the region to remove)")
        mask = dilate(sel, recipe.expand) if recipe.expand else sel
        plan = plan_region(mask, od.doc.w, od.doc.h, recipe.margin_pct, 0, max_size=1 << 20, max_pixels=1 << 40)   # 1×: no engine size limits
        if plan is None:
            raise ValueError("the selection is empty")
        crop = np.ascontiguousarray(comp[plan.y:plan.y + plan.h, plan.x:plan.x + plan.w, :3])
        hole = mask[plan.y:plan.y + plan.h, plan.x:plan.x + plan.w] > 127
        filled = native.content_aware_fill(crop, hole, seed=job.seed or 1)
        arr = np.dstack([filled, np.full(filled.shape[:2], 255, np.uint8)])
        return assemble_layer(arr, plan, mask, recipe.feather, crop, recipe.blend), plan

    q.check_cancel(job)
    t = time.time()
    rgba, plan = await asyncio.wait_for(asyncio.to_thread(work), 300.0)
    q.check_cancel(job)                              # R4: a cancel that arrived during the fill ends the job; no layer is added
    job.result["region"] = plan.to_dict()
    job.log_tail.append(f"quick remove: {plan.w}×{plan.h} at {plan.x},{plan.y} in {time.time() - t:.2f} s (CPU)")
    # R1: the document may have been deleted, or closed and reopened, during the fill — paste into the store's current copy
    # (never save the stale object: that would resurrect a deleted .ora or lose the layer from the fresh copy)
    try:
        current = await asyncio.to_thread(q.documents.get, recipe.document_id)
    except StateError:
        raise ValueError("the document was deleted while Quick Remove ran")
    if (current.doc.w, current.doc.h) != (od.doc.w, od.doc.h):
        raise ValueError("the document's canvas changed size while Quick Remove ran — run it again")
    await q.irreversible(job)                        # R5 (C8): from here the work must never run twice — persisted before the layer lands
    await add_result_layer(q, job, current, recipe, rgba, plan.x, plan.y, "quick remove", as_mask=True)
    return True
