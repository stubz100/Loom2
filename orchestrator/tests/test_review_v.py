"""The review register V (journal 2026-10-27 08:21): one regression test per fixed finding, named after its id.

V21 — a job that ends outside `_fail` / cancel (interrupted by a shutdown, refused over the VRAM budget) runs the origin hook, and a
record's busy marker naming a job the queue no longer holds live is stale, not busy. V22 / V30 — the chains' jobs are submitted on the
loop, staged until their marker is on disk. V24 — a new version takes the set but not a Fill running on the source. V25 — a landing that
fails lets go of its face."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.groups import GroupStore  # noqa: E402
from loom2.origin import JobOrigin  # noqa: E402
from loom2.place_sets import SET_FILL_SURFACE, fill_landed, fill_order, queue_fill  # noqa: E402
from loom2.queue import QUEUE_SCHEMA_VERSION, JobRecord  # noqa: E402
from loom2.stages import PlaceSet, SetFace  # noqa: E402
from loom2.story import StoryStore  # noqa: E402


def _rig(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    return test_lifecycle.Rig(tmp_path, object_info)


def _faces(ws, catalogue, tmp_path: Path, pid: str, spec=(("floor", 40), ("wall_left", 10))) -> StoryStore:
    """The place's set: baked faces with something to fill (the CW6 fill test's), their images in the catalogue."""
    store = StoryStore(ws)
    faces = []
    for fid, bad_cols in spec:
        tex = np.full((32, 48, 4), 150, np.uint8)
        tex[:, :bad_cols, 3] = 0
        cov = np.zeros((32, 48, 3), np.uint8)
        cov[:, bad_cols:, 0] = 220
        for name, arr in (("t", tex), ("c", cov)):
            Image.fromarray(arr).save(tmp_path / f"{fid}_{name}.png")
        t = catalogue.ingest_file(tmp_path / f"{fid}_t.png", kind="image", move=False, suite="story")
        c = catalogue.ingest_file(tmp_path / f"{fid}_c.png", kind="image", move=False, suite="story")
        faces.append(SetFace(id=fid, texture_asset_id=t.id, baked_asset_id=t.id, coverage_asset_id=c.id, bad=bad_cols / 48))
    store.set_place_set(pid, "v1", PlaceSet(kind="room", sizes={}, faces=faces))
    return store


def _face(store: StoryStore, pid: str, fid: str) -> SetFace:
    return next(f for f in store.profile(pid).version("v1").place_set.faces if f.id == fid)


async def test_v21_a_shutdown_interrupted_fill_lets_go_of_its_face(tmp_path: Path, object_info: dict, monkeypatch):
    """A Fill running at a shutdown is failed on the next load, and the hook clears the face's marker — *Fill ▶* works again."""
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        p = StoryStore(rig.ws).create_profile("Kitchen", "place", GroupStore(rig.ws, rig.catalogue))
        store = _faces(rig.ws, rig.catalogue, tmp_path, p.id)
        job = JobRecord(kind="inpaint", recipe={"kind": "inpaint"}, status="running", resumable=False,
                        origin=JobOrigin(suite="story", surface=SET_FILL_SURFACE, ref=p.id, payload={"version": "v1", "face": "floor", "rest": []}))
        store.update_face(p.id, "v1", "floor", fill_job_id=job.id)
        rig.ws.queue_path.write_text(json.dumps({"schema_version": QUEUE_SCHEMA_VERSION, "paused": False, "clean_shutdown": True, "jobs": [job.model_dump()]}), encoding="utf-8")
        rig.queue.load()
        assert rig.queue.jobs[job.id].status == "failed" and rig.queue.jobs[job.id].error == "interrupted by shutdown"
        assert _face(store, p.id, "floor").fill_job_id is None
        assert not rig.queue.job_live(job.id) and not rig.queue.job_live("job_never")
    finally:
        await rig.close()


async def test_v21_a_fill_refused_at_submission_sets_no_marker(tmp_path: Path, object_info: dict, monkeypatch):
    """A job over the VRAM budget is failed at submission: the face is not marked and the caller gets the reason (the route's 422)."""
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        p = StoryStore(rig.ws).create_profile("Kitchen", "place", GroupStore(rig.ws, rig.catalogue))
        store = _faces(rig.ws, rig.catalogue, tmp_path, p.id)
        rig.app.update_settings({"vram_budget_gb": 0.5})
        await rig.queue.start()
        order = fill_order(store.profile(p.id).version("v1").place_set)
        with pytest.raises(ValueError, match="exceeds the budget"):
            await queue_fill(rig.queue, p.id, "v1", order)
        assert all(f.fill_job_id is None for f in store.profile(p.id).version("v1").place_set.faces)
        assert any(j.status == "failed" and "budget" in (j.error or "") for j in rig.queue.jobs.values())
    finally:
        await rig.close()


def test_v21_the_fill_route_lets_go_of_a_stale_marker(tmp_path: Path):
    """A face naming a job the queue does not hold (a crash, a deleted job) is not "running": the route clears it and queues the Fill —
    staged until the face names it, then released (V22); the live one then holds the next *Fill ▶*."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        pid = cl.post("/story/profiles", json={"name": "Kitchen", "cls": "place"}).json()["id"]
        store = _faces(ws, cat, tmp_path, pid)
        store.update_face(pid, "v1", "floor", fill_job_id="job_gone")
        store.update_face(pid, "v1", "wall_left", fill_job_id="job_gone_too")
        svc.queue.paused = True                                                  # the engine is missing here: the job waits, live
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={})
        assert r.status_code == 200, r.text
        faces = {f.id: f for f in store.profile(pid).version("v1").place_set.faces}
        assert faces["wall_left"].fill_job_id == r.json()["job_id"] and faces["floor"].fill_job_id is None
        assert svc.queue.jobs[r.json()["job_id"]].status == "queued"           # released once the face named it
        assert cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={}).status_code == 409


def test_v21_the_clay_route_lets_go_of_a_stale_marker(tmp_path: Path):
    """A variant whose clay names a job the queue does not hold is not "being made": *Make the clay ▶* starts again (V30: the marker
    names the job before it can run)."""
    from loom2.ideas import IdeaStore
    from test_ideas_cw1 import _picture
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        src = _picture(cat, tmp_path, "mara", "a woman in a red coat, full figure")
        store = IdeaStore(ws)
        idea = store.create("character", svc.require_groups(), src.id)
        vid = idea.variants[0].id
        store.set_clay(idea.id, vid, step="drawing", job_id="job_gone")
        svc.queue.paused = True
        r = cl.post(f"/story/ideas/{idea.id}/variants/{vid}/clay")
        assert r.status_code == 200, r.text
        clay = store.get(idea.id).variant(vid).clay
        assert clay.step == "drawing" and clay.job_id == r.json()["job_id"]
        assert svc.queue.jobs[clay.job_id].status == "queued"
        assert cl.post(f"/story/ideas/{idea.id}/variants/{vid}/clay").status_code == 409


def test_v24_a_new_version_takes_the_set_but_not_its_running_fill(tmp_path: Path):
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat = Catalogue(ws)
    try:
        groups = GroupStore(ws, cat)
        store = StoryStore(ws)
        p = store.create_profile("Kitchen", "place", groups)
        store.set_place_set(p.id, "v1", PlaceSet(kind="room", sizes={}, faces=[SetFace(id="floor", fill_job_id="job_running"), SetFace(id="wall_back")]))
        p = store.new_version(p.id, groups)
        assert p.current == "v2"
        assert p.version("v1").place_set.faces[0].fill_job_id == "job_running"
        assert p.version("v2").place_set.kind == "room" and all(f.fill_job_id is None for f in p.version("v2").place_set.faces)
    finally:
        cat.close()


async def test_v25_a_landing_that_fails_lets_go_of_its_face(tmp_path: Path, object_info: dict, monkeypatch):
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        p = StoryStore(rig.ws).create_profile("Kitchen", "place", GroupStore(rig.ws, rig.catalogue))
        store = _faces(rig.ws, rig.catalogue, tmp_path, p.id)
        store.update_face(p.id, "v1", "floor", fill_job_id="job_land")
        job = SimpleNamespace(id="job_land", result={}, log_tail=[],
                              origin=JobOrigin(suite="story", surface=SET_FILL_SURFACE, ref=p.id, payload={"version": "v1", "face": "floor", "rest": ["wall_left"]}))

        def closed():
            raise RuntimeError("the document is closed")
        od = SimpleNamespace(flatten=closed, doc=SimpleNamespace(id="doc_x", source_asset_id=None))
        assert fill_landed(rig.queue, job, od) == []
        assert any("the document is closed" in s for s in job.log_tail)
        assert _face(store, p.id, "floor").fill_job_id is None
    finally:
        await rig.close()


# ---- the catalogue (V1) -----------------------------------------------------------------------------------------------------------------

def test_v1_a_trash_during_the_thumbnails_stays(tmp_path: Path):
    """The thumbnail pass writes the record as it is now, not the caller's copy from before: a trash (or a tag) made while the thumbnails
    were being made is not reverted, and the thumbnail fields are the pass's own."""
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat = Catalogue(ws)
    try:
        Image.fromarray(np.full((40, 60, 3), 90, np.uint8)).save(tmp_path / "a.png")
        rec = cat.ingest_file(tmp_path / "a.png", kind="image", move=False, suite="generate")
        assert rec.thumb_status == "pending" and rec.trashed_at is None
        cat.trash([rec.id])                                                             # meanwhile: the user trashes the fresh tile …
        cat.patch(rec.id, {"tags": ["keep"]})                                          # … and tags it
        stale = rec.model_copy(update={"params": {**rec.params, "thumb_source": "client"}})   # the caller's record, from before both
        out = cat.make_thumbs(stale)
        assert out.thumb_status == "done" and out.trashed_at is not None and out.tags == ["keep"] and out.params.get("thumb_source") == "client"
        again = cat.get(rec.id)
        assert again is not None and again.trashed_at == out.trashed_at and again.tags == ["keep"] and again.thumb_status == "done"
        assert all(ws.thumb_path(rec.id, s).is_file() for s in cat.thumb_sizes)
    finally:
        cat.close()


# ---- the engine's launch (V44, V45, V19) ------------------------------------------------------------------------------------------------

def test_v45_the_engine_reads_the_model_trees_settings_name(tmp_path: Path):
    """The mounts file the engine gets is written from Settings at every launch: `models_root` the default tree, every mounted tree after
    it, each with the template's folder map (the multi-line `checkpoints` entry included) — what the roster reads, the engine reads."""
    import yaml
    from loom2.config import AppState
    from loom2.engine.supervisor import EngineSupervisor
    app = AppState(tmp_path / "state")
    app.update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [str(tmp_path / "more")]})
    argv = EngineSupervisor(app)._argv()
    path = Path(argv[argv.index("--extra-model-paths-config") + 1])
    assert path == tmp_path / "state" / "extra_model_paths.yaml"
    trees = yaml.safe_load(path.read_text(encoding="utf-8"))
    template = yaml.safe_load((Path(app.settings.engine.extra_model_paths)).read_text(encoding="utf-8"))
    name, folders = next(iter(template.items()))
    assert list(trees) == [name, "mounted_1"]
    assert trees[name]["base_path"] == (tmp_path / "models").as_posix() and trees[name]["is_default"] is True
    assert trees["mounted_1"]["base_path"] == (tmp_path / "more").as_posix() and "is_default" not in trees["mounted_1"]
    for k, v in folders.items():
        if k not in ("base_path", "is_default"):
            assert trees[name][k] == v and trees["mounted_1"][k] == v
    assert set(trees[name]["checkpoints"].split()) == {"checkpoints", "sam3"}


def test_v44_the_launch_entry_point_is_the_supervisors(tmp_path: Path):
    """`python -m loom2.engine.supervisor --argv --state DIR` (what scripts/engine-start.ps1 runs) prints the launch `start()` would make:
    the same argv, the engine's cwd, its env, and the output folders made under the state."""
    import json
    import subprocess
    from loom2.config import AppState
    from loom2.engine.supervisor import ENGINE_ENV, EngineSupervisor
    state = tmp_path / "state"
    out = subprocess.run([sys.executable, "-m", "loom2.engine.supervisor", "--argv", "--state", str(state)], capture_output=True, text=True, check=True,
                         cwd=str(Path(__file__).resolve().parents[1]))
    launch = json.loads(out.stdout.strip().splitlines()[-1])
    sup = EngineSupervisor(AppState(state))
    assert launch["argv"] == sup._argv() and launch["cwd"] == str(Path(sup.app.settings.engine.main).parent)
    assert launch["env"] == ENGINE_ENV and launch["port"] == sup.app.settings.engine.port and launch["state"] == str(state)
    assert "--output-directory" in launch["argv"] and launch["argv"][launch["argv"].index("--output-directory") + 1] == str(state / "engine_out")
    assert all((state / d).is_dir() for d in ("engine_out", "engine_tmp", "engine_user"))


async def test_v19_an_adopted_engine_is_not_restarted(tmp_path: Path, object_info: dict, monkeypatch):
    """An engine loom2 adopted (already on its port) is not its to stop: restart says so instead of re-adopting the same process and
    counting a restart."""
    import pytest
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        await rig.engine.ensure_running()
        assert rig.engine.proc is None and rig.engine.state()["running"] is False              # adopted, not supervised
        with pytest.raises(RuntimeError, match="adopted"):
            await rig.engine.restart()
        assert rig.engine.restarts == 0 and "adopted" in (rig.engine.last_error or "")
    finally:
        await rig.close()
