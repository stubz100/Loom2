"""RC0 (D96, proto01_animate/05 §4): a shot version's recipe — the steps that made its frame and clip, as a plan with its history.

Every job made for a shot version (a For-chip job, a stage camera's frame or clip, a lip-sync take) records a **run** on the version's
step for that job: the settings it ran with (the resolved recipe), its outputs (the takes), its wall time, and **stamps** — what it read
that can change after it (a stage's revision, a reference group's revision, a Cast version's sheet, the world style, the frame a clip
started from). Assets are immutable and need no stamp.

A step is **stale** when the run that made the version's used output (or, with none used, the last run) carries a stamp that no longer
matches the project; a step after a stale one is stale too (its input is out of date). Nothing is stale by itself without a stamp —
a manual take (*Use as the frame*) is not a run. The orchestrator computes the state on request (`recipe_state`); nothing is stored.

The templates (§3) name a recipe's steps in order. Today's runnable steps are the frame, the clip and the lip-sync take; the clay
pipeline's steps (CA0–CA6) are listed as planned until their waves land, so a template shows every step and hides none.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import utc_now

RUNS_KEPT = 6                                     # per step: the history the state and the cost read (older runs drop off)
StepState = Literal["fresh", "stale", "missing", "planned"]


class RecipeRun(BaseModel):
    """One job's contribution to a step: what it ran with, what it read (stamps) and what it made."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    job_id: str | None = None
    kind: str                                     # the job's recipe kind (t2i, stage_shot, i2v, …)
    settings: dict[str, Any] = Field(default_factory=dict)
    stamps: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)   # the take ids (asset ids for images, clip ids for clips)
    seconds: float | None = None
    at: str = Field(default_factory=utc_now)


class RecipeStep(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str                                       # the step's role: frame, clip, lipsync (the clay steps join with their waves)
    inputs: list[str] = Field(default_factory=list)   # the step ids it reads
    runs: list[RecipeRun] = Field(default_factory=list)


class ShotRecipe(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    template: str | None = None
    steps: list[RecipeStep] = Field(default_factory=list)

    def step(self, sid: str) -> RecipeStep | None:
        return next((s for s in self.steps if s.id == sid), None)


# ---- the templates (05 §3) ---------------------------------------------------------------------------------------------------------
class TemplateStep(BaseModel):
    id: str
    label: str
    inputs: list[str] = Field(default_factory=list)
    wave: str | None = None                       # planned: the wave that makes it runnable (None = runnable today)
    experimental: bool = False


class Template(BaseModel):
    id: str
    label: str
    hint: str
    steps: list[TemplateStep]


# RC1 (proto01_animate 28): the clay waves are built (CA0–CA1, PS1–PS5, AE1–AE5); a clay version's states come from its graph (shot_graph).
# The start still stays planned: the clay route performs from the animation references, and the stills come with CA5's W3 repair.
_CLAY = [TemplateStep(id="character", label="Character"), TemplateStep(id="anim_ref", label="Animation reference", inputs=["character"]),
         TemplateStep(id="motion", label="Motion"), TemplateStep(id="camera", label="Camera"),
         TemplateStep(id="plate", label="Plate", inputs=["camera"]),
         TemplateStep(id="frame", label="Start still", inputs=["anim_ref", "motion", "camera"], wave="CA5 (W3)"),
         TemplateStep(id="performance", label="Performance (layers)", inputs=["anim_ref", "plate", "motion"]),
         TemplateStep(id="composition", label="Composition", inputs=["performance", "plate"]),
         TemplateStep(id="finish", label="Finish", inputs=["composition"]), TemplateStep(id="take", label="Take", inputs=["finish"])]

TEMPLATES: dict[str, Template] = {t.id: t for t in [
    Template(id="i2v", label="Image to video", hint="a frame, then a performance from it",
             steps=[TemplateStep(id="frame", label="Frame"), TemplateStep(id="clip", label="Performance", inputs=["frame"])]),
    Template(id="stage", label="From the stage", hint="the stage's camera: a still from its passes, then a clip guided by its depth",
             steps=[TemplateStep(id="frame", label="Start still (the stage)"), TemplateStep(id="clip", label="Performance (the stage's guide)", inputs=["frame"])]),
    Template(id="clay1", label="Clay, one character", hint="the clay pipeline (01, 02): the final shot made on the stage — the plate, a layer per character, the composition", steps=_CLAY),
    Template(id="clay2", label="Clay, two characters", hint="as Clay, one character, a layer per character", steps=_CLAY),
    Template(id="dialogue", label="Dialogue with voice", hint="the lines voiced, a frame, a performance, and lip-sync (experimental)",
             steps=[TemplateStep(id="voice", label="Lines and voice", wave="RC2"), TemplateStep(id="frame", label="Frame"),
                    TemplateStep(id="clip", label="Performance", inputs=["frame"]),
                    TemplateStep(id="lipsync", label="Lip-sync", inputs=["frame", "voice"], experimental=True)]),
]}


def default_template(stage_id: str | None) -> str:
    return "stage" if stage_id else "i2v"


# ---- what a job is, as a step ------------------------------------------------------------------------------------------------------
FRAME_KINDS = ("t2i", "i2i", "inpaint", "reangle", "stage_shot", "upscale")


def step_of(recipe: dict[str, Any], frame_asset_id: str | None) -> tuple[str, list[str]] | None:
    """The step a job's (resolved) recipe fills on a version, and the step ids it read; None for a job no step takes."""
    kind = recipe.get("kind")
    if kind in FRAME_KINDS:
        return "frame", []
    if kind == "i2v":
        start = recipe.get("start_asset")
        inputs = ["frame"] if start and start == frame_asset_id else []
        return ("lipsync" if recipe.get("audio") else "clip"), inputs
    return None


def _fp(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def sheet_fp(v: Any) -> str:
    """A Cast version's words and pins as a fingerprint: what a mention of it composes (the sheet), its hero and its LoRA."""
    body = getattr(v, "body", None)
    return _fp(v.appearance, v.outfit, [c.model_dump() for c in v.colours], v.marks, v.hero_asset_id, v.trigger, v.lora, v.label,
               *([body.model_dump()] if body is not None else []))   # CA0: the body shapes the dummy, so the passes (absent body: the old fingerprint)


def stamps_for(recipe: dict[str, Any], *, frame_asset_id: str | None, stage_id: str | None, stage_revision: int | None, story: Any) -> dict[str, Any]:
    """What a run read that can change after it. Keys: `stage:<id>` → revision, `group:<id>` → revision, `sheet:<profile>:<version>` → the
    version's fingerprint, `style:<id>` → the fragment's fingerprint, `frame` → the asset a clip started from (the version's frame)."""
    out: dict[str, Any] = {}
    if stage_id and stage_revision is not None:
        out[f"stage:{stage_id}"] = stage_revision
    for m in recipe.get("mentions") or []:
        if m.get("group_id") and m.get("revision") is not None:
            out[f"group:{m['group_id']}"] = m["revision"]
        if m.get("profile_id") and story is not None:
            p = story.profile(m["profile_id"])
            if p is not None:
                try:
                    v = p.version(m.get("version"))
                except KeyError:
                    continue
                out[f"sheet:{p.id}:{v.id}"] = sheet_fp(v)
    if recipe.get("style_id") and recipe.get("style_text") is not None:
        out[f"style:{recipe['style_id']}"] = _fp(recipe["style_text"])
    if recipe.get("kind") == "i2v" and recipe.get("start_asset") and recipe["start_asset"] == frame_asset_id:
        out["frame"] = recipe["start_asset"]
    return out


def add_run(recipe: ShotRecipe | None, template: str, step_id: str, inputs: list[str], run: RecipeRun) -> ShotRecipe:
    """The recipe with `run` appended to its step (made when missing, inputs kept in step order)."""
    r = recipe.model_copy(deep=True) if recipe else ShotRecipe(template=template)
    st = r.step(step_id)
    if st is None:
        st = RecipeStep(id=step_id, inputs=inputs)
        r.steps.append(st)
    else:
        st.inputs = sorted(set(st.inputs) | set(inputs), key=lambda x: (x != "frame", x))
    st.runs = [*st.runs, run][-RUNS_KEPT:]
    return r


# ---- the state -------------------------------------------------------------------------------------------------------------------
class StampReader:
    """The project's current values for the stamp keys (read once per request)."""

    def __init__(self, *, stages: Any = None, groups: Any = None, story: Any = None) -> None:
        self.stages, self.groups, self.story = stages, groups, story
        self._cache: dict[str, Any] = {}

    def now(self, key: str, version: Any) -> Any:
        if key in self._cache:
            return self._cache[key]
        val: Any = None
        kind, _, rest = key.partition(":")
        if kind == "stage" and self.stages is not None:
            st = self.stages.get(rest)
            val = st.revision if st else None
        elif kind == "group" and self.groups is not None:
            g = self.groups.groups.get(rest)
            val = g.revision if g else None
        elif kind == "sheet" and self.story is not None:
            pid, _, vid = rest.partition(":")
            p = self.story.profile(pid)
            if p is not None:
                try:
                    val = sheet_fp(p.version(vid))
                except KeyError:
                    val = None
        elif kind == "style" and self.story is not None:
            s = self.story.style(rest)
            val = _fp(s.fragment.strip()) if s else None
        elif kind == "frame":
            val = version.frame_asset_id
        self._cache[key] = val
        return val


def _why(key: str, then: Any, now: Any, names: dict[str, str]) -> str | None:
    kind, _, rest = key.partition(":")
    if kind == "stage":
        if now is None:
            return "the stage is gone"
        return f"the stage moved on (revision {then} → {now})" if now > then else None
    if now == then:
        return None
    if kind == "group":
        return f"the references of {names.get(rest, 'a group')} changed" if now is not None else f"{names.get(rest, 'a reference group')} is gone"
    if kind == "sheet":
        return f"{names.get(rest, 'a character')}'s sheet changed" if now is not None else f"{names.get(rest, 'a character version')} is gone"
    if kind == "style":
        return "the world style changed" if now is not None else "the world style is gone"
    if kind == "frame":
        return "the frame changed" if now else "the frame was cleared"
    return f"{key} changed"


def _names(recipe: ShotRecipe, story: Any) -> dict[str, str]:
    """Readable names for the stamp keys: a mention's own name for its group, the character and version for a sheet."""
    out: dict[str, str] = {}
    for st in recipe.steps:
        for run in st.runs:
            for m in run.settings.get("mentions") or []:
                if m.get("group_id"):
                    out[m["group_id"]] = f"@{m.get('name') or m['group_id']}"
                if m.get("profile_id") and story is not None:
                    p = story.profile(m["profile_id"])
                    if p is not None:
                        for v in p.versions:
                            out[f"{p.id}:{v.id}"] = f"{p.name} {v.label or v.id}"
    return out


def used_run(step: RecipeStep, version: Any) -> RecipeRun | None:
    """The run whose output the version uses (its frame, its clip), else the last run."""
    used = version.frame_asset_id if step.id == "frame" else version.clip_id if step.id == "clip" else None
    if used:
        for run in reversed(step.runs):
            if used in run.outputs:
                return run
    return step.runs[-1] if step.runs else None


def recipe_state(version: Any, reader: StampReader) -> dict[str, Any]:
    """The version's recipe as the template's steps in order (plus any step a job made outside it), each with its state, the reasons,
    its last cost and its runs. A step after a stale one is stale ("after <step>")."""
    recipe: ShotRecipe = version.recipe or ShotRecipe(template=default_template(version.stage_id))
    tpl = TEMPLATES.get(recipe.template or default_template(version.stage_id)) or TEMPLATES["i2v"]
    names = _names(recipe, reader.story)
    rows: list[dict[str, Any]] = []
    order = [t.id for t in tpl.steps] + [s.id for s in recipe.steps if s.id not in {t.id for t in tpl.steps}]
    labels = {t.id: t for t in tpl.steps}
    state_of: dict[str, str] = {}
    for sid in order:
        t = labels.get(sid)
        st = recipe.step(sid)
        inputs = list(dict.fromkeys([*(t.inputs if t else []), *(st.inputs if st else [])]))
        run = used_run(st, version) if st else None
        reasons: list[str] = []
        if run is None:
            state: str = "planned" if t and t.wave else "missing"
        else:
            for key, then in run.stamps.items():
                why = _why(key, then, reader.now(key, version), names)
                if why:
                    reasons.append(why)
            stale_inputs = [i for i in inputs if state_of.get(i) == "stale"]
            reasons += [f"after {labels[i].label.lower() if i in labels else i}" for i in stale_inputs]
            state = "stale" if reasons else "fresh"
        state_of[sid] = state
        rows.append({"id": sid, "label": t.label if t else sid, "inputs": inputs, "state": state, "reasons": reasons,
                     "wave": t.wave if t else None, "experimental": bool(t and t.experimental),
                     "runs": len(st.runs) if st else 0, "kind": run.kind if run else None,
                     "seconds": run.seconds if run else None, "job_id": run.job_id if run else None,
                     "outputs": run.outputs if run else [], "at": run.at if run else None})
    return {"template": tpl.id, "label": tpl.label, "steps": rows, "stale": sum(1 for r in rows if r["state"] == "stale"),
            "stale_seconds": round(sum((r["seconds"] or 0) for r in rows if r["state"] == "stale"), 1)}


# ---- Run stale (05 §4: a planned set of jobs, in dependency order, with its cost) -------------------------------------------------------
How = Literal["server", "passes", "stage", "manual"]


def how_to_run(run: RecipeRun) -> How:
    """How a stale step runs again from its counted run: `server` resubmits its settings; `passes` is a stage still whose passes the client
    renders first (the server cannot draw the stage); `stage` is a clip guided by the stage's pass sequence (made again on the stage, in
    Animate); `manual` is anything else (an edit made in Image · Edit)."""
    if run.kind == "stage_shot":
        return "passes"
    if run.kind == "i2v":
        return "stage" if run.settings.get("guide") else "server"
    return "server" if run.kind in ("t2i", "i2i", "reangle", "upscale") else "manual"


def rerun_recipe(run: RecipeRun, version: Any, passes: dict[str, str] | None = None) -> dict[str, Any]:
    """The counted run's recipe made ready to run again: its mentions unstamped (so the queue resolves them against today's groups and
    sheets — the version pins stay), the style re-read, a clip started from the version's frame of now, a stage still on fresh passes.
    The seeds stay: the same take, brought up to date."""
    r = copy.deepcopy(run.settings)
    stale_loras = {m.get("lora") for m in r.get("mentions") or [] if m.get("lora")}
    if stale_loras:
        r["loras"] = [x for x in r.get("loras") or [] if x.get("model_id") not in stale_loras]
    for m in r.get("mentions") or []:
        m.update({"revision": None, "asset_ids": [], "lora": None, "lora_available": None, "composed": None, "skipped": None})
    if r.get("style_id"):
        r["style_text"] = None
    if r.get("kind") == "i2v" and "frame" in run.stamps and version.frame_asset_id:
        r["start_asset"] = version.frame_asset_id
    if r.get("kind") == "stage_shot" and passes:
        r["passes"] = dict(passes)
    if len(r.get("seeds") or []) > 1:
        r["seeds"] = r["seeds"][:1]                         # U0 (BE#3): one take again, never the batch (runs recorded before the job's own seed)
    return r


def stale_plan(version: Any, reader: StampReader) -> list[dict[str, Any]]:
    """The stale steps in order: how each runs, its last cost, and the stale steps it waits for."""
    state = recipe_state(version, reader)
    stale = {r["id"] for r in state["steps"] if r["state"] == "stale"}
    out = []
    recipe: ShotRecipe = version.recipe or ShotRecipe()
    for r in state["steps"]:
        if r["id"] not in stale:
            continue
        st = recipe.step(r["id"])
        run = used_run(st, version) if st else None
        out.append({"id": r["id"], "label": r["label"], "how": how_to_run(run) if run else "manual", "kind": run.kind if run else None,
                    "seconds": r["seconds"], "after": [i for i in r["inputs"] if i in stale], "reasons": r["reasons"]})
    return out


# ---- the coverage check (05 §3: every step's important parts reach the job that runs) -----------------------------------------------
# A runnable step kind → its important parts → the recipe field(s) that carry each. tests/test_shot_recipe_rc0.py asserts the fields exist
# on the typed recipe; scripts/settings_audit.py (D60) already proves every recipe field reaches the compiler.
COVERAGE: dict[str, dict[str, list[str]]] = {
    "t2i": {"model and its preset": ["model_id", "steps", "guidance", "cfg"], "prompt (scene, subjects)": ["prompt_json", "prompt_text", "prompt_mode"],
            "references (slots, groups, mentions)": ["refs", "mentions", "bind_refs"], "Look (style)": ["style_id", "style_text"],
            "size / tier": ["width", "height", "tier"], "LoRAs": ["loras", "auto_lora"], "encoder": ["te_id"], "seed and count": ["seeds"]},
    "stage_shot": {"method": ["method"], "the passes": ["passes"], "references (bound per figure)": ["refs", "mentions", "bind_refs"],
                   "prompt": ["prompt_text"], "size / tier": ["width", "height"], "encoder": ["te_id"], "seed and count": ["seeds"], "the camera": ["stage_id", "camera_id"]},
    "i2v": {"model and preset (steps, CFG, shift)": ["model_id", "preset", "steps", "cfg", "shift"], "length and rate": ["frames", "fps"],
            "start and end": ["start_asset", "end_asset"], "prompt and negative": ["prompt_text", "negative"], "beats": ["beats"],
            "the stage's guide": ["guide"], "size": ["width", "height"], "seed": ["seeds"], "LoRAs": ["loras"],
            "lip-sync (experimental)": ["audio"], "extend (experimental)": ["extend_from"]},
}
