"""D66 (ArtCraft P4): a job's origin is stored, survives a restart, rides on the job and asset events, lands in the asset manifest, and the
Edit AI route sets it server-side; a version-1 queue file still loads."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState
from loom2.origin import JobOrigin
from loom2.queue import JobQueue
from test_lifecycle import Rig

ORIGIN = JobOrigin(suite="generate", surface="results", ref="bat_x", payload={"view": "grid"})


def test_a_version_1_queue_file_loads_with_no_origin(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    v1 = {"schema_version": 1, "paused": False, "jobs": [{"schema_version": 1, "id": "job_old", "kind": "t2i", "recipe": {"kind": "t2i", "prompt_text": "x"},
                                                       "status": "done"}]}
    rig.ws.queue_path.write_text(json.dumps(v1), encoding="utf-8")
    rig.queue.load()
    assert rig.queue.get("job_old").origin is None and rig.queue.get("job_old").status == "done"
    rig.fake.stop()


async def test_origin_survives_a_restart_and_reaches_the_asset(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    seen: list[tuple[str, dict]] = []
    orig = rig.hub.broadcast
    rig.hub.broadcast = lambda t, d=None: (seen.append((t, d)), orig(t, d))[1]          # type: ignore[method-assign]
    try:
        rig.queue.load()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [7], "width": 64, "height": 64}, stage=True, origin=ORIGIN)[0]
        await rig.queue.flush()
        q2 = JobQueue(rig.ws, rig.app, rig.engine, rig.roster, rig.catalogue, rig.hub)       # a restart reads the file
        q2.load()
        assert q2.get(job.id).origin == ORIGIN
        assert any(t == "job.created" and d["origin"] == ORIGIN.model_dump() for t, d in seen)
        await rig.queue.start()                                                           # start() reloads the file, then the release
        rig.queue.release(job.id)
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a.origin == ORIGIN                                                         # lineage at write time: the manifest has it
        manifest = json.loads(rig.catalogue.manifest_path(a).read_text(encoding="utf-8"))
        assert manifest["origin"] == ORIGIN.model_dump()
        assert any(t == "asset.created" and d["origin"] == ORIGIN.model_dump() for t, d in seen)
        assert any(t == "job.updated" and d["status"] == "done" and d["origin"] == ORIGIN.model_dump() for t, d in seen)
    finally:
        await rig.close()


def test_the_edit_ai_route_sets_the_origin(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as c:
        assert c.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        c.post("/queue/pause")
        Image.fromarray(np.full((48, 64, 3), 120, np.uint8)).save(tmp_path / "in.png")
        asset = c.post("/assets/import", json={"paths": [str(tmp_path / "in.png")]}).json()["items"][0]["id"]
        did = c.post("/documents", json={"from_asset": asset}).json()["id"]
        r = c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "segment", "mode": "subject"}})
        assert r.status_code == 200, r.text
        assert r.json()["jobs"][0]["origin"] == {"suite": "edit", "surface": "ai", "ref": did, "payload": None}
        g = c.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x"}, "stage": True, "origin": {"suite": "animate", "surface": "clip", "ref": "clp_1"}})
        assert g.status_code == 200 and g.json()["jobs"][0]["origin"]["ref"] == "clp_1"
