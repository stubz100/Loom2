"""2026-10-07 review register (journal, C1–C31): regression tests for the fixes that have an offline twin — the stack
revision (C1), the engine launch failure (C2), the open-variant gate (C3), the upscale layer's alpha (C4), concurrent
thumbnails (C5), purging a clip (C6) and link types in the contract check (C9)."""
from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.catalogue import Catalogue
from loom2.clips import ClipStore
from loom2.config import AppState
from loom2.documents import RasterLayer
from loom2.engine.contract import check_graph
from loom2.engine.supervisor import EngineSupervisor
from loom2.events import EventHub
from loom2.queue import JobQueue
from loom2.workspace import Workspace

from test_lifecycle import Rig, _tree


def _settings(tmp_path: Path, **extra) -> dict:
    return {"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], **extra}


# ---- C3: the build variant is the shell's, and the queue enforces it ------------------------------------------------
def test_c3_shell_variant_wins_over_the_persisted_one_and_settings_cannot_change_it(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"variant": "full"})             # an earlier `full` launch wrote app.json
    a = AppState(state, variant="open")                              # the `open` shell hands its baked variant over
    assert a.settings.variant == "open"
    a.update_settings({"variant": "full", "vram_budget_gb": 12})
    assert a.settings.variant == "open" and a.settings.vram_budget_gb == 12
    assert AppState(state).settings.variant == "open"                # what the shell set is what got persisted


def test_c3_open_variant_rejects_full_only_weights_and_filters_capabilities(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings(_settings(tmp_path))
    with TestClient(create_app(state, variant="open")) as client:
        H = {"X-Loom-Token": client.app.state.services.app.token}
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "O", "size_cap_gb": 10}, headers=H)
        client.post("/queue/pause", headers=H)
        caps = client.get("/capabilities").json()
        assert caps["variant"] == "open" and "flux2-dev-fp8mixed" not in caps["models"] and "klein-4b" in caps["models"]
        assert set(caps["i2v"]["models"]) == {"wan22-i2v-high-fp8"}                                     # LTX-2.3 is community-licensed

        def post(recipe: dict):
            return client.post("/jobs", json={"recipe": recipe, "stage": True}, headers=H)
        r = post({"kind": "t2i", "prompt_text": "x"})                                                    # dev is the default model
        assert r.status_code == 422 and "open variant" in r.json()["detail"]
        assert post({"kind": "t2i", "prompt_text": "x", "model_id": "klein-4b"}).status_code == 200
        assert post({"kind": "i2v", "start_asset": "a", "model_id": "ltx23-distilled-fp8"}).status_code == 422
        assert post({"kind": "i2v", "start_asset": "a"}).status_code == 200
        doc = client.post("/documents", json={"w": 64, "h": 48}, headers=H).json()

        def ai(recipe: dict):
            return client.post(f"/documents/{doc['id']}/ai", json={"recipe": recipe, "stage": True}, headers=H)
        assert ai({"kind": "inpaint", "mode": "fill_hero", "prompt_text": "x"}).status_code == 422          # forces dev
        assert ai({"kind": "inpaint", "mode": "fill", "prompt_text": "x"}).status_code == 422               # Klein 9B default
        r = ai({"kind": "inpaint", "mode": "remove", "model_id": "klein-4b", "prompt_text": "x"})
        assert r.status_code == 200 and r.json()["jobs"][0]["warm_group"] == "klein-4b"                   # ICM on Klein 4B, not 9B
        assert ai({"kind": "segment", "model_id": "sam3", "mode": "text", "text": "x"}).status_code == 422
        assert ai({"kind": "segment", "model_id": "birefnet", "mode": "subject"}).status_code == 200
        assert ai({"kind": "i2i", "model_id": "klein-base-4b"}).status_code == 200
        assert client.put("/settings", json={"variant": "full"}, headers=H).json()["variant"] == "open"   # read-only (D26)
        client.post("/project/close", headers=H)


# ---- C2: an engine that cannot launch holds the queue instead of failing every job ---------------------------------
async def test_c2_engine_launch_failure_requeues_the_job_and_pauses(tmp_path: Path):
    dying = tmp_path / "dying_main.py"
    dying.write_text("import sys; sys.exit(3)\n", encoding="utf-8")                  # a broken venv / import error
    app = AppState(tmp_path / "state")
    app.update_settings({"engine": {"python": sys.executable, "main": str(dying), "health_timeout_s": 10, "port": 8198},
                         "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat, hub, eng = Catalogue(ws), EventHub(), EngineSupervisor(app)
    q = JobQueue(ws, app, eng, _tree(tmp_path / "models"), cat, hub)
    try:
        await q.start()
        jobs = q.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1, 2]})
        t0 = time.time()
        while not q.paused and time.time() - t0 < 30:
            await asyncio.sleep(0.1)
        assert q.paused, "the queue kept going after the engine failed to launch"
        assert time.time() - t0 < 8, "sat out the health timeout although the process had exited"
        assert all(q.jobs[j.id].status == "queued" for j in jobs) and q.counts().get("failed", 0) == 0
        assert "engine could not start" in q.jobs[jobs[0].id].log_tail[-1]
        assert eng.last_error and "exited with code 3" in eng.last_error
        assert any(e["type"] == "queue.state" and e["data"]["paused"] for e in hub.recent)
    finally:
        await q.stop()
        await eng.stop()
        await eng.client.aclose()
        cat.close()


# ---- C4: the upscale detail layer keeps the source's alpha ------------------------------------------------------
async def test_c4_upscale_detail_layer_keeps_the_source_alpha(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info)
    spec = rig.fake.object_info["UpscaleModelLoader"]["input"]["required"]["model_name"]
    enum = spec[0] if isinstance(spec[0], list) else spec[1]["options"]           # legacy or V3 COMBO form
    if "RealESRGAN_x2.pth" not in enum:
        enum.append("RealESRGAN_x2.pth")
    try:
        px = np.zeros((48, 64, 4), dtype=np.uint8)
        px[..., :3] = (10, 200, 30)
        px[:, 32:, 3] = 255                                                    # left half transparent, right half opaque
        od = rig.docs.create("doc", 64, 48, base_pixels=px)
        lid = od.doc.layers[0].id
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "upscale", "document_id": od.doc.id, "model_id": "realesrgan-x2", "source": "active",
                                "layer_id": lid, "as_layer": True, "seeds": [0]})[0]
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        new = od.pixels[j.result["layers"][0]]
        assert new.shape == (48, 64, 4)
        assert new[:, :32, 3].max() == 0 and new[:, 32:, 3].min() == 255      # before C4 the whole layer was opaque
        assert tuple(new[10, 40, :3]) == (255, 0, 255)                         # the engine's result where the layer is visible
    finally:
        await rig.close()


# ---- C5: two thumbnail makers on one asset ------------------------------------------------------------------------
def test_c5_concurrent_thumbnail_makers_both_succeed(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [64, 128])
    src = tmp_path / "big.png"
    Image.fromarray(np.random.default_rng(1).integers(0, 255, (512, 768, 3), dtype=np.uint8)).save(src)
    rec = cat.ingest_file(src, kind="image", move=True)
    out: list[str] = []

    def worker() -> None:
        out.append(cat.make_thumbs(cat.get(rec.id)).thumb_status)
    for _ in range(6):                                                         # the queue's pass and GET /thumbs, side by side
        ts = [threading.Thread(target=worker) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    assert out == ["done"] * 12 and cat.get(rec.id).thumb_status == "done"
    assert not list((ws.thumbs_dir / rec.id).glob("*.tmp"))
    cat.close()


# ---- C6: purging a clip proxy removes the clip ---------------------------------------------------------------------
def test_c6_purging_a_clip_proxy_removes_the_whole_clip(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings(_settings(tmp_path))
    with TestClient(create_app(state)) as client:
        H = {"X-Loom-Token": client.app.state.services.app.token}
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10}, headers=H)
        svc = client.app.state.services
        store = ClipStore(svc.ws)
        frames = []
        for i in range(3):
            p = tmp_path / f"f{i}.png"
            Image.new("RGB", (64, 48), (i * 80, 20, 200)).save(p)
            frames.append(p)
        rec = store.encode_proxy(store.create(frames, model_id="wan22-i2v-high-fp8", prompt="t", seed=1, fps=16, start_asset_id="ast_x"))
        asset = svc.catalogue.ingest_file(svc.ws.path / rec.proxy_path, kind="video", in_place=True, suite="animate", params={"clip_id": rec.id}, frames=3, w=64, h=48)
        assert client.get(f"/clips/{rec.id}/proxy.mp4").status_code == 200
        client.post("/assets/trash", json={"ids": [asset.id]}, headers=H)
        assert client.post("/assets/purge", json={"ids": [asset.id]}, headers=H).json()["purged"] == 1
        assert not (svc.ws.clips_dir / rec.id).exists()                        # master frames and clip.json went with the proxy
        assert client.get("/clips").json()["items"] == []
        assert client.get(f"/clips/{rec.id}/proxy.mp4").status_code == 404      # not a 500 from FileResponse
        client.post("/project/close", headers=H)


# ---- C1: a stale stack PUT is refused; the server's newer layers survive --------------------------------------------
def test_c1_stale_stack_put_is_refused_and_server_added_layers_survive(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings(_settings(tmp_path))
    with TestClient(create_app(state)) as client:
        H = {"X-Loom-Token": client.app.state.services.app.token}
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        d = client.post("/documents", json={"w": 32, "h": 24, "name": "s"}, headers=H).json()
        assert d["revision"] == 0
        d1 = client.put(f"/documents/{d['id']}", json={**d, "name": "edited"}, headers=H).json()
        assert d1["revision"] == 1
        # the queue inserts a layer server-side (what _add_result_layer does) …
        od = client.app.state.services.documents.get(d["id"])
        od.doc.layers.insert(0, RasterLayer(id="lyr_ai", name="ai"))
        od.set_pixels("lyr_ai", np.zeros((24, 32, 4), dtype=np.uint8))
        od.doc.revision += 1
        # … and a client stack still based on revision 1 must not wipe it
        r = client.put(f"/documents/{d['id']}", json={**d1, "name": "stale"}, headers=H)
        assert r.status_code == 409 and "revision" in r.json()["detail"]
        assert "lyr_ai" in od.pixels and od.doc.find("lyr_ai") is not None and od.doc.name == "edited"
        # a stack that has merged the server's layers saves normally; a legacy body without a revision is not refused
        fresh = client.get(f"/documents/{d['id']}").json()
        assert fresh["revision"] == 2
        assert client.put(f"/documents/{d['id']}", json={**fresh, "name": "merged"}, headers=H).json()["revision"] == 3
        legacy = {k: v for k, v in fresh.items() if k != "revision"}
        assert client.put(f"/documents/{d['id']}", json=legacy, headers=H).status_code == 200
        client.post("/project/close", headers=H)


# ---- C9: link types ----------------------------------------------------------------------------------------------
def test_c9_contract_check_reports_link_type_mismatches(object_info: dict):
    g = {"1": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 64, "height": 64, "batch_size": 1}},
         "2": {"class_type": "VAEEncode", "inputs": {"pixels": ["1", 0], "vae": ["1", 0]}}}
    problems = check_graph(object_info, g)
    assert any("takes IMAGE" in p and "LATENT" in p for p in problems), problems
    assert any("takes VAE" in p for p in problems), problems
