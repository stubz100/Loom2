"""Layered documents (10 §3, §7): the stack model, ORA files in `<project>/documents/`, pixel storage for open
documents, flatten through the exact compositor and the catalogue link.

ORA layout written here (readable by Krita / GIMP for the raster part):
  mimetype                      "image/openraster", stored first, uncompressed
  stack.xml                     the OpenRaster stack (raster layers and groups; composite-op as svg:/loom2: names)
  data/<layer>.png              8-bit RGBA layer pixels (the compositor's working precision; 16-bit is post-MVP)
  data/<layer>.mask.png         8-bit grey layer mask
  data/selection.png            8-bit grey document selection (optional)
  mergedimage.png               the exact flatten
  Thumbnails/thumbnail.png      ≤ 256 px
  loom2.json                    the lossless loom2 stack (adjustment / filter layers, masks, recipes, blend modes)
"""
from __future__ import annotations

import io
import json
import os
import threading
import zipfile
from pathlib import Path
from typing import Any, Literal, Union
from xml.etree import ElementTree as ET

ET.register_namespace("loom2", "loom2")

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .compose import BLEND_MODES, COMPOSE_VERSION, Renderer
from .fsio import StateError, _tmp_for, new_id, replace, utc_now
from .workspace import Workspace

DOC_SCHEMA_VERSION = 3          # 2 (D52): masks carry density and feather; 3 (D54): masks carry their default value (older documents load with the defaults)


class StaleStack(StateError):
    """C1: a stack PUT based on an older revision than the server's (the API answers 409; the editor merges and retries)."""


class DocumentTooNew(StateError):
    """R10: a document saved by a newer loom2 (schema_version above DOC_SCHEMA_VERSION) is refused (the API answers 409) — never
    opened and silently rewritten in the older format on save."""


NodeKind = Literal["raster", "group", "adjustment", "filter"]
ADJ_TYPES = ["levels", "curves", "hue_saturation", "color_balance", "brightness_contrast", "exposure", "black_white", "invert"]
FILTER_TYPES = ["gaussian_blur", "sharpen", "noise", "high_pass", "color_to_alpha"]
SVG_OPS = {"normal": "svg:src-over", "multiply": "svg:multiply", "screen": "svg:screen", "overlay": "svg:overlay", "darken": "svg:darken", "lighten": "svg:lighten",
           "color-dodge": "svg:color-dodge", "color-burn": "svg:color-burn", "hard-light": "svg:hard-light", "soft-light": "svg:soft-light", "difference": "svg:difference",
           "exclusion": "svg:exclusion", "hue": "svg:hue", "saturation": "svg:saturation", "color": "svg:color", "luminosity": "svg:luminosity"}
SVG_TO_MODE = {v: k for k, v in SVG_OPS.items()}


class Mask(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    enabled: bool = True
    linked: bool = True
    x: int = 0
    y: int = 0
    density: float = Field(1.0, ge=0.0, le=1.0)    # D52: 1 − density·(1 − v) — at 0 the mask hides nothing
    feather: float = Field(0.0, ge=0.0, le=250.0)   # D52: Gaussian σ in px (three box passes, the editor's own blur)
    default: int = Field(0, ge=0, le=255)          # D54: the value outside the mask's extent (PSD default colour) — reveal-all 255, else 0


class NodeBase(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    id: str = Field(default_factory=lambda: new_id("lyr"))
    name: str = "Layer"
    opacity: float = 1.0
    blend: str = "normal"
    visible: bool = True
    locked: bool = False
    clip: bool = False
    mask: Mask | None = None


class RasterLayer(NodeBase):
    kind: Literal["raster"] = "raster"
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    fill: float = 1.0
    lock_alpha: bool = False              # D50: painting keeps the layer's transparency (editor only; PSD: transparency lock)
    recipe: dict | None = None            # origin recipe for AI layers (10 §3)
    lineage_asset_id: str | None = None


class GroupLayer(NodeBase):
    kind: Literal["group"] = "group"
    passthrough: bool = True
    children: list["Node"] = Field(default_factory=list)


class AdjustmentLayer(NodeBase):
    kind: Literal["adjustment"] = "adjustment"
    type: str = "levels"
    params: dict = Field(default_factory=dict)


class FilterLayer(NodeBase):
    kind: Literal["filter"] = "filter"
    type: str = "gaussian_blur"
    params: dict = Field(default_factory=dict)


Node = Union[RasterLayer, GroupLayer, AdjustmentLayer, FilterLayer]
GroupLayer.model_rebuild()


class Document(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    schema_version: int = DOC_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("doc"))
    name: str = "Untitled"
    w: int = 1920
    h: int = 1080
    background: str = "transparent"      # or "#rrggbb"
    source_asset_id: str | None = None
    created_at: str = Field(default_factory=utc_now)
    saved_at: str | None = None
    revision: int = 0                   # C1: bumped by every stack replace and by every layer the queue inserts
    layers: list[Node] = Field(default_factory=list)   # top first (ORA order)
    has_selection: bool = False
    meta: dict = Field(default_factory=dict)

    def walk(self):
        def rec(nodes):
            for n in nodes:
                yield n
                if isinstance(n, GroupLayer):
                    yield from rec(n.children)
        yield from rec(self.layers)

    def find(self, lid: str) -> Node | None:
        return next((n for n in self.walk() if n.id == lid), None)


def _validate_modes(doc: Document) -> None:
    for n in doc.walk():
        if n.blend not in BLEND_MODES and n.blend != "pass-through":
            raise StateError(f"layer {n.id}: unknown blend mode {n.blend!r}")
        if isinstance(n, AdjustmentLayer) and n.type not in ADJ_TYPES:
            raise StateError(f"layer {n.id}: unknown adjustment {n.type!r}")
        if isinstance(n, FilterLayer) and n.type not in FILTER_TYPES:
            raise StateError(f"layer {n.id}: unknown filter {n.type!r}")


class OpenDocument:
    """A document plus its pixels in memory (uint8 RGBA per raster layer, uint8 grey per mask / selection)."""

    def __init__(self, doc: Document, path: Path) -> None:
        self.doc = doc
        self.path = path
        self.pixels: dict[str, np.ndarray] = {}
        self.masks: dict[str, np.ndarray] = {}
        self.selection: np.ndarray | None = None
        self.dirty = False
        self._save_lock = threading.Lock()

    # ---- pixels -----------------------------------------------------------------------------------
    def set_pixels(self, lid: str, rgba: np.ndarray) -> RasterLayer:
        node = self.doc.find(lid)
        if not isinstance(node, RasterLayer):
            raise StateError(f"{lid} is not a raster layer")
        if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
            raise StateError("pixels must be uint8 HxWx4")
        self.pixels[lid] = rgba
        node.h, node.w = int(rgba.shape[0]), int(rgba.shape[1])
        self.dirty = True
        return node

    def set_mask(self, lid: str, grey: np.ndarray | None) -> None:
        node = self.doc.find(lid)
        if node is None:
            raise StateError(f"no layer {lid}")
        if grey is None:
            self.masks.pop(lid, None)
            node.mask = None
        else:
            if grey.ndim != 2 or grey.dtype != np.uint8:
                raise StateError("mask must be uint8 HxW")
            self.masks[lid] = grey
            node.mask = node.mask or Mask()
        self.dirty = True

    def nodes_dict(self, exclude: set[str] | None = None) -> list[dict]:
        return [n.model_dump() for n in self.doc.layers if not exclude or n.id not in exclude]

    def flatten(self, exclude: set[str] | None = None) -> np.ndarray:
        """The exact composite; `exclude` drops top-level nodes (the AI candidate group while its siblings render, B3)."""
        return Renderer(self.doc.w, self.doc.h, self.pixels, self.masks, self.doc.background).flatten_u8(self.nodes_dict(exclude))

    def missing_pixels(self) -> tuple[list[str], list[str]]:
        """Raster layers without pixels and masked nodes without mask bytes — what a client must upload before a save."""
        px = [n.id for n in self.doc.walk() if isinstance(n, RasterLayer) and n.id not in self.pixels]
        mk = [n.id for n in self.doc.walk() if n.mask is not None and n.id not in self.masks]
        return px, mk

    # ---- ORA --------------------------------------------------------------------------------------
    def save(self) -> Path:
        """Whole-or-nothing like fsio (B9): a unique temp name per writer, fsync, replace; one writer at a time per document."""
        with self._save_lock:
            _validate_modes(self.doc)
            self.doc.saved_at = utc_now()
            self.doc.schema_version = DOC_SCHEMA_VERSION      # D52: an older document is rewritten in the current format
            self.doc.has_selection = self.selection is not None
            merged = self.flatten()
            self.doc.meta["compose_version"] = COMPOSE_VERSION   # D39: the rules mergedimage.png was rendered with
            tmp = _tmp_for(self.path)
            try:
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(zipfile.ZipInfo("mimetype"), "image/openraster", compress_type=zipfile.ZIP_STORED)
                    z.writestr("stack.xml", self._stack_xml())
                    for n in self.doc.walk():
                        if isinstance(n, RasterLayer) and n.id in self.pixels:
                            z.writestr(f"data/{n.id}.png", _png(self.pixels[n.id]))
                        if n.mask and n.id in self.masks:
                            z.writestr(f"data/{n.id}.mask.png", _png(self.masks[n.id]))
                    if self.selection is not None:
                        z.writestr("data/selection.png", _png(self.selection))
                    z.writestr("mergedimage.png", _png(merged))
                    thumb = Image.fromarray(merged, "RGBA")
                    thumb.thumbnail((256, 256))
                    z.writestr("Thumbnails/thumbnail.png", _png(np.asarray(thumb)))
                    z.writestr("loom2.json", json.dumps(self.doc.model_dump(), indent=1, ensure_ascii=False))
                with open(tmp, "rb+") as f:
                    os.fsync(f.fileno())
                replace(tmp, self.path)                       # D42: retries a briefly locked target
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            self.dirty = False
            return self.path

    def _stack_xml(self) -> str:
        image = ET.Element("image", {"version": "0.0.3", "w": str(self.doc.w), "h": str(self.doc.h), "xres": "72", "yres": "72"})
        ET.SubElement(image, "{loom2}meta", {"doc": self.doc.id, "name": self.doc.name, "background": self.doc.background, "source_asset": self.doc.source_asset_id or ""})

        def emit(parent: ET.Element, nodes: list[Node]) -> None:
            for n in nodes:
                common = {"name": n.name, "opacity": f"{n.opacity:.4f}", "visibility": "visible" if n.visible else "hidden",
                          "composite-op": SVG_OPS.get(n.blend, f"loom2:{n.blend}")}
                if isinstance(n, GroupLayer):
                    st = ET.SubElement(parent, "stack", {**common, "isolation": "auto" if n.passthrough else "isolate"})
                    emit(st, n.children)
                elif isinstance(n, RasterLayer):
                    ET.SubElement(parent, "layer", {**common, "src": f"data/{n.id}.png", "x": str(n.x), "y": str(n.y)})
                else:
                    ET.SubElement(parent, "{loom2}" + n.kind, {**common, "type": n.type})
        root = ET.SubElement(image, "stack")
        emit(root, self.doc.layers)
        return ET.tostring(image, encoding="unicode", xml_declaration=True)

    @classmethod
    def load(cls, path: Path) -> "OpenDocument":
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "loom2.json" in names:
                raw = json.loads(z.read("loom2.json").decode("utf-8"))
                ver = raw.get("schema_version", 1) if isinstance(raw, dict) else 1
                if isinstance(ver, int) and ver > DOC_SCHEMA_VERSION:
                    raise DocumentTooNew(f"{path.name} was saved by a newer loom2 (document format {ver}; this version reads up to "
                                         f"{DOC_SCHEMA_VERSION}) — update loom2 to open it; the file is left untouched")
                doc = Document.model_validate(raw)
            else:
                doc = _doc_from_stack_xml(z.read("stack.xml").decode("utf-8"), path.stem)
            od = cls(doc, path)
            for n in doc.walk():
                if isinstance(n, RasterLayer):
                    src = f"data/{n.id}.png"
                    if src in names:
                        od.pixels[n.id] = np.asarray(Image.open(io.BytesIO(z.read(src))).convert("RGBA"))
                        n.h, n.w = od.pixels[n.id].shape[:2]
                if n.mask and f"data/{n.id}.mask.png" in names:
                    od.masks[n.id] = np.asarray(Image.open(io.BytesIO(z.read(f"data/{n.id}.mask.png"))).convert("L"))
            if "data/selection.png" in names:
                od.selection = np.asarray(Image.open(io.BytesIO(z.read("data/selection.png"))).convert("L"))
        return od


def _doc_from_stack_xml(xml: str, doc_id: str) -> Document:
    """Foreign ORA (Krita / GIMP): raster layers and groups only."""
    root = ET.fromstring(xml)
    doc = Document(id=doc_id, w=int(root.get("w", 0)), h=int(root.get("h", 0)), name=doc_id)

    def parse(el: ET.Element) -> list[Node]:
        out: list[Node] = []
        for child in el:
            tag = child.tag.split("}")[-1]
            common = dict(name=child.get("name", "Layer"), opacity=float(child.get("opacity", "1")), visible=child.get("visibility", "visible") != "hidden",
                          blend=SVG_TO_MODE.get(child.get("composite-op", "svg:src-over"), "normal"))
            if tag == "stack":
                out.append(GroupLayer(children=parse(child), **common))
            elif tag == "layer":
                src = child.get("src", "")
                out.append(RasterLayer(id=Path(src).stem if src.startswith("data/") else new_id("lyr"), x=int(child.get("x", 0)), y=int(child.get("y", 0)), **common))
        return out
    stack = root.find("stack")
    doc.layers = parse(stack) if stack is not None else []
    return doc


def _png(arr: np.ndarray) -> bytes:
    mode = "RGBA" if arr.ndim == 3 else "L"
    buf = io.BytesIO()
    Image.fromarray(arr, mode).save(buf, "PNG", compress_level=6)
    return buf.getvalue()


class DocumentStore:
    """Documents of one project: files under `documents/`, open documents in memory."""

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.open: dict[str, OpenDocument] = {}

    def path_for(self, doc_id: str) -> Path:
        return self.ws.documents_dir / f"{doc_id}.ora"

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.ws.documents_dir.glob("*.ora"), key=lambda q: q.stat().st_mtime, reverse=True):
            try:
                with zipfile.ZipFile(p) as z:
                    meta = json.loads(z.read("loom2.json").decode("utf-8")) if "loom2.json" in z.namelist() else {"id": p.stem, "name": p.stem}
            except (zipfile.BadZipFile, OSError, ValueError):
                continue
            def _count(nodes: list) -> int:   # every node, groups included (what the Documents list shows)
                return sum(1 + _count(n.get("children") or []) for n in nodes)
            out.append({"id": meta.get("id", p.stem), "name": meta.get("name", p.stem), "w": meta.get("w"), "h": meta.get("h"), "saved_at": meta.get("saved_at"),
                        "source_asset_id": meta.get("source_asset_id"), "layers": _count(meta.get("layers", [])), "path": str(p), "open": meta.get("id", p.stem) in self.open,
                        "dirty": self.open[meta.get("id", p.stem)].dirty if meta.get("id", p.stem) in self.open else False})
        return out

    def create(self, name: str, w: int, h: int, background: str = "transparent", source_asset_id: str | None = None,
               base_pixels: np.ndarray | None = None) -> OpenDocument:
        doc = Document(name=name, w=w, h=h, background=background, source_asset_id=source_asset_id)
        od = OpenDocument(doc, self.path_for(doc.id))
        if base_pixels is not None:
            layer = RasterLayer(name="Background", locked=False, lineage_asset_id=source_asset_id)
            doc.layers.append(layer)
            od.set_pixels(layer.id, base_pixels)
        od.save()
        self.open[doc.id] = od
        return od

    def get(self, doc_id: str) -> OpenDocument:
        if doc_id in self.open:
            return self.open[doc_id]
        p = self.path_for(doc_id)
        if not p.is_file():
            raise StateError(f"no document {doc_id}")
        od = OpenDocument.load(p)
        self.open[doc_id] = od
        return od

    def close(self, doc_id: str) -> None:
        self.open.pop(doc_id, None)

    def delete(self, doc_id: str) -> bool:
        self.open.pop(doc_id, None)
        p = self.path_for(doc_id)
        if p.is_file():
            p.unlink()
            return True
        return False

    def update_stack(self, doc_id: str, data: dict) -> OpenDocument:
        """Replace the stack (layer tree + document fields) keeping pixels of layers that still exist.
        C1: the client names the `revision` its stack is based on; a stack older than the server's (an AI job inserted layers
        meanwhile) is refused with `StaleStack` so the editor merges first — a plain replace would delete those layers and
        their pixels. A body without `revision` (legacy caller) is accepted as before."""
        od = self.get(doc_id)
        with od._save_lock:                                   # C17: never swap od.doc under a running save()
            base = data.get("revision")
            if base is not None and int(base) != od.doc.revision:
                raise StaleStack(f"the stack is based on revision {base}; the document is at revision {od.doc.revision} — merge the newer layers first")
            new = Document.model_validate({**od.doc.model_dump(), **data, "id": doc_id, "revision": od.doc.revision + 1})
            _validate_modes(new)
            ids = {n.id for n in new.walk()}
            od.pixels = {k: v for k, v in od.pixels.items() if k in ids}
            od.masks = {k: v for k, v in od.masks.items() if k in ids}
            for n in new.walk():
                if isinstance(n, RasterLayer) and n.id in od.pixels:
                    n.h, n.w = od.pixels[n.id].shape[:2]
            od.doc = new
            od.dirty = True
        return od
