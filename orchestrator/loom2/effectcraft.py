"""AE1 (proto01_animate 20 §2, D114): the EffectCraft session beside the orchestrator — the pinned `effectcraft-cli mcp` (JSON-RPC 2.0 over
stdio, one message a line) driven as the animation editor's engine: every engine command, a frame as PNG at any size, the project saved
through a copy. One request at a time (the session is single-threaded and a frame is ≈ 60 ms, E27); started on first use, restarted when
it dies (the project it held is opened again); its stderr in the state's logs. The binary comes from engine/effectcraft.pin.json through
scripts/build_effectcraft.py (engine/tools/, never in git); a `.py` in Settings › effectcraft.cli runs under this interpreter (the tests'
fake, orchestrator/tests/fake_effectcraft.py). The process and its requests are mcp_session.py's (shared with FilmCraft since CE1, D126).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .mcp_session import PROTOCOL, McpSession, McpSessionError, cli_head
from .recipes import RenderSettings

__all__ = ["PROTOCOL", "EffectCraft", "EffectCraftError", "cli_head", "render_argv"]


def render_argv(settings, project: Path, comp: str, out_pattern: Path, rs: RenderSettings | None = None) -> list[str]:
    """AE5: the composition as a PNG sequence through EffectCraft's render queue (`run renderQueue.add … renderQueue.render`, which waits)
    with the final's render settings — quality, resolution, motion blur and frame blending (the composition's switches or off), the working
    colour depth, the alpha; proxies never used. AE1's defaults are E27's R2 (Best, Full: equal to the preview to 0/255)."""
    if not Path(settings.cli).is_file():
        raise ValueError(f"EffectCraft is not built: {settings.cli} is missing (scripts/build_effectcraft.py)")
    rs = rs or RenderSettings()
    item = {"comp": comp, "output": str(out_pattern), "format": "png", "quality": rs.quality, "resolution": rs.resolution, "channels": "rgba" if rs.alpha else "rgb",
            "colorDepth": str(rs.depth), "motionBlur": "current" if rs.motion_blur == "comp" else "offForAll",
            "frameBlending": "current" if rs.frame_blending == "comp" else "offForAll", "proxyUse": "none", "timeSpan": "comp"}
    return [*cli_head(settings), "run", "renderQueue.add", json.dumps(item), "renderQueue.render", "{}", "--project", str(project)]


class EffectCraftError(McpSessionError):
    """The session refused a request (the engine's own message), timed out, or is not available."""


class EffectCraft(McpSession):
    name = "EffectCraft"
    build_script = "scripts/build_effectcraft.py"
    Error = EffectCraftError

    @property
    def settings(self):
        return self.app.settings.effectcraft

    def argv(self) -> list[str]:
        return [*cli_head(self.settings), "mcp", "--empty"]

    def env(self) -> dict[str, str]:
        return {**super().env(), "WGPU_BACKEND": "vulkan"}

    def _started_locked(self, want: str | None) -> None:
        if want:
            self._tool_locked("open_project", {"path": want})
            self.project = want

    def release(self, path: str | Path) -> bool:
        """V43: let go of this .ecproj when the session holds it — the session ends (the next use starts it again and opens what it asks
        for) — before the project's folder is deleted. True when it was held."""
        with self._lock:
            held = self.project == str(path)
        if held:
            self.stop()
        return held

    def open(self, path: str | Path) -> None:
        """Hold this .ecproj open in the session (a no-op when it already is)."""
        path = str(path)
        with self._lock:
            self._ensure_locked()
            if self.project == path:
                return
            self._tool_locked("open_project", {"path": path})
            self.project = path

    def frame(self, time_s: float, max_side: int = 0, comp: str | int | None = None, transparent: bool = False) -> bytes:
        """A frame of the open project's composition as PNG (`max_side` 0 = full size)."""
        args: dict[str, Any] = {"time": float(time_s), "max_side": int(max_side), "transparent": bool(transparent)}
        if comp is not None:
            args["comp"] = comp
        content = self.tool("render_frame", args, replay=True)         # V97: a render is idempotent — once more if the session ended under it
        img = next((c for c in content if c.get("type") == "image"), None) if isinstance(content, list) else None
        if not img:
            raise EffectCraftError("render_frame returned no image")
        return base64.b64decode(img["data"])

    def save_copy(self, path: str | Path) -> None:
        """Write the session's project to `path` without changing which file it holds (the caller replaces atomically, fsio)."""
        self.command("file.saveCopy", {"path": str(path)})
