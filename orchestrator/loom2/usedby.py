"""D92 §4.2 (owed): what uses an album group — a Cast version's reference set or candidates, a style's samples, a Flow node's board, a
Stage's album page, a World library entry's pictures. Computed on request from the story and stage records (rebuildable, no new truth: a
record names its group, a group never names its users); the Catalogue's group Inspector and page header show it, and deleting or
ungrouping a used group says so in its confirm."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .fsio import read_json_or
from .groups import GroupStore
from .library import Library
from .stages import StageStore
from .story import StoryStore
from .workspace import Workspace

UserKind = Literal["profile_ref", "profile_candidates", "idea", "style", "flow_board", "stage", "library"]   # V26: an idea's page


class GroupUser(BaseModel):
    """One record that names a group. `id` opens the user (a profile, style, node, stage or library entry); `name` is its name; `extra` the
    detail the line shows (a version's label, a node's type, an entry's field); `version` the profile version; `group_id` the group it names
    (the asked group, or one inside it when `deep`)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: UserKind
    id: str
    name: str
    extra: str = ""
    version: str | None = None
    cls: str | None = None                       # a profile's class (character / place / prop)
    group_id: str


def all_users(ws: Workspace) -> dict[str, list[GroupUser]]:
    """Every group a record names → its users, in a fixed order (Cast, ideas, styles, Flow, Stage, library)."""
    out: dict[str, list[GroupUser]] = {}

    def add(gid: str | None, **u) -> None:
        if gid:
            out.setdefault(gid, []).append(GroupUser(group_id=gid, **u))

    store = StoryStore(ws)
    for p in sorted(store.profiles(), key=lambda p: p.name.casefold()):
        for v in p.versions:
            label = v.label or v.id
            add(v.group_id, kind="profile_ref", id=p.id, name=p.name, extra=label, version=v.id, cls=p.cls)
            add(v.candidates_group_id, kind="profile_candidates", id=p.id, name=p.name, extra=label, version=v.id, cls=p.cls)
    from .ideas import IdeaStore                                                   # V26: an idea's page holds its variants (add_variant copies there)
    for i in sorted(IdeaStore(ws).list(), key=lambda i: i.name.casefold()):
        add(i.group_id, kind="idea", id=i.id, name=i.name, cls=i.cls)
    for s in store.world().styles:
        add(s.group_id, kind="style", id=s.id, name=s.name)
    for n in sorted(store.flow_nodes().values(), key=lambda n: (n.title.casefold(), n.id)):
        add(n.board_group_id, kind="flow_board", id=n.id, name=n.title or n.type.capitalize(), extra=n.type)
    for st in StageStore(ws).list():
        add(st.group_id, kind="stage", id=st.id, name=st.name)
    lib = read_json_or(ws.story_dir / "library.json", None)    # read without seeding: a read here never writes the library
    if isinstance(lib, dict):
        for e in Library.model_validate(lib).entries:
            add(e.group_id, kind="library", id=e.id, name=e.name, extra=e.field)
    return out


def users_of(ws: Workspace, groups: GroupStore, ids: list[str] | None, deep: bool = False) -> dict[str, list[GroupUser]]:
    """The users of each asked group (every used group when `ids` is None); `deep` adds the users of the groups inside it — what a delete
    takes with it (a delete removes the groups inside, an ungroup only the group itself)."""
    users = all_users(ws)
    if ids is None:
        return users
    out: dict[str, list[GroupUser]] = {}
    for gid in ids:
        scope = [gid, *sorted(groups.descendants(gid))] if deep else [gid]
        out[gid] = [u for g in scope for u in users.get(g, [])]
    return out
