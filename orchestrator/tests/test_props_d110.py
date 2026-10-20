"""D109 / D110 (PS2): a prop is made like a character — its images, then its 3D model. Every image → mesh result is stood upright (the
reference camera's tilt taken off); a prop version keeps its model and the image it came from; only a prop has one; the routes make it
from the version's animation reference (else its hero) and refuse a character, an imageless prop and the `open` variant; the finisher
sets the model on the version."""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.story import Profile, ProfileVersion, StoryStore, check_profile, model_source  # noqa: E402
from loom2.tools.upright import euler, node_points, read_glb, stand_upright, write_glb  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def box_glb(path: Path, size=(0.8, 0.5, 0.6), tilt=(-21.0, 30.0, 2.0)) -> None:
    """A box's eight corners and its edges' midpoints, tilted the way a reference seen from above tilts a model."""
    w, h, d = size
    pts = np.array([[x, y, z] for x in (-w / 2, 0, w / 2) for y in (0, h / 2, h) for z in (-d / 2, 0, d / 2)], float)
    pts = pts @ euler(*tilt).T
    raw = pts.astype(np.float32).tobytes()
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(pts), "type": "VEC3", "min": pts.min(0).tolist(), "max": pts.max(0).tolist()}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(raw)}], "buffers": [{"byteLength": len(raw)}]}
    write_glb(path, doc, raw)


def extents(path: Path) -> np.ndarray:
    doc, binary = read_glb(path)
    _, p = node_points(doc, binary)
    return p.max(axis=0) - p.min(axis=0)


def test_a_tilted_model_is_stood_upright(tmp_path: Path):
    g = tmp_path / "chest.glb"
    box_glb(g)
    assert extents(g)[1] > 0.6                                                     # tilted: taller than the box
    angles = stand_upright(g)
    assert abs(angles[0]) > 15                                                     # the view's elevation taken off
    ext = extents(g)
    assert ext[1] == pytest.approx(0.5, abs=0.02)                                  # its own height again
    assert sorted(ext[[0, 2]]) == pytest.approx([0.6, 0.8], abs=0.03)              # square to the axes
    doc, _ = read_glb(g)
    q = doc["nodes"][0]["rotation"]
    assert math.isclose(sum(v * v for v in q), 1.0, rel_tol=1e-5)                  # written as the node's rotation; the points are untouched
    assert stand_upright(g) == [0.0, 0.0, 0.0]                                     # a second pass changes nothing


def test_a_flat_or_upright_mesh_is_left_alone(tmp_path: Path):
    from fake_comfy import minimal_glb
    g = tmp_path / "tri.glb"
    g.write_bytes(minimal_glb())
    before = g.read_bytes()
    assert stand_upright(g) == [0.0, 0.0, 0.0] and g.read_bytes() == before
    up = tmp_path / "box.glb"
    box_glb(up, tilt=(0.0, 0.0, 0.0))
    assert stand_upright(up) == [0.0, 0.0, 0.0]
    with pytest.raises(ValueError):
        bad = tmp_path / "x.glb"; bad.write_bytes(b"nope" + b"\0" * 20); stand_upright(bad)


def _version(**kw) -> ProfileVersion:
    return ProfileVersion(id="v1", group_id="grp_x", **kw)


def test_only_a_prop_has_a_model_and_its_source():
    assert model_source(_version(anim_ref_asset_id="ast_ref", hero_asset_id="ast_hero")) == "ast_ref"
    assert model_source(_version(hero_asset_id="ast_hero")) == "ast_hero" and model_source(_version()) is None
    check_profile(Profile(name="Chest", cls="prop", current="v1", versions=[_version(model_asset_id="ast_m")]))
    with pytest.raises(ValueError, match="only a prop"):
        check_profile(Profile(name="Mara", cls="character", current="v1", versions=[_version(model_asset_id="ast_m")]))


def test_the_store_sets_and_clears_a_version_model(tmp_path: Path):
    from loom2.catalogue import Catalogue
    from loom2.groups import GroupStore
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StoryStore(ws)
    groups = GroupStore(ws, Catalogue(ws))
    prop = store.create_profile("Chest", "prop", groups)
    p = store.set_model(prop.id, prop.current, "ast_mesh", "ast_ref")
    v = p.version()
    assert (v.model_asset_id, v.model_from) == ("ast_mesh", "ast_ref") and p.revision == prop.revision + 1
    assert store.set_model(prop.id, prop.current, None, "ast_ref").version().model_from is None
    who = store.create_profile("Mara", "character", groups)
    with pytest.raises(ValueError):
        store.set_model(who.id, who.current, "ast_mesh", None)


def test_routes_make_and_pick(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    for variant in ("full", "open"):
        state = tmp_path / variant / "state"
        AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / variant / "models"),
                                         "mounted_model_trees": [], "variant": variant})
        _pin_review().full_roster(tmp_path / variant / "models")
        app = create_app(state)
        H = {"X-Loom-Token": app.state.services.app.token}
        with TestClient(app) as cl:
            cl.post("/project", json={"path": str(tmp_path / variant / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
            src = tmp_path / variant / "chest.png"
            Image.new("RGB", (64, 48), (160, 40, 30)).save(src)
            a = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
            bare = cl.post("/story/profiles", json={"name": "Empty", "cls": "prop"}, headers=H).json()
            r = cl.post(f"/story/profiles/{bare['id']}/versions/{bare['current']}/model", headers=H)
            assert r.status_code == 422 and "image first" in r.json()["detail"]
            prop = cl.post("/story/profiles", json={"name": "Chest", "cls": "prop", "hero_asset_id": a["id"]}, headers=H).json()
            who = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": a["id"]}, headers=H).json()
            assert cl.post(f"/story/profiles/{who['id']}/versions/{who['current']}/model", headers=H).status_code == 422
            r = cl.post(f"/story/profiles/{prop['id']}/versions/{prop['current']}/model", headers=H)
            if variant == "open":
                assert r.status_code == 422 and "Q22" in r.json()["detail"]
                continue
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["source_asset_id"] == a["id"] and body["model_id"] == "pixal3d-int8"
            job = next(j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] == body["job_id"])
            assert job["recipe"]["kind"] == "image_to_mesh" and job["origin"]["surface"] == "prop_model" and job["origin"]["payload"] == {"version": prop["current"], "from": a["id"]}
            assert cl.put(f"/story/profiles/{prop['id']}/versions/{prop['current']}/model", json={"asset_id": a["id"]}, headers=H).status_code == 422   # an image is not a mesh
            cleared = cl.put(f"/story/profiles/{prop['id']}/versions/{prop['current']}/model", json={"asset_id": None}, headers=H)
            assert cleared.status_code == 200 and cleared.json()["versions"][0]["model_asset_id"] is None


async def test_the_model_lands_on_its_prop_version(tmp_path: Path, object_info: dict, monkeypatch):
    """The whole path: a prop's make → the fake engine's GLB → stood upright → a mesh asset → the version's model, with its source."""
    import test_lifecycle
    from loom2.groups import GroupStore
    from loom2.story import prop_model_origin
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        src = tmp_path / "chest.png"
        Image.new("RGB", (96, 64), (160, 40, 30)).save(src)
        photo = rig.catalogue.ingest_file(src, kind="image", move=False, suite="story")
        store = StoryStore(rig.ws)
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        prop = store.create_profile("Chest", "prop", groups, hero_asset_id=photo.id)
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "image_to_mesh", "asset_id": photo.id}, origin=prop_model_origin(prop.id, prop.current, photo.id))[0]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        mesh = j.result["asset_ids"][0]
        v = store.profile(prop.id).version()
        assert v.model_asset_id == mesh and v.model_from == photo.id
        assert rig.catalogue.get(mesh).params["upright_deg"] == [0.0, 0.0, 0.0]          # the fake's flat triangle stays as it is
        assert any("stood upright" in line for line in j.log_tail)
    finally:
        await rig.close()
