"""Regressions for the 2026-11-06 code review (register K1–K96, journal 2026-11-06 10:18)."""
from __future__ import annotations

from pathlib import Path

import pytest

from loom2.story import StoryStore
from loom2.workspace import Workspace


def _ws(tmp_path: Path) -> Workspace:
    return Workspace.create(tmp_path / "proj", name="K")


def test_k15_a_scene_patch_is_validated(tmp_path: Path):
    st = StoryStore(_ws(tmp_path))
    n = st.create_node("dialogue", title="In", with_shot=False)
    sc = st.create_scene("The gate", [n.id])
    with pytest.raises(ValueError):
        st.patch_scene(sc.id, {"words": "x" * 1001})                   # over the field's 1000: refused, not written
    with pytest.raises(ValueError):
        st.patch_scene(sc.id, {"colour": {"r": 1}})
    assert st.scene_book().scenes[0].words == ""                        # the book still reads
    st.flow_nodes()
    ok = st.patch_scene(sc.id, {"words": "night, drifting fog"})
    assert ok.words == "night, drifting fog" and st.scene_book().scenes[0].words == "night, drifting fog"


def test_k16_the_rebuild_keeps_assets_indexed_in_place(tmp_path: Path):
    from PIL import Image
    from loom2.catalogue import Catalogue
    ws = _ws(tmp_path)
    cat = Catalogue(ws)
    try:
        for rel in ("stages/stg_a/guides/cam_1-depth-r3.mp4", "story/anim_tests/prf_a-v1-tst_1.mp4"):
            p = ws.path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\x00" * 64)
        src = tmp_path / "s.png"
        Image.new("RGB", (8, 8), (1, 2, 3)).save(src)
        kept = cat.ingest_file(src, move=False)
        g = cat.ingest_file(ws.path / "stages/stg_a/guides/cam_1-depth-r3.mp4", kind="video", in_place=True, suite="stage", lineage_kind="stage-pass",
                            parents=[kept.id], frames=1, w=8, h=8)
        t = cat.ingest_file(ws.path / "story/anim_tests/prf_a-v1-tst_1.mp4", kind="video", in_place=True, suite="story", lineage_kind="stage-pass", frames=1, w=8, h=8)
        cat.add_lineage(kept.id, g.id, "", kind="stage-pass")
        assert cat.rebuild() == 3                                        # K16: the guide and the test come back with the asset
        assert cat.get(g.id) is not None and cat.get(t.id) is not None and cat.get(kept.id) is not None
        stray = ws.path / "somewhere" / "x.mp4"
        stray.parent.mkdir(parents=True)
        stray.write_bytes(b"\x00" * 8)
        with pytest.raises(ValueError, match="cannot be indexed in place"):
            cat.ingest_file(stray, kind="video", in_place=True, suite="stage", frames=1, w=8, h=8)
    finally:
        cat.close()


def test_k14_a_new_project_holds_no_file(tmp_path: Path):
    """A make that fails half-way leaves the session on a fresh project: going back to the file held before must open it again."""
    import json
    from loom2.config import AppState
    from loom2.effectcraft import EffectCraft
    app = AppState(tmp_path / "state")
    app.update_settings({"effectcraft": {"cli": str(Path(__file__).parent / "fake_effectcraft.py"), "timeout_s": 10.0}})
    ec = EffectCraft(app)
    try:
        ec.command("comp.new", {"name": "A", "width": 64, "height": 32, "frameRate": 16, "duration": 1})
        a = tmp_path / "a.ecproj"
        ec.tool("save_project", {"path": str(a)})
        ec.open(a)
        ec.new_project()                                                 # final B's make starts …
        assert ec.project is None
        ec.command("comp.new", {"name": "B half", "width": 32, "height": 16, "frameRate": 16, "duration": 1})   # … and fails here
        ec.open(a)                                                       # back to A: opened again, not B's half taken for it
        assert ec.project == str(a)
        out = tmp_path / "a.copy"
        ec.save_copy(out)
        names = [c["name"] for c in json.loads(out.read_text(encoding="utf-8"))["comps"].values()]
        assert names == ["A"]
    finally:
        ec.stop()


@pytest.mark.asyncio
async def test_k2_outpaint_candidates_grow_the_canvas_once(tmp_path: Path, object_info):
    import io
    import numpy as np
    from PIL import Image
    from test_lifecycle import MAGENTA, Rig
    rig = Rig(tmp_path, object_info, color=MAGENTA)
    try:
        base = np.zeros((96, 160, 4), dtype=np.uint8); base[..., 1] = 180; base[..., 3] = 255      # a green document
        od = rig.docs.create("doc", 160, 96, base_pixels=base)
        rig.queue.load()
        await rig.queue.start()
        jobs = rig.queue.submit({"kind": "inpaint", "mode": "outpaint", "document_id": od.doc.id, "prompt_text": "x", "seeds": [1, 2, 3],
                                 "outpaint": {"left": 32, "right": 64}, "feather": 2})
        for j in jobs:
            r = await rig.wait(j.id)
            assert r.status == "done", r.error
        assert (od.doc.w, od.doc.h) == (160 + 32 + 64, 96)                # once, not once per candidate
        assert [j.result.get("shift") for j in (rig.queue.jobs[x.id] for x in jobs)] == [{"left": 32, "top": 0}, {"left": 0, "top": 0}, {"left": 0, "top": 0}]
        group = od.doc.layers[0]
        assert group.id == f"grp_{jobs[0].batch_id}" and len(group.children) == 3
        base_layer = next(n for n in od.doc.walk() if n.kind == "raster" and not n.id.startswith("grp_") and n not in group.children)
        assert base_layer.x == 32                                         # shifted once
        for data in rig.fake.uploaded("image.png"):                      # every candidate saw the green picture padded by its edges, no magenta
            arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
            assert not np.any((arr[..., 0] > 200) & (arr[..., 1] < 50) & (arr[..., 2] > 200))
            assert arr[..., 1].min() > 100                                # no empty (black) strip from a grown canvas
    finally:
        await rig.close()


def test_k6_an_open_documents_synced_changes_are_saved_at_close(tmp_path: Path):
    """The editor syncs layers to the server's open document (D70) and writes the .ora on Save; closing the app (or switching project)
    must not drop what was synced and not yet written."""
    import json
    import zipfile
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        d = cl.post("/documents", json={"w": 64, "h": 32, "name": "Draft", "background": "transparent"}).json()
        assert cl.put(f"/documents/{d['id']}", json={**d, "name": "Renamed, not saved"}).status_code == 200
        listed = next(x for x in cl.get("/documents").json()["items"] if x["id"] == d["id"])
        assert listed["dirty"] is True                                   # what the editor now reads on open
        ora = Path(listed["path"])
    with zipfile.ZipFile(ora) as z:                                      # the app closed: the change is in the file
        assert json.loads(z.read("loom2.json").decode("utf-8"))["name"] == "Renamed, not saved"


def _alive(pid: int) -> bool:
    import subprocess
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


@pytest.mark.asyncio
async def test_k3_a_cancelled_task_takes_its_subprocess(tmp_path: Path):
    import asyncio
    import subprocess
    import sys
    from loom2.trainer import killed_on_cancel
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    async def runner():
        async with killed_on_cancel(proc):
            while proc.poll() is None:
                await asyncio.sleep(0.05)

    t = asyncio.create_task(runner())
    await asyncio.sleep(0.3)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert proc.poll() is not None and not _alive(proc.pid)


@pytest.mark.asyncio
async def test_k3_stopping_the_queue_kills_the_trainer(tmp_path: Path, object_info, monkeypatch):
    """Rule 10: opening another project stops the queue; a training job is re-queued for later and its trainer must not keep the card."""
    import asyncio
    import re
    from test_lifecycle import Rig
    from test_train_lora_lt2 import _cast, _settings, _trainable_base
    rig = Rig(tmp_path, object_info)
    try:
        _settings(rig)
        _, _, prof, v, _ = _cast(rig, 4)
        rig.queue.load()
        await rig.queue.start()
        monkeypatch.setenv("FAKE_TRAINER_STEP_S", "0.05")
        job = rig.queue.submit({"kind": "train_lora", "profile_id": prof.id, "version": v.id, "model_id": _trainable_base(rig.roster), "steps": 400,
                                "trigger": "mara_1a2b"})[0]
        for _ in range(200):
            await asyncio.sleep(0.05)
            j = rig.queue.get(job.id)
            if j.status == "running" and j.progress_text.startswith("step"):
                break
        pid = int(next(m.group(1) for x in rig.queue.get(job.id).log_tail if (m := re.match(r"trainer pid (\d+)", x))))
        assert _alive(pid)
        await rig.queue.stop()
        assert not _alive(pid)                                           # gone with the queue — not left training on the card
        assert rig.queue.get(job.id).status == "queued"                  # and the job waits to run again
    finally:
        await rig.close()


@pytest.mark.asyncio
async def test_k4_an_engine_started_by_hand_unloads_before_a_gpu_job(tmp_path: Path, object_info, monkeypatch):
    """Rule 10: a training job stops loom2's own engine; one started outside loom2 cannot be stopped from here, so it unloads every model
    first (it kept them beside a 13.6 GB trainer)."""
    from test_lifecycle import Rig
    from test_train_lora_lt2 import _cast, _settings, _trainable_base
    rig = Rig(tmp_path, object_info)
    try:
        _settings(rig)
        _, _, prof, v, _ = _cast(rig, 4)
        rig.queue.load()
        await rig.queue.start()
        await rig.engine.ensure_running()                                # the fake engine answers on the port: adopted, as a hand-started one is
        assert rig.engine.adopted
        monkeypatch.setenv("FAKE_TRAINER_STEP_S", "0.002")
        job = rig.queue.submit({"kind": "train_lora", "profile_id": prof.id, "version": v.id, "model_id": _trainable_base(rig.roster), "steps": 100,
                                "trigger": "mara_1a2b"})[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert {"unload_models": True, "free_memory": True} in rig.fake.frees
        assert any("unload its models" in x for x in done.log_tail)
    finally:
        await rig.close()


def test_k5_a_segment_job_is_admitted_as_the_model_it_runs():
    from loom2.engine.graphs import estimate_vram_gb, recipe_weights
    from loom2.models import registry
    from loom2.recipes import Segment, warm_group
    pts = Segment(document_id="d", mode="points")                       # the things/find routes: no model named → the matte by default
    sam = registry.segment_model("points")
    assert sam != pts.model_id
    assert sam in recipe_weights(pts, "full") and pts.model_id not in recipe_weights(pts, "full")
    assert warm_group(pts) == sam and estimate_vram_gb(pts) == registry.get(sam).estimates.vram_gb
    subject = Segment(document_id="d", mode="subject")
    assert recipe_weights(subject, "full") == registry.get(registry.segment_model("subject")).weights()


@pytest.mark.asyncio
async def test_k_rule10_two_overlapping_opens_leave_one_queue(tmp_path: Path):
    import asyncio
    from loom2.config import AppState
    from loom2.services import Services
    from loom2.workspace import Workspace
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    for n in ("a", "b"):
        Workspace.create(tmp_path / n, name=n)
    svc = Services(state)
    try:
        await asyncio.gather(svc.open_project(tmp_path / "a"), svc.open_project(tmp_path / "b"))
        loops = [t for t in asyncio.all_tasks() if "_run_loop" in repr(t.get_coro())]
        assert len(loops) == 1                                           # one queue runs (was two: the orphan ran the old project's jobs)
        await svc.close_project()
        await asyncio.sleep(0.05)
        assert not [t for t in asyncio.all_tasks() if "_run_loop" in repr(t.get_coro()) and not t.done()]
    finally:
        await svc.close_project()


def test_k_h3_gate_covers_the_models_sheet_and_fetch(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.models import registry
    from loom2.roster import ROSTER_BY_ID
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    h3 = next(s for s in registry.video_specs() if s.graph == "minimax_h3")
    gated = {x for x in h3.weights() if ROSTER_BY_ID[x].confirm}
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert not gated & {x["id"] for x in cl.get("/models").json()["items"]}
        r = cl.post("/models/fetch", json={"model_id": h3.id})
        assert r.status_code == 403 and "Settings" in r.json()["detail"]
        cl.put("/settings", json={"h3_licence_confirmed": True})
        assert gated <= {x["id"] for x in cl.get("/models").json()["items"]}
