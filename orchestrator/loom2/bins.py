"""U2 (D157, G1; proto01_UI2 05 §2, 06 §1.2): the Bin — a tree of homes over the album's groups.

Every creation has one home, the path of what it was made for: `world/<class>/<profile>/<version>`, `world/look`, `world/sketches`,
`shots/<shot>`, `episode/<cut>`, `imports`. A home is a group of kind `bin` with its `path` (from ids, so a rename never breaks it); its
display name follows the record's. A version's two pages — its reference set and its candidates — are **role children** of its home
(kind `role`, `role: reference | candidates`): every reader of `v.group_id` keeps reading it, and to the author a picture stays in the bin
and gains a role. The album stays as it is around them.

`migrate_bins` runs once per project at open: each version's pages under its home, each style's samples under `world/look`, a Flow board
used by one Shot under its shot's home; then (U2e, bins schema 2) the Unprocessed assets whose origin names an owner go to its home.
Every finished job's assets land in their owner's home (`land`, from the queue's completion tail). An asset without an owner stays
unplaced until U8 retires Unprocessed with the old Catalogue.
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


def unplaced(groups: GroupStore) -> list[str]:
    """The live assets on no page — Image's free work, a file brought in from disk, a stage's own passes: the Bin shows them in `imports`
    (05 §2.1: an asset with no owner) until U8 retires Unprocessed with the old Catalogue."""
    return [a.id for a in groups.cat.list(AssetQuery(folder="unprocessed", limit=2000)).items]    # the newest 2000 (the catalogue's page)


def tree(groups: GroupStore) -> dict[str, Any]:
    """U8 (05 §2.1): the Bin's tree — each home {id, path, name, count, total, pages, children}: its count is its own live things and its
    role pages' (a version's reference set and candidates are roles inside it, not places), its total adds the homes under it; `imports`
    counts the things on no page too. The Trash's count beside it."""
    counts = groups.cat.counts()
    loose = counts.get("unprocessed", 0)
    with groups._lock:

        def node(g: GroupRecord) -> dict[str, Any]:
            pages, subs = _inside(groups, g)
            count = len(set(_live(groups, g)).union(*(set(_live(groups, p)) for p in pages))) + (loose if g.path == "imports" else 0)
            kids = [node(h) for h in subs]
            return {"id": g.id, "path": g.path or "", "name": g.name, "count": count, "total": count + sum(k["total"] for k in kids),
                    "pages": [p.id for p in pages], "children": kids}

        def top(g: GroupRecord) -> bool:
            par = groups.groups.get(groups.parent.get(("group", g.id)) or "")
            return par is None or par.kind != "bin"
        tops = sorted((g for g in groups.groups.values() if g.kind == "bin" and top(g)), key=_rank)
        return {"homes": [node(g) for g in tops], "trash": counts.get("trash", 0)}


def _roles(groups: GroupStore, ws: Any, g: GroupRecord) -> dict[str, list[str]] | None:
    """The roles of a home's things when its record gives them: a version's (World's: hero, reference, A-pose front / back, set picture,
    model; the rest candidates), a shot version's (its final, the frame and the clip it uses). None for any other home."""
    parts = (g.path or "").split("/")
    from .story import StoryStore
    if len(parts) == 4 and parts[0] == "world":
        prof = StoryStore(ws).profile(parts[2])
        if prof is None or not any(v.id == parts[3] for v in prof.versions):
            return None
        return {x["asset"].id: x["roles"] for x in version_bin(groups, prof, parts[3])["items"]}
    if len(parts) == 3 and parts[0] == "shots":
        s = StoryStore(ws).shot(parts[1])
        v = next((x for x in s.versions if x.id == parts[2]), None) if s is not None else None
        if v is None:
            return None
        from .clips import ClipStore
        from .finals import FinalStore
        clips = ClipStore(ws)
        out: dict[str, list[str]] = {}

        def add(aid: str | None, role: str) -> None:
            if aid and role not in out.setdefault(aid, []):
                out[aid].append(role)
        for f in FinalStore(ws).list():
            if f.shot_id == s.id and (f.shot_version or s.current) == v.id and f.clip_id:
                rec = clips.get(f.clip_id)
                add(rec.asset_id if rec else None, "final")
        add(v.frame_asset_id, "frame")
        rec = clips.get(v.clip_id) if v.clip_id else None
        add(rec.asset_id if rec else None, "clip")
        return out
    return None


def home_items(groups: GroupStore, ws: Any, gid: str) -> dict[str, Any]:
    """U8 (05 §2.2): what a home holds — its own things and its pages', and everything in the homes under it (a parent shows all below
    it), newest first, each with its roles and its home. `imports` holds the things on no page too."""
    with groups._lock:
        top = groups.groups.get(gid)
        if top is None or top.kind != "bin":
            raise KeyError(gid)
        seen: dict[str, dict[str, Any]] = {}

        def walk(g: GroupRecord) -> None:
            pages, subs = _inside(groups, g)
            roles = _roles(groups, ws, g) or {}
            for page, role in [(g, None), *[(p, KIND_ROLE.get(p.role or "", p.role)) for p in pages]]:
                for aid in _live(groups, page):
                    if aid not in seen:
                        seen[aid] = {"asset": groups.cat.get(aid), "roles": roles.get(aid) or ([role] if role else []), "home_id": g.id, "path": g.path or ""}
            if g.path == "imports":
                for aid in unplaced(groups):
                    seen.setdefault(aid, {"asset": groups.cat.get(aid), "roles": [], "home_id": g.id, "path": "imports"})
            for h in subs:
                walk(h)
        walk(top)
        items = [x for x in seen.values() if x["asset"] is not None]
        items.sort(key=lambda x: x["asset"].created_at, reverse=True)
        return {"home_id": top.id, "path": top.path or "", "items": items}


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
