"""U2 (D157, G1; proto01_UI2 05 §2, 06 §1.2): the Bin — a tree of homes over the album's groups.

Every creation has one home, the path of what it was made for: `world/<class>/<profile>/<version>`, `world/look`, `world/sketches`,
`shots/<shot>`, `episode/<cut>`, `imports`. A home is a group of kind `bin` with its `path` (from ids, so a rename never breaks it); its
display name follows the record's. A version's two pages — its reference set and its candidates — are **role children** of its home
(kind `role`, `role: reference | candidates`): every reader of `v.group_id` keeps reading it, and to the author a picture stays in the bin
and gains a role. The album stays as it is around them.

`migrate_bins` runs once per project at open: each version's pages under its home, each style's samples under `world/look`, a Flow board
used by one Shot under its shot's home. Sorting Unprocessed by origin and the finishers writing homes come in U2e.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .fsio import atomic_write_json, read_json_or, utc_now
from .groups import ROOT_ID, GroupRecord, GroupStore

BINS_SCHEMA_VERSION = 1
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


def migrate_bins(ws: Any, groups: GroupStore) -> list[str]:
    """Once per project (`groups/bins.json`): the versions' pages, the styles' samples and the one-shot boards into their homes. Notes."""
    marker = Path(groups.dir) / "bins.json"
    if read_json_or(marker, None) is not None:
        return []
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
    atomic_write_json(marker, {"schema_version": BINS_SCHEMA_VERSION, "migrated_at": utc_now(), "pages": pages, "styles": styles, "boards": boards})
    if not (pages or styles or boards):
        return []
    parts = [f"{pages} version page{'s' if pages != 1 else ''}" if pages else "", f"{styles} style sample group{'s' if styles != 1 else ''}" if styles else "",
             f"{boards} board{'s' if boards != 1 else ''}" if boards else ""]
    return [f"U2: the Bin — {', '.join(x for x in parts if x)} moved into their homes (World › …, Shots › …)"]
