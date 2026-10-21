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
        return c

    def save(self, c: Composition) -> None:
        atomic_write_json(self.record(c.final_id), c.model_dump(exclude={"stale"}))

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
        layers.append(CompositionLayer(id="plate", kind="plate", name=plate.name, layer=added(imported(root / "plate" / "frames" / "0000.png"), plate.name)))
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
            fig = added(imported(root / x.id / "frames" / "0000.png"), x.name)
            ec.command("layer.setTrackMatte", {"layer": fig, "matte": matte, "kind": "luma"})
            for l in (fig, matte):
                ec.tool("set_property", {"layer": l, "path": "transform/position", "value": [w / 2 + dx, h / 2 + dy]})
            ec.command("layer.setParent", {"layers": [matte], "parent": fig})   # drag her and her matte follows
            layers.append(CompositionLayer(id=x.id, kind="figure", name=x.name, layer=fig, matte=matte, offset_px=[dx, dy]))
        c = Composition(final_id=f.id, effectcraft=pinned_version(), assembled_at=f.assembled_at, final_revision=f.revision, stack=list(f.assembly["stack"]),
                        layers=layers)
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
                    return l, self.footage(f.id) / f"{l.id}_matte"
                if l.kind == "prop":
                    return l, self.footage(f.id) / l.id
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
