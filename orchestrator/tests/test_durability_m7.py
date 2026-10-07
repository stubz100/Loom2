"""M7 durability suite, offline half (12 §8, 03 §6 "kill the app mid-job → relaunch resumes paused with the job queued, no
corrupt records"): power loss mid-job, a torn queue.json, a corrupt catalogue index, a truncated manifest, the engine dying
mid-job, and the disk guard. The rig half (real processes, the Job Object) is scripts/m7_durability.py."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import queue as queue_mod
from loom2.api import create_app
from loom2.catalogue import Catalogue
from loom2.config import AppState
from loom2.queue import JobQueue
from loom2.workspace import Workspace

from test_lifecycle import Rig


async def _wait_running(rig: Rig, jid: str, timeout: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = rig.queue.jobs[jid]
        if j.status == "running" and j.prompt_id:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("job never reached the engine")


async def test_power_loss_mid_job_relaunches_paused_with_the_job_queued(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, behaviour="silent")           # the engine accepts the prompt and never answers
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [1], "width": 64, "height": 64, "turbo": True})[0]
        await _wait_running(rig, job.id)
        rig.queue.persist()                                            # what the disk holds at the moment the power goes
        rig.queue._task.cancel()                                       # no clean stop, no clean_shutdown flag
        q2 = JobQueue(rig.ws, rig.app, rig.engine, rig.roster, rig.catalogue, rig.hub)
        q2.load()
        j = q2.jobs[job.id]
        assert j.status == "queued" and j.prompt_id is None and j.retry_count == 1 and "re-queued" in j.log_tail[-1]
        assert q2.paused is True and q2.resumed_unclean is True and q2.state()["resumed_unclean"] is True
        saved = json.loads(rig.ws.queue_path.read_text(encoding="utf-8"))
        assert saved["paused"] is True and saved["jobs"][0]["status"] == "queued"
    finally:
        await rig.close()


def test_torn_queue_file_is_quarantined_and_the_queue_starts_paused(tmp_path: Path):
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    ws.queue_path.write_text('{"schema_version": 1, "paused": false, "jobs": [{"id": "job_x", "sta', encoding="utf-8")   # torn write
    app = AppState(tmp_path / "state")
    cat = Catalogue(ws)
    q = JobQueue(ws, app, None, None, cat, None)  # type: ignore[arg-type]
    q.load()
    assert q.jobs == {} and q.paused is True
    assert q.recovery and "moved aside" in q.recovery[0]
    assert list(ws.jobs_dir.glob("queue.json.corrupt-*")), "the torn file was not kept"
    assert json.loads(ws.queue_path.read_text(encoding="utf-8"))["jobs"] == []     # a fresh, valid file replaced it
    assert q.state()["recovery"] == q.recovery
    cat.close()


def test_corrupt_catalogue_index_is_quarantined_and_rebuilt_from_manifests(tmp_path: Path):
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat = Catalogue(ws)
    png = tmp_path / "a.png"
    Image.new("RGB", (32, 32), (200, 10, 10)).save(png)
    rec = cat.ingest_file(png, kind="image", move=False, suite="import", prompt_text="red square")
    cat.close()
    ws.catalogue_db.write_bytes(b"this is not a database" * 100)
    cat2 = Catalogue(ws)
    again = cat2.get(rec.id)
    assert again is not None and again.prompt_text == "red square"
    assert cat2.recovery and "rebuilt" in cat2.recovery[0]
    assert list(ws.path.glob("catalogue.sqlite.corrupt-*"))
    cat2.close()


def test_truncated_manifest_is_skipped_by_rebuild(tmp_path: Path):
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat = Catalogue(ws)
    png = tmp_path / "a.png"
    Image.new("RGB", (32, 32), (10, 200, 10)).save(png)
    good = cat.ingest_file(png, kind="image", move=False, suite="import")
    bad_dir = ws.assets_dir / "2026-10"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "ast_torn.json").write_text('{"id": "ast_torn", "kind": "image", "path": "assets/2026-10/ast_torn.png", "w": 3', encoding="utf-8")
    n = cat.rebuild()
    assert n == 1 and cat.get(good.id) is not None and cat.get("ast_torn") is None
    cat.close()


async def test_engine_death_mid_job_fails_the_job_and_frees_the_queue(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, behaviour="silent")
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [2], "width": 64, "height": 64, "turbo": True})[0]
        await _wait_running(rig, job.id)
        rig.fake.stop()                                                # the engine process is gone
        t0 = time.time()
        while time.time() - t0 < 60 and rig.queue.jobs[job.id].status not in ("failed", "cancelled", "done"):
            await asyncio.sleep(0.2)
        j = rig.queue.jobs[job.id]
        assert j.status == "failed" and ("engine" in (j.error or "").lower()), j.error
        assert rig.queue._running_id is None
        assert rig.queue.state()["counts"].get("running", 0) == 0
    finally:
        await rig.close()


def test_disk_guard_refuses_new_jobs_with_a_clear_422(tmp_path: Path, monkeypatch):
    state = tmp_path / "state"
    app_state = AppState(state)
    app_state.update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Guard", "size_cap_gb": 10}, headers=H)
        ok = client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x", "seeds": [1]}, "stage": True}, headers=H)
        assert ok.status_code == 200
        monkeypatch.setattr(queue_mod, "free_space_gb", lambda p: 0.4)
        r = client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x", "seeds": [1]}, "stage": True}, headers=H)
        assert r.status_code == 422 and "disk guard" in r.json()["detail"] and "0.4 GB" in r.json()["detail"]
        monkeypatch.setattr(queue_mod, "free_space_gb", lambda p: 500.0)
        svc = app.state.services
        monkeypatch.setattr(svc.catalogue, "usage_bytes", lambda: int(11 * 2**30))      # over the 10 GB cap
        r = client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x", "seeds": [1]}, "stage": True}, headers=H)
        assert r.status_code == 422 and "over its 10 GB cap" in r.json()["detail"]
        assert client.get("/queue").json()["recovery"] == []
