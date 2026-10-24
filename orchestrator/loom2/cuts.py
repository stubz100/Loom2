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
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .clips import ClipRecord, ClipStore
from .filmcraft import TICK, TIMEBASES, FilmCraft, prefs, ticks
from .timelines import Timeline, TimelineClip, duration, line_spans, starts
from .timelines import ticks as lane_ticks
from .workspace import Workspace

CUT_FILE = "cut.fcproj"
FORMAT = "filmcraft.project"


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
    overlaps (a cross dissolve into a clip, in ticks of the lane) and the route the cut was assembled from."""
    its = items(doc)
    _, seq_item, seq = sequence(doc)
    v1 = seq["video_tracks"][0] if seq["video_tracks"] else {"items": [], "transitions": []}
    tis = sorted(v1["items"], key=lambda ti: ti["start"])
    into = {tr["to"]: tr for tr in v1.get("transitions", []) if tr.get("to") is not None and tr.get("from") is not None}
    clips: list[TimelineClip] = []
    overlaps: list[int] = []
    for i, ti in enumerate(tis):
        meta = its.get(str(ti["item"]), {}).get("metadata", {})
        if "loom2.clip" not in meta:
            raise CutError(f"V1's clip {ti['id']} is not a loom2 take (its media has no loom2.clip)")
        clip_fps = int(meta.get("loom2.fps") or fps)
        cut = _frames(ti["start"], fps)
        tr = into.get(ti["id"])
        s_i = _frames(tr["start"], fps) if tr else cut                       # the lane's start: where the dissolve into it begins
        nxt = into.get(tis[i + 1]["id"]) if i + 1 < len(tis) else None
        end = _frames(nxt["start"] + nxt["duration"], fps) if nxt else _frames(ti["start"] + ti["duration"], fps)
        in_ = round((ti["source_in"] / TICK - (cut - s_i) / fps) * clip_fps)
        length = round((end - s_i) * clip_fps / fps)
        clips.append(TimelineClip(id=str(ti["id"]), clip_id=meta["loom2.clip"], **{"in": max(0, in_)}, out=max(0, in_) + max(1, length),
                                  fps=clip_fps if clip_fps != fps else None, shot_id=meta.get("loom2.shot") or None,
                                  shot_version=meta.get("loom2.version") or None, node_id=meta.get("loom2.node") or None))
        overlaps.append(_frames(tr["duration"], fps) if tr and i > 0 else 0)
    route = seq_item.get("metadata", {}).get("loom2.route")
    return clips, overlaps, (json.loads(route) if route else None)


def lines(doc: dict) -> list[dict]:
    """The spoken lines loom2 placed on A1: {track item, start tick, node, line, asset}."""
    its = items(doc)
    _, _, seq = sequence(doc)
    out = []
    for ti in (seq["audio_tracks"][0]["items"] if seq["audio_tracks"] else []):
        meta = its.get(str(ti["item"]), {}).get("metadata", {})
        if "loom2.line" in meta:
            out.append({"clip": ti["id"], "start": ti["start"], "node": meta.get("loom2.node"), "line": int(meta["loom2.line"]), "asset": meta.get("loom2.asset")})
    return out


class Cuts:
    """Writes cuts through the FilmCraft session. `audio_of(clip)` gives a lane clip's spoken lines as story_lookup does (each with the
    file's `path`, its `asset`, `node` and `line`), or None when the cut carries no lines."""

    def __init__(self, ws: Workspace, fc: FilmCraft, audio_of: Callable[[TimelineClip], list[dict | None]] | None = None) -> None:
        self.ws, self.fc, self.audio_of = ws, fc, audio_of

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
        line_steps = self._line_steps(doc, tl, s)
        self.fc.batch(trans + route + line_steps)
        used = set(media.values()) | {st["params"]["item"] for st in line_steps}
        unused = [int(k) for k, it in items(doc).items() if ({"loom2.clip", "loom2.line"} & set(it.get("metadata", {}))) and int(k) not in used]
        if unused:                                                  # loom2's own items no use holds any more (never anything else in the project)
            self.fc.batch([{"id": "project.delete", "params": {"items": unused}}])
        self.fc.save()

    # ---- media ------------------------------------------------------------------------------------
    def _media(self, doc: dict, tl: Timeline, clips: dict[str, ClipRecord]) -> dict[tuple, int]:
        """The project's media item for each use of a take on the lane (the take with its stamps, `_use`), importing the missing ones (a
        take at the cut's rate as its PNG master, any other as its proxy) with their links."""
        have = {_use_of(it["metadata"]): int(k) for k, it in items(doc).items() if "loom2.clip" in it.get("metadata", {})}
        out: dict[tuple, int] = {}
        for use in dict.fromkeys(_use(c) for c in tl.clips):
            cid = use[0]
            if use in have:
                out[use] = have[use]
                continue
            rec = clips.get(cid)
            if rec is None:
                raise CutError(f"clip {cid} is not in the project")
            master = rec.fps == tl.fps and tl.fps in TIMEBASES and (self.ws.path / "clips" / cid / "master" / "000000.png").is_file()
            src = self.ws.path / "clips" / cid / "master" / "000000.png" if master else self.ws.path / rec.proxy_path
            if not src.is_file():
                raise CutError(f"clip {cid} has no {'master' if master else 'proxy'} on disk ({src})")
            r = self.fc.batch([{"id": "prefs.set", "params": {"values": prefs(tl.fps)}},
                               {"id": "file.import", "params": {"paths": [str(src)], **({"imageSequence": True} if master else {})}}])
            item = int(r[1]["items"][0])
            self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.clip": cid, "loom2.fps": str(rec.fps), "loom2.media": "master" if master else "proxy",
                                                                                      "loom2.shot": use[1], "loom2.version": use[2], "loom2.node": use[3]}}}])
            out[use] = item
        return out

    def _line_steps(self, doc: dict, tl: Timeline, s: list[int]) -> list[dict]:
        """The spoken lines on A1 where the exports lay them (`line_spans`), a line that would overlap the one before it starting where
        that one ends; each line's audio imported once with its links."""
        if self.audio_of is None:
            return []
        have = {it["metadata"].get("loom2.asset"): int(k) for k, it in items(doc).items() if "loom2.line" in it.get("metadata", {})}
        placed: list[tuple[int, int, dict]] = []                                  # (start tick at the lane's rate, length in ticks, cue)
        for i, c in enumerate(tl.clips):
            cues = self.audio_of(c) or []
            for (a0, _), cue in zip(line_spans(lane_ticks(tl, c), len(cues)), cues):
                if cue and cue.get("path"):
                    placed.append((s[i] + a0, max(1, round(float(cue["duration_s"]) * tl.fps)), cue))
        placed.sort(key=lambda x: x[0])
        steps: list[dict] = []
        end = 0
        for start, length, cue in placed:
            start = max(start, end)
            end = start + length
            item = have.get(cue.get("asset"))
            if item is None:
                r = self.fc.batch([{"id": "file.import", "params": {"paths": [str(cue["path"])]}}])
                item = int(r[0]["items"][0])
                have[cue.get("asset")] = item
                self.fc.batch([{"id": "metadata.set", "params": {"item": item, "fields": {"loom2.asset": str(cue.get("asset") or ""), "loom2.node": str(cue.get("node") or ""),
                                                                                          "loom2.line": str(cue.get("line", 0))}}}])
            steps.append({"id": "timeline.place", "params": {"item": item, "track": "A1", "time": ticks(start, tl.fps), "insert": False, "video": False}})
        return steps


def _use(c: TimelineClip) -> tuple[str, str, str, str]:
    """A take as the lane uses it: the clip and the stamps of the shot it stands for (none for a plain clip)."""
    return (c.clip_id, c.shot_id or "", c.shot_version or "", c.node_id or "")


def _use_of(meta: dict) -> tuple[str, str, str, str]:
    return (meta["loom2.clip"], meta.get("loom2.shot", ""), meta.get("loom2.version", ""), meta.get("loom2.node", ""))


def clip_records(ws: Workspace) -> dict[str, ClipRecord]:
    return {c.id: c for c in ClipStore(ws).list()}

