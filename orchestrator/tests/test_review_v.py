"""The review register V (journal 2026-10-27 08:21): one regression test per fixed finding, named after its id.

V21 — a job that ends outside `_fail` / cancel (interrupted by a shutdown, refused over the VRAM budget) runs the origin hook, and a
record's busy marker naming a job the queue no longer holds live is stale, not busy. V22 / V30 — the chains' jobs are submitted on the
loop, staged until their marker is on disk. V24 — a new version takes the set but not a Fill running on the source. V25 — a landing that
fails lets go of its face. V23 — a bake lands on the set as it is now. V34 — the finals' writers take turns, a job is appended to the
layer as it is. V35 — RIFE under a watchdog. V36 — a download named with any character. V65 — the hub replays what a reconnecting
client missed."""
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
from loom2.stages import PlaceSet, SetFace, SetSource, SourceCamera  # noqa: E402
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


# ---- the fifth group (journal 2026-10-27): V23, V34, V35, V36, V65 ---------------------------------------------------------------------


def test_v23_a_bake_lands_on_the_set_as_it_is_now(tmp_path: Path):
    """The bake was started from the set as it was; while its faces were being ingested the author dragged a wall and named a material,
    and a Fill took a face. The bake's faces land on the set as it is now: the sizes, the material and the Fill's marker stay, the baked
    assets are the new ones, the key is the bake's; a face the set did not have yet is the bake's (a fit leaves none); no set is a 422."""
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    from loom2.catalogue import Catalogue
    cat = Catalogue(ws)
    store = StoryStore(ws)
    p = store.create_profile("Kitchen", "place", GroupStore(ws, cat))
    store = _faces(ws, cat, tmp_path, p.id, spec=(("floor", 40), ("wall_back", 10)))
    stale = store.profile(p.id).version("v1").place_set                     # what the client baked from
    store.set_place_set(p.id, "v1", stale.model_copy(update={"sizes": {"height": 3.1}}))                   # meanwhile: a drag …
    store.update_face(p.id, "v1", "floor", material="worn terracotta tiles")                               # … a material …
    store.update_face(p.id, "v1", "wall_back", fill_job_id="job_live")                                     # … and a Fill
    baked = [f.model_copy(update={"texture_asset_id": f"ast_new_{f.id}", "baked_asset_id": f"ast_new_{f.id}", "seen": 0.9, "bad": 0.1}) for f in stale.faces]
    baked.append(SetFace(id="ceiling", texture_asset_id="ast_x", baked_asset_id="ast_x"))                 # a face the set did not have yet
    out = store.set_baked_faces(p.id, "v1", baked, "k2").version("v1").place_set
    assert out.sizes["height"] == 3.1 and out.baked_key == "k2" and [f.id for f in out.faces] == ["floor", "wall_back", "ceiling"]
    floor, wall, ceiling = out.faces
    assert ceiling.baked_asset_id == "ast_x" and ceiling.material == "" and ceiling.fill_job_id is None
    assert floor.baked_asset_id == "ast_new_floor" and floor.material == "worn terracotta tiles" and floor.seen == 0.9
    assert wall.baked_asset_id == "ast_new_wall_back" and wall.fill_job_id == "job_live"
    store.set_place_set(p.id, "v1", None)
    with pytest.raises(ValueError, match="the set is gone"):
        store.set_baked_faces(p.id, "v1", baked, "k3")


def test_v23_the_bake_route_waits_for_a_running_fill(tmp_path: Path):
    """A bake while a face's Fill runs would take the Fill's result onto the new bake: 409 until it is over; a stale marker does not hold it."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        pid = cl.post("/story/profiles", json={"name": "Kitchen", "cls": "place"}).json()["id"]
        store = _faces(ws, cat, tmp_path, pid)
        ps = store.profile(pid).version("v1").place_set
        store.set_place_set(pid, "v1", ps.model_copy(update={"sources": [SetSource(asset_id=_face(store, pid, "floor").baked_asset_id, camera=SourceCamera(pos=[0, 1.6, 2], target=[0, 1.6, 0]))]}))
        svc.queue.paused = True
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={})
        assert r.status_code == 200, r.text
        body = {"key": "k", "faces": [{"id": "floor", "image": "0" * 64, "coverage": "0" * 64, "texel_m": 0.01, "seen": 1.0, "bad": 0.0}]}
        r = cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json=body)
        assert r.status_code == 409 and "Fill is running" in r.json()["detail"]
        svc.queue.jobs[next(f.fill_job_id for f in store.profile(pid).version("v1").place_set.faces if f.fill_job_id)].status = "failed"
        assert cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json=body).status_code != 409   # the marker names a job that is over: not held (the blobs are missing → 404)


def test_v34_a_job_is_appended_to_the_layer_as_it_is_now(tmp_path: Path):
    """`add_job` reads the layer again: a job landing between a route's read and its write is kept; and two writers of one record never
    interleave (each `set_key` from two threads lands)."""
    import threading
    import time

    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    from test_finals_d111 import _final_on_disk
    ws = Workspace.create(tmp_path / "p", name="P")
    f = _final_on_disk(ws, "stg_x", "cam_x")
    store = FinalStore(ws)
    store.update_layer(f.id, "plate", job_ids=["job_a"])
    plate = next(x for x in store.get(f.id).layers if x.id == "plate")   # the route's copy …
    store.update_layer(f.id, "plate", job_ids=[*plate.job_ids, "job_b"])  # … a finisher writes meanwhile …
    out = store.add_job(f.id, "plate", "job_c", status="running")        # … the route appends to what is there now
    assert next(x for x in out.layers if x.id == "plate").job_ids == ["job_a", "job_b", "job_c"] and next(x for x in out.layers if x.id == "plate").status == "running"
    with pytest.raises(KeyError):
        store.add_job(f.id, "nowhere", "job_d")
    slow_save = store.save

    def save(rec):
        time.sleep(0.002)                                                # a write that takes time, so unlocked writers would interleave
        slow_save(rec)
    store.save = save

    def keys(parity: int) -> None:
        for frame in range(parity, 60, 2):
            store.set_key(f.id, {"frame": frame, "asset_id": None, "job_id": None, "filled": 0.0, "heal": False})
    threads = [threading.Thread(target=keys, args=(0,)), threading.Thread(target=keys, args=(1,))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    landed = [k["frame"] for k in next(x for x in store.get(f.id).layers if x.id == "plate").keys]
    assert landed == list(range(60))


def test_v35_rife_is_killed_when_it_stalls_or_the_job_is_cancelled(tmp_path: Path, monkeypatch):
    """RIFE under the watchdog: no new frame for RIFE_STALL_S → killed with its tree, TimeoutError (the job fails, the queue goes on);
    a cancel → killed, None; a run that writes every frame and exits 0 → the frames."""
    import subprocess

    from loom2 import final_assembly
    from loom2.engine import supervisor
    killed: list[int] = []
    monkeypatch.setattr(supervisor, "_kill_tree", lambda pid: (killed.append(pid), setattr(Proc.current, "returncode", -9)))
    monkeypatch.setattr(supervisor, "_assign_to_job", lambda proc: True)
    monkeypatch.setattr(final_assembly, "rife_binary", lambda: tmp_path / "rife" / "rife-ncnn-vulkan.exe")
    monkeypatch.setattr(final_assembly, "RIFE_STALL_S", 0.3)
    src = tmp_path / "f16"
    src.mkdir()

    class Proc:
        """A RIFE that hangs (writes one frame, then nothing), unless `frames` says how many it writes before exiting 0."""
        current = None

        def __init__(self, argv, **kw):
            Proc.current = self
            self.pid, self.returncode = 4242, None
            self.dst = Path(argv[argv.index("-o") + 1])
            (self.dst / "000000.png").write_bytes(b"x")
            if Proc.frames:
                for i in range(1, Proc.frames):
                    (self.dst / f"{i:06d}.png").write_bytes(b"x")
                self.returncode = 0

        frames = 0

        def poll(self):
            return self.returncode

        def wait(self):
            return self.returncode
    monkeypatch.setattr(subprocess, "Popen", Proc)
    with pytest.raises(TimeoutError, match="nothing new for 0 s"):
        final_assembly.conform_24(src, tmp_path / "f24", 17)
    assert killed == [4242]
    assert final_assembly.conform_24(src, tmp_path / "f24b", 17, cancelled=lambda: True) is None and killed == [4242, 4242]
    Proc.frames = round(16 * 24 / 16) + 1
    out = final_assembly.conform_24(src, tmp_path / "f24c", 17)
    assert out is not None and len(out) == 25 and killed == [4242, 4242]


def test_v36_export_names_with_any_character(tmp_path: Path):
    """Export PNG of a document named with an em dash and an ellipsis: 200, the name carried in `filename*` (the ASCII fallback beside it)."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "D", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "src.png"
        Image.fromarray(np.full((8, 8, 4), 200, np.uint8), "RGBA").save(src)
        asset = client.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        d = client.post("/documents", json={"from_asset": asset["id"]}, headers=H).json()
        d = client.put(f"/documents/{d['id']}", json={**d, "name": "Scene — take…"}, headers=H).json()
        assert d["name"] == "Scene — take…"
        r = client.post(f"/documents/{d['id']}/export", json={"format": "png"}, headers=H)
        assert r.status_code == 200, r.text
        assert r.headers["content-disposition"] == "attachment; filename=\"Scene _ take_.png\"; filename*=UTF-8''Scene%20%E2%80%94%20take%E2%80%A6.png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_v65_the_hub_replays_since_the_clients_last_seq():
    """`replay(since, run)`: nothing on a first connect; the frames after `since` when the history holds them; a gap when it does not,
    when the run is another (an orchestrator restart) or the seq is beyond ours."""
    from loom2.events import EventHub
    hub = EventHub(history=3)
    for i in range(1, 6):
        hub.broadcast("asset.updated", {"i": i})
    assert hub.replay(0, hub.run) == ([], False)
    missed, gap = hub.replay(3, hub.run)
    assert [f["seq"] for f in missed] == [4, 5] and not gap
    assert hub.replay(5, hub.run) == ([], False)
    assert hub.replay(2, hub.run) == ([f for f in hub.recent], False)      # 3, 4, 5: all there
    assert hub.replay(1, hub.run)[1] is True                               # frame 2 fell out of a history of 3
    assert hub.replay(3, "another") == ([], True)
    assert hub.replay(9, hub.run) == ([], True)


def test_v65_the_socket_hands_a_reconnecting_client_what_it_missed(tmp_path: Path):
    """The auth names `since` and `run`; the hello carries the missed frames in order, or `gap` for another run."""
    from fastapi.testclient import TestClient
    from test_auth_d67 import _app
    app = _app(tmp_path)
    with TestClient(app) as c:
        svc = app.state.services
        token = svc.app.token
        with c.websocket_connect("/events") as ws:
            ws.send_json({"type": "auth", "token": token})
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["data"]["run"] == svc.hub.run and hello["data"]["recent"] == [] and hello["data"]["gap"] is False
        for i in range(1, 4):                                              # while no client listens
            svc.hub.broadcast("asset.updated", {"i": i})
        with c.websocket_connect("/events") as ws:
            ws.send_json({"type": "auth", "token": token, "since": 1, "run": svc.hub.run})
            hello = ws.receive_json()
            assert [f["seq"] for f in hello["data"]["recent"]] == [2, 3] and hello["data"]["gap"] is False and hello["seq"] == 3
            assert [f["data"]["i"] for f in hello["data"]["recent"]] == [2, 3]
        with c.websocket_connect("/events") as ws:
            ws.send_json({"type": "auth", "token": token, "since": 1, "run": "a previous run"})
            hello = ws.receive_json()
            assert hello["data"]["recent"] == [] and hello["data"]["gap"] is True
        with c.websocket_connect("/events") as ws:                         # a bad `since` is a first connect, not an error
            ws.send_json({"type": "auth", "token": token, "since": "three", "run": True})
            assert ws.receive_json()["data"]["gap"] is False
