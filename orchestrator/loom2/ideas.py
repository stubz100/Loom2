"""proto01_UIcast CW1–CW2 (D136 U1–U4; 06 §2.1–2.2): ideas — Cast's loose first stage, kept apart from the profiles.

An idea gathers **variants**: pictures copied onto the idea's own album page (U2), each knowing where it came from (the source picture,
its prompt, model and seed, the idea it was made for). Its name is optional: one left out is read from the first picture's prompt (U3).
*Make the clay ▶* gives a character's variant its figure — an A-pose picture drawn from it, the body fitted to that (D140) — and then,
in the background, its shell (Pixal3D, D139). *Keep ▶* makes a Cast profile (v1), or a new version of a chosen one, from a variant: the
hero, a sheet drafted from the prompt, the clay; the idea records where it went and the version `from_idea`, so lineage runs both ways.
Image stays free (U4): what is made while its For chip names an idea is listed on the idea (`made_for`), never a variant by itself.

Ideas stay out of production: no @mention, no place in Flow's pickers or Shots, no LoRA. Files are truth: `story/ideas/<id>.json`,
written through fsio with a schema version and a revision (409 when stale)."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .body import Body
from .fsio import atomic_write_json, new_id, read_json, utc_now
from .origin import JobOrigin

if TYPE_CHECKING:
    from .catalogue import AssetRecord
    from .groups import GroupStore
    from .workspace import Workspace

IDEA_SCHEMA_VERSION = 1
IdeaClass = Literal["character", "prop", "place"]
IDEA_CLAY_SURFACE = "idea_clay"                  # CW1: origin.surface of a variant's clay jobs; ref = the idea, payload {variant, step}
FOR_IDEA = "for_idea"                             # CW2: the key a job's origin payload carries while Image's For chip names an idea
MADE_FOR_MAX = 200                                # the newest results kept on an idea's *Made for this idea* list
_LOCK = threading.Lock()


class MadeFrom(BaseModel):
    """Where a variant's picture came from (read from the source at the copy, lineage at write time)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    asset_id: str | None = None                   # the picture copied (its page keeps it)
    prompt: str = ""
    model: str | None = None
    seed: int | None = None
    for_idea: str | None = None                   # CW2: the idea the source was made for (its job's origin)


ClayStep = Literal["drawing", "fitting", "shell", "done", "failed"]


class VariantClay(BaseModel):
    """A character variant's clay: the A-pose picture drawn from it, the body fitted to that, the shell made from it — the same three a Cast
    version holds (`anim_ref_asset_id`, `body` + `body_points`, `shell_asset_id`), carried over by *Keep ▶*."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: Literal["figure", "model", "set"] = "figure"
    step: ClayStep = "drawing"                    # where the chain is: the A-pose picture, the fit, the shell, done — or failed (`error`)
    anim_ref_asset_id: str | None = None
    body: Body | None = None
    body_points: dict[str, Any] | None = None
    note: str | None = None                       # the fit's reading of the stance ("arms_close": drawn again, D140)
    shell_asset_id: str | None = None
    model_asset_id: str | None = None             # CW3: a prop idea's model (Prototype ▸ on a free mesh in Clay)
    height_m: float | None = Field(None, gt=0.0, le=100.0)   # CW3/CW4: that model's height
    job_id: str | None = None                     # the step's job (the Dock and the bench follow it)
    error: str | None = None


class Variant(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str = Field(default_factory=lambda: new_id("var"))
    asset_id: str                                 # the copy on the idea's page
    made_from: MadeFrom = Field(default_factory=MadeFrom)
    clay: VariantClay | None = None
    note: str = Field("", max_length=400)
    created_at: str = Field(default_factory=utc_now)


class Kept(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    profile_id: str
    version_id: str
    variant_id: str
    at: str = Field(default_factory=utc_now)


class Idea(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = IDEA_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("ida"))
    cls: IdeaClass = "character"
    name: str = Field(..., min_length=1, max_length=80)
    note: str = Field("", max_length=1000)
    focus: str | None = None                      # the variant in focus (its picture is the idea's card)
    group_id: str                                 # the idea's own album page ("‹name› · idea")
    variants: list[Variant] = Field(default_factory=list)
    kept: list[Kept] = Field(default_factory=list)
    made_for: list[str] = Field(default_factory=list)   # CW2: results made while Image's For chip named it, newest first
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def variant(self, vid: str) -> Variant:
        v = next((x for x in self.variants if x.id == vid), None)
        if v is None:
            raise KeyError(f"no variant {vid!r}")
        return v


class StaleIdea(Exception):
    pass


def focus_variant(idea: Idea) -> Variant | None:
    """The variant in focus, else the newest."""
    return next((v for v in idea.variants if v.id == idea.focus), None) or (idea.variants[-1] if idea.variants else None)


# ---- the words: a name and a sheet from a prompt (U3; 02 §4) --------------------------------------------------------------------------
_LEAD = re.compile(r"^(a|an|the|one|portrait of|photo of|a photo of|an image of|illustration of)\s+", re.I)
# where the subject phrase ends: a verb in -ing (not "wearing", not a short noun like "king" or "ring"), a clause, a place
_CUT = re.compile(r"\s+(?:(?!wearing\b)\w{4,}ing|who|that|with her|with his|against|on a|on the|at the|at a|under|by the)\b.*$", re.I)
_DRESS = re.compile(r"\s+(?:in|wearing|dressed in)\s+", re.I)
CLASS_WORD = {"character": "character", "prop": "prop", "place": "place"}


def _first_clause(prompt: str) -> str:
    s = re.split(r"[,.;:\n]", (prompt or "").strip(), maxsplit=1)[0].strip()
    while _LEAD.match(s):
        s = _LEAD.sub("", s, count=1)
    return s


def name_from_prompt(prompt: str, cls: str = "character") -> str:
    """U3: an idea's name read from its first picture's prompt — the first noun phrase ("woman in a yellow raincoat" from "A woman in a
    yellow raincoat standing on a quay, cinematic"), six words at most; "‹class› idea" when the prompt gives nothing."""
    s = _CUT.sub("", _first_clause(prompt)).strip(" -–—")
    words = s.split()[:6]
    while words and words[-1].lower() in ("a", "an", "the", "and", "of", "in", "with", "wearing"):
        words.pop()                                                          # cut mid-phrase: not on a dangling article
    return " ".join(words)[:60] if words else f"{CLASS_WORD.get(cls, 'character')} idea"


def draft_sheet(prompt: str) -> dict[str, str]:
    """02 §4: a kept variant's sheet drafted from its prompt — the subject phrase as the appearance, what it wears as the outfit (both
    editable in Cast). Nothing when the prompt gives nothing."""
    parts = [x.strip() for x in _DRESS.split(_CUT.sub("", _first_clause(prompt)), maxsplit=1)]
    if not parts[0]:
        return {}
    return {"appearance": parts[0][:1000], **({"outfit": parts[1][:400]} if len(parts) > 1 and parts[1] else {})}


def made_from(rec: AssetRecord) -> MadeFrom:
    """A picture's provenance as a variant keeps it: its prompt, model and seed, and the idea its job was made for."""
    pay = (rec.origin.payload or {}) if rec.origin else {}
    fi = pay.get(FOR_IDEA)
    return MadeFrom(asset_id=rec.duplicate_of or rec.id, prompt=(rec.prompt_text or "")[:2000], model=rec.model_id, seed=rec.seed,
                    for_idea=fi if isinstance(fi, str) else None)


def idea_clay_origin(idea_id: str, variant_id: str, step: str) -> JobOrigin:
    return JobOrigin(suite="story", surface=IDEA_CLAY_SURFACE, ref=idea_id, payload={"variant": variant_id, "step": step})


# ---- the store -------------------------------------------------------------------------------------------------------------------------
class IdeaStore:
    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir: Path = ws.story_dir / "ideas"

    def path(self, iid: str) -> Path:
        return self.dir / f"{iid}.json"

    def get(self, iid: str) -> Idea | None:
        p = self.path(iid)
        return Idea.model_validate(read_json(p)) if p.is_file() else None

    def list(self) -> list[Idea]:
        if not self.dir.is_dir():
            return []
        out = []
        for p in sorted(self.dir.glob("ida_*.json")):
            try:
                out.append(Idea.model_validate(read_json(p)))
            except Exception:  # noqa: BLE001 — a broken file is skipped, not fatal for the board
                continue
        return sorted(out, key=lambda i: i.updated_at, reverse=True)

    def _save(self, idea: Idea, bump: bool = True) -> Idea:
        if bump:
            idea = idea.model_copy(update={"revision": idea.revision + 1, "updated_at": utc_now()})
        with _LOCK:
            self.dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.path(idea.id), idea.model_dump())
        return idea

    def _require(self, iid: str) -> Idea:
        idea = self.get(iid)
        if idea is None:
            raise KeyError(iid)
        return idea

    def _copy(self, groups: GroupStore, asset_id: str, gid: str) -> tuple[str, MadeFrom]:
        """U2: the picture copied onto the idea's page (its own page keeps it)."""
        rec = groups.cat.get(asset_id)
        if rec is None or rec.trashed_at is not None or rec.kind != "image":
            raise ValueError("a variant is a picture in the Catalogue")
        dup = groups.cat.duplicate(asset_id)
        if dup is None:
            raise ValueError("the picture could not be copied (its file is missing)")
        groups.move([("asset", dup.id)], gid)
        return dup.id, made_from(rec)

    def create(self, cls: IdeaClass, groups: GroupStore, asset_id: str | None = None, name: str | None = None, note: str = "", move: bool = False) -> Idea:
        """A new idea on its own album page; a picture given is copied there as its first variant (in focus), and names the idea when no
        name is given (U3). `move`: a picture made for it (Clay's view of a free object) moves there instead."""
        prompt = ""
        if asset_id:
            rec = groups.cat.get(asset_id)
            prompt = (rec.prompt_text or "") if rec else ""
        nm = (name or "").strip() or name_from_prompt(prompt, cls)
        g = groups.create(f"{nm} · idea")
        idea = Idea(cls=cls, name=nm[:80], note=note, group_id=g.id)
        if asset_id and move:
            rec = groups.cat.get(asset_id)
            if rec is None or rec.kind != "image":
                raise ValueError("a variant is a picture in the Catalogue")
            groups.move([("asset", asset_id)], g.id)
            groups.update(g.id, cover_id=asset_id)
            v = Variant(asset_id=asset_id, made_from=made_from(rec))
            idea = idea.model_copy(update={"variants": [v], "focus": v.id})
        elif asset_id:
            aid, src = self._copy(groups, asset_id, g.id)
            groups.update(g.id, cover_id=aid)
            v = Variant(asset_id=aid, made_from=src)
            idea = idea.model_copy(update={"variants": [v], "focus": v.id})
        return self._save(idea, bump=False)

    def patch(self, iid: str, data: dict[str, Any], groups: GroupStore | None = None) -> Idea:
        """The name, note, class and focus, a variant's note (`variants: [{id, note}]`) — from a body based on `revision` (409 when stale)."""
        cur = self._require(iid)
        base = data.get("revision")
        if base is not None and int(base) != cur.revision:
            raise StaleIdea(f"the idea is at revision {cur.revision}, the change is based on {base} — reload it first")
        upd = {k: data[k] for k in ("name", "note", "cls", "focus") if k in data}
        if "name" in upd:
            upd["name"] = str(upd["name"]).strip()
        if upd.get("focus") is not None:
            cur.variant(str(upd["focus"]))
        variants = [v.model_copy() for v in cur.variants]
        for vp in data.get("variants") or []:
            v = next((x for x in variants if x.id == vp.get("id")), None)
            if v is None:
                raise ValueError(f"no variant {vp.get('id')!r}")
            if "note" in vp:
                v.note = str(vp["note"])[:400]
        idea = Idea.model_validate({**cur.model_dump(), **upd, "variants": [v.model_dump() for v in variants]})
        if "name" in upd and groups is not None and idea.group_id in groups.groups:
            groups.update(idea.group_id, name=f"{idea.name} · idea")
        return self._save(idea)

    def add_variant(self, iid: str, asset_id: str, groups: GroupStore) -> tuple[Idea, Variant]:
        """*Add to ‹idea›*, *Add as a variant* (CW2), a picture dropped on its card: copied onto the idea's page, in focus."""
        cur = self._require(iid)
        aid, src = self._copy(groups, asset_id, cur.group_id)
        v = Variant(asset_id=aid, made_from=src)
        if not cur.variants:
            groups.update(cur.group_id, cover_id=aid)
        return self._save(cur.model_copy(update={"variants": [*cur.variants, v], "focus": v.id})), v

    def remove_variant(self, iid: str, vid: str) -> Idea:
        """The variant leaves the idea; its picture stays on the idea's page (nothing is trashed)."""
        cur = self._require(iid)
        cur.variant(vid)
        rest = [v for v in cur.variants if v.id != vid]
        focus = cur.focus if cur.focus != vid else (rest[-1].id if rest else None)
        return self._save(cur.model_copy(update={"variants": rest, "focus": focus}))

    def set_clay(self, iid: str, vid: str, **fields: Any) -> Idea:
        """A variant's clay as its jobs land (no revision guard: a product of the variant, like a version's shell)."""
        cur = self._require(iid)
        variants = [v.model_copy() for v in cur.variants]
        v = next((x for x in variants if x.id == vid), None)
        if v is None:
            raise KeyError(f"no variant {vid!r}")
        clay = (v.clay or VariantClay()).model_dump()
        v.clay = VariantClay.model_validate({**clay, **fields})
        return self._save(cur.model_copy(update={"variants": variants}))

    def add_made_for(self, iid: str, asset_ids: list[str]) -> Idea | None:
        """CW2: results made while Image's For chip named the idea — listed, newest first (never a variant by themselves, U4)."""
        cur = self.get(iid)
        if cur is None:
            return None
        fresh = [a for a in reversed(asset_ids) if a not in cur.made_for]
        return self._save(cur.model_copy(update={"made_for": (fresh + cur.made_for)[:MADE_FOR_MAX]}))

    def record_kept(self, iid: str, kept: Kept) -> Idea:
        cur = self._require(iid)
        return self._save(cur.model_copy(update={"kept": [*cur.kept, kept]}))

    def delete(self, iid: str) -> Idea:
        """The record goes; its page and pictures stay in the album (as a deleted profile's do)."""
        cur = self._require(iid)
        self.path(iid).unlink()
        return cur


# ---- Make the clay ▶ (CW1; 06 §2.3): a character variant's figure, then its shell ----------------------------------------------------
def plan_clay(idea: Idea, v: Variant, variant: str, *, width: int, height: int) -> tuple[dict[str, Any], JobOrigin]:
    """The first step: the A-pose picture drawn from the variant (the clay-reference model with the variant's picture as reference 1, the
    subject from its prompt and CA0's reference sentence, D140's open hands). Its landing queues the fit, the fit the shell."""
    from .story import anim_ref_sentence, expand_spec
    if idea.cls != "character":
        raise ValueError("Make the clay ▶ gives a character's variant its figure — a prop's model and a place's set come with CW4 and CW6")
    spec = expand_spec(variant)
    if spec is None:
        raise ValueError("no model in this build draws the A-pose picture")
    subject = draft_sheet(v.made_from.prompt).get("appearance") or idea.name
    recipe = {"kind": "t2i", "model_id": spec.id, "prompt_mode": "text", "prompt_text": f"{subject}, the same character as the reference. "
              + anim_ref_sentence("character", "front"), "width": width, "height": height, "seeds": [0], "tier": "draft",
              "refs": [{"asset_id": v.asset_id, "note": "the character"}]}
    return recipe, idea_clay_origin(idea.id, v.id, "aref")


def _broadcast(q: Any, idea: Idea | None, **extra: Any) -> None:
    if idea is not None:
        q.hub.broadcast("story.changed", {"kind": "idea", "id": idea.id, "revision": idea.revision, **extra})


def clay_aref_landed(q: Any, job: Any, asset_id: str) -> None:
    """The A-pose picture: on the idea's page, the variant's; the fit queued. Never the job's failure (the variant shows the error)."""
    iid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("variant") or "")
    store = IdeaStore(q.ws)
    try:
        idea = store.get(iid)
        if idea is None:
            return
        if q.groups is not None and idea.group_id in q.groups.groups:
            q.groups.move([("asset", asset_id)], idea.group_id)
            q.hub.broadcast("group.changed", {"ids": [idea.group_id]})
        fit = q.submit({"kind": "keypoints", "asset_id": asset_id}, origin=idea_clay_origin(iid, vid, "fit"))
        _broadcast(q, store.set_clay(iid, vid, step="fitting", anim_ref_asset_id=asset_id, body=None, body_points=None, note=None,
                                     shell_asset_id=None, job_id=fit[0].id, error=None))
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the variant's clay stopped: {e}")
        try:
            _broadcast(q, store.set_clay(iid, vid, step="failed", error=f"the fit was not queued: {e}"))
        except Exception:  # noqa: BLE001
            pass


def clay_fit_landed(q: Any, job: Any, recipe: Any, people: list[dict]) -> None:
    """The fit (D104's, on the A-pose picture): the body and its points on the variant; an arms-down picture fits nothing (D140) and the
    chain stops with the way out; otherwise the shell is queued (Pixal3D, full only — without it the figure is the clay)."""
    from .body import Body, body_points, fit_body, reference_ratios, stance_note
    from .models import registry
    iid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("variant") or "")
    store = IdeaStore(q.ws)
    if not people:
        _broadcast(q, store.set_clay(iid, vid, step="failed", error="no figure found in the A-pose picture — make the clay again"))
        raise ValueError("no figure found in the A-pose picture")
    note = stance_note(people[0])
    if note == "arms_close":
        _broadcast(q, store.set_clay(iid, vid, step="failed", note=note, error="the picture holds its arms against the body: make the clay again for a new A-pose"))
        raise ValueError("the A-pose picture holds its arms against the body (D140)")
    body, report = fit_body(reference_ratios(people[0]), Body(), ())
    pts = body_points(people[0], job.result.get("canvas"))
    job.result["body"], job.result["fit"] = body.model_dump(), report
    spec = next((s for s in registry.mesh_specs() if registry.offered(s, getattr(job, "variant", None))), None)
    if spec is None:
        _broadcast(q, store.set_clay(iid, vid, step="done", body=body.model_dump(), body_points=pts, note=note, job_id=None, error=None))
        return
    shell = q.submit({"kind": "image_to_mesh", "asset_id": recipe.asset_id, "model_id": spec.id}, origin=idea_clay_origin(iid, vid, "shell"))
    _broadcast(q, store.set_clay(iid, vid, step="shell", body=body.model_dump(), body_points=pts, note=note, job_id=shell[0].id, error=None))


def clay_shell_landed(q: Any, job: Any, mesh_id: str) -> None:
    iid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("variant") or "")
    try:
        _broadcast(q, IdeaStore(q.ws).set_clay(iid, vid, step="done", shell_asset_id=mesh_id, job_id=None, error=None))
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"the shell was not set on the variant: {e}")


def clay_failed(q: Any, job: Any, msg: str) -> None:
    """A step's job failed or was cancelled: the variant says so (the clay made so far stays). Never raises."""
    try:
        iid, vid = str(job.origin.ref or ""), str((job.origin.payload or {}).get("variant") or "")
        store = IdeaStore(q.ws)
        idea = store.get(iid)
        if idea is None or not any(v.id == vid and v.clay and v.clay.job_id == job.id for v in idea.variants):
            return
        _broadcast(q, store.set_clay(iid, vid, step="failed", job_id=None, error=msg[:400]))
    except Exception:  # noqa: BLE001
        pass


def made_for_landed(q: Any, job: Any, asset_ids: list[str]) -> None:
    """CW2: results made while Image's For chip named an idea are listed on it. Never the job's failure."""
    iid = (job.origin.payload or {}).get(FOR_IDEA) if job.origin else None
    if not isinstance(iid, str) or not asset_ids:
        return
    try:
        _broadcast(q, IdeaStore(q.ws).add_made_for(iid, asset_ids))
    except Exception as e:  # noqa: BLE001
        job.log_tail.append(f"not listed on the idea: {e}")


# ---- Keep ▶ (CW1; 06 §2.1) ------------------------------------------------------------------------------------------------------------
def keep(ws: Workspace, groups: GroupStore, iid: str, vid: str, profile_id: str | None = None, name: str | None = None) -> tuple[Any, Idea]:
    """A variant kept: a new Cast profile (v1) — or a new version of `profile_id` — with the variant's picture (a copy) as the hero, a sheet
    drafted from its prompt, its clay carried over (the A-pose picture as the animation reference, the fitted body and its points, the
    shell), `from_idea` on the version; the idea records where it went and stays on the board."""
    from .story import StoryStore
    store, stories = IdeaStore(ws), StoryStore(ws)
    idea = store._require(iid)
    v = idea.variant(vid)
    if profile_id is not None and (stories.profile(profile_id) or None) is None:
        raise KeyError(profile_id)
    hero = groups.cat.duplicate(v.asset_id)
    if hero is None:
        raise ValueError("the variant's picture is missing")
    sheet = draft_sheet(v.made_from.prompt)
    if profile_id is None:
        p = stories.create_profile((name or idea.name).strip() or idea.name, idea.cls, groups, hero.id, **sheet)
        ver = p.version()
    else:
        cur = stories.profile(profile_id)
        if cur.cls != idea.cls:
            raise ValueError(f"a {idea.cls} idea is kept as a {idea.cls}, not as a {cur.cls}")
        p = stories.new_version(profile_id, groups)
        ver = p.version()
        groups.move([("asset", hero.id)], ver.group_id)
        groups.update(ver.group_id, cover_id=hero.id)
        p = stories.patch_profile(p.id, {"versions": [{"id": ver.id, "hero_asset_id": hero.id, **sheet}]})
        ver = p.version(ver.id)
    clay = v.clay
    aref = None
    if clay and clay.anim_ref_asset_id:
        dup = groups.cat.duplicate(clay.anim_ref_asset_id)
        if dup is not None:
            groups.move([("asset", dup.id)], ver.group_id)
            aref = dup.id
    p = stories.set_kept_from_idea(p.id, ver.id, {"idea_id": idea.id, "variant_id": v.id},
                                   anim_ref_asset_id=aref,
                                   body=clay.body if clay and idea.cls == "character" else None,
                                   body_points=clay.body_points if clay and aref else None,
                                   note=clay.note if clay and aref else None,
                                   shell_asset_id=clay.shell_asset_id if clay and idea.cls == "character" else None)
    if clay and idea.cls == "prop" and clay.model_asset_id:                         # CW3: a prop's model and height (Prototype ▸ on a mesh)
        p = stories.set_model(p.id, ver.id, clay.model_asset_id, None)
        if clay.height_m:
            p = stories.patch_profile(p.id, {"versions": [{"id": ver.id, "height_m": clay.height_m}]})
    idea = store.record_kept(iid, Kept(profile_id=p.id, version_id=ver.id, variant_id=v.id))
    return p, idea
