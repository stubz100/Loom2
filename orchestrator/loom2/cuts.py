"""CE1 (proto01_animate 30 §10, D126 #2): a cut's file is a FilmCraft project, `timelines/<id>/cut.fcproj`, written by FilmCraft.

Reading needs no FilmCraft: the project is JSON (`filmcraft.project`, schema 13), and `lane()` turns its first video track into the lane
loom2 has always shown, assembled, marked *changed*, checked and exported — the clips by their source frames and the dissolves as overlaps.
loom2's links ride in the project as item metadata (`loom2.clip`, `loom2.fps`, `loom2.media`, `loom2.shot`, `loom2.version`,
`loom2.node` on a take; `loom2.asset`, `loom2.node`, `loom2.line` on a spoken line; `loom2.route` on the sequence). A take is one project
item per use with its stamps — the same clip on the lane as a shot and as a plain clip is two items of one file, so an item's links are
always true.

Writing goes through the FilmCraft session (`Cuts.write`): V1 and the spoken lines on A1 are rebuilt from a lane by commands — the clips
end to end, each cut in its dissolve's middle and the rest its handle under the transition (as FC1's FCPXML); a take at the cut's rate
enters as its PNG master, any other as its proxy (FilmCraft repeats frames for a 16 fps take; the queued movie job conforms it with RIFE,
D27, never an edit — RIFE takes the card, D97). A spoken line sits on A1 where the exports lay it, or where the line before it ends when it
would overlap it (a track holds one clip at a time; CE3 lets the author move them). Tracks other than V1 and A1's lines are left alone.

CE2 (30 §12): the cut's every track is read as it is (`tracks()`), and the Episode's editor changes it by FilmCraft's own commands
(`Cuts.edit`, a whitelist), places a Catalogue clip, picture or sound (`Cuts.place`), swaps a take in place (`Cuts.replace`), draws a
frame (`Cuts.frame`) and exports FilmCraft's FCPXML / EDL (`Cuts.interchange`). Then V1 may hold gaps, speed, holds, other transitions and
things that are not takes: `lane()` stays the takes in order with their links for the Flow's verbs; the exports and renders read the project.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .clips import ClipRecord, ClipStore
from .filmcraft import TICK, TIMEBASES, FilmCraft, prefs, ticks
from .fsio import atomic_copy
from .timelines import Timeline, TimelineClip, duration, line_spans, starts
from .timelines import ticks as lane_ticks
from .workspace import Workspace

CUT_FILE = "cut.fcproj"
FORMAT = "filmcraft.project"
UNDO_DEPTH = 50                                    # the cut's undo: snapshots of its project in `history/undo/` (FilmCraft's own undo dies with its session)


class CutError(ValueError):
    """A cut's project cannot be read or written as asked (the API answers 422)."""


def read(path: Path) -> dict:
    """The project's JSON (FilmCraft's envelope), refusing anything else."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CutError(f"the cut's project {path} cannot be read: {e}") from e
    if doc.get("format") != FORMAT:
        raise CutError(f"{path} is not a FilmCraft project")
    return doc


def items(doc: dict) -> dict[str, dict]:
    return doc["project"]["items"]


def sequence(doc: dict) -> tuple[int, dict, dict]:
    """The cut's sequence: (item id, the item, its Sequence body). A cut's project holds one."""
    for k, it in items(doc).items():
        if isinstance(it.get("kind"), dict) and "Sequence" in it["kind"]:
            return int(k), it, it["kind"]["Sequence"]
    raise CutError("the cut's project holds no sequence")


def _frames(t: int, fps: int) -> int:
    return round(t * fps / TICK)


def lane(doc: dict, fps: int) -> tuple[list[TimelineClip], list[int], dict | None]:
    """V1 as the lane: clips (their FilmCraft track item ids, loom2 clip, source frames in the clip's own rate, the shot's stamps),
    overlaps (a cross dissolve into a clip, in ticks of the lane) and the route the cut was assembled from. CE2: what is not a take is left
    out and a gap closes up — the lane is then the takes in order with their links (the Flow's verbs); timing reads `tracks()`."""
    its = items(doc)
    _, seq_item, seq = sequence(doc)
    v1 = seq["video_tracks"][0] if seq["video_tracks"] else {"items": [], "transitions": []}
    tis = sorted((ti for ti in v1["items"] if "loom2.clip" in its.get(str(ti["item"]), {}).get("metadata", {})), key=lambda ti: ti["start"])
    into = {tr["to"]: tr for tr in v1.get("transitions", []) if tr.get("to") is not None and tr.get("from") is not None
            and _effect(tr) == "cross_dissolve"}
    clips: list[TimelineClip] = []
    overlaps: list[int] = []
    for i, ti in enumerate(tis):
        meta = its[str(ti["item"])]["metadata"]
        clip_fps = int(meta.get("loom2.fps") or fps)
        cut = _frames(ti["start"], fps)
        tr = into.get(ti["id"])
        s_i = _frames(tr["start"], fps) if tr else cut                       # the lane's start: where the dissolve into it begins
        nxt = into.get(tis[i + 1]["id"]) if i + 1 < len(tis) else None
        end = _frames(nxt["start"] + nxt["duration"], fps) if nxt else _frames(ti["start"] + ti["duration"], fps)
        speed = abs(float(ti.get("speed") or 1.0))
        in_ = round((ti["source_in"] / TICK - (cut - s_i) / fps) * clip_fps)
        length = round((end - s_i) * clip_fps / fps * speed)
        clips.append(TimelineClip(id=str(ti["id"]), clip_id=meta["loom2.clip"], **{"in": max(0, in_)}, out=max(0, in_) + max(1, length),
                                  fps=clip_fps if clip_fps != fps else None, shot_id=meta.get("loom2.shot") or None,
                                  shot_version=meta.get("loom2.version") or None, node_id=meta.get("loom2.node") or None))
        overlaps.append(_frames(tr["duration"], fps) if tr and i > 0 else 0)
    route = seq_item.get("metadata", {}).get("loom2.route")
    return clips, overlaps, (json.loads(route) if route else None)


def lines(doc: dict) -> list[dict]:
    """The spoken lines on the cut's audio tracks (A1, or wherever the author moved them, CE3): {track item, start tick, node, line, asset}."""
    its = items(doc)
    _, _, seq = sequence(doc)
    out = []
    for tr in seq["audio_tracks"]:
        for ti in tr["items"]:
            meta = its.get(str(ti["item"]), {}).get("metadata", {})
            if "loom2.line" in meta:
                out.append({"clip": ti["id"], "start": ti["start"], "node": meta.get("loom2.node"), "line": int(meta["loom2.line"]), "asset": meta.get("loom2.asset")})
    return out


def placed_lines(doc: dict) -> set[str]:
    """CE3: the lines the cut has placed (`node:line` in its sequence's `loom2.lines`) — a placed line missing now was lifted by the author."""
    _, seq_item, _ = sequence(doc)
    raw = seq_item.get("metadata", {}).get("loom2.lines") or "[]"
    try:
        return set(json.loads(raw))
    except json.JSONDecodeError:
        return set()


def _effect(tr: dict) -> str:
    e = tr.get("effect")
    return e.get("effect", "") if isinstance(e, dict) else str(e or "")


class CutItem(BaseModel):
    """One clip on a track, as the editor shows it (frames at the cut's rate; the source in seconds)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    item: int                                       # the project item it plays
    name: str = ""
    kind: Literal["take", "line", "video", "picture", "sound", "adjustment", "other"] = "other"
    start: float
    duration: float
    source_in: float = 0.0
    speed: float = 1.0
    reverse: bool = False
    enabled: bool = True
    hold: bool = False
    gain_db: float = 0.0                            # CE3: the clip's gain
    sound: str | None = None                        # CE3: its sound type for FilmCraft's ducking (Dialogue, Music, Sfx, Ambience)
    ducked: bool = False                            # CE3: its volume keyed (FilmCraft's ducking under the dialogue)
    media_path: str | None = None
    clip_id: str | None = None                      # loom2's links: a take's clip and shot, a line's node and index, an asset
    asset_id: str | None = None
    shot_id: str | None = None
    shot_version: str | None = None
    node_id: str | None = None
    line: int | None = None


class CutTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, json_schema_serialization_defaults_required=True)
    id: int
    effect: str
    start: float
    duration: float
    from_: int | None = Field(None, alias="from")
    to: int | None = None


class CutTrack(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    kind: Literal["video", "audio"]
    name: str
    locked: bool = False
    muted: bool = False
    enabled: bool = True
    volume_db: float = 0.0                          # CE3: the track's volume
    items: list[CutItem] = Field(default_factory=list)
    transitions: list[CutTransition] = Field(default_factory=list)


class CutTracks(BaseModel):
    """CE2: a FilmCraft cut's every track, read from its project."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    sequence: int
    fps: int
    w: int
    h: int
    duration: float
    video: list[CutTrack] = Field(default_factory=list)
    audio: list[CutTrack] = Field(default_factory=list)
    undo: int = 0                                   # the cut's changes it can undo / redo (its project's snapshots)
    redo: int = 0


def _kind(it: dict) -> str:
    meta = it.get("metadata", {})
    if "loom2.clip" in meta:
        return "take"
    if "loom2.line" in meta:
        return "line"
    kind = it.get("kind", {}) if isinstance(it.get("kind"), dict) else {}
    if "AdjustmentLayer" in kind:
        return "adjustment"
    k = str(kind.get("Media", {}).get("info", {}).get("kind", ""))
    if k == "AudioOnly":
        return "sound"
    if k == "Movie" or "Sequence" in k:
        return "video"
    if "Image" in k or "Still" in k:
        return "picture"
    return "other"


def tracks(doc: dict) -> CutTracks:
    """Every track of the cut's sequence with its clips and transitions, loom2's links on each clip."""
    its = items(doc)
    sid, _, seq = sequence(doc)
    st = seq["settings"]
    fps = int(round(st["frame_rate"]["num"] / max(1, st["frame_rate"].get("den", 1))))

    def f(t: int) -> float:
        return round(t * fps / TICK, 3)

    def one(t: dict, kind: str) -> CutTrack:
        out = []
        for ti in sorted(t.get("items", []), key=lambda x: x["start"]):
            it = its.get(str(ti["item"]), {})
            meta = it.get("metadata", {})
            media = it.get("kind", {}).get("Media", {}).get("media", {}) if isinstance(it.get("kind"), dict) else {}
            out.append(CutItem(id=ti["id"], item=ti["item"], name=ti.get("name") or it.get("name", ""), kind=_kind(it), start=f(ti["start"]),  # type: ignore[arg-type]
                               duration=f(ti["duration"]), source_in=round(ti.get("source_in", 0) / TICK, 4), speed=float(ti.get("speed") or 1.0),
                               reverse=bool(ti.get("reverse")), enabled=ti.get("enabled", True) is not False, hold=ti.get("frame_hold") is not None,
                               gain_db=round(float(ti.get("gain_db") or 0.0), 2), sound=(ti.get("essential") or {}).get("kind") or None,
                               ducked=any(e.get("effect") == "volume" and (e.get("params", {}).get("level") or {}).get("keyframes") for e in ti.get("effects") or []),
                               media_path=(media.get("File") or {}).get("path"), clip_id=meta.get("loom2.clip") or None,
                               asset_id=meta.get("loom2.asset") or None, shot_id=meta.get("loom2.shot") or None,
                               shot_version=meta.get("loom2.version") or None, node_id=meta.get("loom2.node") or None,
                               line=int(meta["loom2.line"]) if meta.get("loom2.line") not in (None, "") else None))
        trans = [CutTransition(id=x["id"], effect=_effect(x), start=f(x["start"]), duration=f(x["duration"]), **{"from": x.get("from")}, to=x.get("to"))
                 for x in t.get("transitions", [])]
        return CutTrack(id=t["id"], kind=kind, name=t.get("name", ""), locked=bool(t.get("locked")), muted=bool(t.get("muted")),  # type: ignore[arg-type]
                        enabled=t.get("enabled", True) is not False, volume_db=round(float(t.get("volume_db") or 0.0), 2), items=out, transitions=trans)
    video = [one(t, "video") for t in seq.get("video_tracks", [])]
    audio = [one(t, "audio") for t in seq.get("audio_tracks", [])]
    end = max([i.start + i.duration for tr in video + audio for i in tr.items] or [0.0])
    return CutTracks(sequence=sid, fps=fps, w=int(st["width"]), h=int(st["height"]), duration=round(end, 3), video=video, audio=audio)


# CE2: the FilmCraft commands the Episode's editor may run on a cut (never a file command: the cut's own file is FilmCraft's to write)
EDIT_COMMANDS = frozenset({
    "timeline.move", "timeline.trim", "timeline.roll", "timeline.slip", "timeline.slide", "timeline.razor", "timeline.rateStretch",
    "timeline.setTrack", "timeline.select", "edit.rippleDelete", "edit.clear", "sequence.applyVideoTransition",
    "sequence.applyAudioTransition", "sequence.setTransition", "sequence.closeGap", "sequence.addTracks", "sequence.deleteTrack",
    "clip.speedDuration", "clip.frameHold", "clip.insertFrameHoldSegment", "clip.enable", "clip.rename",
    # CE3: sound — a clip's gain, the dialogue / music types FilmCraft ducks by, the ducking itself, the dialogue's loudness, volume keys
    "clip.audioGain", "essentialSound.setType", "essentialSound.generateDucking", "essentialSound.autoMatch", "clipMixer.set",
})
REMOVE_TRANSITION = "loom2.removeTransition"      # FilmCraft has no command for it (764723f): the clip lifted and placed again, its attributes kept


class Cuts:
    """Writes cuts through the FilmCraft session. `audio_of(clip)` gives a lane clip's spoken lines as story_lookup does (each with the
    file's `path`, its `asset`, `node` and `line`), or None when the cut carries no lines; `name_of(clip)` a take's chapter name (its
    node's title or its shot's name) — loom2 keeps the sequence's chapter markers on V1's named takes after every change (`_markers`)."""

    def __init__(self, ws: Workspace, fc: FilmCraft, audio_of: Callable[[TimelineClip], list[dict | None]] | None = None,
                 name_of: Callable[[TimelineClip], str | None] | None = None) -> None:
        self.ws, self.fc, self.audio_of, self.name_of = ws, fc, audio_of, name_of

    def available(self) -> bool:
        return self.fc.available()

    def path(self, tl_id: str) -> Path:
        return self.ws.timelines_dir / tl_id / CUT_FILE

    def forget(self, tl_id: str) -> None:
        """The session closes the cut's project (it is being deleted)."""
        self.fc.close(self.path(tl_id))

    def create(self, tl: Timeline) -> Path:
        """A new cut's project, empty, at the cut's format."""
        p = self.path(tl.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.fc.new(p, tl.name, tl.w, tl.h, tl.fps)
        return p

    def write(self, tl: Timeline, clips: dict[str, ClipRecord]) -> None:
        """Rebuild V1 and A1's lines from `tl`'s lane (making the project first when the cut has none), set the route, save."""
        p = self.path(tl.id)
        if not p.is_file():
            self.create(tl)
        else:
            self._snapshot(p)
        self.fc.open(p)
        doc = read(p)
        seq_id, _, seq = sequence(doc)
        old = [ti["id"] for ti in (seq["video_tracks"][0]["items"] if seq["video_tracks"] else [])] + [x["clip"] for x in lines(doc)]
        if old:
            self.fc.batch([{"id": "edit.clear", "params": {"clips": old}}])
        media = self._media(doc, tl, clips)
        s = starts(tl)
        n = len(tl.clips)
        cuts = [s[i] + (tl.overlaps[i] // 2 if i > 0 else 0) for i in range(n)]
        cuts.append(duration(tl))
        steps: list[dict] = []
        for i, c in enumerate(tl.clips):
            rec = clips[c.clip_id]
            src = c.in_ / rec.fps + (cuts[i] - s[i]) / tl.fps                           # the source's seconds at the cut
            steps.append({"id": "timeline.place", "params": {"item": media[_use(c)], "track": "V1", "time": ticks(cuts[i], tl.fps), "insert": False,
                                                             "sourceIn": round(src * TICK), "duration": ticks(cuts[i + 1] - cuts[i], tl.fps), "audio": False}})
        placed = [r["clips"][0] for r in self.fc.batch(steps)] if steps else []
        trans = [{"id": "sequence.applyVideoTransition", "params": {"clip": placed[i], "effect": "cross_dissolve", "frames": tl.overlaps[i], "edge": "in"}}
                 for i in range(1, n) if tl.overlaps[i] > 0]
        route = [{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.route": json.dumps(tl.route) if tl.route is not None else ""}}}]
        line_steps, placed = self._line_steps(doc, tl, s)
        registry = [{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.lines": json.dumps(sorted(placed))}}}]
        self.fc.batch(trans + route + registry + line_steps)
        used = set(media.values()) | {st["params"]["item"] for st in line_steps}
        unused = [int(k) for k, it in items(doc).items() if ({"loom2.clip", "loom2.line"} & set(it.get("metadata", {}))) and int(k) not in used]
        if unused:                                                  # loom2's own items no use holds any more (never anything else in the project)
            self.fc.batch([{"id": "project.delete", "params": {"items": unused}}])
        self._markers(p)

    # ---- CE2: the editor's verbs on a FilmCraft cut -------------------------------------------------
    def _open(self, tl: Timeline, change: bool = True) -> Path:
        """The cut's project held by the session; before a change, a snapshot for the cut's undo."""
        p = self.path(tl.id)
        if not tl.file or not p.is_file():
            raise CutError("this cut is not a FilmCraft project yet (it becomes one on its first change)")
        if change:
            self._snapshot(p)
        self.fc.open(p)
        return p

    # ---- the cut's undo: its project's snapshots (a change of any size is one step; it survives FilmCraft's session) -------------
    def _stack(self, p: Path, which: str) -> list[Path]:
        return sorted((p.parent / "history" / which).glob("*.fcproj"))

    def _push(self, p: Path, which: str) -> None:
        d = p.parent / "history" / which
        d.mkdir(parents=True, exist_ok=True)
        have = self._stack(p, which)
        n = int(have[-1].stem) + 1 if have else 1
        atomic_copy(p, d / f"{n:06d}.fcproj")
        for old in self._stack(p, which)[:-UNDO_DEPTH]:
            old.unlink()

    def _snapshot(self, p: Path) -> None:
        self._push(p, "undo")
        for x in self._stack(p, "redo"):
            x.unlink()

    def _rollback(self, p: Path) -> None:
        """A change FilmCraft refused part-way: the project as it was before it, the snapshot taken for it dropped."""
        have = self._stack(p, "undo")
        if have:
            atomic_copy(have[-1], p)
            have[-1].unlink()
        self.fc.open(p, reload=True)

    def changing(self, tl: Timeline, fn: Callable[[Path], Any]) -> Any:
        """Run a change on the cut's project (snapshotted first); FilmCraft's refusal rolls it back."""
        p = self._open(tl)
        try:
            return fn(p)
        except Exception:
            self._rollback(p)
            raise

    def undoable(self, tl: Timeline) -> tuple[int, int]:
        """How many changes the cut can undo and redo."""
        p = self.path(tl.id)
        return len(self._stack(p, "undo")), len(self._stack(p, "redo"))

    def undo(self, tl: Timeline, redo: bool = False) -> dict:
        """The cut's project as it was before its last change (`redo`: after the change undone last); the session reopens it."""
        p = self.path(tl.id)
        src, dst = ("redo", "undo") if redo else ("undo", "redo")
        have = self._stack(p, src)
        if not have:
            raise CutError(f"nothing to {'redo' if redo else 'undo'}")
        self._push(p, dst)
        atomic_copy(have[-1], p)
        have[-1].unlink()
        self.fc.open(p, reload=True)
        return {"undo": len(self._stack(p, "undo")), "redo": len(self._stack(p, "redo"))}

    def edit(self, tl: Timeline, steps: list[dict]) -> list[Any]:
        """Run the editor's steps — FilmCraft commands from EDIT_COMMANDS, or loom2's removal of a transition — and save."""
        for st in steps:
            if st.get("id") not in EDIT_COMMANDS and st.get("id") != REMOVE_TRANSITION:
                raise CutError(f"`{st.get('id')}` is not an editor command")
        def run(p: Path) -> list[Any]:
            results: list[Any] = []
            for st in steps:
                if st["id"] == REMOVE_TRANSITION:
                    self.fc.save()                                    # the removal reads the project as it stands
                    results.append(self._remove_transition(read(p), int(st.get("params", {}).get("transition", 0))))
                else:
                    results.extend(self.fc.batch([{"id": st["id"], "params": st.get("params") or {}}]))
            self._markers(p)
            return results
        return self.changing(tl, run)

    def _remove_transition(self, doc: dict, tid: int) -> dict:
        """FilmCraft (764723f) has no command to delete a transition: the clip it leads into is lifted (the orphan goes with it) and
        placed back where it was, with its attributes (motion, opacity, effects) copied over and its speed set again."""
        _, _, seq = sequence(doc)
        for t in seq["video_tracks"] + seq["audio_tracks"]:
            tr = next((x for x in t.get("transitions", []) if x["id"] == tid), None)
            if tr is None:
                continue
            cid = tr.get("to") if tr.get("to") is not None else tr.get("from")
            ti = next(x for x in t["items"] if x["id"] == cid)
            self.fc.batch([{"id": "timeline.select", "params": {"clips": [cid]}}, {"id": "edit.copy", "params": {}}, {"id": "edit.clear", "params": {"clips": [cid]}}])
            new = self.fc.batch([{"id": "timeline.place", "params": {"item": ti["item"], "track": t["id"], "time": ti["start"], "insert": False,
                                                                     "sourceIn": ti["source_in"], "duration": ti["duration"],
                                                                     **({"audio": False} if t in seq["video_tracks"] else {"video": False})}}])[0]["clips"][0]
            steps: list[dict] = [{"id": "edit.pasteAttributes", "params": {"clips": [new]}}]
            if abs(float(ti.get("speed") or 1.0) - 1.0) > 1e-9:
                steps.append({"id": "clip.speedDuration", "params": {"clips": [new], "speed": round(float(ti["speed"]) * 100, 4), "ripple": False}})
            self.fc.batch(steps)
            return {"removed": tid, "clip": new}
        raise CutError(f"no transition {tid} on the cut")

    def place(self, tl: Timeline, src: dict, track: str | int, frame: float, insert: bool = False) -> dict:
        """Put a clip, picture or sound on a track at `frame`: a loom2 clip (`clip_id`, a take with no shot) or a Catalogue asset (`path`,
        `asset_id`, `kind`) imported once as a project item with its links."""
        return self.changing(tl, lambda p: self._place(p, tl, src, track, frame, insert))

    def _place(self, p: Path, tl: Timeline, src: dict, track: str | int, frame: float, insert: bool) -> dict:
        doc = read(p)
        cut = tracks(doc)
        if isinstance(track, str) and track[:1] in ("V", "A") and track[1:].isdigit():
            pool = cut.video if track[0] == "V" else cut.audio
            tr = pool[int(track[1:]) - 1] if 0 < int(track[1:]) <= len(pool) else None
        else:
            tr = next((x for x in cut.video + cut.audio if str(x.id) == str(track)), None)
        if tr is None:
            raise CutError(f"the cut has no track {track}")
        sound = not src.get("clip_id") and src.get("kind") == "audio"
        if sound and tr.kind != "audio":
            raise CutError("a sound goes on an audio track")
        if not sound and tr.kind != "video":
            raise CutError("a clip or a picture goes on a video track")
        if src.get("clip_id"):
            rec = src["record"]
            use = (src["clip_id"], src.get("shot_id") or "", src.get("shot_version") or "", src.get("node_id") or "")
            item = self._media_item(doc, tl, use, rec)
            av = {"audio": False}
        else:
            have = {it["metadata"].get("loom2.asset"): int(k) for k, it in items(doc).items()
                    if it.get("metadata", {}).get("loom2.asset") and "loom2.line" not in it["metadata"]}
            item = have.get(src["asset_id"])
            if item is None:
                r = self.fc.batch([{"id": "file.import", "params": {"paths": [str(src["path"])]}}])
                item = int(r[0]["items"][0])
                self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.asset": src["asset_id"]}}}])
            av = {"video": False} if src.get("kind") == "audio" else {"audio": False}
        r = self.fc.batch([{"id": "timeline.place", "params": {"item": item, "track": track, "time": ticks(frame, tl.fps), "insert": bool(insert), **av}}])
        self._markers(p)
        return {"clips": r[0]["clips"], "item": item}

    def replace(self, tl: Timeline, clip: int, use: tuple[str, str, str, str], rec: ClipRecord) -> dict:
        """*Update* (D125 S13) on a FilmCraft cut: the track's clip plays another take in place — its start and length kept, the source
        from the take's start — so the edits around it survive."""
        def run(p: Path) -> dict:
            item = self._media_item(read(p), tl, use, rec)
            self.fc.batch([{"id": "clip.replaceFromBin", "params": {"clips": [clip], "item": item, "keepSourceIn": False}}])
            self._markers(p)
            return {"clip": clip, "item": item}
        return self.changing(tl, run)

    def _markers(self, p: Path) -> None:
        """Save, then put the sequence's chapter markers on V1's named takes (a take's start; FilmCraft keeps no marker on a clip by
        command, and a sequence marker does not follow a clip that moves) and save again — FilmCraft's FCPXML carries them to Resolve.
        The cut's markers are loom2's: hand-set markers come with the editor's marker tools (CE5)."""
        self.fc.save()
        if self.name_of is None:
            return
        cut = tracks(read(p))
        steps: list[dict] = [{"id": "markers.clearAll", "params": {"target": "program"}}]
        for i, start, _ in runs(cut):
            name = self.name_of(_as_clip(i))
            if name:
                steps.append({"id": "markers.addChapter", "params": {"time": ticks(start, cut.fps), "name": name}})
        self.fc.batch(steps)
        self.fc.save()

    def frame(self, tl: Timeline, seconds: float, side: int) -> bytes:
        self._open(tl, change=False)
        return self.fc.frame(seconds, side)

    def mix(self, tl: Timeline, loudness: float | None) -> Path:
        """CE3: the cut's sound as FilmCraft mixes it — a WAV of every audio track (gain, fades, ducking, the tracks' volume), at the movie's
        loudness — kept per revision in `timelines/<id>/mix/` (the older ones go): what the page plays with the picture."""
        out = self.path(tl.id).parent / "mix" / f"{tl.revision}.wav"
        if out.is_file():
            return out
        self._open(tl, change=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(f"{tl.revision}.part.wav")
        self.fc.command("file.exportMedia", {"path": str(part), "format": "wav", "wait": True, **({"loudnessLufs": loudness} if loudness is not None else {})})
        part.replace(out)
        for old in out.parent.glob("*.wav"):
            if old != out:
                old.unlink(missing_ok=True)
        return out

    def interchange(self, tl: Timeline, fmt: str, out: Path) -> str:
        """FilmCraft's own FCPXML or EDL of the cut (everything the project holds), written to `out`."""
        self._open(tl, change=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(out.name + ".part")
        self.fc.command("file.exportInterchange", {"format": fmt, "path": str(part)})
        part.replace(out)
        return out.read_text(encoding="utf-8")

    # ---- media ------------------------------------------------------------------------------------
    def _media(self, doc: dict, tl: Timeline, clips: dict[str, ClipRecord]) -> dict[tuple, int]:
        """The project's media item for each use of a take on the lane (the take with its stamps, `_use`)."""
        out: dict[tuple, int] = {}
        for use in dict.fromkeys(_use(c) for c in tl.clips):
            rec = clips.get(use[0])
            if rec is None:
                raise CutError(f"clip {use[0]} is not in the project")
            out[use] = self._media_item(doc, tl, use, rec)
        return out

    def _media_item(self, doc: dict, tl: Timeline, use: tuple[str, str, str, str], rec: ClipRecord) -> int:
        """The project item of a take as used, imported when it is missing (a take at the cut's rate as its PNG master, any other as
        its proxy) with its links."""
        have = {_use_of(it["metadata"]): int(k) for k, it in items(doc).items() if "loom2.clip" in it.get("metadata", {})}
        if use in have:
            return have[use]
        cid = use[0]
        master = rec.fps == tl.fps and tl.fps in TIMEBASES and (self.ws.path / "clips" / cid / "master" / "000000.png").is_file()
        src = self.ws.path / "clips" / cid / "master" / "000000.png" if master else self.ws.path / rec.proxy_path
        if not src.is_file():
            raise CutError(f"clip {cid} has no {'master' if master else 'proxy'} on disk ({src})")
        r = self.fc.batch([{"id": "prefs.set", "params": {"values": prefs(tl.fps)}},
                           {"id": "file.import", "params": {"paths": [str(src)], **({"imageSequence": True} if master else {})}}])
        item = int(r[1]["items"][0])
        self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.clip": cid, "loom2.fps": str(rec.fps), "loom2.media": "master" if master else "proxy",
                                                                                  "loom2.shot": use[1], "loom2.version": use[2], "loom2.node": use[3]}}}])
        doc["project"]["items"][str(item)] = {"metadata": {"loom2.clip": cid, "loom2.shot": use[1], "loom2.version": use[2], "loom2.node": use[3]}}   # seen by the next use
        return item

    def _line_steps(self, doc: dict, tl: Timeline, s: list[int]) -> tuple[list[dict], set[str]]:
        """The spoken lines on A1 where the exports lay them (`line_spans`), a line that would overlap the one before it starting where
        that one ends; each line's audio imported once with its links. Returns the steps and the lines placed (`node:line`)."""
        if self.audio_of is None:
            return [], set()
        have = {it["metadata"].get("loom2.asset"): int(k) for k, it in items(doc).items() if "loom2.line" in it.get("metadata", {})}
        placed: list[tuple[int, int, dict]] = []                                  # (start tick at the lane's rate, length in ticks, cue)
        for i, c in enumerate(tl.clips):
            cues = self.audio_of(c) or []
            for (a0, _), cue in zip(line_spans(lane_ticks(tl, c), len(cues)), cues):
                if cue and cue.get("path"):
                    placed.append((s[i] + a0, max(1, round(float(cue["duration_s"]) * tl.fps)), cue))
        placed.sort(key=lambda x: x[0])
        steps: list[dict] = []
        keys = {f"{cue.get('node')}:{cue.get('line')}" for _, _, cue in placed}
        end = 0
        for start, length, cue in placed:
            start = max(start, end)
            end = start + length
            item = have.get(cue.get("asset"))
            if item is None:
                item = have[cue.get("asset")] = self._line_item(cue)
            steps.append({"id": "timeline.place", "params": {"item": item, "track": "A1", "time": ticks(start, tl.fps), "insert": False, "video": False}})
        return steps, keys

    def _line_item(self, cue: dict) -> int:
        """A spoken line's audio imported as a project item with its links."""
        r = self.fc.batch([{"id": "file.import", "params": {"paths": [str(cue["path"])]}}])
        item = int(r[0]["items"][0])
        self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.asset": str(cue.get("asset") or ""), "loom2.node": str(cue.get("node") or ""),
                                                                                  "loom2.line": str(cue.get("line", 0))}}}])
        return item

    def sync_lines(self, tl: Timeline) -> int:
        """Before an export or the movie: a voiced line not on A1 yet is placed where the exports lay it (its shot's lines evenly across the
        shot's run on V1, pushed past a clip already there); a line voiced anew plays its new audio in place; a line the author moved stays.
        One change (one undo step) when anything moved; none otherwise. Returns how many lines changed. CE3: the lines are the author's — a line
        on any audio track counts, and a line the cut placed before that is gone now was lifted by the author and stays out."""
        if self.audio_of is None:
            return 0
        p = self.path(tl.id)
        doc = read(p)
        cut = tracks(doc)
        seq_id = cut.sequence
        a1 = cut.audio[0].items if cut.audio else []
        have = {(i.node_id, i.line): i for t in cut.audio for i in t.items if i.kind == "line"}
        gone = placed_lines(doc)
        missing: list[tuple[float, dict]] = []
        revoiced: list[tuple[CutItem, dict]] = []
        for first, start, end in runs(cut):
            cues = self.audio_of(_as_clip(first)) or []
            for (a0, _), cue in zip(line_spans(round(end - start), len(cues)), cues):
                if not cue or not cue.get("path"):
                    continue
                ex = have.get((cue.get("node"), cue.get("line")))
                if ex is None:
                    if f"{cue.get('node')}:{cue.get('line')}" not in gone:              # lifted by the author: it stays out
                        missing.append((start + a0, cue))
                elif ex.asset_id != cue.get("asset"):
                    revoiced.append((ex, cue))
        if not missing and not revoiced:
            return 0

        def run(p: Path) -> int:
            steps: list[dict] = []
            for ex, cue in revoiced:
                steps.append({"id": "clip.replaceFromBin", "params": {"clips": [ex.id], "item": self._line_item(cue), "keepSourceIn": True}})
            spans = sorted((i.start, i.start + i.duration) for i in a1)
            for start, cue in sorted(missing, key=lambda x: x[0]):
                length = max(1.0, round(float(cue["duration_s"]) * cut.fps))
                for a, b in spans:                                          # pushed past a clip the line would land on
                    if a < start + length and start < b:
                        start = b
                spans = sorted(spans + [(start, start + length)])
                steps.append({"id": "timeline.place", "params": {"item": self._line_item(cue), "track": "A1", "time": ticks(start, cut.fps), "insert": False, "video": False}})
            known = sorted(gone | {f"{c.get('node')}:{c.get('line')}" for _, c in missing})
            steps.append({"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.lines": json.dumps(known)}}})
            self.fc.batch(steps)
            self._markers(p)
            return len(steps)
        return self.changing(tl, run)


def _as_clip(i: CutItem) -> TimelineClip:
    """A take as the story lookups read it (by its clip, shot and node)."""
    return TimelineClip(id=str(i.id), clip_id=i.clip_id or "", **{"in": 0}, out=1, shot_id=i.shot_id, shot_version=i.shot_version, node_id=i.node_id)


def runs(cut: CutTracks) -> list[tuple[CutItem, float, float]]:
    """V1's takes as shots: consecutive pieces of the same node (a take razored, or held) are one run — (its first piece, start, end)."""
    out: list[tuple[CutItem, float, float]] = []
    for i in (cut.video[0].items if cut.video else []):
        if i.kind != "take":
            continue
        if out and i.node_id and out[-1][0].node_id == i.node_id and abs(out[-1][2] - i.start) < 0.5:
            out[-1] = (out[-1][0], out[-1][1], i.start + i.duration)
        else:
            out.append((i, i.start, i.start + i.duration))
    return out


def cut_srt(cut: CutTracks, lines_of: Callable[[TimelineClip], list[str]]) -> str:
    """CE2: the SubRip of a FilmCraft cut — each shot's lines across where its run sits on V1 (laid evenly, as the lane's SRT), a voiced
    line where its clip sits on A1."""
    from .timelines import srt_tc
    voiced = {(i.node_id, i.line): (i.start, i.start + i.duration) for t in cut.audio for i in t.items if i.kind == "line"}
    cues: list[tuple[float, float, str]] = []
    for i, start, end in runs(cut):
        if not i.node_id:
            continue
        said = [(k, x.strip()) for k, x in enumerate(lines_of(_as_clip(i))) if x and x.strip()]
        for (a0, b0), (k, text) in zip(line_spans(round(end - start), len(said)), said):
            a, b = voiced.get((i.node_id, k), (start + a0, start + b0))
            cues.append((a, b, text))
    out: list[str] = []
    for n, (a, b, text) in enumerate(sorted(cues, key=lambda x: x[0]), 1):
        out += [str(n), f"{srt_tc(round(a), cut.fps)} --> {srt_tc(max(round(a) + 1, round(b)), cut.fps)}", text, ""]
    return "\n".join(out)


def cut_markers(cut: CutTracks, name_of: Callable[[TimelineClip], str | None]) -> str:
    """CE2: the markers sidecar of a FilmCraft cut — a line per named shot (a run of V1) at its start (`HH:MM:SS:FF<TAB>name`)."""
    from .timelines import tc
    out = [f"{tc(round(start), cut.fps)}\t{name}" for i, start, _ in runs(cut) if (name := name_of(_as_clip(i)))]
    return "\n".join(out) + ("\n" if out else "")


def _use(c: TimelineClip) -> tuple[str, str, str, str]:
    """A take as the lane uses it: the clip and the stamps of the shot it stands for (none for a plain clip)."""
    return (c.clip_id, c.shot_id or "", c.shot_version or "", c.node_id or "")


def _use_of(meta: dict) -> tuple[str, str, str, str]:
    return (meta["loom2.clip"], meta.get("loom2.shot", ""), meta.get("loom2.version", ""), meta.get("loom2.node", ""))


def clip_records(ws: Workspace) -> dict[str, ClipRecord]:
    return {c.id: c for c in ClipStore(ws).list()}

