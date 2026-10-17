"""D73 (ArtCraft P12): `@`mentions of album groups resolve to reference images.

A T2I recipe's `mentions` name groups; on submit and preview each unresolved mention becomes references: the group's cover first, then
its assets in page order (top to bottom, left to right), skipping trashed assets and ones already referenced. Mentions take turns so
two groups both get images, and they only fill the room the model has left after the explicit references (`refs_max`) — a mention
never pushes a reference out. Each reference it adds carries the group's name as its note ("Image 2 shows the hero") and the group id
in `mention`; the mention is stamped with the group's revision and the asset ids it gave (lineage at write time, loom lesson 7). A
stamped mention is not resolved again, so re-running a stored recipe uses the same images. The Story workspace (14) will resolve
AssetProfiles behind the same function. D93 (A3): after the turns, each mention's images are put together (a linked subject's first, in
subject order) so the prompt can bind a subject to its range; the images left out for room are stamped as `skipped`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .recipes import Mention, RefImage, T2I, LoraRef

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
    stubs: dict[str, str] = {}
    pinned: dict[int, Mention] = {}
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
        pinned[i] = Mention(group_id=v.group_id, name=m.name or p.name, profile_id=p.id, version=v.id, lora=added, lora_available=v.lora if v.lora in trained else None,
                            subject=m.subject)
        if v.stub.strip() and v.stub.strip().lower() != (m.name or p.name).strip().lower():
            stubs[v.group_id] = v.stub.strip().rstrip(".")
    if pinned:
        recipe = recipe.model_copy(update={"mentions": [pinned.get(i, m) for i, m in enumerate(recipe.mentions)]})
        todo = [m for m in recipe.mentions if m.revision is None]
    if any(not m.group_id for m in todo):
        raise ValueError("a mention names a group or a profile")
    refs = [r for r in recipe.refs if not (r.mention and any(m.group_id == r.mention for m in todo))]   # a re-resolve replaces its own
    taken = {r.asset_id for r in refs if r.asset_id}
    queues = {m.group_id: [a for a in candidates(groups, catalogue, m.group_id)] for m in todo}
    given: dict[str, list[str]] = {m.group_id: [] for m in todo}
    names = {m.group_id: (m.name or groups.groups[m.group_id].name) for m in todo}
    room = max(0, refs_max - len(refs))
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
    # D93 (A3): the turns share the room fairly; then each mention's images sit together (subject order first), so a subject can name its
    # own range ("reference images 1–3") — the explicit references keep their places in front
    order = sorted(range(len(todo)), key=lambda i: (todo[i].subject is None, todo[i].subject if todo[i].subject is not None else 0, i))
    mine = {m.group_id for m in todo}
    refs = [r for r in refs if r.mention not in mine] + [r for i in order for r in refs if r.mention == todo[i].group_id]
    skipped = {m.group_id: len([a for a in queues[m.group_id] if a not in taken]) for m in todo}
    stamped = [m if m.revision is not None else Mention(group_id=m.group_id, name=names[m.group_id], revision=groups.groups[m.group_id].revision,
                                                        asset_ids=given[m.group_id], profile_id=m.profile_id, version=m.version, lora=m.lora, lora_available=m.lora_available,
                                                        subject=m.subject, skipped=skipped[m.group_id])
               for m in recipe.mentions]
    return recipe.model_copy(update={"refs": refs, "mentions": stamped, "loras": loras})
