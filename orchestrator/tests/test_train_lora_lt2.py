"""LT2 (18 §3a / §3c / §4, D86): the `train_lora` job on the fake trainer — the registry and the engine's cached copy, the dataset with its
captions, the config in E16's shape, the submission's sentences, a staged job released → the engine stopped → progress from the trainer's
lines → the adapter promoted (the record, the version's slot, the slots' list, a Generate job carrying it), a crash requeued and resumed
from the newest save, the delete, the routes and /capabilities.train."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import loras as L  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import TrainLora  # noqa: E402
from loom2.story import StoryStore, cell_sentence  # noqa: E402
from loom2 import trainer as T  # noqa: E402

from test_lifecycle import Rig  # noqa: E402

TESTS = Path(__file__).resolve().parent
FAKE = TESTS / "fake_trainer.py"
CELLS = [{"shot": "close-up", "angle": "front", "expression": "neutral", "take": 1}, {"shot": "medium", "angle": "three-quarter left", "expression": "smiling", "take": 1},
         {"shot": "full body", "angle": "profile right", "expression": "neutral", "take": 1}, {"shot": "cowboy", "angle": "back", "expression": "neutral", "take": 1}]


def _trainable_base(roster) -> str:
    return next(i for i, sp in registry.SPECS.items() if sp.recipes.train and roster.resolve(i).path)


def _cast(rig: Rig, n_refs: int = 4, cells: bool = True):
    """A profile with a hero and `n_refs` references on its page (with coverage cells, as Expand leaves them)."""
    groups = GroupStore(rig.ws, rig.catalogue)
    rig.queue.groups = groups
    store = StoryStore(rig.ws)
    src = rig.ws.temp_dir / "src"
    src.mkdir(parents=True, exist_ok=True)
    ids = []
    for i in range(n_refs + 1):
        p = src / f"ref{i}.png"
        Image.new("RGB", (640, 360), (i * 40 % 255, 80, 120)).save(p)
        params = {"coverage_cell": CELLS[(i - 1) % len(CELLS)]} if i and cells else {}
        ids.append(rig.catalogue.ingest_file(p, move=False, params=params, state="keep" if i else "none", suite="story").id)
    prof = store.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier in a long grey coat")
    v = prof.versions[0]
    groups.move([("asset", a) for a in ids[1:]], v.group_id)
    return store, groups, prof, v, ids


def _settings(rig: Rig, **extra) -> None:
    rig.app.update_settings({"trainer": {"python": sys.executable, "run": str(FAKE), "cwd": str(TESTS), "vae": "ai-toolkit/flux2_vae", "quantize": "qfloat8"}, **extra})


# ---- the registry and the engine's copy --------------------------------------------------------------------------------------------
def test_registry_publish_and_options(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        reg = L.LoraRegistry(rig.ws)
        assert reg.list() == []
        rec = L.LoraRecord(id="lora_abc12345", name="Mara v1", profile_id="prf_1", version="v1", base="klein-9b", model_id=_trainable_base(rig.roster), trigger="mara_1a2b",
                           steps=1000, rank=16, resolution=512, lr=1e-4, seed=42, sha256="00" * 32, size=46, dataset={"count": 4})
        reg.save(rec)
        reg.file(rec.id).write_bytes(b"x" * 46)
        assert [r.id for r in reg.list()] == [rec.id] and reg.get(rec.id).trigger == "mara_1a2b"
        trained = L.publish(rig.roster, reg, tmp_path / "models", "prj1")
        assert trained[rec.id]["name"] == "projects/prj1/lora_abc12345.safetensors" and (tmp_path / "models" / "loras" / "projects" / "prj1" / "lora_abc12345.safetensors").stat().st_size == 46
        assert rig.roster.trained == trained
        rig.roster.scan()
        assert not any(u["name"] == "lora_abc12345.safetensors" for u in rig.roster.unlisted_files())       # the cache is not an unknown file
        assert not any(f["rel"].startswith("projects/") for f in rig.roster.lora_files())
        opts = L.lora_options(rig.roster, "klein-9b", "full")
        assert opts[0]["id"] == rec.id and opts[0]["source"] == "trained" and opts[0]["fits"] and opts[0]["trigger"] == "mara_1a2b" and "1000 steps" in opts[0]["label"]
        assert L.lora_name(rig.roster, rec.id) == "projects/prj1/lora_abc12345.safetensors"
        for9 = L.lora_options(rig.roster, "klein-4b", "full")
        assert for9[0]["id"] == rec.id and not for9[0]["fits"] and for9[0]["why"] == "trained for Klein 9B"
        with pytest.raises(ValueError, match="trained for Klein 9B"):
            L.check_loras(rig.roster, [L.LoraRef(model_id=rec.id)], "klein-4b", "full")
        L.check_loras(rig.roster, [L.LoraRef(model_id=rec.id, strength=0.8)], "klein-base-9b", "full")
        L.unpublish(rig.roster, tmp_path / "models", "prj1", rec.id)
        assert rec.id not in rig.roster.trained and not (tmp_path / "models" / "loras" / "projects" / "prj1" / "lora_abc12345.safetensors").exists()
    finally:
        import asyncio
        asyncio.run(rig.close())


# ---- the dataset and the config ----------------------------------------------------------------------------------------------------
def test_materialise_and_config(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        store, groups, prof, v, ids = _cast(rig, 4)
        base = _trainable_base(rig.roster)
        recipe = TrainLora(profile_id=prof.id, version=v.id, model_id=base, trigger="mara_1a2b", setting="plain studio background", steps=300)
        out = tmp_path / "set"
        meta = T.materialise(rig.ws, rig.catalogue, groups, store, recipe, out)
        assert meta["count"] == 5 and set(meta["asset_ids"]) == set(ids) and meta["setting"] == "plain studio background"
        pngs = sorted(out.glob("*.png"))
        assert len(pngs) == 5 and all(p.with_suffix(".txt").is_file() for p in pngs)
        caps = {p.stem.split("_", 1)[1]: p.with_suffix(".txt").read_text(encoding="utf-8") for p in pngs}
        assert caps[ids[0]] == "mara_1a2b, Mara, a wiry courier in a long grey coat, plain studio background"      # the hero: the stub
        assert caps[ids[1]] == f"mara_1a2b, {cell_sentence(CELLS[0])}, plain studio background"                  # a reference: its cell
        with Image.open(pngs[0]) as im:
            assert im.size == (640, 360)
        cfg = T.train_config(recipe, "job_x", out, tmp_path / "run", tmp_path / "models", "C:/hf/ae.safetensors", "qfloat8")
        p = cfg["config"]["process"][0]
        spec = registry.get(base)
        assert p["model"]["arch"] == spec.recipes.train.arch and p["model"]["layer_offloading"] == spec.recipes.train.offload
        assert p["model"]["name_or_path"] == str(tmp_path / "models" / "diffusion_models") and p["model"]["qtype"] == "qfloat8" and p["model"]["low_vram"] is True
        assert p["train"]["steps"] == 300 and p["train"]["optimizer"] == "adamw" and p["train"]["disable_sampling"] is True and p["network"]["linear"] == 16
        assert p["datasets"][0]["folder_path"] == str(out) and p["datasets"][0]["resolution"] == [512] and p["trigger_word"] == "mara_1a2b"
        got = T.parse_progress("x: 25%|██▌ | 250/1000 [00:00<?, ?it/s]\rx: 26%|██▌ | 260/1000 [00:10<13:00, 1.06s/it, lr: 1.0e-04 loss: 4.996e-01]\r")
        assert got == {"step": 260, "total": 1000, "s_per_it": 1.06, "loss": 0.4996}
        assert T.parse_progress("Found step 250 in metadata, starting from there\n")["resumed_from"] == 250
        assert T.parse_progress("x: 50%| | 5/10 [00:00<00:00, 20.00it/s]\r")["s_per_it"] == 0.05
    finally:
        import asyncio
        asyncio.run(rig.close())


# ---- the job on the fake trainer -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_train_job_staged_released_promoted_and_used(tmp_path: Path, object_info: dict, monkeypatch: pytest.MonkeyPatch):
    rig = Rig(tmp_path, object_info)
    try:
        _settings(rig)
        store, groups, prof, v, ids = _cast(rig, 4)
        base = _trainable_base(rig.roster)
        rig.queue.load()
        await rig.queue.start()
        body = {"kind": "train_lora", "profile_id": prof.id, "version": v.id, "model_id": base, "steps": 200, "trigger": "mara_1a2b", "name": "Mara v1"}
        for bad, why in (({**body, "model_id": "klein-9b"}, "not a trainable base"), ({**body, "trigger": ""}, "trigger word"), ({**body, "version": "v9"}, "v9")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit(bad)
        rig.app.update_settings({"trainer": {"python": str(tmp_path / "nope.exe")}})
        with pytest.raises(ValueError, match="trainer venv is missing"):
            rig.queue.submit(body)
        _settings(rig)
        store2, groups2, prof2, v2, _ = _cast(rig, 2)
        with pytest.raises(ValueError, match="at least 4"):
            rig.queue.submit({**body, "profile_id": prof2.id, "version": v2.id})
        job = rig.queue.submit(body, stage=True)[0]
        assert job.status == "staged" and job.warm_group == "trainer" and job.vram_estimate_gb == registry.get(base).recipes.train.vram_gb
        monkeypatch.setenv("FAKE_TRAINER_STEP_S", "0.002")
        rig.queue.release(job.id)
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert done.result["lora_id"].startswith("lora_") and done.result["trigger"] == "mara_1a2b" and done.result["refs"] == 5 and done.result["steps"] == 200
        assert done.progress == 1.0 and done.result["s_per_it"] == 1.0 and "peak_vram_gb" in done.result   # the trainer's own rate; the counter needs seconds a 0.4 s fake run never gives
        reg = L.LoraRegistry(rig.ws)
        rec = reg.get(done.result["lora_id"])
        assert rec and rec.base == L.model_base(base) and rec.model_id == base and rec.dataset["count"] == 5 and rec.size > 1000 and reg.file(rec.id).stat().st_size == rec.size
        assert rec.measured["s_per_it"] == 1.0 and rec.previous == []
        p = store.profile(prof.id)
        assert p.version(v.id).lora == rec.id and p.version(v.id).trigger == "mara_1a2b"
        assert rec.id in rig.roster.trained and (tmp_path / "models" / "loras" / "projects").is_dir()
        assert not (rig.ws.temp_dir / "train" / job.id).exists()                                          # the set and the saves are gone; the log stays
        assert (rig.app.logs_dir / f"train-{job.id}.log").is_file()
        # the slot: a Generate job on a model of the LoRA's base carries it to the engine under the engine's own name
        model = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and L.model_base(i) == rec.base and rig.roster.resolve(i).path)
        from fake_comfy import list_loras
        list_loras(rig.fake.object_info, tmp_path / "models")
        await rig.queue.object_info_refresh()
        t2i = rig.queue.submit({"kind": "t2i", "model_id": model, "prompt_mode": "text", "prompt_text": f"{rec.trigger}, a courier", "seeds": [3], "width": 64, "height": 64,
                                "loras": [{"model_id": rec.id, "strength": 1.0}]})[0]
        d2 = await rig.wait(t2i.id)
        assert d2.status == "done", d2.error
        assert d2.result["compiled"]["loras"][0]["lora_name"] == f"projects/{(rig.ws.info() or {}).get('id') or rig.ws.path.name}/{rec.id}.safetensors"
        node = next(n for n in rig.fake.prompts[-1]["graph"].values() if n["class_type"] == "LoraLoaderModelOnly" and rec.id in n["inputs"]["lora_name"])
        assert os.sep in node["inputs"]["lora_name"] or "/" not in node["inputs"]["lora_name"]
        # a retrain keeps the old id in `previous`
        job2 = rig.queue.submit({**body, "steps": 100})[0]
        d3 = await rig.wait(job2.id, timeout=60)
        assert d3.status == "done", d3.error
        rec2 = reg.get(d3.result["lora_id"])
        assert rec2.previous == [rec.id] and store.profile(prof.id).version(v.id).lora == rec2.id and len(reg.list()) == 2
    finally:
        await rig.close()


@pytest.mark.asyncio
async def test_train_job_crash_requeue_resumes_and_cancel(tmp_path: Path, object_info: dict, monkeypatch: pytest.MonkeyPatch):
    rig = Rig(tmp_path, object_info)
    try:
        _settings(rig)
        store, groups, prof, v, ids = _cast(rig, 4)
        base = _trainable_base(rig.roster)
        rig.queue.load()
        await rig.queue.start()
        body = {"kind": "train_lora", "profile_id": prof.id, "version": v.id, "model_id": base, "steps": 600, "trigger": "mara_1a2b"}
        monkeypatch.setenv("FAKE_TRAINER_STEP_S", "0.002")
        monkeypatch.setenv("FAKE_TRAINER_CRASH_AT", "300")                                              # the kill: after the step-250 save
        job = rig.queue.submit(body)[0]
        failed = await rig.wait(job.id, timeout=60)
        assert failed.status == "failed" and "exited with 1" in (failed.error or "") and failed.resumable
        assert (rig.ws.temp_dir / "train" / job.id / "out" / job.id.replace("-", "_") / f"{job.id.replace('-', '_')}_000000250.safetensors").is_file()
        with pytest.raises(KeyError):
            rig.queue.requeue(ids[0])                                                                   # not a job (the route's 404)
        monkeypatch.delenv("FAKE_TRAINER_CRASH_AT")
        rec = rig.queue.requeue(job.id)
        assert rec.status == "queued" and rec.retry_count == 1
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert done.result["resumed_from"] == 250 and done.result["lora_id"].startswith("lora_")
        assert L.LoraRegistry(rig.ws).get(done.result["lora_id"]).measured["resumed_from"] == 250
        with pytest.raises(ValueError, match="is done"):
            rig.queue.requeue(job.id)
        # a cancel while it runs kills the trainer
        monkeypatch.setenv("FAKE_TRAINER_STEP_S", "0.05")
        job2 = rig.queue.submit({**body, "steps": 400})[0]
        import asyncio
        for _ in range(200):
            await asyncio.sleep(0.05)
            j = rig.queue.get(job2.id)
            if j.status == "running" and j.progress_text.startswith("step"):
                break
        assert await rig.queue.cancel(job2.id)
        c = await rig.wait(job2.id, timeout=30)
        assert c.status == "cancelled"
    finally:
        await rig.close()


# ---- the routes and the capabilities -----------------------------------------------------------------------------------------------
def test_train_routes_and_capabilities(tmp_path: Path):
    state, models = tmp_path / "state", tmp_path / "models"
    for rel in ("diffusion_models/flux-2-klein-base-4b.safetensors", "text_encoders/qwen_3_4b.safetensors", "vae/flux2-vae.safetensors", "diffusion_models/flux-2-klein-4b.safetensors"):
        p = models / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(models), "mounted_model_trees": [], "variant": "full",
                                     "trainer": {"python": sys.executable, "run": str(FAKE), "cwd": str(TESTS)}})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "T", "size_cap_gb": 10}, headers=H)
        caps = cl.get("/capabilities", headers=H).json()["train"]
        assert caps["available"] and caps["why"] is None and caps["min_refs"] == 4 and caps["steps"]["default"] == 1000
        assert any(b["model_id"] == "klein-base-4b" and b["health"] == "present" and not b["offload"] and b["s_per_it"] == 1.07 for b in caps["bases"])
        assert cl.get("/story/loras", headers=H).json() == {"items": []}
        assert cl.get("/story/loras/lora_nope", headers=H).status_code == 404
        # a profile with too few references: the route answers the queue's sentence
        src = tmp_path / "h.png"
        Image.new("RGB", (64, 64), (200, 50, 50)).save(src)
        hero = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]["id"]
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, "stub": "Mara"}, headers=H).json()
        r = cl.post(f"/story/profiles/{p['id']}/train", json={"steps": 200}, headers=H)
        assert r.status_code == 422 and "at least 4" in r.json()["detail"]
        assert cl.post("/story/profiles/prf_none/train", json={}, headers=H).status_code == 404
        # the trigger is made from the name when absent, and the version keeps it
        for i in range(4):
            q = tmp_path / f"r{i}.png"
            Image.new("RGB", (64, 64), (50, 50, 200)).save(q)
            aid = cl.post("/assets/import", json={"paths": [str(q)]}, headers=H).json()["items"][0]["id"]
            cl.post(f"/story/profiles/{p['id']}/versions/v1/curate", json={"asset_ids": [aid], "verdict": "keep"}, headers=H)
        r = cl.post(f"/story/profiles/{p['id']}/train", json={"steps": 200, "stage": True}, headers=H)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["staged"] and body["model_id"] == "klein-base-4b" and body["trigger"].startswith("mara_") and len(body["trigger"]) == 9
        assert cl.get(f"/story/profiles/{p['id']}", headers=H).json()["versions"][0]["trigger"] == body["trigger"]
        job = cl.get(f"/jobs/{body['job_id']}", headers=H).json()
        assert job["status"] == "staged" and job["recipe"]["kind"] == "train_lora" and job["origin"]["surface"] == "train"
        assert cl.post(f"/jobs/{body['job_id']}/requeue", headers=H).status_code == 409                   # staged, not failed
        pv = cl.post("/recipes/preview", json={"recipe": job["recipe"]}, headers=H)
        assert pv.status_code == 200 and pv.json()["engine"] is False and pv.json()["estimate"]["seconds"] == 214
        assert cl.delete("/story/loras/lora_nope", headers=H).status_code == 404
