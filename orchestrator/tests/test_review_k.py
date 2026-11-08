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


@pytest.mark.asyncio
async def test_k_broadcast_and_submit_from_a_worker_thread_land_on_the_loop(tmp_path: Path, object_info):
    """Three reviewers: finishers and routes broadcast and submit inside asyncio.to_thread — the hub's queues and the job table are the loop's."""
    import asyncio
    import threading
    from loom2.events import EventHub
    hub = EventHub()

    class WS:
        def __init__(self): self.sent = []
        async def send_text(self, t): self.sent.append(t)
        async def send_bytes(self, b): self.sent.append(b)
    ws = WS()
    hub.attach(ws)
    threads: list[str] = []

    def from_thread():
        threads.append(threading.current_thread().name)
        return [hub.broadcast("job.updated", {"n": i})["seq"] for i in range(5)]
    seqs = await asyncio.to_thread(from_thread)
    await asyncio.sleep(0.05)                                            # delivered without waiting for another wake-up of the loop
    assert seqs == [1, 2, 3, 4, 5] and len(ws.sent) == 5 and threads and threads[0] != threading.current_thread().name
    hub.detach(ws)
    from test_lifecycle import Rig
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.load()
        await rig.queue.start()
        rig.queue.pause()
        loop_thread = threading.current_thread()
        seen: list[bool] = []
        orig = rig.queue._submit
        def spy(*a, **k):
            seen.append(threading.current_thread() is loop_thread)
            return orig(*a, **k)
        rig.queue._submit = spy
        jobs = await asyncio.to_thread(rig.queue.submit, {"kind": "t2i", "prompt_text": "x", "seeds": [1]})
        assert jobs and seen == [True]                                   # the body ran on the loop, the thread got its jobs
    finally:
        await rig.close()


@pytest.mark.asyncio
async def test_k25_a_canvas_changed_while_the_job_ran_is_refused(tmp_path: Path, object_info, monkeypatch):
    """A crop while an inpaint runs: the result was planned on the old canvas — the job fails cleanly, nothing pasted at stale coordinates."""
    import numpy as np
    from loom2.engine import pipeline
    from test_lifecycle import MAGENTA, Rig
    rig = Rig(tmp_path, object_info, color=MAGENTA)
    real = pipeline.prepare_document

    async def then_crop(job, recipe, q):
        out = await real(job, recipe, q)
        od = q.documents.get(recipe.document_id)
        od.doc.w, od.doc.h = 120, 80                                    # the author crops while the engine works
        return out
    monkeypatch.setattr(pipeline, "prepare_document", then_crop)
    try:
        base = np.zeros((96, 160, 4), dtype=np.uint8); base[..., 1] = 180; base[..., 3] = 255
        od = rig.docs.create("doc", 160, 96, base_pixels=base)
        sel = np.zeros((96, 160), dtype=np.uint8); sel[30:60, 50:100] = 255
        od.selection, od.doc.has_selection = sel, True
        layers = len(list(od.doc.walk()))
        rig.queue.load()
        await rig.queue.start()
        j = rig.queue.submit({"kind": "inpaint", "mode": "fill", "document_id": od.doc.id, "prompt_text": "x", "seeds": [1]})[0]
        r = await rig.wait(j.id)
        assert r.status == "failed" and "canvas changed" in (r.error or "")
        assert len(list(od.doc.walk())) == layers                        # no layer landed
    finally:
        await rig.close()


def test_k1_a_reference_keeps_its_shape(tmp_path: Path):
    """D194: the reference reaches ReferenceLatent at the size fit_reference gave it (inside ref_max_px², its aspect kept) — no square ImageScale."""
    from types import SimpleNamespace
    from PIL import Image
    from loom2.engine import graphs
    from loom2.engine.pipeline import fit_reference
    src = tmp_path / "hero.png"
    Image.new("RGB", (2048, 1152), (9, 9, 9)).save(src)
    q = SimpleNamespace(ws=SimpleNamespace(temp_dir=tmp_path / "temp"))
    with Image.open(fit_reference(q, src, 1024, "ast_hero")) as im:
        assert im.size == (1024, 576)
    g: dict = {}
    from loom2.recipes import RefImage
    graphs._ref_chain(g, ["5", 0], [RefImage(asset_id="ast_hero")], {"ast_hero": "loom2ref-ast_hero.png"}, ["3", 0], 1024)
    assert [n["class_type"] for n in g.values()] == ["LoadImage", "VAEEncode", "ReferenceLatent"]


def test_k26_temp_and_engine_uploads_are_swept(tmp_path: Path, object_info):
    """Job-named upload files of dead jobs, graphs beyond the newest 200, stale blobs no waiting job names, and the engine's own uploads."""
    import os
    import time as _t
    from loom2.engine.supervisor import EngineSupervisor
    from loom2.queue import JobRecord
    from test_lifecycle import Rig
    rig = Rig(tmp_path, object_info)
    q, tmp = rig.queue, rig.ws.temp_dir
    q.load()
    live = JobRecord(kind="t2i", recipe={"kind": "t2i", "refs": [{"blob": "b" * 64}]}, status="queued")
    q.jobs[live.id] = live
    for sub, name in (("mattes", "clip-clip_1-job_dead0001.mp4"), ("lead", "lead-job_dead0002.mp4"), ("passes", "fin_1-lay_1-job_dead0003"),
                      ("mattes", f"clip-clip_2-{live.id}.mp4"), ("train", "job_dead0004")):
        p = tmp / sub / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.mkdir() if sub in ("passes", "train") else p.write_bytes(b"x")
    graphs = rig.ws.queue_path.with_name("graphs")
    graphs.mkdir(parents=True, exist_ok=True)
    for i in range(205):
        g = graphs / f"job_{i:08x}.json"
        g.write_text("{}", encoding="utf-8")
        os.utime(g, (1_000_000 + i, 1_000_000 + i))
    blobs = tmp / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    old = _t.time() - 3 * 24 * 3600
    for name in ("a" * 64, "b" * 64):
        (blobs / name).write_bytes(b"x")
        os.utime(blobs / name, (old, old))
    (blobs / ("c" * 64)).write_bytes(b"x")                              # fresh: kept
    q._reconcile_leftovers()
    assert not (tmp / "mattes" / "clip-clip_1-job_dead0001.mp4").exists() and not (tmp / "lead" / "lead-job_dead0002.mp4").exists()
    assert not (tmp / "passes" / "fin_1-lay_1-job_dead0003").exists() and not (tmp / "train" / "job_dead0004").exists()
    assert (tmp / "mattes" / f"clip-clip_2-{live.id}.mp4").exists()     # a live job's upload stays
    left = sorted(p.stem for p in graphs.glob("*.json"))
    assert len(left) == 200 and left[0] == f"job_{5:08x}"               # the oldest five went
    assert sorted(p.name for p in blobs.iterdir()) == ["b" * 64, "c" * 64]   # old and unnamed: gone; named by a waiting job or fresh: kept
    sup = EngineSupervisor(rig.app)
    inp = rig.app.state_dir / "engine_in"
    (inp / "sub").mkdir(parents=True, exist_ok=True)
    (inp / "loom2ref-ast_1.png").write_bytes(b"x"); (inp / "sub" / "image.png").write_bytes(b"x")
    assert sup.sweep_inputs() == 2 and not any(p.is_file() for p in inp.rglob("*"))
    assert "--input-directory" in sup._argv() and sup._argv()[sup._argv().index("--input-directory") + 1] == str(inp)


def test_k28_instruct_names_what_its_graph_loads():
    """The gate and /capabilities read one list: the transformer, encoder, VAE and Lightning — not the angles LoRA (Reangle's)."""
    from loom2.engine.graphs import instruct_weights, recipe_weights
    from loom2.models import registry
    from loom2.recipes import Instruct
    spec = registry.instruct_specs()[0]
    want = instruct_weights(spec)
    assert spec.roles.extra["angles"] not in want and spec.roles.extra["lightning"] in want and spec.roles.vae in want and len(want) == 4
    assert recipe_weights(Instruct(document_id="d", model_id=spec.id, prompt_text="make it night")) == want


def test_k42_a_composition_operation_holds_the_session():
    """Two finals' operations from two route threads: the second waits for the first's open → commands → save (no interleaving)."""
    import threading
    import time as _t
    from types import SimpleNamespace
    from loom2.compositions import CompositionStore, _held
    log: list = []

    class Store:
        @_held
        def op(self, f, ec, name):
            log.append(("open", name)); _t.sleep(0.05); log.append(("save", name))
    ec, s = SimpleNamespace(op_lock=threading.RLock()), Store()
    ts = [threading.Thread(target=s.op, args=(None, ec, n)) for n in ("A", "B")]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert [log[0][1], log[1][1]] == [log[0][1]] * 2 and [log[2][1], log[3][1]] == [log[2][1]] * 2
    assert all(getattr(CompositionStore, n).__wrapped__ for n in ("command", "batch", "set_source", "frame", "make", "mask_from_content"))


def test_k43_a_cancelled_assembly_leaves_the_compositions_footage(tmp_path: Path):
    """The footage is staged beside and swapped in at the end: a cancel (or a failure) mid-way leaves the live footage whole."""
    from loom2 import final_assembly
    from loom2.finals import FinalStore
    from loom2.stages import StageStore
    from test_compositions_ae1 import N, _final_assembled
    ws = _ws(tmp_path)
    st = StageStore(ws).create("Room")
    f, _ = _final_assembled(ws, st.id, st.cameras[0].id, tmp_path / "src")
    store = FinalStore(ws)
    comp = store.folder(f.id) / "comp"
    before = {p.relative_to(comp).as_posix(): p.read_bytes() for p in comp.rglob("*.png")}
    assert len(before) == 3 * N                                          # shadow, the box, her matte
    asked = []
    out = final_assembly.assemble_frames(store, store.get(f.id), tmp_path / "again", None, comp, lambda: asked.append(1) or len(asked) > 1)
    assert out == {"cancelled": True, "frames": 1}
    assert {p.relative_to(comp).as_posix(): p.read_bytes() for p in comp.rglob("*.png")} == before
    assert not comp.with_name("comp.new").exists()
    again = final_assembly.assemble_frames(store, store.get(f.id), tmp_path / "again2", None, comp)    # a whole run swaps in
    assert again["frames"] == N and len(list(comp.rglob("*.png"))) == 3 * N and not comp.with_name("comp.new").exists()


def test_k48_a_newer_shorter_final_ends_with_its_media(tmp_path: Path):
    """Assemble plays a newer final in place keeping the run's length — a final remade shorter is trimmed to its end (no held last frame)."""
    from fastapi.testclient import TestClient
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    from test_cuts_u7b import _client, _clip, _final, _v1
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "A", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b, a2 = _clip(ws, tmp_path, "a", (200, 0, 0), 48), _clip(ws, tmp_path, "b", (0, 0, 200)), _clip(ws, tmp_path, "a2", (250, 50, 0), 30)
        st = StoryStore(ws)
        na, nb = (st.create_node("shot", title=t) for t in ("Arrival", "The seal"))
        _final(ws, na.shot_id, a.id)
        _final(ws, nb.shot_id, b.id)
        route = [{"shot_id": n.shot_id, "node_id": n.id} for n in (na, nb)]
        tl = cl.post("/timelines", json={"name": "E", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"revision": tl["revision"], "route": {}, "shots": route}).json()
        assert [(x[1], x[3], x[4]) for x in _v1(cl, base)] == [("Arrival", 0, 48), ("The seal", 48, 24)]
        _final(ws, na.shot_id, a2.id)                                           # remade at 30 frames
        r = cl.post(f"{base}/assemble", json={"revision": r["timeline"]["revision"], "route": {}, "shots": route}).json()
        assert r["report"]["updated"] == ["Arrival"]
        assert [(x[1], x[2], x[3], x[4]) for x in _v1(cl, base)] == [("Arrival", a2.id, 0, 30), ("The seal", b.id, 30, 24)]   # closed up


def test_k46_a_revoiced_line_plays_whole(tmp_path: Path):
    """A line voiced again is swapped in place — at the new take's length (it kept the old one: a longer take was cut off)."""
    from fastapi.testclient import TestClient
    from fake_tts import tone
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    from test_cuts_u7b import _client, _clip, _final
    app = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "L", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a = _clip(ws, tmp_path, "a", (200, 0, 0), 48)
        st = StoryStore(ws)
        na = st.create_node("shot", title="Gate")
        st.patch_node(na.id, {"revision": st.flow_nodes()[na.id].revision, "lines": [{"speaker": None, "text": "Come in."}]})

        def voice(secs: float, tag: str) -> None:
            wav = tmp_path / f"{tag}.wav"
            tone(str(wav), secs)
            st.set_line_audio(na.id, 0, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        voice(0.5, "first")
        _final(ws, na.shot_id, a.id)
        route = [{"shot_id": na.shot_id, "node_id": na.id}]
        tl = cl.post("/timelines", json={"name": "Lines", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"revision": tl["revision"], "route": None, "shots": route}).json()
        assert [(i["line"], i["start"], i["duration"]) for i in r["tracks"]["audio"][0]["items"]] == [(0, 0, 12)]
        voice(1.0, "again")                                                  # voiced again, twice as long
        r = cl.post(f"{base}/assemble", json={"route": None, "shots": route}).json()
        assert [(i["line"], i["start"], i["duration"]) for i in r["tracks"]["audio"][0]["items"]] == [(0, 0, 24)]
        voice(0.25, "short")                                                 # and shorter
        r = cl.post(f"{base}/assemble", json={"route": None, "shots": route}).json()
        assert [(i["line"], i["start"], i["duration"]) for i in r["tracks"]["audio"][0]["items"]] == [(0, 0, 6)]


def test_k45_a_failed_print_leaves_the_earlier_ones_known(tmp_path: Path, monkeypatch):
    """Two tracks with effects; the second print fails: the first's companion is on disk with its entry (it was not, and the next mix
    printed it again — heard twice)."""
    import json
    from fastapi.testclient import TestClient
    from fake_tts import tone
    from loom2.cuts import CutError, Cuts
    from test_cuts_au4 import _client
    app, _ = _client(tmp_path)
    svc = app.state.services
    real, calls = Cuts._print, []

    def second_fails(self, *a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise CutError("the host fell over")
        return real(self, *a, **k)
    monkeypatch.setattr(Cuts, "_print", second_fails)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        tl = cl.post("/timelines", json={"name": "Fx", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        plugin = cl.get("/audio/plugins").json()["plugins"][0]
        ids = []
        for track, hz in (("A2", 220), ("A3", 330)):
            wav = tmp_path / f"{track}.wav"
            tone(str(wav), 1.0, hz=hz)
            a = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="import")
            r = cl.post(f"{base}/place", json={"asset_id": a.id, "track": track, "frame": 0}).json()
            tid = r["tracks"]["audio"][int(track[1:]) - 1]["id"]
            ids.append(tid)
            assert cl.post(f"{base}/fx", json={"track": tid, "op": "add", "plugin": {k: plugin[k] for k in ("bundle", "uid", "name", "vendor")}}).status_code == 200
        assert cl.get(f"{base}/mix").status_code >= 400                      # the second print failed
        raw = json.loads((tmp_path / "proj" / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))
        seq_item = next(it for it in raw["project"]["items"].values() if "Sequence" in it["kind"])
        known = json.loads(seq_item["metadata"].get("loom2.prints") or "{}")
        assert list(known) == [str(ids[0])]                                   # the first's companion is known
        monkeypatch.setattr(Cuts, "_print", real)
        assert cl.get(f"{base}/mix").status_code == 200
        raw = json.loads((tmp_path / "proj" / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))
        seq = next(it["kind"]["Sequence"] for it in raw["project"]["items"].values() if "Sequence" in it["kind"])
        assert len(seq["audio_tracks"]) == 3 + 2                              # A1–A3 and one companion each — not a second for A2


def test_k92_a_live_records_home_is_not_rehomed(tmp_path: Path):
    """The rehome deletes a home and its pages on the client's word that the record is gone — refused while the profile lives."""
    from loom2.bins import home_of, rehome, version_home
    from test_bin_b0 import _setup
    ws, cat, groups, ids = _setup(tmp_path, n=2)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    vh = version_home(groups, ines, "v1")
    top = home_of(groups, groups.parent.get(("group", vh.id)))
    with pytest.raises(ValueError, match="still in the project"):
        rehome(groups, top.id)
    with pytest.raises(ValueError, match="still in the project"):
        rehome(groups, vh.id)
    assert vh.id in groups.groups                                       # nothing deleted


def test_k90_a_voice_job_writes_on_the_voice_as_it_is_now(tmp_path: Path):
    """The TTS job's measurements land on the record as it is now: a rename meanwhile stays, a deleted voice stays deleted."""
    from loom2.voices import VoiceRecord, VoiceStore
    ws = _ws(tmp_path)
    vs = VoiceStore(ws)
    rec = VoiceRecord(name="Narrator", tier="draft", voice="af_heart")
    vs.save(rec)
    stale = vs.get(rec.id)                                               # the job read it …
    vs.change(rec.id, lambda r: setattr(r, "name", "Old sailor"))       # … the author renamed it meanwhile
    vs.change(stale.id, lambda r: setattr(r, "measured", {"lines": 3}))
    got = vs.get(rec.id)
    assert got.name == "Old sailor" and got.measured == {"lines": 3}
    vs.delete(rec.id)
    assert vs.change(rec.id, lambda r: setattr(r, "measured", {"lines": 4})) is None and vs.get(rec.id) is None


def test_k91_a_torn_library_animation_is_left_out(tmp_path: Path):
    from loom2.animations import AnimationStore
    lib = tmp_path / "state" / "animations"
    lib.mkdir(parents=True)
    (lib / "anm_torn.json").write_text("{torn", encoding="utf-8")
    assert AnimationStore(tmp_path / "stages", tmp_path / "state").library() == []   # it raised (a 400 for the whole library)


def test_k87_a_camera_move_on_a_model_without_one_is_refused():
    from loom2.engine.graphs import CompileError, build_i2v
    from loom2.models import registry
    from loom2.recipes import I2V
    ltx = next(s for s in registry.video_specs() if s.graph == "ltx23")
    with pytest.raises(CompileError, match="takes no camera move"):
        build_i2v(I2V(model_id=ltx.id, start_asset="ast_x", prompt_text="x", camera={"move": "pan_left", "speed": 1.0}), None, 1, "loom2/t", "s.png")   # type: ignore[arg-type]
