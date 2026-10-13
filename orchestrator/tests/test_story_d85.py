"""17 (D85) · SY0: the Story world — invariants, the store's revision guard, the routes — and the style a generation carries: resolved to
its fragment at preview and submit, appended after the prompt per model family, both kept in the asset's manifest."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine import graphs  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import T2I, RefImage  # noqa: E402
from loom2.story import StoryBeat, StaleWorld, StoryStore, StoryStyle, StoryVariable, World, check_world, resolve_style  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_lifecycle import Rig  # noqa: E402

DEV = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and s.sampling.json_prompt and s.inputs.refs_max > 1)
KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max > 1)


def test_world_invariants():
    check_world(World(styles=[StoryStyle(id="a", name="Ink"), StoryStyle(id="b", name="Wash")], default_style="a", spine=[StoryBeat(id="x", title="Open")],
                      variables=[StoryVariable(name="met_mara"), StoryVariable(name="door", type="enum", values=["open", "shut"], default="open")]))
    with pytest.raises(ValueError, match="style ids"):
        check_world(World(styles=[StoryStyle(id="a", name="Ink"), StoryStyle(id="a", name="Wash")]))
    with pytest.raises(ValueError, match="style names"):
        check_world(World(styles=[StoryStyle(id="a", name="Ink"), StoryStyle(id="b", name=" ink ")]))
    with pytest.raises(ValueError, match="needs a name"):
        check_world(World(styles=[StoryStyle(id="a", name="  ")]))
    with pytest.raises(ValueError, match="default style"):
        check_world(World(styles=[StoryStyle(id="a", name="Ink")], default_style="zz"))
    with pytest.raises(ValueError, match="beat ids"):
        check_world(World(spine=[StoryBeat(id="x", title="a"), StoryBeat(id="x", title="b")]))
    with pytest.raises(ValueError, match="variable names"):
        check_world(World(variables=[StoryVariable(name="a"), StoryVariable(name="a")]))
    with pytest.raises(ValueError, match="identifier|letters"):
        check_world(World(variables=[StoryVariable(name="1st")]))
    with pytest.raises(ValueError, match="distinct, non-empty"):
        check_world(World(variables=[StoryVariable(name="door", type="enum", values=[], default="x")]))
    with pytest.raises(ValueError, match="one of its values"):
        check_world(World(variables=[StoryVariable(name="door", type="enum", values=["open"], default="shut")]))
    with pytest.raises(ValueError, match="true or false"):
        check_world(World(variables=[StoryVariable(name="flag", default="yes")]))


def test_store_world_revision_guard(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    w0 = st.world()
    assert w0.revision == 0 and w0.styles == [] and not st.world_path.is_file()                  # a read writes nothing
    w1 = st.put_world({"revision": 0, "logline": "A courier.", "styles": [{"id": "a", "name": "Ink", "fragment": "ink and wash"}], "default_style": "a"})
    assert w1.revision == 1 and w1.logline == "A courier." and st.world_path.is_file() and w1.created_at == w0.created_at
    assert st.world() == w1 and st.style("a").fragment == "ink and wash" and st.style("zz") is None
    with pytest.raises(StaleWorld):
        st.put_world({"revision": 0, "logline": "again"})
    with pytest.raises(ValueError):
        st.put_world({"revision": 1, "default_style": "zz"})
    assert st.world().revision == 1
    w2 = st.put_world({"revision": 1, "spine": [{"id": "b1", "title": "Open", "line": "She arrives."}], "schema_version": 99, "created_at": "nope"})
    assert w2.revision == 2 and w2.schema_version == 1 and w2.created_at == w0.created_at and w2.spine[0].title == "Open"   # the server's fields stay its own


def test_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        assert cl.get("/story/world", headers=H).status_code == 409                                   # no project
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        w = cl.get("/story/world", headers=H).json()
        assert w["revision"] == 0 and w["styles"] == [] and w["default_style"] is None
        body = {**w, "logline": "A courier.", "styles": [{"id": "sty_a", "name": "Ink", "fragment": "ink and wash", "group_id": None}], "default_style": "sty_a",
                "variables": [{"name": "met", "type": "bool", "values": [], "default": False}]}
        r = cl.put("/story/world", json=body, headers=H)
        assert r.status_code == 200 and r.json()["revision"] == 1 and r.json()["styles"][0]["name"] == "Ink"
        assert cl.put("/story/world", json=body, headers=H).status_code == 409                            # based on revision 0 again
        assert cl.put("/story/world", json={**body, "revision": 1, "default_style": "zz"}, headers=H).status_code == 422
        assert cl.get("/story/world", headers=H).json()["logline"] == "A courier."
        assert (Workspace(tmp_path / "proj").story_dir / "world.json").is_file()


# ---- the style a generation carries ---------------------------------------------------------------------------------------------
def test_resolve_style_stamps_the_fragment(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    st.put_world({"revision": 0, "styles": [{"id": "a", "name": "Ink", "fragment": "  ink and wash  "}]})
    r = T2I(model_id=KLEIN, prompt_text="a courier", style_id="a")
    out = resolve_style(r, st)
    assert out.style_text == "ink and wash" and out.style_id == "a"
    assert resolve_style(out, st) is out                                                             # stamped: not resolved again
    assert resolve_style(T2I(model_id=KLEIN, prompt_text="x"), None).style_id is None                # no style: nothing to do, no project needed
    with pytest.raises(ValueError, match="does not exist"):
        resolve_style(T2I(model_id=KLEIN, style_id="zz"), st)
    with pytest.raises(ValueError, match="open project"):
        resolve_style(r, None)


def test_the_style_is_appended_after_the_prompt_per_family():
    refs = [RefImage(asset_id="a", note="the hero")]
    text, mode = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="a courier at the gate", style_text="ink and wash", refs=refs))
    assert (text, mode) == ("a courier at the gate. ink and wash. Image 1 shows the hero.", "text")      # after the prompt, before the reference sentences
    text, _ = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="a courier", style_text=""))
    assert text == "a courier"                                                                         # an empty fragment adds nothing
    prose, mode = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="tree", prompt_json={"scene": "a gate", "style": "painterly"}, style_text="ink and wash"))
    assert mode == "prose" and "style: painterly, ink and wash" in prose
    js, mode = graphs.serialize_prompt(T2I(model_id=DEV, prompt_mode="tree", prompt_json={"scene": "a gate"}, style_text="ink and wash"))
    assert mode == "json" and '"style":"ink and wash"' in js
    ep = graphs.effective_params(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="x", style_id="a", style_text="ink and wash"))
    assert ep["style_id"] == "a" and ep["style_text"] == "ink and wash"


def test_preview_resolves_the_style_like_a_submit(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        w = cl.get("/story/world").json()
        cl.put("/story/world", json={**w, "styles": [{"id": "sty_a", "name": "Ink", "fragment": "ink and wash", "group_id": None}]})
        p = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "text", "prompt_text": "a courier", "style_id": "sty_a"}}).json()
        assert p["style_id"] == "sty_a" and p["style_text"] == "ink and wash" and p["serialized_prompt"] == "a courier. ink and wash"
        assert cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_text": "x", "style_id": "zz"}}).status_code == 422
        none = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "text", "prompt_text": "a courier"}}).json()
        assert none["style_id"] is None and none["serialized_prompt"] == "a courier"


async def test_the_asset_records_the_style_it_ran_with(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        st = StoryStore(rig.ws)
        st.put_world({"revision": 0, "styles": [{"id": "sty_a", "name": "Ink", "fragment": "ink and wash"}]})
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path)   # weights in the fake tree
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "a courier", "seeds": [3], "width": 64, "height": 64, "style_id": "sty_a"})[0]
        assert job.recipe["style_text"] == "ink and wash"                                            # stamped before the job record was written
        st.put_world({"revision": 1, "styles": [{"id": "sty_a", "name": "Ink", "fragment": "changed since"}]})
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        a = rig.catalogue.get(done.result["asset_ids"][0])
        assert a.params["style_id"] == "sty_a" and a.params["style_text"] == "ink and wash" and a.params["recipe"]["style_id"] == "sty_a"
        assert a.prompt_text.endswith("ink and wash")                                                 # the text that ran, not today's fragment
    finally:
        await rig.close()
