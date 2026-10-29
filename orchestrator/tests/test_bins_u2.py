"""U2 (D157, G1; proto01_UI2 05 §2, 06 §1.2): the Bin — every creation has one home. A version's reference set and candidates are role
children of its home `world/<class>/<profile>/<version>` (every reader of `group_id` reads on); the migration once moves today's pages, the
styles' sample groups and a board used by one Shot into their homes; `/bin/homes` gives the named homes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import home, migrate_bins  # noqa: E402
from loom2.groups import ROOT_ID  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_groups_d34 import _setup  # noqa: E402


def _chain(groups, gid: str) -> list[str]:
    """The names from the album down to the group."""
    out = []
    while gid != ROOT_ID:
        out.append(groups.groups[gid].name)
        gid = groups.parent[("group", gid)]
    return out[::-1]


def test_a_version_lives_in_its_home(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    v1 = ines.version("v1")
    page = groups.groups[v1.group_id]
    assert (page.kind, page.role) == ("role", "reference") and _chain(groups, v1.group_id) == ["World", "Characters", "Ines", "v1", "Ines · v1"]
    h = groups.groups[groups.parent[("group", v1.group_id)]]
    assert (h.kind, h.path) == ("bin", f"world/character/{ines.id}/v1") and groups.parent[("asset", ids[0])] == v1.group_id
    ines, cand, made = st.ensure_candidates(ines.id, "v1", groups)
    assert made and groups.parent[("group", cand)] == h.id and groups.groups[cand].role == "candidates"
    ines = st.new_version(ines.id, groups)
    v2 = ines.version("v2")
    assert _chain(groups, v2.group_id) == ["World", "Characters", "Ines", "v2", "Ines · v2"] and groups.groups[v2.group_id].role == "reference"
    pier = st.create_profile("Harbour pier", "place", groups)
    assert _chain(groups, pier.version("v1").group_id)[:3] == ["World", "Places", "Harbour pier"]
    assert home(groups, "world/look").id == home(groups, "world/look").id                     # made once


def test_the_migration_moves_todays_pages_once(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    mara = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0])
    v = mara.version("v1")
    groups.move([("group", v.group_id)], ROOT_ID)                                          # as before U2: the pages on the album
    groups.mark(v.group_id, kind="album")
    cand = groups.create("Mara · v1 · candidates")
    mara = st.set_candidates(mara.id, "v1", cand.id)
    ink = groups.create("Ink wash samples")
    st.put_world({"styles": [{"id": "sty_ink", "name": "Ink wash", "fragment": "ink wash", "group_id": ink.id}]})
    one, shared = groups.create("Gate board"), groups.create("Harbour board")
    a, b, c = (st.create_node("shot", t) for t in ("Gate", "Quay", "Pier"))
    st.patch_node(a.id, {"board_group_id": one.id})
    st.patch_node(b.id, {"board_group_id": shared.id})
    st.patch_node(c.id, {"board_group_id": shared.id})
    notes = migrate_bins(ws, groups)
    assert notes == ["U2: the Bin — 2 version pages, 1 style sample group, 1 board moved into their homes (World › …, Shots › …)",
                     "B3: 1 album page moved into its home (the Bin: pages are folders of a home)"]                # B3 (D159): the shared board
    assert _chain(groups, v.group_id) == ["World", "Characters", "Mara", "v1", "Mara · v1"] and groups.groups[cand.id].role == "candidates"
    assert _chain(groups, ink.id) == ["World", "Look", "Ink wash samples"] and _chain(groups, one.id) == ["Shots", "Gate", "Gate board"]
    assert _chain(groups, shared.id)[0] == "Shots" and _chain(groups, shared.id)[1] in ("Quay", "Pier")   # B3: a board two Shots use, to its first's
    assert migrate_bins(ws, groups) == []                                                   # once
    assert (ws.path / "bins.json").is_file() and not list(groups.dir.glob("bins.json*"))    # U4: the mark outside the album (it read it as a torn group)
    assert st.profile(mara.id).version("v1").group_id == v.group_id                         # the records unchanged: readers read on


def test_a_versions_bin_is_one_grid_with_roles(tmp_path: Path):
    """U3 (D157, 03 §5): the version's bin through its route — the home's and the role pages' creations, newest first, with their roles."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_groups_d34 import _png
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        a, b, c = (svc.catalogue.ingest_file(_png(tmp_path / f"{i}.png"), prompt_text=f"Ines {i}").id for i in range(3))
        prof = cl.post("/story/profiles", json={"name": "Ines", "cls": "character", "hero_asset_id": a}).json()
        st = StoryStore(svc.ws)
        st.add_assets(prof["id"], "v1", [b], "reference", svc.groups, svc.catalogue)
        st.add_assets(prof["id"], "v1", [c], "candidate", svc.groups, svc.catalogue)
        r = cl.get(f"/story/profiles/{prof['id']}/versions/v1/bin").json()
        assert r["path"] == f"world/character/{prof['id']}/v1" and r["reference_id"] == prof["versions"][0]["group_id"]
        assert {x["asset"]["id"]: x["roles"] for x in r["items"]} == {a: ["hero"], b: ["reference"], c: ["candidate"]}   # newest first (one second here)
        assert cl.get(f"/story/profiles/{prof['id']}/versions/v9/bin").status_code == 404
