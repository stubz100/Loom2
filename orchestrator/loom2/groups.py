"""Groups: hand-made arrangements of assets on album pages (proto01_design/01 §6c, §8; D34).

A group is an atomic JSON record `groups/<id>.json` (the files are the truth, as for asset manifests): a name, an optional cover
and its items, assets or other groups, at free positions on an endless page. `groups/album.json` is the root page. An item has
at most one placement: placing it elsewhere moves it, and an asset with no placement is *Unprocessed*. The catalogue index
caches the asset placements (`placements`) so queries can filter on Unprocessed or a group; it is rewritten from the files
whenever a project opens.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .catalogue import AssetQuery, Catalogue
from .fsio import StateError, atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

log = logging.getLogger(__name__)

GROUP_SCHEMA_VERSION = 1
ROOT_ID = "album"
ASSET_W = 240            # default width of a placed photo (page units = CSS px at 100 %)
GROUP_W = 200            # default width of a card
CARD_RATIO = 0.8         # card height / width (the frontend draws the card in this box)
GAP = 32
MARGIN = 40
ROW_W = 1600             # auto placement wraps here

ItemKind = Literal["asset", "group"]


class StaleGroup(StateError):
    """A layout edit based on an older revision of the group than the file's (the API answers 409; the page reloads)."""


class GroupNotFound(StateError):
    """No group with that id (404)."""


class GroupItem(BaseModel):
    kind: ItemKind
    id: str
    x: float = 0
    y: float = 0
    w: float = ASSET_W
    z: int = 0


class GroupRecord(BaseModel):
    schema_version: int = GROUP_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("grp"))
    name: str
    cover_id: str | None = None             # an asset id; None = the first asset on the page
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    revision: int = 0
    items: list[GroupItem] = Field(default_factory=list)


Key = tuple[str, str]                         # (kind, id)


class GroupStore:
    def __init__(self, ws: Workspace, cat: Catalogue) -> None:
        self.ws, self.cat = ws, cat
        self.dir = ws.path / "groups"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.groups: dict[str, GroupRecord] = {}
        self.parent: dict[Key, str] = {}
        self.migrated: int = 0                # collections turned into groups at this open (0 = none)
        self._load()

    # ---- load / integrity -------------------------------------------------------------------------
    def _path(self, gid: str) -> Path:
        return self.dir / f"{gid}.json"

    def _load(self) -> None:
        with self._lock:
            first_open = not self._path(ROOT_ID).is_file()
            for p in sorted(self.dir.glob("*.json")):
                try:
                    g = GroupRecord.model_validate(read_json(p))
                except Exception as e:  # noqa: BLE001 — one unreadable file must not take the album down
                    log.error("group file %s unreadable (%s); skipped", p.name, e)
                    continue
                self.groups[g.id] = g
            if ROOT_ID not in self.groups:
                self.groups[ROOT_ID] = GroupRecord(id=ROOT_ID, name="Album")
                self._write(self.groups[ROOT_ID])
            self._repair()
            if first_open:
                self._migrate_collections()
            self._reindex()

    def _repair(self) -> None:
        """One placement per item, no dangling group items, every group reachable from the album (hand-edited or torn files)."""
        dirty: set[str] = set()
        seen: dict[Key, str] = {}
        for g in sorted(self.groups.values(), key=lambda g: g.updated_at, reverse=True):     # the most recent placement wins
            keep = []
            for it in g.items:
                k = (it.kind, it.id)
                if k in seen or (it.kind == "group" and (it.id not in self.groups or it.id == ROOT_ID or it.id == g.id)):
                    log.warning("group %s: dropped %s %s (placed twice or missing)", g.id, it.kind, it.id)
                    dirty.add(g.id)
                    continue
                seen[k] = g.id
                keep.append(it)
            g.items = keep
        self.parent = seen
        reachable = self._descendants(ROOT_ID) | {ROOT_ID}
        for gid in [g for g in self.groups if g not in reachable]:                          # orphans and cycles: back onto the album
            old = self.parent.pop(("group", gid), None)
            if old:
                self.groups[old].items = [it for it in self.groups[old].items if not (it.kind == "group" and it.id == gid)]
                dirty.add(old)
            self._place(ROOT_ID, [("group", gid)])
            dirty.add(ROOT_ID)
        for gid in dirty:
            self._write(self.groups[gid], bump=True)

    def _migrate_collections(self) -> None:
        """D34: manual and smart collections become groups on the album page (once, at the first open with groups). An asset in
        several collections stays in the oldest and is duplicated into the others, so nothing arranged is lost."""
        cols = self.cat.collections()
        if not cols:
            return
        for col in sorted(cols, key=lambda c: c.created_at):
            if col.kind == "manual":
                with self.cat._lock:
                    ids = [r["asset_id"] for r in self.cat._db.execute(
                        "SELECT asset_id FROM collection_assets WHERE collection_id=? ORDER BY added_at", (col.id,)).fetchall()]
            else:
                ids = [a.id for a in self.cat.list(AssetQuery(**(col.filter or {}), limit=2000)).items]
            g = GroupRecord(name=col.name)
            self.groups[g.id] = g
            self._place(ROOT_ID, [("group", g.id)])
            keys: list[Key] = []
            for aid in ids:
                if self.cat.get(aid) is None:
                    continue
                if ("asset", aid) in self.parent:
                    dup = self.cat.duplicate(aid)
                    if dup is None:
                        continue
                    aid = dup.id
                keys.append(("asset", aid))
            self._place(g.id, keys)
            self._write(g)
            self.migrated += 1
        self._write(self.groups[ROOT_ID], bump=True)
        log.info("migrated %d collections into groups", self.migrated)

    def _reindex(self) -> None:
        self.cat.set_placements({k[1]: gid for k, gid in self.parent.items() if k[0] == "asset"})

    # ---- helpers ----------------------------------------------------------------------------------
    def _write(self, g: GroupRecord, bump: bool = False) -> None:
        if bump:
            g.revision += 1
            g.updated_at = utc_now()
        atomic_write_json(self._path(g.id), g.model_dump())

    def _get(self, gid: str) -> GroupRecord:
        g = self.groups.get(gid)
        if g is None:
            raise GroupNotFound(f"group {gid} not found")
        return g

    def _descendants(self, gid: str) -> set[str]:
        out: set[str] = set()
        stack = [gid]
        while stack:
            for it in self.groups[stack.pop()].items:
                if it.kind == "group" and it.id not in out and it.id in self.groups:
                    out.add(it.id)
                    stack.append(it.id)
        return out

    def _height(self, it: GroupItem) -> float:
        if it.kind == "group":
            return it.w * CARD_RATIO
        a = self.cat.get(it.id)
        return it.w * (a.h / a.w) if a and a.w and a.h else it.w * 0.75

    def _next_spots(self, g: GroupRecord, sizes: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Free spots below the page's content, left to right, wrapping at ROW_W."""
        bottom = max((it.y + self._height(it) for it in g.items), default=MARGIN - GAP)
        x, y, row_h, out = float(MARGIN), bottom + GAP, 0.0, []
        for w, h in sizes:
            if x > MARGIN and x + w > ROW_W:
                x, y, row_h = float(MARGIN), y + row_h + GAP, 0.0
            out.append((x, y))
            x += w + GAP
            row_h = max(row_h, h)
        return out

    def _place(self, gid: str, keys: list[Key], positions: list[dict] | None = None) -> None:
        """Put items on a page (taking them off wherever they were). Positions default to free spots."""
        g = self.groups[gid]
        for k in keys:
            self._unplace(k)
        items = [GroupItem(kind=k[0], id=k[1], w=GROUP_W if k[0] == "group" else ASSET_W) for k in keys]  # type: ignore[arg-type]
        if positions and len(positions) == len(items):
            for it, p in zip(items, positions):
                it.x, it.y = float(p.get("x", 0)), float(p.get("y", 0))
                if p.get("w"):
                    it.w = float(p["w"])
        else:
            for it, (x, y) in zip(items, self._next_spots(g, [(it.w, self._height(it)) for it in items])):
                it.x, it.y = x, y
        z = max((it.z for it in g.items), default=0)
        for it in items:
            z += 1
            it.z = z
            g.items.append(it)
            self.parent[(it.kind, it.id)] = gid

    def _unplace(self, k: Key) -> str | None:
        old = self.parent.pop(k, None)
        if old and old in self.groups:
            self.groups[old].items = [it for it in self.groups[old].items if (it.kind, it.id) != k]
        return old

    def _path_of(self, gid: str) -> list[dict]:
        out, cur = [], gid
        while cur:
            g = self.groups.get(cur)
            if g is None:
                break
            out.append({"id": g.id, "name": g.name})
            cur = self.parent.get(("group", cur)) if cur != ROOT_ID else None
        return list(reversed(out))

    def _asset_ids(self, gid: str) -> list[str]:
        """Every asset placed in the group or below it."""
        out: list[str] = []
        for g in [gid, *self._descendants(gid)]:
            out += [it.id for it in self.groups[g].items if it.kind == "asset"]
        return out

    def _cover(self, g: GroupRecord, n: int = 3) -> list[str]:
        """Up to n asset ids for a card's fan: the chosen cover first, then the page's assets by stacking order, then sub-groups'."""
        live = lambda aid: (r := self.cat.get(aid)) is not None and r.trashed_at is None  # noqa: E731
        out = [g.cover_id] if g.cover_id and live(g.cover_id) else []
        for it in sorted(g.items, key=lambda it: -it.z):
            if len(out) >= n:
                break
            if it.kind == "asset" and it.id not in out and live(it.id):
                out.append(it.id)
        for it in g.items:
            if len(out) >= n:
                break
            if it.kind == "group" and it.id in self.groups:
                out += [a for a in self._cover(self.groups[it.id], n - len(out)) if a not in out]
        return out[:n]

    def _summary(self, g: GroupRecord) -> dict:
        assets = sum(1 for it in g.items if it.kind == "asset")
        return {"id": g.id, "name": g.name, "assets": assets, "groups": len(g.items) - assets, "total": len(self._asset_ids(g.id)),
                "cover_ids": self._cover(g), "revision": g.revision}

    # ---- reads ------------------------------------------------------------------------------------
    def tree(self) -> dict:
        with self._lock:
            def node(gid: str) -> dict:
                g = self.groups[gid]
                kids = [node(it.id) for it in sorted(g.items, key=lambda it: (it.y, it.x)) if it.kind == "group" and it.id in self.groups]
                return {**self._summary(g), "children": kids}
            return node(ROOT_ID)

    def page(self, gid: str) -> dict:
        """A page: the group, its breadcrumb, its live items (trashed assets hidden), asset records and card summaries."""
        with self._lock:
            g = self._get(gid)
            recs = {r.id: r for r in self.cat.get_many([it.id for it in g.items if it.kind == "asset"])}
            items = [it for it in g.items if (it.kind == "group" and it.id in self.groups) or (it.kind == "asset" and it.id in recs and recs[it.id].trashed_at is None)]
            return {"group": {**g.model_dump(), "items": [it.model_dump() for it in items]}, "path": self._path_of(gid),
                    "assets": {i: recs[i].model_dump() for i in recs if recs[i].trashed_at is None},
                    "groups": {it.id: self._summary(self.groups[it.id]) for it in items if it.kind == "group"}}

    def where(self, ids: list[str]) -> dict[str, dict | None]:
        """For each asset: its group and that group's breadcrumb, or None (Unprocessed)."""
        with self._lock:
            out: dict[str, dict | None] = {}
            for aid in ids:
                gid = self.parent.get(("asset", aid))
                out[aid] = {"group_id": gid, "path": self._path_of(gid)} if gid else None
            return out

    # ---- writes (each returns the ids of the groups it changed) -----------------------------------
    def create(self, name: str, parent_id: str = ROOT_ID, x: float | None = None, y: float | None = None) -> GroupRecord:
        with self._lock:
            parent = self._get(parent_id)
            g = GroupRecord(name=name.strip() or "Group")
            self.groups[g.id] = g
            self._place(parent.id, [("group", g.id)], [{"x": x, "y": y}] if x is not None and y is not None else None)
            self._write(g)
            self._write(parent, bump=True)
            return g

    def update(self, gid: str, name: str | None = None, cover_id: str | None = None) -> GroupRecord:
        with self._lock:
            g = self._get(gid)
            if name is not None:
                g.name = name.strip() or g.name
            if cover_id is not None:
                g.cover_id = cover_id or None
            self._write(g, bump=True)
            return g

    def layout(self, gid: str, items: list[dict], revision: int | None = None) -> GroupRecord:
        """Positions, sizes and stacking of items already on the page (one call per drag end)."""
        with self._lock:
            g = self._get(gid)
            if revision is not None and revision != g.revision:
                raise StaleGroup(f"the page is based on revision {revision}; the group is at revision {g.revision}")
            by = {(it.kind, it.id): it for it in g.items}
            for d in items:
                it = by.get((d.get("kind"), d.get("id")))
                if it is None:
                    raise StateError(f"{d.get('kind')} {d.get('id')} is not on this page")
                it.x, it.y = float(d.get("x", it.x)), float(d.get("y", it.y))
                it.w = max(24.0, float(d.get("w", it.w)))
                it.z = int(d.get("z", it.z))
            self._write(g, bump=True)
            return g

    def move(self, keys: list[Key], to: str | None, positions: list[dict] | None = None) -> set[str]:
        """Move items onto a page (`to`), or assets back to Unprocessed (`to` = None)."""
        with self._lock:
            changed = {self.parent[k] for k in keys if k in self.parent}
            if to is None:
                if any(k[0] == "group" for k in keys):
                    raise StateError("a group cannot go to Unprocessed; move it onto a page or delete it")
                for k in keys:
                    self._unplace(k)
            else:
                self._get(to)
                for k in keys:
                    if k[0] == "group":
                        if k[1] == ROOT_ID or k[1] not in self.groups:
                            raise StateError(f"group {k[1]} cannot be moved")
                        if k[1] == to or to in self._descendants(k[1]):
                            raise StateError("a group cannot go inside itself")
                    elif self.cat.get(k[1]) is None:
                        raise StateError(f"asset {k[1]} not found")
                self._place(to, keys, positions)
                changed.add(to)
            for gid in changed:
                self._write(self.groups[gid], bump=True)
            self._reindex()
            return changed

    def group_items(self, gid: str, keys: list[Key], name: str) -> GroupRecord:
        """Make a group of items on a page: they keep their relative layout on the new page; its card takes their place."""
        with self._lock:
            parent = self._get(gid)
            by = {(it.kind, it.id): it for it in parent.items}
            picked = [by[k] for k in keys if k in by]
            if not picked:
                raise StateError("none of those items is on this page")
            x0, y0 = min(it.x for it in picked), min(it.y for it in picked)
            g = GroupRecord(name=name.strip() or "Group")
            self.groups[g.id] = g
            for it in picked:
                self._unplace((it.kind, it.id))
            for it in sorted(picked, key=lambda it: it.z):
                g.items.append(GroupItem(kind=it.kind, id=it.id, x=it.x - x0 + MARGIN, y=it.y - y0 + MARGIN, w=it.w, z=len(g.items) + 1))
                self.parent[(it.kind, it.id)] = g.id
            self._place(gid, [("group", g.id)], [{"x": x0, "y": y0}])
            self._write(g)
            self._write(parent, bump=True)
            self._reindex()
            return g

    def ungroup(self, gid: str) -> str:
        """Dissolve a group: its items land on the parent page where its card was, keeping their layout."""
        with self._lock:
            if gid == ROOT_ID:
                raise StateError("the album cannot be ungrouped")
            g = self._get(gid)
            pid = self.parent.get(("group", gid), ROOT_ID)
            parent = self.groups[pid]
            card = next((it for it in parent.items if it.kind == "group" and it.id == gid), None)
            cx, cy = (card.x, card.y) if card else (float(MARGIN), float(MARGIN))
            self._unplace(("group", gid))
            x0 = min((it.x for it in g.items), default=0.0)
            y0 = min((it.y for it in g.items), default=0.0)
            z = max((it.z for it in parent.items), default=0)
            for it in sorted(g.items, key=lambda it: it.z):
                z += 1
                parent.items.append(GroupItem(kind=it.kind, id=it.id, x=cx + it.x - x0, y=cy + it.y - y0, w=it.w, z=z))
                self.parent[(it.kind, it.id)] = pid
            del self.groups[gid]
            self._path(gid).unlink(missing_ok=True)
            self._write(parent, bump=True)
            self._reindex()
            return pid

    def delete(self, gid: str) -> list[str]:
        """Delete a group and the groups inside it; every asset in them returns to Unprocessed (nothing is trashed)."""
        with self._lock:
            if gid == ROOT_ID:
                raise StateError("the album cannot be deleted")
            self._get(gid)
            freed = self._asset_ids(gid)
            pid = self._unplace(("group", gid)) or ROOT_ID
            for sub in [gid, *self._descendants(gid)]:
                for it in self.groups[sub].items:
                    self.parent.pop((it.kind, it.id), None)
            for sub in [gid, *self._descendants(gid)]:
                self.groups.pop(sub, None)
                self._path(sub).unlink(missing_ok=True)
            self._write(self.groups[pid], bump=True)
            self._reindex()
            return freed

    def duplicate_assets(self, ids: list[str]) -> list[str]:
        """A copy of each asset (a new item with its own file); placed next to the original, or Unprocessed like it."""
        with self._lock:
            out, changed = [], set()
            for aid in ids:
                dup = self.cat.duplicate(aid)
                if dup is None:
                    continue
                out.append(dup.id)
                gid = self.parent.get(("asset", aid))
                if gid:
                    orig = next(it for it in self.groups[gid].items if it.kind == "asset" and it.id == aid)
                    self._place(gid, [("asset", dup.id)], [{"x": orig.x + 24, "y": orig.y + 24, "w": orig.w}])
                    changed.add(gid)
            for gid in changed:
                self._write(self.groups[gid], bump=True)
            self._reindex()
            return out

    def duplicate_group(self, gid: str) -> GroupRecord:
        """A deep copy next to the original: its assets duplicated, its groups copied the same way."""
        with self._lock:
            if gid == ROOT_ID:
                raise StateError("the album cannot be duplicated")
            src = self._get(gid)

            def copy(g: GroupRecord, name: str) -> GroupRecord:
                new = GroupRecord(name=name, cover_id=None)
                self.groups[new.id] = new
                for it in g.items:
                    if it.kind == "asset":
                        dup = self.cat.duplicate(it.id)
                        if dup is None:
                            continue
                        nid = dup.id
                        if g.cover_id == it.id:
                            new.cover_id = nid
                    else:
                        nid = copy(self.groups[it.id], self.groups[it.id].name).id
                    new.items.append(GroupItem(kind=it.kind, id=nid, x=it.x, y=it.y, w=it.w, z=it.z))
                    self.parent[(it.kind, nid)] = new.id
                self._write(new)
                return new

            pid = self.parent.get(("group", gid), ROOT_ID)
            card = next((it for it in self.groups[pid].items if it.kind == "group" and it.id == gid), None)
            new = copy(src, f"{src.name} copy")
            pos = [{"x": card.x + card.w + GAP, "y": card.y, "w": card.w}] if card else None
            self._place(pid, [("group", new.id)], pos)
            self._write(self.groups[pid], bump=True)
            self._reindex()
            return new

    def forget_assets(self, ids: list[str]) -> set[str]:
        """Purged assets lose their placements."""
        with self._lock:
            changed = {gid for aid in ids if (gid := self._unplace(("asset", aid)))}
            for gid in changed:
                self._write(self.groups[gid], bump=True)
            self._reindex()
            return changed
