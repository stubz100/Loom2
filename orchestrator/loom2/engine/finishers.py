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
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from PIL import Image

from .. import matting, native, preset_icons
from ..clips import ClipStore, compute_identity
from ..documents import GroupLayer, RasterLayer
from ..edit_ai import RegionPlan, assemble_layer, combine_selection, dilate, mask_from_engine, plan_region
from ..fsio import StateError, new_id
from ..models import registry
from ..origin import JobOrigin
from ..recipes import I2I, I2V, TTS, AssembleFinal, ImageToMesh, Inpaint, Keypoints, MatteSequence, Reangle, Render, Segment, StageShot, TrainLora, Upscale, stage_model_id
from ..roster import ROSTER_BY_ID
from ..body import Body
from ..finals import FINAL_LAYER_SURFACE, FINAL_PLATE_SURFACE
from ..story import BODY_FIT_SURFACE, FOR_SHOT, PROP_MODEL_SURFACE, body_fit_origin
from ..timelines import TimelineStore, at, duration, starts
from ..tools import facesim
from ..tools.upright import stand_upright
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
        plate = job.origin is not None and job.origin.surface == FINAL_PLATE_SURFACE
        if plate and assets:                                                                    # D111 (PS5b): the final's plate still
            await asyncio.to_thread(_final_plate_result, q, str(job.origin.ref or ""), assets[0].id)
        if isinstance(recipe, StageShot) and assets and not plate:                              # 17 §3c: the frame of every shot pointing at this camera
            mine = job.origin.payload.get("shot_id") if job.origin and job.origin.surface == FOR_SHOT and job.origin.payload else None
            await asyncio.to_thread(_stage_result, q, recipe.stage_id, recipe.camera_id, "image", assets[0].id, _run(job, recipe, q), mine)
        if assets and job.origin and job.origin.surface == "lora_check":                        # 18 §3h (LT3): FaceSim against the hero, the record grows
            await asyncio.to_thread(_lora_check_result, q, job.origin.payload or {}, assets[0].id)
        if assets and job.origin and job.origin.surface == preset_icons.SURFACE:              # D90 (02 §6.3): the swatch pack, in app state
            await _swatch_result(job, assets[0], compiled.summary.get("model_id", getattr(recipe, "model_id", None)), q)
        if assets and job.origin and job.origin.surface == FOR_SHOT:                         # D90 (02 §5): made for a shot version → its takes
            await asyncio.to_thread(_shot_takes, q, job.origin.payload or {}, "image", [a.id for a in assets], _use(job.origin.payload), _run(job, recipe, q))
            await _chain(q, job.origin.payload or {})                                           # RC0: Run stale goes on with the steps after it
        panel = (job.origin.payload or {}).get("saved_panel") if job.origin else None       # D92: made from an applied saved panel → its picture
        if assets and isinstance(panel, str) and panel:
            await asyncio.to_thread(_panel_thumb, q, panel, assets[0].id)
        if assets and job.origin and job.origin.surface == "anim_ref":                        # CA0: the first result is the reference while there is none
            fit = await asyncio.to_thread(_anim_ref_result, q, job.origin.ref, job.origin.payload or {}, assets[0].id)
            if fit:
                try:
                    q.submit({"kind": "keypoints", "asset_id": assets[0].id}, origin=body_fit_origin(*fit))
                except Exception as e:  # noqa: BLE001 — the reference stands; the fit is offered by hand (Cast's button)
                    job.log_tail.append(f"body fit not queued: {e}")
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
                                      timings={"engine_wall_s": q.wall_s(), "node_s": job.node_times},
                                      chained_from=recipe.extend_from.clip_id if recipe.extend_from else None,
                                      overlap=int(recipe.extend_from.lead) if recipe.extend_from else 0,
                                      audio_asset_id=recipe.audio.asset_id if recipe.audio else None)
        q.progress(job, "encoding the proxy")
        line = q.catalogue.get(recipe.audio.asset_id) if recipe.audio else None
        rec = await asyncio.to_thread(clips.encode_proxy, rec, audio=q.catalogue.abs_path(line) if line else None)
        prev = clips.get(recipe.extend_from.clip_id) if recipe.extend_from else None
        parents = [recipe.start_asset] + ([recipe.end_asset] if recipe.end_asset else []) + [b.asset_id for b in recipe.beats] + ([recipe.guide.asset_id] if recipe.guide else []) \
            + ([prev.asset_id] if prev and prev.asset_id else []) + ([recipe.audio.asset_id] if recipe.audio else [])
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
        cam = (job.origin.payload or {}).get("camera_id") if job.origin else None
        if from_stage and recipe.guide and job.origin and job.origin.ref and isinstance(cam, str):      # 17 §3c: the clip of every shot pointing at this camera
            await asyncio.to_thread(_stage_result, q, job.origin.ref, cam, "clip", rec.id, _run(job, recipe, q))
        if job.origin and job.origin.surface == "lipsync" and job.origin.ref:   # D88 XL: a take on the shot version
            await asyncio.to_thread(_shot_takes, q, {"shot_id": job.origin.ref, "version": (job.origin.payload or {}).get("version")}, "clip", [rec.id], False, _run(job, recipe, q))
        if job.origin and job.origin.surface == FINAL_LAYER_SURFACE and job.origin.ref:   # D111 (PS5c): a character layer's batch
            await _final_layer_batch(q, job, recipe, rec.id)
        if job.origin and job.origin.surface == "anim_test" and job.origin.ref:   # CA0: the reference's test animation → the version's
            await asyncio.to_thread(_anim_test_result, q, job.origin.ref, job.origin.payload or {}, rec.id)
        if job.origin and job.origin.surface == FOR_SHOT:                     # D90 (02 §5): Animate for a shot version → its takes
            await asyncio.to_thread(_shot_takes, q, job.origin.payload or {}, "clip", [rec.id], _use(job.origin.payload), _run(job, recipe, q))
            await _chain(q, job.origin.payload or {})
        if facesim.available(q.app.settings.models_root):             # advisory, off the job's critical path
            q.side(identity_task(q, rec.id))


async def _swatch_result(job: JobRecord, rec: Any, model_id: str | None, q: JobQueue) -> None:
    """D90 (02 §6.3): the first result, downscaled, becomes the preset's swatch under its key (the asset stays in the Catalogue with its
    lineage). Never the job's failure: a swatch that cannot be stored is logged, and the preset keeps its glyph or its text."""
    payload = (job.origin.payload or {}) if job.origin else {}
    field, value = payload.get("field"), payload.get("value")
    if not (isinstance(field, str) and isinstance(value, str)):
        job.log_tail.append("swatch: the origin names no field / value")
        return
    try:
        icon = await asyncio.to_thread(preset_icons.PresetIconStore(q.app.state_dir).store_from, field, value, q.catalogue.abs_path(rec),
                                       model_id=model_id, seed=job.seed, asset_id=rec.id)
    except Exception as e:
        job.log_tail.append(f"swatch not stored: {e}")
        return
    job.result["preset_icon"] = icon.key
    q.hub.broadcast(preset_icons.EVENT, {"keys": [icon.key], "deleted": False})


def _lora_check_result(q: JobQueue, payload: dict, asset_id: str) -> None:
    """18 §3h: one check image scored against the hero (the largest face each; cosine), appended to the record's `identity` under
    `with` / `without`; the means follow. Advisory and never the job's failure; without the weights the record says so."""
    from ..loras import LoraRegistry
    try:
        reg = LoraRegistry(q.ws)
        rec = reg.get(str(payload.get("lora_id") or ""))
        if rec is None:
            return
        ident = dict(rec.identity or {})
        ident.setdefault("with", []); ident.setdefault("without", [])
        which = "with" if payload.get("which") == "with" else "without"
        sim: float | None = None
        if not facesim.available(q.app.settings.models_root):
            ident["status"] = "weights missing — scripts/fetch_facesim.py"
        else:
            hero = q.catalogue.get(str(ident.get("hero_asset_id") or ""))
            img = q.catalogue.get(asset_id)
            if hero is not None and img is not None:
                fs = facesim.FaceSim(q.app.settings.models_root)
                a = np.asarray(Image.open(q.catalogue.abs_path(hero)).convert("RGB"))
                b = np.asarray(Image.open(q.catalogue.abs_path(img)).convert("RGB"))
                fa, fb = fs.detect(a), fs.detect(b)
                if fa and fb:
                    sim = round(fs.similarity(fs.embed(a, fa[0].kps), fs.embed(b, fb[0].kps)), 3)
                ident["status"] = "ok"
        ident[which] = [*ident[which], sim]
        for k in ("with", "without"):
            vals = [x for x in ident[k] if isinstance(x, (int, float))]
            ident[f"{k}_mean"] = round(sum(vals) / len(vals), 3) if vals else None
        ident["done"] = len(ident["with"]) + len(ident["without"])
        if ident.get("n") and ident["done"] >= ident["n"] and ident.get("status") == "running":
            ident["status"] = "ok"
        rec.identity = ident
        reg.save(rec)
        q.hub.broadcast("lora.changed", {"id": rec.id, "profile_id": rec.profile_id, "version": rec.version})
    except Exception as e:  # noqa: BLE001 — advisory
        q.hub.broadcast("lora.changed", {"id": str(payload.get("lora_id") or ""), "profile_id": None, "version": None, "error": str(e)})


def _run(job: JobRecord, recipe: Any, q: JobQueue) -> dict[str, Any]:
    """RC0 (D96): what a shot's recipe records of a finished job — the resolved recipe it ran, its id and its wall time."""
    return {"recipe": recipe.model_dump(), "job_id": job.id, "seconds": q.wall_s()}


def _use(payload: dict | None) -> bool | None:
    """RC0: a Run stale job's result replaces the version's frame / clip (`use: true`); a For-chip job fills an empty slot only."""
    return True if (payload or {}).get("use") is True else None


async def _chain(q: JobQueue, payload: dict) -> None:
    """RC0 (D96, 05 §4): after a Run stale job, the steps of its plan that waited for it and run on the server are queued (one job at a time
    as always, D97). Never the job's failure: a plan that cannot go on is said on the shot's event."""
    chain = [c for c in payload.get("chain") or [] if isinstance(c, str)]
    if not chain:
        return
    from ..stages import StageStore
    from ..shot_recipe import StampReader, rerun_recipe, stale_plan, used_run
    from ..story import StoryStore, for_shot_target
    t = for_shot_target(payload)
    if t is None:
        return
    try:
        store = StoryStore(q.ws)
        s = await asyncio.to_thread(store.shot, t[0])
        v = s.version(t[1]) if s else None
        if v is None or v.state != "open" or v.recipe is None:
            return
        plan = await asyncio.to_thread(stale_plan, v, StampReader(stages=StageStore(q.ws), groups=q.groups, story=store))
        ready = [p for p in plan if p["id"] in chain and not p["after"] and p["how"] == "server"]
        rest = [c for c in chain if c not in {p["id"] for p in ready}]
        for p in ready:
            run = used_run(v.recipe.step(p["id"]), v)
            if run is None:
                continue
            q.submit(rerun_recipe(run, v), origin=JobOrigin(suite="animate", surface=FOR_SHOT, ref=None, payload={**payload, "chain": rest}))
        await q.flush()
    except Exception as e:                                                                      # noqa: BLE001 — never the job's failure
        q.hub.broadcast("story.changed", {"kind": "shot", "id": t[0], "revision": 0, "error": f"Run stale stopped: {e}"})


def _shot_takes(q: JobQueue, payload: dict, kind: str, ids: list[str], use: bool | None, run: dict[str, Any] | None = None) -> None:
    """Results recorded as takes of a shot version (payload {shot_id, version}): D88 XL's talking clip with `use=False` (never the version's
    clip until the author picks it); D90 (02 §5) a frame or clip made for the shot with `use=None` (it fills an empty slot, as a stage
    camera's result does). Never the job's failure: a version finalized meanwhile, or a shot deleted, leaves the results in the Catalogue."""
    from ..story import StoryStore, for_shot_target
    t = for_shot_target(payload)
    try:
        if t is None:
            raise ValueError("the origin names no shot version")
        store = StoryStore(q.ws)
        for ref in ids:
            s = store.add_take(t[0], t[1], kind, ref, use=use)
        if run is not None:                                                                     # RC0: the job, as a run of the version's step
            s = store.record_run(t[0], t[1], run["recipe"], outputs=ids, job_id=run.get("job_id"), seconds=run.get("seconds")) or s
        q.hub.broadcast("story.changed", {"kind": "shot", "id": s.id, "revision": s.revision})
    except Exception as e:                                                                      # never the job's failure
        q.hub.broadcast("story.changed", {"kind": "shot", "id": t[0] if t else None, "revision": 0, "error": str(e)})


async def _final_layer_batch(q: JobQueue, job: JobRecord, recipe: I2V, clip_id: str) -> None:
    """D111 (PS5c): a character layer's batch landed — the next batch is queued, carrying this one's last frames (E23a W1); after the last,
    the batches are stitched into the layer's frames (the carried frames dropped, the final's count kept) and the layer is done. A failure
    here fails the layer, not the job (the clip stays)."""
    from ..finals import FinalStore, character_recipe, plan_batches, stitch
    from ..origin import JobOrigin
    fid, payload = str(job.origin.ref), job.origin.payload or {}
    lid, k = str(payload.get("layer") or ""), int(payload.get("batch") or 0)
    store = FinalStore(q.ws)
    try:
        f = store.get(fid)
        layer = next((x for x in f.layers if x.id == lid), None) if f else None
        if f is None or layer is None:
            raise ValueError(f"the final {fid} or its layer {lid} is gone")
        batches = [dict(b) for b in layer.batches]
        if k >= len(batches) or batches[k].get("job_id") != job.id:
            job.log_tail.append(f"the layer {lid} was re-taken meanwhile; this batch is not used")
            return
        batches[k]["clip_id"] = clip_id
        plan = plan_batches(f.frames)
        if k + 1 < len(plan):
            nxt = q.submit(character_recipe(f, layer, recipe.model_id, recipe.prompt_text, plan[k + 1], clip_id),
                           origin=JobOrigin(suite="stage", surface=job.origin.surface, ref=fid, payload={**payload, "batch": k + 1}))[0]
            batches.append({"k": k + 1, "job_id": nxt.id, "clip_id": None})
            f = store.update_layer(fid, lid, status="running", batches=batches, job_ids=[*layer.job_ids, nxt.id])
            job.log_tail.append(f"layer {lid}: batch {k + 1} of {len(plan)} queued ({nxt.id})")
        else:
            clips = ClipStore(q.ws)
            frames = [[clips.frame_path(b["clip_id"], i) for i in range(clips.get(b["clip_id"]).frames)] for b in batches]
            store.update_layer(fid, lid, batches=batches)
            f = store.set_frames(fid, lid, stitch(frames, f.frames), status="running")
            from ..recipes import matte_mode
            mj = q.submit({"kind": "matte_sequence", "final_id": fid, "layer_id": lid, "mode": matte_mode(q.app.settings.variant)}, origin=JobOrigin(suite="stage", surface=job.origin.surface, ref=fid, payload={"layer": lid, "matte": True}))[0]
            f = store.update_layer(fid, lid, job_ids=[*next(x for x in f.layers if x.id == lid).job_ids, mj.id])
            job.log_tail.append(f"layer {lid}: {len(batches)} batch(es) stitched into {f.frames} frames; its matte queued ({mj.id})")
        q.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"layer {lid}: {e}")
        try:
            f = store.update_layer(fid, lid, status="failed", error=str(e))
            q.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
        except Exception:  # noqa: BLE001
            pass


def _final_plate_result(q: JobQueue, fid: str, asset_id: str) -> None:
    """D111 (PS5b): the plate's still on its final — the layer waits for Stage to project it (status running). Never the job's failure."""
    from ..finals import FinalStore
    try:
        f = FinalStore(q.ws).update_layer(fid, "plate", still_asset_id=asset_id, status="running")
        q.hub.broadcast("final.updated", {"id": fid, "revision": f.revision})
    except Exception as e:  # noqa: BLE001
        q.hub.broadcast("final.updated", {"id": fid, "revision": 0, "error": f"plate not set: {e}"})


def _anim_ref_result(q: JobQueue, pid: str | None, payload: dict, asset_id: str) -> tuple[str, str] | None:
    """CA0: an animation-reference job's first result becomes the version's reference (or back view) while it has none; every result stays
    on the candidates page for the author's pick. Never the job's failure."""
    from ..story import StoryStore
    try:
        p = StoryStore(q.ws).set_anim_ref(str(pid or ""), str(payload.get("version") or ""), str(payload.get("side") or "front"), asset_id, only_if_empty=True)
        if p is not None:
            q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
            v = p.version(str(payload.get("version") or ""))
            if (payload.get("side") or "front") == "front" and p.cls == "character" and v.body_fit_from is None and (v.body is None or v.body == Body()):
                return p.id, v.id                                      # CA1b: an untouched body is fitted at once (queued by the caller, on the loop)
    except Exception as e:  # noqa: BLE001
        q.hub.broadcast("story.changed", {"kind": "profile", "id": pid, "revision": 0, "error": f"animation reference not set: {e}"})
    return None


def _anim_test_result(q: JobQueue, pid: str, payload: dict, clip_id: str) -> None:
    """CA0: a reference's test animation is recorded on its version (the latest one). Never the job's failure."""
    from ..story import StoryStore
    try:
        p = StoryStore(q.ws).set_anim_test(pid, str(payload.get("version") or ""), clip_id)
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    except Exception as e:  # noqa: BLE001
        q.hub.broadcast("story.changed", {"kind": "profile", "id": pid, "revision": 0, "error": f"test animation not recorded: {e}"})


def _panel_thumb(q: JobQueue, name: str, asset_id: str) -> None:
    """D92: the saved panel's picture is its most recent result. Never the job's failure (a panel renamed or deleted meanwhile)."""
    from ..library import set_panel_thumb
    try:
        if set_panel_thumb(q.ws.path, name, asset_id):
            q.hub.broadcast("story.changed", {"kind": "panels", "revision": 0})
    except Exception as e:  # noqa: BLE001
        q.hub.broadcast("story.changed", {"kind": "panels", "revision": 0, "error": str(e)})


def _stage_result(q: JobQueue, stage_id: str, camera_id: str, kind: str, ref_id: str, run: dict[str, Any] | None = None, skip: str | None = None) -> None:
    """17 §3c: a stage camera's frame or clip is recorded as a take of the shots that point at the camera (their slot filled when empty)."""
    from ..stages import StageStore
    from ..story import StoryStore
    try:
        st = StageStore(q.ws).get(stage_id)
        for s in StoryStore(q.ws).record_stage_result(stage_id, camera_id, kind, ref_id, st.revision if st else None, run, skip):
            q.hub.broadcast("story.changed", {"kind": "shot", "id": s.id, "revision": s.revision})
    except Exception as e:                                                                      # never the job's failure
        q.hub.broadcast("story.changed", {"kind": "shot", "id": None, "revision": 0, "error": str(e)})


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
        upright = None
        try:                                                                                    # D109: stood upright (the reference camera's tilt off)
            upright = await asyncio.to_thread(stand_upright, glb)
            job.log_tail.append(f"stood upright: turned {upright[0]}° / {upright[1]}° / {upright[2]}° about x / y / z")
        except Exception as e:  # noqa: BLE001  (an unusual GLB is kept as it came)
            job.log_tail.append(f"not stood upright: {e}")
        compiled = sub.compiled
        licences = {rid: ROSTER_BY_ID[rid].license for rid in recipe_weights(recipe) if rid in ROSTER_BY_ID}
        rec = await asyncio.to_thread(q.catalogue.ingest_file, glb, kind="mesh", move=True, job_id=job.id, batch_id=job.batch_id, suite="generate",
                                      model_id=recipe.model_id, seed=job.seed, prompt_text=None,
                                      params=compiled.summary | {"recipe": recipe.model_dump(), "licences": licences, "format": "glb", "upright_deg": upright},
                                      timings={"wall_s": q.wall_s(), "node_s": job.node_times}, compiled_graph_hash=compiled.graph_hash, variant=job.variant,
                                      parents=[recipe.asset_id], lineage_kind="image-to-mesh", origin=job.origin)
        if view is not None:
            rec = await asyncio.to_thread(q.catalogue.make_thumbs, rec, view)
        q.hub.broadcast("asset.created", rec.model_dump())
        job.result["asset_ids"] = [rec.id]
        job.log_tail.append(f"mesh {rec.id}: {glb.name} ({(rec.bytes or 0) / 2**20:.1f} MiB)" + (" with its view" if view else ", no view for the thumbnail"))
        if job.origin and job.origin.surface == PROP_MODEL_SURFACE:                            # D110 (PS2): a Cast prop version's own model
            await asyncio.to_thread(_prop_model_result, q, job, rec.id)


def _prop_model_result(q: JobQueue, job: JobRecord, asset_id: str) -> None:
    """D110 (PS2): the model becomes its prop version's, with the reference it was made from (a newer reference marks it stale). Never the
    job's failure: the mesh stays in the Catalogue and the Stage library either way."""
    from ..story import StoryStore
    pid, payload = str(job.origin.ref or ""), job.origin.payload or {}
    try:
        p = StoryStore(q.ws).set_model(pid, str(payload.get("version") or ""), asset_id, str(payload.get("from") or "") or None)
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the model was not set on the prop: {e}")
        q.hub.broadcast("story.changed", {"kind": "profile", "id": pid, "revision": 0, "error": f"3D model not set: {e}"})


class KeypointsFinisher:
    """CA1b (D104): the people SDPose found go on the job's result (largest first); a `body_fit` job fits its Cast version's body to the
    largest one. Nothing enters the Catalogue."""
    frees_cache = False

    async def finish(self, job: JobRecord, recipe: Keypoints, files: list[dict], sub: Submission, q: JobQueue) -> None:
        import json
        text = next((f["text"] for f in files if "text" in f), None)
        if text is None:
            raise ValueError("the engine finished but returned no keypoints")
        frames = json.loads(text)
        frame = (frames[0] if isinstance(frames, list) and frames else frames) or {}
        people = sorted(frame.get("people") or [], key=lambda p: -sum((p.get("pose_keypoints_2d") or [])[2::3]))
        job.result["people"] = people
        job.result["canvas"] = [frame.get("canvas_width"), frame.get("canvas_height")]
        job.log_tail.append(f"{len(people)} {'person' if len(people) == 1 else 'people'} found")
        if job.origin and job.origin.surface == BODY_FIT_SURFACE:
            await asyncio.to_thread(_body_fit_result, q, job, recipe, people)


def _body_fit_result(q: JobQueue, job: JobRecord, recipe: Keypoints, people: list[dict]) -> None:
    """CA1b: the version's body fitted to the reference's proportions (the height, build, head, feet and attachments stay). A reference that
    shows no whole figure fails the job, so the author sees why."""
    from ..body import Body, fit_body, reference_ratios
    from ..story import StoryStore
    if not people:
        raise ValueError("no figure found in the animation reference")
    measured = reference_ratios(people[0])
    store = StoryStore(q.ws)
    pid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("version") or "")
    cur = store.profile(pid)
    if cur is None:
        raise ValueError(f"the profile {pid} is gone")
    v = cur.version(vid)
    body, report = fit_body(measured, v.body or Body())
    p = store.set_fitted_body(pid, v.id, body, recipe.asset_id)
    job.result["body"] = body.model_dump()
    job.result["fit"] = report
    job.log_tail.append("body fitted: " + ", ".join(f"{k} {body.model_dump()[k]}" for k in ("neck", "torso", "shoulders", "arms", "legs", "hands")))
    q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})


class MatteFinisher:
    """D111 (PS5d): SAM 3's masks become the character layer's `matte/` (one per frame, at the final's size); the layer is done."""
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: MatteSequence, files: list[dict], sub: Submission, q: JobQueue) -> None:
        from ..finals import FinalStore
        paths = [p for p in (output_path(q, f) for f in sorted(files, key=lambda x: x["filename"])) if p.is_file()]
        store = FinalStore(q.ws)
        f = store.get(recipe.final_id)
        if f is None:
            raise ValueError(f"the final {recipe.final_id} is gone")
        if len(paths) != f.frames:
            raise ValueError(f"SAM 3 returned {len(paths)} masks for {f.frames} frames")
        w, h = f.size["w"], f.size["h"]

        def write() -> None:
            d = store.pass_dir(f.id, recipe.layer_id, "matte")
            if d.exists():
                for old in d.glob("*.png"):
                    old.unlink()
            d.mkdir(parents=True, exist_ok=True)
            for i, src in enumerate(paths):
                with Image.open(src) as im:
                    im = im.convert("L")
                    if im.size != (w, h):
                        im = im.resize((w, h), Image.BILINEAR)
                    im.save(d / f"{i:04d}.png")
        await asyncio.to_thread(write)
        f = await asyncio.to_thread(store.update_layer, f.id, recipe.layer_id, status="done", error=None)
        job.result["final_id"], job.result["layer_id"] = f.id, recipe.layer_id
        job.log_tail.append(f"matte: {len(paths)} masks for {recipe.layer_id}")
        q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})


def finisher_for(recipe: AnyRecipe) -> Finisher:
    if isinstance(recipe, MatteSequence):
        return MatteFinisher()
    if isinstance(recipe, Keypoints):
        return KeypointsFinisher()
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
    if isinstance(recipe, AssembleFinal):                              # D111 (PS5e): the final's layers composited into the shot
        return await run_assemble(job, recipe, q)
    if isinstance(recipe, TrainLora):                                 # LT2: ai-toolkit in its venv, the engine stopped by the queue
        from ..trainer import run_train
        return await run_train(job, recipe, q)
    if isinstance(recipe, TTS):                                       # CN2: the TTS runner in the voices venv (the cloning tier with the engine stopped)
        from ..voices import run_tts
        return await run_tts(job, recipe, q)
    if isinstance(recipe, Inpaint):
        return await run_quick_remove(job, recipe, q)
    raise ValueError(f"no CPU path for recipe kind {recipe.kind!r}")


async def run_assemble(job: JobRecord, recipe: AssembleFinal, q: JobQueue) -> bool:
    """D111 (PS5e): the final's layers composited frame by frame (final_assembly.py), the frames a clip (master, proxy, asset with lineage
    to the layers' sources); conformed to 24 fps by the local RIFE at F16 when it is there (D27); a take on the Story shot it was made for."""
    from ..final_assembly import assemble_frames, conform_24
    from ..finals import FinalStore
    store, clips = FinalStore(q.ws), ClipStore(q.ws)
    f = await asyncio.to_thread(store.get, recipe.final_id)
    if f is None:
        raise ValueError(f"the final {recipe.final_id} is not in the project")
    tmp = q.ws.temp_dir / f"assemble-{job.id}"
    shutil.rmtree(tmp, ignore_errors=True)

    def progress(done: int, total: int) -> None:
        job.progress = done / total
        job.progress_text = f"compositing {done}/{total}"
    stats = await asyncio.to_thread(assemble_frames, store, f, tmp / "f16", progress, store.folder(f.id) / "comp")   # AE1: + the composition's footage
    q.check_cancel(job)
    paths = sorted((tmp / "f16").glob("*.png"))
    fps = f.rate
    conformed = await asyncio.to_thread(conform_24, tmp / "f16", tmp / "f24", f.frames) if f.rate == 16 else None
    if conformed:
        paths, fps = conformed, 24
        stats["conform"] = "RIFE v4.6 to 24 fps (D27)"
    job.log_tail.append(f"assembly: {stats['frames']} frames in {stats['seconds']} s; offsets {stats['offsets_px']}; " + (f"conformed to {len(paths)} at 24 fps" if conformed else f"at {fps} fps"))
    q.progress(job, "writing the master")
    parents = [x.still_asset_id for x in f.layers if x.still_asset_id] + [x.reference_asset_id for x in f.layers if x.reference_asset_id]
    rec = await asyncio.to_thread(clips.create, paths, job_id=job.id, batch_id=job.batch_id, model_id="final", preset="draft", prompt=f.name, seed=job.seed, fps=fps,
                                  start_asset_id=parents[0] if parents else "", beats=[], params={"recipe": recipe.model_dump(), "final_id": f.id, "assembly": stats},
                                  timings={"assemble_s": stats["seconds"]})
    q.progress(job, "encoding the proxy")
    rec = await asyncio.to_thread(clips.encode_proxy, rec)
    asset = await asyncio.to_thread(q.catalogue.ingest_file, q.ws.path / rec.proxy_path, kind="video", in_place=True, job_id=job.id, batch_id=job.batch_id,
                                    suite="stage", model_id="final", seed=job.seed, prompt_text=f.name,
                                    params={"clip_id": rec.id, "final_id": f.id, "recipe": recipe.model_dump(), "assembly": stats},
                                    timings={"wall_s": q.wall_s()}, parents=parents, lineage_kind="final", frames=rec.frames, w=rec.w, h=rec.h,
                                    variant=job.variant, origin=job.origin)
    asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, clips.frame_path(rec.id, 0))
    rec.asset_id = asset.id
    clips.save(rec)
    shutil.rmtree(tmp, ignore_errors=True)
    f = await asyncio.to_thread(store.set_result, f.id, rec.id, stats)
    q.hub.broadcast("asset.created", asset.model_dump())
    job.result["asset_ids"] = [asset.id]
    job.result["clip_id"] = rec.id
    q.hub.broadcast("clip.ready", {"clip_id": rec.id, "asset_id": asset.id, "job_id": job.id, "frames": rec.frames, "fps": rec.fps, "w": rec.w, "h": rec.h,
                                   "origin": job.origin.model_dump() if job.origin else None})
    q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
    if f.shot_id:                                                                   # the take on the Story shot it was made for
        await asyncio.to_thread(_shot_takes, q, {"shot_id": f.shot_id}, "clip", [rec.id], False, _run(job, recipe, q))
    return True


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
