"""CS2 (proto01_UIcast 03 §3.2, 06 §2.4; D136 U6, U17): the skeleton bench's server half — the body's new rows (the head carried forward,
the shoulders' drop, the feet turned out, the fingers' spread and the thumb at rest, the locks), *Fit again* on the author's points at once
(no job), and a character's shell: made from its animation reference by the image → 3D model job, or picked from the Catalogue."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.body import Body, body_points, dummy_ratios, fit_body, person_of, reference_ratios, stance_note  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from fake_comfy import fake_person  # noqa: E402


def test_the_new_rows_shape_the_front_view():
    d = dummy_ratios(Body())
    assert dummy_ratios(Body(shoulder_drop=2.0))["head_neck"] > d["head_neck"] and dummy_ratios(Body(shoulder_drop=2.0))["torso"] < d["torso"]   # lower shoulders
    assert dummy_ratios(Body(head_forward=30.0))["head_neck"] < d["head_neck"]                 # a stoop: the nose lower over the shoulders
    b = Body(feet_out=15.0, hand_rest={"preset": "relaxed", "curl": 1.0, "spread": 8.0, "thumb": 12.0}, locks=["neck"])
    assert b.model_dump()["hand_rest"]["thumb"] == 12.0 and Body.model_validate(b.model_dump()).feet_out == 15.0


def test_the_points_go_back_into_a_person():
    p = fake_person({"head_neck": 0.17})
    pts = body_points(p, [832, 480])
    assert reference_ratios(person_of(pts)) == pytest.approx(reference_ratios(p), abs=1e-3)       # kept and read back: the same measures
    moved = {**pts, "pose": [list(r) for r in pts["pose"]]}
    for k in (8, 11):
        moved["pose"][k][1] -= 20                                                                   # the hips dragged up 20 px (a coat hid them)
    a, b = fit_body(reference_ratios(person_of(pts)))[0], fit_body(reference_ratios(person_of(moved)))[0]
    assert b.torso < a.torso and b.legs > a.legs


def a_pose_glb(path: Path) -> None:
    """A figure in the A-pose as points: a body column 1.75 m tall, the arms 30° out from it — what E36's shells are."""
    from loom2.tools.upright import write_glb
    import numpy as np
    body = [[x, y, z] for x in (-0.18, 0.18) for y in np.linspace(0, 1.75, 15) for z in (-0.12, 0.12)]
    arms = [[s * (0.2 + t * 0.62 * 0.5), 1.42 - t * 0.62 * 0.866, z] for s in (-1, 1) for t in np.linspace(0, 1, 10) for z in (-0.04, 0.04)]
    pts = np.array(body + arms, np.float32)
    raw = pts.tobytes()
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(pts), "type": "VEC3", "min": pts.min(0).tolist(), "max": pts.max(0).tolist()}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(raw)}], "buffers": [{"byteLength": len(raw)}]}
    write_glb(path, doc, raw)


def test_a_shell_is_never_stood_upright(tmp_path: Path):
    """E36: D109's smallest upright box tilts a figure holding its arms out (the six A-pose shells leaned 12–44°); undo_upright takes the
    turn back exactly."""
    from loom2.tools.upright import node_points, read_glb, stand_upright, undo_upright
    g = tmp_path / "shell.glb"
    a_pose_glb(g)
    before = node_points(*read_glb(g))[1]
    angles = stand_upright(g)
    assert max(abs(a) for a in angles) > 10                                                         # the figure tilted to a smaller box
    undo_upright(g, angles)
    doc, binary = read_glb(g)
    assert "rotation" not in doc["nodes"][0] and node_points(doc, binary)[1] == pytest.approx(before, abs=1e-5)


def test_the_shell_knows_where_its_figure_stands(tmp_path: Path):
    """E36: the mesh graph's matte gives the figure's box in its picture (hair and hat included), written into the GLB beside the mesh."""
    from PIL import Image
    from loom2.tools.upright import figure_box, read_glb, set_scene_extras
    m = Image.new("L", (1280, 720), 0)
    m.paste(255, (560, 60, 720, 690))
    m.save(tmp_path / "matte.png")
    assert figure_box(tmp_path / "matte.png") == [560, 60, 720, 690, 1280, 720]
    Image.new("L", (8, 8), 0).save(tmp_path / "empty.png")
    assert figure_box(tmp_path / "empty.png") is None
    g = tmp_path / "shell.glb"
    a_pose_glb(g)
    set_scene_extras(g, {"figure_box": [560, 60, 720, 690, 1280, 720]})
    doc, _ = read_glb(g)
    assert doc["scenes"][0]["extras"]["loom2"]["figure_box"][1] == 60 and doc["nodes"][0]["mesh"] == 0


def _client(tmp_path: Path, variant: str = "full"):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / variant / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / variant / "models"),
                                     "mounted_model_trees": [], "variant": variant})
    _pin_review().full_roster(tmp_path / variant / "models")
    app = create_app(state)
    return app, TestClient(app, headers={"X-Loom-Token": app.state.services.app.token})


def test_fit_again_on_the_author_points(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        store = StoryStore(app.state.services.require_project()[0])
        person = fake_person({"head_neck": 0.16})
        pts = body_points(person, [832, 480])
        body, _ = fit_body(reference_ratios(person), Body(locks=["neck"], neck=1.2), ["neck"])
        store.set_fitted_body(p["id"], "v1", body, "ast_ref", pts, None)
        moved = {**pts, "pose": [list(r) for r in pts["pose"]]}
        for k in (8, 11):
            moved["pose"][k][1] -= 20
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/body/refit", json={"points": moved})
        assert r.status_code == 200, r.text
        out = r.json()
        v = out["profile"]["versions"][0]
        assert v["body"]["neck"] == 1.2                                                              # locked: the author's
        assert v["body"]["torso"] < body.torso and v["body"]["legs"] > body.legs                      # the hips moved up: a shorter torso, longer legs
        assert v["body_points"]["pose"][8][1] == pytest.approx(moved["pose"][8][1]) and v["body_fit_from"] == "ast_ref"
        assert v["body_points"]["sdpose"]["pose"][8][1] == pytest.approx(pts["pose"][8][1])            # SDPose's own read kept (Back to SDPose's points)
        again = cl.post(f"/story/profiles/{p['id']}/versions/v1/body/refit", json={"points": {**moved, "sdpose": {"pose": []}}}).json()["profile"]["versions"][0]
        assert again["body_points"]["sdpose"]["pose"][8][1] == pytest.approx(pts["pose"][8][1])        # a second refit keeps the first read, whatever it is sent
        assert all(abs(x["reference"] - x["fitted"]) / x["reference"] < 0.05 for k, x in out["fit"].items() if k != "head_neck")
        bad = {**pts, "pose": [[0, 0, 0]] * 18}
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/body/refit", json={"points": bad}).status_code == 422   # not a whole figure
        prop = cl.post("/story/profiles", json={"name": "Box", "cls": "prop"}).json()
        assert cl.post(f"/story/profiles/{prop['id']}/versions/v1/body/refit", json={"points": pts}).status_code == 422


def test_the_shell_routes(tmp_path: Path):
    from PIL import Image
    for variant in ("full", "open"):
        app, cl = _client(tmp_path, variant)
        with cl:
            cl.post("/project", json={"path": str(tmp_path / variant / "proj"), "name": "S", "size_cap_gb": 10})
            src = tmp_path / variant / "mara.png"
            Image.new("RGB", (64, 48), (120, 120, 120)).save(src)
            a = cl.post("/assets/import", json={"paths": [str(src)]}).json()["items"][0]
            who = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
            r = cl.post(f"/story/profiles/{who['id']}/versions/v1/shell")
            assert r.status_code == 422 and "animation reference first" in r.json()["detail"]
            cl.put(f"/story/profiles/{who['id']}/versions/v1/anim-ref", json={"side": "front", "asset_id": a["id"]})
            r = cl.post(f"/story/profiles/{who['id']}/versions/v1/shell")
            assert r.status_code == 422 and "fit the body" in r.json()["detail"]                         # D139: the fit reads the stance first
            store = StoryStore(app.state.services.require_project()[0])
            pts = body_points(fake_person(), [64, 48])
            down = {**pts, "pose": [list(x) for x in pts["pose"]]}
            down["pose"][4][0], down["pose"][7][0] = down["pose"][8][0], down["pose"][11][0]              # the arms down, the hands on the hips
            store.set_fitted_body(who["id"], "v1", Body(), a["id"], down, stance_note(person_of(down)))
            r = cl.post(f"/story/profiles/{who['id']}/versions/v1/shell")
            assert r.status_code == 422 and "arms against the body" in r.json()["detail"]                # Pixal3D would fuse them
            moved = {**down, "pose": [list(x) for x in down["pose"]]}
            moved["pose"][4][0] -= 80; moved["pose"][7][0] += 80                                          # the wrists dragged out on the bench
            r = cl.post(f"/story/profiles/{who['id']}/versions/v1/body/refit", json={"points": moved})
            assert r.status_code == 422 and "only on an A-pose" in r.json()["detail"]                    # D140: the picture's stance, not the points dragged
            v = cl.get(f"/story/profiles/{who['id']}").json()["versions"][0]
            assert v["anim_ref_note"] == "arms_close" and v["body_points"]["pose"][4][0] == down["pose"][4][0]   # nothing refitted
            assert cl.post(f"/story/profiles/{who['id']}/versions/v1/body/fit").status_code == 422     # nor fitted again on that picture
            assert cl.post(f"/story/profiles/{who['id']}/versions/v1/shell").status_code == 422
            store.set_fitted_body(who["id"], "v1", Body(), a["id"], pts, None)                              # drawn again in the A-pose and fitted
            r = cl.post(f"/story/profiles/{who['id']}/versions/v1/shell")
            if variant == "open":
                assert r.status_code == 422 and "full only" in r.json()["detail"]
                continue
            assert r.status_code == 200, r.text
            job = next(j for j in cl.get("/jobs").json()["items"] if j["id"] == r.json()["job_id"])
            assert job["recipe"]["kind"] == "image_to_mesh" and job["origin"]["surface"] == "character_shell" and job["origin"]["payload"] == {"version": "v1", "from": a["id"]}
            assert cl.put(f"/story/profiles/{who['id']}/versions/v1/shell", json={"asset_id": a["id"]}).status_code == 422   # an image is not a mesh
            prop = cl.post("/story/profiles", json={"name": "Box", "cls": "prop", "hero_asset_id": a["id"]}).json()
            assert cl.post(f"/story/profiles/{prop['id']}/versions/v1/shell").status_code == 422          # a prop has its model
            # a mesh D109 stood upright, picked as the shell: an un-turned copy is the shell, the Catalogue's own stays as it is
            ws, cat, _ = app.state.services.require_project()
            g = tmp_path / variant / "made.glb"
            a_pose_glb(g)
            from loom2.tools.upright import read_glb, stand_upright
            turned = stand_upright(g)
            mesh = cat.ingest_file(g, kind="mesh", move=True, suite="generate", params={"upright_deg": turned}, parents=[a["id"]], lineage_kind="image-to-mesh")
            v = cl.put(f"/story/profiles/{who['id']}/versions/v1/shell", json={"asset_id": mesh.id}).json()["versions"][0]
            assert v["shell_asset_id"] != mesh.id and v["shell_from"] == a["id"]
            copy = cat.get(v["shell_asset_id"])
            assert copy.parents == [mesh.id] and copy.kind == "mesh" and (copy.params or {}).get("unturned_from") == mesh.id
            assert "rotation" not in read_glb(ws.path / copy.path)[0]["nodes"][0] and "rotation" in read_glb(ws.path / mesh.path)[0]["nodes"][0]
            cleared = cl.put(f"/story/profiles/{who['id']}/versions/v1/shell", json={"asset_id": None})
            assert cleared.status_code == 200 and cleared.json()["versions"][0]["shell_asset_id"] is None


async def test_the_shell_lands_on_its_version(tmp_path: Path, object_info: dict, monkeypatch):
    """The whole path: a character's shell job → the fake engine's GLB → a mesh asset → the version's shell, with its source."""
    import test_lifecycle
    from loom2.groups import GroupStore
    from loom2.story import shell_origin
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    from loom2.engine import finishers
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    stood: list[Path] = []
    monkeypatch.setattr(finishers, "stand_upright", lambda path: stood.append(path) or [0.0, 0.0, 0.0])
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        src = tmp_path / "mara.png"
        Image.new("RGB", (96, 64), (120, 120, 120)).save(src)
        ref = rig.catalogue.ingest_file(src, kind="image", move=False, suite="story")
        store = StoryStore(rig.ws)
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        who = store.create_profile("Mara", "character", groups)
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "image_to_mesh", "asset_id": ref.id}, origin=shell_origin(who.id, who.current, ref.id))[0]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        v = store.profile(who.id).version()
        assert v.shell_asset_id == j.result["asset_ids"][0] and v.shell_from == ref.id and v.model_asset_id is None
        assert stood == [] and rig.catalogue.get(v.shell_asset_id).params.get("upright_deg") is None   # E36: front-on as made, never stood upright
    finally:
        await rig.close()


def test_a_shell_from_an_arms_down_picture_says_so():
    """D139: the sheet and the bench name a shell made from the reference the version has now, when that reference holds its arms down."""
    from loom2.story import ProfileVersion, shell_blocked, shell_from_arms_down
    v = ProfileVersion(id="v1", group_id="grp_x", anim_ref_asset_id="ast_ref", body_fit_from="ast_ref", body_points={"pose": [[0, 0, 1]]},
                       anim_ref_note="arms_close", shell_asset_id="ast_shell", shell_from="ast_ref")
    assert shell_from_arms_down(v) and "A-pose" in (shell_blocked(v) or "")
    assert not shell_from_arms_down(v.model_copy(update={"shell_from": "ast_older"}))               # made from another picture: not this one's fault
    assert not shell_from_arms_down(v.model_copy(update={"anim_ref_note": None})) and shell_blocked(v.model_copy(update={"anim_ref_note": None})) is None
