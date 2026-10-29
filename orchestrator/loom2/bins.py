"""U2 (D157, G1; proto01_UI2 05 §2, 06 §1.2): the Bin — a tree of homes over the album's groups.

Every creation has one home, the path of what it was made for: `world/<class>/<profile>/<version>`, `world/look`, `world/sketches`,
`shots/<shot>`, `episode/<cut>`, `imports`. A home is a group of kind `bin` with its `path` (from ids, so a rename never breaks it); its
display name follows the record's. A version's two pages — its reference set and its candidates — are **role children** of its home
(kind `role`, `role: reference | candidates`): every reader of `v.group_id` keeps reading it, and to the author a picture stays in the bin
and gains a role. The album stays as it is around them.

`migrate_bins` runs once per project at open: each version's pages under its home, each style's samples under `world/look`, a Flow board
used by one Shot under its shot's home; then (U2e, bins schema 2) the Unprocessed assets whose origin names an owner go to its home.
Every finished job's assets land in their owner's home (`land`, from the queue's completion tail). An asset without an owner stays
unplaced until B4 (D159) retires Unprocessed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .fsio import atomic_write_json, read_json_or, unlink, utc_now
from .catalogue import AssetQuery
from .groups import ROOT_ID, GroupRecord, GroupStore

BINS_SCHEMA_VERSION = 2                            # U2e: 2 — the Unprocessed assets sorted by their origin
CLASS_HOME = {"character": "Characters", "prop": "Props", "place": "Places"}
NAMED = {"world": "World", "world/look": "Look", "world/sketches": "Sketches", "shots": "Shots", "episode": "Episode", "imports": "Imports",
         **{f"world/{c}": n for c, n in CLASS_HOME.items()}}


def home(groups: GroupStore, path: str, names: dict[str, str] | None = None) -> GroupRecord:
    """The home at `path`, made with its parents when missing (the top one on the album). `names` gives the segments' display names by
    path (an entity's, a version's); a home whose record was renamed takes the new name."""
    names = {**NAMED, **(names or {})}
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("a home has a path")
    with groups._lock:
        parent = ROOT_ID
        g: GroupRecord | None = None
        for i in range(len(parts)):
            sub = "/".join(parts[: i + 1])
            want = names.get(sub, parts[i])
            g = next((x for x in groups.groups.values() if x.kind == "bin" and x.path == sub), None)
            if g is None:
                g = groups.create(want, parent_id=parent, kind="bin", path=sub)
            elif sub in (names or {}) and g.name != want:
                g = groups.update(g.id, name=want)
            parent = g.id
        assert g is not None
        return g


def version_home(groups: GroupStore, profile: Any, vid: str) -> GroupRecord:
    """A profile version's home: `world/<class>/<profile id>/<version>` (the entity's name and the version's label for display)."""
    v = profile.version(vid)
    label = f"{v.id} · {v.label}" if getattr(v, "label", None) and v.label != v.id else v.id   # a version's label is its id when blank
    base = f"world/{profile.cls}/{profile.id}"
    return home(groups, f"{base}/{v.id}", {base: profile.name, f"{base}/{v.id}": label})


def as_role(groups: GroupStore, gid: str | None, under: GroupRecord, role: str) -> bool:
    """A page as a role child of a home (moved under it, marked). False when there is no such page or it is there already."""
    if not gid or gid not in groups.groups or gid == ROOT_ID:
        return False
    g = groups.groups[gid]
    moved = groups.parent.get(("group", gid)) != under.id
    if moved:
        groups.move([("group", gid)], under.id)
    if g.kind != "role" or g.role != role:
        groups.mark(gid, kind="role", role=role)
        moved = True
    return moved


def version_bin(groups: GroupStore, profile: Any, vid: str) -> dict[str, Any]:
    """U3 (D157, 03 §5): a version's bin as World shows it — one grid, newest first: the home's own assets and its role pages' (the
    reference set, the candidates), each with its roles (hero, reference, A-pose front / back, set picture, model; the rest candidates).
    A page that is not yet under the home (a project opened before U2) is read where it is."""
    v = profile.version(vid)
    h = version_home(groups, profile, v.id)
    pages = {h.id: "candidate", v.group_id: "reference"}
    if v.candidates_group_id:
        pages[v.candidates_group_id] = "candidate"
    ranked: list[tuple[str | None, str]] = [(v.hero_asset_id, "hero")]                  # the roles by class, the first the tile's badge
    if profile.cls == "character":
        ranked += [(v.anim_ref_asset_id, "a_pose_front"), (v.anim_ref_back_asset_id, "a_pose_back"), (v.shell_asset_id, "model")]
    elif profile.cls == "prop":
        ranked += [(v.model_asset_id, "model")]
    elif v.place_set is not None:
        ranked += [(src.asset_id, "set_picture") for src in v.place_set.sources]
    special: dict[str, list[str]] = {}
    for aid, role in ranked:
        if aid and role not in special.setdefault(aid, []):
            special[aid].append(role)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gid, role in pages.items():
        g = groups.groups.get(gid)
        if g is None:
            continue
        for it in g.items:
            if it.kind != "asset" or it.id in seen:
                continue
            a = groups.cat.get(it.id)
            if a is None or a.trashed_at is not None:
                continue
            seen.add(it.id)
            roles = [role] if role != "reference" or it.id != v.hero_asset_id else []
            if it.id in special:
                roles = [*special[it.id], *[r for r in roles if r != "candidate"]]
            items.append({"asset": a, "roles": roles, "page": gid})
    items.sort(key=lambda x: x["asset"].created_at, reverse=True)
    return {"home_id": h.id, "path": h.path, "reference_id": v.group_id, "candidates_id": v.candidates_group_id, "items": items}


def owner_home(groups: GroupStore, ws: Any, origin: Any) -> GroupRecord | None:
    """U2e (G1): the home of what an origin was made for — a shot version (made for it, its lip-sync, a line's voice, a final made for it)
    or a profile version (a Cast job: the set fit and its Fill, the anim test, the body fit, the prop's model, a check …); None when it
    names no owner (Image's free work, an import, a stage's own passes)."""
    if origin is None:
        return None
    o = origin if isinstance(origin, dict) else origin.model_dump()
    p = o.get("payload") or {}
    ref, surface, suite = o.get("ref") or "", o.get("surface") or "", o.get("suite") or ""
    from .story import FOR_SHOT, StoryStore
    st = StoryStore(ws)
    shot, version = None, None
    if surface == FOR_SHOT and isinstance(p.get("shot_id"), str):
        shot, version = p["shot_id"], p.get("version")
    elif suite == "story" and surface == "lipsync" and ref.startswith("sht_"):
        shot, version = ref, p.get("version")
    elif suite == "story" and surface == "voice" and ref.startswith("node_"):
        n = st.flow_node(ref)
        shot = n.shot_id if n is not None else None
    elif suite == "stage" and ref.startswith("fin_"):
        from .finals import FinalStore
        f = FinalStore(ws).get(ref)
        shot, version = (f.shot_id, f.shot_version) if f is not None else (None, None)
    elif suite == "animate" and surface == "sequence" and ref.startswith("tl_"):     # U8: a cut's movie or draft lands in its home
        from .timelines import TimelineStore
        tl = TimelineStore(ws).get(ref)
        return home(groups, f"episode/{tl.id}", {f"episode/{tl.id}": tl.name}) if tl is not None else None
    elif suite == "story" and ref.startswith("prf_"):
        prof = st.profile(ref)
        if prof is None:
            return None
        vid = p.get("version") if isinstance(p.get("version"), str) and any(v.id == p.get("version") for v in prof.versions) else prof.current
        return version_home(groups, prof, vid)
    if not shot:
        return None
    s = st.shot(shot)
    if s is None:
        return None
    vid = version if isinstance(version, str) and any(v.id == version for v in s.versions) else s.current
    return home(groups, f"shots/{s.id}/{vid}", {f"shots/{s.id}": s.name, f"shots/{s.id}/{vid}": vid})


def land(groups: GroupStore, ws: Any, origin: Any, asset_ids: list[str]) -> GroupRecord | None:
    """U2e (G1): a finished job's assets that no page took yet go to their owner's home (a page a finisher chose — Expand's candidates,
    a style's group — keeps them). The home, or None."""
    loose = [a for a in asset_ids if ("asset", a) not in groups.parent and groups.cat.get(a) is not None]
    if not loose:
        return None
    h = owner_home(groups, ws, origin)
    if h is not None:
        groups.move([("asset", a) for a in loose], h.id)
    return h


# ---- U8 (D157, proto01_UI2 05 §2): the Bin as a place — its tree, a home's things with their roles, a search across every home ------
ORDER = ["world", "world/character", "world/prop", "world/place", "world/look", "world/sketches", "shots", "episode", "imports"]
KIND_ROLE = {"reference": "reference", "candidates": "candidate"}   # a role page's role as its things carry it (World's names)


def _rank(g: GroupRecord) -> tuple[int, str]:
    path = g.path or ""
    return (ORDER.index(path) if path in ORDER else len(ORDER), g.name.lower())


def _live(groups: GroupStore, g: GroupRecord) -> list[str]:
    out: list[str] = []
    for it in g.items:
        if it.kind == "asset":
            a = groups.cat.get(it.id)
            if a is not None and a.trashed_at is None:
                out.append(it.id)
    return out


def _inside(groups: GroupStore, g: GroupRecord) -> tuple[list[GroupRecord], list[GroupRecord]]:
    """A home's pages (its role pages, an album page inside it) and the homes under it."""
    kids = [groups.groups[it.id] for it in g.items if it.kind == "group" and it.id in groups.groups]
    return [k for k in kids if k.kind != "bin"], sorted((k for k in kids if k.kind == "bin"), key=_rank)


MADE = {"model", "set_picture", "final", "clip"}         # B0 (D159 Q5): a role a job built its record on — the thing stays with it
CHOSEN = {"hero", "a_pose_front", "a_pose_back", "frame"}   # a role the author chose — moved out of its home, it is dropped (asked first)


class _Records:
    """The records one read of the Bin needs, each read once (a page of 200 things in 30 shot homes reads the shots once, not 30 times)."""

    def __init__(self, ws: Any) -> None:
        from .story import StoryStore
        self.ws, self.st = ws, StoryStore(ws)
        self._profiles: dict[str, Any] | None = None
        self._shots: dict[str, Any] | None = None
        self._finals: list[Any] | None = None
        self._clips: Any = None

    def profile(self, pid: str) -> Any:
        if self._profiles is None:
            self._profiles = {p.id: p for p in self.st.profiles()}
        return self._profiles.get(pid)

    def shot(self, sid: str) -> Any:
        if self._shots is None:
            self._shots = {s.id: s for s in self.st.shots()}
        return self._shots.get(sid)

    def finals(self) -> list[Any]:
        if self._finals is None:
            from .finals import FinalStore
            self._finals = FinalStore(self.ws).list()
        return self._finals

    def clips(self) -> Any:
        if self._clips is None:
            from .clips import ClipStore
            self._clips = ClipStore(self.ws)
        return self._clips


def _record_roles(ws: Any, path: str, rec: _Records | None = None) -> tuple[dict[str, list[str]], bool] | None:
    """The roles a home's record gives its things by id — a version's (hero, A-pose front / back, model, set pictures), a shot version's
    (its final, the frame and the clip it uses) — and whether it is a version's home (its loose things are candidates). None for any
    other home, or a record that is gone. Read from the records alone (no asset is loaded)."""
    parts = path.split("/")
    rec = rec or _Records(ws)
    out: dict[str, list[str]] = {}

    def add(aid: str | None, role: str) -> None:
        if aid and role not in out.setdefault(aid, []):
            out[aid].append(role)
    if len(parts) == 4 and parts[0] == "world":
        prof = rec.profile(parts[2])
        v = next((x for x in prof.versions if x.id == parts[3]), None) if prof is not None else None
        if v is None:
            return None
        add(v.hero_asset_id, "hero")
        if prof.cls == "character":
            add(v.anim_ref_asset_id, "a_pose_front")
            add(v.anim_ref_back_asset_id, "a_pose_back")
            add(v.shell_asset_id, "model")
        elif prof.cls == "prop":
            add(v.model_asset_id, "model")
        elif v.place_set is not None:
            for src in v.place_set.sources:
                add(src.asset_id, "set_picture")
        return out, True
    if len(parts) == 3 and parts[0] == "shots":
        s = rec.shot(parts[1])
        v = next((x for x in s.versions if x.id == parts[2]), None) if s is not None else None
        if v is None:
            return None
        clips = rec.clips()
        for f in rec.finals():
            if f.shot_id == s.id and (f.shot_version or s.current) == v.id and f.clip_id:
                rec = clips.get(f.clip_id)
                add(rec.asset_id if rec else None, "final")
        add(v.frame_asset_id, "frame")
        rec = clips.get(v.clip_id) if v.clip_id else None
        add(rec.asset_id if rec else None, "clip")
        return out, False
    return None


def roles_of(aid: str, page_role: str | None, record: tuple[dict[str, list[str]], bool] | None) -> list[str]:
    """A thing's roles in its home, as World's version bin gives them: its record's (the hero, …) first, then its page's (a reference, a
    sample, a board); a version's other things are its candidates. A hero on the reference page is the hero only."""
    special, version = record if record is not None else ({}, False)
    mine = special.get(aid, [])
    base = [page_role] if page_role else (["candidate"] if version else [])
    if page_role == "reference" and "hero" in mine:
        base = []
    return [*mine, *[r for r in base if r != "candidate"]] if mine else base


def _pages_of(groups: GroupStore, top: GroupRecord) -> dict[str, tuple[GroupRecord, str | None]]:
    """Every page a home's listing reads — the home, its role pages, every home under it with theirs — with its home and its role."""
    out: dict[str, tuple[GroupRecord, str | None]] = {}

    def walk(g: GroupRecord) -> None:
        out[g.id] = (g, None)
        pages, subs = _inside(groups, g)
        for p in pages:
            out[p.id] = (g, KIND_ROLE.get(p.role or "", p.role) if p.kind == "role" else None)
        for h in subs:
            walk(h)
    walk(top)
    return out


def _names(ws: Any) -> dict[str, str]:
    """B0 (R5): each record home's name by its path, read from the records now — a rename shows at once; a path missing here whose
    segment is a record's id (an entity, a shot, a cut) is a home whose record is gone."""
    from .story import StoryStore
    from .timelines import TimelineStore
    st = StoryStore(ws)
    out: dict[str, str] = {}
    for p in st.profiles():
        base = f"world/{p.cls}/{p.id}"
        out[base] = p.name
        for v in p.versions:
            out[f"{base}/{v.id}"] = f"{v.id} · {v.label}" if getattr(v, "label", None) and v.label != v.id else v.id
    for s in st.shots():
        out[f"shots/{s.id}"] = s.name
        for v in s.versions:
            out[f"shots/{s.id}/{v.id}"] = v.id
    for tl in TimelineStore(ws).list():
        out[f"episode/{tl.id}"] = tl.name
    return out


def _is_record(path: str) -> bool:
    return any(seg.startswith(("prf_", "sht_", "tl_")) for seg in path.split("/"))


def tree(groups: GroupStore, ws: Any = None) -> dict[str, Any]:
    """U8 (05 §2.1): the Bin's tree — each home {id, path, name, count, total, pages, gone, children}: its count is its own live things
    and its role pages' (a version's reference set and candidates are roles inside it, not places), its total adds the homes under it;
    `imports` counts the things on no page too. B0: the counts come from the index (no thing is read); a record home is named as its
    record is now, and one whose record was deleted is `gone` (hidden once nothing is left in it). The Trash's count beside it."""
    counts = groups.cat.counts()
    placed = groups.cat.placed_counts()
    loose = counts.get("unprocessed", 0)
    names = _names(ws) if ws is not None else {}
    with groups._lock:

        def node(g: GroupRecord) -> dict[str, Any] | None:
            pages, subs = _inside(groups, g)
            path = g.path or ""
            count = placed.get(g.id, 0) + sum(placed.get(p.id, 0) for p in pages) + (loose if path == "imports" else 0)
            kids = [k for k in (node(h) for h in subs) if k is not None]
            gone = ws is not None and _is_record(path) and path not in names
            total = count + sum(k["total"] for k in kids)
            if gone and not total:
                return None
            return {"id": g.id, "path": path, "name": names.get(path, g.name), "count": count, "total": total, "gone": gone,
                    "pages": [p.id for p in pages], "children": kids}

        def top(g: GroupRecord) -> bool:
            par = groups.groups.get(groups.parent.get(("group", g.id)) or "")
            return par is None or par.kind != "bin"
        tops = sorted((g for g in groups.groups.values() if g.kind == "bin" and top(g)), key=_rank)
        return {"homes": [n for n in (node(g) for g in tops) if n is not None], "trash": counts.get("trash", 0)}


def home_page(groups: GroupStore, ws: Any, gid: str, cursor: str | None = None, limit: int = 200, kinds: list[str] | None = None) -> dict[str, Any]:
    """U8 (05 §2.2), paged in B0: what a home holds — its own things and its pages', and everything in the homes under it (a parent shows
    all below it), newest first, a page at a time (`next_cursor`), each with its roles and its home; `imports` holds the things on no
    page too. `kinds` keeps those kinds only. `total` comes with the first page."""
    with groups._lock:
        top = groups.groups.get(gid)
        if top is None or top.kind != "bin":
            raise KeyError(gid)
        pages = _pages_of(groups, top)
        imports = next((g for g in groups.groups.values() if g.kind == "bin" and g.path == "imports"), None)
        loose = imports is not None and imports.id in pages
    page = groups.cat.list(AssetQuery(group_ids=list(pages), unplaced_too=loose, kinds=kinds or [], limit=limit, cursor=cursor))  # type: ignore[arg-type]
    rec = _Records(ws)
    records: dict[str, tuple[dict[str, list[str]], bool] | None] = {}
    items = []
    with groups._lock:
        for a in page.items:
            at = pages.get(groups.parent.get(("asset", a.id)) or "")
            h, role = at if at is not None else (imports, None)
            if h is None:
                continue
            if h.id not in records:
                records[h.id] = _record_roles(ws, h.path or "", rec)
            items.append({"asset": a, "roles": roles_of(a.id, role, records[h.id]), "home_id": h.id, "path": h.path or ""})
    return {"home_id": top.id, "path": top.path or "", "items": items, "total": page.total, "next_cursor": page.next_cursor}


def home_items(groups: GroupStore, ws: Any, gid: str) -> dict[str, Any]:
    """A home's things, every page of them (the checks; the Bin reads `home_page`)."""
    out = home_page(groups, ws, gid, limit=2000)
    while out["next_cursor"]:
        more = home_page(groups, ws, gid, cursor=out["next_cursor"], limit=2000)
        out = {**out, "items": [*out["items"], *more["items"]], "next_cursor": more["next_cursor"]}
    return out


def home_of(groups: GroupStore, gid: str | None) -> GroupRecord | None:
    """The home a page is in (a home is its own); None for no page or a page in no home."""
    while gid and gid in groups.groups:
        g = groups.groups[gid]
        if g.kind == "bin":
            return g
        gid = groups.parent.get(("group", gid))
    return None


def move_things(groups: GroupStore, ws: Any, ids: list[str], to: str, confirm: bool = False) -> dict[str, Any]:
    """B0 (D159 Q5, R6): things moved to another home. A thing that leaves its home loses its roles there: a role the author chose (the
    hero, an A-pose, a shot's frame) or a page's (a reference, a style's sample, a board) is named in `ask` and the thing stays, unless
    `confirm` — then the record lets go of it (the hero cleared, …) and it moves; a role a job built its record on (a 3D model, a set's
    picture, a final, a shot's clip) is `refused`, and so is a final version's hero. Within its home a thing just moves."""
    rec = _Records(ws)
    st = rec.st
    target = home_of(groups, to)
    if to not in groups.groups or target is None:
        raise KeyError(to)
    plain: list[str] = []
    ask: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    drops: list[tuple[str, str, str]] = []                        # (asset, role, the home's path)
    with groups._lock:
        for aid in ids:
            if groups.cat.get(aid) is None:
                continue
            page = groups.parent.get(("asset", aid))
            h = home_of(groups, page)
            if h is None or h.id == target.id:
                plain.append(aid)
                continue
            g = groups.groups.get(page or "")
            page_role = KIND_ROLE.get(g.role or "", g.role) if g is not None and g.kind == "role" else None
            roles = [r for r in roles_of(aid, page_role, _record_roles(ws, h.path or "", rec)) if r != "candidate"]
            made = [r for r in roles if r in MADE]
            locked = [r for r in roles if r == "hero" and _version_locked(st, h.path or "")]
            if made or locked:
                refused.append({"id": aid, "role": (made or locked)[0], "home": h.path or "",
                                "why": "its record is made on it" if made else "its version is final"})
                continue
            if roles and not confirm:
                ask.append({"id": aid, "roles": roles, "home": h.path or ""})
                continue
            drops += [(aid, r, h.path or "") for r in roles if r in CHOSEN]
            plain.append(aid)
    for aid, role, path in drops:
        _drop_role(st, path, aid, role)
    changed = groups.move([("asset", a) for a in plain], to) if plain else set()
    return {"moved": plain, "ask": ask, "refused": refused, "dropped": [{"id": a, "role": r, "home": p} for a, r, p in drops],
            "changed": sorted(changed), "records": sorted({p.split("/")[2] if p.startswith("world/") else p.split("/")[1] for _, _, p in drops})}


def _version_locked(st: Any, path: str) -> bool:
    parts = path.split("/")
    if len(parts) != 4 or parts[0] != "world":
        return False
    prof = st.profile(parts[2])
    v = next((x for x in prof.versions if x.id == parts[3]), None) if prof is not None else None
    return v is not None and v.state != "open"


def _drop_role(st: Any, path: str, aid: str, role: str) -> None:
    """The record lets go of a thing that left its home (B0, D159 Q5)."""
    parts = path.split("/")
    if parts[0] == "world" and len(parts) == 4:
        prof = st.profile(parts[2])
        if prof is None:
            return
        if role == "hero":
            st.patch_profile(prof.id, {"versions": [{"id": parts[3], "hero_asset_id": None}]})
        elif role in ("a_pose_front", "a_pose_back"):
            st.set_anim_ref(prof.id, parts[3], "back" if role == "a_pose_back" else "front", None)
    elif parts[0] == "shots" and len(parts) == 3 and role == "frame":
        vid = parts[2]

        def fn(part: Any, _r: Any) -> Any:
            part.versions = [v.model_copy(update={"frame_asset_id": None}) if v.id == vid and v.frame_asset_id == aid else v for v in part.versions]
            return part
        st._change_part(parts[1], fn)


def rehome(groups: GroupStore, gid: str, to_path: str = "world/sketches") -> dict[str, Any]:
    """B0 (R5): a home whose record was deleted gives its things (the Trash's that were in it too) to another home — the Sketches — and
    goes with its pages."""
    with groups._lock:
        g = groups.groups.get(gid)
        if g is None or g.kind != "bin":
            raise KeyError(gid)
        ids = [it.id for sub in [gid, *groups._descendants(gid)] for it in groups.groups[sub].items if it.kind == "asset"]
        parent = groups.parent.get(("group", gid))
    dest = home(groups, to_path)
    changed = groups.move([("asset", a) for a in ids], dest.id) if ids else set()
    groups.delete(gid)
    return {"moved": len(ids), "to": dest.id, "changed": sorted({*changed, dest.id, *([parent] if parent else [])})}


def subtree_pages(groups: GroupStore, gid: str) -> tuple[list[str], bool]:
    """U8 (05 §2.3): the pages a home's listing reads — the home, its role pages and every home under it with theirs — and whether it
    reads what is on no page too (the imports home)."""
    with groups._lock:
        top = groups.groups.get(gid)
        if top is None:
            return [], False
        out: list[str] = []

        def walk(g: GroupRecord) -> None:
            out.append(g.id)
            pages, subs = _inside(groups, g)
            out.extend(p.id for p in pages)
            for h in subs:
                walk(h)
        walk(top)
        return out, top.kind == "bin" and top.path == "imports"


def where(groups: GroupStore, aid: str) -> GroupRecord | None:
    """The home an asset is in (its page, or the home above its page); None on no page."""
    gid = groups.parent.get(("asset", aid))
    while gid and gid in groups.groups:
        g = groups.groups[gid]
        if g.kind == "bin":
            return g
        gid = groups.parent.get(("group", gid))
    return None


def search(groups: GroupStore, q: str, limit: int = 200) -> dict[str, Any]:
    """U8 (05 §2.2): a search across every home — the prompt, the name and the tags (the catalogue's full-text search), and a seed when
    the words are a number — each thing with its home (`imports` when it is on no page)."""
    q = q.strip()
    if not q:
        return {"home_id": None, "path": "", "items": []}
    found = {a.id: a for a in groups.cat.list(AssetQuery(search=q, limit=limit)).items}
    if q.isdigit():
        found.update({a.id: a for a in groups.cat.list(AssetQuery(seed=int(q), limit=limit)).items})
    with groups._lock:
        imports = next((g for g in groups.groups.values() if g.kind == "bin" and g.path == "imports"), None)
        items = []
        for a in found.values():
            if a.trashed_at is not None:
                continue
            h = where(groups, a.id) or imports
            items.append({"asset": a, "roles": [], "home_id": h.id if h else None, "path": h.path if h else "imports"})
    items.sort(key=lambda x: x["asset"].created_at, reverse=True)
    return {"home_id": None, "path": "", "items": items[:limit]}


def _marker(ws: Any, groups: GroupStore) -> Path:
    """The migration's mark, `bins.json` at the project's root. U4: U2 wrote it into `groups/`, where the album read it as a torn group file
    and moved it aside at every open (so the migration ran again); such a mark — the file or its moved-aside copies, the newest — is taken
    over once and the copies removed (they were never groups)."""
    root = Path(getattr(ws, "path", Path(groups.dir).parent))
    marker = root / "bins.json"
    old = sorted(Path(groups.dir).glob("bins.json*"), key=lambda p: p.stat().st_mtime)
    if old:
        if not marker.is_file():
            for p in reversed(old):
                raw = read_json_or(p, None)
                if isinstance(raw, dict) and "schema_version" in raw and "id" not in raw:
                    atomic_write_json(marker, raw)
                    break
        for p in old:
            raw = read_json_or(p, None)
            if isinstance(raw, dict) and "id" not in raw:
                unlink(p)
    return marker


def migrate_bins(ws: Any, groups: GroupStore) -> list[str]:
    """Once per project (`bins.json`): the versions' pages, the styles' samples and the one-shot boards into their homes. Notes."""
    marker = _marker(ws, groups)
    done = read_json_or(marker, None)
    if isinstance(done, dict) and int(done.get("schema_version", 1)) >= BINS_SCHEMA_VERSION:
        return []
    if isinstance(done, dict):                                              # U2d's pages are in: only the Unprocessed assets are left
        notes = _sort_unprocessed(ws, groups)
        atomic_write_json(marker, {**done, "schema_version": BINS_SCHEMA_VERSION, "sorted_at": utc_now()})
        return notes
    from .story import StoryStore
    st = StoryStore(ws)
    pages = styles = boards = 0
    for p in st.profiles():
        for v in p.versions:
            h = version_home(groups, p, v.id)
            pages += int(as_role(groups, v.group_id, h, "reference"))
            pages += int(as_role(groups, v.candidates_group_id, h, "candidates"))
    look = None
    for s in st.world().styles:
        gid = getattr(s, "group_id", None)
        if gid and gid in groups.groups:
            look = look or home(groups, "world/look")
            styles += int(as_role(groups, gid, look, "sample"))
    by_board: dict[str, list[Any]] = {}
    for n in st.flow_nodes().values():
        if n.board_group_id and n.shot_id:
            by_board.setdefault(n.board_group_id, []).append(n)
    for gid, users in by_board.items():
        if len(users) == 1 and gid in groups.groups and groups.groups[gid].kind == "album":
            n = users[0]
            h = home(groups, f"shots/{n.shot_id}", {f"shots/{n.shot_id}": n.title or "Shot"})
            boards += int(as_role(groups, gid, h, "board"))
    sorted_notes = _sort_unprocessed(ws, groups)
    atomic_write_json(marker, {"schema_version": BINS_SCHEMA_VERSION, "migrated_at": utc_now(), "pages": pages, "styles": styles, "boards": boards})
    if not (pages or styles or boards):
        return sorted_notes
    parts = [f"{pages} version page{'s' if pages != 1 else ''}" if pages else "", f"{styles} style sample group{'s' if styles != 1 else ''}" if styles else "",
             f"{boards} board{'s' if boards != 1 else ''}" if boards else ""]
    return [f"U2: the Bin — {', '.join(x for x in parts if x)} moved into their homes (World › …, Shots › …)", *sorted_notes]


def _sort_unprocessed(ws: Any, groups: GroupStore) -> list[str]:
    """U2e: the Unprocessed assets whose origin names an owner, into its home (the rest stay unplaced)."""
    from .catalogue import AssetQuery
    moved, cursor = 0, None
    while True:
        page = groups.cat.list(AssetQuery(folder="unprocessed", limit=500, cursor=cursor))
        for a in page.items:
            if a.origin is not None and land(groups, ws, a.origin, [a.id]) is not None:
                moved += 1
        cursor = page.next_cursor
        if not cursor or not page.items:
            break
    return [f"U2: {moved} unprocessed asset{'s' if moved != 1 else ''} went to the home of what {'they were' if moved != 1 else 'it was'} made for"] if moved else []
