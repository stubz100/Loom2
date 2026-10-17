"""D92 (wave UI7): the World library — seeded per project on the first read (the built-in vocabulary and the app-wide presets, once), the
revision guard, add / edit / remove (with the Undo's id and place) / reorder, the invariants; Generate's saved panels as a record with a
picture (kept across a client's PUT, set by the finisher for a job made from an applied panel); a subject card's profile link rides on
its mention through resolve_mentions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.library import FIELDS, Library, LibraryEntry, LibraryStore, StaleLibrary, check_library, read_panels, seed_entries  # noqa: E402
from loom2.mentions import resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.origin import JobOrigin  # noqa: E402
from loom2.recipes import T2I, Mention  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_lifecycle import Rig  # noqa: E402
from test_story_cast_d85 import _story  # noqa: E402

KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max > 1)


def test_the_seed_is_the_builtin_vocabulary():
    seed = seed_entries()
    fields = {f for f, _, _ in seed}
    assert fields <= set(FIELDS) and "subject.description" not in fields                     # a subject is a Cast character now (D92)
    assert {"lighting", "mood", "style", "background", "composition", "scene", "text", "negative", "subject.pose", "camera.lens"} <= fields
    assert ("negative", "blur", "blurry, low detail") in seed and ("lighting", "moonlight", "moonlight") in seed   # [name, words] or the words as the name
    check_library(Library(entries=[LibraryEntry(field=f, name=n, text=t) for f, n, t in seed]))  # the seed keeps the invariants


def test_seeded_once_with_the_app_wide_presets(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "snippets.json").write_text(json.dumps({"snippets": [
        {"name": "rim", "field": "lighting", "text": "golden hour rim light"},          # a built-in's words: not twice
        {"name": "my dusk", "field": "lighting", "text": "violet dusk glow"},
        {"name": "Mara", "field": "subject.description", "text": "a wiry courier in a grey coat"},   # kept, though descriptions are not seeded
        {"name": "x", "field": "nope", "text": "dropped"}, {"name": "empty", "field": "mood", "text": "  "}]}), encoding="utf-8")
    ws = Workspace.create(tmp_path / "p", name="P")
    st = LibraryStore(ws.story_dir, state)
    assert not st.path.is_file()
    lib = st.get()
    assert st.path.is_file() and lib.revision == 0 and lib.schema_version == 1                # the first read writes the seed
    snips = [e for e in lib.entries if e.source == "snippet"]
    assert [(e.field, e.name, e.text) for e in snips] == [("lighting", "my dusk", "violet dusk glow"), ("subject.description", "Mara", "a wiry courier in a grey coat")]
    assert len(lib.entries) == len(seed_entries()) + 2
    assert st.get() == lib                                                                     # a second read: the same record, nothing merged again
    (state / "snippets.json").write_text(json.dumps({"snippets": [{"name": "later", "field": "mood", "text": "giddy"}]}), encoding="utf-8")
    assert not any(e.text == "giddy" for e in st.get().entries)                                # the seed is once per project
    other = LibraryStore(Workspace.create(tmp_path / "q", name="Q").story_dir, state).get()
    assert any(e.text == "giddy" for e in other.entries)                                       # a new project seeds from what the app holds then


def test_add_edit_remove_reorder_and_the_revision_guard(tmp_path: Path):
    st = LibraryStore(Workspace.create(tmp_path / "p", name="P").story_dir)
    lib = st.get()
    lib1, e = st.add("lighting", "", "teal rim light from a shop sign", base=lib.revision)
    assert lib1.revision == 1 and e.name == "teal rim light from a shop sign" and e.source == "user" and e.id.startswith("lib_")
    lights = [x.id for x in lib1.entries if x.field == "lighting"]
    assert lights[-1] == e.id                                                                   # at the end of its field, not of the list
    assert [x.field for x in lib1.entries].index("lighting") < lib1.entries.index(e) < len(lib1.entries) - 1
    with pytest.raises(StaleLibrary):
        st.add("mood", "x", "wistful", base=0)
    with pytest.raises(ValueError, match="already in the library"):
        st.add("lighting", "again", "  Teal rim light from a shop sign ")
    with pytest.raises(ValueError, match="not a prompt field"):
        st.add("palette", "x", "y")
    lib2, e2 = st.patch(e.id, {"revision": 1, "name": "shop sign", "text": "teal rim light"})
    assert lib2.revision == 2 and (e2.name, e2.text) == ("shop sign", "teal rim light")
    with pytest.raises(StaleLibrary):
        st.patch(e.id, {"revision": 1, "name": "late"})
    with pytest.raises(ValueError, match="needs a name"):
        st.patch(e.id, {"name": "  "})
    with pytest.raises(KeyError):
        st.patch("lib_gone", {"name": "x"})
    lib3, gone, at = st.remove(e.id, base=2)
    assert lib3.revision == 3 and gone.id == e.id and e.id not in {x.id for x in lib3.entries}
    lib4, back = st.add(gone.field, gone.name, gone.text, entry_id=gone.id, at=at)              # the Undo: the same id, the same place
    assert back.id == gone.id and lib4.entries[at].id == gone.id
    ids = [x.id for x in lib4.entries]
    lib5 = st.reorder([ids[1], ids[0], *ids[2:]], base=lib4.revision)
    assert [x.id for x in lib5.entries][:2] == [ids[1], ids[0]]
    with pytest.raises(ValueError, match="every library entry once"):
        st.reorder(ids[1:])


def _app(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    (state / "snippets.json").write_text(json.dumps({"snippets": [{"name": "my dusk", "field": "lighting", "text": "violet dusk glow"}]}), encoding="utf-8")
    return create_app(state)


def test_routes(tmp_path: Path):
    app = _app(tmp_path)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app, headers=H) as cl:
        assert cl.get("/story/library").status_code == 409                                    # no project
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "L", "size_cap_gb": 10})
        lib = cl.get("/story/library").json()
        assert lib["revision"] == 0 and any(e["source"] == "snippet" and e["text"] == "violet dusk glow" for e in lib["entries"])
        assert set(lib["entries"][0]) == {"id", "field", "name", "text", "source", "group_id"}
        r = cl.post("/story/library/entries", json={"field": "mood", "text": "wistful", "revision": 0})
        assert r.status_code == 200 and r.json()["library"]["revision"] == 1 and r.json()["entry"]["name"] == "wistful"
        eid = r.json()["entry"]["id"]
        assert cl.post("/story/library/entries", json={"field": "mood", "text": "giddy", "revision": 0}).status_code == 409
        assert cl.post("/story/library/entries", json={"field": "mood", "text": "Wistful"}).status_code == 422
        assert cl.post("/story/library/entries", json={"field": "mood", "text": ""}).status_code == 422
        p = cl.patch(f"/story/library/entries/{eid}", json={"revision": 1, "name": "longing"})
        assert p.status_code == 200 and p.json()["entry"]["name"] == "longing" and p.json()["library"]["revision"] == 2
        assert cl.patch(f"/story/library/entries/{eid}", json={"revision": 1, "name": "x"}).status_code == 409
        assert cl.patch("/story/library/entries/lib_gone", json={"name": "x"}).status_code == 404
        d = cl.delete(f"/story/library/entries/{eid}", params={"revision": 2})
        assert d.status_code == 200 and d.json()["entry"]["id"] == eid and d.json()["library"]["revision"] == 3
        undo = cl.post("/story/library/entries", json={"field": "mood", "text": "wistful", "name": "longing", "id": eid, "at": d.json()["index"]})
        assert undo.json()["entry"]["id"] == eid and undo.json()["library"]["entries"][d.json()["index"]]["id"] == eid
        ids = [e["id"] for e in undo.json()["library"]["entries"]]
        o = cl.put("/story/library/order", json={"ids": ids[::-1], "revision": 4})
        assert o.status_code == 200 and o.json()["entries"][0]["id"] == ids[-1]
        assert cl.put("/story/library/order", json={"ids": ids[1:]}).status_code == 422
        assert cl.get("/snippets").status_code == 404                                           # D92: the app-wide snippets are gone


def test_saved_panels_keep_their_picture(tmp_path: Path):
    app = _app(tmp_path)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "L", "size_cap_gb": 10})
        assert cl.get("/project/presets").json() == {"schema_version": 1, "presets": [], "last": None}
        body = {"presets": [{"name": "alley", "panel": {"model_id": KLEIN}, "saved_at": "2026-10-17T08:00:00Z", "thumb_asset_id": "ast_1"}], "last": "alley"}
        assert cl.put("/project/presets", json=body).json()["presets"][0]["thumb_asset_id"] == "ast_1"
        # a client's older copy (no picture) does not wipe the server's; a new picture replaces it; a missing `last` is dropped
        body2 = {"presets": [{"name": "alley", "panel": {"model_id": KLEIN}}, {"name": "dock", "panel": {}}], "last": "gone"}
        got = cl.put("/project/presets", json=body2).json()
        assert [p["thumb_asset_id"] for p in got["presets"]] == ["ast_1", None] and got["last"] is None
        assert cl.put("/project/presets", json={"presets": [{"name": "a", "panel": {}}, {"name": "a", "panel": {}}]}).status_code == 422
        on_disk = json.loads((tmp_path / "proj" / "generate" / "presets.json").read_text(encoding="utf-8"))
        assert on_disk["schema_version"] == 1


def test_a_legacy_presets_file_reads(tmp_path: Path):
    (tmp_path / "generate").mkdir()
    (tmp_path / "generate" / "presets.json").write_text(json.dumps({"presets": [{"name": "old", "panel": {"x": 1}, "saved_at": "t"}], "last": "old"}), encoding="utf-8")
    p = read_panels(tmp_path)
    assert p.presets[0].name == "old" and p.presets[0].thumb_asset_id is None and p.last == "old"


@pytest.mark.asyncio
async def test_a_job_from_an_applied_panel_becomes_its_picture(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        rig.queue.load()
        await rig.queue.start()
        from loom2.library import put_panels
        put_panels(rig.ws.path, {"presets": [{"name": "alley", "panel": {}}], "last": "alley"})
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path)
        origin = JobOrigin(suite="generate", surface="results", payload={"saved_panel": "alley"})
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "an alley", "width": 64, "height": 64, "seeds": [3]}, origin=origin)[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        assert read_panels(rig.ws.path).presets[0].thumb_asset_id == done.result["asset_ids"][0]
        gone = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "x", "width": 64, "height": 64, "seeds": [4]},
                                origin=JobOrigin(suite="generate", surface="results", payload={"saved_panel": "deleted meanwhile"}))[0]
        assert (await rig.wait(gone.id)).status == "done"                                      # a panel that is gone is never the job's failure
    finally:
        await rig.close()


def test_a_subject_link_rides_on_the_profile_mention(tmp_path: Path):
    ws, cat, groups, ids, st = _story(tmp_path)
    p = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier in a grey coat.")
    r = T2I(model_id=KLEIN, prompt_mode="tree", prompt_json={"subjects": [{"description": "Mara, a wiry courier in a grey coat."}]},
            mentions=[Mention(profile_id=p.id, name="Mara", group_id=p.version().group_id, subject=0)])
    out = resolve_mentions(r, groups, cat, 4, st)
    m = out.mentions[0]
    assert m.subject == 0 and m.profile_id == p.id and m.revision is not None and out.refs[0].asset_id == ids[0]   # the hero as a reference, the link kept
    assert T2I.model_validate(out.model_dump()).mentions[0].subject == 0                         # stored with the recipe, back on Load
