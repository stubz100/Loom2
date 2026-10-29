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

D127 (30 §16): every audio track has a channel strip — gain, width, volume, pan — kept in the project as FilmCraft holds it (the fader and the
pan on the track, the gain as pre-fader Amplify inserts, the width as a Stereo Width insert after the other pre-fader effects, the volume
past the fader's +15 dB as a post-fader Amplify; a neutral stage is no insert) and read back from it (`strip_of`); a track's role
(dialogue, music, effects) rides in the sequence's `loom2.roles`. A new cut's A1–A3 are the three roles with Settings › Audio's strips.

AU4 (30 §16): an audio track's chain of VST3 effects rides in the sequence's `loom2.chains` (each effect's state a file of loom2's host in
`timelines/<id>/fx/`, a new file per edit so the cut's undo takes it back). FilmCraft cannot run a plug-in, so a track with an effect on is
*printed* (`Cuts.sync_prints`, before the page's mix, the movie and the exports): its sound alone at unity — the other tracks muted, its
strip neutral — is exported by FilmCraft in a process of its own (the project untouched), run through its gain and chain by loom2's host,
and placed on a companion track (`loom2.prints`) that carries the source's width, volume, pan and mute; the source plays into a muted
submix. A print is current while its key — the track's clips, media, gain and other pre-fader effects, the chain and the span — is the
same and its file is there. The companions are not shown (`tracks()` leaves them out).

CE4 (30 §5, O6): colour. A clip's grade is its Lumetri effect (FilmCraft's): a preset, a look (built in or a LUT file), the basic values,
and a match to another shot (`lumetri.applyMatch`: FilmCraft solves the colour wheels toward a reference frame). *Grade the scene* puts an
adjustment layer on the cut's top *Grade* track over the run of shots in the same scene as the chosen one (RC2c: the Flow's scene group;
a shot in none falls back to its place) — a clip the author trims like any other, its own Lumetri the scene's grade.

CE5 (30 §5): captions and markers. *Captions from the lines* makes the cut's caption track (FilmCraft's, `captions.*`) from the Dialogue
lines where the SRT lays them (a voiced line where its clip sits); the author edits the captions by FilmCraft's commands; the movie burns
them in or writes them beside it, and the SRT export is the caption track when there is one. The author's own markers (comment markers)
live beside loom2's chapter markers: the chapters are rebuilt after every change, the author's kept.
"""
from __future__ import annotations

import functools
import json
import threading
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .clips import ClipRecord, ClipStore
from .config import TRACK_ROLES, AudioSettings, TrackStrip
from .filmcraft import TICK, TIMEBASES, FilmCraft, prefs, ticks
from .fsio import atomic_copy, new_id, plain_name
from .timelines import Timeline, TimelineClip, duration, line_spans, starts
from .timelines import ticks as lane_ticks
from .workspace import Workspace

CUT_FILE = "cut.fcproj"
FORMAT = "filmcraft.project"
UNDO_DEPTH = 50                                    # the cut's undo: snapshots of its project in `history/undo/` (FilmCraft's own undo dies with its session)
ROLE_NAMES = {"dialogue": "Dialogue", "music": "Music", "effects": "Effects"}   # D127: a track given a role is named after it
AMPLIFY_MAX_DB = 24.0                              # FilmCraft's Amplify reaches +24 dB (764723f): past it, a second stage
FADER_MAX_DB = 15.0                                # its fader reaches +15 dB: past it, a post-fader Amplify
SILENT_DB = -96.0                                  # its fader's floor renders silence (−∞)
MAX_INSERTS = 5                                    # its effect slots on a track
STRIP_EFFECTS = ("amplify", "stereo_width")        # the inserts a strip is made of (the author's other track effects stay where they are)
GRADE_PARAMS = {                                   # CE4: the grade values loom2 sets (Lumetri's ranges; defaults: 0, saturation and intensity 100)
    "temperature": (-100.0, 100.0), "tint": (-100.0, 100.0), "exposure": (-5.0, 5.0), "contrast": (-100.0, 100.0),
    "highlights": (-100.0, 100.0), "shadows": (-100.0, 100.0), "whites": (-100.0, 100.0), "blacks": (-100.0, 100.0),
    "saturation": (0.0, 200.0), "vibrance": (-100.0, 100.0), "faded_film": (0.0, 100.0), "look_intensity": (0.0, 200.0),
}
CAPTION_TRACK = "Lines"                            # CE5: the caption track made from the lines
CAPTION_STYLE = {"size": 42, "background": True, "anchor": "bottom"}   # its first look: subtitles at the bottom, on a box
GRADE_TRACK = "Grade"                              # CE4: the top video track the scene grades sit on
TAIL_S = 8.0                                       # AU4: a print runs this far past its track's last sound (an effect's tail), within the cut
PRINT_BUS = "loom2 · printed sources"              # the muted submix a printed track plays into


def mix_name(revision: int, loudness: float | None) -> str:
    """V39: the cut's mix file, by revision and loudness target (`12-auto.wav`, `12-m16.wav` for −16 LUFS)."""
    return f"{revision}-{'auto' if loudness is None else format(loudness, 'g').replace('-', 'm').replace('.', '_')}.wav"


CUT_LOCK = threading.RLock()                       # U7c (06 §3): the FilmCraft session holds one project at a time — a change (its project
                                                   # opened, the commands, the save) holds it whole, so two requests never interleave in it


def _held(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def run(*a: Any, **k: Any) -> Any:
        with CUT_LOCK:
            return fn(*a, **k)
    return run


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


def roles(doc: dict) -> dict[int, str]:
    """D127: the audio tracks' roles (track id → dialogue / music / effects), from the sequence's `loom2.roles`."""
    _, seq_item, _ = sequence(doc)
    try:
        raw = json.loads(seq_item.get("metadata", {}).get("loom2.roles") or "{}")
    except json.JSONDecodeError:
        return {}
    return {int(k): v for k, v in raw.items() if v in TRACK_ROLES and str(k).isdigit()}


def _meta_json(doc: dict, key: str) -> dict:
    _, seq_item, _ = sequence(doc)
    try:
        raw = json.loads(seq_item.get("metadata", {}).get(key) or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def chains(doc: dict) -> dict[int, list[dict]]:
    """AU4: the audio tracks' effect chains (track id → [{id, bundle, uid, name, vendor, bypass, state}] in order), from `loom2.chains`."""
    return {int(k): v for k, v in _meta_json(doc, "loom2.chains").items() if str(k).isdigit() and isinstance(v, list)}


def prints(doc: dict) -> dict[int, dict]:
    """AU4: the printed tracks (source id → {track: the companion's id, key, file}), from `loom2.prints`."""
    return {int(k): v for k, v in _meta_json(doc, "loom2.prints").items() if str(k).isdigit() and isinstance(v, dict) and "track" in v}


def active(chain: list[dict]) -> list[dict]:
    return [e for e in chain if not e.get("bypass")]


def _end(t: dict) -> int:
    return max((ti["start"] + ti["duration"] for ti in t.get("items", [])), default=0)


def print_span(seq: dict, t: dict, companions: set[int]) -> float:
    """The seconds a print of `t` covers: to its last sound and an effect's tail, within the cut (the companions not counted)."""
    cut = max((_end(x) for x in seq["video_tracks"] + seq["audio_tracks"] if x["id"] not in companions), default=0)
    return round(min(cut, _end(t) + TAIL_S * TICK) / TICK, 6)


def print_key(doc: dict, t: dict, chain: list[dict], companions: set[int]) -> str:
    """What a print of `t` depends on: its clips and transitions, their media, its gain and other pre-fader effects, the active chain (a
    new state file is a new edit), the span and the rate. The width, volume, pan and mute are the companion's, never printed."""
    import hashlib
    its = items(doc)
    _, _, seq = sequence(doc)
    media = {str(ti["item"]): ((its.get(str(ti["item"]), {}).get("kind", {}) or {}).get("Media", {}).get("media", {}).get("File") or {}).get("path")
             for ti in t.get("items", []) if isinstance(its.get(str(ti["item"]), {}).get("kind"), dict)}
    pre = [e for e in t.get("effects") or [] if not e.get("post_fader") and e.get("effect") != "stereo_width"]
    body = {"items": t.get("items", []), "transitions": t.get("transitions", []), "media": media, "pre": pre,
            "chain": [[e["bundle"], e.get("uid", ""), e.get("state")] for e in active(chain)], "span": print_span(seq, t, companions),
            "rate": seq["settings"].get("sample_rate")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _param(e: dict, name: str, default: float) -> float:
    v = (e.get("params", {}).get(name) or {}).get("value")
    if isinstance(v, dict):
        v = v.get("Float", default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def strip_of(t: dict) -> TrackStrip:
    """D127: an audio track's strip as its project holds it — the gain is the pre-fader Amplify stages, the width the last pre-fader
    Stereo Width, the volume the fader and any post-fader Amplify (the floor is silence), the pan the track's. Read as it is, not clamped."""
    fx = [e for e in t.get("effects") or [] if e.get("enabled", True) is not False]
    pre = [e for e in fx if not e.get("post_fader")]
    widths = [_param(e, "width", 100.0) for e in pre if e.get("effect") == "stereo_width"]
    fader = float(t.get("volume_db") or 0.0)
    extra = sum(_param(e, "gain", 0.0) for e in fx if e.get("post_fader") and e.get("effect") == "amplify")
    return TrackStrip.model_construct(gain_db=round(sum(_param(e, "gain", 0.0) for e in pre if e.get("effect") == "amplify"), 2),
                                      volume_db=SILENT_DB if fader <= SILENT_DB else round(fader + extra, 2),
                                      pan=round(float(t.get("pan") or 0.0), 2), width=round(widths[-1] if widths else 100.0, 2))


def _stages(db: float) -> list[float]:
    """A level as Amplify stages FilmCraft can hold (each up to +24 dB); none for 0 dB."""
    out = []
    while db > AMPLIFY_MAX_DB + 1e-9:
        out.append(AMPLIFY_MAX_DB)
        db -= AMPLIFY_MAX_DB
    if abs(db) > 1e-9:
        out.append(round(db, 2))
    return out


def strip_steps(t: dict, s: TrackStrip) -> list[dict]:
    """D127: the FilmCraft commands that give the audio track `t` (its project dict) the strip `s`: the strip's old inserts out, the gain
    stages first, the width after the track's other pre-fader effects, the volume's stage past +15 dB right after the fader; the fader and
    the pan on the track."""
    ref = t["id"]
    fx = t.get("effects") or []
    steps: list[dict] = [{"id": "mixer.removeInsert", "params": {"strip": ref, "slot": k}} for k in reversed(range(len(fx))) if fx[k].get("effect") in STRIP_EFFECTS]
    rest = [e for e in fx if e.get("effect") not in STRIP_EFFECTS]
    gains = _stages(s.gain_db)
    extra = _stages(s.volume_db - FADER_MAX_DB) if s.volume_db > FADER_MAX_DB else []
    wide = abs(s.width - 100.0) > 1e-9
    if len(rest) + len(gains) + int(wide) + len(extra) > MAX_INSERTS:
        raise CutError(f"FilmCraft holds {MAX_INSERTS} effects on a track and this one has {len(rest)} of its own — the strip needs {len(gains) + int(wide) + len(extra)} more")

    def add(slot: int, effect: str, params: dict, post: bool = False) -> list[dict]:
        return [{"id": "mixer.addInsert", "params": {"strip": ref, "effect": effect, "slot": slot, "postFader": post}},
                {"id": "mixer.setInsert", "params": {"strip": ref, "slot": slot, "params": params}}]
    for k, g in enumerate(gains):
        steps += add(k, "amplify", {"gain": g})
    pre_rest = max((k + 1 for k, e in enumerate(rest) if not e.get("post_fader")), default=0)
    at = len(gains) + pre_rest
    if wide:
        steps += add(at, "stereo_width", {"width": s.width})
        at += 1
    for k, g in enumerate(extra):
        steps += add(at + k, "amplify", {"gain": g}, post=True)
    fader = SILENT_DB if s.volume_db <= SILENT_DB else min(s.volume_db, FADER_MAX_DB)
    steps.append({"id": "mixer.setStrip", "params": {"strip": ref, "volumeDb": fader, "pan": s.pan}})
    return steps


def _effect(tr: dict) -> str:
    e = tr.get("effect")
    return e.get("effect", "") if isinstance(e, dict) else str(e or "")


class CutGrade(BaseModel):
    """CE4: a clip's grade as its Lumetri holds it — the look (a LUT ref, or none), the values, whether it is matched to another shot."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    look: str = ""                                  # "builtin:…" / "lib:…" (an imported LUT file) / "" none
    values: dict[str, float] = Field(default_factory=dict)
    matched: bool = False                           # the colour wheels moved (a match, or a preset that sets them)


def grade_of(ti: dict) -> CutGrade | None:
    """The clip's Lumetri, read as it is (None: no grade)."""
    e = next((x for x in ti.get("effects") or [] if x.get("effect") == "lumetri" and x.get("enabled", True) is not False), None)
    if e is None:
        return None
    pr = e.get("params", {})

    def val(name: str, default: float) -> float:
        v = (pr.get(name) or {}).get("value", {})
        return float(v.get("Float", default)) if isinstance(v, dict) else default
    look = ((pr.get("look_lut") or {}).get("value") or {}).get("Text", "") or ""
    wheels = any(abs(float(((pr.get(f"wheel_{w}") or {}).get("value") or {}).get("Vec2", {}).get(k, 0.0))) > 1e-6 for w in ("shadows", "midtones", "highlights") for k in ("x", "y"))
    wheels = wheels or any(abs(val(f"wheel_{w}_l", 0.0)) > 1e-6 for w in ("shadows", "midtones", "highlights"))
    return CutGrade(look=look, values={k: round(val(k, 100.0 if k in ("saturation", "look_intensity") else 0.0), 3) for k in GRADE_PARAMS}, matched=wheels)


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
    grade: CutGrade | None = None                   # CE4: its colour (a video clip's or an adjustment layer's Lumetri)


class CutTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, json_schema_serialization_defaults_required=True)
    id: int
    effect: str
    start: float
    duration: float
    from_: int | None = Field(None, alias="from")
    to: int | None = None


class CutEffect(BaseModel):
    """AU4: a VST3 effect in an audio track's chain (its state a file of loom2's host, relative to the cut's folder; none: its defaults)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    bundle: str
    uid: str = ""
    name: str
    vendor: str = ""
    bypass: bool = False
    state: str | None = None


class CutTrack(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    kind: Literal["video", "audio"]
    name: str
    locked: bool = False
    muted: bool = False
    enabled: bool = True
    volume_db: float = 0.0                          # CE3: the track's volume (D127: the fader and the stage past it; −96 is −∞)
    gain_db: float = 0.0                            # D127: an audio track's strip — its gain, pan (−100 left … +100 right) and width (%)
    pan: float = 0.0
    width: float = 100.0
    role: Literal["dialogue", "music", "effects"] | None = None   # D127: the track's role (its defaults come from Settings › Audio)
    chain: list[CutEffect] = Field(default_factory=list)          # AU4: its VST3 effects in order
    printed: Literal["none", "current", "stale"] = "none"         # AU4: no effect on / its print matches it / it prints before the next mix
    items: list[CutItem] = Field(default_factory=list)
    transitions: list[CutTransition] = Field(default_factory=list)


class CutCaption(BaseModel):
    """CE5: one caption (frames at the cut's rate)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    start: float
    duration: float
    text: str = ""
    speaker: str | None = None


class CutCaptionTrack(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    name: str = ""
    enabled: bool = True                            # shown in the viewer and burned in when asked
    size: float = 42.0
    anchor: str = "bottom"
    background: bool = True
    captions: list[CutCaption] = Field(default_factory=list)


class CutMarker(BaseModel):
    """CE5: a sequence marker — loom2's chapters (one per named shot, rebuilt after every change) and the author's own."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: int
    frame: float
    duration: float = 0.0
    name: str = ""
    comment: str = ""
    kind: str = "Comment"                           # "Chapter" (loom2's) or the author's ("Comment" …)
    color: str = ""


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
    captions: list[CutCaptionTrack] = Field(default_factory=list)   # CE5
    markers: list[CutMarker] = Field(default_factory=list)
    undo: int = 0                                   # the cut's changes it can undo / redo (its project's snapshots)
    redo: int = 0


LINE_BREATH_S = 0.25                                # U7b: between a shot's lines when it is held for them (U6c's layLines: the same breath)


class AssembleShot(BaseModel):
    """U7b (05 §1): one shot of the route as Assemble lays it — the version and its final's clip (None: no final yet), its name, and how
    long its voiced lines run one after another (a breath between)."""
    shot_id: str
    node_id: str | None = None
    version: str
    clip_id: str | None = None
    name: str = ""
    lines_s: float = 0.0


class ShortLines(BaseModel):
    """F39: a shot whose lines run longer than its final, which has no more frames to hold them."""
    name: str
    lines_s: float
    final_s: float


class AssembleReport(BaseModel):
    """U7b: what *Assemble* did to V1 — the shots placed, updated to a newer final, kept as they were, taken off (no longer on the route),
    those without a final (left out, or kept as they are when already on the cut), held for their lines, too short for them, the clips
    renamed after their shots."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    placed: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    kept: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    unfinished: list[str] = Field(default_factory=list)
    held: list[str] = Field(default_factory=list)
    short: list[ShortLines] = Field(default_factory=list)
    renamed: int = 0


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
    role = roles(doc)
    chain_of, printed = chains(doc), prints(doc)
    companions = {v["track"] for v in printed.values()}
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
                               line=int(meta["loom2.line"]) if meta.get("loom2.line") not in (None, "") else None,
                               grade=grade_of(ti) if kind == "video" else None))
        trans = [CutTransition(id=x["id"], effect=_effect(x), start=f(x["start"]), duration=f(x["duration"]), **{"from": x.get("from")}, to=x.get("to"))
                 for x in t.get("transitions", [])]
        sound = strip_of(t).model_dump() if kind == "audio" else {}
        chain = chain_of.get(t["id"], []) if kind == "audio" else []
        state = "none"
        if active(chain):
            pr = printed.get(t["id"]) or {}
            state = "current" if pr.get("key") == print_key(doc, t, chain, companions) and pr.get("file") and Path(pr["file"]).is_file() else "stale"
        return CutTrack(id=t["id"], kind=kind, name=t.get("name", ""), locked=bool(t.get("locked")), muted=bool(t.get("muted")),  # type: ignore[arg-type]
                        enabled=t.get("enabled", True) is not False, items=out, transitions=trans, role=role.get(t["id"]) if kind == "audio" else None,  # type: ignore[arg-type]
                        chain=[CutEffect.model_validate(e) for e in chain], printed=state, **sound)  # type: ignore[arg-type]
    video = [one(t, "video") for t in seq.get("video_tracks", [])]
    audio = [one(t, "audio") for t in seq.get("audio_tracks", []) if t["id"] not in companions]
    end = max([i.start + i.duration for tr in video + audio for i in tr.items] or [0.0])
    caps = []
    for ct in seq.get("caption_tracks") or []:
        style = ct.get("style") or {}
        caps.append(CutCaptionTrack(id=ct["id"], name=ct.get("name", ""), enabled=ct.get("enabled", True) is not False, size=float(style.get("size", 42.0)),
                                    anchor=str(style.get("anchor", "Bottom")).lower(), background=bool(style.get("background", True)),
                                    captions=[CutCaption(id=c["id"], start=f(c["start"]), duration=f(c["duration"]), text=c.get("text", ""), speaker=c.get("speaker"))
                                              for c in sorted(ct.get("captions") or [], key=lambda c: c["start"])]))
    marks = [CutMarker(id=m["id"], frame=f(m["start"]), duration=f(m.get("duration", 0)), name=m.get("name", ""), comment=m.get("comment", ""),
                       kind=str(m.get("kind", "Comment")), color=str(m.get("color", ""))) for m in sorted(seq.get("markers") or [], key=lambda m: m["start"])]
    return CutTracks(sequence=sid, fps=fps, w=int(st["width"]), h=int(st["height"]), duration=round(end, 3), video=video, audio=audio, captions=caps, markers=marks)


# CE2: the FilmCraft commands the Episode's editor may run on a cut (never a file command: the cut's own file is FilmCraft's to write)
EDIT_COMMANDS = frozenset({
    "timeline.move", "timeline.trim", "timeline.roll", "timeline.slip", "timeline.slide", "timeline.razor", "timeline.rateStretch",
    "timeline.setTrack", "timeline.select", "edit.rippleDelete", "edit.clear", "sequence.applyVideoTransition",
    "sequence.applyAudioTransition", "sequence.setTransition", "sequence.closeGap", "sequence.addTracks", "sequence.deleteTrack",
    "clip.speedDuration", "clip.frameHold", "clip.insertFrameHoldSegment", "clip.enable", "clip.rename",
    # CE3: sound — a clip's gain, the dialogue / music types FilmCraft ducks by, the ducking itself, the dialogue's loudness, volume keys
    "clip.audioGain", "essentialSound.setType", "essentialSound.generateDucking", "essentialSound.autoMatch", "clipMixer.set",
    # CE5: captions (the track's own and the author's edits) and the author's markers (loom2 keeps the chapters)
    "captions.add", "captions.setText", "captions.setTimes", "captions.trim", "captions.move", "captions.delete", "captions.split",
    "captions.merge", "captions.setStyle", "captions.setTrack", "markers.add", "markers.edit",
})
REMOVE_TRANSITION = "loom2.removeTransition"      # FilmCraft has no command for it (764723f): the clip lifted and placed again, its attributes kept
REMOVE_MARKER = "loom2.removeMarker"              # CE5: nor for a marker by its id (clearCurrent takes every marker at the playhead): the rest re-added


class Cuts:
    """Writes cuts through the FilmCraft session. `audio_of(clip)` gives a lane clip's spoken lines as story_lookup does (each with the
    file's `path`, its `asset`, `node` and `line`), or None when the cut carries no lines; `name_of(clip)` a take's chapter name (its
    node's title or its shot's name) — loom2 keeps the sequence's chapter markers on V1's named takes after every change (`_markers`)."""

    def __init__(self, ws: Workspace, fc: FilmCraft, audio_of: Callable[[TimelineClip], list[dict | None]] | None = None,
                 name_of: Callable[[TimelineClip], str | None] | None = None, audio: Callable[[], AudioSettings] | None = None,
                 host: Any = None) -> None:
        self.ws, self.fc, self.audio_of, self.name_of = ws, fc, audio_of, name_of
        self.host = host                                    # AU4: loom2's VST3 host (loom2.vsthost.VstHost) — the prints need it
        self.audio = audio or AudioSettings                 # D127: Settings › Audio (the track roles' strips), read when a cut is made

    def available(self) -> bool:
        return self.fc.available()

    def path(self, tl_id: str) -> Path:
        return self.ws.timelines_dir / plain_name(tl_id) / CUT_FILE

    @_held
    def forget(self, tl_id: str) -> None:
        """The session closes the cut's project (it is being deleted)."""
        self.fc.close(self.path(tl_id))

    @_held
    def create(self, tl: Timeline) -> Path:
        """A new cut's project, empty, at the cut's format; A1–A3 are the dialogue, music and effects tracks with Settings › Audio's strips."""
        p = self.path(tl.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.fc.new(p, tl.name, tl.w, tl.h, tl.fps)
        doc = read(p)
        seq_id, _, seq = sequence(doc)
        steps: list[dict] = []
        for t, role in zip(seq["audio_tracks"], TRACK_ROLES):
            steps += [{"id": "timeline.setTrack", "params": {"track": t["id"], "name": ROLE_NAMES[role]}}, *strip_steps(t, self.audio().role(role))]
        given = {str(t["id"]): role for t, role in zip(seq["audio_tracks"], TRACK_ROLES)}
        self.fc.batch(steps + [{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.roles": json.dumps(given)}}}])
        self.fc.save()
        return p

    @_held
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

    @_held
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

    @_held
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
            if st.get("id") not in EDIT_COMMANDS and st.get("id") not in (REMOVE_TRANSITION, REMOVE_MARKER):
                raise CutError(f"`{st.get('id')}` is not an editor command")
        def run(p: Path) -> list[Any]:
            results: list[Any] = []
            for st in steps:
                if st["id"] == REMOVE_TRANSITION:
                    self.fc.save()                                    # the removal reads the project as it stands
                    results.append(self._remove_transition(read(p), int(st.get("params", {}).get("transition", 0))))
                elif st["id"] == REMOVE_MARKER:
                    self.fc.save()
                    results.append(self._remove_marker(read(p), int(st.get("params", {}).get("marker", 0))))
                else:
                    results.extend(self.fc.batch([{"id": st["id"], "params": st.get("params") or {}}]))
            self._markers(p)
            return results
        return self.changing(tl, run)

    # ---- D127: a track's strip and role ------------------------------------------------------------------------------------------
    def _audio_track(self, doc: dict, track: int) -> dict:
        _, _, seq = sequence(doc)
        t = next((x for x in seq["audio_tracks"] if x["id"] == track), None)
        if t is None:
            raise CutError(f"the cut has no audio track {track}")
        return t

    def strip(self, tl: Timeline, track: int, change: dict) -> dict:
        """The audio track's strip with `change` (any of gain_db, volume_db, pan, width) — the rest as it is — as FilmCraft holds it."""
        def run(p: Path) -> dict:
            t = self._audio_track(read(p), track)
            s = TrackStrip.model_validate({**strip_of(t).model_dump(), **{k: v for k, v in change.items() if v is not None}})
            self.fc.batch(strip_steps(t, s))
            self.fc.save()
            return {"track": track, **s.model_dump()}
        return self.changing(tl, run)

    def role(self, tl: Timeline, track: int, role: str | None) -> dict:
        """The audio track's role: named after it and its strip set to the role's in Settings › Audio (None: no role, the strip kept)."""
        if role is not None and role not in TRACK_ROLES:
            raise CutError(f"a track's role is one of {', '.join(TRACK_ROLES)}")
        def run(p: Path) -> dict:
            doc = read(p)
            t = self._audio_track(doc, track)
            seq_id, _, _ = sequence(doc)
            given = {str(k): v for k, v in roles(doc).items() if k != track}
            steps: list[dict] = []
            if role is not None:
                given[str(track)] = role
                steps += [{"id": "timeline.setTrack", "params": {"track": track, "name": ROLE_NAMES[role]}}, *strip_steps(t, self.audio().role(role))]
            self.fc.batch(steps + [{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.roles": json.dumps(given)}}}])
            self.fc.save()
            return {"track": track, "role": role}
        return self.changing(tl, run)

    # ---- CE4: colour ---------------------------------------------------------------------------------------------------------------
    def _video_clip(self, doc: dict, clip: int) -> tuple[dict, dict]:
        _, _, seq = sequence(doc)
        for tr in seq["video_tracks"]:
            ti = next((x for x in tr["items"] if x["id"] == clip), None)
            if ti is not None:
                return tr, ti
        raise CutError(f"the cut has no video clip {clip}")

    def grade(self, tl: Timeline, clip: int, change: dict) -> dict:
        """A video clip's (or a scene grade's) colour: `preset` (one of FilmCraft's; it replaces the clip's grade), `look` (a LUT ref, ""
        none), `look_file` (a .cube / .3dl imported into the cut's project), `values` (GRADE_PARAMS, brought inside their ranges), `match`
        (another clip: this one's colour solved toward that clip's middle frame), `reset` (the grade away) — one change of the cut. A clip
        keeps one Lumetri: FilmCraft's looks, matches and values act on a clip's first, but a preset always inserts another (764723f)."""
        def run(p: Path) -> dict:
            doc = read(p)
            _, ti = self._video_clip(doc, clip)
            out: dict = {"clip": clip}
            mine = [i for i, e in enumerate(ti.get("effects") or []) if e.get("effect") == "lumetri"]
            away = [{"id": "effects.remove", "params": {"clip": clip, "index": k}} for k in reversed(mine)]
            if change.get("reset"):
                if away:
                    self.fc.batch(away)
                self.fc.save()
                return out
            steps: list[dict] = []
            if change.get("preset"):
                steps += away + [{"id": "lumetri.applyPreset", "params": {"name": change["preset"], "clips": [clip]}}]
            elif not mine:
                steps.append({"id": "effects.apply", "params": {"clips": [clip], "effect": "lumetri"}})
            if change.get("look_file"):
                lut = self.fc.batch([{"id": "lut.import", "params": {"path": str(change["look_file"])}}])[0]
                steps.append({"id": "lumetri.setLook", "params": {"clip": clip, "lut": lut["ref"]}})
            elif change.get("look") is not None:
                steps.append({"id": "lumetri.setLook", "params": {"clip": clip, "lut": str(change["look"])}})
            for k, v in (change.get("values") or {}).items():
                if k not in GRADE_PARAMS:
                    raise CutError(f"`{k}` is not a grade value ({', '.join(GRADE_PARAMS)})")
                lo, hi = GRADE_PARAMS[k]
                steps.append({"id": "effects.setParam", "params": {"clip": clip, "effect": "lumetri", "param": k, "value": min(hi, max(lo, float(v)))}})
            if change.get("match") is not None:
                _, ref = self._video_clip(doc, int(change["match"]))
                steps.append({"id": "lumetri.applyMatch", "params": {"clip": clip, "referenceTime": ref["start"] + ref["duration"] // 2}})
            res = self.fc.batch(steps) if steps else []
            if change.get("match") is not None and res:
                m = res[-1] or {}
                out["match"] = {"before": round(float(m.get("distanceBefore", 0.0)), 4), "after": round(float(m.get("distanceAfter", 0.0)), 4)}
            self.fc.save()
            return out
        return self.changing(tl, run)

    def grade_scene(self, tl: Timeline, clip: int, place_of: Callable[[str | None], tuple[str | None, str]]) -> dict:
        """*Grade the scene*: an adjustment layer on the top *Grade* track over the run of V1's shots in the same scene as `clip` (RC2c: its
        node's scene group, else its place; a shot with neither is its own run); the scene's grade if it is there already. `place_of(node_id)`
        → (the group's key — `scene:<id>` or `place:<id>` — and its name)."""
        def run(p: Path) -> dict:
            doc = read(p)
            seq_id, _, seq = sequence(doc)
            its = items(doc)
            v1 = sorted(seq["video_tracks"][0]["items"], key=lambda x: x["start"]) if seq["video_tracks"] else []
            k = next((i for i, x in enumerate(v1) if x["id"] == clip), None)
            if k is None:
                raise CutError("a scene is graded from one of V1's shots")
            node = lambda x: its.get(str(x["item"]), {}).get("metadata", {}).get("loom2.node") or None   # noqa: E731
            place, name = place_of(node(v1[k]))
            lo = hi = k
            while place and lo > 0 and place_of(node(v1[lo - 1]))[0] == place:
                lo -= 1
            while place and hi + 1 < len(v1) and place_of(node(v1[hi + 1]))[0] == place:
                hi += 1
            key = f"{place}:{v1[lo]['id']}" if place else f"clip:{clip}"
            start, end = v1[lo]["start"], v1[hi]["start"] + v1[hi]["duration"]
            meta = json.loads(its[str(seq_id)].get("metadata", {}).get("loom2.gradetrack") or "null")
            track = meta if any(t["id"] == meta for t in seq["video_tracks"]) else None
            if track is not None:
                have = next((x for x in next(t for t in seq["video_tracks"] if t["id"] == track)["items"]
                             if its.get(str(x["item"]), {}).get("metadata", {}).get("loom2.grade") == key), None)
                if have is not None:
                    return {"clip": have["id"], "made": False, "shots": hi - lo + 1}
            else:
                track = int(self.fc.batch([{"id": "sequence.addTracks", "params": {"video": 1, "audio": 0}}])[0]["video"][0])
                self.fc.batch([{"id": "timeline.setTrack", "params": {"track": track, "name": GRADE_TRACK}},
                               {"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.gradetrack": json.dumps(track)}}}])
            item = int(self.fc.batch([{"id": "file.newAdjustmentLayer", "params": {"seconds": (end - start) / TICK}}])[0]["item"])
            placed = self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.grade": key}}},
                                    {"id": "timeline.place", "params": {"item": item, "track": track, "time": start, "duration": end - start, "insert": False, "audio": False}}])
            new = int(placed[1]["clips"][0])
            self.fc.batch([{"id": "clip.rename", "params": {"clip": new, "name": f"Grade · {name}" if place else "Grade"}}])   # as shot until a preset, a look or a value
            self._markers(p)
            return {"clip": new, "made": True, "shots": hi - lo + 1}
        return self.changing(tl, run)

    def grade_own(self, tl: Timeline, clip: int) -> dict:
        """RC2f (proto01_animate 31 §3b): *Make its grade independent* — a V1 shot leaves its scene's grade: the scene's adjustment layer is
        cut at the shot's edges (FilmCraft's razor) and the piece over it lifted, and the shot gets the scene's Lumetri as its own (copied
        whole — look, values, wheels — by FilmCraft's paste attributes, its own Lumetri replaced). The rest of the scene keeps its grade."""
        def run(p: Path) -> dict:
            doc = read(p)
            seq_id, _, seq = sequence(doc)
            its = items(doc)
            v1 = seq["video_tracks"][0]["items"] if seq["video_tracks"] else []
            ti = next((x for x in v1 if x["id"] == clip), None)
            if ti is None:
                raise CutError("a grade is made independent on one of V1's shots")
            start, end = ti["start"], ti["start"] + ti["duration"]
            meta = json.loads(its[str(seq_id)].get("metadata", {}).get("loom2.gradetrack") or "null")
            track = next((t for t in seq["video_tracks"] if t["id"] == meta), None)
            layer = next((x for x in (track or {}).get("items", []) if x["start"] < end and x["start"] + x["duration"] > start
                          and its.get(str(x["item"]), {}).get("metadata", {}).get("loom2.grade")), None)
            if track is None or layer is None:
                raise CutError("the shot is under no scene grade — its grade is its own already")
            mine = [i for i, e in enumerate(ti.get("effects") or []) if e.get("effect") == "lumetri"]
            steps: list[dict] = [{"id": "timeline.select", "params": {"clips": [layer["id"]]}}, {"id": "edit.copy", "params": {}}]
            steps += [{"id": "effects.remove", "params": {"clip": clip, "index": k}} for k in reversed(mine)]
            steps.append({"id": "edit.pasteAttributes", "params": {"clips": [clip], "motion": False, "opacity": False, "timeRemapping": False, "volume": False,
                                                                    "channelVolume": False, "panner": False, "effects": ["lumetri"], "scaleTimes": False}})
            for at in (start, end):
                if layer["start"] < at < layer["start"] + layer["duration"]:
                    steps.append({"id": "timeline.razor", "params": {"time": at, "track": track["id"]}})
            self.fc.batch(steps)
            self.fc.save()                                        # the piece over the shot is found in the project as it stands
            _, _, seq = sequence(read(p))
            t2 = next(t for t in seq["video_tracks"] if t["id"] == track["id"])
            piece = next((x for x in t2["items"] if x["start"] == max(start, layer["start"])), None)
            if piece is not None:
                self.fc.batch([{"id": "edit.clear", "params": {"clips": [piece["id"]]}}])
            self._markers(p)
            return {"clip": clip, "left": layer["id"]}
        return self.changing(tl, run)

    # ---- AU4: a track's chain of VST3 effects and its print ------------------------------------------------------------------------
    def _set_chains(self, seq_id: int, ch: dict[int, list[dict]]) -> None:
        self.fc.batch([{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.chains": json.dumps({str(k): v for k, v in ch.items() if v})}}}])

    def fx(self, tl: Timeline, track: int, op: str, plugin: dict | None = None, fx: str | None = None, to: int | None = None,
           bypass: bool | None = None) -> dict:
        """The audio track's chain changed: `add` an effect (`plugin`: bundle, uid, name, vendor; at `to`, else last), `remove`, `move` to
        `to`, `bypass` on or off — one change of the cut (undoable)."""
        def run(p: Path) -> dict:
            doc = read(p)
            self._audio_track(doc, track)
            seq_id = sequence(doc)[0]
            ch = chains(doc)
            chain = ch.get(track, [])
            if op == "add":
                if not plugin or not plugin.get("bundle"):
                    raise CutError("adding an effect needs its bundle and class")
                e = {"id": new_id("fx"), "bundle": plugin["bundle"], "uid": plugin.get("uid") or "", "name": plugin.get("name") or Path(plugin["bundle"]).stem,
                     "vendor": plugin.get("vendor") or "", "bypass": False, "state": None}
                chain.insert(len(chain) if to is None else max(0, min(int(to), len(chain))), e)
            else:
                k = next((i for i, e in enumerate(chain) if e["id"] == fx), None)
                if k is None:
                    raise CutError(f"the track has no effect {fx}")
                if op == "remove":
                    chain.pop(k)
                elif op == "move":
                    e = chain.pop(k)
                    chain.insert(max(0, min(int(to or 0), len(chain))), e)
                elif op == "bypass":
                    chain[k]["bypass"] = bool(bypass)
                else:
                    raise CutError(f"`{op}` is not a chain change (add, remove, move, bypass)")
            ch[track] = chain
            self._set_chains(seq_id, ch)
            self.fc.save()
            return {"track": track, "chain": chain}
        return self.changing(tl, run)

    def fx_editor(self, tl: Timeline, track: int, fx: str) -> dict:
        """The effect's own editor (loom2's host, a window); when the author closes it, its state is a new file of the cut's (one change,
        undoable). No time limit and no base revision: the cut may change meanwhile."""
        if self.host is None:
            raise CutError("the effects need loom2's VST3 host (scripts/build_vsthost.py)")
        p = self.path(tl.id)
        doc = read(p)
        t = self._audio_track(doc, track)
        e = next((x for x in chains(doc).get(track, []) if x["id"] == fx), None)
        if e is None:
            raise CutError(f"the track has no effect {fx}")
        folder = p.parent / "fx"
        n = 1 + max((int(f.stem.rsplit("-", 1)[-1]) for f in folder.glob(f"{fx}-*.vststate") if f.stem.rsplit("-", 1)[-1].isdigit()), default=0)
        out = folder / f"{fx}-{n}.vststate"
        self.host.editor(e["bundle"], e.get("uid") or "", p.parent / e["state"] if e.get("state") else None, out,
                         f"{e['name']} — {t.get('name', '')} · {tl.name} (loom2)")
        rel = out.relative_to(p.parent).as_posix()

        def run(p: Path) -> dict:
            doc = read(p)
            ch = chains(doc)
            for x in ch.get(track, []):
                if x["id"] == fx:
                    x["state"] = rel
            self._set_chains(sequence(doc)[0], ch)
            self.fc.save()
            return {"track": track, "fx": fx, "state": rel}
        return self.changing(tl, run)

    @_held
    def sync_prints(self, tl: Timeline) -> int:
        """Print every audio track with an effect on whose print is not current; take away the prints of tracks with none (or gone), their
        source back to the Mix; keep each companion's width, volume, pan and mute the source's. Returns the tracks printed. Not a change of
        the cut's (a print follows from it): no snapshot, the revision as it is."""
        p = self.path(tl.id)
        if not tl.file or not p.is_file():
            return 0
        self.fc.open(p)
        doc = read(p)
        seq_id, _, seq = sequence(doc)
        ch, pr = chains(doc), prints(doc)
        by_id = {t["id"]: t for t in seq["audio_tracks"]}
        steps: list[dict] = []
        for src in list(pr):
            if src not in by_id or not active(ch.get(src, [])):
                if pr[src]["track"] in by_id:
                    steps.append({"id": "sequence.deleteTrack", "params": {"track": pr[src]["track"]}})
                if src in by_id:
                    steps.append({"id": "mixer.setStrip", "params": {"strip": src, "output": None}})
                del pr[src]
        companions = {v["track"] for v in pr.values()}
        todo = [t for t in seq["audio_tracks"] if t["id"] not in companions and active(ch.get(t["id"], []))]
        if not steps and not todo and not pr:
            return 0
        if steps:
            self.fc.batch(steps)
        printed = 0
        for t in todo:
            chain = ch[t["id"]]
            key = print_key(doc, t, chain, companions)
            cur = pr.get(t["id"]) or {}
            if cur.get("key") == key and cur.get("file") and Path(cur["file"]).is_file() and cur.get("track") in by_id:
                continue
            if self.host is None or not self.host.available():
                raise CutError("a track's effects print through loom2's VST3 host, which is not built here (scripts/build_vsthost.py)")
            wav = self._print(p, tl, seq, t, chain, key, companions)
            pr[t["id"]] = self._place_print(p, t, wav, key, cur.get("track") if cur.get("track") in by_id else None)
            companions = {v["track"] for v in pr.values()}
            if cur.get("file") and cur["file"] != str(wav):
                Path(cur["file"]).unlink(missing_ok=True)
            printed += 1
        self.fc.batch([{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.prints": json.dumps({str(k): v for k, v in pr.items()})}}}])
        self._mirror_prints(p)
        self.fc.save()
        return printed

    def _bus(self, seq: dict) -> int:
        """The muted submix printed tracks play into (made once)."""
        bus = next((s["id"] for s in seq.get("submix_tracks", []) if s.get("name") == PRINT_BUS), None)
        if bus is None:
            bus = int(self.fc.batch([{"id": "mixer.addSubmix", "params": {"name": PRINT_BUS}}])[0]["id"])
        self.fc.batch([{"id": "mixer.setStrip", "params": {"strip": bus, "muted": True}}])
        return bus

    def _print(self, p: Path, tl: Timeline, seq: dict, t: dict, chain: list[dict], key: str, companions: set[int]) -> Path:
        """The track's sound alone at unity — FilmCraft's export in a process of its own on the saved project (the other tracks muted, the
        track's strip neutral, back to the Mix) — then its gain and chain by loom2's host. Returns the print's WAV."""
        import subprocess
        import tempfile
        from .filmcraft import export_argv
        self.fc.save()
        out = p.parent / "prints" / f"{t['id']}-{key[:12]}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
            src = Path(tmp) / "source.wav"
            steps = [{"id": "prefs.set", "params": {"values": prefs(tl.fps)}}]
            steps += [{"id": "mixer.setStrip", "params": {"strip": x["id"], "muted": True}} for x in seq["audio_tracks"] if x["id"] != t["id"]]
            steps += [{"id": "mixer.setStrip", "params": {"strip": t["id"], "muted": False, "output": None}}, *strip_steps(t, TrackStrip())]
            steps.append({"id": "file.exportMedia", "params": {"path": str(src), "format": "wav", "wait": True, "range": "custom", "startSeconds": 0,
                                                              "endSeconds": max(1.0 / tl.fps, print_span(seq, t, companions))}})
            script = Path(tmp) / "print.jsonl"
            script.write_text("".join(json.dumps(s) + "\n" for s in steps), encoding="utf-8")
            r = self._export(p, script, "render the track's sound for its print")
            if r.returncode != 0 or not src.is_file():
                raise CutError(f"FilmCraft did not render the track's sound for its print: {(r.stdout + r.stderr).strip().splitlines()[-1:] or r.returncode}")
            fx = [{"bundle": e["bundle"], "uid": e.get("uid") or "", "state": p.parent / e["state"] if e.get("state") else None} for e in active(chain)]
            self.host.render(fx, src, out, gain_db=strip_of(t).gain_db)
        return out

    def _place_print(self, p: Path, t: dict, wav: Path, key: str, companion: int | None) -> dict:
        """The print on its companion track (made once, after the cut's tracks), its old print gone, the source into the muted bus."""
        self.fc.save()
        doc = read(p)
        _, _, seq = sequence(doc)
        if companion is None:
            companion = int(self.fc.batch([{"id": "sequence.addTracks", "params": {"video": 0, "audio": 1}}])[0]["audio"][0])
            self.fc.batch([{"id": "timeline.setTrack", "params": {"track": companion, "name": f"{t.get('name', '')} · print"}}])
        else:
            old = next((x for x in seq["audio_tracks"] if x["id"] == companion), {"items": []})
            if old["items"]:
                self.fc.batch([{"id": "edit.clear", "params": {"clips": [ti["id"] for ti in old["items"]]}}])
            gone = [int(k) for k, it in items(doc).items() if it.get("metadata", {}).get("loom2.print") == str(t["id"])]
            if gone:
                self.fc.batch([{"id": "project.delete", "params": {"items": gone}}])
        item = int(self.fc.batch([{"id": "file.import", "params": {"paths": [str(wav)]}}])[0]["items"][0])
        self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.print": str(t["id"])}}},
                       {"id": "timeline.place", "params": {"item": item, "track": companion, "time": 0, "insert": False, "video": False}},
                       {"id": "mixer.setStrip", "params": {"strip": t["id"], "output": self._bus(seq)}}])
        return {"track": companion, "key": key, "file": str(wav)}

    def _mirror_prints(self, p: Path) -> None:
        """Each companion carries its source's width, volume and pan (its gain is in the print) and its mute."""
        self.fc.save()
        doc = read(p)
        _, _, seq = sequence(doc)
        by_id = {t["id"]: t for t in seq["audio_tracks"]}
        steps: list[dict] = []
        for src, v in prints(doc).items():
            s, c = by_id.get(src), by_id.get(v["track"])
            if s is None or c is None:
                continue
            want = strip_of(s)
            steps += strip_steps(c, TrackStrip.model_construct(gain_db=0.0, volume_db=want.volume_db, pan=want.pan, width=want.width))
            steps.append({"id": "mixer.setStrip", "params": {"strip": c["id"], "muted": bool(s.get("muted"))}})
        if steps:
            self.fc.batch(steps)

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
        r = self.fc.batch([{"id": "timeline.place", "params": {"item": item, "track": tr.id, "time": ticks(frame, tl.fps), "insert": bool(insert), **av}}])
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
        CE5: the author's own markers (any kind but Chapter) are kept — FilmCraft clears markers all at once, so they are added back."""
        self.fc.save()
        if self.name_of is None:
            return
        doc = read(p)
        cut = tracks(doc)
        steps: list[dict] = [{"id": "markers.clearAll", "params": {"target": "program"}}]
        for i, start, _ in runs(cut):
            name = self.name_of(_as_clip(i))
            if name:
                steps.append({"id": "markers.addChapter", "params": {"time": ticks(start, cut.fps), "name": name}})
        steps += self._readd(sequence(doc)[2].get("markers") or [])
        self.fc.batch(steps)
        self.fc.save()

    @staticmethod
    def _readd(markers: list[dict], skip: int | None = None) -> list[dict]:
        """The author's markers (not loom2's chapters) as the commands that put them back."""
        out = []
        for m in markers:
            if m.get("kind") == "Chapter" or m.get("id") == skip:
                continue
            frames = {"durationFrames": round(m["duration"] * 24 / TICK)} if m.get("duration") else {}
            out.append({"id": "markers.add", "params": {"target": "program", "time": m["start"], "name": m.get("name", ""), "comment": m.get("comment", ""),
                                                        **({"color": m["color"]} if m.get("color") else {}), **frames}})
        return out

    def _remove_marker(self, doc: dict, mid: int) -> dict:
        """An author's marker away: every marker cleared and the others put back (the chapters come back with `_markers`)."""
        marks = sequence(doc)[2].get("markers") or []
        if not any(m.get("id") == mid for m in marks):
            raise CutError(f"the cut has no marker {mid}")
        self.fc.batch([{"id": "markers.clearAll", "params": {"target": "program"}}, *self._readd(marks, skip=mid)])
        return {"removed": mid}

    # ---- CE5: captions from the lines --------------------------------------------------------------------------------------------
    def captions_from_lines(self, tl: Timeline, lines_of: Callable[[TimelineClip], list[str]]) -> dict:
        """The cut's caption track from the Dialogue lines, timed as the SRT lays them (a voiced line where its clip sits on the audio
        tracks): the track loom2 made before is replaced (the author's edits on it go — the client asks first), another caption track
        is left alone. One change of the cut."""
        def run(p: Path) -> dict:
            doc = read(p)
            seq_id, seq_item, seq = sequence(doc)
            cut = tracks(doc)
            cues = line_cues(cut, lines_of)
            mine = json.loads(seq_item.get("metadata", {}).get("loom2.captiontrack") or "null")
            if any(ct["id"] == mine for ct in seq.get("caption_tracks") or []):
                self.fc.batch([{"id": "captions.deleteTrack", "params": {"track": mine}}])
            track = int(self.fc.batch([{"id": "captions.newTrack", "params": {"format": "Subtitle", "name": CAPTION_TRACK, "language": "en"}}])[0]["track"])
            steps: list[dict] = [{"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.captiontrack": json.dumps(track)}}},
                                 {"id": "captions.setStyle", "params": {"track": track, **CAPTION_STYLE}}]
            steps += [{"id": "captions.add", "params": {"track": track, "text": text, "seconds": round(a / cut.fps, 4),
                                                        "durationSeconds": round(max(1, b - a) / cut.fps, 4)}} for a, b, text in cues]
            self.fc.batch(steps)
            self._markers(p)
            return {"track": track, "captions": len(cues)}
        return self.changing(tl, run)

    @_held
    def frame(self, tl: Timeline, seconds: float, side: int) -> bytes:
        self._open(tl, change=False)
        return self.fc.frame(seconds, side)

    def _export(self, p: Path, script: Path, what: str):
        """V40: FilmCraft's export process (a script against the project) with its timeout — a timeout is a `CutError` (the route's 422,
        with the seconds), not a `TimeoutExpired` the routes never mapped (a 500)."""
        import subprocess
        from .filmcraft import export_argv
        try:
            return subprocess.run(export_argv(self.fc.settings, self.fc.app, p, script), capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=self.fc.settings.timeout_s, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise CutError(f"FilmCraft did not {what} within {self.fc.settings.timeout_s} s — the export was stopped")

    @_held
    def mix(self, tl: Timeline, loudness: float | None) -> Path:
        """CE3: the cut's sound as FilmCraft mixes it — a WAV of every audio track (gain, fades, ducking, the tracks' volume), at the movie's
        loudness — kept per revision and loudness in `timelines/<id>/mix/` (the older ones go): what the page plays with the picture.
        V39: the loudness is in the file's name — a changed target used to be served the old WAV."""
        out = self.path(tl.id).parent / "mix" / mix_name(tl.revision, loudness)
        if out.is_file():
            return out
        self._open(tl, change=False)
        self.sync_prints(tl)                                # AU4: a track with effects is heard through its print
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(out.stem + ".part.wav")
        self.fc.command("file.exportMedia", {"path": str(part), "format": "wav", "wait": True, **({"loudnessLufs": loudness} if loudness is not None else {})})
        part.replace(out)
        for old in out.parent.glob("*.wav"):
            if old != out:
                old.unlink(missing_ok=True)
        return out

    @_held
    def interchange(self, tl: Timeline, fmt: str, out: Path) -> str:
        """FilmCraft's own FCPXML or EDL of the cut (everything the project holds), written to `out`. AU4: the prints stand for their
        sources — a process of its own deletes the printed sources before it exports (the project untouched)."""
        import subprocess
        import tempfile
        from .filmcraft import export_argv
        p = self._open(tl, change=False)
        self.sync_prints(tl)
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(out.name + ".part")
        printed = prints(read(p))
        if not printed:
            self.fc.command("file.exportInterchange", {"format": fmt, "path": str(part)})
        else:
            with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
                steps = [{"id": "prefs.set", "params": {"values": prefs(tl.fps)}}]
                steps += [{"id": "sequence.deleteTrack", "params": {"track": src}} for src in printed]
                steps.append({"id": "file.exportInterchange", "params": {"format": fmt, "path": str(part)}})
                script = Path(tmp) / "interchange.jsonl"
                script.write_text("".join(json.dumps(s) + "\n" for s in steps), encoding="utf-8")
                r = self._export(p, script, "export the cut with its prints")
                if r.returncode != 0 or not part.is_file():
                    raise CutError(f"FilmCraft did not export the cut with its prints: {(r.stdout + r.stderr).strip().splitlines()[-1:] or r.returncode}")
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

    @_held
    def sync_lines(self, tl: Timeline) -> int:
        """Before an export or the movie: a voiced line not on A1 yet is placed where the exports lay it (its shot's lines evenly across the
        shot's run on V1, pushed past a clip already there); a line voiced anew plays its new audio in place; a line the author moved stays.
        One change (one undo step) when anything moved; none otherwise. Returns how many lines changed. CE3: the lines are the author's — a line
        on any audio track counts, and a line the cut placed before that is gone now was lifted by the author and stays out."""
        if self.audio_of is None:
            return 0
        if self._line_steps_now(read(self.path(tl.id))) is None:
            return 0

        def run(p: Path) -> int:
            steps = self._line_steps_now(read(p)) or []
            self.fc.batch(steps)
            self._markers(p)
            return len(steps)
        return self.changing(tl, run)

    def _line_steps_now(self, doc: dict, forget: set[str] | frozenset[str] = frozenset()) -> list[dict] | None:
        """sync_lines' steps on the cut as it stands (None: nothing to do). `forget`: lines the cut placed and took off with their shot
        (U7b) — placed again, not taken for the author's. U7b (F39): a shot's missing lines stay inside its run when they fit there — each
        after the one before it, and early enough for the rest; a line longer than the run is pushed past what is on A1 as before."""
        cut = tracks(doc)
        seq_id = cut.sequence
        a1 = cut.audio[0].items if cut.audio else []
        have = {(i.node_id, i.line): i for t in cut.audio for i in t.items if i.kind == "line"}
        gone = placed_lines(doc) - set(forget)
        missing: list[tuple[float, dict]] = []
        revoiced: list[tuple[CutItem, dict]] = []
        for first, start, end in runs(cut):
            cues = self.audio_of(_as_clip(first)) or []                             # type: ignore[misc]
            lay = [(start + a0, cue) for (a0, _), cue in zip(line_spans(round(end - start), len(cues)), cues) if cue and cue.get("path")]
            todo = [(t, cue) for t, cue in lay if (cue.get("node"), cue.get("line")) not in have and f"{cue.get('node')}:{cue.get('line')}" not in gone]
            revoiced += [(have[(cue.get("node"), cue.get("line"))], cue) for _, cue in lay
                         if (cue.get("node"), cue.get("line")) in have and have[(cue.get("node"), cue.get("line"))].asset_id != cue.get("asset")]
            lens = [max(1.0, round(float(cue["duration_s"]) * cut.fps)) for _, cue in todo]
            prev = start
            for k, (t, cue) in enumerate(todo):
                rest = sum(lens[k:])
                if end - rest >= start:                                             # F39: early enough for the rest to fit before the run ends
                    t = min(t, end - rest)
                t = max(t, prev)                                                    # and after the line before it
                missing.append((t, cue))
                prev = t + lens[k]
        if not missing and not revoiced:
            return None
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
        return steps

    @staticmethod
    def to_conform(doc: dict) -> list[tuple[str, int, dict]]:
        """U7c: the cut's 16 fps takes that play their proxies — (clip, project item, its links)."""
        return [(it["metadata"]["loom2.clip"], int(k), it["metadata"]) for k, it in items(doc).items()
                if it.get("metadata", {}).get("loom2.media") == "proxy" and it["metadata"].get("loom2.fps") == "16" and it["metadata"].get("loom2.clip")]

    def conform(self, tl: Timeline, ready: dict[str, list[Path]]) -> list[str]:
        """U7c (05 §1 fix 2): each 16 fps take whose RIFE frames at 24 are `ready` plays them in place of its proxy — the frames imported
        once (an image sequence at 24 with the take's links), its uses swapped (`clip.replaceFromBin`, the source in kept), the proxy's
        item gone — as one change (one undo step). Returns the clips swapped."""
        if not any(cid in ready for cid, _, _ in self.to_conform(read(self.path(tl.id)))):
            return []

        def run(p: Path) -> list[str]:
            doc = read(p)
            _, _, seq = sequence(doc)
            v1 = seq["video_tracks"][0]["items"] if seq["video_tracks"] else []
            done: list[str] = []
            for cid, k, meta in self.to_conform(doc):
                if cid not in ready:
                    continue
                r = self.fc.batch([{"id": "prefs.set", "params": {"values": prefs(24)}},              # RIFE numbers from 1: the first it wrote
                                   {"id": "file.import", "params": {"paths": [str(ready[cid][0])], "imageSequence": True}}])
                new = int(r[1]["items"][0])
                uses = [ti for ti in v1 if ti["item"] == k]
                steps = [{"id": "metadata.set", "params": {"item": new, "fields": {**meta, "loom2.media": "conform24"}}}]
                if uses:
                    steps.append({"id": "clip.replaceFromBin", "params": {"clips": [ti["id"] for ti in uses], "item": new, "keepSourceIn": True}})
                    steps += [{"id": "clip.rename", "params": {"clip": ti["id"], "name": ti["name"]}} for ti in uses if ti.get("name")]   # F40: still its shot's
                steps.append({"id": "project.delete", "params": {"items": [k]}})
                self.fc.batch(steps)
                done.append(cid)
            self._markers(p)
            return done
        return self.changing(tl, run)

    # ---- U7b (D157, proto01_UI2 05 §1, 06 §3; G14): Assemble from the Flow, placing only what changed ---------------------------
    def assemble(self, tl: Timeline, want: list[AssembleShot], records: dict[str, ClipRecord], route: dict[str, str] | None) -> AssembleReport:
        """The route's shots onto V1 as one change (one undo step), keeping what the author did to what stays:

        - a shot already on V1 in the route's order is kept with its trims, speed, grade and dissolves; with a newer final it plays it in
          place (its start and length kept, as *Update*);
        - a shot no longer on the route (or out of the route's order) goes with its lines, the later clips closing up on every track;
        - a shot not on V1 yet goes in after the one before it, the later clips moving on every track (an insert), at its final's length;
        - a shot whose lines run longer than it is held for them when its final has the frames, else it is listed (F39);
        - every shot's clip is named after its shot (F40); the lines not on A1 yet are laid inside their shots; the route is kept.

        A shot without a final is left out, or kept as it is when it is on the cut already. Plain clips (not shots) are never touched."""
        def run(p: Path) -> AssembleReport:
            rep = AssembleReport()
            fps = tl.fps
            cut = tracks(read(p))
            on = [r for r in run_pieces(cut) if r[0].shot_id]
            used: set[int] = set()
            match: list[int | None] = []
            for w in want:                                                  # each shot of the route: its first run on V1 not taken yet
                j = next((k for k, r in enumerate(on) if k not in used and r[0].shot_id == w.shot_id), None)
                if j is not None:
                    used.add(j)
                match.append(j)
            keep = _in_order([(i, j) for i, j in enumerate(match) if j is not None])
            kept_runs = {match[i] for i in keep}
            # off: the runs no longer on the route (or out of its order), their lines first (they would stand in the gap's way)
            off = [r for k, r in enumerate(on) if k not in kept_runs]
            forget: set[str] = set()
            if off:
                lines_off = [i for r in off if r[0].node_id for t in cut.audio for i in t.items if i.kind == "line" and i.node_id == r[0].node_id
                             and r[0].start - 0.5 <= i.start < r[-1].start + r[-1].duration - 0.5]
                forget = {f"{i.node_id}:{i.line}" for i in lines_off}
                if lines_off:
                    self.fc.batch([{"id": "edit.clear", "params": {"clips": [i.id for i in lines_off]}}])
                self.fc.batch([{"id": "edit.rippleDelete", "params": {"clips": [i.id for r in off for i in r]}}])
                rep.removed = [(self.name_of(_as_clip(r[0])) if self.name_of else None) or r[0].name or "a shot" for r in off]

            def doc_now() -> dict:
                self.fc.save()
                return read(p)

            def now() -> CutTracks:
                return tracks(doc_now())

            def runs_of(c: CutTracks) -> dict[int, list[CutItem]]:
                return {r[0].id: r for r in run_pieces(c)}

            # kept: a newer final plays in place; a shot without a final stays as it is
            firsts: dict[int, int] = {i: on[match[i]][0].id for i in keep}        # a want → its run's first piece (ids survive the edits)
            for i in sorted(keep):
                w, r = want[i], on[match[i]]                                        # type: ignore[index]
                use = (w.clip_id or "", w.shot_id, w.version, w.node_id or "")
                if not w.clip_id:
                    rep.unfinished.append(w.name)
                elif (r[0].clip_id, r[0].shot_id, r[0].shot_version, r[0].node_id or "") != use:
                    item = self._media_item(doc_now(), tl, use, records[w.clip_id])
                    self.fc.batch([{"id": "clip.replaceFromBin", "params": {"clips": [x.id for x in r], "item": item, "keepSourceIn": True}}])
                    rep.updated.append(w.name)
                else:
                    rep.kept.append(w.name)
            # placed: after the shot before it on the route (or before the next one on the cut, or at V1's end), as an insert
            for i, w in enumerate(want):
                if i in keep:
                    continue
                if not w.clip_id or w.clip_id not in records:
                    rep.missing.append(w.name)
                    continue
                cur = now()
                rs = runs_of(cur)
                before = [firsts[k] for k in range(i - 1, -1, -1) if k in firsts and firsts[k] in rs]
                after = [firsts[k] for k in range(i + 1, len(want)) if k in firsts and firsts[k] in rs]
                if before:
                    last = rs[before[0]][-1]
                    at = last.start + last.duration
                elif after:
                    at = rs[after[0]][0].start
                else:
                    at = max((x.start + x.duration for x in (cur.video[0].items if cur.video else [])), default=0.0)
                rec = records[w.clip_id]
                item = self._media_item(doc_now(), tl, (w.clip_id, w.shot_id, w.version, w.node_id or ""), rec)
                length = max(1, rec.frames * fps // rec.fps)                       # never past its source's end (17 at 16 fps: 25 at 24)
                placed = self.fc.batch([{"id": "timeline.place", "params": {"item": item, "track": "V1", "time": ticks(at, fps), "insert": True, "audio": False,
                                                                          "sourceIn": 0, "duration": ticks(length, fps)}}])
                firsts[i] = int(placed[0]["clips"][0])
                rep.placed.append(w.name)
            # held for its lines (F39), and named after its shot (F40)
            cur = now()
            rs = runs_of(cur)
            steps: list[dict] = []
            for i, w in enumerate(want):
                r = rs.get(firsts.get(i, -1))
                if r is None:
                    continue
                span = r[-1].start + r[-1].duration - r[0].start
                need = round(w.lines_s * fps)
                if w.lines_s > 0 and need > span + 0.5:
                    last = r[-1]
                    rec = records.get(last.clip_id or "")
                    room = (rec.frames / rec.fps * fps - (last.source_in * fps + last.duration * abs(last.speed))) if rec else 0.0
                    if rec and abs(last.speed) == 1.0 and not last.hold and room >= need - span - 0.5:
                        steps.append({"id": "timeline.trim", "params": {"clip": last.id, "edge": "out", "mode": "ripple", "deltaFrames": int(round(need - span))}})
                        rep.held.append(w.name)
                    else:
                        rep.short.append(ShortLines(name=w.name, lines_s=round(w.lines_s, 1), final_s=round(span / fps, 1)))
                for x in r:
                    if w.name and x.name != w.name:
                        steps.append({"id": "clip.rename", "params": {"clip": x.id, "name": w.name}})
                        rep.renamed += 1
            seq_id = cur.sequence
            steps.append({"id": "metadata.set", "params": {"item": seq_id, "fields": {"loom2.route": json.dumps(route) if route is not None else ""}}})
            self.fc.batch(steps)
            if self.audio_of is not None:                                            # the lines not on A1 yet, inside their shots
                line_steps = self._line_steps_now(doc_now(), forget)
                if line_steps:
                    self.fc.batch(line_steps)
            self._markers(p)
            return rep
        return self.changing(tl, run)


def _as_clip(i: CutItem) -> TimelineClip:
    """A take as the story lookups read it (by its clip, shot and node)."""
    return TimelineClip(id=str(i.id), clip_id=i.clip_id or "", **{"in": 0}, out=1, shot_id=i.shot_id, shot_version=i.shot_version, node_id=i.node_id)


def run_pieces(cut: CutTracks) -> list[list[CutItem]]:
    """V1's takes as shots: consecutive pieces of the same node (a take razored, or held) are one run — its pieces in order."""
    out: list[list[CutItem]] = []
    for i in (cut.video[0].items if cut.video else []):
        if i.kind != "take":
            continue
        last = out[-1][-1] if out else None
        if last is not None and i.node_id and last.node_id == i.node_id and abs(last.start + last.duration - i.start) < 0.5:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def runs(cut: CutTracks) -> list[tuple[CutItem, float, float]]:
    """V1's runs (`run_pieces`) as (its first piece, start, end)."""
    return [(r[0], r[0].start, r[-1].start + r[-1].duration) for r in run_pieces(cut)]


def _in_order(pairs: list[tuple[int, int]]) -> set[int]:
    """U7b: of (a shot's place on the route, its run's place on V1), the most that are in the same order on both — the route's places
    kept (a longest increasing run of the V1 places); the rest move."""
    prev: dict[int, int | None] = {}
    tails: list[int] = []                                           # tails[k]: the pair ending the lowest run of length k + 1 so far
    for n, (_, j) in enumerate(pairs):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if pairs[tails[mid]][1] < j:
                lo = mid + 1
            else:
                hi = mid
        prev[n] = tails[lo - 1] if lo else None
        if lo == len(tails):
            tails.append(n)
        else:
            tails[lo] = n
    out: set[int] = set()
    k = tails[-1] if tails else None
    while k is not None:
        out.add(pairs[k][0])
        k = prev[k]
    return out


def line_cues(cut: CutTracks, lines_of: Callable[[TimelineClip], list[str]]) -> list[tuple[float, float, str]]:
    """Each shot's lines across where its run sits on V1 (laid evenly, as the lane's SRT), a voiced line where its clip sits on the audio
    tracks — (start, end, text) in frames, in time order."""
    voiced = {(i.node_id, i.line): (i.start, i.start + i.duration) for t in cut.audio for i in t.items if i.kind == "line"}
    cues: list[tuple[float, float, str]] = []
    for i, start, end in runs(cut):
        if not i.node_id:
            continue
        said = [(k, x.strip()) for k, x in enumerate(lines_of(_as_clip(i))) if x and x.strip()]
        for (a0, b0), (k, text) in zip(line_spans(round(end - start), len(said)), said):
            a, b = voiced.get((i.node_id, k), (start + a0, start + b0))
            cues.append((a, b, text))
    return sorted(cues, key=lambda x: x[0])


def srt_of(cues: list[tuple[float, float, str]], fps: int) -> str:
    from .timelines import srt_tc
    out: list[str] = []
    for n, (a, b, text) in enumerate(cues, 1):
        out += [str(n), f"{srt_tc(round(a), fps)} --> {srt_tc(max(round(a) + 1, round(b)), fps)}", text, ""]
    return "\n".join(out)


def cut_srt(cut: CutTracks, lines_of: Callable[[TimelineClip], list[str]]) -> str:
    """CE2: the SubRip of a FilmCraft cut — its lines (`line_cues`). CE5: the caption track's captions when the cut has them (the
    author's edits are the subtitles)."""
    caps = next((ct for ct in cut.captions if ct.enabled and ct.captions), None)
    if caps is not None:
        return srt_of([(c.start, c.start + c.duration, c.text) for c in caps.captions], cut.fps)
    return srt_of(line_cues(cut, lines_of), cut.fps)


def cut_markers(cut: CutTracks, name_of: Callable[[TimelineClip], str | None]) -> str:
    """CE2: the markers sidecar of a FilmCraft cut — a line per named shot (a run of V1) at its start (`HH:MM:SS:FF<TAB>name`); CE5: the
    author's markers too (`name — comment`), all in time order."""
    from .timelines import tc
    rows = [(start, name) for i, start, _ in runs(cut) if (name := name_of(_as_clip(i)))]
    rows += [(m.frame, m.name + (f" — {m.comment}" if m.comment else "")) for m in cut.markers if m.kind != "Chapter"]
    out = [f"{tc(round(a), cut.fps)}\t{n}" for a, n in sorted(rows, key=lambda r: r[0])]
    return "\n".join(out) + ("\n" if out else "")


def _use(c: TimelineClip) -> tuple[str, str, str, str]:
    """A take as the lane uses it: the clip and the stamps of the shot it stands for (none for a plain clip)."""
    return (c.clip_id, c.shot_id or "", c.shot_version or "", c.node_id or "")


def _use_of(meta: dict) -> tuple[str, str, str, str]:
    return (meta["loom2.clip"], meta.get("loom2.shot", ""), meta.get("loom2.version", ""), meta.get("loom2.node", ""))


def clip_records(ws: Workspace) -> dict[str, ClipRecord]:
    return {c.id: c for c in ClipStore(ws).list()}

