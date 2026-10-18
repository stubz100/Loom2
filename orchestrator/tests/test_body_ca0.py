"""CA0 (D94, proto01_animate 01 §9): the body on a Cast character's sheet — height, build, proportions, attachments; saved with the sheet
(read-only once the version is final, copied into a new version), refused on a place or a prop, part of the sheet's fingerprint (a body
change makes a shot's stage still stale, RC0), and copied onto a bound Stage figure (the stage document keeps it)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.body import Body  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.shot_recipe import sheet_fp  # noqa: E402
from loom2.story import ProfileVersion  # noqa: E402

from test_groups_d34 import _png  # noqa: E402

OGRE = {"height_m": 2.4, "build": "heavy", "head": 1.2, "torso": 1.1, "shoulders": 1.5, "arms": 1.3, "legs": 0.9,
        "attachments": [{"kind": "horns", "joint": None, "size": 1.2, "note": "curled"}, {"kind": "tail", "joint": "root", "size": 0.8, "note": ""}]}


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    return TestClient(app, headers={"X-Loom-Token": app.state.services.app.token})


def test_the_body_on_the_sheet(tmp_path: Path):
    with _client(tmp_path) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        hero = cl.app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        p = cl.post("/story/profiles", json={"name": "Grak", "cls": "character", "hero_asset_id": hero}).json()
        assert p["versions"][0]["body"] is None                                                   # the default dummy
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"], "versions": [{"id": "v1", "body": OGRE}]})
        assert r.status_code == 200, r.text
        assert r.json()["versions"][0]["body"]["height_m"] == 2.4 and r.json()["versions"][0]["body"]["attachments"][0]["kind"] == "horns"
        bad = {**OGRE, "height_m": 9}
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": r.json()["revision"], "versions": [{"id": "v1", "body": bad}]}).status_code == 422
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": r.json()["revision"], "versions": [{"id": "v1", "body": {**OGRE, "attachments": [{"kind": "jetpack"}]}}]}).status_code == 422
        p2 = cl.post(f"/story/profiles/{p['id']}/versions").json()
        assert p2["versions"][1]["body"] == r.json()["versions"][0]["body"]                     # a new version copies the body
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/lock").status_code == 200
        cur = cl.get(f"/story/profiles/{p['id']}").json()
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": cur["revision"], "versions": [{"id": "v1", "body": None}]}).status_code == 422   # final: read-only
        # a place or a prop has no body
        prop = cl.post("/story/profiles", json={"name": "Compass", "cls": "prop"}).json()
        assert cl.patch(f"/story/profiles/{prop['id']}", json={"revision": prop["revision"], "versions": [{"id": "v1", "body": OGRE}]}).status_code == 422
        # a bound figure keeps the copy in the stage document
        st = cl.post("/stages", json={"name": "Cave"}).json()
        fig = {"id": "obj_1", "kind": "mannequin", "name": "Grak", "preset": "adult", "profile_id": p["id"], "version": "v2", "body": OGRE}
        r = cl.put(f"/stages/{st['id']}", json={**st, "objects": [fig]})
        assert r.status_code == 200, r.text
        assert cl.get(f"/stages/{st['id']}").json()["objects"][0]["body"]["build"] == "heavy"


def test_the_body_is_part_of_the_sheets_fingerprint():
    v = ProfileVersion(id="v1", group_id="g")
    plain = sheet_fp(v)
    assert sheet_fp(v.model_copy(update={"body": None})) == plain                               # no body: the fingerprint of before
    tall = sheet_fp(v.model_copy(update={"body": Body(height_m=2.0)}))
    assert tall != plain and tall != sheet_fp(v.model_copy(update={"body": Body(height_m=2.1)}))
