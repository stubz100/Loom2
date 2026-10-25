"""proto01_UIcast CW3–CW5 (D142; 06 §2.7, 02 §7, 03 §4): a Cast version's bench is a stage made once and kept (a character's figure bound
to it; a prop's model at its height beside a 1.75 m figure); benches and the line-up stay out of the stage list; a prop's height is read
from its words; the line-up stands Cast's characters and props and ideas with clay side by side, made again each time."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.body import Body  # noqa: E402
from loom2.ideas import IdeaStore  # noqa: E402
from loom2.sizes import prop_height  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_ideas_cw1 import _picture  # noqa: E402
from test_skeleton_bench_cs2 import _client  # noqa: E402


def test_a_props_height_from_its_words():
    assert prop_height("Grandma's cup") == 0.1 and prop_height("old wardrobe") == 2.0 and prop_height("coffee table") == 0.45
    assert prop_height("two barrels") == 0.9 and prop_height("the thing", None) == 1.0


def test_benches_and_the_lineup(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        StoryStore(ws).set_fitted_body(mara["id"], "v1", Body(height_m=1.62, figure="female"), "ast_ref", None, None)
        cup = cl.post("/story/profiles", json={"name": "Grandma cup", "cls": "prop"}).json()
        assert cup["versions"][0]["height_m"] == 0.1                                                     # CW4: read from its name
        harbour = cl.post("/story/profiles", json={"name": "Harbour", "cls": "place"}).json()
        # a character's bench: made once, kept; out of the stage list
        r = cl.post("/stages/bench", json={"profile_id": mara["id"]})
        assert r.status_code == 200, r.text
        st, made = r.json()["stage"], r.json()["made"]
        assert made and st["purpose"] == "bench" and st["bound"] == {"profile_id": mara["id"], "version": "v1"}
        fig = st["objects"][0]
        assert fig["kind"] == "mannequin" and fig["profile_id"] == mara["id"] and fig["body"]["height_m"] == 1.62
        again = cl.post("/stages/bench", json={"profile_id": mara["id"], "version": "v1"}).json()
        assert again["stage"]["id"] == st["id"] and again["made"] is False
        assert st["id"] not in [s["id"] for s in cl.get("/stages").json()["items"]]
        assert st["id"] in [s["id"] for s in cl.get("/stages?purpose=all").json()["items"]]
        # a prop's bench needs its model; then its model at its height beside a 1.75 m figure; a place has none yet
        assert cl.post("/stages/bench", json={"profile_id": cup["id"]}).status_code == 422
        mesh = _picture(cat, tmp_path, "model")                                                       # any asset stands in for the GLB here
        StoryStore(ws).set_model(cup["id"], "v1", mesh.id, None)
        objs = cl.post("/stages/bench", json={"profile_id": cup["id"]}).json()["stage"]["objects"]
        assert objs[0]["kind"] == "mesh" and objs[0]["height_m"] == 0.1 and objs[0]["profile_id"] == cup["id"]
        assert objs[1]["kind"] == "mannequin" and objs[1]["profile_id"] is None and objs[1]["transform"]["pos"][0] < 0
        assert cl.post("/stages/bench", json={"profile_id": harbour["id"]}).status_code == 422
        # the line-up: Mara (bound), an idea with clay (free, its body), an idea without clay and the place left out; made again in place
        groups = svc.require_groups()
        ideas = IdeaStore(ws)
        a = ideas.create("character", groups, _picture(cat, tmp_path, "a", "a tall knight").id)
        ideas.set_clay(a.id, a.variants[0].id, step="done", body=Body(height_m=1.9).model_dump(), shell_asset_id="ast_shell")
        b = ideas.create("character", groups, _picture(cat, tmp_path, "b", "a goblin").id)
        r = cl.post("/stages/lineup", json={"items": [{"profile_id": mara["id"]}, {"idea_id": a.id}, {"idea_id": b.id}, {"profile_id": cup["id"]}, {"profile_id": harbour["id"]}]})
        assert r.status_code == 200, r.text
        lu = r.json()
        assert lu["purpose"] == "lineup" and lu["objects"][0]["preset"] == "lineup"
        row = lu["objects"][1:]
        assert [o["name"] for o in row] == ["Mara", "tall knight", "Grandma cup"]                          # the idea named from its prompt (U3)
        assert row[0]["profile_id"] == mara["id"] and row[1]["profile_id"] is None and row[1]["body"]["height_m"] == 1.9 and row[1]["shadow_proxy"] == "ast_shell"
        assert row[2]["kind"] == "mesh" and row[2]["height_m"] == 0.1
        xs = [o["transform"]["pos"][0] for o in row]
        assert xs == sorted(xs) and abs(xs[0] + xs[-1]) < 1.5                                             # left to right, about the middle
        again = cl.post("/stages/lineup", json={"items": [{"idea_id": a.id}]}).json()
        assert again["id"] == lu["id"] and len(again["objects"]) == 2                                      # the one line-up, made again
        assert cl.post("/stages/lineup", json={"items": [{"idea_id": b.id}]}).status_code == 422       # nothing with clay
        assert lu["id"] not in [s["id"] for s in cl.get("/stages").json()["items"]]


def _png(path: Path) -> tuple[str, bytes]:
    import hashlib
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (90, 90, 90)).save(buf, format="PNG")
    data = buf.getvalue()
    return hashlib.sha256(data).hexdigest(), data


def test_prototype_from_clay(tmp_path: Path):
    """CW3: Prototype ▸ on a free figure or mesh in Clay — an idea whose picture is Clay's view of it and whose clay is the object; Keep ▶
    carries a figure's body and shell (by hand: no A-pose picture) or a mesh's model and height; the line-up stands an idea's prop."""
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        _, cat, _ = svc.require_project()
        groups = svc.require_groups()
        sha, data = _png(tmp_path)
        assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
        model = _picture(cat, tmp_path, "glb")                                                         # stands in for a mesh asset
        r = cl.post("/story/ideas/from-clay", json={"cls": "prop", "name": "Old lantern", "blob": sha, "clay": {"kind": "model", "model_asset_id": model.id, "height_m": 0.4}})
        assert r.status_code == 200, r.text
        idea = r.json()
        v = idea["variants"][0]
        assert idea["name"] == "Old lantern" and groups.parent[("asset", v["asset_id"])] == idea["group_id"]   # the view on the idea's page
        assert cat.get(v["asset_id"]).parents == [model.id]                                               # its lineage: the model it shows
        assert v["clay"]["model_asset_id"] == model.id and v["clay"]["height_m"] == 0.4 and v["clay"]["step"] == "done"
        p = cl.post(f"/story/ideas/{idea['id']}/keep", json={"variant_id": v["id"]}).json()["profile"]
        assert p["cls"] == "prop" and p["versions"][0]["model_asset_id"] == model.id and p["versions"][0]["height_m"] == 0.4
        lu = cl.post("/stages/lineup", json={"items": [{"idea_id": idea["id"]}]}).json()
        assert lu["objects"][1]["kind"] == "mesh" and lu["objects"][1]["height_m"] == 0.4
        fig = cl.post("/story/ideas/from-clay", json={"cls": "character", "name": "Tall one", "blob": sha, "clay": {"kind": "figure", "body": {"height_m": 1.95}, "shell_asset_id": model.id}}).json()
        ch = cl.post(f"/story/ideas/{fig['id']}/keep", json={"variant_id": fig["variants"][0]["id"]}).json()["profile"]["versions"][0]
        assert ch["body"]["height_m"] == 1.95 and ch["body_fit_from"] is None and ch["shell_asset_id"] == model.id   # by hand, with its shell
        assert cl.post("/story/ideas/from-clay", json={"cls": "prop", "name": "x", "blob": sha, "clay": {"kind": "figure"}}).status_code == 422
        assert cl.post("/story/ideas/from-clay", json={"cls": "prop", "name": "x", "blob": "0" * 64, "clay": {"kind": "model"}}).status_code == 422
