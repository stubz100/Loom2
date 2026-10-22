"""AE1 (proto01_animate 20 §2): a stand-in for `effectcraft-cli` for the offline suite and the e2e, the way fake_comfy.py stands in for the
engine. Standard library only.

    python fake_effectcraft.py mcp [--empty | --project P]            the MCP subset loom2/effectcraft.py uses, JSON-RPC over stdio
    python fake_effectcraft.py render --project P --comp C --out X_[####].png --format png [...]   a PNG a frame of the comp

It keeps a small project (items, comps, layers with a few properties, a revision, an undo stack) and writes it as JSON on save. A frame is
a flat colour that tells the time and the state apart: R = the frame number, G = the revision, B = 128 — sized by `max_side`.
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import time
import zlib
from pathlib import Path


def png(w: int, h: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


SWITCHES = {"video": True, "audio": True, "solo": False, "locked": False, "shy": False, "collapse": False, "quality": "Best", "effects": True,
            "frame_blend": "Off", "motion_blur": False, "adjustment": False, "three_d": False, "guide": False, "sampling": "Bilinear"}
SWITCH_NAMES = {"lock": "locked", "fx": "effects", "frameBlend": "frame_blend", "motionBlur": "motion_blur", "threeD": "three_d"}   # the command's names → the report's
FLAT = (("anchor", "vec3"), ("position", "vec3"), ("scale", "vec3"), ("rotation", "scalar"), ("opacity", "scalar"))
# AE3: a slice of the engine's effect registry — the curated effects with their dials (id, type, default, min, max, options)
_DIM = [{"label": "Horizontal and Vertical", "value": 0}, {"label": "Horizontal", "value": 1}, {"label": "Vertical", "value": 2}]
FX_REGISTRY: dict[str, tuple[str, str, list]] = {
    "Gaussian Blur": ("ec.blur.gaussian", "Blur & Sharpen", [("blurriness", "scalar", 0.0, 0.0, 3000.0, None), ("dimensions", "enum", 0, None, None, _DIM), ("repeatEdge", "bool", False, None, None, None)]),
    "Fast Box Blur": ("ec.blur.fastbox", "Blur & Sharpen", [("radius", "scalar", 0.0, 0.0, 3000.0, None), ("iterations", "scalar", 3.0, 1.0, 50.0, None)]),
    "Directional Blur": ("ec.blur.directional", "Blur & Sharpen", [("direction", "scalar", 0.0, None, None, None), ("length", "scalar", 0.0, 0.0, 1000.0, None)]),
    "Sharpen": ("ec.blur.sharpen", "Blur & Sharpen", [("amount", "scalar", 0.0, 0.0, 500.0, None)]),
    "Lumetri Color": ("ec.color.lumetri", "Color Correction", [("basicCorrection/tone/exposure", "scalar", 0.0, -5.0, 5.0, None), ("basicCorrection/tone/contrast", "scalar", 0.0, -100.0, 100.0, None),
                                                               ("basicCorrection/whiteBalance/temperature", "scalar", 0.0, -100.0, 100.0, None), ("basicCorrection/saturation", "scalar", 100.0, 0.0, 200.0, None)]),
    "Curves": ("ec.color.curves", "Color Correction", [("rgb", "string", "0,0 1,1", None, None, None)]),
    "Levels": ("ec.color.levels", "Color Correction", [("inBlack", "scalar", 0.0, -1.0, 2.0, None), ("inWhite", "scalar", 1.0, -1.0, 2.0, None), ("gamma", "scalar", 1.0, 0.1, 10.0, None),
                                                       ("outBlack", "scalar", 0.0, -1.0, 2.0, None), ("outWhite", "scalar", 1.0, -1.0, 2.0, None)]),
    "Hue/Saturation": ("ec.color.huesaturation", "Color Correction", [("hue", "scalar", 0.0, None, None, None), ("saturation", "scalar", 0.0, -100.0, 100.0, None), ("lightness", "scalar", 0.0, -100.0, 100.0, None)]),
    "Tint": ("ec.color.tint", "Color Correction", [("black", "color", [0.0, 0.0, 0.0, 1.0], None, None, None), ("white", "color", [1.0, 1.0, 1.0, 1.0], None, None, None), ("amount", "scalar", 100.0, 0.0, 100.0, None)]),
    "Color Balance": ("ec.color.colorbalance", "Color Correction", [(k, "scalar", 0.0, -100.0, 100.0, None) for k in ("shadowRed", "shadowGreen", "shadowBlue", "midRed", "midGreen", "midBlue", "hiRed", "hiGreen", "hiBlue")]),
    "Add Grain": ("ec.noise.addgrain", "Noise & Grain", [("tweaking/intensity", "scalar", 1.0, 0.0, 4.0, None), ("tweaking/size", "scalar", 1.0, 0.1, 10.0, None), ("tweaking/softness", "scalar", 0.0, 0.0, 10.0, None)]),
    "Match Grain": ("ec.noise.matchgrain", "Noise & Grain", [("noiseSourceLayer", "layer", None, None, None, None), ("compensateForExistingNoise", "scalar", 0.0, 0.0, 100.0, None), ("tweaking/intensity", "scalar", 1.0, 0.0, 4.0, None)]),
    "Remove Grain": ("ec.noise.removegrain", "Noise & Grain", [("noiseReductionSettings/noiseReduction", "scalar", 1.0, 0.0, 4.0, None), ("noiseReductionSettings/passes", "scalar", 2.0, 1.0, 10.0, None)]),
    "Simple Choker": ("ec.matte.simplechoker", "Matte", [("chokeMatte", "scalar", 0.0, -100.0, 100.0, None)]),
    "Matte Choker": ("ec.matte.mattechoker", "Matte", [("choke1", "scalar", 75.0, -127.0, 127.0, None), ("geometricSoftness1", "scalar", 4.0, 0.0, 1000.0, None), ("grayLevelSoftness1", "scalar", 10.0, 0.0, 100.0, None)]),
    "Refine Soft Matte": ("ec.matte.refinesoft", "Matte", [("radius", "scalar", 10.0, 1.0, 200.0, None), ("feather", "scalar", 10.0, 0.0, 100.0, None), ("contrast", "scalar", 0.0, 0.0, 100.0, None),
                                                          ("shiftEdge", "scalar", 0.0, -100.0, 100.0, None), ("smooth", "scalar", 0.0, 0.0, 100.0, None)]),
    "Drop Shadow": ("ec.perspective.dropshadow", "Perspective", [("color", "color", [0.0, 0.0, 0.0, 1.0], None, None, None), ("opacity", "scalar", 50.0, 0.0, 100.0, None), ("direction", "scalar", 135.0, None, None, None),
                                                                 ("distance", "scalar", 5.0, 0.0, 32000.0, None), ("softness", "scalar", 0.0, 0.0, 1000.0, None)]),
    "Glow": ("ec.stylize.glow", "Stylize", [("threshold", "scalar", 60.0, 0.0, 100.0, None), ("radius", "scalar", 10.0, 0.0, 1000.0, None), ("intensity", "scalar", 1.0, 0.0, 255.0, None)]),
    "CC Vignette": ("ec.stylize.ccvignette", "Stylize", [("amount", "scalar", 50.0, -100.0, 100.0, None), ("angleOfView", "scalar", 60.0, 0.0, 179.0, None), ("pinHighlights", "scalar", 0.0, 0.0, 100.0, None)]),
    "Exposure": ("ec.color.exposure", "Color Correction", [("master/exposure", "scalar", 0.0, -20.0, 20.0, None), ("master/offset", "scalar", 0.0, -2.0, 2.0, None), ("master/gamma", "scalar", 1.0, 0.01, 9.99, None)]),
    "Black & White": ("ec.color.blackwhite", "Color Correction", [(k, "scalar", v, -200.0, 300.0, None) for k, v in (("reds", 40.0), ("yellows", 60.0), ("greens", 40.0), ("cyans", 60.0), ("blues", 20.0), ("magentas", 80.0))]
                      + [("tint", "bool", False, None, None, None), ("tintColor", "color", [0.88, 0.76, 0.6, 1.0], None, None, None)]),
    "Object Matte": ("ec.matte.objectmatte", "Matte", [("reach", "scalar", 30.0, 0.0, 300.0, None)]),   # D116: what objectMatte.apply adds
}


def fx_def(name: str) -> dict | None:
    for n, (fid, cat, params) in FX_REGISTRY.items():
        if n.lower() == name.lower() or fid == name:
            return {"id": fid, "name": n, "category": cat, "gpu": True, "float": True,
                    "params": [{"id": pid, "name": pid.split("/")[-1].title(), "type": t, "default": d, **({"min": lo, "max": hi} if lo is not None else {}), **({"options": o} if o else {})}
                               for pid, t, d, lo, hi, o in params]}
    return None


class Fake:
    def __init__(self) -> None:
        self.p: dict = {"schema": 2, "items": {}, "comps": {}, "active": None, "path": None, "dirty": False, "revision": 0, "time": 0.0,
                        "settings": {"renderer": "gpu"}}
        self.next = 1
        self.undo: list[str] = []
        self.redo: list[str] = []

    # ---- helpers --------------------------------------------------------------------------------
    def nid(self) -> int:
        self.next += 1
        return self.next - 1

    def edit(self) -> None:
        self.undo.append(json.dumps(self.p))
        self.redo.clear()
        self.p["revision"] += 1
        self.p["dirty"] = True

    def comp(self, ref=None) -> dict:
        if ref is None or ref == "-":
            ref = self.p["active"]
        for cid, c in self.p["comps"].items():
            if str(cid) == str(ref) or c["name"] == ref:
                return c
        raise KeyError(f"no composition {ref}")

    def layer(self, c: dict, ref) -> dict:
        for l in c["layers"]:
            if str(l["id"]) == str(ref) or l["name"] == ref:
                return l
        raise KeyError(f"no layer {ref}")

    @staticmethod
    def mask_of(l: dict, ref) -> dict:
        m = next((m for m in l["masks"] if str(m["id"]) == str(ref) or m["name"] == ref), None)
        if m is None:
            raise ValueError(f"no mask {ref}")
        return m

    @staticmethod
    def path_value(m: dict, verts=None) -> dict:
        v = verts if verts is not None else m["vertices"]
        return {"t": "Path", "v": {"closed": m.get("closed", True), "vertices": v, "in_tangents": [[0.0, 0.0]] * len(v), "out_tangents": [[0.0, 0.0]] * len(v)}}

    def layers_of(self, p: dict) -> list[dict]:
        c = self.comp(p.get("comp"))
        refs = p.get("layers") or ([p["layer"]] if "layer" in p else [])
        return [self.layer(c, r) for r in refs]

    # ---- commands -------------------------------------------------------------------------------
    def command(self, cid: str, p: dict) -> dict:
        if cid == "comp.new":
            self.edit()
            i = self.nid()
            self.p["comps"][str(i)] = {"id": i, "name": p.get("name", f"Comp {i}"), "width": int(p.get("width", 1920)), "height": int(p.get("height", 1080)),
                                       "frameRate": float(p.get("frameRate", 30)), "duration": float(p.get("duration", 10)), "layers": [], "effects": []}
            self.p["items"][str(i)] = {"id": i, "name": self.p["comps"][str(i)]["name"], "type": "Composition"}
            self.p["active"] = i
            return {"comp": i}
        if cid == "comp.open":
            self.p["active"] = self.comp(p.get("comp"))["id"]
            return {}
        if cid == "file.import":
            self.edit()
            items = []
            for path in p.get("paths") or [p.get("path")]:
                i = self.nid()
                self.p["items"][str(i)] = {"id": i, "name": Path(path).name, "type": "Footage", "path": path, "sequence": bool(p.get("sequence", True)),
                                           "frameRate": p.get("frameRate")}
                items.append(i)
            return {"items": items, "comps": [], "errors": [], "warnings": []}
        if cid == "file.replaceFootage":                                # D118 (AE4a): a footage item's file swapped — the layers keep everything
            self.edit()
            it = self.p["items"].get(str(p["item"]))
            if it is None or it.get("type") != "Footage":
                raise ValueError("select footage")
            it["path"], it["sequence"] = p["path"], bool(p.get("sequence", True))
            return None
        if cid == "file.interpretFootage":
            self.edit()
            out = []
            for i in p.get("items") or []:
                it = self.p["items"][str(i)]
                if "frameRate" in p:
                    it["frameRate"] = float(p["frameRate"])
                out.append({"item": it["id"], "frameRate": it.get("frameRate"), "frames": 0})
            return {"items": out}
        if cid == "layer.select":                                        # D118 (AE4b): a selection the next edit.clear removes
            self.sel_layers = [int(x) for x in p.get("layers") or []]
            return self.sel_layers
        if cid == "edit.clear":
            self.edit()
            c = self.comp(p.get("comp"))
            sel = getattr(self, "sel_layers", [])
            before = len(c["layers"])
            c["layers"] = [l for l in c["layers"] if l["id"] not in sel]
            self.sel_layers = []
            return before - len(c["layers"])
        if cid == "layer.addItem":
            self.edit()
            c = self.comp(p.get("comp"))
            item = self.p["items"][str(p["item"])]
            i = self.nid()
            t = float(p.get("time", 0.0))                                   # D118 (AE4b): `time` is the layer's In point (an audio line placed on the lanes)
            c["layers"].insert(0, {"id": i, "name": item["name"], "item": item["id"], "type": "AV", "label": "Lavender", "blendMode": "Normal", "trackMatte": None,
                                   "parent": None, "in": t, "out": c["duration"], "start": t, "stretch": 100.0,
                                   "anchor": [c["width"] / 2, c["height"] / 2, 0.0], "position": [c["width"] / 2, c["height"] / 2, 0.0], "scale": [100.0, 100.0, 100.0],
                                   "rotation": 0.0, "opacity": 100.0, "switches": dict(SWITCHES), "masks": [], "effects": [], "keys": {}})
            return {"layer": i}
        if cid == "layer.arrange":                                      # what dragging Timeline rows does
            self.edit()
            c = self.comp(p.get("comp"))
            moving = self.layers_of(p)
            rest = [l for l in c["layers"] if l not in moving]
            to, above = p.get("to"), p.get("above")
            if above is not None:
                k = next(i for i, l in enumerate(rest) if str(l["id"]) == str(above) or l["name"] == above)
            elif to == "front":
                k = 0
            elif to == "back":
                k = len(rest)
            elif to in ("forward", "backward"):
                idx = [c["layers"].index(l) for l in moving]
                k = max(0, min(len(rest), (min(idx) - 1) if to == "forward" else (max(idx) + 2 - len(moving))))
            else:
                k = int(p.get("index", 1)) - 1
            c["layers"] = rest[:k] + moving + rest[k:]
            return {}
        if cid == "layer.nudge":
            self.edit()
            for l in self.layers_of(p):
                l["position"] = [l["position"][0] + float(p.get("x", 0)), l["position"][1] + float(p.get("y", 0)), l["position"][2]]
            return {}
        if cid == "layer.setTransform":
            self.edit()
            for l in self.layers_of(p):
                l[p["prop"]] = p["value"]
            return {}
        if cid == "time.set":
            c = self.comp(p.get("comp"))
            self.p["time"] = float(p["time"]) if "time" in p else float(p.get("frame", 0)) / c["frameRate"]
            return {"time": self.p["time"]}
        if cid == "prop.toggleKey":                                     # a key at the current time added, or the one there removed
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            path = p.get("path") or p.get("prop")
            key = str(path).split("/")[-1]
            t = float(p.get("time", self.p["time"]))
            keys = l["keys"].setdefault(key, [])
            had = [k for k in keys if abs(k["time"] - t) < 1e-6]
            if had:
                keys[:] = [k for k in keys if k not in had]
            else:
                keys.append({"time": t, "value": l.get(key), "in": "linear", "out": "linear"})
                keys.sort(key=lambda k: k["time"])
            return {"added": not had}
        if cid == "keys.select":
            self.sel = [{"layer": k["layer"], "prop": str(k["prop"]).split("/")[-1], "time": float(k["time"])} for k in p.get("keys", [])]
            return {"selected": len(self.sel)}
        if cid in ("keys.easyEase", "keys.toggleHold", "keys.interpolation", "keys.delete"):
            self.edit()
            c = self.comp(p.get("comp"))
            for s_ in getattr(self, "sel", []):
                l = self.layer(c, s_["layer"])
                keys = l["keys"].get(s_["prop"], [])
                for k in [k for k in keys if abs(k["time"] - s_["time"]) < 1e-6]:
                    if cid == "keys.delete":
                        keys.remove(k)
                    elif cid == "keys.easyEase":
                        k["in"] = k["out"] = "bezier"
                    elif cid == "keys.toggleHold":
                        k["out"] = "linear" if k["out"] == "hold" else "hold"
                    else:
                        k["in"] = k["out"] = p.get("interpolation", "linear")
            if cid == "keys.delete":
                self.sel = []
            return {}
        if cid == "layer.rename":
            self.edit()
            self.layer(self.comp(p.get("comp")), p["layer"])["name"] = p["name"]
            return {}
        if cid == "layer.setBlendMode":
            self.edit()
            for l in self.layers_of(p):
                l["blendMode"] = p["mode"]
            return {}
        if cid == "layer.setTrackMatte":
            self.edit()
            c = self.comp(p.get("comp"))
            l = self.layer(c, p["layer"])
            m = self.layer(c, p["matte"]) if p.get("matte") is not None else None
            l["trackMatte"] = {"layer": m["id"], "kind": {"luma": "Luma Matte", "alpha": "Alpha Matte"}.get(str(p.get("kind", "alpha")).lower(), "Alpha Matte")} if m else None
            if m:
                m["switches"]["video"] = False
            return {}
        if cid == "layer.setParent":
            self.edit()
            c = self.comp(p.get("comp"))
            parent = self.layer(c, p["parent"])["id"] if p.get("parent") is not None else None
            for l in self.layers_of(p):
                l["parent"] = parent
            return {}
        if cid == "layer.setSwitch":
            self.edit()
            name = SWITCH_NAMES.get(p["switch"], p["switch"])
            for l in self.layers_of(p):
                l["switches"][name] = p["value"] if "value" in p else not l["switches"].get(name)
            return {}
        if cid == "layer.addMask":
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            i = self.nid()
            x, y, w, h = p.get("rect") or [0, 0, 10, 10]
            l["masks"].append({"id": i, "name": f"Mask {len(l['masks']) + 1}", "shape": p.get("shape", "rect"), "rect": [x, y, w, h],
                               "vertices": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                               "feather": [0.0, 0.0], "opacity": 100.0, "expansion": 0.0, "mode": p.get("mode", "Add"), "inverted": False})
            return {"mask": i}
        if cid == "mask.new":                                           # UX9 U3: a shape from points
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            i = self.nid()
            verts = [[float(v[0]), float(v[1])] for v in p["vertices"]]
            l["masks"].append({"id": i, "name": f"Mask {len(l['masks']) + 1}", "shape": "poly", "rect": None, "vertices": verts, "closed": p.get("closed", True),
                               "feather": [0.0, 0.0], "opacity": 100.0, "expansion": 0.0, "mode": p.get("mode", "Add"), "inverted": False})
            return {"mask": i}
        if cid == "track.mask":                                         # D116: the fake tracker slides the mask one pixel right per frame
            self.edit()
            c = self.comp(p.get("comp"))
            l = self.layer(c, p["layer"])
            m = self.mask_of(l, p["mask"])
            rate = c["frameRate"]
            n = int(round(c["duration"] * rate))
            i0 = int(round(self.p["time"] * rate))
            keys = m.setdefault("path_keys", [])
            keys[:] = [k for k in keys if k["time"] < i0 / rate - 1e-6]
            for i in range(i0, n):
                keys.append({"time": i / rate, "value": self.path_value(m, [[x + (i - i0), y] for x, y in m["vertices"]]), "in": "linear", "out": "linear"})
            return {"mask": m["id"], "method": p.get("method", "positionScaleRotation"), "frames": max(0, n - 1 - i0), "start": i0 / rate, "end": (n - 1) / rate,
                    "running": False, "progress": None, "faceModel": None}
        if cid == "objectMatte.apply":                                  # D116: an Object Matte effect on the layer from a click
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            d = fx_def("Object Matte")
            uid = self.nid()
            l["effects"].append({"uid": uid, "id": d["id"], "name": "Object Matte", "enabled": True, "params": {q["id"]: q["default"] for q in d["params"]},
                                 "object": {"point": p["point"], "frame": int(p.get("frame", 0)), "computed": [], "frozen": False}})
            return {"effect": uid, "layer": l["id"], "frame": int(p.get("frame", 0)), "span": [-int(p.get("before", 30)), int(p.get("after", 30))], "track": True, "updated": False}
        if cid in ("objectMatte.propagate", "objectMatte.status", "objectMatte.freeze"):
            c = self.comp(p.get("comp"))
            l = self.layer(c, p["layer"])
            e = next((e for e in reversed(l["effects"]) if "object" in e), None)
            if e is None:
                raise ValueError("no Object Matte on the layer")
            n = int(round(c["duration"] * c["frameRate"]))
            if cid == "objectMatte.propagate":
                self.edit()
                e["object"]["computed"] = list(range(n))
            if cid == "objectMatte.freeze":
                self.edit()
                e["object"]["frozen"] = True
            o = e["object"]
            return {"effect": e["uid"], "layer": l["id"], "frames": n, "computed": o["computed"], "frozen": o["frozen"], "running": False, "progress": None, "pending": not o["computed"]}
        if cid == "mask.setVertex":
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            m = next((m for m in l["masks"] if str(m["id"]) == str(p["mask"]) or m["name"] == p["mask"]), None)
            if m is None:
                raise ValueError(f"no mask {p['mask']}")
            m["vertices"][int(p["index"])] = [float(p["point"][0]), float(p["point"][1])]
            return None
        if cid in ("layer.mask.set", "layer.mask.invert", "layer.mask.mode", "layer.mask.remove", "layer.mask.shape"):
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            if not l["masks"]:
                raise ValueError("the layer has no mask")
            m = next((m for m in l["masks"] if str(m["id"]) == str(p.get("mask"))), l["masks"][-1])
            if cid == "layer.mask.set":
                f_ = p["field"]
                if f_ not in ("feather", "opacity", "expansion"):
                    raise ValueError("field: feather|opacity|expansion")
                v = p["value"]
                m[f_] = [float(v), float(v)] if f_ == "feather" and not isinstance(v, list) else v
            elif cid == "layer.mask.invert":
                m["inverted"] = bool(p["value"]) if "value" in p else not m["inverted"]
            elif cid == "layer.mask.mode":
                m["mode"] = p["mode"]
            elif cid == "layer.mask.shape":
                x, y, w, h = p["rect"]
                m["rect"], m["shape"], m["vertices"] = p["rect"], p.get("shape", m["shape"]), [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            else:
                l["masks"].remove(m)
                return {"removed": 1}
            return {"masks": 1}
        if cid == "layer.timing":                                      # AE2d: in / out trimmed, or the layer moved by delta
            self.edit()
            for l in self.layers_of(p):
                if "delta" in p:
                    d = float(p["delta"])
                    l["in"], l["out"], l["start"] = l["in"] + d, l["out"] + d, l["start"] + d
                for k in ("in", "out", "start"):
                    if k in p:
                        l[k] = float(p[k])
            return None
        if cid == "layer.slip":
            self.edit()
            d = float(p["delta"]) if "delta" in p else float(p.get("frames", 0)) / self.comp(p.get("comp"))["frameRate"]
            return {"slipped": [{"layer": l["id"], "delta": d} for l in self.layers_of(p)]}
        if cid == "effect.apply":
            d = fx_def(p["effect"])
            if d is None:
                raise ValueError(f"unknown effect `{p['effect']}`")
            self.edit()
            paths, uids = [], []
            for l in self.layers_of(p):
                same = sum(1 for e in l["effects"] if e["id"] == d["id"])
                uid = self.nid()
                l["effects"].append({"uid": uid, "id": d["id"], "name": d["name"] if same == 0 else f"{d['name']} {same + 1}", "enabled": True,
                                     "params": {q["id"]: q["default"] for q in d["params"]}})
                paths.append(f"effects/#{len(l['effects'])}")
                uids.append(uid)
            return {"effect": d["id"], "effects": uids, "paths": paths}
        if cid in ("effect.toggle", "effect.remove", "effect.reset"):
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            ref = p["effect"]
            e = next((e for e in l["effects"] if str(e["uid"]) == str(ref) or e["name"] == ref), None)
            if e is None and isinstance(ref, int) and 1 <= ref <= len(l["effects"]):
                e = l["effects"][ref - 1]
            if e is None:
                raise ValueError(f"no effect {ref}")
            if cid == "effect.toggle":
                e["enabled"] = bool(p["value"]) if "value" in p else not e["enabled"]
                return e["enabled"]
            if cid == "effect.reset":
                e["params"] = {q["id"]: q["default"] for q in fx_def(e["id"])["params"]}
                return {}
            l["effects"].remove(e)
            return len(l["effects"])
        if cid == "file.projectSettings":
            self.edit()
            if "renderer" in p:
                self.p["settings"]["renderer"] = p["renderer"]
            return dict(self.p["settings"])
        if cid in ("file.saveCopy", "file.saveAs", "file.save"):
            path = p.get("path") or self.p["path"]
            if not path:
                raise ValueError("the project has no file: give `path`")
            Path(path).write_text(json.dumps(self.p, indent=1), encoding="utf-8")
            if cid != "file.saveCopy":
                self.p["path"] = path
                self.p["dirty"] = False
            return {"path": path}
        if cid == "file.open":
            self.load(p["path"])
            return {}
        if cid == "edit.undo":
            if self.undo:
                self.redo.append(json.dumps(self.p))
                self.p = json.loads(self.undo.pop())
            return {}
        if cid == "edit.redo":
            if self.redo:
                self.undo.append(json.dumps(self.p))
                self.p = json.loads(self.redo.pop())
            return {}
        if cid == "time.go":
            c = self.comp(p.get("comp"))
            self.p["time"] = 0.0 if p.get("to") == "start" else c["duration"] - 1 / c["frameRate"]
            return {}
        if cid == "time.nextFrame":
            self.p["time"] += 1 / self.comp(p.get("comp"))["frameRate"]
            return {}
        if cid == "fake.sleep":                                     # the tests: a request that never answers in time
            time.sleep(float(p.get("seconds", 2)))
            return {}
        raise ValueError(f"unknown command `{cid}`")

    def load(self, path: str) -> None:
        self.p = json.loads(Path(path).read_text(encoding="utf-8"))
        self.p["path"] = path
        self.next = max([self.next, *(int(k) + 1 for k in self.p["items"]), *(l["id"] + 1 for c in self.p["comps"].values() for l in c["layers"])])
        self.undo.clear()
        self.redo.clear()

    # ---- tools ----------------------------------------------------------------------------------
    def tool(self, name: str, a: dict) -> list[dict]:
        text = lambda v: [{"type": "text", "text": json.dumps(v)}]   # noqa: E731
        if name == "command_run":
            return text(self.command(a["id"], a.get("params") or {}))
        if name == "set_property" and str(a["path"]).startswith("effects/#"):          # AE3: an effect's parameter
            self.edit()
            l = self.layer(self.comp(a.get("comp")), a["layer"])
            n, pid = a["path"].split("/", 2)[1:]
            e = l["effects"][int(n.lstrip("#")) - 1]
            if pid not in e["params"]:
                raise ValueError(f"no property `{a['path']}`")
            e["params"][pid] = a["value"]
            return text({"path": a["path"], "value": a["value"], "animated": False})
        if name in ("set_property", "get_property") and str(a["path"]).startswith("masks/"):   # D116: a mask's path, keyed with a time
            l = self.layer(self.comp(a.get("comp")), a["layer"])
            seg, field = a["path"].split("/")[1:3]
            m = l["masks"][int(seg.split("#")[1]) - 1 if "#" in seg else 0]
            if field != "path":
                raise ValueError(f"no property `{a['path']}`")
            keys = m.setdefault("path_keys", [])
            if name == "get_property":
                return text({"layer": l["id"], "path": a["path"], "uid": m["id"] * 10, "type": "path", "value": self.path_value(m), "animated": bool(keys), "keys": keys, "expression": None})
            self.edit()
            v = a["value"]["v"]
            if "time" in a:
                keys[:] = [k for k in keys if abs(k["time"] - float(a["time"])) >= 1e-6]
                keys.append({"time": float(a["time"]), "value": a["value"], "in": "linear", "out": "linear"})
                keys.sort(key=lambda k: k["time"])
            if "time" not in a or not [k for k in keys if k["time"] < float(a["time"]) - 1e-6]:
                m["vertices"], m["closed"] = [[float(q[0]), float(q[1])] for q in v["vertices"]], v.get("closed", True)   # the shape shown: the first key's
            return text({"path": a["path"], "value": a["value"], "animated": bool(keys)})
        if name == "set_property":
            self.edit()
            l = self.layer(self.comp(a.get("comp")), a["layer"])
            key = a["path"].split("/")[-1]
            if "time" in a:
                keys = l["keys"].setdefault(key, [])
                keys[:] = [k for k in keys if abs(k["time"] - float(a["time"])) >= 1e-6]   # a key there is replaced
                keys.append({"time": float(a["time"]), "value": a["value"], "in": "linear", "out": "linear"})
                keys.sort(key=lambda k: k["time"])
            l[key] = a["value"]
            return text({"path": a["path"], "value": a["value"], "animated": bool(l["keys"].get(key))})
        if name == "get_property":
            l = self.layer(self.comp(a.get("comp")), a["layer"])
            key = a["path"].split("/")[-1]
            keys = l["keys"].get(key, [])
            return text({"layer": l["id"], "path": a["path"], "uid": key, "type": dict(FLAT).get(key, "scalar"), "value": l.get(key), "animated": bool(keys), "keys": keys, "expression": None})
        if name == "get_layer":
            l = self.layer(self.comp(a.get("comp")), a["layer"])
            props = [{"path": f"transform/{k}", "type": t, "value": l.get(k), **({"keys": len(l["keys"][k])} if l["keys"].get(k) else {})} for k, t in FLAT]
            fx_flat = [{"path": f"effects/#{n}/{q['id']}", "type": q["type"], "value": e["params"].get(q["id"], q["default"])}
                       for n, e in enumerate(l["effects"], 1) for q in fx_def(e["id"])["params"]]
            head = {k: v for k, v in l.items() if k not in ("masks", "effects", "keys", "anchor", "position", "scale", "rotation", "opacity")}
            if a.get("flat"):
                return text({**head, "time": self.p["time"], "properties": props + fx_flat})
            effects = [{"effect": e["id"], "enabled": e["enabled"], "match": e["id"], "name": e["name"], "path": f"effects/#{n}", "uid": e["uid"],
                        "children": [{"match": q["id"].split("/")[-1], "name": q["name"], "path": f"effects/#{n}/{q['id']}", "type": q["type"], "uid": e["uid"] * 100 + j, "value": e["params"].get(q["id"], q["default"])}
                                     for j, q in enumerate(fx_def(e["id"])["params"], 1)]} for n, e in enumerate(l["effects"], 1)]
            masks = [{"name": m["name"], "path": f"masks/mask{'' if i == 0 else f'#{i + 1}'}", "uid": m["id"], "match": "mask", "enabled": True,
                      "mask": {"inverted": m["inverted"], "mode": m["mode"]},
                      "children": [{"path": f"masks/mask{'' if i == 0 else f'#{i + 1}'}/{k}", "name": f"Mask {k.title()}", "match": k, "uid": m["id"] * 10 + j,
                                    "type": "vec2" if k == "feather" else "path" if k == "path" else "scalar",
                                    "value": self.path_value(m) if k == "path" else m[k], **({"animated": True, "keys": len(m["path_keys"])} if k == "path" and m.get("path_keys") else {})}
                                   for j, k in enumerate(("path", "feather", "opacity", "expansion"))]} for i, m in enumerate(l["masks"])]
            tree = {"name": l["name"], "path": "", "uid": l["id"], "match": "layer", "enabled": True, "children": [
                {"name": "Transform", "path": "transform", "uid": l["id"] * 100, "match": "transform", "enabled": True, "children": [{**p, "uid": l["id"] * 100 + k} for k, p in enumerate(props, 1)]},
                {"name": "Masks", "path": "masks", "uid": l["id"] * 100 + 50, "match": "masks", "enabled": True, "children": masks},
                {"name": "Effects", "path": "effects", "uid": l["id"] * 100 + 60, "match": "effects", "enabled": True, "children": effects}]}
            return text({**head, "time": self.p["time"], "properties": tree})
        if name == "list_effects":
            items = [fx_def(n) for n in FX_REGISTRY]
            q = str(a.get("filter", "")).lower()
            return text([e for e in items if not q or q in e["name"].lower() or q in e["id"] or q in e["category"].lower()])
        if name == "command_batch":
            results, failed = [], 0
            for i, step in enumerate(a.get("steps") or []):
                try:
                    results.append({"ok": True, "result": self.command(step["id"], step.get("params") or {})})
                except (KeyError, ValueError, TypeError) as e:
                    results.append({"ok": False, "error": str(e)})
                    failed += 1
                    if a.get("stop_on_error", True):
                        break
            return text({"completed": len(results) - failed, "failed": failed, "results": results})
        if name == "get_comp":
            c = self.comp(a.get("comp"))
            return text({**{k: v for k, v in c.items() if k != "layers"}, "layers": [{**l, "index": i + 1} for i, l in enumerate(c["layers"])]})
        if name == "get_project":
            return text({"path": self.p["path"], "dirty": self.p["dirty"], "activeComp": self.p["active"], "revision": self.p["revision"],
                         "items": list(self.p["items"].values())})
        if name == "open_project":
            if a.get("path"):
                self.load(a["path"])
            elif a.get("new"):
                self.__init__()
            return self.tool("get_project", {})
        if name == "save_project":
            return text(self.command("file.saveAs" if a.get("path") else "file.save", {"path": a.get("path")}))
        if name in ("undo", "redo"):
            self.command(f"edit.{name}", {})
            return text({})
        if name == "add_effect":
            r = self.command("effect.apply", {"effect": a["effect"], "layers": [a["layer"]], "comp": a.get("comp")})
            for pid, v in (a.get("values") or {}).items():
                self.tool("set_property", {"layer": a["layer"], "path": f"{r['paths'][0]}/{pid}", "value": v, "comp": a.get("comp")})
            return text({"layer": a["layer"], "path": r["paths"][0], "params": a.get("values", {})})
        if name == "render_frame":
            c = self.comp(a.get("comp"))
            t = float(a.get("time", self.p["time"]))
            w, h = c["width"], c["height"]
            side = int(a.get("max_side", 960))
            if side and max(w, h) > side:
                k = side / max(w, h)
                w, h = max(1, round(w * k)), max(1, round(h * k))
            data = png(w, h, (round(t * c["frameRate"]) % 256, self.p["revision"] % 256, 128))
            if a.get("path"):
                Path(a["path"]).write_bytes(data)
            info = {"comp": c["id"], "time": t, "width": w, "height": h}
            if a.get("inline") is False:
                return text(info)
            return [{"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"}, {"type": "text", "text": json.dumps(info)}]
        raise ValueError(f"unknown tool `{name}`")


def serve(argv: list[str]) -> int:
    f = Fake()
    if "--project" in argv:
        f.load(argv[argv.index("--project") + 1])
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            out.flush()
            continue
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:
            continue                                                # a notification
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}}, "serverInfo": {"name": "fake-effectcraft", "version": "0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/call":
            try:
                content = f.tool(params["name"], params.get("arguments") or {})
                failed = 0
                try:                                                    # as the real server: a batch with a failed step is an error reply
                    failed = int(json.loads(next(c["text"] for c in content if c.get("type") == "text")).get("failed", 0))
                except (StopIteration, ValueError, TypeError, AttributeError):
                    failed = 0
                result = {"content": content, "isError": failed > 0}
            except (KeyError, ValueError, TypeError) as e:
                result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        else:
            out.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}) + "\n")
            out.flush()
            continue
        out.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
        out.flush()
    return 0


def render(argv: list[str]) -> int:
    """`render --project P [--comp C] --out X_[####].png --format png ...`: a flat PNG a frame over the comp's duration."""
    def opt(k: str, default=None):
        return argv[argv.index(k) + 1] if k in argv else default
    f = Fake()
    f.load(opt("--project"))
    c = f.comp(opt("--comp"))
    out = opt("--out")
    if not out:
        print("render: --out FILE is required", file=sys.stderr)
        return 2
    n = int(round(c["duration"] * c["frameRate"]))
    first = None
    for i in range(n):
        k = out.find("[")
        width = out[k + 1:out.index("]", k)].count("#") if k >= 0 else 0
        path = out[:k] + str(i).zfill(width) + out[out.index("]", k) + 1:] if k >= 0 else out
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(png(c["width"], c["height"], (i % 256, f.p["revision"] % 256, 128)))
        first = first or path
    print(f"{c['name']} -> {out} ({c['width']}x{c['height']}, {n} frames, PNG Sequence - RGB)\ndone: {c['name']} -> {first} in 0.01s")   # ASCII: a cp1252 console
    return 0


if __name__ == "__main__":
    sys.exit(serve(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "mcp" else render(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "render" else 2)
