"""LT3 (18 §3f / §3h, D86): a profile mention adds its version's trained LoRA to the slots and its trigger to the note when the model takes
the base (off per prompt with `auto_lora`, never for another base, stamped on the mention); the identity check queues its eight jobs with
and without the LoRA and the record's `identity` grows as they land (the weights absent here: the record says so); the trainer's process
sits in the orchestrator's job object on Windows."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import loras as L  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.mentions import resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import LoraRef, T2I, Mention  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_lifecycle import Rig  # noqa: E402
from test_train_lora_lt2 import FAKE, TESTS, _cast, _settings  # noqa: E402


def _trained(rig: Rig, store: StoryStore, prof, v, base: str, lid: str = "lora_11112222") -> L.LoraRecord:
    reg = L.LoraRegistry(rig.ws)
    rec = L.LoraRecord(id=lid, name=f"{prof.name} {v.id}", profile_id=prof.id, version=v.id, base=base, model_id="klein-base-9b", trigger="mara_1a2b",
                       steps=1000, rank=16, resolution=512, lr=1e-4, seed=42, sha256="00" * 32, size=46, dataset={"count": 5})
    reg.save(rec)
    reg.file(rec.id).write_bytes(b"x" * 46)
    store.set_version_lora(prof.id, v.id, rec.id, rec.trigger)
    L.publish(rig.roster, reg, rig.app.state_dir.parent / "models", "prj")
    return rec


@pytest.mark.asyncio
async def test_a_mention_adds_the_versions_lora_and_trigger(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        store, groups, prof, v, ids = _cast(rig, 4)
        rec = _trained(rig, store, prof, v, "klein-9b")
        spec_ok = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and L.model_base(i) == "klein-9b" and rig.roster.resolve(i).path)
        r = T2I(model_id=spec_ok, prompt_mode="text", prompt_text="@Mara at the gate", width=64, height=64, mentions=[Mention(profile_id=prof.id, name="Mara")])
        out = resolve_mentions(r, groups, rig.catalogue, 4, store, rig.roster)
        assert [l.model_dump() for l in out.loras] == [{"model_id": rec.id, "strength": 1.0}]
        assert out.mentions[0].lora == rec.id and out.mentions[0].lora_available == rec.id and out.mentions[0].version == v.id
        assert out.refs and all(x.note and x.note.startswith("mara_1a2b, ") for x in out.refs)                     # the trigger leads every note
        assert resolve_mentions(out, groups, rig.catalogue, 4, store, rig.roster) is out                          # stamped: not resolved again
        # off for this prompt: no LoRA, the note without the trigger, the chip knows it is available
        off = resolve_mentions(r.model_copy(update={"auto_lora": False}), groups, rig.catalogue, 4, store, rig.roster)
        assert off.loras == [] and off.mentions[0].lora is None and off.mentions[0].lora_available == rec.id and not off.refs[0].note.startswith("mara_")
        # a slot already holding it is not doubled; a full set of slots is left alone
        twice = resolve_mentions(r.model_copy(update={"loras": [LoraRef(model_id=rec.id, strength=0.7)]}), groups, rig.catalogue, 4, store, rig.roster)
        assert [l.strength for l in twice.loras] == [0.7] and twice.mentions[0].lora is None
        # another base: nothing added, the chip still knows
        other = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and L.model_base(i) != "klein-9b" and rig.roster.resolve(i).path)
        o = resolve_mentions(r.model_copy(update={"model_id": other}), groups, rig.catalogue, 4, store, rig.roster)
        assert o.loras == [] and o.mentions[0].lora is None and o.mentions[0].lora_available == rec.id
        # the queue's path: preview == submit — the job's recipe carries the slot and the engine's graph the loader
        rig.queue.load()
        await rig.queue.start()
        from fake_comfy import list_loras
        list_loras(rig.fake.object_info, tmp_path / "models")
        await rig.queue.object_info_refresh()
        job = rig.queue.submit({**r.model_dump(), "seeds": [3]})[0]
        assert job.recipe["loras"] == [{"model_id": rec.id, "strength": 1.0}] and job.recipe["mentions"][0]["lora"] == rec.id
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        assert any(n["class_type"] == "LoraLoaderModelOnly" and rec.id in n["inputs"]["lora_name"] for n in rig.fake.prompts[-1]["graph"].values())
        a = rig.catalogue.get(done.result["asset_ids"][0])
        assert a.params["recipe"]["loras"][0]["model_id"] == rec.id and "mara_1a2b" in (a.prompt_text or "")
    finally:
        await rig.close()


@pytest.mark.asyncio
async def test_the_identity_check_queues_eight_jobs_and_the_record_grows(tmp_path: Path, object_info: dict):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state, models = tmp_path / "state", tmp_path / "models"
    for rel in ("diffusion_models/flux-2-klein-base-4b.safetensors", "text_encoders/qwen_3_4b.safetensors", "vae/flux2-vae.safetensors", "diffusion_models/flux-2-klein-4b.safetensors"):
        p = models / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    from fake_comfy import FakeComfy, list_loras
    fake = FakeComfy(object_info, state / "engine_out")
    port = fake.start()
    AppState(state).update_settings({"engine": {"port": port, "health_timeout_s": 5, "stall_timeout_s": 2}, "models_root": str(models), "mounted_model_trees": [], "variant": "full",
                                     "trainer": {"python": sys.executable, "run": str(FAKE), "cwd": str(TESTS)}})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "h.png"
        Image.new("RGB", (64, 64), (200, 50, 50)).save(src)
        hero = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]["id"]
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, "stub": "Mara"}, headers=H).json()
        svc = app.state.services
        reg = L.LoraRegistry(svc.ws)
        rec = L.LoraRecord(id="lora_33334444", name="Mara v1", profile_id=p["id"], version="v1", base="klein-4b", model_id="klein-base-4b", trigger="mara_9f9f",
                           steps=100, rank=16, resolution=512, lr=1e-4, seed=42, sha256="00" * 32, size=46)
        reg.save(rec)
        reg.file(rec.id).write_bytes(b"x" * 46)
        StoryStore(svc.ws).set_version_lora(p["id"], "v1", rec.id, rec.trigger)
        project_id = svc.ws.info()["id"]                                                                  # the route unpublishes under the project's own id
        L.publish(svc.roster, reg, models, project_id)
        list_loras(fake.object_info, models)
        # the preview with a slot before the engine ever answered a catalogue (a relaunched orchestrator): 200, the slot named, no problems list to filter
        pv = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_mode": "text", "prompt_text": "x", "mentions": [{"profile_id": p["id"], "name": "Mara"}]}}, headers=H)
        assert pv.status_code == 200, pv.text
        assert pv.json()["loras"][0]["model_id"] == rec.id and pv.json()["mentions"][0]["lora"] == rec.id and "mara_9f9f" in pv.json()["serialized_prompt"]
        assert cl.post("/story/loras/lora_nope/check", headers=H).status_code == 404
        r = cl.post(f"/story/loras/{rec.id}/check", headers=H)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["job_ids"]) == 8 and body["model_id"] == "klein-4b"                                     # the distilled model of the base first
        jobs = {j["id"]: j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] in body["job_ids"]}
        withs = [j for j in jobs.values() if j["origin"]["payload"]["which"] == "with"]
        assert len(withs) == 4 and all(j["recipe"]["loras"] == [{"model_id": rec.id, "strength": 1.0}] for j in withs)
        assert all(j["recipe"]["loras"] == [] for j in jobs.values() if j["origin"]["payload"]["which"] == "without")
        assert all(j["recipe"]["prompt_text"].startswith("mara_9f9f, ") and j["recipe"]["auto_lora"] is False and j["batch_id"] == body["batch_id"] for j in jobs.values())
        assert cl.get(f"/story/loras/{rec.id}", headers=H).json()["identity"]["status"] == "running"
        import time
        t0 = time.time()
        while time.time() - t0 < 60:
            st = {j["status"] for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] in body["job_ids"]}
            if st <= {"done", "failed", "cancelled"}:
                break
            time.sleep(0.2)
        assert st == {"done"}, st
        ident = cl.get(f"/story/loras/{rec.id}", headers=H).json()["identity"]
        assert ident["done"] == 8 and len(ident["with"]) == 4 and len(ident["without"]) == 4
        assert ident["status"] == "weights missing — scripts/fetch_facesim.py" and ident["with_mean"] is None    # no FaceSim weights in this tree
        page = cl.get(f"/groups/{body['group_id']}", headers=H).json()
        assert len(page["assets"]) == 8 and page["group"]["name"] == "Mara · v1 · LoRA check"
        assert cl.get("/story/loras", headers=H).json()["items"][0]["identity"]["n"] == 8
        # the delete: the record, the file, the engine's cache, the version's slot (the trigger stays)
        cache = models / "loras" / "projects" / project_id / f"{rec.id}.safetensors"
        assert cache.is_file()
        r = cl.delete(f"/story/loras/{rec.id}", headers=H)
        assert r.status_code == 200 and r.json() == {"deleted": rec.id}, r.text
        assert cl.get(f"/story/loras/{rec.id}", headers=H).status_code == 404 and not reg.file(rec.id).exists() and not cache.exists()
        vv = cl.get(f"/story/profiles/{p['id']}", headers=H).json()["versions"][0]
        assert vv["lora"] is None and vv["trigger"] == "mara_9f9f"
        assert rec.id not in svc.roster.trained
    fake.stop() if hasattr(fake, "stop") else None


def test_trainer_log_notes_the_job_object(tmp_path: Path):
    """The trainer's Popen is assigned to the orchestrator's job object on Windows (a kill takes it along); elsewhere it is simply noted."""
    from loom2.engine.supervisor import _assign_to_job
    import subprocess
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    ok = _assign_to_job(proc)
    proc.wait()
    assert ok is (os.name == "nt") or ok is False
