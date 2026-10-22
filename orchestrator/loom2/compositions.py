"""AE1 (proto01_animate 20 §2, D114): the final shot's composition — one per final, an EffectCraft project (`finals/<id>/comp.ecproj`)
beside its record (`comp.json`), written from the final's layers and the assembly's own result (PS5e: the stack order, the contact offsets,
the composition footage the assembly wrote under `comp/`) through the EffectCraft session's commands — never the JSON, except to make the
footage paths relative, so the project directory moves as one (EffectCraft finds relative footage next to the project file; no `..`: the
composition sits at the final's root and its footage below it). An edit is an engine command; each is saved through a copy and an atomic
replace (house rule 4), and the revision counts them. *Make again* writes it from the layers afresh, dropping the edits.
"""
from __future__ import annotations

import json
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .config import REPO_ROOT
from .effectcraft import EffectCraft
from .finals import Final, FinalStore
from .fsio import atomic_write_json, atomic_write_text, read_json, utc_now
from .tools.outline import outline, resample
from .workspace import Workspace

COMPOSITION_SCHEMA_VERSION = 1
COMP_NAME = "Final"


class CompositionLayer(BaseModel):
    """The lineage: a final layer and what it became in the composition."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str                                        # the final's layer
    kind: str
    name: str
    layer: int                                     # EffectCraft's layer id
    matte: int | None = None                       # a character's matte layer (a luma track matte parented to her)
    offset_px: list[float] = Field(default_factory=lambda: [0.0, 0.0])   # D107: her contact offset, the layer's position from the centre


class AudioLayer(BaseModel):
    """D118 (AE4b): a spoken line as an audio layer of the composition, bound to the character's layer; its timing (in, out, start) lives on
    the layer itself, placed on the lanes like a picture layer. `file` is the WAV copied under the final's folder (the project moves as one)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    layer: int                                     # EffectCraft's layer id
    final_layer: str | None = None                 # the final's layer the line belongs to (the speaker's character), None when no layer matched
    asset_id: str                                  # the Catalogue's audio asset (CN2)
    node_id: str | None = None                     # the Flow's Dialogue node and the line's index, when it came from one
    index: int | None = None
    speaker: str | None = None                     # the profile
    text: str = ""
    duration_s: float | None = None
    file: str = ""                                 # audio/<asset>.wav under the final's folder


class Composition(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = COMPOSITION_SCHEMA_VERSION
    final_id: str
    comp: str = COMP_NAME                          # the composition's name in the project
    revision: int = 0                              # edits since it was made
    effectcraft: str                               # the pinned EffectCraft version that wrote it
    assembled_at: str | None = None                # the assembly it was made from
    final_revision: int = 0                        # the final's revision it was made at (any change to the final since makes it stale)
    stale: bool = False                            # computed on read: the final changed since (assembled again, a layer re-made)
    stack: list[str] = Field(default_factory=list) # the actors far to near (the assembly's most common order)
    layers: list[CompositionLayer] = Field(default_factory=list)
    sources: dict[str, str | None] = Field(default_factory=dict)   # D118: per final layer, the take its footage shows (None: the original)
    audio: list[AudioLayer] = Field(default_factory=list)          # D118 (AE4b): the lines as audio layers
    processing: dict[str, int] = Field(default_factory=dict)       # D118 (AE4e): per processing layer (the final's record), its engine layer
    processing_jobs: dict[str, str] = Field(default_factory=dict)  # … and the job whose frames its footage shows (another job: replace)
    processing_stale: dict[str, bool] = Field(default_factory=dict)   # computed on read: the layers below changed since it was rendered
    clip_id: str | None = None                     # the finished shot: the last `comp_render` (the final's clip too)
    rendered_revision: int | None = None           # the revision that render saw (edits since: the clip is behind)
    render_job_id: str | None = None
    made_at: str = Field(default_factory=utc_now)
    edited_at: str = Field(default_factory=utc_now)


@lru_cache(maxsize=1)
def pinned_version() -> str:
    p = REPO_ROOT / "engine" / "effectcraft.pin.json"
    try:
        return str(json.loads(p.read_text(encoding="utf-8")).get("version", "?"))
    except (OSError, ValueError):
        return "?"


def relativise(text: str, root: Path) -> str:
    """The project's footage paths under `root` made relative to it (forward slashes), the rest left as they are."""
    base = os.path.normcase(str(root.resolve())) + os.sep

    def rel(s: str) -> str:
        if isinstance(s, str) and os.path.normcase(s).startswith(base):
            return s[len(base):].replace("\\", "/")
        return s

    def walk(v: Any, depth: int) -> Any:
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                if k == "path" and depth > 0:
                    out[k] = rel(x)
                elif k == "sequence" and isinstance(x, list):
                    out[k] = [rel(s) for s in x]
                else:
                    out[k] = walk(x, depth + 1)
            return out
        if isinstance(v, list):
            return [walk(x, depth + 1) for x in v]
        return v
    return json.dumps(walk(json.loads(text), 0), indent=1)


class CompositionStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.finals = FinalStore(ws)

    def folder(self, fid: str) -> Path:
        return self.finals.folder(fid)

    def record(self, fid: str) -> Path:
        return self.folder(fid) / "comp.json"

    def ecproj(self, fid: str) -> Path:
        return self.folder(fid) / "comp.ecproj"

    def footage(self, fid: str) -> Path:
        return self.folder(fid) / "comp"

    def get(self, f: Final) -> Composition | None:
        p = self.record(f.id)
        if not p.is_file() or not self.ecproj(f.id).is_file():
            return None
        c = Composition.model_validate(read_json(p))
        c.stale = c.final_revision != f.revision
        if f.processing:
            try:
                sigs = self.below_signatures(f, [(rec.id, rec.below) for rec in f.processing])
                c.processing_stale = {rec.id: sigs.get(rec.id) != rec.signature for rec in f.processing}
            except (OSError, ValueError, KeyError):
                c.processing_stale = {rec.id: True for rec in f.processing}
        return c

    def save(self, c: Composition) -> None:
        atomic_write_json(self.record(c.final_id), c.model_dump(exclude={"stale", "processing_stale"}))

    # ---- D118 (AE4e): the stack below a layer, rendered apart; what it looked like ----------------------------------------
    @staticmethod
    def _comp_layers(pj: dict) -> list[dict]:
        """The composition's layer records top to bottom from the project file (the engine's `items[*].kind.layers`, the fake's `comps`)."""
        for it in (pj.get("items") or {}).values():
            kd = it.get("kind") or {}
            if kd.get("type") == "Comp":
                return list(kd.get("layers") or [])
        for comp in (pj.get("comps") or {}).values():
            return list(comp.get("layers") or [])
        return []

    @staticmethod
    def _layer_signature(pj: dict, layers: list[dict], ids: list[int]) -> str:
        """What the layers `ids` look like, as one hash: each record without its volatile fields, plus its footage item's path."""
        import hashlib
        by_id = {int(l["id"]): l for l in layers if l.get("id") is not None}
        items = pj.get("items") or {}
        rows = []
        for i in ids:
            l = by_id.get(int(i))
            if l is None:
                rows.append({"id": int(i), "gone": True})
                continue
            rec = {k: v for k, v in l.items() if k not in ("comment", "label", "markers")}
            src = (l.get("source") or {}).get("item") if isinstance(l.get("source"), dict) else l.get("item")
            it = items.get(str(src)) if src is not None else None
            rec["_path"] = (it.get("path") or (it.get("kind") or {}).get("path")) if isinstance(it, dict) else None
            rows.append(rec)
        return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]

    def below_copy(self, f: Final, point: int, out: Path) -> tuple[list[int], str]:
        """A copy of the project for rendering the stack from the engine layer `point` down: every layer above it has its video switch off.
        Returns the engine layers that stay (top to bottom) and their signature. The copy sits beside the project (its footage paths are
        relative to that folder); the caller renders it and deletes it."""
        pj = read_json(self.ecproj(f.id))
        layers = self._comp_layers(pj)
        pos = next((i for i, l in enumerate(layers) if int(l.get("id", -1)) == int(point)), None)
        if pos is None:
            raise KeyError(f"the composition has no layer {point}")
        for l in layers[:pos]:
            sw = l.setdefault("switches", {})
            sw["video"] = False
        below = [int(l["id"]) for l in layers[pos:]]
        atomic_write_text(out, json.dumps(pj, indent=1))
        return below, self._layer_signature(pj, layers, below)

    def below_signatures(self, f: Final, wanted: list[tuple[str, list[int]]]) -> dict[str, str]:
        """The signature of each processing layer's stack as the project file is now (compared with the record's: stale when they differ)."""
        pj = read_json(self.ecproj(f.id))
        layers = self._comp_layers(pj)
        return {pid: self._layer_signature(pj, layers, ids) for pid, ids in wanted}

    def set_render(self, fid: str, clip_id: str, revision: int, job_id: str) -> Composition:
        """The finished shot rendered from the composition at `revision` (the `comp_render` job)."""
        p = self.record(fid)
        if not p.is_file():
            raise KeyError(f"the final {fid} has no composition")
        c = Composition.model_validate(read_json(p))
        c.clip_id, c.rendered_revision, c.render_job_id = clip_id, revision, job_id
        self.save(c)
        return c

    # ---- making ----------------------------------------------------------------------------------
    def make(self, f: Final, ec: EffectCraft) -> Composition:
        """The composition from the final's layers through the session: the plate; Stage's shadows as a Multiply layer; each prop with its
        alpha; each character over her matte (luma, parented to her), both moved by her contact offset; the actors in the assembly's order."""
        if not f.assembly or f.assembly.get("stack") is None or not (self.footage(f.id) / "shadow").is_dir():
            raise ValueError("assemble the shot first: the composition is written from the assembly's result")
        w, h, rate = f.size["w"], f.size["h"], f.rate
        root = self.folder(f.id)
        by_id = {x.id: x for x in f.layers}
        offsets = {k: (float(v[0]), float(v[1])) for k, v in (f.assembly.get("offsets_px") or {}).items()}
        ec.tool("open_project", {"new": True})                        # a fresh project in the session
        ec.command("comp.new", {"name": COMP_NAME, "width": w, "height": h, "frameRate": rate, "duration": f.frames / rate})

        def imported(first: Path) -> int:
            r = ec.command("file.import", {"paths": [str(first)], "sequence": True, "frameRate": rate})
            if r.get("errors"):
                raise ValueError(f"import {first.name}: {'; '.join(map(str, r['errors']))}")
            return int(r["items"][0])

        def added(item: int, name: str) -> int:
            lid = int(ec.command("layer.addItem", {"item": item, "time": 0})["layer"])
            ec.command("layer.rename", {"layer": lid, "name": name})
            return lid
        layers: list[CompositionLayer] = []
        plate = by_id["plate"]
        layers.append(CompositionLayer(id="plate", kind="plate", name=plate.name, layer=added(imported(FinalStore(self.ws).frames_dir(f.id, "plate") / "0000.png"), plate.name)))
        shadows = by_id["shadows"]
        sid = added(imported(self.footage(f.id) / "shadow" / "0000.png"), shadows.name)
        ec.command("layer.setBlendMode", {"layers": [sid], "mode": "Multiply"})
        layers.append(CompositionLayer(id="shadows", kind="shadows", name=shadows.name, layer=sid))
        for lid in f.assembly["stack"]:                                   # far to near: each new layer goes on top
            x = by_id[lid]
            if x.kind == "prop":
                layers.append(CompositionLayer(id=x.id, kind="prop", name=x.name, layer=added(imported(self.footage(f.id) / x.id / "0000.png"), x.name)))
                continue
            dx, dy = offsets.get(x.id, (0.0, 0.0))
            matte = added(imported(self.footage(f.id) / f"{x.id}_matte" / "0000.png"), f"{x.name} · matte")
            fig = added(imported(FinalStore(self.ws).frames_dir(f.id, x.id) / "0000.png"), x.name)
            ec.command("layer.setTrackMatte", {"layer": fig, "matte": matte, "kind": "luma"})
            for l in (fig, matte):
                ec.tool("set_property", {"layer": l, "path": "transform/position", "value": [w / 2 + dx, h / 2 + dy]})
            ec.command("layer.setParent", {"layers": [matte], "parent": fig})   # drag her and her matte follows
            layers.append(CompositionLayer(id=x.id, kind="figure", name=x.name, layer=fig, matte=matte, offset_px=[dx, dy]))
        c = Composition(final_id=f.id, effectcraft=pinned_version(), assembled_at=f.assembled_at, final_revision=f.revision, stack=list(f.assembly["stack"]),
                        layers=layers, sources={x.id: x.source for x in f.layers})
        self._write(f, ec, c, save_as=True)
        self.save(c)
        return c

    def _write(self, f: Final, ec: EffectCraft, c: Composition, save_as: bool = False) -> None:
        """The session's project to `comp.ecproj`: a copy to a temp name, its footage paths made relative, then the atomic replace; the
        session then holds the written file."""
        root, final = self.folder(f.id), self.ecproj(f.id)
        tmp = root / "comp.ecproj.tmp"
        if save_as:
            ec.tool("save_project", {"path": str(tmp)})
        else:
            ec.save_copy(tmp)
        text = relativise(tmp.read_text(encoding="utf-8"), root)
        atomic_write_text(final, text)
        tmp.unlink(missing_ok=True)
        if save_as:
            ec.project = None                                             # the session saved the temp name: hold the real file instead
            ec.open(final)

    # ---- D118 (AE4a): the layer's footage swapped for a take ---------------------------------------
    def item_of(self, f: Final, c: Composition, layer_id: str, matte: bool = False) -> int | None:
        """The footage item behind a layer's engine layer (or, with `matte`, behind a character's matte layer), read from the project file's
        composition (its layers name their source item)."""
        cl = next((x for x in c.layers if x.id == layer_id), None)
        if cl is None or (matte and cl.matte is None):
            return None
        want = cl.matte if matte else cl.layer
        try:
            pj = read_json(self.ecproj(f.id))
        except (OSError, ValueError):
            return None
        for it in (pj.get("items") or {}).values():
            kd = it.get("kind") or {}
            if kd.get("type") != "Comp":
                continue
            for l in kd.get("layers") or []:
                if l.get("id") == want and (l.get("source") or {}).get("type") == "Footage":
                    return int(l["source"]["item"])
        for comp in (pj.get("comps") or {}).values():                     # the fake's flat form: a layer names its item
            for l in comp.get("layers") or []:
                if l.get("id") == want and l.get("item") is not None:
                    return int(l["item"])
        return None

    def matte_footage(self, f: Final, layer_id: str, take_id: str | None) -> Path:
        """D118 (AE4c): the composition footage of a character's matte for a source — the take's `matte_comp/` when the pass changed her
        silhouette (the face pass), else the assembly's `comp/<layer>_matte/`."""
        if take_id:
            d = FinalStore(self.ws).pass_dir(f.id, layer_id, f"passes/{take_id}/matte_comp")
            if len(list(d.glob("*.png"))) == f.frames:
                return d
        return self.footage(f.id) / f"{layer_id}_matte"

    def set_source(self, f: Final, ec: EffectCraft, layer_id: str, take_id: str | None) -> Composition:
        """The layer's footage item replaced by the take's frames (or its original frames): `file.replaceFootage` keeps the layer's
        transforms, masks, effects and keys; `file.interpretFootage` keeps the rate. One save; the composition stays fresh to the final."""
        c = self._open(f, ec)
        item = self.item_of(f, c, layer_id)
        if item is None:
            raise KeyError(f"the composition has no footage for the layer {layer_id}")
        store = FinalStore(self.ws)
        d = store.pass_dir(f.id, layer_id, f"passes/{take_id}") if take_id else store.pass_dir(f.id, layer_id, "frames")
        first = d / "0000.png"
        if not first.is_file():
            raise ValueError(f"no frames for {layer_id} under {d.name}")
        ec.command("file.replaceFootage", {"item": item, "path": str(first), "sequence": True})
        ec.command("file.interpretFootage", {"items": [item], "frameRate": float(f.rate)})
        mitem = self.item_of(f, c, layer_id, matte=True)
        if mitem is not None:                                             # AE4c: her matte follows the source (the face pass changes her silhouette)
            mfirst = self.matte_footage(f, layer_id, take_id) / "0000.png"
            if mfirst.is_file():
                ec.command("file.replaceFootage", {"item": mitem, "path": str(mfirst), "sequence": True})
                ec.command("file.interpretFootage", {"items": [mitem], "frameRate": float(f.rate)})
        c.sources[layer_id] = take_id
        c = self._edited(f, ec, c)
        c.final_revision = f.revision                                 # the swap is the final's own change: not stale
        c.stale = False
        self.save(c)
        return c

    # ---- D118 (AE4b): the line as an audio layer -------------------------------------------------
    def add_audio(self, f: Final, ec: EffectCraft, src: Path, meta: dict[str, Any], t: float, name: str) -> Composition:
        """The line's WAV copied under the final's folder, imported and added as a layer at `t` (its In point), named for the character and
        the line, recorded with what it is; one save."""
        c = self._open(f, ec)
        d = self.folder(f.id) / "audio"
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"{meta['asset_id']}{src.suffix.lower() or '.wav'}"
        if not dst.is_file():
            shutil.copyfile(src, dst)
        r = ec.command("file.import", {"paths": [str(dst)]})
        if r.get("errors") or not r.get("items"):
            raise ValueError(f"import {dst.name}: {'; '.join(map(str, r.get('errors') or ['no item']))}")
        lid = int(ec.command("layer.addItem", {"item": int(r["items"][0]), "time": float(t)})["layer"])
        ec.command("layer.rename", {"layer": lid, "name": name})
        c.audio.append(AudioLayer(layer=lid, file=f"audio/{dst.name}", **{k: v for k, v in meta.items() if k in ("final_layer", "asset_id", "node_id", "index", "speaker", "text", "duration_s")}))
        return self._edited(f, ec, c)

    def remove_audio(self, f: Final, ec: EffectCraft, layer: int) -> Composition:
        """The audio layer taken out of the composition (selected, cleared) and off the record; the WAV stays for another attach."""
        c = self._open(f, ec)
        if not any(a.layer == layer for a in c.audio):
            raise KeyError(f"the composition has no audio layer {layer}")
        ec.command("layer.select", {"layers": [layer]})
        ec.command("edit.clear", {})
        c.audio = [a for a in c.audio if a.layer != layer]
        return self._edited(f, ec, c)

    def audio_timing(self, f: Final, c: Composition) -> list[dict[str, Any]]:
        """Every audio layer with its In, Out and start in seconds, read from the project file (the engine's ticks, or the fake's seconds):
        the samples from `in - start` to `out - start` of the file play at `in`…`out` of the shot."""
        try:
            pj = read_json(self.ecproj(f.id))
        except (OSError, ValueError):
            return []
        secs = max(1e-6, f.frames / float(f.rate or 16))
        out: list[dict[str, Any]] = []
        comp_layers: dict[int, dict] = {}
        scale = 1.0
        for it in (pj.get("items") or {}).values():
            kd = it.get("kind") or {}
            if kd.get("type") == "Comp":
                scale = float(kd.get("duration") or 0) / secs or 1.0            # ticks per second
                for l in kd.get("layers") or []:
                    comp_layers[int(l["id"])] = {"in": l.get("in_point", 0) / scale, "out": l.get("out_point", 0) / scale, "start": l.get("start_time", 0) / scale}
        if not comp_layers:
            for comp in (pj.get("comps") or {}).values():
                for l in comp.get("layers") or []:
                    comp_layers[int(l["id"])] = {"in": float(l.get("in", 0)), "out": float(l.get("out", 0)), "start": float(l.get("start", 0))}
        for a in c.audio:
            tl = comp_layers.get(a.layer)
            if tl is None:
                continue
            out.append({**a.model_dump(), **tl, "path": str(self.folder(f.id) / a.file)})
        return out

    def sync_sources(self, f: Final, ec: EffectCraft) -> Composition:
        """Every layer whose source moved on the final (a pass landed, a take chosen) swapped in the composition; AE4e: the final's
        processing layers brought in (imported and added right above their layer), replaced when run again, taken out when dropped."""
        c = self._open(f, ec)
        for x in f.layers:
            if any(cl.id == x.id for cl in c.layers) and c.sources.get(x.id) != x.source:
                c = self.set_source(f, ec, x.id, x.source)
        return self._sync_processing(f, ec, c)

    def _sync_processing(self, f: Final, ec: EffectCraft, c: Composition) -> Composition:
        from .recipes import LayerPassPreset  # noqa: F401  (the labels below name the presets)
        store = FinalStore(self.ws)
        labels = {"cleanup": "Clean up", "creative": "Creative"}
        changed = False
        engine = {int(l["id"]): l for l in (ec.tool("get_comp", {"comp": COMP_NAME}).get("layers") or [])}
        for rec in f.processing:
            first = store.processing_dir(f.id, rec.id) / "frames" / "0000.png"
            if not first.is_file():
                continue
            eid = c.processing.get(rec.id)
            point = next((cl for cl in c.layers if cl.id == rec.above and cl.kind != "processing"), None)
            if eid is None or eid not in engine:
                if point is None or point.layer not in engine:
                    continue
                r = ec.command("file.import", {"paths": [str(first)], "sequence": True, "frameRate": f.rate})
                if r.get("errors") or not r.get("items"):
                    raise ValueError(f"import {first.parent.name}: {'; '.join(map(str, r.get('errors') or ['no item']))}")
                index = engine[point.layer].get("index")
                lid = int(ec.command("layer.addItem", {"item": int(r["items"][0]), "time": 0, **({"index": int(index)} if index else {})})["layer"])
                name = f"Processed · {labels.get(rec.preset, rec.preset)} ({point.name} down)"
                ec.command("layer.rename", {"layer": lid, "name": name})
                c.processing[rec.id] = lid
                c.processing_jobs[rec.id] = rec.job_id
                c.layers = [cl for cl in c.layers if cl.id != rec.id] + [CompositionLayer(id=rec.id, kind="processing", name=name, layer=lid)]
                changed = True
            elif c.processing_jobs.get(rec.id) != rec.job_id:                 # run again: the footage replaced, the layer kept
                item = self._item_of_engine_layer(f, eid)
                if item is not None:
                    ec.command("file.replaceFootage", {"item": item, "path": str(first), "sequence": True})
                    ec.command("file.interpretFootage", {"items": [item], "frameRate": float(f.rate)})
                    c.processing_jobs[rec.id] = rec.job_id
                    changed = True
        keep = {rec.id for rec in f.processing}
        for pid in [p for p in c.processing if p not in keep]:                # dropped on the final: the layer goes
            eid = c.processing.pop(pid)
            c.processing_jobs.pop(pid, None)
            if eid in engine:
                ec.command("layer.select", {"layers": [eid]})
                ec.command("edit.clear", {})
            c.layers = [cl for cl in c.layers if cl.id != pid]
            changed = True
        if changed:
            c = self._edited(f, ec, c)
            c.final_revision = f.revision
            c.stale = False
            self.save(c)
        return c

    def _item_of_engine_layer(self, f: Final, layer: int) -> int | None:
        """The footage item behind an engine layer, read from the project file."""
        try:
            pj = read_json(self.ecproj(f.id))
        except (OSError, ValueError):
            return None
        for l in self._comp_layers(pj):
            if int(l.get("id", -1)) != int(layer):
                continue
            src = l.get("source")
            if isinstance(src, dict) and src.get("type") == "Footage":
                return int(src["item"])
            if l.get("item") is not None:
                return int(l["item"])
        return None

    # ---- editing ---------------------------------------------------------------------------------
    def _open(self, f: Final, ec: EffectCraft) -> Composition:
        c = self.get(f)
        if c is None:
            raise KeyError(f"the final {f.id} has no composition yet")
        ec.open(self.ecproj(f.id))
        return c

    def _edited(self, f: Final, ec: EffectCraft, c: Composition) -> Composition:
        self._write(f, ec, c)
        c.revision += 1
        c.edited_at = utc_now()
        self.save(c)
        return c

    def command(self, f: Final, ec: EffectCraft, cid: str, params: dict | None) -> tuple[Any, Composition]:
        """One engine command on the composition (a blend mode, a mask, a parent, undo …), saved."""
        c = self._open(f, ec)
        result = ec.command(cid, params or {})
        return result, self._edited(f, ec, c)

    def set_property(self, f: Final, ec: EffectCraft, args: dict) -> tuple[Any, Composition]:
        """A property set (or keyed, with `time`) on a layer, saved."""
        c = self._open(f, ec)
        result = ec.tool("set_property", args)
        return result, self._edited(f, ec, c)

    def batch(self, f: Final, ec: EffectCraft, steps: list[dict]) -> tuple[Any, Composition]:
        """Several engine commands as one edit (`command_batch`, stopping at the first refusal), saved once."""
        c = self._open(f, ec)
        result = ec.tool("command_batch", {"steps": [{"id": s["id"], "params": s.get("params") or {}} for s in steps], "stop_on_error": True})
        return result, self._edited(f, ec, c)

    def frame(self, f: Final, ec: EffectCraft, t: float, side: int, before: bool = False) -> bytes:
        """A frame of the composition as PNG at the longest side `side` (0: full size). `before` (AE3): every layer's effects off for this
        frame only — one switch, the frame, the switch undone; nothing saved, the revision unmoved."""
        self._open(f, ec)
        if not before:
            return ec.frame(t, side, comp=COMP_NAME)
        ids = [int(l["id"]) for l in (ec.tool("get_comp", {"comp": COMP_NAME}).get("layers") or [])]
        if not ids:
            return ec.frame(t, side, comp=COMP_NAME)
        ec.command("layer.setSwitch", {"layers": ids, "switch": "fx", "value": False, "comp": COMP_NAME})
        try:
            return ec.frame(t, side, comp=COMP_NAME)
        finally:
            ec.command("edit.undo", {})

    def effect_defs(self, f: Final, ec: EffectCraft, names: list[str]) -> list[dict]:
        """AE3: the engine's definitions of these effects (by their names): id, category, GPU, the parameters with their types, defaults,
        ranges and options — what the Effects section shows is what the engine runs (T8)."""
        self._open(f, ec)
        wanted = {n.strip().lower() for n in names if n.strip()}
        items = ec.tool("list_effects", {})
        out = [e for e in (items if isinstance(items, list) else []) if str(e.get("name", "")).lower() in wanted or str(e.get("id", "")).lower() in wanted]
        order = {n.strip().lower(): i for i, n in enumerate(names)}
        return sorted(out, key=lambda e: order.get(str(e.get("name", "")).lower(), order.get(str(e.get("id", "")).lower(), 999)))

    # ---- reading (AE2) ---------------------------------------------------------------------------
    def layers(self, f: Final, ec: EffectCraft) -> list[dict]:
        """The composition's layers top to bottom as EffectCraft reports them (id, index, name, blend mode, track matte, parent, switches,
        in / out / start)."""
        self._open(f, ec)
        return list(ec.tool("get_comp", {"comp": COMP_NAME}).get("layers") or [])

    def layer(self, f: Final, ec: EffectCraft, ref: str | int, flat: bool = True) -> dict:
        """One layer's properties with its header: flat (path, type, value, keys), or the tree (groups with their uids — the masks and
        their mode / inverted, AE2c)."""
        self._open(f, ec)
        return ec.tool("get_layer", {"layer": ref, "comp": COMP_NAME, "flat": True} if flat else {"layer": ref, "comp": COMP_NAME, "depth": 3})

    def prop(self, f: Final, ec: EffectCraft, ref: str | int, path: str, t: float | None = None) -> dict:
        """One property: its value (at `t`), whether it is animated, its keyframes (time, value, interpolation)."""
        self._open(f, ec)
        args: dict[str, Any] = {"layer": ref, "path": path, "comp": COMP_NAME}
        if t is not None:
            args["time"] = t
        return ec.tool("get_property", args)

    # ---- D116: a mask from the layer's visible content -----------------------------------------------
    def content_footage(self, f: Final, c: Composition, ref: str | int) -> tuple[CompositionLayer, Path]:
        """The composition layer `ref` names (the engine's id or the name) and the footage that carries its visible content: a character's
        matte (hers or her matte layer's), a prop's RGBA, the shadows' strength. The plate fills the frame: nothing to trace."""
        for l in c.layers:
            if str(l.layer) == str(ref) or l.name == ref or (l.matte is not None and str(l.matte) == str(ref)) or f"{l.name} · matte" == ref:
                if l.kind == "figure":
                    return l, self.matte_footage(f, l.id, c.sources.get(l.id))
                if l.kind == "prop":
                    return l, self.footage(f.id) / l.id
                if l.kind == "processing":
                    raise ValueError("a processed stack fills the frame: nothing to trace into a mask")
                if l.kind == "shadows":
                    return l, self.footage(f.id) / "shadow"
                raise ValueError("the plate fills the frame: nothing to trace into a mask")
        raise KeyError(f"no composition layer {ref!r}")

    def mask_from_content(self, f: Final, ec: EffectCraft, ref: str | int, t: float, follow: bool = True, tolerance: float = 1.5,
                          max_points: int = 160) -> tuple[dict, Composition]:
        """A new mask on the layer traced from what is visible on it at the frame under `t` (`tools/outline.py`: the largest region's
        boundary, simplified); with `follow`, its path keyed on every frame of the shot with the same vertex count, so it follows the
        character (or the prop, or the shadow). One save. Returns {mask, points, frames}."""
        c = self._open(f, ec)
        layer, folder = self.content_footage(f, c, ref)
        n, rate = max(1, int(f.frames)), float(f.rate or 16)
        i0 = max(0, min(n - 1, int(round(t * rate))))

        def frame(i: int) -> Image.Image:
            path = folder / f"{i:04d}.png"
            if not path.is_file():
                raise KeyError(f"no footage frame {i} for {layer.name} ({path.name}): assemble the final first")
            with Image.open(path) as im:
                return im.copy()

        first = outline(frame(i0), tolerance=tolerance, max_points=max_points)
        if len(first) < 3:
            raise ValueError(f"nothing visible on {layer.name} at frame {i0}: no outline to trace")
        fixed = max(16, len(first)) if follow and n > 1 else None
        verts = resample(first, fixed) if fixed else first
        target = ref if isinstance(ref, int) or str(ref).isdigit() else layer.layer
        r = ec.command("mask.new", {"layer": target, "vertices": [[round(x, 2), round(y, 2)] for x, y in verts], "closed": True})
        uid = r.get("mask") if isinstance(r, dict) else None
        frames = 1
        if fixed:
            tree = ec.tool("get_layer", {"layer": target, "comp": COMP_NAME, "depth": 3})
            masks = next((g for g in tree["properties"]["children"] if g["path"] == "masks"), {"children": []})["children"]
            m = next((m for m in masks if m.get("uid") == uid), masks[-1] if masks else None)
            if m is not None:
                path = next(ch["path"] for ch in m["children"] if str(ch["path"]).endswith("/path"))
                for i in range(n):
                    pts = verts if i == i0 else outline(frame(i), tolerance=tolerance, max_points=max_points, fixed=fixed)
                    if len(pts) < 3:
                        continue                                           # nothing visible there: no key, the last shape holds
                    value = {"t": "Path", "v": {"closed": True, "vertices": [[round(x, 2), round(y, 2)] for x, y in pts],
                                                "in_tangents": [[0.0, 0.0]] * len(pts), "out_tangents": [[0.0, 0.0]] * len(pts)}}
                    ec.tool("set_property", {"layer": target, "comp": COMP_NAME, "path": path, "value": value, "time": i / rate})
                    frames += int(i != i0)
        return {"mask": uid, "points": len(verts), "frames": frames}, self._edited(f, ec, c)
