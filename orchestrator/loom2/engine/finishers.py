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
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from PIL import Image

from .. import matting, native, preset_icons, set_things
from ..clips import ClipStore, compute_identity
from ..documents import GroupLayer, RasterLayer
from ..edit_ai import RegionPlan, assemble_layer, combine_selection, dilate, mask_from_engine, plan_region
from ..fsio import StateError, new_id
from ..models import registry
from ..origin import JobOrigin
from ..recipes import I2I, I2V, TTS, AssembleFinal, CompRender, ImageToMesh, ImageToSet, Inpaint, Keypoints, LayerPass, MatteSequence, Reangle, Render, Segment, StageShot, TrainLora, Upscale, stage_model_id
from ..roster import ROSTER_BY_ID
from ..fsio import utc_now
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
        if isinstance(recipe, Inpaint) and getattr(job, "origin", None) and job.origin.surface == set_things.CLEAN_SURFACE:   # D123 (SC3c-3): a picture set's plate
            done = await asyncio.to_thread(set_things.clean_plate, q, job, od)
            q.hub.broadcast("asset.created", done["asset"].model_dump())
            nxt = q.submit({"kind": "image_to_set", "asset_id": done["asset"].id, "stage_id": done["stage_id"], "replace_set_id": done["set_id"], "lens_deg": done["lens_deg"]},
                           origin=JobOrigin(suite="stage", surface=set_things.REBUILD_SURFACE, ref=done["stage_id"], payload={"set_id": done["set_id"]}))[0]
            models = []
            for c in (job.origin.payload or {}).get("cutouts") or []:                    # then a model of each thing's cut-out
                models.append(q.submit({"kind": "image_to_mesh", "asset_id": c["cutout_id"]},
                                       origin=JobOrigin(suite="stage", surface=set_things.MODEL_SURFACE, ref=done["stage_id"],
                                                        payload={"set_id": done["set_id"], "thing_id": c["thing_id"]}))[0].id)
            job.result.update({"clean_plate_id": done["asset"].id, "next_job_id": nxt.id, "next_job_ids": [nxt.id, *models]})
            job.log_tail.append(f"the clean plate {done['asset'].id}; the relief rebuilt from it next ({nxt.id}), then {len(models)} model{'s' if len(models) != 1 else ''}")


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


def _shot_takes(q: JobQueue, payload: dict, kind: str, ids: list[str], use: bool | None, run: dict[str, Any] | None = None,
                stage_revision: int | None = None) -> None:
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
            s = store.add_take(t[0], t[1], kind, ref, use=use, stage_revision=stage_revision)   # RC1: a final's clip stamps the stage it read
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


def _stage_result(q: JobQueue, stage_id: str, camera_id: str, kind: str, ref_id: str, run: dict[str, Any] | None = None, skip: str | None = None,
                  use: bool | None = None) -> None:
    """17 §3c: a stage camera's frame or clip is recorded as a take of the shots that point at the camera (their slot filled when empty;
    `use` False: never by itself)."""
    from ..stages import StageStore
    from ..story import StoryStore
    try:
        st = StageStore(q.ws).get(stage_id)
        for s in StoryStore(q.ws).record_stage_result(stage_id, camera_id, kind, ref_id, st.revision if st else None, run, skip, use=use):
            q.hub.broadcast("story.changed", {"kind": "shot", "id": s.id, "revision": s.revision})
    except Exception as e:                                                                      # never the job's failure
        q.hub.broadcast("story.changed", {"kind": "shot", "id": None, "revision": 0, "error": str(e)})


def _final_take(q: JobQueue, f: Any, clip_id: str, use: bool | None, run: dict[str, Any] | None) -> None:
    """D125 (A1): a final's assembled or rendered clip as a take — of the Story shot version it was made for (the For chip's; a final made
    before D125 names no version: the shot's current one), else of the shots whose current open version points at its stage and camera, as
    a stage clip is (17 §3c). WB2: the take needs the version — `for_shot_target` takes a shot id and a version, never one alone."""
    if not f.shot_id:
        _stage_result(q, f.stage_id, f.camera_id, "clip", clip_id, run, use=use)
        return
    version = f.shot_version
    if not version:
        from ..story import StoryStore
        s = StoryStore(q.ws).shot(f.shot_id)
        version = s.current if s else None
    _shot_takes(q, {"shot_id": f.shot_id, "version": version}, "clip", [clip_id], use, run, stage_revision=f.stage_revision)


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
        if job.origin and job.origin.surface == set_things.MODEL_SURFACE:                      # D123 (SC3c-3): a picture set's thing, stood on its relief
            await asyncio.to_thread(set_things.model_landed, q, job, rec.id)


class SetFinisher:
    """SC3 (D120): the relief GLB becomes a Catalogue asset of kind `mesh` (lineage `image-to-set` ← the picture; the lens, the floor and the
    depth range read back from its vertices in `params.relief`; MoGe's depth render its thumbnail) and, when the recipe names a stage, that
    stage gets the set standing on its floor and the picture's camera as the active one."""
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: ImageToSet, files: list[dict], sub: Submission, q: JobQueue) -> None:
        from ..relief import lens_of_glb
        from ..stages import StageStore
        paths = [output_path(q, f) for f in files]
        glb = next((p for p in paths if p.suffix.lower() in (".glb", ".gltf") and p.is_file()), None)
        depth = next((p for p in paths if p.suffix.lower() == ".png" and "_depth" in p.name and p.is_file()), None)
        if glb is None:
            raise ValueError("the engine finished but produced no relief (no .glb among its outputs)")
        lens = await asyncio.to_thread(lens_of_glb, glb)
        job.log_tail.append(f"the relief: {lens['vertices']} vertices, {lens['faces']} faces, lens {lens['fov_x']}×{lens['fov_y']}°, the floor {lens['y_floor']} m under the camera, "
                            f"median depth {lens['depth_median']} m" if lens else "the relief carries no UVs — the lens is not read from it")
        compiled = sub.compiled
        rec = await asyncio.to_thread(q.catalogue.ingest_file, glb, kind="mesh", move=True, job_id=job.id, batch_id=job.batch_id, suite="stage",
                                      model_id=recipe.model_id, seed=job.seed, prompt_text=None,
                                      params=compiled.summary | {"recipe": recipe.model_dump(), "format": "glb", "relief": lens or {}},
                                      timings={"wall_s": q.wall_s(), "node_s": job.node_times}, compiled_graph_hash=compiled.graph_hash, variant=job.variant,
                                      parents=[recipe.asset_id], lineage_kind="image-to-set", origin=job.origin)
        if depth is not None:
            rec = await asyncio.to_thread(q.catalogue.make_thumbs, rec, depth)
        q.hub.broadcast("asset.created", rec.model_dump())
        job.result["asset_ids"] = [rec.id]
        job.result["relief"] = lens
        job.log_tail.append(f"relief {rec.id}: {glb.name} ({(rec.bytes or 0) / 2**20:.1f} MiB)")
        if recipe.stage_id:
            lens_deg, floor_y = (lens or {}).get("fov_x") or recipe.lens_deg, (lens or {}).get("y_floor")
            glb = q.catalogue.abs_path(rec)                                                      # SC3d: the store lays the set level by its floor
            store = StageStore(q.ws)
            if recipe.replace_set_id:                                                  # SC3b: the set rebuilt in place (a corrected lens; SC3c-3: a clean plate)
                st = await asyncio.to_thread(store.replace_image_set, recipe.stage_id, recipe.replace_set_id, rec.id, lens_deg, floor_y, recipe.asset_id, glb)
                obj = next(o for o in st.objects if o.id == recipe.replace_set_id)
            else:
                st = await asyncio.to_thread(store.add_image_set, recipe.stage_id, rec.id, recipe.asset_id, lens_deg, floor_y, glb)
                obj = st.objects[-1]
            if recipe.replace_set_id:                                                  # SC3f: the made things follow their set
                moved = await asyncio.to_thread(set_things.restand_things, store, q.catalogue, recipe.stage_id, obj.id)
                st = await asyncio.to_thread(store.get, recipe.stage_id) or st
                job.result["restood"] = moved
                if moved["stood"] or moved["left"] or moved["failed"]:
                    job.log_tail.append("the made things: " + "; ".join(x for x in (
                        f"stood again on the new relief: {', '.join(moved['stood'])}" if moved["stood"] else "",
                        f"left where you put them: {', '.join(moved['left'])}" if moved["left"] else "",
                        f"not stood again: {'; '.join(moved['failed'])}" if moved["failed"] else "") if x))
            job.result["stage_id"], job.result["set_id"], job.result["camera_id"] = st.id, obj.id, obj.plate_camera_id
            q.hub.broadcast("stage.updated", {"id": st.id, "revision": st.revision})
            job.log_tail.append(f"on stage {st.id}: {obj.name} with its camera {obj.plate_camera_id} (lens {obj.lens_deg}°, the floor {obj.floor_y} m under it)")
            job.result["level"] = obj.level
            job.log_tail.append(f"laid level: pitched {obj.level['pitch_deg']}°, turned {obj.level['roll_deg']}° sideways" if obj.level
                                else "not laid level (too little floor in the picture, or too steep a one)")


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


class LayerPassFinisher:
    """D118 (AE4a): the pass's frames become a take of the layer (`passes/<take>/`, cropped back from the model's padding, at the final's
    size), and the layer takes it as its source; the composition follows when the Final level syncs (routes: …/composition/sync)."""
    frees_cache = True

    async def finish(self, job: JobRecord, recipe: LayerPass, files: list[dict], sub: Submission, q: JobQueue) -> None:
        from ..finals import FinalStore
        from ..fsio import new_id
        paths = [p for p in (output_path(q, f) for f in sorted(files, key=lambda x: x["filename"])) if p.is_file()]
        store = FinalStore(q.ws)
        f = store.get(recipe.final_id)
        if f is None:
            raise ValueError(f"the final {recipe.final_id} is gone")
        if recipe.preset in ("face", "lipsync"):
            await _finish_face_step(job, recipe, paths, q, store, f)
            return
        if len(paths) != f.frames:
            raise ValueError(f"the pass returned {len(paths)} frames for {f.frames}")
        w, h = f.size["w"], f.size["h"]
        take_id = new_id("take")
        proc = (sub.compiled.summary or {}).get("processing") if recipe.scope == "below" else None
        if recipe.scope == "below" and not proc:
            raise ValueError("the pass over the stack below lost its record (pipeline.render_below)")
        d = store.processing_dir(f.id, proc["pid"]) / "frames" if proc else store.pass_dir(f.id, recipe.layer_id, f"passes/{take_id}")

        def write() -> None:
            if proc:
                shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)
            for i, src in enumerate(paths):
                with Image.open(src) as im:
                    im = im.convert("RGB")
                    if im.size != (w, h):
                        im = im.crop((0, 0, w, h)) if im.width >= w and im.height >= h else im.resize((w, h), Image.BILINEAR)
                    im.save(d / f"{i:04d}.png")
        await asyncio.to_thread(write)
        if proc:                                                          # AE4e: a processing layer — the final's record; the composition brings it in on sync
            from ..finals import ProcessingLayer
            rec = ProcessingLayer(id=proc["pid"], above=recipe.layer_id, preset=recipe.preset, strength=recipe.strength, model_id=recipe.model_id, job_id=job.id,
                                  frames=len(paths), made_at=utc_now(), signature=str(proc.get("signature") or ""), below=[int(x) for x in proc.get("below") or []])
            shutil.rmtree(store.processing_dir(f.id, proc["pid"]) / "in", ignore_errors=True)
            f = await asyncio.to_thread(store.set_processing, f.id, rec)
            job.result["final_id"], job.result["layer_id"], job.result["processing_id"] = f.id, recipe.layer_id, proc["pid"]
            job.log_tail.append(f"{recipe.preset} pass at {recipe.strength:g} over the stack from {recipe.layer_id} down: {len(paths)} frames → processing layer {proc['pid']}")
            q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
            return
        take = {"id": take_id, "preset": recipe.preset, "strength": recipe.strength, "model_id": recipe.model_id, "job_id": job.id, "frames": len(paths),
                "seed": job.seed, "made_at": utc_now()}
        f = await asyncio.to_thread(store.add_take, f.id, recipe.layer_id, take, True)
        job.result["final_id"], job.result["layer_id"], job.result["take_id"] = f.id, recipe.layer_id, take_id
        job.log_tail.append(f"{recipe.preset} pass at {recipe.strength:g}: {len(paths)} frames → take {take_id} of {recipe.layer_id}, now its source")
        q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})


async def finish_face_take(job: JobRecord, recipe: LayerPass, q: JobQueue, store: Any, f: Any, layer: Any, take_dir: Path, work: Path, plan: dict, heads: list[Path],
                           extra: dict[str, Any]) -> None:
    """D118 (AE4c): the face pass's last step — the rendered heads (RGBA, one per frame) pasted back onto the layer's shown frames at their
    boxes (heads.paste_take: the frames, head/, matte/, matte_comp/), the work dir dropped, the take recorded with `extra` (AE4d: the mouth
    by the model) and shown as the layer's source. Called by the head finisher, and by the mouth runner (lipsync.run_mouth)."""
    from ..compositions import CompositionStore
    from ..heads import paste_take
    step = recipe.step
    root = store.folder(f.id)
    n = f.frames
    base = sorted((root / plan["base"]).glob("*.png"))
    mattes = sorted((root / plan["matte"]).glob("*.png")) if plan.get("matte") else []
    comp_m = CompositionStore(q.ws).footage(f.id) / f"{layer.id}_matte"
    comp_mattes = sorted(comp_m.glob("*.png")) if comp_m.is_dir() else []
    boxes = [tuple(int(v) for v in b) for b in plan["boxes"]]

    def paste_all() -> None:
        paste_take(take_dir, heads, base, mattes, comp_mattes, boxes, n)       # the frames, head/, matte/, matte_comp/
        shutil.rmtree(work, ignore_errors=True)
    await asyncio.to_thread(paste_all)
    take = {"id": step.take_id, "preset": recipe.preset, "strength": recipe.strength, "model_id": recipe.model_id, "job_id": job.id, "frames": n, "seed": job.seed,
            "made_at": utc_now(), "head": True, "matte": len(mattes) == n, "boxes": [list(boxes[0]), list(boxes[-1])], "ref": plan.get("ref"), "mouth": recipe.mouth,
            "lines": [{"layer": w_.get("layer"), "text": w_.get("text"), "f0": w_["f0"], "f1": w_["f1"]} for w_ in plan.get("windows") or []], **extra}
    f = await asyncio.to_thread(store.add_take, f.id, recipe.layer_id, take, True)
    job.result["final_id"], job.result["layer_id"], job.result["take_id"] = f.id, recipe.layer_id, step.take_id
    job.log_tail.append(f"{recipe.preset} pass: {n} heads pasted back → take {step.take_id} of {recipe.layer_id}, now its source"
                        + (f" ({len(take['lines'])} line window(s){', the mouth by the model' if take.get('mouth') == 'model' else ''})" if recipe.preset == "lipsync" else ""))
    q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})


async def _finish_face_step(job: JobRecord, recipe: LayerPass, paths: list[Path], q: JobQueue, store: Any, f: Any) -> None:
    """D118 (AE4c): one step of the face pass landed. A talking head (`face_video` k) is kept under the take's work dir and the next window
    — or the first head batch — is queued; a head batch (`head` k, RGBA: the render and its silhouette) is kept and the next batch queued,
    carrying its last frames; after the last batch the heads are stitched (finals.stitch), pasted back onto the layer's shown frames at
    their boxes under the grown, feathered mask (heads.paste_head), the layer's matte updated in the box (the composition's matte footage
    too, keeping a nearer prop's cut), and the take is recorded as the layer's source. The same origin rides every step, so the Final
    level sees one running pass. A failure anywhere drops the take's folder."""
    from ..finals import stitch
    from ..fsio import read_json
    from ..heads import CROP
    step = recipe.step
    if step is None:
        raise ValueError("the face pass runs in steps")
    layer = next((x for x in f.layers if x.id == recipe.layer_id), None)
    if layer is None:
        raise ValueError(f"the final has no layer {recipe.layer_id}")
    take_dir = store.pass_dir(f.id, layer.id, f"passes/{step.take_id}")
    work = take_dir / "work"
    try:
        plan = read_json(work / "plan.json")
        if step.stage == "face_video":
            wnd = plan["windows"][step.k]
            if len(paths) < int(wnd["frames"]):
                raise ValueError(f"the talking head returned {len(paths)} frames for {wnd['frames']}")

            def keep_face() -> None:
                d = work / "face" / str(step.k)
                d.mkdir(parents=True, exist_ok=True)
                for i, src in enumerate(paths[: int(wnd["frames"])]):
                    with Image.open(src) as im:
                        im = im.convert("RGB")
                        if im.size != (CROP, CROP):
                            im = im.resize((CROP, CROP), Image.LANCZOS)
                        im.save(d / f"{i:04d}.png")
            await asyncio.to_thread(keep_face)
            job.log_tail.append(f"talking head {step.k + 1} of {len(plan['windows'])}: {wnd['frames']} frames")
            if step.k + 1 < len(plan["windows"]):
                nxt = {"take_id": step.take_id, "stage": "face_video", "k": step.k + 1}
                model = recipe.model_id
            else:
                nxt = {"take_id": step.take_id, "stage": "head", "k": 0}
                spec = next((s for s in registry.animate_specs() if registry.offered(s, q.app.settings.variant)), None)
                if spec is None:
                    raise ValueError("no pose-driven model in this build")
                model = spec.id
        else:
            batch = plan["batches"][step.k]
            if len(paths) < int(batch["frames"]):
                raise ValueError(f"the head batch returned {len(paths)} frames for {batch['frames']}")

            def keep_head() -> None:
                d = work / "head" / str(step.k)
                d.mkdir(parents=True, exist_ok=True)
                for i, src in enumerate(paths[: int(batch["frames"])]):
                    with Image.open(src) as im:
                        im = im.convert("RGBA")
                        if im.size != (CROP, CROP):
                            im = im.resize((CROP, CROP), Image.LANCZOS)
                        im.save(d / f"{i:04d}.png")
            await asyncio.to_thread(keep_head)
            job.log_tail.append(f"head batch {step.k + 1} of {len(plan['batches'])}: {batch['frames']} frames rendered and matted")
            if step.k + 1 < len(plan["batches"]):
                nxt = {"take_id": step.take_id, "stage": "head", "k": step.k + 1}
                model = recipe.model_id
            else:
                heads = stitch([sorted((work / "head" / str(k)).glob("*.png")) for k in range(len(plan["batches"]))], f.frames)
                if recipe.mouth == "model":                               # AE4d: the lip-sync model redraws the mouth on the rendered heads first
                    nxt = {"take_id": step.take_id, "stage": "mouth", "k": 0}
                    model = recipe.model_id
                else:
                    await finish_face_take(job, recipe, q, store, f, layer, take_dir, work, plan, heads, {})
                    return
        nj = q.submit({**recipe.model_dump(), "model_id": model, "step": nxt, "seeds": [job.seed]},
                      origin=JobOrigin(**job.origin.model_dump()) if job.origin else None)[0]
        job.result["final_id"], job.result["layer_id"], job.result["take_id"], job.result["next_job_id"] = f.id, recipe.layer_id, step.take_id, nj.id
        f = await asyncio.to_thread(store.update_layer, f.id, recipe.layer_id, job_ids=[*layer.job_ids, nj.id])
        job.log_tail.append(f"next: {nxt['stage']} {nxt['k'] + 1} ({nj.id})")
        q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
    except Exception:
        shutil.rmtree(take_dir, ignore_errors=True)
        raise


def finisher_for(recipe: AnyRecipe) -> Finisher:
    if isinstance(recipe, LayerPass):
        return LayerPassFinisher()
    if isinstance(recipe, MatteSequence):
        return MatteFinisher()
    if isinstance(recipe, Keypoints):
        return KeypointsFinisher()
    if isinstance(recipe, ImageToSet):
        return SetFinisher()
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
    if isinstance(recipe, CompRender):                                # AE1: the composition rendered by effectcraft-cli
        return await run_comp_render(job, recipe, q)
    if isinstance(recipe, TrainLora):                                 # LT2: ai-toolkit in its venv, the engine stopped by the queue
        from ..trainer import run_train
        return await run_train(job, recipe, q)
    if isinstance(recipe, TTS):                                       # CN2: the TTS runner in the voices venv (the cloning tier with the engine stopped)
        from ..voices import run_tts
        return await run_tts(job, recipe, q)
    if isinstance(recipe, LayerPass):                                 # AE4d: the face pass's mouth step — the lip-sync model in its venv, the engine stopped
        from ..lipsync import run_mouth
        return await run_mouth(job, recipe, q)
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
    await asyncio.to_thread(_final_take, q, f, rec.id, False, _run(job, recipe, q))      # a draft composite: a take, never the clip by itself
    return True


async def run_comp_render(job: JobRecord, recipe: CompRender, q: JobQueue) -> bool:
    """AE1 (proto01_animate 20 §2, D114): the finished shot — the final's composition rendered by the pinned `effectcraft-cli render`
    (Best, Full, a PNG sequence, on the CPU: a render never takes the GPU beside a job, D97 / D113) into a clip (master, proxy, asset with
    lineage to the assembly's clip), conformed to 24 fps by the local RIFE at F16 (D27); it becomes the final's clip (the final's record
    does not move, so the composition stays fresh) and a take on the Story shot the final was made for."""
    from ..compositions import CompositionStore
    from ..effectcraft import render_argv
    from ..final_assembly import conform_24, mix_audio
    from ..finals import FinalStore
    from ..fsio import utc_now
    from ..trainer import _kill
    from .supervisor import _assign_to_job
    store, clips, cs = FinalStore(q.ws), ClipStore(q.ws), CompositionStore(q.ws)
    f = await asyncio.to_thread(store.get, recipe.final_id)
    if f is None:
        raise ValueError(f"the final {recipe.final_id} is not in the project")
    c = await asyncio.to_thread(cs.get, f)
    if c is None:
        raise ValueError(f"the final {f.id} has no composition yet (make it first)")
    stale = [pid for pid, v in (c.processing_stale or {}).items() if v]
    if stale:                                                          # AE4e: the UI asked before; the log says what the shot carries
        job.log_tail.append(f"{len(stale)} processing layer(s) stale ({', '.join(stale)}): rendered as they are — a layer below changed since")
    tmp = q.ws.temp_dir / f"comp-render-{job.id}"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "f16").mkdir(parents=True)
    argv = render_argv(q.app.settings.effectcraft, cs.ecproj(f.id), c.comp, tmp / "f16" / "f_[####].png")
    env = {**os.environ, "RAYON_NUM_THREADS": str(q.app.settings.effectcraft.threads), "WGPU_BACKEND": "vulkan"}
    log_path = q.app.logs_dir / f"comp-render-{job.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log_path.open("ab") as lf:
        lf.write(f"==== launch {utc_now()} job {job.id} {' '.join(argv)}\n".encode("utf-8"))
        lf.flush()
        proc = subprocess.Popen(argv, stdout=lf, stderr=subprocess.STDOUT, env=env)
        _assign_to_job(proc)
    job.log_tail.append(f"effectcraft-cli render pid {proc.pid}")
    q.progress(job, "rendering the composition")
    while proc.poll() is None:
        await asyncio.sleep(0.5)
        done = len(list((tmp / "f16").glob("*.png")))
        job.progress = min(1.0, done / max(1, f.frames))
        job.progress_text = f"rendering {done}/{f.frames}"
        if job.id in q._cancel_requested:
            _kill(proc.pid)
            await asyncio.to_thread(proc.wait)
            q.check_cancel(job)
    if proc.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").strip()[-400:]
        raise ValueError(f"effectcraft-cli render failed ({proc.returncode}): {tail}")
    paths = sorted((tmp / "f16").glob("*.png"))
    if len(paths) != f.frames:
        raise ValueError(f"the render wrote {len(paths)} frames, the final has {f.frames}")
    render_s = round(time.time() - t0, 1)
    fps = f.rate
    conformed = await asyncio.to_thread(conform_24, tmp / "f16", tmp / "f24", f.frames) if f.rate == 16 else None
    if conformed:
        paths, fps = conformed, 24
    job.log_tail.append(f"composition rendered: {f.frames} frames in {render_s} s (revision {c.revision})" + (f"; conformed to {len(paths)} at 24 fps" if conformed else ""))
    q.progress(job, "writing the master")
    previous = await asyncio.to_thread(clips.get, f.clip_id) if f.clip_id else None
    parents = [previous.asset_id] if previous and previous.asset_id else []
    stats = {"frames": f.frames, "render_s": render_s, "composition_revision": c.revision, "effectcraft": c.effectcraft, "conform": "RIFE v4.6 to 24 fps (D27)" if conformed else None}
    rec = await asyncio.to_thread(clips.create, paths, job_id=job.id, batch_id=job.batch_id, model_id="composition", preset="best", prompt=f.name, seed=job.seed, fps=fps,
                                  start_asset_id=parents[0] if parents else "", beats=[], params={"recipe": recipe.model_dump(), "final_id": f.id, "render": stats},
                                  timings={"render_s": render_s})
    q.progress(job, "encoding the proxy")
    timing = await asyncio.to_thread(cs.audio_timing, f, c)                                             # D118 (AE4b): the lines ride the proxy
    mix = await asyncio.to_thread(mix_audio, timing, f.frames / float(f.rate or 16), tmp / "mix.wav") if timing else None
    rec = await asyncio.to_thread(clips.encode_proxy, rec, audio=mix)
    if mix is not None:
        rec.audio_asset_id = timing[0]["asset_id"]
        job.log_tail.append(f"{len(timing)} line{'s' if len(timing) != 1 else ''} mixed into the proxy")
    asset = await asyncio.to_thread(q.catalogue.ingest_file, q.ws.path / rec.proxy_path, kind="video", in_place=True, job_id=job.id, batch_id=job.batch_id,
                                    suite="stage", model_id="composition", seed=job.seed, prompt_text=f.name,
                                    params={"clip_id": rec.id, "final_id": f.id, "recipe": recipe.model_dump(), "render": stats},
                                    timings={"wall_s": q.wall_s()}, parents=parents, lineage_kind="final", frames=rec.frames, w=rec.w, h=rec.h,
                                    variant=job.variant, origin=job.origin)
    asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, clips.frame_path(rec.id, 0))
    rec.asset_id = asset.id
    clips.save(rec)
    shutil.rmtree(tmp, ignore_errors=True)
    await asyncio.to_thread(cs.set_render, f.id, rec.id, c.revision, job.id)
    f = await asyncio.to_thread(store.set_clip, f.id, rec.id)
    q.hub.broadcast("asset.created", asset.model_dump())
    job.result["asset_ids"] = [asset.id]
    job.result["clip_id"] = rec.id
    q.hub.broadcast("clip.ready", {"clip_id": rec.id, "asset_id": asset.id, "job_id": job.id, "frames": rec.frames, "fps": rec.fps, "w": rec.w, "h": rec.h,
                                   "origin": job.origin.model_dump() if job.origin else None})
    q.hub.broadcast("final.updated", {"id": f.id, "revision": f.revision})
    await asyncio.to_thread(_final_take, q, f, rec.id, None, _run(job, recipe, q))       # the finished shot: it fills an empty clip slot
    return True


async def run_render(job: JobRecord, recipe: Render, q: JobQueue) -> bool:
    """P17 (D83): the sequence as a Catalogue clip — every lane tick read from the clips' PNG masters (exact, not the proxies), two
    frames blended through a dissolve, frames mapped by nearest frame where a clip's rate differs from the lane's (D27: no conform
    here), at the first clip's size and the lane's fps; then the clip pipeline as for an i2v job (master, proxy, asset, lineage to
    every source clip's asset, `clip.ready`)."""
    if recipe.movie:
        return await run_movie(job, recipe, q)
    store, clips = TimelineStore(q.ws), ClipStore(q.ws)
    tl = await asyncio.to_thread(store.get, recipe.timeline_id)
    if tl is None:
        raise ValueError(f"sequence {recipe.timeline_id} is not in the project")
    recs = {c.id: c for c in await asyncio.to_thread(clips.list)}
    missing = [c.clip_id for c in tl.clips if c.clip_id not in recs]
    if missing:
        raise ValueError(f"clips missing from the project: {', '.join(missing)}")
    fc = getattr(q, "filmcraft", None)
    if tl.file and fc is not None and fc.available():                # CE2 (30 §12): a FilmCraft cut's draft is its own export, to PNG
        paths, t0 = await _draft_frames_filmcraft(job, q, tl)
        return await _draft_clip(job, recipe, q, tl, recs, paths, t0)
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
    return await _draft_clip(job, recipe, q, tl, recs, paths, t0)


async def _draft_clip(job: JobRecord, recipe: Render, q: JobQueue, tl: Any, recs: dict, paths: list[Path], t0: float) -> bool:
    """The draft's frames as a clip (master, proxy, asset with lineage to every source clip, `clip.ready`) — P17's tail, shared with CE2's
    FilmCraft draft."""
    clips = ClipStore(q.ws)
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


async def _draft_frames_filmcraft(job: JobRecord, q: JobQueue, tl: Any) -> tuple[list[Path], float]:
    """CE2: a FilmCraft cut's draft frames — `filmcraft-cli run` exports the saved project as a PNG sequence at draft size (the longer
    side 960) in a process of its own (software decoding, D97), cancellable."""
    import re

    from ..filmcraft import export_argv, export_script
    from ..fsio import utc_now
    from ..trainer import _kill
    from .supervisor import _assign_to_job
    project = TimelineStore(q.ws).export_dir(tl.id) / tl.file
    tmp = q.ws.temp_dir / f"render-{job.id}"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "png").mkdir(parents=True)
    script = tmp / "export.jsonl"
    script.write_text(export_script(tmp / "png" / "frame.png", "png", tl.fps, scale=round(min(1.0, 960 / max(tl.w, tl.h)), 4)), encoding="utf-8")
    argv = export_argv(q.app.settings.filmcraft, q.app, project, script)
    log_path = q.app.logs_dir / f"render-{job.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log_path.open("ab") as lf:
        lf.write(f"==== launch {utc_now()} job {job.id} {' '.join(argv)}\n".encode("utf-8"))
        lf.flush()
        proc = subprocess.Popen(argv, stdout=lf, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        _assign_to_job(proc)
    q.progress(job, "rendering the draft (FilmCraft)")
    while proc.poll() is None:
        await asyncio.sleep(0.3)
        if job.id in q._cancel_requested:
            _kill(proc.pid)
            await asyncio.to_thread(proc.wait)
            q.check_cancel(job)
    paths = sorted((tmp / "png").glob("*.png"), key=lambda x: int(re.sub(r"\D", "", x.stem) or 0))
    if proc.returncode != 0 or not paths:
        tail = log_path.read_text(encoding="utf-8", errors="replace").strip()[-400:]
        raise ValueError(f"filmcraft-cli draft export failed ({proc.returncode}): {tail}")
    job.log_tail.append(f"render (FilmCraft): {len(paths)} frames @ {tl.fps} fps in {time.time() - t0:.1f} s (CPU)")
    return paths, t0


MOVIE_SR = 48_000


def _movie_audio(tl: Any, cues_of: Any, total: int) -> tuple[np.ndarray, int]:
    """RC3: the voice lane as one mono track at 48 kHz — each lane clip's spoken lines (`cues_of(clip)`: {path, duration_s} or None per line)
    where the exports place them (`line_spans`: laid evenly across the clip), resampled and summed, clipped to ±1. Returns the samples and
    the number of lines placed."""
    import soundfile as sf
    from ..timelines import line_spans, ticks
    out = np.zeros(int(round(total / tl.fps * MOVIE_SR)), dtype=np.float32)
    s = starts(tl)
    placed = 0
    for i, c in enumerate(tl.clips):
        cues = cues_of(c) or []
        for (a0, _), cue in zip(line_spans(ticks(tl, c), len(cues)), cues):
            if not cue or not cue.get("path"):
                continue
            data, sr = sf.read(cue["path"], dtype="float32", always_2d=True)
            mono = data.mean(axis=1)
            if sr != MOVIE_SR and len(mono) > 1:
                n = int(round(len(mono) * MOVIE_SR / sr))
                mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono).astype(np.float32)
            at0 = int(round((s[i] + a0) / tl.fps * MOVIE_SR))
            if at0 >= len(out):
                continue
            seg = mono[: len(out) - at0]
            out[at0:at0 + len(seg)] += seg
            placed += 1
    return np.clip(out, -1.0, 1.0), placed


async def run_movie(job: JobRecord, recipe: Render, q: JobQueue) -> bool:
    """RC3 (D96, proto01_animate 29): the cut as a movie — every lane tick from the clips' PNG masters, a 16 fps clip on a 24 fps lane
    conformed by RIFE v4.6 (D27, D102) when the local tool is there (else the nearest frame, as the draft), each frame fitted into the cut's
    w × h (the project format; letterboxed, Lanczos), dissolves blended; the spoken lines mixed into one track where the exports place them;
    H.264 + AAC in one MP4 in the cut's folder (`timelines/<id>/<cut>/<cut>.mp4`, beside the Resolve export) and a Catalogue video with
    lineage to every clip. A CPU job (RIFE runs on its own, one job at a time, D97)."""
    from fractions import Fraction

    import av

    from ..final_assembly import conform_24, rife_binary
    from ..fsio import slugify
    from ..timelines import story_lookup
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
    fc = getattr(q, "filmcraft", None)
    if tl.file and fc is not None and fc.available():                  # CE1 (D126 #5): the cut is a FilmCraft project — its own export
        return await run_movie_filmcraft(job, recipe, q, tl, recs)
    s = starts(tl)
    W, H = tl.w - tl.w % 2, tl.h - tl.h % 2
    tmp = q.ws.temp_dir / f"movie-{job.id}"
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    # the conform: each 16 fps clip on a 24 fps lane, once (the RIFE frames cached for the whole render)
    conformed: dict[str, list[Path]] = {}
    if tl.fps == 24 and rife_binary() is not None:
        for cid in dict.fromkeys(c.clip_id for c in tl.clips):
            rec = recs[cid]
            if rec.fps == 16:
                q.progress(job, f"conforming {cid} to 24 fps (RIFE)")
                got = await asyncio.to_thread(conform_24, clips.frame_path(cid, 0).parent, tmp / "conform" / cid, rec.frames)
                if got:
                    conformed[cid] = got
    job.log_tail.append(f"movie: {len(conformed)} clip(s) conformed to 24 fps by RIFE" if conformed else "movie: no RIFE conform (the nearest frame where a clip's rate differs)")
    cache: dict[tuple[str, int], np.ndarray] = {}

    def picture(k: int, f: int, local: int) -> np.ndarray:
        c = tl.clips[k]
        conf = conformed.get(c.clip_id)
        if conf is not None:                                                     # the conformed sequence at the lane's rate
            i = min(len(conf) - 1, round(c.in_ * 24 / 16) + (f - s[k]))
            path, key = conf[i], (c.clip_id + ":24", i)
        else:
            path, key = clips.frame_path(c.clip_id, local), (c.clip_id, local)
        arr = cache.get(key)
        if arr is None:
            with Image.open(path) as im:
                im = im.convert("RGB")
                scale = min(W / im.width, H / im.height)
                fw, fh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
                canvas = Image.new("RGB", (W, H), (0, 0, 0))
                canvas.paste(im.resize((fw, fh), Image.LANCZOS), ((W - fw) // 2, (H - fh) // 2))
                arr = np.asarray(canvas, dtype=np.float32)
            if len(cache) > 8:
                cache.pop(next(iter(cache)))
            cache[key] = arr
        return arr

    def frame_at(f: int) -> np.ndarray:
        what = at(tl, f, s)
        assert what is not None
        (ka, la), b, mix = what
        img = picture(ka, f, la)
        if b is not None:
            img = img * (1.0 - mix) + picture(b[0], f, b[1]) * mix
        return np.ascontiguousarray(np.clip(img + 0.5, 0, 255).astype(np.uint8))

    _, _, cues_of = await asyncio.to_thread(story_lookup, q.ws, q.catalogue)
    audio, placed = await asyncio.to_thread(_movie_audio, tl, cues_of, total)
    folder = store.export_dir(tl.id) / slugify(tl.name, "sequence")
    folder.mkdir(parents=True, exist_ok=True)
    out, part = folder / f"{slugify(tl.name, 'sequence')}.mp4", tmp / "movie.tmp.mp4"
    first_png = tmp / "first.png"

    def encode() -> None:
        with av.open(str(part), "w", format="mp4", options={"movflags": "+faststart"}) as container:
            vs = container.add_stream("libx264", rate=tl.fps)
            vs.width, vs.height, vs.pix_fmt = W, H, "yuv420p"
            vs.options = {"crf": "18", "preset": "medium"}
            ast = None
            if placed:
                ast = container.add_stream("aac", rate=MOVIE_SR)
                ast.layout = "mono"
            for f in range(total):
                if f % max(1, tl.fps) == 0:
                    q.check_cancel(job)
                    job.progress = f / total
                    q.progress(job, f"rendering {f}/{total}")
                arr = frame_at(f)
                if f == 0:
                    Image.fromarray(arr).save(first_png)
                for pkt in vs.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                    container.mux(pkt)
            for pkt in vs.encode():
                container.mux(pkt)
            if ast is not None:
                for i in range(0, len(audio), 1024):
                    af = av.AudioFrame.from_ndarray(np.ascontiguousarray(audio[i:i + 1024].reshape(1, -1)), format="fltp", layout="mono")
                    af.sample_rate, af.pts, af.time_base = MOVIE_SR, i, Fraction(1, MOVIE_SR)
                    for pkt in ast.encode(af):
                        container.mux(pkt)
                for pkt in ast.encode():
                    container.mux(pkt)
        part.replace(out)
    await asyncio.to_thread(encode)
    q.check_cancel(job)
    secs = round(time.time() - t0, 1)
    job.log_tail.append(f"movie: {total} frames at {W}×{H} @ {tl.fps} fps, {placed} spoken line(s), in {secs} s → {out.relative_to(q.ws.path).as_posix()}")
    parents = list(dict.fromkeys(recs[c.clip_id].asset_id for c in tl.clips if recs[c.clip_id].asset_id))
    asset = await asyncio.to_thread(q.catalogue.ingest_file, out, kind="video", move=False, job_id=job.id, batch_id=job.batch_id, suite="animate", model_id="movie",
                                    seed=job.seed, prompt_text=tl.name, params={"recipe": recipe.model_dump(), "timeline_id": tl.id, "revision": tl.revision, "movie": True,
                                                                                 "conformed": sorted(conformed), "lines": placed},
                                    timings={"wall_s": q.wall_s(), "render_s": secs}, parents=parents, lineage_kind="render", frames=total, w=W, h=H,
                                    variant=job.variant, origin=job.origin)
    asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, first_png)
    q.hub.broadcast("asset.created", asset.model_dump())
    job.result["asset_ids"] = [asset.id]
    job.result["path"] = out.relative_to(q.ws.path).as_posix()
    job.result["lines"] = placed
    job.result["revision"] = tl.revision
    job.result["file"] = str(out)                                                  # the absolute path, for Reveal the movie
    shutil.rmtree(tmp, ignore_errors=True)
    return True


async def run_movie_filmcraft(job: JobRecord, recipe: Render, q: JobQueue, tl: Any, recs: dict) -> bool:
    """CE1 (proto01_animate 30 §10, D126 #5): the movie of a cut whose file is a FilmCraft project — FilmCraft's own export, run by loom2.
    First each 16 fps take on a 24 fps cut is conformed once by RIFE v4.6 (D27; FilmCraft repeats frames), cached beside its master
    (`clips/<id>/conform24/`), and swapped into the project for its proxy through the session (`clip.replaceFromBin`, the source in kept);
    then `filmcraft-cli run` exports the saved project in a process of its own (software decoding, D97) to H.264 + AAC; the file goes to the
    cut's folder and a copy to the Catalogue with lineage to every clip, as RC3's movie."""
    from ..cuts import lines as cut_lines
    from ..cuts import read
    from ..filmcraft import export_argv, export_script, prefs
    from ..final_assembly import conform_24, rife_binary
    from ..fsio import slugify, utc_now
    from ..trainer import _kill
    from .supervisor import _assign_to_job
    from ..cuts import Cuts
    from ..timelines import story_lookup
    fc, store, clips = q.filmcraft, TimelineStore(q.ws), ClipStore(q.ws)
    project = store.export_dir(tl.id) / tl.file
    t0 = time.time()
    name_of, _, audio_of = await asyncio.to_thread(story_lookup, q.ws, q.catalogue)
    synced = await asyncio.to_thread(Cuts(q.ws, fc, audio_of, name_of).sync_lines, tl)     # a line voiced since the cut was made is in the movie
    if synced:
        job.log_tail.append(f"movie (FilmCraft): {synced} spoken line(s) brought onto A1")
    conformed: list[str] = []
    if tl.fps == 24 and rife_binary() is not None:
        await asyncio.to_thread(fc.open, project)
        doc = await asyncio.to_thread(read, project)
        its = doc["project"]["items"]
        seq = next(it["kind"]["Sequence"] for it in its.values() if "Sequence" in it["kind"])
        v1 = seq["video_tracks"][0]["items"] if seq["video_tracks"] else []
        for k, it in list(its.items()):
            meta = it.get("metadata", {})
            cid = meta.get("loom2.clip")
            if meta.get("loom2.media") != "proxy" or meta.get("loom2.fps") != "16" or cid not in recs:
                continue
            rec, dst = recs[cid], q.ws.path / "clips" / cid / "conform24"
            got = sorted(dst.glob("*.png"))
            if len(got) != round((rec.frames - 1) * 24 / 16) + 1:
                q.progress(job, f"conforming {cid} to 24 fps (RIFE)")
                got = await asyncio.to_thread(conform_24, clips.frame_path(cid, 0).parent, dst, rec.frames) or []
                if not got:
                    continue
            q.check_cancel(job)
            r = await asyncio.to_thread(fc.batch, [{"id": "prefs.set", "params": {"values": prefs(24)}},                    # RIFE numbers from 1: the first it wrote
                                                   {"id": "file.import", "params": {"paths": [str(got[0])], "imageSequence": True}}])
            new = int(r[1]["items"][0])
            uses = [ti["id"] for ti in v1 if ti["item"] == int(k)]
            steps = [{"id": "metadata.set", "params": {"item": new, "fields": {**meta, "loom2.media": "conform24"}}}]
            if uses:
                steps.append({"id": "clip.replaceFromBin", "params": {"clips": uses, "item": new, "keepSourceIn": True}})
            steps.append({"id": "project.delete", "params": {"items": [int(k)]}})
            await asyncio.to_thread(fc.batch, steps)
            conformed.append(cid)
        if conformed:
            await asyncio.to_thread(fc.save)
    job.log_tail.append(f"movie (FilmCraft): {len(conformed)} take(s) conformed to 24 fps by RIFE and swapped in" if conformed
                        else "movie (FilmCraft): nothing to conform (no 16 fps proxy on the cut, or no RIFE)")
    tmp = q.ws.temp_dir / f"movie-{job.id}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    part, script = tmp / "movie.mp4", tmp / "export.jsonl"
    lufs = q.app.settings.audio.loudness_lufs                        # CE3: the movie normalised (D127: Settings › Audio › loudness)
    script.write_text(export_script(part, "h264", tl.fps, **({"loudnessLufs": lufs} if lufs is not None else {})), encoding="utf-8")
    argv = export_argv(q.app.settings.filmcraft, q.app, project, script)
    log_path = q.app.logs_dir / f"movie-{job.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as lf:
        lf.write(f"==== launch {utc_now()} job {job.id} {' '.join(argv)}\n".encode("utf-8"))
        lf.flush()
        proc = subprocess.Popen(argv, stdout=lf, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        _assign_to_job(proc)
    job.log_tail.append(f"filmcraft-cli export pid {proc.pid}")
    q.progress(job, "exporting the movie (FilmCraft)")
    while proc.poll() is None:
        await asyncio.sleep(0.5)
        if job.id in q._cancel_requested:
            _kill(proc.pid)
            await asyncio.to_thread(proc.wait)
            q.check_cancel(job)
    if proc.returncode != 0 or not part.is_file():
        tail = log_path.read_text(encoding="utf-8", errors="replace").strip()[-400:]
        raise ValueError(f"filmcraft-cli export failed ({proc.returncode}): {tail}")
    slug = slugify(tl.name, "sequence")
    folder = store.export_dir(tl.id) / slug
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{slug}.mp4"
    part.replace(out)
    secs = round(time.time() - t0, 1)
    placed = len(cut_lines(await asyncio.to_thread(read, project)))

    def first_frame() -> Path:
        import av
        with av.open(str(out)) as c:
            img = next(c.decode(video=0)).to_image()
        p = tmp / "first.png"
        img.save(p)
        return p
    first_png = await asyncio.to_thread(first_frame)
    W, H, total = await asyncio.to_thread(_video_size, out)
    job.log_tail.append(f"movie (FilmCraft): {total} frames at {W}×{H} @ {tl.fps} fps, {placed} spoken line(s), in {secs} s → {out.relative_to(q.ws.path).as_posix()}")
    parents = list(dict.fromkeys(recs[c.clip_id].asset_id for c in tl.clips if recs[c.clip_id].asset_id))
    asset = await asyncio.to_thread(q.catalogue.ingest_file, out, kind="video", move=False, job_id=job.id, batch_id=job.batch_id, suite="animate", model_id="movie",
                                    seed=job.seed, prompt_text=tl.name, params={"recipe": recipe.model_dump(), "timeline_id": tl.id, "revision": tl.revision, "movie": True,
                                                                                 "engine": "filmcraft", "conformed": sorted(conformed), "lines": placed},
                                    timings={"wall_s": q.wall_s(), "render_s": secs}, parents=parents, lineage_kind="render", frames=total, w=W, h=H,
                                    variant=job.variant, origin=job.origin)
    asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset, first_png)
    q.hub.broadcast("asset.created", asset.model_dump())
    job.result.update({"asset_ids": [asset.id], "path": out.relative_to(q.ws.path).as_posix(), "lines": placed, "revision": tl.revision, "file": str(out),
                       "engine": "filmcraft", "loudness_lufs": lufs})
    shutil.rmtree(tmp, ignore_errors=True)
    return True


def _video_size(path: Path) -> tuple[int, int, int]:
    """A movie's width, height and frame count."""
    import av
    with av.open(str(path)) as c:
        v = c.streams.video[0]
        return v.codec_context.width, v.codec_context.height, v.frames or sum(1 for _ in c.decode(video=0))


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
