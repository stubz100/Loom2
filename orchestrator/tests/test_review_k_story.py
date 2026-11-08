"""The 2026-11-06 review register (journal 10:18), the Story / ideas / stages / sets backend: K30–K32, K36, K37, K50–K52, K88, K91 — one
test (or a few) per fixed finding."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import set_things  # noqa: E402
from loom2.ideas import IdeaStore  # noqa: E402
from loom2.origin import JobOrigin  # noqa: E402
from loom2.stages import Pose, StageStore  # noqa: E402
from loom2.story import Profile, ProfileVersion, StaleProfile, StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_skeleton_bench_cs2 import _client  # noqa: E402


def _open(tmp_path: Path):
    app, cl = _client(tmp_path)
    cl.__enter__()
    assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
    svc = app.state.services
    ws, cat, _ = svc.require_project()
    return app, cl, svc, ws, cat, svc.require_groups()


def _picture(cat, tmp_path: Path, name: str, prompt: str = "a woman in a yellow raincoat"):
    src = tmp_path / f"{name}.png"
    Image.new("RGB", (64, 48), (120, 120, 120)).save(src)
    return cat.ingest_file(src, kind="image", move=False, suite="generate", prompt_text=prompt, model_id="flux2_klein_9b", seed=7)


def _at_once(fns: list) -> list:
    """Run the callables on threads released together; their results (or exceptions) in order."""
    gate, out = threading.Barrier(len(fns)), [None] * len(fns)

    def run(i: int, fn) -> None:
        gate.wait()
        try:
            out[i] = fn()
        except Exception as e:  # noqa: BLE001
            out[i] = e
    ts = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return out


# ---- K30 / K31: the profiles and the Flow under story's lock ---------------------------------------------------------------------
def test_k30_profile_setters_and_patches_take_turns(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        store = StoryStore(ws)
        names = [f"pose {i}" for i in range(8)]
        _at_once([lambda n=n: store.set_pose(p["id"], "v1", n, Pose(preset="stand")) for n in names])
        after = store.profile(p["id"])
        assert sorted(after.version("v1").poses) == names and after.revision == p["revision"] + 8      # none written over another
        base = after.revision
        got = _at_once([lambda i=i: store.patch_profile(p["id"], {"revision": base, "versions": [{"id": "v1", "outfit": f"coat {i}"}]}) for i in range(4)])
        assert sum(isinstance(g, Profile) for g in got) == 1 and sum(isinstance(g, StaleProfile) for g in got) == 3   # one base, one pass
    finally:
        cl.__exit__(None, None, None)


def test_k31_the_flow_repair_keeps_a_node_made_meanwhile(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StoryStore(ws)
    a = store.create_node("shot", "A", 40.0, 40.0)
    snapshot = store.flow_nodes()                                       # the GET's read, before …
    b = store.create_node("shot", "B", 500.0, 300.0)                   # … a quick second New shot
    store.put_graph({"revision": store.flow_graph().revision, "edges": [{"from": a.id, "port": "out", "to": b.id}]})
    g = store.flow_graph(snapshot)                                     # the repair against the old snapshot dropped B and its edge
    assert any(pl.id == b.id and pl.x == 500.0 for pl in g.nodes) and [(e.from_, e.to) for e in g.edges] == [(a.id, b.id)]
    g2, nodes = store.flow_state()
    assert set(nodes) == {a.id, b.id} and {pl.id for pl in g2.nodes} == {a.id, b.id}


# ---- K32: ideas ----------------------------------------------------------------------------------------------------------------------
def test_k32_idea_changes_take_turns(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        pic = _picture(cat, tmp_path, "a")
        idea = cl.post("/story/ideas", json={"cls": "character", "asset_id": pic.id}).json()
        store = IdeaStore(ws)
        vid = idea["variants"][0]["id"]
        _at_once([lambda i=i: store.add_made_for(idea["id"], [f"ast_{i:08x}"]) for i in range(6)]
                 + [lambda: store.set_clay(idea["id"], vid, step="fitting", job_id="job_x")])
        after = store.get(idea["id"])
        assert sorted(after.made_for) == [f"ast_{i:08x}" for i in range(6)] and after.variants[0].clay.step == "fitting"
        assert after.revision == idea["revision"] + 7
    finally:
        cl.__exit__(None, None, None)


# ---- K36: a hero on a final version's locked set ---------------------------------------------------------------------------------------
def test_k36_a_hero_on_a_locked_set_is_copied_not_taken(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        a = _picture(cat, tmp_path, "a")
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": a.id}).json()
        assert groups.parent[("asset", a.id)] == mara["versions"][0]["group_id"]                     # nobody's: moved
        StoryStore(ws).lock_version(mara["id"], "v1", groups)
        n0 = len(groups.groups)
        cl.post("/story/profiles", json={"name": "Nora", "cls": "character"})
        per_profile = len(groups.groups) - n0                                                       # its homes and its set
        n_groups = len(groups.groups)
        r = cl.post("/story/profiles", json={"name": "Mara's twin", "cls": "character", "hero_asset_id": a.id})
        assert r.status_code == 200, r.text                                                         # was 423, an orphan home + set each retry
        twin = r.json()
        hero = twin["versions"][0]["hero_asset_id"]
        assert hero != a.id and cat.get(hero).duplicate_of == a.id
        assert groups.parent[("asset", a.id)] == mara["versions"][0]["group_id"]                     # the final set keeps its picture
        assert groups.parent[("asset", hero)] == twin["versions"][0]["group_id"]
        assert len(groups.groups) == n_groups + per_profile                                         # made once, nothing orphaned
    finally:
        cl.__exit__(None, None, None)


# ---- K37 / K88: Bring the ideas in, Keep ▶ -----------------------------------------------------------------------------------------
def test_k37_fold_skips_an_idea_whose_picture_is_trashed(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        a, b = _picture(cat, tmp_path, "a"), _picture(cat, tmp_path, "b", "a brass bell")
        gone = cl.post("/story/ideas", json={"cls": "character", "asset_id": a.id}).json()
        bell = cl.post("/story/ideas", json={"cls": "prop", "asset_id": b.id}).json()
        assert cl.post("/assets/trash", json={"ids": [gone["variants"][0]["asset_id"]]}).status_code == 200
        r = cl.post("/story/ideas/fold")
        assert r.status_code == 200, r.text                                                         # was a 500, the ideas after it never folded
        out = r.json()
        assert [x["idea_id"] for x in out["items"]] == [bell["id"]]
        assert [(x["idea_id"], "Trash" in x["reason"]) for x in out["skipped"]] == [(gone["id"], True)]
    finally:
        cl.__exit__(None, None, None)


def test_k88_keep_refuses_another_class_before_copying(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        a = _picture(cat, tmp_path, "a")
        idea = cl.post("/story/ideas", json={"cls": "character", "asset_id": a.id}).json()
        bell = cl.post("/story/profiles", json={"name": "Bell", "cls": "prop"}).json()
        manifests = lambda: sorted(x.name for x in (ws.path / "assets").rglob("*.json"))  # noqa: E731
        before = manifests()
        r = cl.post(f"/story/ideas/{idea['id']}/keep", json={"variant_id": idea["variants"][0]["id"], "profile_id": bell["id"]})
        assert r.status_code == 422 and "kept as a character" in r.json()["detail"]
        assert manifests() == before                                                                 # no copy of the picture left behind
    finally:
        cl.__exit__(None, None, None)


# ---- K88: the Story store's smaller faults ---------------------------------------------------------------------------------------
def test_k88_a_node_file_gone_mid_listing_is_no_500(tmp_path: Path, monkeypatch):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StoryStore(ws)
    a = store.create_node("shot", "A")
    b = store.create_node("shot", "B")
    import loom2.story as story_mod
    from loom2.fsio import StateError
    real = story_mod.read_json

    def vanished(p):
        if Path(p).name == f"{b.id}.json":
            raise StateError(f"missing record: {p}") from FileNotFoundError(p)
        return real(p)
    monkeypatch.setattr(story_mod, "read_json", vanished)
    assert set(store.flow_nodes()) == {a.id} and store.flow_node(b.id) is None


def test_k88_an_unknown_shot_rewrites_no_index(tmp_path: Path, monkeypatch):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StoryStore(ws)
    store.create_node("shot", "A")
    import loom2.story as story_mod
    writes: list[str] = []
    real = story_mod.atomic_write_json
    monkeypatch.setattr(story_mod, "atomic_write_json", lambda p, d, *a, **k: (writes.append(Path(p).name), real(p, d, *a, **k))[1])
    assert store.shot("sht_nothere") is None and store.shot("sht_nothere") is None
    assert "shots.json" not in writes


def test_k88_a_final_version_refuses_before_a_camera_is_copied(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    store, stages = StoryStore(ws), StageStore(ws)
    st = stages.create("Scene")
    cam = st.cameras[0].id
    one = store.create_shot("One", stage_id=st.id, camera_id=cam, stage_revision=st.revision)
    two = store.create_shot("Two")
    store._change_part(two.id, lambda part, r: part.model_copy(update={"versions": [v.model_copy(update={"state": "final"}) for v in part.versions]}))
    with pytest.raises(ValueError, match="final"):
        store.set_source(two.id, "v1", st.id, cam, st.revision)
    assert len(stages.get(st.id).cameras) == len(stages.get(st.id).cameras) == 1 and one.id    # no copy made for a refused source


# ---- K50: the stage's read-modify-writes ------------------------------------------------------------------------------------------
def test_k50_an_image_set_keeps_an_edit_made_while_its_relief_is_read(tmp_path: Path, monkeypatch):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StageStore(ws)
    st = store.create("Room")
    import loom2.relief as relief

    def slow_read(path, lift):                                         # the author's autosave lands while the relief is read
        store.put(st.id, {"revision": st.revision, "name": "Edited"})
        return None, None
    monkeypatch.setattr(relief, "frame_of_glb", slow_read)
    out = store.add_image_set(st.id, "ast_relief01", "ast_plate001", 70.0, -1.0, tmp_path / "relief.glb")
    assert out.name == "Edited" and out.revision == st.revision + 2 and out.objects[-1].preset == "image"   # both kept, no 409 lost


def test_k91_a_bench_is_made_once(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StageStore(ws)
    prof = Profile(name="Mara", cls="character", current="v1", versions=[ProfileVersion(id="v1", group_id="grp_x")])
    got = _at_once([lambda: store.bench(prof, "v1") for _ in range(6)])
    assert sum(made for _, made in got) == 1 and len({s.id for s, _ in got}) == 1
    assert len([s for s in store.list() if s.purpose == "bench"]) == 1


# ---- K51 / K91: a picture set's things -----------------------------------------------------------------------------------------------
async def test_k51_a_second_model_makes_no_second_prop_and_a_make_is_seen_live(tmp_path: Path, object_info: dict, monkeypatch):
    from test_set_things_d123 import _project
    rig, store, st_id, set_id, pic, relief, box = _project(tmp_path, object_info, monkeypatch)
    try:
        rev = store.get(st_id).revision
        od = set_things.ensure_document(store, rig.docs, rig.catalogue, st_id, set_id)
        assert store.get(st_id).revision == rev                                                       # K91: the pointer at the same revision
        stale = store.get(st_id).model_dump()
        stale["objects"] = [{**o, "things_document_id": None} for o in stale["objects"]]              # a client that never saw it …
        stale["name"] = "Room (edited)"
        kept = store.put(st_id, stale)
        assert kept.name == "Room (edited)" and next(o for o in kept.objects if o.id == set_id).things_document_id == od.doc.id   # … keeps it
        od.selection = np.where(box, 255, 0).astype(np.uint8)
        _, thing, _ = set_things.keep_thing(store, rig.docs, rig.catalogue, st_id, set_id, "Crate", [{"x": 128, "y": 100, "label": 1}])
        q = SimpleNamespace(ws=rig.ws, catalogue=rig.catalogue, hub=SimpleNamespace(broadcast=lambda *a, **k: None))
        job = lambda: SimpleNamespace(origin=JobOrigin(suite="stage", surface=set_things.MODEL_SURFACE, ref=st_id,  # noqa: E731
                                                       payload={"set_id": set_id, "thing_id": thing.id}), result={}, log_tail=[])
        first, second = job(), job()
        set_things.model_landed(q, first, relief.id)                                                  # the relief stands in for a model
        set_things.model_landed(q, second, relief.id)
        meshes = [o for o in store.get(st_id).objects if o.kind == "mesh"]
        assert len(meshes) == 1 and first.result["object_id"] == meshes[0].id
        assert "object_id" not in second.result and any("already has its model" in x for x in second.log_tail)
        live = SimpleNamespace(jobs={"job_m": SimpleNamespace(id="job_m", origin=job().origin)}, job_live=lambda jid: jid == "job_m")
        assert set_things.make_live(live, st_id, set_id) == "job_m" and set_things.make_live(live, st_id, "set_other") is None
        over = SimpleNamespace(jobs=live.jobs, job_live=lambda jid: False)
        assert set_things.make_live(over, st_id, set_id) is None
    finally:
        await rig.close()


# ---- K52: the reach as one labelling, the grow as two running sums -------------------------------------------------------------
def _steps_grow(m: np.ndarray, px: int) -> np.ndarray:
    img = Image.fromarray(np.where(m, 255, 0).astype(np.uint8))
    for _ in range(max(0, px)):
        img = img.filter(ImageFilter.MaxFilter(3))
    return np.asarray(img) > 127


def _steps_reach(seed: np.ndarray, within: np.ndarray) -> np.ndarray:
    grown = seed & within
    while True:
        nxt = _steps_grow(grown, 1) & within
        if (nxt == grown).all():
            return grown
        grown = nxt


def test_k52_the_reach_and_the_grow_are_the_steps_own():
    rng = np.random.default_rng(5)
    for _ in range(150):
        h, w = int(rng.integers(1, 30)), int(rng.integers(1, 30))
        within = rng.random((h, w)) < rng.uniform(0.2, 0.8)
        seed = rng.random((h, w)) < rng.uniform(0.0, 0.1)
        assert (set_things._reach(seed, within) == _steps_reach(seed, within)).all()
        for px in (0, 1, 3):
            assert (set_things._grow(within, px) == _steps_grow(within, px)).all()
    within = np.zeros((9, 9), bool)                                                     # diagonal steps join (8-connected), a gap does not
    within[[0, 1, 2, 3], [0, 1, 2, 3]] = True
    within[6:, 6:] = True
    seed = np.zeros_like(within)
    seed[0, 0] = True
    assert set_things._reach(seed, within).sum() == 4


def test_k52_a_large_reach_is_quick():
    H, W = 1088, 1920
    yy, xx = np.mgrid[0:H, 0:W]
    within = ((xx - 960) ** 2 / 600 ** 2 + (yy - 544) ** 2 / 520 ** 2) < 1             # a thing 1200 px wide …
    within &= ~((yy % 40 == 0) & (xx % 7 != 0))                                        # … crossed through gaps
    seed = np.zeros_like(within)
    seed[544, 361] = True                                                              # from one end
    t = time.perf_counter()
    got = set_things._reach(seed, within)
    assert time.perf_counter() - t < 2.0 and (got == within).all()                     # the steps took about a minute here


# ---- K91: bodies, sets, the animation thumbnail ----------------------------------------------------------------------------------
def test_k91_a_body_with_every_factor_locked_fits_nothing():
    from loom2.body import Body, dummy_ratios, fit_body
    b = Body()
    keys = ("head", "neck", "torso", "shoulders", "hips", "legs", "arms", "elbow", "knee", "hands", "feet")
    out, report = fit_body(dummy_ratios(b), b, locks=keys)
    assert all(getattr(out, k) == pytest.approx(getattr(b, k)) for k in keys) and report


def test_k91_a_refit_keeps_the_sets_model():
    from loom2.place_sets import place_set_from_fit
    from loom2.stages import PlaceSet
    f = {"camera": {"pos": [0.0, 1.6, 0.0], "target": [0.0, 1.6, -1.0], "focal_mm": 35.0, "sensor_mm": 36.0}, "kind": "room",
         "sizes": {"width": 5.0, "depth": 6.0, "height": 2.8}, "assumed": []}
    keep = PlaceSet(kind="room", sizes={"width": 5.0, "depth": 6.0, "height": 2.8}, model_id="made_up_painter")
    assert place_set_from_fit(f, "ast_pic00001", None, keep).model_id == "made_up_painter"


def test_k91_an_animation_thumbnail_names_a_blob_by_its_sha(tmp_path: Path):
    app, cl, svc, ws, cat, groups = _open(tmp_path)
    try:
        r = cl.post(app.url_path_for("animations_thumbnail", aid="anm_x"), json={"blob": "../../project.json"})
        assert r.status_code == 422
    finally:
        cl.__exit__(None, None, None)
