"""RC1 (D96; proto01_animate 28): a Shot version's recipe as a graph — built on request from the records, nothing stored, as RC0's state is.

RC0's record keeps the runs of the jobs made for the shot (the frame, the clip, the lip-sync). A clay final shot's work lives elsewhere: the
final's record (the plate, a layer per figure or Cast prop, the assembly), its composition (the edits, the render), the stage (the figures,
their keys, the camera) and the Cast (each character's version, hero and animation reference). The graph joins them: one node per thing
the shot is made of, an edge where a step reads another, each node done, stale (with why), owed, running or none (optional and unused);
stale spreads along the edges ("after <node>") as RC0's does.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

NodeState = Literal["done", "stale", "owed", "running", "none"]
FRAME_KINDS = ("t2i", "i2i", "inpaint", "reangle", "upscale", "stage_shot")
_RC0 = {"fresh": "done", "stale": "stale", "missing": "owed", "planned": "owed"}


class GraphNode(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str                                        # character:<pid> · anim_ref:<pid> · place:<pid> · lines · stage · motion:<object> · camera ·
    kind: str                                      #   step:<frame|clip|lipsync> · plate · layer:<lid> · composition · finish · take
    label: str
    sub: str | None = None                         # one short line under the label
    state: NodeState = "done"
    reasons: list[str] = Field(default_factory=list)
    thumb: str | None = None                       # an image asset id (a clip's asset for a clip)
    ref: dict[str, str] = Field(default_factory=dict)   # what opens it: profile_id, version, object_id, final_id, layer, node_id, step
    seconds: float | None = None                   # its last run's cost, when known


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, json_schema_serialization_defaults_required=True)
    from_: str = Field(alias="from")
    to: str


class ShotGraph(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    shot_id: str
    version: str
    route: str                                     # the recipe template (clay when a final shot is made for it)
    final_id: str | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stale: int = 0
    owed: int = 0


def _fp(v: Any) -> str:
    import hashlib
    import json
    return hashlib.sha1(json.dumps(v, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


_QUIET = {"name", "locked", "colour_id"}                                      # an object's fields that change nothing it renders


def stage_stamps(stage: Any, camera_id: str) -> dict[str, str]:
    """What a final read of its stage, part by part, when it was made (UX0 W6: an edit marks what depends on it): `camera` (the camera and
    its keys), `set` (the sets, lights and the ambient — the plate's world) and `object:<id>` for each figure and prop (its transform,
    pose, path, binding and keys). A layer goes stale when its own object or the camera changes, the plate when the set or the camera does."""
    keys = stage.keyframes or {}
    cam = next((c for c in stage.cameras if c.id == camera_id), None)
    out = {"camera": _fp([cam.model_dump(exclude={"name"}) if cam else None, (keys.get("camera") or {}).get(camera_id)])}
    world = [o.model_dump(exclude=_QUIET) for o in stage.objects if o.kind in ("set", "light")]
    out["set"] = _fp([world, getattr(stage, "ambient", None)])
    for o in stage.objects:
        if o.kind in ("mannequin", "prop", "mesh", "plane"):
            out[f"object:{o.id}"] = _fp([o.model_dump(exclude=_QUIET), (keys.get("objects") or {}).get(o.id)])
    return out


def final_for(shot_id: str, version: Any, finals: Iterable[Any]) -> Any | None:
    """The final shot a version's graph reads: the newest made for this shot version (a final made before A1 names no version: it counts for
    every version of its shot), else the newest on the version's stage camera that names no other shot."""
    fs = list(finals)
    mine = [f for f in fs if f.shot_id == shot_id and f.shot_version in (None, version.id)]
    if not mine and version.stage_id and version.camera_id:
        mine = [f for f in fs if f.stage_id == version.stage_id and f.camera_id == version.camera_id and f.shot_id in (None, shot_id)]
    return max(mine, key=lambda f: f.created_at) if mine else None


def shot_graph(shot: Any, version: Any, *, rc0: dict[str, Any], node: Any | None, profiles: dict[str, Any], stage: Any | None,
               final: Any | None, composition: Any | None, clip_asset: Callable[[str], str | None], jobs: Iterable[Any] = ()) -> ShotGraph:
    """The graph of one shot version. `rc0`: RC0's state of the version (recipe_state); `node`: the Flow node that binds the shot; `jobs`:
    the queue's queued and running jobs (a node of theirs is running); `clip_asset`: a clip id → its asset id (the pictures)."""
    nodes: dict[str, GraphNode] = {}
    edges: list[tuple[str, str]] = []
    route = rc0["template"]
    if final is not None and not route.startswith("clay"):                        # a final shot made for it: the clay route, by its characters
        route = "clay2" if sum(1 for lay in final.layers if lay.kind == "figure") > 1 else "clay1"
    clay = route.startswith("clay")
    active = [j for j in jobs if getattr(j, "status", None) in ("queued", "running")]

    def add(n: GraphNode) -> GraphNode:
        nodes.setdefault(n.id, n)
        return nodes[n.id]

    def link(a: str, b: str) -> None:
        if a in nodes and b in nodes and (a, b) not in edges:
            edges.append((a, b))

    def version_of(pid: str, vid: str | None) -> Any | None:
        p = profiles.get(pid)
        if p is None:
            return None
        return next((v for v in p.versions if v.id == (vid or p.current)), None)

    # ---- the elements: characters (the node's speakers, the stage's bound figures), props, the place ----
    figures = [o for o in (stage.objects if stage else []) if o.kind == "mannequin" and o.visible]
    bound = {o.profile_id: o.version for o in (stage.objects if stage else []) if o.profile_id and o.visible}
    speakers = [ln.speaker for ln in (node.lines if node else []) if ln.speaker]   # U2 (G5): a Shot's lines
    for pid in list(dict.fromkeys([*speakers, *bound])):
        p = profiles.get(pid)
        if p is None or p.cls not in ("character", "prop"):
            continue
        v = version_of(pid, bound.get(pid) or (node.speaker_versions.get(pid) if node else None))
        add(GraphNode(id=f"character:{pid}", kind="character" if p.cls == "character" else "prop", label=f"{p.name} {v.id if v else ''}".strip(),
                      sub="character" if p.cls == "character" else "prop", state="done" if v and v.hero_asset_id else "owed",
                      reasons=[] if v and v.hero_asset_id else ["no hero yet"], thumb=v.hero_asset_id if v else None,
                      ref={"profile_id": pid, "version": v.id if v else ""}))
        if clay and pid in bound:
            ref_id = v.anim_ref_asset_id if v else None
            add(GraphNode(id=f"anim_ref:{pid}", kind="anim_ref", label="Animation reference", sub=p.name, state="done" if ref_id else "owed",
                          reasons=[] if ref_id else ["the clay route performs from it"], thumb=ref_id, ref={"profile_id": pid, "version": v.id if v else ""}))
            link(f"character:{pid}", f"anim_ref:{pid}")
    place = node.place_id if node and node.place_id in profiles else None
    if place:
        p = profiles[place]
        v = version_of(place, None)
        add(GraphNode(id=f"place:{place}", kind="place", label=p.name, sub="place", state="done" if v and v.hero_asset_id else "owed",
                      thumb=v.hero_asset_id if v else None, ref={"profile_id": place, "version": v.id if v else ""}))
    lines = [ln for ln in (node.lines if node else []) if ln.text.strip()]
    if lines:
        voiced = [ln for ln in lines if ln.audio_asset_id and ln.audio_text == ln.text.strip()]
        changed = [ln for ln in lines if ln.audio_asset_id and ln.audio_text != ln.text.strip()]
        state: NodeState = "done" if len(voiced) == len(lines) else "stale" if changed and len(voiced) + len(changed) == len(lines) else "owed"
        add(GraphNode(id="lines", kind="lines", label="Lines", sub=f"{len(voiced)} of {len(lines)} voiced", state=state,
                      reasons=([f"{len(changed)} changed since voiced"] if changed else []) + ([f"{len(lines) - len(voiced) - len(changed)} not voiced"] if len(voiced) + len(changed) < len(lines) else []),
                      ref={"node_id": node.id}))

    # ---- the stage: its camera and each figure's motion ----
    if stage is not None:
        add(GraphNode(id="stage", kind="stage", label=f"Stage · {stage.name}", sub=f"revision {stage.revision}", ref={"stage_id": stage.id}))
        cam = next((c for c in stage.cameras if c.id == version.camera_id), None)
        if cam is not None:
            ckeys = len((stage.keyframes.get("camera") or {}).get(cam.id) or [])
            add(GraphNode(id="camera", kind="camera", label=f"Camera · {cam.name}", sub=f"{cam.focal_mm:g} mm" + (f" · {ckeys} keys" if ckeys else ""),
                          ref={"stage_id": stage.id, "camera_id": cam.id}))
            link("stage", "camera")
        for o in figures:
            keys = len((stage.keyframes.get("objects") or {}).get(o.id) or [])
            add(GraphNode(id=f"motion:{o.id}", kind="motion", label=f"Motion · {o.name}", sub=f"{keys} keys" if keys else "stands still",
                          state="done" if keys else "none", ref={"stage_id": stage.id, "object_id": o.id}))
            link("stage", f"motion:{o.id}")

    # ---- RC0's steps (the frame, the clip, the lip-sync; the dialogue's voice is the lines node) ----
    rows = {r["id"]: r for r in rc0["steps"]}
    for r in rc0["steps"]:
        if r["id"] not in ("frame", "clip", "lipsync") or (clay and r["state"] in ("missing", "planned")):    # the clay route makes no frame or clip of its own
            continue
        out = (r.get("outputs") or [None])[0]
        thumb = (clip_asset(out) if out and r["id"] != "frame" else out) if out else None
        running = any(getattr(j, "origin", None) and j.origin.surface == "for_shot" and (j.origin.payload or {}).get("shot_id") == shot.id
                      and ((j.kind in FRAME_KINDS) == (r["id"] == "frame")) for j in active)
        add(GraphNode(id=f"step:{r['id']}", kind=r["id"], label=r["label"], sub=r.get("kind"), state="running" if running else _RC0.get(r["state"], "owed"),
                      reasons=[] if running else list(r.get("reasons") or []) + ([f"comes with {r['wave']}"] if r["state"] == "planned" and r.get("wave") else []),
                      thumb=thumb, ref={"step": r["id"]}, seconds=r.get("seconds")))
    for r in rc0["steps"]:
        for i in r.get("inputs") or []:
            link(f"step:{i}", f"step:{r['id']}")
    if "step:frame" in nodes:
        for nid in list(nodes):
            if nid.startswith(("character:", "place:")):
                link(nid, "step:frame")
        link("camera", "step:frame")
    if "step:lipsync" in nodes:
        link("lines", "step:lipsync")

    # ---- the final shot: the plate, a layer per figure or Cast prop, the composition, the finish ----
    head = "step:lipsync" if "step:lipsync" in nodes and rows.get("lipsync", {}).get("state") == "fresh" else "step:clip"
    if final is not None:
        here = stage is not None and stage.id == final.stage_id
        stamped = bool(getattr(final, "stamps", None)) and here
        now = stage_stamps(stage, final.camera_id) if stamped else {}
        moved = here and not stamped and stage.revision > final.stage_revision      # a final made before RC1's stamps: the stage's revision
        why_moved = [f"the stage moved on (revision {final.stage_revision} → {stage.revision})"] if moved else []

        def why_stale(lay: Any) -> list[str]:
            """What changed since the final that this layer read (per part when the final has stamps, else the whole stage)."""
            if not stamped:
                return why_moved
            out = ["the camera moved"] if now.get("camera") != final.stamps.get("camera") else []
            if lay.kind == "plate":
                return out + (["the set changed"] if now.get("set") != final.stamps.get("set") else [])
            key = f"object:{lay.object_id}"
            if lay.object_id and key in final.stamps and now.get(key) != final.stamps[key]:
                out.append(f"{lay.name} is gone from the stage" if key not in now else f"{lay.name} moved or was re-keyed")
            return out
        busy = {j.id for j in active}
        for lay in final.layers:
            if lay.kind not in ("plate", "figure") and not (lay.kind == "prop" and lay.profile_id):
                continue
            running = bool(busy & set(lay.job_ids)) or lay.status in ("queued", "running")
            if running:
                st, why = "running", []
            elif lay.status == "done":
                why = why_stale(lay)
                st = "stale" if why else "done"
            elif lay.status == "failed":
                st, why = "owed", [lay.error or "its job failed"]
            else:
                st, why = "owed", ["not made yet" if lay.kind == "plate" else "not performed yet"]
            nid = "plate" if lay.kind == "plate" else f"layer:{lay.id}"
            last = next((b.get("clip_id") for b in reversed(lay.batches) if b.get("clip_id")), None)
            thumb = lay.still_asset_id if lay.kind == "plate" else (clip_asset(last) if last else None)
            sub = (f"{len(lay.batches)} batch{'es' if len(lay.batches) != 1 else ''}" if lay.batches else None) if lay.kind != "plate" else ("projected" if lay.frames_done else None)
            add(GraphNode(id=nid, kind="plate" if lay.kind == "plate" else "layer", label="Plate" if lay.kind == "plate" else f"{lay.name} layer", sub=sub,
                          state=st, reasons=why, thumb=thumb, ref={"final_id": final.id, "layer": lay.id, **({"object_id": lay.object_id} if lay.object_id else {})}))
            if lay.kind == "plate":
                link("camera", "plate"); link("stage", "plate")
            else:
                if f"anim_ref:{lay.profile_id}" in nodes:
                    link(f"anim_ref:{lay.profile_id}", nid)
                else:
                    link(f"character:{lay.profile_id}", nid)
                link(f"motion:{lay.object_id}", nid); link("camera", nid)
        assembling = any(j.kind == "assemble_final" and (j.recipe or {}).get("final_id") == final.id for j in active)
        c = composition
        sub = f"composed · {c.revision} edit{'s' if c.revision != 1 else ''}" if c else ("assembled" if final.assembled_at else None)
        cst: NodeState = "running" if assembling else ("stale" if (c and c.stale) else "done") if (c or final.assembled_at) else "owed"
        add(GraphNode(id="composition", kind="composition", label="Composition", sub=sub, state=cst,
                      reasons=(["the final changed since it was composed"] if cst == "stale" else []) + ([] if (c or final.assembled_at or assembling) else ["not assembled yet"]),
                      thumb=clip_asset(final.clip_id) if final.clip_id else None, ref={"final_id": final.id}))
        for nid in [n for n in nodes if n == "plate" or n.startswith("layer:")]:
            link(nid, "composition")
        passes = sum(len(lay.takes) for lay in final.layers) + len(final.processing)
        pstale = [k for k, v in ((c.processing_stale if c else {}) or {}).items() if v]
        add(GraphNode(id="finish", kind="finish", label="Finish", sub=f"{passes} pass{'es' if passes != 1 else ''}" if passes else "no pass",
                      state="stale" if pstale else ("done" if passes else "none"),
                      reasons=[f"{len(pstale)} processing layer{'s' if len(pstale) != 1 else ''}: the layers below changed"] if pstale else [], ref={"final_id": final.id}))
        link("composition", "finish")
        head = "finish"

    elif clay:                                                                     # a clay template, nothing made yet: the route's plan
        for nid, label in (("plate", "Plate"), ("composition", "Composition")):
            add(GraphNode(id=nid, kind=nid, label=label, state="owed", reasons=["make the final shot (Animate › Performance)"]))
        for nid in [n for n in nodes if n.startswith(("anim_ref:", "motion:"))] + ["camera"]:
            link(nid, "plate")
        link("plate", "composition")
        head = "composition"

    # ---- the take: the version's clip ----
    rendering = final is not None and any(j.kind == "comp_render" and (j.recipe or {}).get("final_id") == final.id for j in active)
    behind = composition is not None and composition.clip_id is not None and composition.rendered_revision is not None and composition.revision > composition.rendered_revision
    tst: NodeState = "running" if rendering else ("stale" if behind else "done") if version.clip_id else "owed"
    add(GraphNode(id="take", kind="take", label="Take", sub=f"{version.id} · {version.state}", state=tst,
                  reasons=(["edits since the render"] if tst == "stale" else []) + ([] if version.clip_id or rendering else ["no clip yet"]),
                  thumb=clip_asset(version.clip_id) if version.clip_id else None, ref={"step": "take"}))
    link(head if head in nodes else "step:clip", "take")
    if "take" in nodes and not any(b == "take" for _, b in edges) and "step:clip" in nodes:
        link("step:clip", "take")

    # ---- stale spreads along the edges ----
    order = _topo(list(nodes), edges)

    def stale_up(nid: str) -> list[str]:                                        # a node with no part in the shot ("none") passes it on
        out: list[str] = []
        for a, b in edges:
            if b == nid:
                out += [a] if nodes[a].state == "stale" else stale_up(a) if nodes[a].state == "none" else []
        return out
    for nid in order:
        n = nodes[nid]
        if n.state not in ("done", "stale"):
            continue
        up = list(dict.fromkeys(stale_up(nid)))
        if up:
            n.state = "stale"
            n.reasons += [f"after {nodes[a].label.lower()}" for a in up if f"after {nodes[a].label.lower()}" not in n.reasons]
    out = [nodes[i] for i in order]
    return ShotGraph(shot_id=shot.id, version=version.id, route=route, final_id=final.id if final is not None else None, nodes=out,
                     edges=[GraphEdge(from_=a, to=b) for a, b in edges], stale=sum(1 for n in out if n.state == "stale"),
                     owed=sum(1 for n in out if n.state == "owed"))


def _topo(ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """The nodes in an order where every node comes after its inputs (the insertion order among peers)."""
    indeg = {i: 0 for i in ids}
    for _, b in edges:
        indeg[b] += 1
    out: list[str] = []
    ready = [i for i in ids if indeg[i] == 0]
    while ready:
        i = ready.pop(0)
        out.append(i)
        for a, b in edges:
            if a == i:
                indeg[b] -= 1
                if indeg[b] == 0:
                    ready.append(b)
    return out + [i for i in ids if i not in out]


# ---- RC0's list for a clay version, read from the graph (its steps have no runs: the final's records hold them) ----------------------
CLAY_STEPS = {"character": ("character", "prop"), "anim_ref": ("anim_ref",), "motion": ("motion",), "camera": ("camera",), "plate": ("plate",),
              "performance": ("layer",), "composition": ("composition",), "finish": ("finish",), "take": ("take",)}
_ROW = {"done": "fresh", "stale": "stale", "owed": "missing", "running": "fresh", "none": "fresh"}


def clay_rows(rows: list[dict[str, Any]], graph: ShotGraph) -> list[dict[str, Any]]:
    """A clay template's rows with their states from the graph: a step is stale when one of its nodes is, missing when one is owed and
    none is stale, fresh otherwise; a step with no node keeps RC0's state (the start still, made only by the stage route)."""
    out = []
    for r in rows:
        kinds = CLAY_STEPS.get(r["id"])
        mine = [n for n in graph.nodes if n.kind in kinds] if kinds else []
        if not mine:
            out.append(r)
            continue
        st = "stale" if any(n.state == "stale" for n in mine) else "missing" if any(n.state == "owed" for n in mine) else "fresh"
        reasons = list(dict.fromkeys(x for n in mine for x in n.reasons)) if st != "fresh" else []
        out.append({**r, "state": st, "reasons": reasons, "wave": None})
    return out
