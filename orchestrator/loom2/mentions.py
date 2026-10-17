"""D73 (ArtCraft P12): `@`mentions of album groups resolve to reference images.

A T2I recipe's `mentions` name groups; on submit and preview each unresolved mention becomes references: the group's cover first, then
its assets in page order (top to bottom, left to right), skipping trashed assets and ones already referenced. Mentions take turns so
two groups both get images, and they only fill the room the model has left after the explicit references (`refs_max`) — a mention
never pushes a reference out. Each reference it adds carries the group's name as its note ("Image 2 shows the hero") and the group id
in `mention`; the mention is stamped with the group's revision and the asset ids it gave (lineage at write time, loom lesson 7). A
stamped mention is not resolved again, so re-running a stored recipe uses the same images. The Story workspace (14) will resolve
AssetProfiles behind the same function. D93 (A3): after the turns, each mention's images are put together (a linked subject's first, in
subject order) so the prompt can bind a subject to its range; the images left out for room are stamped as `skipped`. D93 (B4): a subject
card linked to a profile carries no words of its own — its description is composed here from the chosen version's sheet and the card's
per-shot override (`Mention.shot`), written into the subject and stamped on the mention (`composed`), so Cast's edits follow and the
recipe keeps what ran. D93 (C6): a Cast place linked to the Tree's scene (`Mention.scene`) composes the scene's text the same way (its sheet
+ this shot's line); a prop held by a subject card (`Mention.held_by`) puts its clause under the subject's `holding` (the serialiser says
"holding …" and binds its images); the images sit subject by subject, each holder's prop after it, the place after the subjects. D93 (C8):
`resolve_figures` does the same for a StageShot's figures bound to characters (left to right), within the method's room after the deck.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .recipes import Mention, RefImage, StageShot, T2I, LoraRef

if TYPE_CHECKING:
    from .catalogue import Catalogue
    from .groups import GroupStore
    from .story import StoryStore


def candidates(groups: GroupStore, catalogue: Catalogue, gid: str) -> list[str]:
    """A group's assets as references: the cover, then the page's assets by position (y, then x); trashed ones skipped."""
    g = groups.groups.get(gid)
    if g is None:
        raise ValueError(f"mentioned group {gid} does not exist")
    live = lambda aid: (r := catalogue.get(aid)) is not None and r.trashed_at is None and r.kind == "image"  # noqa: E731
    out = [g.cover_id] if g.cover_id and live(g.cover_id) else []
    for it in sorted(g.items, key=lambda it: (it.y, it.x)):
        if it.kind == "asset" and it.id not in out and live(it.id):
            out.append(it.id)
    return out


def resolve_mentions(recipe: T2I, groups: GroupStore | None, catalogue: Catalogue | None, refs_max: int, story: StoryStore | None = None, roster: Any = None) -> T2I:
    """The recipe with its unresolved mentions turned into references and stamped. Without mentions it is returned unchanged. D85: a
    profile mention is first pointed at its version's reference group (the current one unless pinned), and its note carries the
    version's prompt stub ('Image 2 shows Mara, a wiry courier in a grey coat')."""
    todo = [m for m in recipe.mentions if m.revision is None]
    if not todo:
        return recipe
    if groups is None or catalogue is None:
        raise ValueError("mentions need an open project")
    from .story import compose_sheet
    stubs: dict[str, str] = {}
    pinned: dict[int, Mention] = {}
    subs = recipe.prompt_json.get("subjects") if recipe.prompt_mode in ("tree", "json") and isinstance(recipe.prompt_json, dict) else None
    composed: dict[int, str] = {}                                               # D93 (B4): subject index → the description it carries
    holding: dict[int, str] = {}                                                # D93 (C6): subject index → the clause of the prop it holds (one each)
    scene: str | None = None                                                    # D93 (C6): the linked place's composed scene
    triggers: dict[str, str] = {}                                               # LT3 (18 §3f): group id → the trigger of the LoRA the mention added
    loras = list(recipe.loras)
    trained = getattr(roster, "trained", {}) or {}
    base = None
    if roster is not None:
        from .loras import MAX_SLOTS, model_base
        base = model_base(recipe.model_id)
    for i, m in enumerate(recipe.mentions):
        if m.revision is not None or not m.profile_id:
            continue
        if story is None:
            raise ValueError("profile mentions need an open project")
        p = story.profile(m.profile_id)
        if p is None:
            raise ValueError(f"mentioned profile {m.profile_id} does not exist")
        try:
            v = p.version(m.version)
        except KeyError as e:
            raise ValueError(str(e)) from e
        added = None
        if v.lora and v.lora in trained and roster is not None:               # LT3: the version's LoRA rides along when the model takes its base
            fits = trained[v.lora]["base"] == base
            if fits and recipe.auto_lora and v.lora not in {l.model_id for l in loras} and len(loras) < MAX_SLOTS:
                loras.append(LoraRef(model_id=v.lora, strength=1.0))
                added = v.lora
                if v.trigger:
                    triggers[v.group_id] = v.trigger.strip()
        text = None
        if m.subject is not None and isinstance(subs, list) and m.subject < len(subs) and isinstance(subs[m.subject], dict):
            text = composed[m.subject] = compose_sheet(v, m.shot, p.name, p.cls)   # D93 (B4): the sheet of the version chosen + this shot
        elif m.held_by is not None and isinstance(subs, list) and m.held_by < len(subs) and isinstance(subs[m.held_by], dict) and m.held_by not in holding:
            text = holding[m.held_by] = compose_sheet(v, None, p.name, p.cls)   # D93 (C6): the prop's clause, said as "holding …" by the serialiser
        elif m.scene and isinstance(recipe.prompt_json, dict) and recipe.prompt_mode in ("tree", "json") and scene is None:
            text = scene = compose_sheet(v, m.shot, p.name, p.cls)              # D93 (C6): the place's sheet + this shot's line is the scene
        pinned[i] = Mention(group_id=v.group_id, name=m.name or p.name, profile_id=p.id, version=v.id, lora=added, lora_available=v.lora if v.lora in trained else None,
                            subject=m.subject, shot=m.shot, composed=text, scene=m.scene, held_by=m.held_by)
        sheet = compose_sheet(v, None, "", p.cls)                               # D85: the clause the references' note carries (the sheet, no shot)
        if sheet and sheet.lower() != (m.name or p.name).strip().lower():
            stubs[v.group_id] = sheet
    if composed or holding:                                                     # a linked card's own words (an old panel's copy) give way to the sheet
        tree = {**recipe.prompt_json, "subjects": [{**({"description": composed[k]} if k in composed else {}),
                                                    **{x: y for x, y in sub.items() if (x != "description" or k not in composed) and x != "holding"},
                                                    **({"holding": holding[k]} if k in holding else {})} if isinstance(sub, dict) else sub
                                                   for k, sub in enumerate(subs)]}
        recipe = recipe.model_copy(update={"prompt_json": tree})
    if scene is not None:                                                       # D93 (C6): the place is the scene (the card's own scene words were moved to its line)
        recipe = recipe.model_copy(update={"prompt_json": {**(recipe.prompt_json or {}), "scene": scene}})
    if pinned:
        recipe = recipe.model_copy(update={"mentions": [pinned.get(i, m) for i, m in enumerate(recipe.mentions)]})
        todo = [m for m in recipe.mentions if m.revision is None]
    if any(not m.group_id for m in todo):
        raise ValueError("a mention names a group or a profile")
    refs, stamped = _fill(recipe.refs, recipe.mentions, todo, groups, catalogue, refs_max, stubs, triggers, _bind_order)
    return recipe.model_copy(update={"refs": refs, "mentions": stamped, "loras": loras})


def _bind_order(m: Mention, i: int) -> tuple:
    """D93 (A3, C6): where a mention's images sit — each linked subject in subject order with the prop it holds right after it, then the
    place of the scene, then the rest as written."""
    if m.subject is not None:
        return (0, m.subject, 0, i)
    if m.held_by is not None:
        return (0, m.held_by, 1, i)
    return (1 if m.scene else 2, 0, 0, i)


def _fill(explicit: list[RefImage], mentions: list[Mention], todo: list[Mention], groups: GroupStore, catalogue: Catalogue, room_max: int,
          stubs: dict[str, str], triggers: dict[str, str], order_key: Any) -> tuple[list[RefImage], list[Mention]]:
    """The unresolved mentions' images after the explicit references, within `room_max`: the mentions take turns (each group's next image),
    then each mention's images sit together in `order_key` order (D93 A3: so a subject or a figure can name its own range); every mention is
    stamped with its group's revision, the images it gave and how many of its set were left out (`skipped`)."""
    refs = [r for r in explicit if not (r.mention and any(m.group_id == r.mention for m in todo))]   # a re-resolve replaces its own
    taken = {r.asset_id for r in refs if r.asset_id}
    queues = {m.group_id: [a for a in candidates(groups, catalogue, m.group_id)] for m in todo}
    given: dict[str, list[str]] = {m.group_id: [] for m in todo}
    names = {m.group_id: (m.name or groups.groups[m.group_id].name) for m in todo}
    room = max(0, room_max - len(refs))
    while room > 0 and any(queues.values()):
        for m in todo:                                                  # take turns: each group's next image
            q = queues[m.group_id]
            while q and q[0] in taken:
                q.pop(0)
            if not q or room <= 0:
                continue
            aid = q.pop(0)
            taken.add(aid)
            given[m.group_id].append(aid)
            stub = stubs.get(m.group_id)                                        # D85: the stub is the clause ('Mara, a wiry courier…'); it leads with the name or gets it
            note = names[m.group_id] if not stub else stub if stub.lower().startswith(names[m.group_id].lower()) else f"{names[m.group_id]}, {stub}"
            if m.group_id in triggers:                                          # LT3: the trigger word leads the note the prompt carries
                note = f"{triggers[m.group_id]}, {note}"
            refs.append(RefImage(asset_id=aid, note=note, mention=m.group_id))
            room -= 1
    # D93 (A3): the turns share the room fairly; then each mention's images sit together, so a subject can name its own range
    # ("reference images 1–3") — the explicit references keep their places in front
    order = sorted(range(len(todo)), key=lambda i: order_key(todo[i], i))
    mine = {m.group_id for m in todo}
    refs = [r for r in refs if r.mention not in mine] + [r for i in order for r in refs if r.mention == todo[i].group_id]
    skipped = {m.group_id: len([a for a in queues[m.group_id] if a not in taken]) for m in todo}
    stamped = [m if m.revision is not None else m.model_copy(update={"name": names[m.group_id], "revision": groups.groups[m.group_id].revision,
                                                                     "asset_ids": given[m.group_id], "skipped": skipped[m.group_id]})
               for m in mentions]
    return refs, stamped


def resolve_figures(recipe: StageShot, groups: GroupStore | None, catalogue: Catalogue | None, room: int, story: StoryStore | None) -> StageShot:
    """D93 (C8): a StageShot's figures bound to Cast characters — each mention (`figure` = the stage object, in screen order left to right)
    points at its version's reference set, composes the character's sheet (stamped `composed`, said in the prompt per figure) and gives
    images after the deck's own, within the method's room (`room`: clay the model's references less the pass, refcontrol one); the images
    sit figure by figure. A stamped mention is not resolved again (a re-run uses the same images)."""
    if not any(m.revision is None for m in recipe.mentions):
        return recipe
    if groups is None or catalogue is None or story is None:
        raise ValueError("bound figures need an open project")
    from .story import compose_sheet
    stubs: dict[str, str] = {}
    pinned: list[Mention] = []
    for m in recipe.mentions:
        if m.revision is not None:
            pinned.append(m)
            continue
        if not m.profile_id or not m.figure:
            raise ValueError("a figure binding names a stage figure and a Cast character")
        p = story.profile(m.profile_id)
        if p is None:
            raise ValueError(f"the character {m.profile_id} bound to figure {m.figure} does not exist")
        try:
            v = p.version(m.version)
        except KeyError as e:
            raise ValueError(str(e)) from e
        sheet = compose_sheet(v, None, "", p.cls)
        if sheet and sheet.lower() != p.name.strip().lower():
            stubs[v.group_id] = sheet
        pinned.append(m.model_copy(update={"group_id": v.group_id, "name": m.name or p.name, "version": v.id, "composed": compose_sheet(v, m.shot, p.name, p.cls)}))
    if len({m.group_id for m in pinned}) != len(pinned):
        raise ValueError("two figures are bound to the same character version — one figure per character")
    todo = [m for m in pinned if m.revision is None]
    refs, stamped = _fill(recipe.refs, pinned, todo, groups, catalogue, room, stubs, {}, lambda m, i: (i,))
    return recipe.model_copy(update={"refs": refs, "mentions": stamped})
