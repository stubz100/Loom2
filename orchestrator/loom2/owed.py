"""D164 (E45, journal 2026-10-30): what a final still owes and what it costs. That is its plate, each character layer not performed yet,
and per character layer its face work:

- the face pass (D118: the head at 512², pasted back), for a head in the band where it gains a face;
- lip-sync, for the voiced lines on its lane.

*Perform the owed layers ▶* queues them in turn. A layer performed with `then_owed` has its face work queued after its matte (the matte
finisher calls `follow_up`). A layer re-taken retires its takes, so its face work is owed again.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .config import Settings
    from .finals import Final, FinalLayer, FinalStore
    from .queue import JobQueue
    from .workspace import Workspace

FACE_BAND = (48.0, 78.0)      # E45: the head box's side in the frame (2.6 × nose–neck, px) where the face pass gains a face — 55 px gained
                              # +0.24 FaceSim over its window take, 110 px +0.05 (78: their geometric mean); 11 px pasted a giant bust,
                              # so below heads.MIN_SIDE (the crop no longer the head) it is not owed
IN_FRAME = 0.8                # the head inside the frame on at least this share of the layer's frames (the box is tracked there)
FACING = 0.5                  # … and facing the camera on at least this share (D158; from behind the pass paints a stranger's face, E45 B2)
PLATE_SECONDS = 60.0          # U6c: the plate's still, Stage's picture or a Klein shot (≈ 1 min)
FACE_PRESETS = ("face", "lipsync")


def head_stats(kps: list, w: int, h: int) -> dict[str, float]:
    """The head as the face pass would track it, over the layer's frames.

    - `px`: the median head-box side in the frame, without heads.MIN_SIDE's floor;
    - `in_frame`: the share of frames whose head centre lies inside the frame;
    - `facing`: the share of frames facing the camera (finals.faces_away).

    Stage projects every point, in the frame or not, so the coordinates are read whatever the flags say.
    """
    from .finals import faces_away
    sides, inside, facing, n = [], 0, 0, 0
    for k in kps or []:
        a = np.asarray(k, dtype=float).reshape(-1, 3) if k else None
        if a is None or len(a) < 18:
            continue
        n += 1
        c = a[[0, 14, 15, 16, 17], :2].mean(axis=0)
        if 0 <= c[0] < w and 0 <= c[1] < h:
            inside += 1
            sides.append(max(2.6 * float(np.hypot(*(a[0, :2] - a[1, :2]))), 1.8 * float(np.hypot(*(a[16, :2] - a[17, :2])))))
        facing += not faces_away(k)
    return {"px": round(float(np.median(sides)), 1) if sides else 0.0, "in_frame": round(inside / max(1, n), 3), "facing": round(facing / max(1, n), 3)}


def face_fit(stats: dict[str, float]) -> str:
    """Where a head stands against the band: `band` (the face pass gains a face), `large` (Wan Animate draws it well enough; lip-sync
    still moves its mouth), `small` (no pass can show a face there), `away` (seen from behind) or `out` (outside the frame)."""
    lo, hi = FACE_BAND
    if stats["in_frame"] < IN_FRAME:
        return "out"
    if stats["facing"] < FACING:
        return "away"
    return "small" if stats["px"] < lo else "large" if stats["px"] > hi else "band"


FIT_WHY = {"small": "its head is too small to show a face", "away": "it is seen from behind", "out": "its head is outside the frame"}


def current_takes(layer: "FinalLayer") -> list[dict[str, Any]]:
    """The takes made on the layer's current performance (a re-take retires the others, `stale`)."""
    return [t for t in layer.takes if not t.get("stale")]


def face_recipe(ws: "Workspace", settings: "Settings", store: "FinalStore", f: "Final", layer: "FinalLayer", preset: str, mouth: str = "head",
                seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """The face pass's first step (AE4c), as the route and the matte finisher's follow-up queue it: the recipe and the origin's payload.
    ValueError names what is missing (keypoints, the matte, a line on the layer, the model)."""
    from .compositions import CompositionStore
    from .fsio import new_id
    from .models import registry
    if layer.kind != "figure":
        raise ValueError("the face pass renders a character's head: run it on a character layer")
    if not layer.keypoints:
        raise ValueError(f"{layer.name} has no keypoints — the face pass tracks the head from the Stage's")
    if len(list(store.pass_dir(f.id, layer.id, "matte").glob("*.png"))) != f.frames:
        raise ValueError(f"{layer.name} has no matte yet — matte it first")
    variant = settings.variant
    animate = next((s for s in registry.animate_specs() if registry.offered(s, variant)), None)
    if animate is None:
        raise ValueError("no pose-driven model in this build")
    model_id, stage = animate.id, "head"
    if preset == "lipsync":
        cs = CompositionStore(ws)
        c = cs.get(f)
        lines = [t for t in (cs.audio_timing(f, c) if c else []) if t.get("final_layer") == layer.id]
        if not lines:
            raise ValueError(f"attach a line to {layer.name} first (Layers › Attach a line…) — Lip-sync follows the lines on the layer")
        if mouth == "model":                                              # AE4d: the lip-sync model on the rendered heads — no talking head first
            from .lipsync import lipsync_available
            why = lipsync_available(settings)
            if why:
                raise ValueError(why)
        else:
            s2v = next((s for s in registry.lipsync_specs() if registry.offered(s, variant)), None)
            if s2v is None:
                raise ValueError("no lip-sync model in this build")
            model_id, stage = s2v.id, "face_video"
    store.sweep_unfinished(f.id, layer.id)
    take_id = new_id("take")
    recipe = {"kind": "layer_pass", "final_id": f.id, "layer_id": layer.id, "preset": preset, "strength": 0.10, "seeds": [layer.seed if seed is None else seed],
              "scope": "layer", "model_id": model_id, "step": {"take_id": take_id, "stage": stage, "k": 0}, "mouth": mouth if preset == "lipsync" else "head"}
    payload = {"layer": layer.id, "pass": preset, "strength": 0.10, "scope": "layer", "take": take_id, "mouth": mouth}
    return recipe, payload


def _busy(q: "JobQueue | None", layer: "FinalLayer", skip: str | None = None) -> bool:
    """A face pass or a matte of the layer is queued or running now (the matte's finisher queues the face work it was asked for);
    `skip`: the job asking (a matte whose finisher follows up)."""
    jobs = q.jobs if q is not None else {}
    return any(j.id != skip and j.status in ("queued", "running", "staged") and (j.recipe.get("kind") == "matte_sequence" or (j.recipe.get("kind") == "layer_pass" and j.recipe.get("preset") in FACE_PRESETS))
               for j in (jobs.get(i) for i in layer.job_ids) if j is not None)


def _seconds(q: "JobQueue | None", f: "Final", layer: "FinalLayer", preset: str, windows: int) -> float | None:
    """The face work's cost, by the queue's estimate of its steps (D60): a talking head per line window for lip-sync, then the head
    batches."""
    from .finals import plan_batches
    from .models import registry
    from .recipes import parse_recipe
    if q is None:
        return None
    variant = q.app.settings.variant
    animate = next((s for s in registry.animate_specs() if registry.offered(s, variant)), None)
    s2v = next((s for s in registry.lipsync_specs() if registry.offered(s, variant)), None)
    if animate is None:
        return None

    def step(model_id: str, stage: str) -> float:
        r = {"kind": "layer_pass", "final_id": f.id, "layer_id": layer.id, "preset": preset, "model_id": model_id, "step": {"take_id": "take_est", "stage": stage, "k": 0}}
        try:
            return float(q.estimate(parse_recipe(r)).get("seconds") or 0.0)
        except Exception:                                                 # noqa: BLE001 — a cost is advice, never a failure
            return 0.0
    total = len(plan_batches(f.frames)) * step(animate.id, "head")
    if preset == "lipsync" and s2v is not None:
        total += windows * step(s2v.id, "face_video")
    return round(total, 1) or None


def layer_owed(ws: "Workspace", q: "JobQueue | None", store: "FinalStore", f: "Final", layer: "FinalLayer", voiced: list[dict[str, Any]],
               timing: list[dict[str, Any]] | None, skip: str | None = None) -> dict[str, Any] | None:
    """The character layer's face work, or None (nothing owed). `voiced` lists the shot's voiced lines its character speaks (the story's);
    `timing` lists the lines on its lane (the composition's), or None when there is no composition yet. The item says whether *Perform
    the owed layers ▶* queues it now (`queue`), after the layer's performance (`after`), or only lists it (`why`)."""
    from .heads import windows
    if layer.kind != "figure" or not layer.keypoints or _busy(q, layer, skip):
        return None
    if layer.head_keys == []:                                             # D165: its head box removed by hand — no face work
        return None
    done = {t.get("preset") for t in current_takes(layer)}
    fit = "band" if layer.head_keys else face_fit(head_stats(store.keypoints(f.id, layer.id), f.size["w"], f.size["h"]))   # D165: set by hand, asked for
    after = layer.status != "done"
    item: dict[str, Any] = {"layer": layer.id, "name": layer.name, "after": after, "queue": True, "why": None, "seconds": None}
    if voiced or timing:                                                  # the character speaks in the shot: lip-sync makes its head (no face pass first)
        if "lipsync" in done:
            return None
        item["kind"] = "lipsync"
        longest = 77 / max(1, f.rate)                                     # one talking head's window (77 frames: 4.8 s at 16 fps)
        lines = timing or []
        if fit not in ("band", "large"):
            item.update(queue=False, why=FIT_WHY[fit])
        elif not lines:
            item.update(queue=False, why="its lines go on the lanes at Final")
        elif any(float(t.get("out", 0.0)) - float(t.get("in", 0.0)) > longest + 1e-6 for t in lines):
            item.update(queue=False, why=f"a line is longer than {longest:.1f} s — Lip-sync it from the layer's passes")
        item["seconds"] = _seconds(q, f, layer, "lipsync", len(windows(lines, f.rate, f.frames)) or len(voiced))
        return item
    if fit != "band" or done & set(FACE_PRESETS):
        return None
    item["kind"] = "face"
    item["seconds"] = _seconds(q, f, layer, "face", 0)
    return item


def voiced_by_layer(ws: "Workspace", f: "Final") -> dict[str, list[dict[str, Any]]]:
    """The voiced lines of the Dialogue nodes bound to the final's Story shot, by the layer their speaker performs (routes: GET
    /finals/{fid}/lines reads the same)."""
    from .story import StoryStore, has_lines
    store = StoryStore(ws)
    shots = {f.shot_id} if f.shot_id else {s.id for s in store.shots() if s.version().stage_id == f.stage_id and s.version().camera_id == f.camera_id}
    out: dict[str, list[dict[str, Any]]] = {}
    if not shots:
        return out
    for n in store.flow_nodes().values():
        if not has_lines(n) or n.shot_id not in shots:
            continue
        for ln in n.lines:
            layer = next((x.id for x in f.layers if x.kind == "figure" and ln.speaker and x.profile_id == ln.speaker), None)
            if layer and ln.audio_asset_id:
                out.setdefault(layer, []).append({"text": ln.text, "audio_asset_id": ln.audio_asset_id})
    return out


def owed_work(ws: "Workspace", q: "JobQueue | None", f: "Final", perform_seconds: dict[str, float] | None = None, skip: str | None = None) -> list[dict[str, Any]]:
    """Every item the final owes, in the order the queue takes them: the plate, the performances, then the face work (the face pass for
    a head in the band, lip-sync for a speaking character). `perform_seconds` is each layer's cost still owed (GET /finals/{fid}/plan);
    `skip` a job not to count as under way (the matte whose finisher asks)."""
    from .compositions import CompositionStore
    from .finals import FinalStore
    store = FinalStore(ws)
    owes = ("passes", "failed")
    items: list[dict[str, Any]] = []
    plate = next((x for x in f.layers if x.kind == "plate"), None)
    if plate is not None and plate.status in owes:
        items.append({"kind": "plate", "layer": plate.id, "name": plate.name, "after": False, "queue": True, "why": None, "seconds": PLATE_SECONDS})
    figures = [x for x in f.layers if x.kind == "figure"]
    for x in figures:
        if x.status in owes:
            items.append({"kind": "perform", "layer": x.id, "name": x.name, "after": False, "queue": True, "why": None, "seconds": (perform_seconds or {}).get(x.id)})
    cs = CompositionStore(ws)
    c = cs.get(f)
    timing = cs.audio_timing(f, c) if c else None
    try:
        voiced = voiced_by_layer(ws, f)
    except Exception:                                                     # noqa: BLE001 — a final outside the story owes no lip-sync
        voiced = {}
    for x in figures:
        it = layer_owed(ws, q, store, f, x, voiced.get(x.id, []), [t for t in timing if t.get("final_layer") == x.id] if timing is not None else None, skip)
        if it is None:
            continue
        if it["after"] and x.then_owed and x.status not in owes:          # already asked: queued after the performance under way
            it.update(queue=False, why="queued after its performance")
        items.append(it)
    return items


async def queue_face_work(q: "JobQueue", f: "Final", layer: "FinalLayer", preset: str, flush: bool = True) -> str:
    """The layer's face pass or lip-sync queued (its first step; the chain follows), the job recorded on the layer. ValueError: refused.
    A finisher passes `flush=False` (the queue persists after it)."""
    import asyncio
    from .finals import FINAL_LAYER_SURFACE, FinalStore
    from .origin import JobOrigin
    store = FinalStore(q.ws)
    recipe, payload = await asyncio.to_thread(face_recipe, q.ws, q.app.settings, store, f, layer, preset)
    jobs = q.submit(recipe, origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id, payload=payload))
    if flush:
        await q.flush()
    f2 = await asyncio.to_thread(store.add_job, f.id, layer.id, jobs[0].id)
    q.hub.broadcast("final.updated", {"id": f.id, "revision": f2.revision})
    return jobs[0].id


async def follow_up(q: "JobQueue", fid: str, lid: str, skip: str | None = None) -> str | None:
    """D164: after a layer's last matte (`skip`, the matte's job), the face work its owed run asked for (`then_owed`) — queued when it is
    still owed and can be; a sentence for the job's log."""
    import asyncio
    from .finals import FinalStore
    store = FinalStore(q.ws)
    f = await asyncio.to_thread(store.get, fid)
    layer = next((x for x in f.layers if x.id == lid), None) if f else None
    if f is None or layer is None or not layer.then_owed:
        return None
    f = await asyncio.to_thread(store.update_layer, fid, lid, then_owed=False)
    layer = next(x for x in f.layers if x.id == lid)
    it = await asyncio.to_thread(lambda: next((x for x in owed_work(q.ws, q, f, skip=skip) if x["layer"] == lid and x["kind"] in FACE_PRESETS), None))
    if it is None:
        return f"{layer.name}: no face work owed"
    if not it["queue"]:
        return f"{layer.name}: {it['kind']} listed, not queued — {it['why']}"
    try:
        jid = await queue_face_work(q, f, layer, it["kind"], flush=False)
    except ValueError as e:
        return f"{layer.name}: {it['kind']} not queued — {e}"
    return f"{layer.name}: {'the face pass' if it['kind'] == 'face' else 'lip-sync'} queued after its matte ({jid})"
