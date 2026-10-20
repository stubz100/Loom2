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
        if cid == "layer.addItem":
            self.edit()
            c = self.comp(p.get("comp"))
            item = self.p["items"][str(p["item"])]
            i = self.nid()
            c["layers"].insert(0, {"id": i, "name": item["name"], "item": item["id"], "type": "AV", "label": "Lavender", "blendMode": "Normal", "trackMatte": None,
                                   "parent": None, "in": 0.0, "out": c["duration"], "start": 0.0, "stretch": 100.0,
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
            l["masks"].append({"id": i, "shape": p.get("shape", "rect"), "rect": p.get("rect"), "feather": 0.0, "opacity": 100.0, "expansion": 0.0})
            return {"mask": i}
        if cid == "layer.mask.set":
            self.edit()
            l = self.layer(self.comp(p.get("comp")), p["layer"])
            if not l["masks"]:
                raise ValueError("the layer has no mask")
            l["masks"][-1][p["field"]] = p["value"]
            return {}
        if cid == "effect.apply":
            self.edit()
            paths = []
            for l in self.layers_of(p):
                l["effects"].append({"name": p["effect"], "params": {}})
                paths.append(f"effects/#{len(l['effects'])}")
            return {"paths": paths}
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
            head = {k: v for k, v in l.items() if k not in ("masks", "effects", "keys", "anchor", "position", "scale", "rotation", "opacity")}
            return text({**head, "time": self.p["time"], "properties": props})
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
