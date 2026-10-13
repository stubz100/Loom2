"""Sequences (P17 / D83; 14 R157, loom P5): one lane of clips at the project fps, kept as a document `timelines/<id>.json`.

Integer frame ticks at the lane's fps; a clip names a Catalogue clip (`clips/<id>`) and the source frames it uses, `[in, out)`, in
that clip's own frames; `overlaps[i]` is how many ticks clip i dissolves over clip i − 1 (0 = a cut). A clip at another frame rate
(Wan at 16 fps on a 24 fps lane) takes `round(len × lane_fps / clip_fps)` ticks and is scrubbed by nearest frame — no frames are made
here (D27: the RIFE conform at export is post-MVP, Q14); the exports carry each clip's native rate for Resolve to conform.

The TypeScript model (frontend/src/suites/animate/lane.ts) does the same maths for the live view; the two are parity-tested on the
EDL text. Writes go through fsio (temp → fsync → replace); `revision` guards a PUT like a document's stack (409 on a stale base).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from .clips import ClipRecord
from .fsio import atomic_write_json, atomic_write_text, new_id, read_json, slugify, utc_now
from .workspace import Workspace

TIMELINE_SCHEMA_VERSION = 1


class StaleTimeline(ValueError):
    """A PUT based on an older revision than the document's (the API answers 409; the client reloads and re-applies)."""


class TimelineClip(BaseModel):
    model_config = ConfigDict(populate_by_name=True, json_schema_serialization_defaults_required=True)
    id: str
    clip_id: str                                  # clips/<id> (ClipRecord)
    in_: int = Field(0, alias="in", ge=0)         # source frames used: [in, out)
    out: int = Field(..., gt=0)
    fps: int | None = None                        # the clip's own rate when it differs from the lane's (stamped on add from the ClipRecord)
    shot_id: str | None = None                    # 17 §3e (D85): the Story shot this clip is (its version and owner node) — the Shots bin stamps them
    shot_version: str | None = None
    node_id: str | None = None

    @property
    def length(self) -> int:
        return self.out - self.in_


class Timeline(BaseModel):
    model_config = ConfigDict(populate_by_name=True, json_schema_serialization_defaults_required=True)
    schema_version: int = TIMELINE_SCHEMA_VERSION
    id: str
    name: str = "Sequence"
    fps: int = 24
    w: int = 1920
    h: int = 1080
    clips: list[TimelineClip] = Field(default_factory=list)
    overlaps: list[int] = Field(default_factory=list)      # overlaps[i] for clip i (overlaps[0] is 0)
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


# ---- the lane maths (mirrors lane.ts) ----------------------------------------------------------------------------------------------
def ticks(tl: Timeline, c: TimelineClip) -> int:
    """Lane ticks a clip occupies: its source frames, scaled when its own rate differs from the lane's."""
    rate = c.fps or tl.fps
    return max(1, round(c.length * tl.fps / rate))


def starts(tl: Timeline) -> list[int]:
    out: list[int] = []
    t = 0
    for i, c in enumerate(tl.clips):
        if i > 0:
            t -= tl.overlaps[i] if i < len(tl.overlaps) else 0
        out.append(t)
        t += ticks(tl, c)
    return out


def duration(tl: Timeline) -> int:
    if not tl.clips:
        return 0
    s = starts(tl)
    return s[-1] + ticks(tl, tl.clips[-1])


def at(tl: Timeline, f: int, s: list[int] | None = None) -> tuple[tuple[int, int], tuple[int, int] | None, float] | None:
    """What the lane shows at tick f: ((clip index, source frame), the incoming clip mid-dissolve or None, its weight) — the mirror of
    lane.ts `at()`; the source frame is the nearest when the clip's rate differs from the lane's."""
    s = s if s is not None else starts(tl)
    if f < 0 or f >= duration(tl) or not tl.clips:
        return None
    lo, hi = 0, len(s) - 1
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if s[mid] <= f:
            lo = mid
        else:
            hi = mid - 1
    i = lo

    def shown(k: int) -> tuple[int, int]:
        c = tl.clips[k]
        local = c.in_ + int((f - s[k]) * (c.fps or tl.fps) / tl.fps)
        return k, min(c.out - 1, local)

    if i > 0 and f < s[i - 1] + ticks(tl, tl.clips[i - 1]):
        ov = tl.overlaps[i]
        return shown(i - 1), shown(i), (f - s[i] + 0.5) / ov
    return shown(i), None, 0.0


def check(tl: Timeline, clip_frames: dict[str, int] | None = None) -> None:
    """The invariants a saved document keeps: one overlap per clip (the first 0), a dissolve shorter than both clips, in < out, and —
    when the clips are known — out within the clip's frames."""
    if len(tl.overlaps) != len(tl.clips):
        raise ValueError(f"overlaps ({len(tl.overlaps)}) must match the clips ({len(tl.clips)})")
    if tl.overlaps and tl.overlaps[0] != 0:
        raise ValueError("the first clip has nothing to dissolve from (overlaps[0] must be 0)")
    for i, c in enumerate(tl.clips):
        if c.out <= c.in_:
            raise ValueError(f"clip {c.id}: out ({c.out}) must be after in ({c.in_})")
        if clip_frames is not None:
            n = clip_frames.get(c.clip_id)
            if n is None:
                raise ValueError(f"clip {c.id}: clip {c.clip_id} is not in the project")
            if c.out > n:
                raise ValueError(f"clip {c.id}: out ({c.out}) is past the clip's {n} frames")
        if i > 0 and tl.overlaps[i] < 0:
            raise ValueError(f"clip {c.id}: a negative overlap")
        if i > 0 and tl.overlaps[i] >= min(ticks(tl, c), ticks(tl, tl.clips[i - 1])):
            raise ValueError(f"clip {c.id}: the dissolve ({tl.overlaps[i]} ticks) must be shorter than both clips")


# ---- exports ------------------------------------------------------------------------------------------------------------------------
def tc(frames: int, fps: int) -> str:
    """HH:MM:SS:FF at an integer fps (non-drop)."""
    f, s = frames % fps, frames // fps
    return f"{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}:{f:02d}"


def reel(clip_id: str) -> str:
    """An 8-character reel name from the clip id (CMX 3600)."""
    return clip_id.removeprefix("clp_")[:8].ljust(8)


def to_edl(tl: Timeline, title: str) -> str:
    """CMX 3600: one event per clip; a dissolve event ("D nnn") where a clip overlaps the previous one. Source times are in the
    clip's own frames at its own rate; record times are lane ticks."""
    s = starts(tl)
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    for i, c in enumerate(tl.clips):
        n = f"{i + 1:03d}"
        rate = c.fps or tl.fps
        ov = tl.overlaps[i] if i > 0 else 0
        rec_in, rec_out = s[i], s[i] + ticks(tl, c)
        if ov > 0:
            prev = tl.clips[i - 1]
            prate = prev.fps or tl.fps
            pov = round(ov * prate / tl.fps)
            lines.append(f"{n}  {reel(prev.clip_id)} V     C        {tc(prev.out - pov, prate)} {tc(prev.out - pov, prate)} {tc(rec_in, tl.fps)} {tc(rec_in, tl.fps)}")
            lines.append(f"{n}  {reel(c.clip_id)} V     D    {ov:03d} {tc(c.in_, rate)} {tc(c.out, rate)} {tc(rec_in, tl.fps)} {tc(rec_out, tl.fps)}")
        else:
            lines.append(f"{n}  {reel(c.clip_id)} V     C        {tc(c.in_, rate)} {tc(c.out, rate)} {tc(rec_in, tl.fps)} {tc(rec_out, tl.fps)}")
        lines.append(f"* FROM CLIP NAME: {c.clip_id}")
        lines.append("")
    return "\n".join(lines)


def srt_tc(frames: int, fps: int) -> str:
    """SubRip time: HH:MM:SS,mmm from lane ticks."""
    ms = round(frames * 1000 / fps)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(tl: Timeline, lines_of: Callable[[TimelineClip], list[str]]) -> str:
    """SubRip (loom R152): each lane clip's node lines laid evenly across the clip's ticks (a dissolve's overlap shortens the first)."""
    s = starts(tl)
    out: list[str] = []
    n = 0
    for i, c in enumerate(tl.clips):
        lines = [x.strip() for x in lines_of(c) if x and x.strip()]
        if not lines:
            continue
        span = ticks(tl, c)
        t0 = s[i]
        per = max(1, span // len(lines))
        for k, text in enumerate(lines):
            a = t0 + k * per
            b = t0 + span if k == len(lines) - 1 else t0 + (k + 1) * per
            n += 1
            out += [str(n), f"{srt_tc(a, tl.fps)} --> {srt_tc(max(a + 1, b), tl.fps)}", text, ""]
    return "\n".join(out)


def to_markers(tl: Timeline, name_of: Callable[[TimelineClip], str | None]) -> str:
    """The sidecar list (loom R158): one line per lane clip with a name — `HH:MM:SS:FF<TAB>name`."""
    s = starts(tl)
    out = []
    for i, c in enumerate(tl.clips):
        name = name_of(c)
        if name:
            out.append(f"{tc(s[i], tl.fps)}\t{name}")
    return "\n".join(out) + ("\n" if out else "")


def _esc(x: str) -> str:
    return x.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def to_fcpxml(tl: Timeline, title: str, media: Callable[[str], tuple[str, str, int, int]], name_of: Callable[[TimelineClip], str | None] | None = None) -> str:
    """FCPXML 1.10: a format per frame rate, one asset per clip (`media(clip_id)` → name, src URL, frames, fps), a spine of
    asset-clips with a cross dissolve where clips overlap; `name_of` gives a chapter marker at a clip's head (loom R158 — Resolve reads them)."""
    def t(fr: int, fps: int) -> str:
        return f"{fr}/{fps}s"
    clip_ids = list(dict.fromkeys(c.clip_id for c in tl.clips))
    infos = {cid: media(cid) for cid in clip_ids}
    rates = sorted({tl.fps, *(info[3] for info in infos.values())})
    formats = [f'    <format id="f{r}" frameDuration="1/{r}s" width="{tl.w}" height="{tl.h}"/>' for r in rates]
    assets = [f'    <asset id="a{k}" name="{_esc(name)}" start="0s" duration="{t(frames, fps)}" hasVideo="1" format="f{fps}">'
              f'<media-rep kind="original-media" src="{_esc(src)}"/></asset>'
              for k, (name, src, frames, fps) in ((clip_ids.index(cid), info) for cid, info in infos.items())]
    s = starts(tl)
    spine: list[str] = []
    for i, c in enumerate(tl.clips):
        name, _, _, fps = infos[c.clip_id]
        k = clip_ids.index(c.clip_id)
        ov = tl.overlaps[i] if i > 0 else 0
        if ov > 0:
            spine.append(f'            <transition name="Cross Dissolve" offset="{t(s[i], tl.fps)}" duration="{t(ov, tl.fps)}"/>')
        marker = name_of(c) if name_of else None
        head = (f'            <asset-clip ref="a{k}" name="{_esc(name)}" offset="{t(s[i], tl.fps)}" start="{t(c.in_, fps)}" '
                f'duration="{t(c.length, fps)}" format="f{fps}" tcFormat="NDF"')
        if marker:
            spine.append(head + ">")
            spine.append(f'                <marker start="{t(c.in_, fps)}" duration="{t(1, fps)}" value="{_esc(marker)}"/>')
            spine.append("            </asset-clip>")
        else:
            spine.append(head + "/>")
    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>', "<!DOCTYPE fcpxml>", '<fcpxml version="1.10">', "  <resources>", *formats, *assets,
        "  </resources>", "  <library>", f'    <event name="{_esc(title)}">', f'      <project name="{_esc(title)}">',
        f'        <sequence format="f{tl.fps}" duration="{t(duration(tl), tl.fps)}" tcStart="0s" tcFormat="NDF">', "          <spine>",
        *spine, "          </spine>", "        </sequence>", "      </project>", "    </event>", "  </library>", "</fcpxml>", "",
    ])


# ---- the store ----------------------------------------------------------------------------------------------------------------------
class TimelineStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.timelines_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, tl_id: str) -> Path:
        return self.dir / f"{tl_id}.json"

    def export_dir(self, tl_id: str) -> Path:
        return self.dir / tl_id

    def get(self, tl_id: str) -> Timeline | None:
        p = self.path(tl_id)
        return Timeline.model_validate(read_json(p)) if p.is_file() else None

    def list(self) -> list[Timeline]:
        out = [Timeline.model_validate(read_json(p)) for p in self.dir.glob("tl_*.json")]
        return sorted(out, key=lambda t: t.updated_at, reverse=True)

    def save(self, tl: Timeline) -> None:
        atomic_write_json(self.path(tl.id), tl.model_dump(by_alias=True))

    def create(self, name: str = "Sequence", fps: int = 24, w: int = 1920, h: int = 1080) -> Timeline:
        tl = Timeline(id=new_id("tl"), name=name.strip() or "Sequence", fps=fps, w=w, h=h)
        self.save(tl)
        return tl

    def put(self, tl_id: str, data: dict[str, Any], clip_frames: dict[str, int] | None = None) -> Timeline:
        """Replace the document from a client body based on `revision` (409 when stale); id, schema and timestamps are the server's."""
        cur = self.get(tl_id)
        if cur is None:
            raise KeyError(tl_id)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleTimeline(f"the sequence is at revision {cur.revision}, the change is based on {base} — reload it first")
        merged = {**cur.model_dump(by_alias=True), **{k: v for k, v in data.items() if k in ("name", "fps", "w", "h", "clips", "overlaps")},
                  "id": tl_id, "schema_version": TIMELINE_SCHEMA_VERSION, "revision": cur.revision + 1, "created_at": cur.created_at, "updated_at": utc_now()}
        tl = Timeline.model_validate(merged)
        check(tl, clip_frames)
        self.save(tl)
        return tl

    def delete(self, tl_id: str) -> bool:
        p = self.path(tl_id)
        if not p.is_file():
            return False
        p.unlink()
        d = self.export_dir(tl_id)
        if d.is_dir():
            for f in d.iterdir():
                f.unlink()
            d.rmdir()
        return True

    def export(self, tl: Timeline, fmt: str, clips: dict[str, ClipRecord], name_of: Callable[[TimelineClip], str | None] | None = None,
               lines_of: Callable[[TimelineClip], list[str]] | None = None) -> tuple[Path, str]:
        """Write the EDL, FCPXML or SRT beside the document (`timelines/<id>/<name>.<ext>`); the FCPXML names each clip's proxy by file URL and
        carries a chapter marker per named clip (`name_of`), written to `markers.txt` beside it too; the SRT takes each clip's lines (`lines_of`)."""
        if fmt == "edl":
            text = to_edl(tl, tl.name)
        elif fmt == "fcpxml":
            def media(cid: str) -> tuple[str, str, int, int]:
                rec = clips[cid]
                src = (self.ws.path / rec.proxy_path).resolve().as_uri() if rec.proxy_path else cid
                return cid, src, rec.frames, int(rec.fps)
            text = to_fcpxml(tl, tl.name, media, name_of)
        elif fmt == "srt":
            text = to_srt(tl, lines_of or (lambda c: []))
        else:
            raise ValueError(f"unknown export format {fmt!r}")
        d = self.export_dir(tl.id)
        d.mkdir(parents=True, exist_ok=True)
        out = d / f"{slugify(tl.name, 'sequence')}.{fmt}"
        atomic_write_text(out, text)
        if fmt == "fcpxml" and name_of:
            atomic_write_text(d / "markers.txt", to_markers(tl, name_of))
        return out, text
