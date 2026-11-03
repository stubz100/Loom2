"""U5a (D157 G8, G9; proto01_UI2 04 §3.2, 06 §2.4): clip blocks on the figures' tracks, animation templates, motion *Import…*.

- a stage of schema 4 keeps each figure's clip blocks (`tracks`), validated (a figure's, unique ids, a clip that ends after it starts);
  a figure removed takes its track; a stage of schema 3 reads at 4 without its bodies touched again;
- a block is part of what a final read of its figure (a figure without blocks keeps its stamp); the recipe graph counts the clips;
- the project's templates are revision-guarded; *Save to my library* makes one the author's in every project;
- *Import…* copies a motion file into the local folder (none set: refused), a name already there numbered.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.animations import AnimationStore, AnimationTemplate, StaleAnimations  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.fsio import atomic_write_json, read_json  # noqa: E402
from loom2.shot_graph import stage_stamps  # noqa: E402
from loom2.stages import StageObject, StageStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

WALK = {"source": {"kind": "library", "id": "mot_0123456789ab", "clip": "Walk_Loop"}, "start": 12, "loops": 3, "path": True}


def test_a_figures_track_of_clip_blocks(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    stages = StageStore(ws)
    st = stages.create("Pier")
    figs = [StageObject(id="fig_a", kind="mannequin", name="Ines").model_dump(), StageObject(id="box", kind="prop", name="Crate").model_dump()]
    st = stages.put(st.id, {"revision": st.revision, "objects": figs})
    before = stage_stamps(st, st.cameras[0].id)
    st = stages.put(st.id, {"revision": st.revision, "tracks": {"fig_a": [WALK]}})
    b = st.tracks["fig_a"][0]
    assert b.id.startswith("blk_") and (b.start, b.loops, b.speed, b.blend_in, b.foot_lock, b.path) == (12, 3, 1.0, 6, True, True)
    after = stage_stamps(st, st.cameras[0].id)
    assert after["object:fig_a"] != before["object:fig_a"] and after["object:box"] == before["object:box"]   # the block is part of the figure
    again = stages.put(st.id, {"revision": st.revision, "tracks": {"fig_a": [{**b.model_dump(), "length": 329}]}})
    assert stage_stamps(again, st.cameras[0].id)["object:fig_a"] == after["object:fig_a"]                     # its measured length is not
    assert stages.put(st.id, {"revision": again.revision, "tracks": {"nobody": [WALK]}}).tracks == {}            # no such object: pruned
    for bad in ({"box": [WALK]}, {"fig_a": [{**WALK, "id": "blk_1"}, {**WALK, "id": "blk_1"}]},
                {"fig_a": [{**WALK, "trim_in": 2.0, "trim_out": 1.0}]}, {"fig_a": [{**WALK, "speed": 9.0}]}):
        with pytest.raises(ValueError):
            stages.put(st.id, {"revision": stages.get(st.id).revision, "tracks": bad})
    gone = stages.put(st.id, {"revision": stages.get(st.id).revision, "objects": [figs[1]]})
    assert gone.tracks == {}                                                                                   # the figure took its track


def test_schema_3_reads_at_4_once(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    stages = StageStore(ws)
    st = stages.create("Old")
    body = {"height_m": 1.62, "neck": 1.4}
    raw = st.model_dump() | {"schema_version": 3, "objects": [{"id": "fig", "kind": "mannequin", "name": "Mara", "body": body, "detail": "female"}]}
    raw.pop("tracks")
    atomic_write_json(stages.path(st.id), raw)
    got = stages.get(st.id)
    assert got.schema_version == 4 and got.tracks == {} and got.objects[0].body.neck == pytest.approx(1.4)       # a body of schema 3 is not rebased again


def test_templates_and_the_library(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = AnimationStore(ws.stages_dir, tmp_path / "state")
    t = AnimationTemplate(name="Look back", frames=29, keys=[{"frame": 0, "ease": "ease", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}}])
    b = store.put(0, [t])
    assert b.revision == 1 and [x.name for x in store.book().items] == ["Look back"]
    with pytest.raises(StaleAnimations):
        store.put(0, [])
    with pytest.raises(ValueError):
        store.put(1, [t.model_copy(update={"keys": [{"frame": 40, "transform": {}}]})])                     # a key past its length
    store.to_library(t.id)
    other = AnimationStore(Workspace.create(tmp_path / "q", name="Q").stages_dir, tmp_path / "state")          # another project
    assert [x.id for x in other.library()] == [t.id] and other.book().items == []
    other.from_library_remove(t.id)
    assert store.library() == []


def test_the_library_written_over_and_a_thumbnail(tmp_path: Path):
    """D182 (C2b): a library animation is written over (*Save* on the animation bench); a thumbnail lands on the project's item or the library's."""
    ws = Workspace.create(tmp_path / "p", name="P")
    store = AnimationStore(ws.stages_dir, tmp_path / "state")
    t = AnimationTemplate(name="Glance", frames=12, keys=[{"frame": 0, "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}}],
                          source={"file_id": "mot_a", "clip": "Walk_Loop", "licence": "CC0"})
    store.put(0, [t])
    with pytest.raises(KeyError):
        store.library_put(t)                                                                                # not in the library yet
    store.to_library(t.id)
    edited = t.model_copy(update={"name": "Glance back", "frames": 24, "keys": t.keys + [{"frame": 23, "transform": {"pos": [0, 0, 1]}}]})
    store.library_put(edited)
    lib = store.library()[0]
    assert (lib.name, lib.frames, len(lib.keys), lib.source.clip, lib.source.licence) == ("Glance back", 24, 2, "Walk_Loop", "CC0")
    with pytest.raises(ValueError):
        store.library_put(edited.model_copy(update={"keys": [{"frame": 40, "transform": {}}]}))
    assert store.set_thumb(t.id, "ast_p").thumb_asset_id == "ast_p" and store.book().items[0].thumb_asset_id == "ast_p"   # the project's item
    assert store.book().revision == 1                                                                       # a thumbnail is no edit of the keys
    store.put(1, [])
    assert store.set_thumb(t.id, "ast_l").thumb_asset_id == "ast_l" and store.library()[0].thumb_asset_id == "ast_l"   # then the library's
    with pytest.raises(KeyError):
        store.set_thumb("anm_none", "ast_x")


def test_the_routes_and_motion_import(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        a = cl.get("/stages/animations", headers=H).json()
        assert a == {"revision": 0, "items": [], "library": []}
        t = {"name": "Wave", "frames": 24, "keys": [{"frame": 0, "transform": {"pos": [0, 0, 0]}}]}
        r = cl.put("/stages/animations", json={"revision": 0, "items": [t]}, headers=H)
        assert r.status_code == 200 and r.json()["revision"] == 1
        aid = r.json()["items"][0]["id"]
        assert cl.put("/stages/animations", json={"revision": 0, "items": []}, headers=H).status_code == 409
        r = cl.post(f"/stages/animations/{aid}/library", headers=H)
        assert r.status_code == 200 and [x["id"] for x in r.json()["library"]] == [aid]
        # D182 (C2b): the library written over, the thumbnail from an uploaded PNG, the animation bench
        r = cl.post(f"/stages/animations/{aid}/library", headers=H)
        over = {**r.json()["library"][0], "name": "Wave twice", "frames": 48}
        assert cl.put(f"/stages/animations/library/{aid}", json=over, headers=H).json()["library"][0]["name"] == "Wave twice"
        assert cl.put("/stages/animations/library/anm_x", json=over, headers=H).status_code == 422          # the id is the path's
        assert cl.put(f"/stages/animations/library/{aid}", json={**over, "keys": [{"frame": 90, "transform": {}}]}, headers=H).status_code == 422
        # D183 (C2c): the character the animation is tried on, kept on the record
        assert cl.put(f"/stages/animations/library/{aid}", json={**over, "try_on": "prf_x"}, headers=H).json()["library"][0]["try_on"] == "prf_x"
        assert cl.get("/stages/animations", headers=H).json()["library"][0]["try_on"] == "prf_x"
        import hashlib
        import io as _io
        from PIL import Image
        buf = _io.BytesIO()
        Image.new("RGB", (64, 36), (40, 40, 48)).save(buf, format="PNG")
        png = buf.getvalue()
        sha = hashlib.sha256(png).hexdigest()
        assert cl.post(f"/stages/animations/{aid}/thumbnail", json={"blob": sha}, headers=H).status_code == 422   # not uploaded yet
        assert cl.put(f"/blobs/{sha}", content=png, headers=H).status_code == 200
        r = cl.post(f"/stages/animations/{aid}/thumbnail", json={"blob": sha}, headers=H)
        assert r.status_code == 200, r.text
        thumb = r.json()["items"][0]["thumb_asset_id"]
        assert thumb and cl.get(f"/assets/{thumb}", headers=H).json()["lineage_kind"] == "animation-thumb"
        assert cl.post("/stages/animations/anm_none/thumbnail", json={"blob": sha}, headers=H).status_code == 404
        b = cl.post("/stages/animation-bench", json={"name": "Wave", "frames": 48}, headers=H)
        assert b.status_code == 200, b.text
        bench = b.json()
        assert (bench["purpose"], bench["name"], bench["range"], [o["kind"] for o in bench["objects"]], len(bench["cameras"])) == ("animation", "Animation · Wave", {"start": 0, "end": 47}, ["mannequin"], 1)
        again = cl.post("/stages/animation-bench", json={"name": "Nod", "frames": 10}, headers=H).json()
        assert again["id"] == bench["id"] and again["name"] == "Animation · Nod" and again["revision"] == bench["revision"] + 1   # the one bench, made again
        assert bench["id"] not in [x["id"] for x in cl.get("/stages", headers=H).json()["items"]]                              # out of the pickers
        assert [x["id"] for x in cl.get("/stages?purpose=animation", headers=H).json()["items"]] == [bench["id"]]
        assert cl.delete(f"/stages/animations/library/{aid}", headers=H).json()["library"] == []
        src = tmp_path / "Wave.glb"
        src.write_bytes(b"glTF-not-really")                                                                  # the scanner does not parse
        assert cl.post("/motion/import", json={"path": str(src)}, headers=H).status_code == 422                # no local folder yet
        local = tmp_path / "motion-local"
        local.mkdir()
        cl.put("/settings", json={"motion": {"starter_dir": "", "local_dir": str(local)}}, headers=H)
        r = cl.post("/motion/import", json={"path": str(src)}, headers=H)
        assert r.status_code == 200, r.text
        assert cl.post("/motion/import", json={"path": str(src)}, headers=H).status_code == 200
        assert sorted(p.name for p in local.iterdir()) == ["Wave 2.glb", "Wave.glb"]
        assert cl.post("/motion/import", json={"path": str(tmp_path / "notes.txt")}, headers=H).status_code == 422
