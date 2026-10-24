"""CE1 (proto01_animate 30 §10, D126): the FilmCraft session beside the orchestrator — the pinned `filmcraft-cli mcp` driven as the cut
editor's engine (the process and its requests are mcp_session.py's): every edit a FilmCraft command, the viewer's frames as PNG, the cut's
project (`timelines/<id>/cut.fcproj`) written by FilmCraft itself. At every start the session decodes in software, scales a clip to the
frame when it is placed and reads image sequences at the cut's rate (E32: the CLI decodes on the card by default, and a preference lasts
one process — so the movie's export, a process of its own, sets them again first). The binary comes from engine/filmcraft.pin.json through
scripts/build_filmcraft.py (engine/tools/, never in git); a `.py` in Settings › filmcraft.cli runs under this interpreter (the tests' fake,
orchestrator/tests/fake_filmcraft.py).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .mcp_session import McpSession, McpSessionError, cli_head

TICK = 254_016_000_000                          # FilmCraft's ticks a second: exact for every frame rate and sample rate loom2 uses
TIMEBASES = (24, 25, 30, 50, 60)                # the integer rates FilmCraft's "indeterminate media timebase" offers for image sequences
CUT_TRACKS = {"video": 2, "audio": 3}           # D126 #3: V1 shots, V2 inserts and titles; A1 dialogue, A2 music, A3 effects


def ticks(frames: int | float, fps: int) -> int:
    """`frames` at `fps` in FilmCraft's ticks (exact for an integer count)."""
    return round(frames * TICK / fps)


def prefs(fps: int = 24) -> dict[str, str]:
    """The preferences every FilmCraft process loom2 starts sets first (D97: never decode on the card beside ComfyUI)."""
    return {"playback.hardwareDecoding": "off", "media.defaultMediaScaling": "scaleToFrameSize",
            "media.indeterminateTimebase": str(fps if fps in TIMEBASES else 24)}


def data_dir(app) -> Path:
    """FilmCraft's per-user folder for loom2's processes (its export presets), inside loom2's state, never the author's own FilmCraft's."""
    return Path(app.state_dir) / "filmcraft"


def export_script(out: Path, fmt: str, fps: int = 24, **settings: Any) -> str:
    """The movie's `run` script (JSON lines): the preferences, then `file.exportMedia` waiting for the file."""
    steps = [{"id": "prefs.set", "params": {"values": prefs(fps)}},
             {"id": "file.exportMedia", "params": {"path": str(out), "format": fmt, "wait": True, **settings}}]
    return "\n".join(json.dumps(s) for s in steps) + "\n"


def export_argv(settings, app, project: Path, script: Path) -> list[str]:
    """`filmcraft-cli run`: the cut's project opened by a process of its own, the export script run in it (a queued CPU job, D126 #5)."""
    if not Path(settings.cli).is_file():
        raise ValueError(f"FilmCraft is not built: {settings.cli} is missing (scripts/build_filmcraft.py)")
    return [*cli_head(settings), "--data-dir", str(data_dir(app)), "--project", str(project), "run", str(script)]


class FilmCraftError(McpSessionError):
    """The session refused a request (FilmCraft's own message), timed out, or is not available."""


class FilmCraft(McpSession):
    name = "FilmCraft"
    build_script = "scripts/build_filmcraft.py"
    Error = FilmCraftError

    @property
    def settings(self):
        return self.app.settings.filmcraft

    def argv(self) -> list[str]:
        return [*cli_head(self.settings), "--data-dir", str(data_dir(self.app)), "mcp"]

    def _started_locked(self, want: str | None) -> None:
        self._tool_locked("command_run", {"id": "prefs.set", "params": {"values": prefs()}})
        if want:
            self._tool_locked("command_run", {"id": "file.open", "params": {"path": want}})
            self.project = want

    def open(self, path: str | Path) -> None:
        """Hold this cut's project open in the session (a no-op when it already is)."""
        path = str(path)
        with self._lock:
            self._ensure_locked()
            if self.project == path:
                return
            self._tool_locked("command_run", {"id": "file.open", "params": {"path": path}})
            self.project = path

    def close(self, path: str | Path) -> None:
        """Let go of this project when the session holds it (before its file is deleted)."""
        with self._lock:
            if self.project != str(path) or not self.alive():
                return
            self._tool_locked("command_run", {"id": "file.closeProject", "params": {"force": True}})
            self.project = None

    def new(self, path: str | Path, name: str, w: int, h: int, fps: int) -> int:
        """A new cut's project at `path`: one sequence at the cut's format with D126's tracks, saved; the session holds it. Returns the
        sequence's item id."""
        path = str(path)
        with self._lock:
            self._ensure_locked()
            self._tool_locked("command_run", {"id": "file.newProject", "params": {"name": name}})
            seq = self._tool_locked("command_run", {"id": "file.newSequence", "params": {"name": name, "width": w, "height": h, "fps": fps,
                                                                                           "sampleRate": 48000, "mix": "Stereo", **CUT_TRACKS}})
            self._tool_locked("command_run", {"id": "file.saveAs", "params": {"path": path}})
            self.project = path
            return int(seq["sequence"])

    def batch(self, steps: list[dict]) -> list[Any]:
        """Several commands in order, stopping at the first refusal (FilmCraft's `command_batch`): their results."""
        r = self.tool("command_batch", {"steps": steps, "stop_on_error": True})
        results = r.get("results") or []
        bad = next((x for x in results if not x.get("ok")), None)
        if r.get("failed") or bad is not None:
            raise FilmCraftError(f"command_batch: {(bad or {}).get('error') or r}")
        return [x.get("result") for x in results]

    def save(self) -> None:
        """Write the held project to its file (FilmCraft saves atomically)."""
        self.command("file.save", {})

    def sequence(self) -> dict:
        """The active sequence as FilmCraft reports it (tracks, items, transitions, markers; ticks and frames)."""
        return self.tool("sequence_inspect", {})

    def frame(self, seconds: float, max_side: int = 960) -> bytes:
        """The active sequence's frame at `seconds` as PNG, its longer side at most `max_side`."""
        content = self.tool("render_frame", {"seconds": float(seconds), "max_side": int(max_side)})
        img = next((c for c in content if c.get("type") == "image"), None) if isinstance(content, list) else None
        if not img:
            raise FilmCraftError("render_frame returned no image")
        return base64.b64decode(img["data"])
