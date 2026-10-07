"""Engine and queue lifecycle against the fake ComfyUI (tests/fake_comfy.py) — the paths the 2026-10-06 review found
untested: supervisor start failure (B1), clean shutdown with a running job (B2), candidate isolation (B3), the stall
watchdog and a hung history poll (B4), cancel before submission (B5), engine_out cleanup (B6)."""
from __future__ import annotations

import asyncio
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from loom2.catalogue import Catalogue
from loom2.config import AppState
from loom2.documents import DocumentStore
from loom2.engine import supervisor as sup
from loom2.engine.supervisor import EngineSupervisor
from loom2.events import EventHub
from loom2.queue import JobQueue
from loom2.roster import Roster
from loom2.workspace import Workspace

from fake_comfy import FakeComfy, graph_image_name

MAGENTA = (255, 0, 255, 255)


def _tree(root: Path) -> Roster:
    for rel in ("diffusion_models/flux2_dev_fp8mixed.safetensors", "text_encoders/mistral_3_small_flux2_fp8.safetensors", "vae/flux2-vae.safetensors",
                "loras/Flux2TurboComfyv2.safetensors", "diffusion_models/flux-2-klein-9b.safetensors", "diffusion_models/flux-2-klein-base-9b.safetensors",
                "text_encoders/qwen_3_8b_fp8mixed.safetensors", "upscale_models/RealESRGAN_x2.pth"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


class Rig:
    """A project, an AppState pointed at the fake engine, a real EngineSupervisor (which adopts it) and a JobQueue."""

    def __init__(self, tmp: Path, object_info: dict, **fake_kw) -> None:
        self.state = tmp / "state"
        self.fake = FakeComfy(object_info, self.state / "engine_out", **fake_kw)
        port = self.fake.start()
        self.app = AppState(self.state)
        self.app.update_settings({"engine": {"port": port, "health_timeout_s": 5, "stall_timeout_s": 2}, "models_root": str(tmp / "models"), "mounted_model_trees": [],
                                  "variant": "full"})          # the fake tree holds full-only weights (dev, Klein 9B); C3 gates them under `open`
        self.roster = _tree(tmp / "models")
        self.ws = Workspace.create(tmp / "proj", name="P", size_cap_gb=10)
        self.catalogue = Catalogue(self.ws)
        self.hub = EventHub()
        self.engine = EngineSupervisor(self.app)
        self.queue = JobQueue(self.ws, self.app, self.engine, self.roster, self.catalogue, self.hub)
        self.docs = DocumentStore(self.ws)
        self.queue.documents = self.docs

    async def wait(self, job_id: str, statuses=("done", "failed", "cancelled"), timeout: float = 30.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = self.queue.get(job_id)
            if j and j.status in statuses:
                return j
            await asyncio.sleep(0.05)
        raise AssertionError(f"job {job_id} still {self.queue.get(job_id).status if self.queue.get(job_id) else None} after {timeout}s")

    async def close(self) -> None:
        await self.queue.stop()
        await self.engine.stop()
        await self.engine.client.aclose()
        self.catalogue.close()
        self.fake.stop()


# ---- B1 ---------------------------------------------------------------------------------------------------
async def test_supervisor_start_failure_raises_and_releases_lock(tmp_path: Path, monkeypatch):
    app = AppState(tmp_path / "state")
    app.update_settings({"engine": {"python": sys.executable, "main": "-c", "port": 1, "health_timeout_s": 0.5}})   # argv runs `python -c --listen …` → exits
    monkeypatch.setattr(sup, "wait_for_engine", lambda client, timeout_s=0.5, poll_s=1.0, **kw: asyncio.sleep(0.05, result=False))
    s = EngineSupervisor(app)
    with pytest.raises(RuntimeError, match="did not answer|exited with code"):
        await asyncio.wait_for(s.start(), timeout=10.0)       # before B1 this hung forever on the supervisor's own lock
    assert await asyncio.wait_for(s.stop(), timeout=10.0) and s.proc is None and s._log_fh is None
    await s.client.aclose()


# ---- B2 ---------------------------------------------------------------------------------------------------
async def test_clean_stop_requeues_running_job_and_interrupts(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, behaviour="silent")
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [1], "width": 64, "height": 64})[0]
        t0 = time.time()
        while not (rig.queue.get(job.id).status == "running" and rig.queue.get(job.id).prompt_id):
            assert time.time() - t0 < 20, rig.queue.get(job.id)
            await asyncio.sleep(0.05)
        await rig.queue.stop()
        on_disk = json.loads(rig.ws.queue_path.read_text(encoding="utf-8"))
        assert on_disk["clean_shutdown"] is True and on_disk["jobs"][0]["status"] == "queued"
        assert rig.fake.interrupts == 1
        q2 = JobQueue(rig.ws, rig.app, rig.engine, rig.roster, rig.catalogue, rig.hub)
        q2.load()
        j = q2.get(job.id)
        assert j.status == "queued" and j.error is None and j.prompt_id is None and not q2.paused
    finally:
        await rig.close()


# ---- happy path + B6 ---------------------------------------------------------------------------------------
async def test_t2i_job_end_to_end_moves_output_into_the_project(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [7], "width": 64, "height": 64, "turbo": True})[0]
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        assert j.result["asset_ids"] and j.result["compiled"]["graph_hash"]
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a and a.seed == 7 and rig.catalogue.abs_path(a).is_file() and a.thumb_status == "done"
        assert not list((rig.state / "engine_out" / "loom2").glob("*")), "engine output was not moved into the project"
        assert rig.engine.jobs_since_start == 1 and rig.engine.state()["running"] is False     # adopted, not supervised
    finally:
        await rig.close()


# ---- B5 ---------------------------------------------------------------------------------------------------
async def test_cancel_before_submission_never_reaches_the_engine(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, object_info_delay=1.0)
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [1], "width": 64, "height": 64})[0]
        t0 = time.time()
        while rig.queue.get(job.id).status != "running":
            assert time.time() - t0 < 10
            await asyncio.sleep(0.02)
        assert await rig.queue.cancel(job.id)
        j = await rig.wait(job.id, timeout=15)
        assert j.status == "cancelled" and j.error is None
        assert rig.fake.prompts == [], "the prompt was submitted although the job had been cancelled"
    finally:
        await rig.close()


# ---- B4 ---------------------------------------------------------------------------------------------------
async def test_stall_watchdog_fails_job_restarts_engine_and_pauses(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, behaviour="silent")
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [1], "width": 64, "height": 64})[0]
        j = await rig.wait(job.id, timeout=30)
        assert j.status == "failed" and "stalled" in (j.error or "")
        assert rig.queue.paused and rig.queue.state()["running"] is None
        assert rig.fake.interrupts >= 1 and rig.engine.restarts == 1
    finally:
        await rig.close()


async def test_hung_history_poll_does_not_crash_the_job(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, behaviour="silent")
    try:
        import httpx
        real_history = rig.engine.client.history

        async def hung(pid: str):
            raise httpx.ReadTimeout("hung")
        rig.engine.client.history = hung                     # type: ignore[method-assign]
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [1], "width": 64, "height": 64})[0]
        j = await rig.wait(job.id, timeout=30)
        assert j.status == "failed" and "stalled" in (j.error or ""), j.error   # the watchdog, not a traceback, ends it
        assert rig.queue.paused
        rig.engine.client.history = real_history             # type: ignore[method-assign]
    finally:
        await rig.close()


# ---- B3 ---------------------------------------------------------------------------------------------------
async def test_inpaint_candidates_are_alternatives_not_a_chain(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info, color=MAGENTA)
    try:
        base = np.zeros((96, 160, 4), dtype=np.uint8); base[..., 1] = 180; base[..., 3] = 255      # a green document
        od = rig.docs.create("doc", 160, 96, base_pixels=base)
        sel = np.zeros((96, 160), dtype=np.uint8); sel[30:60, 50:110] = 255
        od.selection = sel
        rig.queue.load()
        await rig.queue.start()
        jobs = rig.queue.submit({"kind": "inpaint", "mode": "fill", "document_id": od.doc.id, "prompt_text": "x", "seeds": [1, 2],
                                 "min_size": 128, "margin_pct": 10, "feather": 2})
        assert len(jobs) == 2 and jobs[0].batch_id == jobs[1].batch_id
        for j in jobs:
            r = await rig.wait(j.id)
            assert r.status == "done", r.error
        # both engine inputs were cropped from the document *without* the other candidate: no magenta anywhere
        crops = rig.fake.uploaded("image.png")
        assert len(crops) == 2
        for data in crops:
            arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
            assert not np.any((arr[..., 0] > 200) & (arr[..., 1] < 50) & (arr[..., 2] > 200)), "candidate 1 leaked into candidate 2's input"
        # the document got one AI group with two candidates, the first visible, recipes with seeds, and was saved
        group = od.doc.layers[0]
        assert group.kind == "group" and group.id == f"grp_{jobs[0].batch_id}" and len(group.children) == 2
        assert [c.visible for c in group.children] == [True, False]
        assert [c.recipe["seed"] for c in group.children] == [jobs[0].seed, jobs[1].seed]
        assert all(c.id in od.pixels for c in group.children) and od.path.is_file() and not od.dirty
        assert rig.fake.frees and all(f["unload_models"] is False for f in rig.fake.frees)      # cache freed, weights resident
        assert not list((rig.state / "engine_out" / "loom2").glob("*"))                       # B6: results are not left behind
        assert not (rig.ws.temp_dir / "ai").exists() or not any((rig.ws.temp_dir / "ai").iterdir())
        # the graphs really asked for the uploaded crop and mask
        g = rig.fake.prompts[0]["graph"]
        assert graph_image_name(g) == "image.png" and graph_image_name(g, "LoadImageMask") == "mask.png"
    finally:
        await rig.close()


# ---- B6: leftovers from a crashed run go when the project opens ----------------------------------------------------
async def test_start_reconciles_engine_leftovers(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info)
    try:
        out = rig.state / "engine_out" / "loom2"
        out.mkdir(parents=True)
        (out / "job_dead1_00001_.png").write_bytes(b"x")                     # a job nobody remembers
        (rig.ws.temp_dir / "ai" / "job_dead2").mkdir(parents=True)
        (rig.ws.temp_dir / "ai" / "job_dead2" / "image.png").write_bytes(b"x")
        rig.queue.load()
        live = rig.queue.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1]}, stage=True)[0]   # staged: not live either
        rig.queue.pause()
        queued = rig.queue.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1]})[0]
        (out / f"{queued.id}_00001_.png").write_bytes(b"x")                   # belongs to a queued job: kept
        removed = rig.queue._reconcile_leftovers()
        assert removed == 2
        assert not (out / "job_dead1_00001_.png").exists() and not (rig.ws.temp_dir / "ai" / "job_dead2").exists()
        assert (out / f"{queued.id}_00001_.png").exists()
        assert rig.queue.get(live.id).status == "staged"
    finally:
        await rig.close()


# ---- B11: scheduling and submission ---------------------------------------------------------------------------
def test_warm_group_affinity_ages_out(tmp_path: Path):
    from loom2 import queue as qmod
    from datetime import datetime, timedelta, timezone
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    app = AppState(tmp_path / "state")
    q = JobQueue(ws, app, type("E", (), {"started_at": None, "jobs_since_start": 0})(), Roster(tmp_path / "none"), Catalogue(ws), EventHub())
    try:
        q.load()
        dev = q.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1]})[0]                       # flux2-dev-fp8mixed
        klein = q.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1], "model_id": "klein-9b"})[0]
        q._last_group = "klein-9b"
        assert q._next().id == klein.id                                                            # affinity wins …
        dev.created_at = (datetime.now(timezone.utc) - timedelta(seconds=qmod.MAX_WARM_SKIP_S + 1)).isoformat(timespec="seconds")
        assert q._next().id == dev.id                                                              # … until the other job has waited too long
        with pytest.raises(ValueError, match="unknown model id"):
            q.submit({"kind": "t2i", "prompt_text": "x", "model_id": "nope"})
        with pytest.raises(ValueError, match="unknown model id"):
            q.submit({"kind": "inpaint", "document_id": "d", "loras": [{"model_id": "nope"}]})
    finally:
        q.catalogue.close()


# ---- recipe bounds (B4) --------------------------------------------------------------------------------------
def test_recipe_size_knobs_are_bounded():
    from loom2.recipes import parse_recipe
    with pytest.raises(ValueError):
        parse_recipe({"kind": "inpaint", "document_id": "d", "expand": 10**6})
    with pytest.raises(ValueError):
        parse_recipe({"kind": "inpaint", "document_id": "d", "mode": "outpaint", "outpaint": {"right": 10**6}})
    with pytest.raises(ValueError):
        parse_recipe({"kind": "i2i", "document_id": "d", "strength": 7})
    assert parse_recipe({"kind": "inpaint", "document_id": "d", "expand": 12, "margin_pct": 50}).expand == 12
