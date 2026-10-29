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
file.exportInterchange (a small FCPXML or EDL of V1); CE3's sound — clip.audioGain, the audio fades (an edge), essentialSound.setType /
generateDucking / autoMatch (recorded on the clip), a track's volume, and a WAV mixdown (every audio track at its clips' gain and its
volume, muted tracks left out; fades and ducking recorded, not shaped — the rig measures the real ones). A frame is a flat colour: R = the frame
number, G = how many clips V1 holds, B = 128. The export writes an H.264 MP4 at the sequence's size — each V1 clip a flat colour (its media
item's id × 40), a dissolve blended — and A1's audio clips mixed into one AAC track where they sit.
"""
from __future__ import annotations

import base64
import json
import re
import struct
import sys
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
        if isinstance(ref, str) and re.fullmatch(r"S\d+", ref):              # AU4: a submix by its ref
            subs = s.setdefault("submix_tracks", [])
            if int(ref[1:]) - 1 < len(subs):
                return subs[int(ref[1:]) - 1]
        for t in s["video_tracks"] + s["audio_tracks"] + s.get("submix_tracks", []):
            if t["id"] == ref:
                return t
        raise Refused(f"no track {ref}")

    def shift(self, at: int, d: int, skip: dict | None = None) -> None:
        """U7b: every track's clips (and transitions) from `at` on move by `d` ticks — FilmCraft's ripple on the sync-locked tracks."""
        s = self.sequence()
        for t in s["video_tracks"] + s["audio_tracks"]:
            for x in t["items"]:
                if x is not skip and x["start"] >= at:
                    x["start"] += d
            for x in t["transitions"]:
                if x["start"] >= at - x["duration"]:
                    x["start"] += d

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
            import soundfile as sf                                     # AU4: a print is a float WAV (the stdlib's wave reads PCM only)
            info = sf.info(str(path))
            sr, frames, ch = info.samplerate, info.frames, info.channels
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
                         "enabled": True, "muted": False, "volume_db": 0.0, "pan": 0.0, "effects": []} for k in range(n)]
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
            if it is None or not ({"Media", "AdjustmentLayer"} & set(it["kind"])):
                raise Refused(f"no media item {p['item']}")
            info = it["kind"]["Media"]["info"] if "Media" in it["kind"] else it["kind"]["AdjustmentLayer"]          # CE4: a scene grade
            t = self.track(p.get("track", "V1"))
            start = int(p["time"]) if "time" in p else (int(p["frame"]) * TICK // 24 if "frame" in p else round(float(p["seconds"]) * TICK))
            src = int(p.get("sourceIn", 0))
            dur = int(p.get("duration", info["duration"] - src))
            end = start + dur
            if p.get("insert"):                                        # U7b: an insert opens the gap on every track (all sync-locked, as the real one)
                self.shift(start, dur)
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
            if p.get("format") == "wav":                               # CE3: the cut's mix (AU4: a custom range's end)
                return self.export_wav(Path(p["path"]), float(p["endSeconds"]) if p.get("range") == "custom" and p.get("endSeconds") is not None else None)
            if p.get("format") == "png":                               # a PNG sequence: frame000.png … beside `path`, at `scale`
                return self.export_png(Path(p["path"]), float(p.get("scale", 1.0)))
            out = self.export(Path(p["path"]))
            side = p.get("captionSidecar")                             # CE5: the captions beside the movie (the burn-in and the codec: the real one's)
            tracks = [ct for ct in self.sequence().get("caption_tracks", []) if ct.get("enabled", True) and ct["captions"]]
            if side and tracks:
                def tc(t: int, sep: str) -> str:
                    ms = round(t * 1000 / TICK)
                    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"
                caps = sorted(tracks[0]["captions"], key=lambda c: c["start"])
                sep = "," if side == "srt" else "."
                body = "".join(f"{n}\n{tc(c['start'], sep)} --> {tc(c['start'] + c['duration'], sep)}\n{c['text']}\n\n" for n, c in enumerate(caps, 1))
                Path(p["path"]).with_suffix(f".{side}").write_text(("WEBVTT\n\n" if side == "vtt" else "") + body, encoding="utf-8")
            out["burned"] = bool(p.get("burnCaptions"))
            return out
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

    # ---- CE4: colour, as the real ones answer (the probe on 764723f) -----------------------------------------------------------------
    PRESETS = {"Golden Dusk": {"temperature": 35.0, "saturation": 110.0}, "Steel Blue": {"temperature": -40.0, "saturation": 70.0},
               "Neutral Mono": {"saturation": 0.0}}

    def lumetri(self, clip: int) -> dict:
        _, ti = self.find_clip(clip)
        e = next((x for x in ti.setdefault("effects", []) if x["effect"] == "lumetri"), None)
        if e is None:
            e = {"effect": "lumetri", "enabled": True, "params": {"look_lut": {"value": {"Text": ""}}}}
            ti["effects"].insert(0, e)
        return e

    def colour(self, cid: str, p: dict):
        if cid == "lumetri.presets":
            return {"folders": ["Cinematic", "Monochrome"], "presets": [{"folder": "Monochrome" if n == "Neutral Mono" else "Cinematic", "name": n, "description": n}
                                                                        for n in self.PRESETS]}
        if cid == "lut.list":
            return {"library": [], "builtin": [{"ref": "builtin:look-teal-orange", "name": "Teal & Orange", "input": False},
                                               {"ref": "builtin:look-night", "name": "Night", "input": False},
                                               {"ref": "builtin:slog3-sgamut3-to-rec709", "name": "Sony S-Log3 / S-Gamut3 to Rec. 709", "input": True}]}
        if cid == "lut.import":
            if not Path(p["path"]).is_file() or Path(p["path"]).suffix.lower() not in (".cube", ".3dl"):
                raise Refused(f"lut.import: {p['path']}: expected a .cube or .3dl file")
            lid = f"lut{self.new_id()}"
            return {"id": lid, "ref": f"lib:{lid}", "name": Path(p["path"]).stem}
        if cid == "file.newAdjustmentLayer":
            iid = self.new_id()
            s = self.sequence()
            self.items()[str(iid)] = {"id": iid, "name": "Adjustment Layer", "label": "Lavender", "metadata": {}, "created": iid,
                                      "kind": {"AdjustmentLayer": {"width": s["settings"]["width"], "height": s["settings"]["height"],
                                                                   "rate": s["settings"]["frame_rate"], "duration": round(float(p.get("seconds", 5)) * TICK)}}}
            return {"item": iid}
        if cid == "lumetri.applyPreset":                                    # as the real one: always another instance, after the Lumetri there
            if p["name"] not in self.PRESETS:
                raise Refused(f"lumetri.applyPreset: no preset `{p['name']}`")
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                e = {"effect": "lumetri", "enabled": True, "params": {"look_lut": {"value": {"Text": ""}}}}
                for k, v in self.PRESETS[p["name"]].items():
                    e["params"][k] = {"value": {"Float": v}}
                fx = ti.setdefault("effects", [])
                fx.insert(max([i + 1 for i, x in enumerate(fx) if x["effect"] == "lumetri"], default=0), e)
            return {"clips": len(p.get("clips") or []), "preset": p["name"]}
        if cid == "effects.apply":
            for c in p.get("clips") or []:
                if p["effect"] != "lumetri":
                    raise Refused(f"effects.apply: the fake knows lumetri only, not {p['effect']}")
                self.lumetri(int(c))
            return None
        if cid == "effects.setParam":
            _, ti = self.find_clip(int(p["clip"]))
            e = next((x for x in ti.get("effects") or [] if x["effect"] == p.get("effect")), None)
            if e is None:
                raise Refused("effects.setParam: no such effect on clip")
            e["params"][p["param"]] = {"value": {"Float": float(p["value"])}}
            return None
        if cid == "effects.remove":
            _, ti = self.find_clip(int(p["clip"]))
            fx = ti.get("effects") or []
            if not 0 <= int(p["index"]) < len(fx):
                raise Refused("effects.remove: no effect at that index")
            fx.pop(int(p["index"]))
            return None
        if cid == "lumetri.setLook":
            self.lumetri(int(p["clip"]))["params"]["look_lut"] = {"value": {"Text": p.get("lut") or ""}}
            return {"clip": int(p["clip"]), "lut": p.get("lut") or ""}
        if cid == "lumetri.applyMatch":
            e = self.lumetri(int(p["clip"]))
            e["params"]["wheel_midtones"] = {"value": {"Vec2": {"x": 0.3, "y": 0.1}}}
            return {"clip": int(p["clip"]), "distanceBefore": 0.6, "distanceAfter": 0.2}
        return NotImplemented

    # ---- CE5: captions and the author's markers, as the real ones (the probe on 764723f) --------------------------------------------
    def caption_track(self, ref) -> dict:
        tracks = self.sequence().setdefault("caption_tracks", [])
        for k, ct in enumerate(tracks):
            if ref in (ct["id"], f"C{k + 1}"):
                return ct
        if ref is None and tracks:
            return tracks[0]
        raise Refused(f"no caption track {ref}")

    def find_caption(self, cid: int) -> tuple[dict, dict]:
        for ct in self.sequence().get("caption_tracks", []):
            for c in ct["captions"]:
                if c["id"] == cid:
                    return ct, c
        raise Refused(f"no caption {cid}")

    def captions(self, cid: str, p: dict):
        if not (cid.startswith("captions.") or cid in ("markers.add", "markers.edit")):
            return NotImplemented
        s = self.sequence()
        if cid == "captions.newTrack":
            tid = self.new_id()
            s.setdefault("caption_tracks", []).append({"id": tid, "name": p.get("name", "Subtitle"), "format": p.get("format", "Subtitle"),
                                                       "language": p.get("language", "en"), "enabled": True, "locked": False,
                                                       "style": {"size": 32.0, "background": True, "anchor": "Bottom"}, "captions": []})
            return {"track": tid}
        if cid == "captions.deleteTrack":
            tid = self.caption_track(p["track"])["id"]
            s["caption_tracks"] = [x for x in s["caption_tracks"] if x["id"] != tid]
            return None
        if cid == "captions.add":
            if not s.get("caption_tracks"):
                self.captions("captions.newTrack", {})
            ct = self.caption_track(p.get("track"))
            start = int(p["time"]) if "time" in p else round(float(p.get("seconds", 0.0)) * TICK)
            c = {"id": self.new_id(), "start": start, "duration": round(float(p.get("durationSeconds", 3.0)) * TICK), "text": p.get("text", ""),
                 "speaker": None, "cue_id": None, "settings": ""}
            ct["captions"].append(c)
            return {"caption": c["id"]}
        if cid == "captions.setText":
            _, c = self.find_caption(int(p["caption"]))
            if "text" in p:
                c["text"] = p["text"]
            if "speaker" in p:
                c["speaker"] = p["speaker"]
            return None
        if cid == "captions.setTimes":
            _, c = self.find_caption(int(p["caption"]))
            a = round(float(p["startSeconds"]) * TICK) if "startSeconds" in p else c["start"]
            b = round(float(p["endSeconds"]) * TICK) if "endSeconds" in p else c["start"] + c["duration"]
            c["start"], c["duration"] = a, max(1, b - a)
            return None
        if cid == "captions.move":
            for k in p.get("captions") or []:
                _, c = self.find_caption(int(k))
                c["start"] = max(0, c["start"] + self.delta(p))
            return None
        if cid == "captions.trim":
            _, c = self.find_caption(int(p["caption"]))
            d = self.delta(p)
            if p["edge"] == "in":
                c["start"], c["duration"] = c["start"] + d, max(1, c["duration"] - d)
            else:
                c["duration"] = max(1, c["duration"] + d)
            return None
        if cid == "captions.delete":
            gone = set(p.get("captions") or [])
            for ct in s.get("caption_tracks", []):
                ct["captions"] = [c for c in ct["captions"] if c["id"] not in gone]
            return None
        if cid == "captions.setStyle":
            st = self.caption_track(p["track"])["style"]
            for k in ("size", "background", "font", "outline"):
                if k in p:
                    st[k] = p[k]
            if "anchor" in p:
                st["anchor"] = str(p["anchor"]).capitalize()
            return None
        if cid == "captions.setTrack":
            ct = self.caption_track(p["track"])
            for k in ("name", "enabled", "locked"):
                if k in p:
                    ct[k] = p[k]
            return None
        if cid == "markers.add":
            mid = self.new_id()
            s["markers"].append({"id": mid, "start": int(p.get("time", 0)), "duration": 0, "name": p.get("name", ""), "comment": p.get("comment", ""),
                                 "kind": "Comment", "color": p.get("color", "Green")})
            return {"marker": mid}
        if cid == "markers.edit":
            m = next((x for x in s["markers"] if x["id"] == int(p["marker"])), None)
            if m is None:
                raise Refused("markers.edit: no such marker")
            for k in ("name", "comment", "color"):
                if k in p:
                    m[k] = p[k]
            return None
        return NotImplemented

    def editor(self, cid: str, p: dict):
        c = self.colour(cid, p)
        if c is not NotImplemented:
            return c
        c = self.captions(cid, p)
        if c is not NotImplemented:
            return c
        # D127: a track's strip — the fader and pan (FilmCraft's clamps), its inserts (Amplify −96…+24 dB, Stereo Width 0–200 %), at most 5
        if cid == "mixer.addSubmix":                                        # AU4: the muted bus of the printed sources
            subs = self.sequence().setdefault("submix_tracks", [])
            sid = self.new_id()
            subs.append({"id": sid, "kind": "Audio", "name": p.get("name") or f"Submix {len(subs) + 1}", "items": [], "transitions": [], "muted": False,
                         "volume_db": 0.0, "pan": 0.0, "effects": [], "mixer": {"output": None}})
            return {"id": sid, "ref": f"S{len(subs)}"}
        if cid == "mixer.deleteSubmix":
            sid = self.track(p["strip"])["id"]
            s = self.sequence()
            s["submix_tracks"] = [x for x in s.get("submix_tracks", []) if x["id"] != sid]
            return None
        if cid == "sequence.deleteTrack":
            tid = self.track(p["track"])["id"]
            s = self.sequence()
            s["video_tracks"] = [x for x in s["video_tracks"] if x["id"] != tid]
            s["audio_tracks"] = [x for x in s["audio_tracks"] if x["id"] != tid]
            return None
        if cid == "mixer.setStrip":
            t = self.track(p["strip"])
            if "muted" in p:
                t["muted"] = bool(p["muted"])
            if "output" in p:
                out = p["output"]
                t.setdefault("mixer", {})["output"] = None if out in (None, "Mix", "mix") else self.track(out)["id"]
            if "volumeDb" in p:
                t["volume_db"] = min(15.0, max(-96.0, float(p["volumeDb"])))
            if "pan" in p:
                t["pan"] = min(100.0, max(-100.0, float(p["pan"])))
            if "name" in p:
                t["name"] = p["name"]
            return {"ref": p["strip"], "volumeDb": t.get("volume_db", 0.0), "pan": t.get("pan", 0.0)}
        if cid == "mixer.addInsert":
            t = self.track(p["strip"])
            fx = t.setdefault("effects", [])
            if p["effect"] not in ("amplify", "stereo_width", "parametric_eq"):
                raise Refused(f"mixer.addInsert: `{p['effect']}` is not an audio effect")
            if len(fx) >= 5:
                raise Refused("mixer.addInsert: all 5 effect slots are in use")
            at = min(int(p.get("slot", len(fx))), len(fx))
            e = {"effect": p["effect"], "enabled": True, "params": {"gain" if p["effect"] == "amplify" else "width": {"value": {"Float": 0.0 if p["effect"] == "amplify" else 100.0}}}}
            if p.get("postFader"):
                e["post_fader"] = True
            fx.insert(at, e)
            return {"slot": at}
        if cid == "mixer.removeInsert":
            fx = self.track(p["strip"]).get("effects") or []
            if not 0 <= int(p["slot"]) < len(fx):
                raise Refused("mixer.removeInsert: no effect in that slot")
            fx.pop(int(p["slot"]))
            return None
        if cid == "mixer.setInsert":
            fx = self.track(p["strip"]).get("effects") or []
            if not 0 <= int(p["slot"]) < len(fx):
                raise Refused("mixer.setInsert: no effect in that slot")
            e = fx[int(p["slot"])]
            for k, v in (p.get("params") or {}).items():
                lo, hi = (-96.0, 24.0) if k == "gain" else (0.0, 200.0)
                e["params"][k] = {"value": {"Float": min(hi, max(lo, float(v)))}}
            return None
        if cid == "timeline.setTrack":
            t = self.track(p["track"])
            for k, v in (("name", "name"), ("locked", "locked"), ("muted", "muted"), ("enabled", "enabled"), ("volume_db", "volumeDb")):
                if v in p:
                    t[k] = p[v]
            return None
        if cid == "clip.audioGain":
            out = []
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["gain_db"] = float(p.get("db", 0.0)) + (ti.get("gain_db", 0.0) if p.get("mode") == "adjust" else 0.0)
                out.append({"clip": ti["id"], "gainDb": ti["gain_db"]})
            return {"clips": len(out), "gainDb": out}
        if cid == "sequence.applyAudioTransition":
            t, ti = self.find_clip(int(p["clip"]))
            dur = int(p.get("frames", 12)) * TICK // self.fps()
            out_edge = p.get("edge") == "out"
            xid = self.new_id()
            t["transitions"].append({"id": xid, "effect": {"effect": p.get("effect") or "constant_power", "enabled": True, "params": {}},
                                     "start": ti["start"] + ti["duration"] - dur if out_edge else ti["start"], "duration": dur,
                                     "from": ti["id"] if out_edge else None, "to": None if out_edge else ti["id"], "align": "Start"})
            return {"transition": xid}
        if cid == "essentialSound.setType":
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["essential"] = {"kind": str(p.get("type", "")).capitalize()}
            return {"clips": len(p.get("clips") or []), "type": str(p.get("type", "")).capitalize()}
        if cid == "essentialSound.generateDucking":
            out = []
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["effects"] = [e for e in ti.get("effects", []) if e.get("effect") != "volume"] + [   # FilmCraft keys the clip's volume down
                    {"effect": "volume", "enabled": True, "params": {"level": {"value": {"Float": 0.0}, "keyframes": [{"time": 0, "value": {"Float": -15.0}}]}}}]
                out.append({"clip": ti["id"], "keyframes": [{"levelDb": -15.0}]})
            return {"clips": out}
        if cid == "essentialSound.autoMatch":
            out = []
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                ti["gain_db"] = float(p.get("target", -23.0)) + 13.0             # a stand-in: a tone measured at −13 LUFS
                out.append({"clip": ti["id"], "gainDb": ti["gain_db"], "targetLufs": p.get("target", -23.0)})
            return {"clips": out}
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
                if p.get("mode") == "ripple":                           # U7b: every track's later clips follow (the real one: all sync-locked)
                    self.shift(old_end, d, skip=ti)
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
                a, b = ti["start"], ti["start"] + ti["duration"]
                for o in self.sequence()["video_tracks"] + self.sequence()["audio_tracks"]:     # U7b: as the real one, a clip in the way refuses
                    if o is not t and any(x["start"] < b and x["start"] + x["duration"] > a for x in o["items"]):
                        raise Refused(f"this edit would break sync: {o.get('name', o['id'])} is sync-locked and has a clip in the way")
                t["items"].remove(ti)
                t["transitions"] = [x for x in t["transitions"] if ti["id"] not in (x.get("from"), x.get("to"))]
                self.shift(b, -ti["duration"])                         # the later clips move up by one amount on every track
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
                                   "enabled": True, "muted": False, "volume_db": 0.0, "pan": 0.0, "effects": []})
                    made[kind].append(tid)
            return made
        if cid == "edit.pasteAttributes":
            want = p.get("effects")                                     # RC2f: as the real one — a list names the effects pasted, appended to the clip's
            for c in p.get("clips") or []:
                _, ti = self.find_clip(int(c))
                if isinstance(want, list):
                    ti["effects"] = [*ti.get("effects", []), *[dict(e) for e in (self.clipboard or []) if e.get("effect") in want]]
                else:
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

    def mixdown(self, sr: int = 48000, end_s: float | None = None):
        """Stereo, every audio track through its strip in FilmCraft's order: clip gain → pre-fader inserts → fader → post-fader inserts →
        pan (balance). The Stereo Width law is D127's patched one (past 100 % the Mid is lowered up to 3 dB)."""
        import numpy as np
        import soundfile as sf
        s = self.sequence()
        end = max([ti["start"] + ti["duration"] for t in s["video_tracks"] + s["audio_tracks"] for ti in t["items"]] or [0])
        audio = np.zeros((int(round(end / TICK * sr)) + 1 if end_s is None else int(round(end_s * sr)), 2), dtype=np.float32)
        muted_bus = {x["id"] for x in s.get("submix_tracks", []) if x.get("muted")}

        def insert(buf, e):
            v = e["params"].get("gain" if e["effect"] == "amplify" else "width", {}).get("value", {}).get("Float")
            if e["effect"] == "amplify":
                return buf * 10 ** (float(v or 0.0) / 20)
            w = float(100.0 if v is None else v) / 100
            m, side = (buf[:, 0] + buf[:, 1]) / 2, (buf[:, 0] - buf[:, 1]) / 2 * w
            m = m * (10 ** (-3 * (w - 1) / 20) if w > 1 else 1.0)
            return np.stack([m + side, m - side], axis=1)
        for t in s["audio_tracks"]:
            if t.get("muted") or (t.get("mixer") or {}).get("output") in muted_bus:
                continue
            buf = np.zeros_like(audio)
            for ti in t["items"]:
                src = self.items()[str(ti["item"])]["kind"]["Media"]["media"]["File"]["path"]
                data, rate = sf.read(src, dtype="float32", always_2d=True)
                data = data[:, :2] if data.shape[1] >= 2 else np.repeat(data, 2, axis=1)
                if rate != sr:
                    x = np.linspace(0, len(data) - 1, int(len(data) * sr / rate))
                    data = np.stack([np.interp(x, np.arange(len(data)), data[:, c]) for c in (0, 1)], axis=1).astype(np.float32)
                data = data * 10 ** (ti.get("gain_db", 0.0) / 20)
                at = int(round(ti["start"] / TICK * sr))
                seg = data[: max(0, min(len(data), len(buf) - at, int(ti["duration"] / TICK * sr)))]
                buf[at:at + len(seg)] += seg
            fx = [e for e in t.get("effects") or [] if e.get("enabled", True)]
            for e in (e for e in fx if not e.get("post_fader")):
                buf = insert(buf, e)
            fader = t.get("volume_db", 0.0)
            buf = buf * (0.0 if fader <= -96 else 10 ** (fader / 20))
            for e in (e for e in fx if e.get("post_fader")):
                buf = insert(buf, e)
            pan = t.get("pan", 0.0) / 100                                  # balance: centre unity, the far side constant power
            if pan > 0:
                buf[:, 0] *= np.cos(pan * np.pi / 2)
            elif pan < 0:
                buf[:, 1] *= np.cos(-pan * np.pi / 2)
            audio += buf
        return audio, sr

    def export_wav(self, out: Path, end_s: float | None = None) -> dict:
        import soundfile as sf
        audio, sr = self.mixdown(end_s=end_s)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), audio, sr, subtype="PCM_16")
        return {"path": str(out), "result": {"frames": len(audio)}}

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
