"""U4d (D157, G13; proto01_UI2 04 §6, 06 §2.8): the words of a shot's pictures — one composer for the plate, a still of the shot and a
performance, built from the shot's own records, so nothing is carried over from the last picture made (F25, F29). In order:

1. the Look — the project's default style;
2. the place — the World place bound to the stage's set, else the one the shot's node is at (its sheet; its hero as a reference);
3. the cast in frame — each figure and World prop on the stage that the shot's camera sees, left to right (their sheets and heroes);
4. the lights as words — each Clay light's colour, strength, softness and direction as the shot's camera sees it;
5. the scene's words — time of day, weather, the air (`Scene.words`);
6. the action — the shot's description (the node's text);
7. this shot only — the author's extra words, kept with the version (`ShotVersion.words`).

A plate has no cast and no action (its people are layers). Every part names its source, so *Show the words* can say where each phrase comes
from. The plate route sends the plate's words (F38: a set preset's plate read "The room is empty … bare walls and floor" on a street)."""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Purpose = Literal["plate", "still", "performance"]
PURPOSES: tuple[str, ...] = ("plate", "still", "performance")
PartId = Literal["look", "place", "cast", "lights", "scene", "action", "shot"]
_SKIP: dict[str, set[str]] = {"plate": {"cast", "action"}, "still": set(), "performance": set()}


class PromptPart(BaseModel):
    """One part of a shot's words, with where it came from."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: PartId
    label: str
    source: str
    text: str
    refs: list[str] = Field(default_factory=list)  # the pictures that go with it (a place's or a cast member's hero)


class ShotPrompt(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    purpose: Purpose
    text: str
    parts: list[PromptPart] = Field(default_factory=list)


# ---- geometry: what the camera sees, and from where a light comes ----

def _sub(a: list[float], b: list[float]) -> list[float]:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a: list[float], b: list[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: list[float]) -> list[float]:
    n = math.sqrt(_dot(a, a)) or 1.0
    return [a[0] / n, a[1] / n, a[2] / n]


def _basis(cam: Any) -> tuple[list[float], list[float], list[float]]:
    """The camera's forward, right and up (Y up; three.js: the camera looks down its −Z, right is +X when it looks down −Z)."""
    f = _norm(_sub(list(cam.target), list(cam.pos)))
    r = _norm([-f[2], 0.0, f[0]]) if abs(f[0]) + abs(f[2]) > 1e-6 else [1.0, 0.0, 0.0]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return f, r, u


def screen_x(point: list[float], cam: Any, aspect: float = 16 / 9) -> float | None:
    """Where a point falls across the camera's frame (−1 left edge … 1 right edge), or None when it is behind the camera or out of frame
    (a little margin: a figure half in frame counts)."""
    f, r, u = _basis(cam)
    d = _sub(point, list(cam.pos))
    z = _dot(d, f)
    if z <= 0.1:
        return None
    half_w = (cam.sensor_mm / 2) / cam.focal_mm
    x, y = _dot(d, r) / z / half_w, _dot(d, u) / z / (half_w / aspect)
    return x if abs(x) <= 1.15 and abs(y) <= 1.3 else None


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def light_words(o: Any, cam: Any) -> str:
    """A Clay light as words for the camera that sees it: colour (warm, cool), strength (dim, strong), softness, its name when the author
    gave one (a lamp, moonlight) and where it comes from — *warm soft lamp light from the left*, *cool light from behind*."""
    spec = o.light
    colour, intensity, softness = (spec.colour, spec.intensity, spec.softness) if spec is not None else ("#ffffff", 2.3, 0.3)
    red, _, blue = _hex_rgb(colour)
    tone = "warm" if red - blue > 40 else "cool" if blue - red > 40 else ""
    strength = "dim" if intensity < 1.0 else "strong" if intensity > 5.0 else ""
    soft = "soft" if softness >= 0.6 else "hard" if softness <= 0.1 else ""
    name = o.name.strip().lower()
    kind = "light" if not name or name.startswith("light") else (name if name.endswith("light") else f"{name} light")
    f, r, _ = _basis(cam)
    d = _sub(list(o.transform.pos), list(cam.target))
    side, toward, up = _dot(d, r), -_dot(d, f), d[1]
    flat = math.hypot(side, toward)
    if up > 2.0 * flat:
        where = "from above"
    elif abs(side) >= abs(toward):
        where = "from the right" if side > 0 else "from the left"
    else:
        where = "from the front" if toward > 0 else "from behind"
    return " ".join(w for w in (tone, strength, soft, kind, where) if w)


# ---- the composer ----

def _sentence(t: str) -> str:
    t = t.strip()
    return "" if not t else t if t[-1] in ".!?" else f"{t}."


def shot_prompt(ws: Any, sid: str, vid: str | None = None, purpose: str = "still") -> ShotPrompt:
    """The shot's words for a picture of `purpose`, part by part (KeyError: no such shot; ValueError: no such purpose)."""
    from .stages import StageStore
    from .story import StoryStore, compose_sheet
    if purpose not in PURPOSES:
        raise ValueError(f"a shot's words are for {', '.join(PURPOSES)}")
    st = StoryStore(ws)
    shot = st.shot(sid)
    if shot is None:
        raise KeyError(sid)
    v = next((x for x in shot.versions if x.id == (vid or shot.current)), None)
    if v is None:
        raise KeyError(f"{sid} {vid}")
    node = st.flow_node(shot.owner_node) if shot.owner_node else None
    stage = StageStore(ws).get(v.stage_id) if v.stage_id else None
    cam = next((c for c in stage.cameras if c.id == v.camera_id), None) if stage is not None else None
    aspect = (stage.size.get("w", 16) / max(1, stage.size.get("h", 9))) if stage is not None else 16 / 9
    parts: list[PromptPart] = []

    world = st.world()
    style = next((s for s in world.styles if s.id == world.default_style), None)
    if style is not None and style.fragment.strip():
        parts.append(PromptPart(id="look", label="the Look", source=f"World › Look › {style.name} ★", text=style.fragment.strip()))

    def sheet(pid: str | None, version: str | None) -> tuple[Any, Any] | None:
        p = st.profile(pid) if pid else None
        if p is None:
            return None
        pv = next((x for x in p.versions if x.id == (version or p.current)), None) or p.versions[0]
        return p, pv

    # the place bound to the stage's set (04 §6), else the place the shot's node is at
    on_set = next((o for o in stage.objects if o.kind == "set" and o.visible and o.profile_id), None) if stage is not None else None
    place_id, place_ver = (on_set.profile_id, on_set.version) if on_set is not None else (node.place_id if node is not None else None, None)
    hit = sheet(place_id, place_ver)
    if hit is not None and hit[0].cls == "place":
        p, pv = hit
        words = compose_sheet(pv, None, p.name, "place")
        parts.append(PromptPart(id="place", label="the place", source=f"World › Places › {p.name} {pv.id}",
                                text=words if words.lower().startswith(p.name.lower()) else f"{p.name}: {words}", refs=[pv.hero_asset_id] if pv.hero_asset_id else []))

    if stage is not None and cam is not None:
        seen: list[tuple[float, str, str, list[str]]] = []
        for o in stage.objects:
            if not o.visible or not o.profile_id or o.kind not in ("mannequin", "mesh"):
                continue
            x = screen_x([o.transform.pos[0], o.transform.pos[1] + (1.0 if o.kind == "mannequin" else 0.3), o.transform.pos[2]], cam, aspect)
            hit = sheet(o.profile_id, o.version)
            if x is None or hit is None:
                continue
            p, pv = hit
            words = compose_sheet(pv, None, p.name, p.cls)
            seen.append((x, p.name, words if words.lower().startswith(p.name.lower()) else f"{p.name}, {words}", [pv.hero_asset_id] if pv.hero_asset_id else []))
        seen.sort(key=lambda t: t[0])
        if seen:
            parts.append(PromptPart(id="cast", label="the cast in frame", source="Clay › " + ", ".join(n for _, n, _, _ in seen) + " (left to right)",
                                    text="; ".join(w for _, _, w, _ in seen), refs=[a for *_, rs in seen for a in rs]))
        lights = [o for o in stage.objects if o.kind == "light" and o.visible]
        if lights:
            parts.append(PromptPart(id="lights", label="the lights", source="Clay › " + ", ".join(o.name for o in lights),
                                    text=", ".join(light_words(o, cam) for o in lights)))

    scene = next((s for s in st.scene_book().scenes if s.id == node.scene_id), None) if node is not None and node.scene_id else None
    if scene is not None and scene.words.strip():
        parts.append(PromptPart(id="scene", label="the scene", source=f"Scene › {scene.name}", text=scene.words.strip()))
    if node is not None and node.text.strip():
        parts.append(PromptPart(id="action", label="the action", source="the shot's description", text=node.text.strip()))
    if v.words.strip():
        parts.append(PromptPart(id="shot", label="this shot only", source=f"{shot.name} {v.id}", text=v.words.strip()))

    parts = [x for x in parts if x.id not in _SKIP[purpose]]
    return ShotPrompt(purpose=purpose, text=" ".join(s for s in (_sentence(x.text) for x in parts) if s), parts=parts)  # type: ignore[arg-type]
