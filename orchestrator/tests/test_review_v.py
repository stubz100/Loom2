"""The review register V (journal 2026-10-27 08:21): one regression test per fixed finding, named after its id.

V21 — a job that ends outside `_fail` / cancel (interrupted by a shutdown, refused over the VRAM budget) runs the origin hook, and a
record's busy marker naming a job the queue no longer holds live is stale, not busy. V22 / V30 — the chains' jobs are submitted on the
loop, staged until their marker is on disk. V24 — a new version takes the set but not a Fill running on the source. V25 — a landing that
fails lets go of its face. V23 — a bake lands on the set as it is now. V34 — the finals' writers take turns, a job is appended to the
layer as it is. V35 — RIFE under a watchdog. V36 — a download named with any character. V65 — the hub replays what a reconnecting
client missed. V26–V29, V31, V32, V37–V43 — the server lows (an idea's page used, a place use, the poses' revision, a refit off the
loop, no orphan on a refused import, why nothing is filled, temp folders gone with a job, a surround WAV, the mix by loudness, an
export timeout, a bad stack, the plate's id, a final deleted with its jobs). V2–V12, V14–V18, V20 — the queue, engine and catalogue lows
(trained LoRAs after a rescan, a batch checked as a submit, a held file at purge, a torn app.json or group file, CORS on a 401, a typed
layout, the thumbnail temp file, counts without the trashed, a requeue on disk, a retried thumbnail replace, a preview without a graph,
a wedged engine restarted, tiers per model, the headroom of the models that run, the history read again, the disk guard cached).
V53, V54, V56 — READY after the bind, a gone parent ends the process, a gain that is not a number refused."""
from __future__ import annotations

import contextlib
import json
import os
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


# ---- the sixth group (journal 2026-10-27): the server lows V26–V29, V31, V32, V37–V43 ----------------------------------------------


def test_v26_an_ideas_page_is_a_used_group(tmp_path: Path):
    """An idea's album page holds its variants (`add_variant` copies there): `used-by` names it, so a delete from the Catalogue says so."""
    from loom2.catalogue import Catalogue
    from loom2.ideas import IdeaStore
    from loom2.usedby import all_users
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    cat = Catalogue(ws)
    groups = GroupStore(ws, cat)
    Image.fromarray(np.full((16, 16, 3), 90, np.uint8)).save(tmp_path / "m.png")
    pic = cat.ingest_file(tmp_path / "m.png", kind="image", move=False, suite="story")
    idea = IdeaStore(ws).create("character", groups, pic.id, "Mara")
    users = all_users(ws)[idea.group_id]
    assert [(u.kind, u.id, u.name, u.cls) for u in users] == [("idea", idea.id, "Mara", "character")]


def test_v27_a_built_set_bound_to_a_place_is_a_place_use(tmp_path: Path):
    """Cast's readiness: a stage's `set` object bound to a place reads `how: place`; a mannequin `figure`, a mesh `prop`; hidden objects not."""
    from loom2.story import cast_uses
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    shot = StoryStore(ws).create_shot("Kitchen, dawn", stage_id="stg_1", camera_id="cam_1")
    objs = [SimpleNamespace(profile_id="prof_place", visible=True, kind="set"), SimpleNamespace(profile_id="prof_mara", visible=True, kind="mannequin"),
            SimpleNamespace(profile_id="prof_jug", visible=True, kind="mesh"), SimpleNamespace(profile_id="prof_hidden", visible=False, kind="set")]
    uses = cast_uses([shot], {}, {"stg_1": SimpleNamespace(objects=objs)})
    assert uses["prof_place"][0].how == ["place"] and uses["prof_mara"][0].how == ["figure"] and uses["prof_jug"][0].how == ["prop"]
    assert "prof_hidden" not in uses


def test_v28_the_pose_library_has_a_schema_version_and_a_revision(tmp_path: Path):
    """`stages/poses.json`: schema_version 1 and revision 0 at first; a save names the revision it read (409 when another save came
    first), the reply carries the next."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        assert cl.get("/stages/poses").json() == {"schema_version": 1, "revision": 0, "poses": {}}
        pose = {"preset": "stand", "joints": {"r_shoulder": [-150, 0, -20]}}
        r = cl.put("/stages/poses", json={"revision": 0, "poses": {"salute": pose}})
        assert r.status_code == 200 and r.json()["revision"] == 1 and r.json()["poses"] == {"salute": pose}
        r = cl.put("/stages/poses", json={"revision": 0, "poses": {}})                   # another window's save, on the old revision
        assert r.status_code == 409 and "revision 1" in r.json()["detail"]
        assert cl.get("/stages/poses").json()["poses"] == {"salute": pose}
        assert cl.put("/stages/poses", json={"revision": 1, "poses": {}}).json() == {"schema_version": 1, "revision": 2, "poses": {}}
        ws, _, _ = app.state.services.require_project()
        assert json.loads((ws.stages_dir / "poses.json").read_text(encoding="utf-8"))["schema_version"] == 1


def test_v29_a_degenerate_refit_is_a_422(tmp_path: Path, monkeypatch):
    """*Fit again* with points the fit cannot use answers 422 with the reason (it was a 500 raised on the loop)."""
    from loom2 import body as body_mod
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        pid = cl.post("/story/profiles", json={"name": "Ines", "cls": "character", "appearance": "Ines"}).json()["id"]
        monkeypatch.setattr(body_mod, "reference_ratios", lambda person: {"head": 0.0})
        monkeypatch.setattr(body_mod, "stance_note", lambda person: "arms_open")

        def degenerate(measured, body=None, locks=()):
            raise ZeroDivisionError("float division by zero")
        monkeypatch.setattr(body_mod, "fit_body", degenerate)
        r = cl.post(f"/story/profiles/{pid}/versions/v1/body/refit", json={"points": {"pose": [[1, 2, 1]] * 18}})
        assert r.status_code == 422 and "cannot be fitted: float division by zero" in r.json()["detail"]


def test_v31_a_model_import_refused_leaves_no_orphan(tmp_path: Path):
    """A GLB for a character (422) or for a version that is not there (404) is refused before anything is ingested: no orphan mesh."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        total = lambda: cl.get("/assets", params={"folder": "all"}).json()["total"]   # noqa: E731
        n = total()
        ines = cl.post("/story/profiles", json={"name": "Ines", "cls": "character", "appearance": "Ines"}).json()["id"]
        box = cl.post("/story/profiles", json={"name": "Box", "cls": "prop"}).json()["id"]
        r = cl.post(f"/story/profiles/{ines}/versions/v1/model/import", json={"path": str(tmp_path / "nothing.glb")})
        assert r.status_code == 422 and "only a prop" in r.json()["detail"]
        assert cl.post(f"/story/profiles/{box}/versions/v9/model/import", json={"path": str(tmp_path / "nothing.glb")}).status_code == 404
        assert total() == n


def test_v32_a_small_mask_is_not_a_missing_bake(tmp_path: Path):
    """*Fill ▶* on faces whose coverage leaves under the minimum says so (422 'saw these faces well enough'); only bakes that are gone
    say 'bake the set again'."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        pid = cl.post("/story/profiles", json={"name": "Kitchen", "cls": "place"}).json()["id"]
        store = _faces(ws, cat, tmp_path, pid, spec=(("floor", 0),))                    # the coverage sees everything …
        store.update_face(pid, "v1", "floor", bad=0.5)                                   # … while the face's share says half (a stale bake share)
        svc.queue.paused = True
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={})
        assert r.status_code == 422 and "saw these faces well enough" in r.json()["detail"], r.text
        store.update_face(pid, "v1", "floor", baked_asset_id="ast_gone")
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={})
        assert r.status_code == 422 and "bake the set again" in r.json()["detail"], r.text


async def test_v37_a_jobs_temp_folders_go_with_it(tmp_path: Path, object_info: dict, monkeypatch):
    """The finishers' work folders (`assemble-<job>`, `movie-<job>`, `lipsync/<job>`, `tts/<job>`, `ai/<job>`) go when the job fails or is
    cancelled, and at load for jobs that are not queued or running; a live job's stay."""
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        q, t = rig.queue, rig.ws.temp_dir
        gone = [t / "assemble-job_a", t / "movie-job_a", t / "comp-render-job_a", t / "lipsync" / "job_a", t / "tts" / "job_a", t / "ai" / "job_a"]
        kept = [t / "render-job_live", t / "tts" / "job_live", t / "set_fills"]
        for d in gone + kept:
            d.mkdir(parents=True, exist_ok=True)
            (d / "x.bin").write_bytes(b"x")
        q._origin_stopped(JobRecord(id="job_a", kind="i2v", recipe={"kind": "i2v"}, status="failed", error="x"), "x")
        assert not any(d.exists() for d in gone) and all(d.exists() for d in kept)
        q.jobs["job_live"] = JobRecord(id="job_live", kind="i2v", recipe={"kind": "i2v"}, status="queued")
        for d in gone:
            d.mkdir(parents=True, exist_ok=True)
        assert q._reconcile_leftovers() >= len(gone)
        assert not any(d.exists() for d in gone) and all(d.exists() for d in kept)
    finally:
        await rig.close()


def test_v38_a_surround_wav_is_a_sentence(tmp_path: Path):
    """A line's audio with more than two channels: a sentence naming the file and its channels, not numpy's broadcast error."""
    import soundfile as sf

    from loom2.final_assembly import mix_audio
    p = tmp_path / "six.wav"
    sf.write(str(p), np.zeros((4800, 6), np.float32), 48000)
    with pytest.raises(ValueError, match="six.wav has 6 channels"):
        mix_audio([{"path": str(p), "in": 0.0, "out": 0.1, "start": 0.0, "layer": "a", "text": ""}], 1.0, tmp_path / "mix.wav")


def test_v39_the_mix_is_cached_by_revision_and_loudness():
    """The cut's mix file is named by revision and loudness target: a changed target is a new mix, not the old WAV."""
    from loom2.cuts import mix_name
    assert mix_name(12, None) == "12-auto.wav" and mix_name(12, -16.0) == "12-m16.wav" and mix_name(12, -14.5) == "12-m14_5.wav"
    assert len({mix_name(12, None), mix_name(12, -16.0), mix_name(12, -23.0), mix_name(13, -16.0)}) == 4


def test_v40_a_filmcraft_export_timeout_is_a_cut_error(tmp_path: Path, monkeypatch):
    """FilmCraft's export process past its timeout: a CutError with the seconds (the route's 422), not a TimeoutExpired (a 500)."""
    import subprocess

    from loom2.cuts import CutError, Cuts

    def hangs(*a, **k):
        raise subprocess.TimeoutExpired(cmd="filmcraft", timeout=k.get("timeout"))
    monkeypatch.setattr(subprocess, "run", hangs)
    monkeypatch.setattr("loom2.filmcraft.export_argv", lambda *a: ["filmcraft"])
    fake = SimpleNamespace(fc=SimpleNamespace(settings=SimpleNamespace(timeout_s=7), app=None))
    with pytest.raises(CutError, match="did not export the cut within 7 s"):
        Cuts._export(fake, tmp_path / "p.fcproj", tmp_path / "s.jsonl", "export the cut")


def test_v41_a_bad_stack_is_a_422(tmp_path: Path):
    """`PUT /documents/{id}` with a layer the model refuses (a bogus blend) answers 422 with the reason, not a 500."""
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
        r = client.put(f"/documents/{d['id']}", json={**d, "layers": [{"kind": "hologram", "id": "x"}]}, headers=H)       # a kind the model does not know: pydantic, not _validate_modes
        assert r.status_code == 422 and "hologram" in r.json()["detail"]
        assert client.get(f"/documents/{d['id']}", headers=H).json()["layers"] == d["layers"]


def test_v42_the_plate_layer_carries_its_id(tmp_path: Path):
    """`check()`: the plate and shadows layers carry their kind's id — the routes and finishers find them by it."""
    from loom2.finals import check
    from loom2.workspace import Workspace
    from test_finals_d111 import _final_on_disk
    f = _final_on_disk(Workspace.create(tmp_path / "p", name="P"), "stg_x", "cam_x")
    check(f)
    bad = f.model_copy(deep=True)
    bad.layers[0].id = "background"
    with pytest.raises(ValueError, match="the plate layer's id is 'plate'"):
        check(bad)


def test_v43_deleting_a_final_cancels_its_jobs_and_releases_the_session(tmp_path: Path, monkeypatch):
    """DELETE /finals/{id}: the final's live jobs (its layers' and every job made for it) are cancelled, the EffectCraft session lets
    go of its composition, then the folder goes; another final's job is not touched."""
    from loom2.compositions import CompositionStore
    from loom2.finals import FinalStore
    from test_finals_d111 import _final_on_disk
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, _, _ = svc.require_project()
        f = _final_on_disk(ws, "stg_x", "cam_x")
        store = FinalStore(ws)
        jobs = [JobRecord(id="job_layer", kind="i2v", recipe={"kind": "i2v"}, status="queued"),
                JobRecord(id="job_made_for", kind="matte_sequence", recipe={"kind": "matte_sequence"}, status="queued",
                          origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "mara"})),
                JobRecord(id="job_other", kind="i2v", recipe={"kind": "i2v"}, status="queued")]
        for j in jobs:
            svc.queue.jobs[j.id] = j
        store.update_layer(f.id, "plate", job_ids=["job_layer", "job_done_long_ago"])
        svc.queue.paused = True
        ec = svc.effectcraft
        ecproj = str(CompositionStore(ws).ecproj(f.id))
        ec.project = ecproj
        stopped: list[str | None] = []
        monkeypatch.setattr(type(ec), "stop", lambda self: (stopped.append(self.project), setattr(self, "project", None)))
        assert cl.delete(f"/finals/{f.id}").status_code == 200
        assert svc.queue.jobs["job_layer"].status == "cancelled" and svc.queue.jobs["job_made_for"].status == "cancelled"
        assert svc.queue.jobs["job_other"].status == "queued"
        assert stopped == [ecproj] and ec.project is None
        assert not store.path(f.id).exists()
        assert cl.delete(f"/finals/{f.id}").status_code == 404


# ---- the seventh group (journal 2026-10-27): the queue, engine and catalogue lows V2–V12, V14–V18, V20 ------------------------------


@contextlib.contextmanager
def _project(tmp_path: Path):
    """An app with a project open (the CS2 client), its services — entered once (a second enter restarts the lifespan)."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        yield app, cl, app.state.services


def _png_bytes(w: int = 8, h: int = 8, v: int = 120) -> bytes:
    import io
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w, 3), v, np.uint8)).save(buf, "PNG")
    return buf.getvalue()


def test_v2_a_settings_change_keeps_the_trained_loras(tmp_path: Path, monkeypatch):
    """PUT /settings and POST /models/scan rescan the roster; the project's trained LoRAs are published onto it again (they were known
    from the queue's start only, so a settings change lost them until the project was reopened)."""
    from loom2 import loras
    calls: list[tuple] = []
    monkeypatch.setattr(loras, "publish", lambda roster, reg, root, pid: calls.append((id(roster), pid)) or {})
    with _project(tmp_path) as (app, cl, svc):
        n = len(calls)
        assert cl.put("/settings", json={"vram_budget_gb": 15.5}).status_code == 200
        assert len(calls) == n + 1 and calls[-1] == (id(svc.roster), (svc.ws.info() or {}).get("id") or svc.ws.path.name)
        assert cl.post("/models/scan").status_code == 200
        assert len(calls) == n + 2 and calls[-1][0] == id(svc.roster)


def test_v3_a_batch_refused_leaves_no_job(tmp_path: Path, monkeypatch):
    """`/jobs/batch` checks every item as a submit would — the disk guard and the mentions included — so a refused item leaves no job."""
    with _project(tmp_path) as (app, cl, svc):
        items = [{"recipe": {"kind": "t2i", "prompt_text": "a cat", "seeds": [3]}}, {"recipe": {"kind": "t2i", "prompt_text": "a dog", "seeds": [4]}}]
        monkeypatch.setattr(svc.catalogue, "usage_bytes", lambda: 11 * 2**30)             # over the project's 10 GB cap
        r = cl.post("/jobs/batch", json={"items": items})
        assert r.status_code == 422 and "disk guard" in r.json()["detail"]
        assert cl.get("/jobs").json()["items"] == []
        with pytest.raises(ValueError, match="disk guard"):
            svc.queue.check(items[0]["recipe"])


def test_v4_a_held_file_keeps_one_asset_trashed_and_the_rest_go(tmp_path: Path, monkeypatch):
    """Empty Trash with one file held open (Edge streaming its thumbnail, an antivirus): that asset stays trashed with its row and is
    counted as failed, the others go — no 500 half-way."""
    from loom2 import catalogue as cat_mod
    with _project(tmp_path) as (app, cl, svc):
        cat = svc.catalogue
        ids = []
        for k in range(3):
            (tmp_path / f"a{k}.png").write_bytes(_png_bytes(v=40 * k + 10))
            ids.append(cat.ingest_file(tmp_path / f"a{k}.png", kind="image", move=False, suite="story").id)
        assert cl.post("/assets/trash", json={"ids": ids}).status_code == 200
        held = Path(cat.get(ids[1]).path).name
        real = cat_mod.unlink

        def unlink(p, missing_ok=False):
            if Path(p).name == held:
                raise PermissionError(13, "held open", str(p))
            real(p, missing_ok)
        monkeypatch.setattr(cat_mod, "unlink", unlink)
        r = cl.post("/assets/purge", json={"ids": ids})
        assert r.status_code == 200, r.text
        assert r.json()["purged"] == 2 and r.json()["failed"] == 1 and set(r.json()["ids"]) == {ids[0], ids[2]}
        assert cat.get(ids[0]) is None and cat.get(ids[2]) is None
        kept = cat.get(ids[1])
        assert kept is not None and kept.trashed_at and cat.abs_path(kept).is_file()


def test_v5_a_torn_app_json_is_moved_aside(tmp_path: Path):
    """A corrupt or stale app.json never stops the launch: moved aside, the defaults, a recovery note."""
    from loom2.config import AppState
    state = tmp_path / "state"
    state.mkdir()
    (state / "app.json").write_text("{not json", encoding="utf-8")
    a = AppState(state)
    assert a.settings.vram_budget_gb > 0 and a.recovery and "moved aside" in a.recovery[0]
    assert not (state / "app.json").exists() and list(state.glob("app.json.corrupt-*"))
    (state / "app.json").write_text(json.dumps({"settings": {"vram_budget_gb": "lots"}}), encoding="utf-8")   # a value an older build never wrote
    b = AppState(state)
    assert b.recovery and not (state / "app.json").exists()
    assert AppState(state).recovery == []                                                   # nothing to recover: no note


def test_v6_a_torn_group_file_is_moved_aside_and_a_transient_failure_is_not_a_repair(tmp_path: Path, monkeypatch):
    """A group file that is not JSON is moved aside (its items go back to the album, as for a hand edit); a read that fails for a
    moment is read again; one that keeps failing stops the load — the album is not restructured over it."""
    from loom2 import groups as groups_mod
    from loom2.catalogue import Catalogue
    from loom2.fsio import StateError
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    cat = Catalogue(ws)
    store = GroupStore(ws, cat)
    g = store.create("Kitchen")
    inner = store.create("Pots", g.id)
    p = store._path(inner.id)
    good = p.read_text(encoding="utf-8")
    p.write_text("{torn", encoding="utf-8")
    again = GroupStore(ws, cat)
    assert inner.id not in again.groups and list(p.parent.glob(f"{p.name}.corrupt-*"))
    p.write_text(good, encoding="utf-8")
    real = groups_mod.read_json
    calls = {"n": 0}

    def flaky(path):
        if Path(path) == p and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(13, "locked", str(path))
        return real(path)
    monkeypatch.setattr(groups_mod, "read_json", flaky)
    monkeypatch.setattr(groups_mod.time, "sleep", lambda s: None)
    third = GroupStore(ws, cat)
    assert inner.id in third.groups and calls["n"] == 2

    def dead(path):
        if Path(path) == p:
            raise PermissionError(13, "locked", str(path))
        return real(path)
    monkeypatch.setattr(groups_mod, "read_json", dead)
    files = {q.name: q.read_text(encoding="utf-8") for q in p.parent.glob("*.json")}
    with pytest.raises(StateError, match="could not be read"):
        GroupStore(ws, cat)
    assert {q.name: q.read_text(encoding="utf-8") for q in p.parent.glob("*.json")} == files   # nothing rewritten


def test_v7_a_401_carries_the_cors_headers(tmp_path: Path):
    """The token gate sits inside CORS: a 401 reaches browser dev with its headers (it surfaced as 'Failed to fetch')."""
    from fastapi.testclient import TestClient
    from test_auth_d67 import _app
    with TestClient(_app(tmp_path), headers={}, raise_server_exceptions=False) as c:          # no token (the conftest gives every client one)
        r = c.get("/project", headers={"Origin": "http://127.0.0.1:1420"})
        assert r.status_code == 401 and r.headers.get("access-control-allow-origin") == "http://127.0.0.1:1420"
        assert c.options("/project", headers={"Origin": "http://127.0.0.1:1420", "Access-Control-Request-Method": "GET"}).status_code == 200


def test_v8_a_bad_layout_value_is_a_422(tmp_path: Path):
    """A layout item the model refuses (a kind it does not know, a size under one pixel) is a 422, not a 500 from the casts."""
    with _project(tmp_path) as (app, cl, svc):
        g = svc.require_groups().create("Kitchen")
        path = str(app.url_path_for("groups_layout", gid=g.id))
        method = next(next(iter(x.methods)) for r in app.routes for x in getattr(getattr(r, "original_router", r), "routes", []) if getattr(x, "name", "") == "groups_layout")
        put = lambda body: cl.request(method, path, json=body)   # noqa: E731
        assert put({"items": [{"kind": "banana", "id": "x"}]}).status_code == 422
        assert put({"items": [{"kind": "asset", "id": "x", "x": "far"}]}).status_code == 422
        assert put({"items": [{"kind": "asset", "id": "x", "w": 0}]}).status_code == 422
        assert put({"items": [{"kind": "asset", "id": "nowhere", "x": 1}]}).status_code == 400   # not on the page: the store's sentence, as before


def test_v9_an_uploaded_thumbnail_leaves_no_temp_file(tmp_path: Path):
    with _project(tmp_path) as (app, cl, svc):
        (tmp_path / "a.png").write_bytes(_png_bytes())
        rec = svc.catalogue.ingest_file(tmp_path / "a.png", kind="image", move=False, suite="story")
        r = cl.put(f"/assets/{rec.id}/thumbnail", content=_png_bytes(64, 64, 200), headers={"Content-Type": "image/png"})
        assert r.status_code == 200 and r.json()["params"]["thumb_source"] == "client"
        assert not (svc.ws.temp_dir / "thumbs" / f"{rec.id}.png").exists()
        assert svc.ws.thumb_path(rec.id, 256).is_file()


def test_v10_a_groups_counts_leave_trashed_assets_out(tmp_path: Path):
    """The page hides trashed assets; the card's and the tree's counts leave them out too."""
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    cat = Catalogue(ws)
    groups = GroupStore(ws, cat)
    ids = []
    for k in range(3):
        (tmp_path / f"a{k}.png").write_bytes(_png_bytes(v=30 * k + 5))
        ids.append(cat.ingest_file(tmp_path / f"a{k}.png", kind="image", move=False, suite="story").id)
    g = groups.create("Kitchen")
    groups.move([("asset", i) for i in ids], g.id)
    cat.trash([ids[0]])
    node = next(c for c in groups.tree()["children"] if c["id"] == g.id)
    assert node["assets"] == 2 and node["total"] == 2 and node["groups"] == 0
    assert len(groups.page(g.id)["group"]["items"]) == 2


def test_v11_a_requeue_is_on_disk_before_the_reply(tmp_path: Path):
    with _project(tmp_path) as (app, cl, svc):
        job = JobRecord(id="job_tr", kind="train_lora", recipe={"kind": "train_lora"}, status="failed", resumable=True, error="killed")
        svc.queue.jobs[job.id] = job
        svc.queue.paused = True
        r = cl.post(f"/jobs/{job.id}/requeue")
        assert r.status_code == 200 and r.json()["status"] == "queued"
        on_disk = json.loads(svc.ws.queue_path.read_text(encoding="utf-8"))
        assert next(j for j in on_disk["jobs"] if j["id"] == job.id)["status"] == "queued"


def test_v12_a_transient_permission_error_does_not_fail_the_thumbnail(tmp_path: Path, monkeypatch):
    """The thumbnail's replace retries (D42): one PermissionError no longer stamps `thumb_status: failed` for good."""
    from loom2 import fsio
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    cat = Catalogue(ws)
    (tmp_path / "a.png").write_bytes(_png_bytes())
    rec = cat.ingest_file(tmp_path / "a.png", kind="image", move=False, suite="story")
    monkeypatch.setattr(fsio, "REPLACE_FIRST_DELAY_S", 0.001)
    import os
    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        if str(dst).endswith(".webp") and calls["n"] < 1:
            calls["n"] += 1
            raise PermissionError(13, "held", str(dst))
        return real(src, dst)
    monkeypatch.setattr(os, "replace", flaky)
    assert cat.make_thumbs(rec).thumb_status == "done" and calls["n"] == 1


def test_v14_a_recipe_without_an_engine_graph_previews_no_problems(tmp_path: Path, object_info: dict):
    """`preview_problems` for a kind with no compiler (train_lora, tts): nothing to check, not a NotImplementedError (a 500)."""
    from loom2.engine.pipeline import preview_problems
    from test_graph_parity_d64 import _pin_review
    roster = _pin_review().full_roster(tmp_path)
    assert preview_problems(SimpleNamespace(kind="tts", refs=[], loras=None), roster, object_info) == []


async def test_v15_a_wedged_engine_is_restarted(tmp_path: Path, monkeypatch):
    """An engine process that lives but does not answer is restarted before the job, not failed job by job (one timeout each)."""
    from loom2.config import AppState
    from loom2.engine.supervisor import EngineSupervisor
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    sup = EngineSupervisor(AppState(state))
    sup.proc = SimpleNamespace(poll=lambda: None, pid=4242)                 # alive …
    calls: list[tuple] = []

    async def is_up():
        return False                                                       # … and silent

    async def restart(want=None):
        calls.append(("restart", want))
        sup.proc = None
    monkeypatch.setattr(sup.client, "is_up", is_up)
    monkeypatch.setattr(sup, "restart", restart)
    assert await sup.ensure_running(None) is False
    assert calls == [("restart", sup.headroom_for(None))] and sup.restarts == 1


def test_v16_generates_tiers_are_per_model():
    """Generate's tier sizes are the chosen model's, with the family's first spec as the fallback (krea2-raw's Full is not the turbo's)."""
    from loom2.capabilities import image_tiers
    from loom2.models import registry
    tiers = image_tiers()
    specs = registry.image_specs()
    for s in specs:
        for tier, wh in s.geometry.tiers.items():
            assert tiers[tier][s.id] == list(wh) and tiers[tier][s.family]
    assert any(tiers[t][s.id] != tiers[t][s.family] for s in specs for t in s.geometry.tiers)


def test_v17_the_headroom_follows_the_models_that_run(monkeypatch):
    from loom2 import queue as queue_mod
    monkeypatch.setattr(queue_mod, "plan", lambda recipe, variant: SimpleNamespace(weights=["m-panel", "m-runs", "lora-x"]))
    specs = {"m-panel": SimpleNamespace(engine=SimpleNamespace(vram_headroom_gb=None)), "m-runs": SimpleNamespace(engine=SimpleNamespace(vram_headroom_gb=3.0))}
    monkeypatch.setattr(queue_mod.registry, "get", lambda mid: specs.get(mid))
    assert queue_mod.model_headroom(SimpleNamespace(model_id="m-panel"), "full") == 3.0

    def refused(recipe, variant):
        raise ValueError("no plan")
    monkeypatch.setattr(queue_mod, "plan", refused)
    assert queue_mod.model_headroom(SimpleNamespace(), "full") is None


async def test_v18_the_history_is_read_again(tmp_path: Path, object_info: dict, monkeypatch):
    """ComfyUI writes a prompt's history after its success event: an empty first read is read again, briefly, before the job fails."""
    import asyncio as aio
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        q = rig.queue
        hist = {"outputs": {"9": {"images": [{"filename": "job_x_00001_.png", "subfolder": "", "type": "output"}]}}}
        answers: list = [None, {}, hist]

        async def history(pid):
            return answers.pop(0)
        naps: list[float] = []

        async def nap(s):
            naps.append(s)
        monkeypatch.setattr(q.engine.client, "history", history)
        monkeypatch.setattr(aio, "sleep", nap)
        job = JobRecord(id="job_x", kind="t2i", recipe={"kind": "t2i"}, status="running", prompt_id="p1")
        assert await q._outputs_after_success(job) == [{"filename": "job_x_00001_.png", "subfolder": ""}]
        assert answers == [] and len(naps) == 2
    finally:
        await rig.close()


async def test_v20_the_disk_guard_sums_once_per_few_seconds(tmp_path: Path, object_info: dict, monkeypatch):
    rig = _rig(tmp_path, object_info, monkeypatch)
    try:
        q = rig.queue
        calls = {"n": 0}
        monkeypatch.setattr(q.catalogue, "usage_bytes", lambda: calls.__setitem__("n", calls["n"] + 1) or 0)
        monkeypatch.setattr(q.ws, "info", lambda: {"size_cap_gb": 10})
        q._disk_guard()
        q._disk_guard()
        assert calls["n"] == 1
        q._usage_cache = (q._usage_cache[0] - 6.0, 0)
        q._disk_guard()
        assert calls["n"] == 2
    finally:
        await rig.close()


# ---- the eighth group (journal 2026-10-27): the shell, CI and the e2e (V48, V53–V56) and Story / Generate (V69–V77, Vitest) ----------


def test_v53_v54_the_ready_line_follows_the_bind_and_a_gone_parent_ends_the_orchestrator(tmp_path: Path):
    """`python -m loom2.main --parent-pid <gone>`: READY is printed once the socket answers (the first request after the line is a 200,
    never ECONNREFUSED), and the orchestrator ends by itself when the named parent is no longer running."""
    import socket
    import subprocess
    import time
    import urllib.request
    py = sys.executable
    gone = subprocess.run([py, "-c", "pass"], capture_output=True)                     # a pid that was, and is no more
    assert gone.returncode == 0
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    state = tmp_path / "state"
    from loom2.config import AppState
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    proc = subprocess.Popen([py, "-m", "loom2.main", "--port", str(port), "--state", str(state), "--parent-pid", str(_dead_pid(py))],
                            cwd=str(Path(__file__).resolve().parents[1]), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    try:
        line, t0 = "", time.time()
        while time.time() - t0 < 60:
            line = proc.stdout.readline()                                               # type: ignore[union-attr]
            if line.startswith("LOOM2_READY ") or not line:
                break
        assert line.startswith("LOOM2_READY "), line
        ready = json.loads(line[len("LOOM2_READY "):])
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"X-Loom-Token": ready["token"]})
        with urllib.request.urlopen(req, timeout=5) as r:                              # V53: right after the line — the socket is bound
            assert r.status == 200
        assert proc.wait(timeout=20) == 0                                               # V54: the parent is gone — the orchestrator ends on its own
    finally:
        if proc.poll() is None:
            proc.kill()


def _dead_pid(py: str) -> int:
    import subprocess
    p = subprocess.Popen([py, "-c", "pass"])
    p.wait()
    return p.pid


def test_v54_process_alive_and_watch_parent(tmp_path: Path):
    from loom2.parent import process_alive, watch_parent
    assert process_alive(os.getpid())
    assert not process_alive(_dead_pid(sys.executable))
    gone = []
    t = watch_parent(_dead_pid(sys.executable), lambda: gone.append(1), interval_s=0.05)
    t.join(5)
    assert gone == [1] and not t.is_alive()


def test_v56_a_gain_that_is_not_a_number_is_refused(tmp_path: Path):
    """The host splices the gain raw into its JSON reply: nan / inf are refused before anything runs."""
    from loom2 import vsthost
    host = next(v for v in vars(vsthost).values() if isinstance(v, type) and hasattr(v, "render"))
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="not a number"):
            host.render(SimpleNamespace(), [], tmp_path / "in.wav", tmp_path / "out" / "out.wav", bad)
    assert not (tmp_path / "out").exists()
