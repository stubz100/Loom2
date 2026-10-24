"""CE1 (proto01_animate 30 §10, D126): a stand-in for `filmcraft-cli` for the offline suite and the e2e, the way fake_effectcraft.py stands
in for EffectCraft. Runs under the orchestrator's interpreter (PyAV, NumPy, soundfile for the export).

    python fake_filmcraft.py [--data-dir D] [--project P] mcp           the MCP subset loom2/filmcraft.py uses, JSON-RPC over stdio
    python fake_filmcraft.py [--data-dir D] --project P run SCRIPT      a JSON-lines script of commands (the movie's export)

It keeps the project in FilmCraft's own JSON shape (`filmcraft.project`, schema 13: items with `kind` Media / Sequence and `metadata`,
sequences with video and audio tracks of items in ticks and transitions) for the commands loom2 sends — prefs.set, file.newProject,
file.newSequence, file.open, file.save(As), file.import (media, PNG sequences at the preference's rate, audio), timeline.place (overwrite),
edit.clear, sequence.applyVideoTransition (centred on the cut), metadata.set, clip.replaceFromBin, project.delete, file.exportMedia;
CE2's editor commands as the probe saw the real ones do them — timeline.trim (regular / ripple), roll, slip, slide, razor (the
dissolve follows the new piece), move (across tracks, its transitions dropped), edit.rippleDelete, clip.speedDuration, clip.frameHold,
timeline.setTrack, sequence.addTracks, timeline.select, edit.copy / pasteAttributes, edit.undo / redo (snapshots), and
file.exportInterchange (a small FCPXML or EDL of V1). A frame is a flat colour: R = the frame
number, G = how many clips V1 holds, B = 128. The export writes an H.264 MP4 at the sequence's size — each V1 clip a flat colour (its media
item's id × 40), a dissolve blended — and A1's audio clips mixed into one AAC track where they sit.
"""
from __future__ import annotations

import base64
import json
import re
import struct
import sys
import wave
import zlib
from pathlib import Path

TICK = 254_016_000_000


def png(w: int, h: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class Refused(Exception):
    pass


class Fake:
    def __init__(self) -> None:
        self.prefs = {"playback.hardwareDecoding": "auto", "media.indeterminateTimebase": "29.97df", "media.defaultMediaScaling": "none"}
        self.path: str | None = None
        self.doc = self.blank("Untitled")
        self.seq: int | None = None
        self.undo: list[dict] = []
        self.redo: list[dict] = []
        self.selection: list[int] = []
        self.clipboard: list | None = None

    @staticmethod
    def blank(name: str) -> dict:
        return {"format": "filmcraft.project", "schema_version": 13, "generator": "fake_filmcraft",
                "project": {"name": name, "settings": {}, "root": {"children": []}, "items": {}, "next_id": 1}, "view": {}}

    def new_id(self) -> int:
        n = self.doc["project"]["next_id"]
        self.doc["project"]["next_id"] = n + 1
        return n

    def items(self) -> dict:
        return self.doc["project"]["items"]

    def sequence(self) -> dict:
        if self.seq is None:
            raise Refused("no sequence")
        return self.items()[str(self.seq)]["kind"]["Sequence"]

    def track(self, ref) -> dict:
        s = self.sequence()
        if isinstance(ref, str) and re.fullmatch(r"[VA]\d+", ref):
            tracks = s["video_tracks"] if ref[0] == "V" else s["audio_tracks"]
            k = int(ref[1:]) - 1
            if k >= len(tracks):
                raise Refused(f"no track {ref}")
            return tracks[k]
        for t in s["video_tracks"] + s["audio_tracks"]:
            if t["id"] == ref:
                return t
        raise Refused(f"no track {ref}")

    def find_clip(self, cid: int) -> tuple[dict, dict]:
        s = self.sequence()
        for t in s["video_tracks"] + s["audio_tracks"]:
            for ti in t["items"]:
                if ti["id"] == cid:
                    return t, ti
        raise Refused(f"no clip {cid}")

    # ---- media ------------------------------------------------------------------------------------
    def media_info(self, path: Path, sequence: bool) -> dict:
        if sequence:
            m = re.match(r"(.*?)(\d+)(\.\w+)$", path.name)
            if not m:
                raise Refused(f"{path.name} is not numbered")
            head, digits, ext = m.groups()
            n = 0
            while (path.parent / f"{head}{int(digits) + n:0{len(digits)}d}{ext}").is_file():
                n += 1
            rate = round(float(self.prefs["media.indeterminateTimebase"].rstrip("df")))
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
            return {"name": path.name, "kind": "Image Sequence", "duration": n * TICK // rate, "frames": n,
                    "video": {"width": w, "height": h, "frame_rate": {"num": rate, "den": 1}}, "audio_streams": []}
        if path.suffix.lower() == ".wav":
            with wave.open(str(path)) as w:
                sr, frames, ch = w.getframerate(), w.getnframes(), w.getnchannels()
            return {"name": path.name, "kind": "AudioOnly", "duration": frames * TICK // sr, "video": None,
                    "audio_streams": [{"sample_rate": sr, "channels": ch, "codec": "PCM"}]}
        import av
        with av.open(str(path)) as c:
            v = c.streams.video[0]
            rate = int(round(float(v.average_rate)))
            n = v.frames or sum(1 for _ in c.decode(video=0))
            return {"name": path.name, "kind": "Movie", "duration": n * TICK // rate, "frames": n,
                    "video": {"width": v.codec_context.width, "height": v.codec_context.height, "frame_rate": {"num": rate, "den": 1}}, "audio_streams": []}

    # ---- commands ---------------------------------------------------------------------------------
    PURE = {"prefs.set", "file.newProject", "file.closeProject", "file.newSequence", "file.save", "file.saveAs", "file.open", "file.import",
            "file.exportMedia", "file.exportInterchange", "timeline.select", "edit.copy", "edit.undo", "edit.redo", "metadata.set", "project.delete"}

    def run(self, cid: str, p: dict):
        if cid not in self.PURE:
            import copy
            before = copy.deepcopy(self.doc)
            r = self.run_edit(cid, p)
            self.undo.append(before)
            self.redo.clear()
            return r
        if cid == "edit.undo":
            if not self.undo:
                raise Refused("nothing to undo")
            self.redo.append(self.doc)
            self.doc = self.undo.pop()
            return {"undone": True}
        if cid == "edit.redo":
            if not self.redo:
                raise Refused("nothing to redo")
            self.undo.append(self.doc)
            self.doc = self.redo.pop()
            return {"redone": True}
        if cid == "timeline.select":
            self.selection = [int(c) for c in p.get("clips") or []]
            return {"selection": self.selection}
        if cid == "edit.copy":
            if not self.selection:
                raise Refused("command `edit.copy` is not available right now: nothing selected")
            _, ti = self.find_clip(self.selection[0])
            self.clipboard = [dict(e) for e in ti.get("effects", [])]
            return None
        if cid == "file.exportInterchange":
            return self.interchange(p.get("format", "xml"), Path(p["path"]))
        return self.run_edit(cid, p)

    def run_edit(self, cid: str, p: dict):
        ed = self.editor(cid, p)
        if ed is not NotImplemented:
            return ed
        if cid == "prefs.set":
            self.prefs.update(p.get("values") or {p["key"]: p["value"]})
            return {"ok": True}
        if cid in ("file.newProject", "file.closeProject"):
            self.doc, self.path, self.seq = self.blank(p.get("name", "Untitled")), None, None
            return None
        if cid == "file.newSequence":
            sid = self.new_id()
            fps = round(float(p.get("fps", 23.976)))

            def tracks(kind: str, n: int) -> list[dict]:
                return [{"id": self.new_id(), "kind": kind, "name": f"{kind} {k + 1}", "items": [], "transitions": [], "locked": False,
                         "enabled": True, "muted": False} for k in range(n)]
            self.items()[str(sid)] = {"id": sid, "name": p["name"], "label": "Forest", "metadata": {}, "created": 0,
                                      "kind": {"Sequence": {"settings": {"width": p.get("width", 1920), "height": p.get("height", 1080),
                                                                         "frame_rate": {"num": fps, "den": 1}, "sample_rate": p.get("sampleRate", 48000)},
                                                            "video_tracks": tracks("Video", int(p.get("video", 3))), "audio_tracks": tracks("Audio", int(p.get("audio", 3))),
                                                            "markers": []}}}
            self.seq = sid
            return {"sequence": sid}
        if cid in ("file.save", "file.saveAs"):
            path = p.get("path") or self.path
            if not path:
                raise Refused("no path")
            Path(path).write_text(json.dumps(self.doc), encoding="utf-8")
            self.path = str(path)
            return {"path": self.path}
        if cid == "file.open":
            self.doc = json.loads(Path(p["path"]).read_text(encoding="utf-8"))
            self.path = p["path"]
            self.seq = next((int(k) for k, it in self.items().items() if "Sequence" in it["kind"]), None)
            return {"path": self.path}
        if cid == "file.import":
            out = []
            for f in p["paths"]:
                path = Path(f)
                if not path.is_file():
                    raise Refused(f"{f}: The system cannot find the path specified. (os error 3)")
                info = self.media_info(path, bool(p.get("imageSequence")))
                iid = self.new_id()
                self.items()[str(iid)] = {"id": iid, "name": path.name, "label": "Violet", "metadata": {}, "created": iid,
                                          "kind": {"Media": {"media": {"File": {"path": str(path)}}, "info": info}}}
                out.append(iid)
            return {"items": out, "errors": []}
        if cid == "timeline.place":
            it = self.items().get(str(p["item"]))
            if it is None or "Media" not in it["kind"]:
                raise Refused(f"no media item {p['item']}")
            info = it["kind"]["Media"]["info"]
            t = self.track(p.get("track", "V1"))
            start = int(p["time"]) if "time" in p else (int(p["frame"]) * TICK // 24 if "frame" in p else round(float(p["seconds"]) * TICK))
            src = int(p.get("sourceIn", 0))
            dur = int(p.get("duration", info["duration"] - src))
            end = start + dur
            keep = []
            for ti in t["items"]:                                      # overwrite: what it covers goes, what it overlaps is trimmed
                a, b = ti["start"], ti["start"] + ti["duration"]
                if b <= start or a >= end:
                    keep.append(ti)
                elif a < start:
                    ti["duration"] = start - a
                    keep.append(ti)
                elif b > end:
                    ti["source_in"] += end - a
                    ti["start"], ti["duration"] = end, b - end
                    keep.append(ti)
            cid2 = self.new_id()
            keep.append({"id": cid2, "item": int(p["item"]), "name": it["name"], "start": start, "duration": dur, "source_in": src, "speed": 1.0,
                         "reverse": False, "enabled": True, "effects": [], "markers": [], "gain_db": 0.0, "scale_to_frame": True})
            t["items"] = sorted(keep, key=lambda x: x["start"])
            return {"clips": [cid2]}
        if cid == "edit.clear":
            gone = set(p.get("clips") or [])
            s = self.sequence()
            for t in s["video_tracks"] + s["audio_tracks"]:
                t["items"] = [ti for ti in t["items"] if ti["id"] not in gone]
                t["transitions"] = [x for x in t["transitions"] if x.get("from") not in gone and x.get("to") not in gone]
            return {"cleared": len(gone)}
        if cid == "sequence.applyVideoTransition":
            t, ti = self.find_clip(int(p["clip"]))
            prev = next((x for x in t["items"] if x["start"] + x["duration"] == ti["start"]), None)
            dur = int(p.get("frames", 24)) * TICK // round(self.sequence()["settings"]["frame_rate"]["num"])
            xid = self.new_id()
            t["transitions"].append({"id": xid, "effect": {"effect": p.get("effect", "cross_dissolve"), "enabled": True, "params": {}},
                                     "start": ti["start"] - dur // 2, "duration": dur, "from": prev["id"] if prev else None, "to": ti["id"], "align": "CenterAtCut"})
            return {"transition": xid}
        if cid == "clip.replaceFromBin":
            it = self.items().get(str(p["item"]))
            if it is None or "Media" not in it["kind"]:
                raise Refused(f"no media item {p['item']}")
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["item"], ti["name"] = int(p["item"]), it["name"]
                if not p.get("keepSourceIn"):
                    ti["source_in"] = 0
            return {"replaced": len(p.get("clips") or [])}
        if cid == "project.delete":
            for i in p.get("items") or []:
                self.items().pop(str(i), None)
            return {"deleted": len(p.get("items") or [])}
        if cid == "metadata.set":
            it = self.items().get(str(p["item"]))
            if it is None:
                raise Refused(f"no item {p['item']}")
            it["metadata"].update(p.get("fields") or {p["field"]: p["value"]})
            return {"item": int(p["item"]), "metadata": it["metadata"], "changed": True}
        if cid == "file.exportMedia":
            if p.get("format") == "png":                               # a PNG sequence: frame000.png … beside `path`, at `scale`
                return self.export_png(Path(p["path"]), float(p.get("scale", 1.0)))
            return self.export(Path(p["path"]))
        raise Refused(f"unknown command `{cid}`")

    # ---- CE2: the editor's commands, as the real ones do them (the probe on 764723f) ---------------------------------------------------
    def fps(self) -> int:
        return round(self.sequence()["settings"]["frame_rate"]["num"])

    def delta(self, p: dict) -> int:
        return int(p["delta"]) if "delta" in p else int(p["deltaFrames"]) * TICK // self.fps()

    def neighbours(self, t: dict, ti: dict) -> tuple[dict | None, dict | None]:
        items = sorted(t["items"], key=lambda x: x["start"])
        k = items.index(ti)
        return (items[k - 1] if k > 0 else None), (items[k + 1] if k + 1 < len(items) else None)

    def editor(self, cid: str, p: dict):
        if cid == "timeline.setTrack":
            t = self.track(p["track"])
            for k, v in (("name", "name"), ("locked", "locked"), ("muted", "muted"), ("enabled", "enabled")):
                if v in p:
                    t[k] = p[v]
            return None
        if cid == "timeline.trim":
            t, ti = self.find_clip(int(p["clip"]))
            d = self.delta(p)
            if p.get("edge") == "in":
                ti["start"] += d
                ti["source_in"] += round(d * ti.get("speed", 1.0))
                ti["duration"] -= d
            else:
                old_end = ti["start"] + ti["duration"]
                ti["duration"] += d
                if p.get("mode") == "ripple":
                    for x in t["items"]:
                        if x is not ti and x["start"] >= old_end:
                            x["start"] += d
                    for x in t["transitions"]:
                        if x["start"] >= old_end - x["duration"]:
                            x["start"] += d
            return {"delta": d}
        if cid == "timeline.roll":
            t, left = self.find_clip(int(p["left"]))
            _, right = self.find_clip(int(p["right"]))
            d = self.delta(p)
            left["duration"] += d
            right["start"] += d
            right["source_in"] += d
            right["duration"] -= d
            for x in t["transitions"]:
                if x.get("from") == left["id"] and x.get("to") == right["id"]:
                    x["start"] += d
            return {"delta": d}
        if cid == "timeline.slip":
            _, ti = self.find_clip(int(p["clip"]))
            ti["source_in"] += self.delta(p)
            return None
        if cid == "timeline.slide":
            t, ti = self.find_clip(int(p["clip"]))
            d = self.delta(p)
            prev, nxt = self.neighbours(t, ti)
            ti["start"] += d
            if prev is not None:
                prev["duration"] += d
            if nxt is not None:
                nxt["start"] += d
                nxt["source_in"] += d
                nxt["duration"] -= d
            return None
        if cid == "timeline.razor":
            at = int(p["time"])
            tracks = [self.track(p["track"])] if p.get("track") is not None else self.sequence()["video_tracks"] + self.sequence()["audio_tracks"]
            cuts = 0
            for t in tracks:
                for ti in list(t["items"]):
                    if ti["start"] < at < ti["start"] + ti["duration"]:
                        nid = self.new_id()
                        head = at - ti["start"]
                        piece = {**ti, "id": nid, "start": at, "duration": ti["duration"] - head, "source_in": ti["source_in"] + round(head * ti.get("speed", 1.0))}
                        ti["duration"] = head
                        t["items"].append(piece)
                        for x in t["transitions"]:
                            if x.get("from") == ti["id"] and x["start"] >= at - x["duration"]:
                                x["from"] = nid
                        cuts += 1
                t["items"].sort(key=lambda x: x["start"])
            return {"cuts": cuts}
        if cid == "timeline.move":
            moved = []
            for m in p.get("moves") or []:
                t, ti = self.find_clip(int(m["clip"]))
                t["items"].remove(ti)
                t["transitions"] = [x for x in t["transitions"] if ti["id"] not in (x.get("from"), x.get("to"))]
                dest = self.track(m.get("track", t["id"]))
                ti["start"] = int(m["time"])
                dest["items"].append(ti)
                dest["items"].sort(key=lambda x: x["start"])
                moved.append(ti["id"])
            return {"moved": moved, "overwritten": []}
        if cid == "edit.rippleDelete":
            for c in p.get("clips") or []:
                t, ti = self.find_clip(int(c))
                t["items"].remove(ti)
                t["transitions"] = [x for x in t["transitions"] if ti["id"] not in (x.get("from"), x.get("to"))]
                for x in t["items"]:
                    if x["start"] >= ti["start"] + ti["duration"]:
                        x["start"] -= ti["duration"]
            return None
        if cid == "clip.speedDuration":
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["speed"] = float(p.get("speed", 100)) / 100.0
            return None
        if cid == "clip.frameHold":
            out = []
            for c in p.get("clips") or []:
                t, ti = self.find_clip(int(c))
                at = int(p.get("time", ti["start"]))
                if ti["start"] < at < ti["start"] + ti["duration"]:
                    self.editor("timeline.razor", {"time": at, "track": t["id"]})
                    piece = next(x for x in t["items"] if x["start"] == at)
                    piece["frame_hold"] = piece["source_in"]
                    out.append(piece["id"])
            return {"clips": out}
        if cid == "sequence.addTracks":
            s = self.sequence()
            made = {"video": [], "audio": [], "submix": []}
            for kind, key, label in (("video", "video_tracks", "Video"), ("audio", "audio_tracks", "Audio")):
                for _ in range(int(p.get(kind, 1 if kind == "video" else 0))):
                    tid = self.new_id()
                    s[key].append({"id": tid, "kind": label, "name": f"{label} {len(s[key]) + 1}", "items": [], "transitions": [], "locked": False,
                                   "enabled": True, "muted": False})
                    made[kind].append(tid)
            return made
        if cid == "edit.pasteAttributes":
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["effects"] = [dict(e) for e in (self.clipboard or [])]
            return None
        if cid == "markers.clearAll":
            self.sequence()["markers"] = []
            return None
        if cid == "markers.addChapter":
            mid = self.new_id()
            self.sequence()["markers"].append({"id": mid, "start": int(p.get("time", 0)), "duration": 0, "name": p.get("name", ""), "comment": "",
                                               "kind": "Chapter", "color": "Mango"})
            return {"marker": mid}
        if cid == "clip.rename":
            _, ti = self.find_clip(int(p["clip"]))
            ti["name"] = p["name"]
            return None
        return NotImplemented

    def interchange(self, fmt: str, out: Path) -> dict:
        s = self.sequence()
        fps = self.fps()
        v1 = sorted(s["video_tracks"][0]["items"], key=lambda x: x["start"])
        if fmt == "edl":
            rows = [f"{k + 1:03d}  AX       V     C        {ti['start'] * fps // TICK} {(ti['start'] + ti['duration']) * fps // TICK}\n* FROM CLIP NAME: {ti['name']}"
                    for k, ti in enumerate(v1)]
            text = "TITLE: " + self.items()[str(self.seq)]["name"] + "\n\n" + "\n".join(rows) + "\n"
        else:
            clips = "".join(f'<asset-clip name="{ti["name"]}" offset="{ti["start"] * fps // TICK}/{fps}s" duration="{ti["duration"] * fps // TICK}/{fps}s"/>' for ti in v1)
            clips += "".join(f'<chapter-marker start="{m["start"] * fps // TICK}/{fps}s" value="{m["name"]}"/>' for m in s.get("markers", []) if m.get("kind") == "Chapter")
            a1 = s["audio_tracks"][0]["items"] if s["audio_tracks"] else []                   # the dialogue: connected clips below the spine, as FilmCraft writes them
            clips += "".join(f'<asset-clip lane="-1" name="{ti["name"]}" offset="{ti["start"] * fps // TICK}/{fps}s" duration="{ti["duration"] * fps // TICK}/{fps}s"/>' for ti in a1)
            if a1:
                clips = '<resources><asset hasAudio="1"/></resources>' + clips
            text = f'<?xml version="1.0" encoding="UTF-8"?>\n<fcpxml version="1.10"><library><event><project><sequence><spine>{clips}</spine></sequence></project></event></library></fcpxml>\n'
        out.write_text(text, encoding="utf-8")
        return {"bytes": len(text), "path": str(out)}

    def inspect(self) -> dict:
        s = self.sequence()
        fps = s["settings"]["frame_rate"]["num"]

        def view(t: dict) -> dict:
            return {"id": t["id"], "name": t["name"], "items": [{**ti, "sourceIn": ti["source_in"]} for ti in t["items"]], "transitions": t["transitions"]}
        end = max([ti["start"] + ti["duration"] for t in s["video_tracks"] + s["audio_tracks"] for ti in t["items"]] or [0])
        return {"name": self.items()[str(self.seq)]["name"], "settings": s["settings"], "duration": end, "durationFrames": round(end * fps / TICK),
                "video": [view(t) for t in s["video_tracks"]], "audio": [view(t) for t in s["audio_tracks"]], "markers": s["markers"]}

    def frame(self, seconds: float, max_side: int) -> bytes:
        s = self.sequence()
        w, h = s["settings"]["width"], s["settings"]["height"]
        scale = min(1.0, max_side / max(w, h)) if max_side else 1.0
        f = round(seconds * s["settings"]["frame_rate"]["num"])
        return png(max(1, round(w * scale)), max(1, round(h * scale)), (f % 256, len(s["video_tracks"][0]["items"]) % 256, 128))

    def export_png(self, out: Path, scale: float) -> dict:
        s = self.sequence()
        fps = s["settings"]["frame_rate"]["num"]
        end = max([ti["start"] + ti["duration"] for ti in s["video_tracks"][0]["items"]] or [0])
        total = round(end * fps / TICK)
        w, h = max(2, round(s["settings"]["width"] * scale)), max(2, round(s["settings"]["height"] * scale))
        out.parent.mkdir(parents=True, exist_ok=True)
        width = max(3, len(str(total - 1)))
        for f in range(total):
            (out.parent / f"{out.stem}{f:0{width}d}.png").write_bytes(png(w, h, (f % 256, 0, 128)))
        return {"path": str(out), "result": {"frames": total}}

    def export(self, out: Path) -> dict:
        from fractions import Fraction

        import av
        import numpy as np
        import soundfile as sf
        s = self.sequence()
        fps, w, h = s["settings"]["frame_rate"]["num"], s["settings"]["width"], s["settings"]["height"]
        v1 = s["video_tracks"][0]
        end = max([ti["start"] + ti["duration"] for ti in v1["items"]] or [0])
        total = round(end * fps / TICK)
        colours = {ti["id"]: (ti["item"] * 40) % 256 for ti in v1["items"]}

        def colour_at(t: int) -> float:
            for x in v1["transitions"]:
                if x["start"] <= t < x["start"] + x["duration"] and x["from"] in colours and x["to"] in colours:
                    mix = (t - x["start"] + 0.5 * TICK / fps) / x["duration"]
                    return colours[x["from"]] * (1 - mix) + colours[x["to"]] * mix
            for ti in v1["items"]:
                if ti["start"] <= t < ti["start"] + ti["duration"]:
                    return colours[ti["id"]]
            return 0.0
        sr = 48000
        audio = np.zeros(int(round(end / TICK * sr)) + 1, dtype=np.float32)
        a1 = s["audio_tracks"][0]["items"] if s["audio_tracks"] else []
        for ti in a1:
            src = self.items()[str(ti["item"])]["kind"]["Media"]["media"]["File"]["path"]
            data, rate = sf.read(src, dtype="float32", always_2d=True)
            mono = data.mean(axis=1)
            if rate != sr:
                mono = np.interp(np.linspace(0, len(mono) - 1, int(len(mono) * sr / rate)), np.arange(len(mono)), mono).astype(np.float32)
            at = int(round(ti["start"] / TICK * sr))
            seg = mono[: max(0, min(len(mono), len(audio) - at, int(ti["duration"] / TICK * sr)))]
            audio[at:at + len(seg)] += seg
        out.parent.mkdir(parents=True, exist_ok=True)
        with av.open(str(out), "w", format="mp4") as c:
            vs = c.add_stream("libx264", rate=fps)
            vs.width, vs.height, vs.pix_fmt = w - w % 2, h - h % 2, "yuv420p"
            ast = c.add_stream("aac", rate=sr) if a1 else None
            if ast is not None:
                ast.layout = "mono"
            for f in range(total):
                v = int(round(colour_at(f * TICK // fps)))
                arr = np.full((vs.height, vs.width, 3), (v, 0, 0), dtype=np.uint8)
                for pkt in vs.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                    c.mux(pkt)
            for pkt in vs.encode():
                c.mux(pkt)
            if ast is not None:
                for i in range(0, len(audio), 1024):
                    af = av.AudioFrame.from_ndarray(np.ascontiguousarray(audio[i:i + 1024].reshape(1, -1)), format="fltp", layout="mono")
                    af.sample_rate, af.pts, af.time_base = sr, i, Fraction(1, sr)
                    for pkt in ast.encode(af):
                        c.mux(pkt)
                for pkt in ast.encode():
                    c.mux(pkt)
        return {"path": str(out), "frames": total}


def serve(fake: Fake) -> None:
    def reply(mid, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": mid, **({"error": error} if error else {"result": result})}
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    def text(obj, is_error=False):
        return {"content": [{"type": "text", "text": json.dumps(obj) if not isinstance(obj, str) else obj}], **({"isError": True} if is_error else {})}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:
            continue
        if method == "initialize":
            reply(mid, {"protocolVersion": params.get("protocolVersion"), "capabilities": {"tools": {}}, "serverInfo": {"name": "fake_filmcraft", "version": "0"}})
            continue
        if method != "tools/call":
            reply(mid, error={"code": -32601, "message": f"unknown method {method}"})
            continue
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            if name == "command_run":
                reply(mid, text(fake.run(args["id"], args.get("params") or {})))
            elif name == "command_batch":
                results, failed = [], 0
                for st in args.get("steps") or []:
                    try:
                        results.append({"ok": True, "result": fake.run(st["id"], st.get("params") or {})})
                    except Refused as e:
                        results.append({"ok": False, "error": str(e)})
                        failed += 1
                        if args.get("stop_on_error", True):
                            break
                reply(mid, text({"completed": len(results) - failed, "failed": failed, "results": results}))
            elif name == "sequence_inspect":
                reply(mid, text(fake.inspect()))
            elif name == "render_frame":
                data = fake.frame(float(args.get("seconds") or 0.0), int(args.get("max_side") or 960))
                reply(mid, {"content": [{"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"}]})
            else:
                reply(mid, text(f"unknown tool {name}", True))
        except (Refused, KeyError) as e:
            reply(mid, text(str(e), True))


def main(argv: list[str]) -> int:
    args, opts, k = [], {}, 0
    while k < len(argv):
        if argv[k] in ("--data-dir", "--project"):
            opts[argv[k]] = argv[k + 1]
            k += 2
        else:
            args.append(argv[k])
            k += 1
    fake = Fake()
    if "--project" in opts:
        fake.run("file.open", {"path": opts["--project"]})
    if args[:1] == ["mcp"]:
        serve(fake)
        return 0
    if args[:1] == ["run"]:
        for n, line in enumerate(Path(args[1]).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            step = json.loads(line)
            try:
                r = fake.run(step["id"], step.get("params") or {})
                print(json.dumps({"line": n, "id": step["id"], "ok": True, "result": r}))
            except Refused as e:
                print(json.dumps({"line": n, "id": step["id"], "ok": False, "error": str(e)}))
                return 1
        return 0
    print(f"fake_filmcraft: unknown subcommand {args}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
