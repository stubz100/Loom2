import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image

from loom2.catalogue import Catalogue
from loom2.config import AppState
from loom2.engine import graphs
from loom2.events import EventHub
from loom2.queue import JobQueue
from loom2.recipes import T2I, parse_recipe
from loom2.roster import Roster
from loom2.workspace import Workspace


def _tree(tmp_path: Path, names: dict[str, list[str]]) -> Path:
    root = tmp_path / "models"
    for folder, files in names.items():
        for f in files:
            p = root / folder / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
    return root


@pytest.fixture
def dev_roster(tmp_path: Path) -> Roster:
    root = _tree(tmp_path, {"diffusion_models": ["flux2_dev_fp8mixed.safetensors", "flux-2-klein-9b.safetensors"],
                            "text_encoders": ["mistral_3_small_flux2_fp8.safetensors", "qwen_3_8b_fp8mixed.safetensors", "Qwen3-8B-Q4_K_M.gguf"],
                            "vae": ["flux2-vae.safetensors"], "loras": ["Flux2TurboComfyv2.safetensors"]})
    return Roster(root).scan()


def test_compile_t2i_dev_json_prompt(dev_roster: Roster, object_info: dict):
    r = T2I(prompt_json={"scene": "a rainy alley", "subject": {"name": "a woman", "pose": "turning"}}, width=950, height=540, turbo=True)
    c = graphs.compile_recipe(r, dev_roster, object_info, seed=7, out_prefix="loom2/job_x")
    assert c.problems == [], c.problems
    assert c.graph["8"]["inputs"] == {"width": 944, "height": 544, "batch_size": 1}   # multiples of 16
    assert c.graph["9"]["inputs"]["steps"] == 8 and c.graph["9"]["inputs"]["model"] == ["4", 0]    # turbo LoRA in the chain
    assert json.loads(c.graph["5"]["inputs"]["text"])["scene"] == "a rainy alley"                    # JSON verbatim for dev
    assert c.graph["11"]["inputs"]["filename_prefix"] == "loom2/job_x" and c.graph_hash and c.summary["prompt_mode"] == "json"


def test_compile_t2i_klein_flattens(dev_roster: Roster, object_info: dict):
    r = T2I(model_id="klein-9b", prompt_text="storyboard frame", prompt_json={"scene": "harbour", "lighting": ["dusk", "neon"]}, loras=[])
    c = graphs.compile_recipe(r, dev_roster, object_info, seed=1, out_prefix="p")
    assert c.problems == []
    text = c.graph["5"]["inputs"]["text"]
    assert text.startswith("storyboard frame. scene: harbour") and "dusk, neon" in text
    assert c.graph["9"]["inputs"]["steps"] == 4 and c.graph["1"]["inputs"]["weight_dtype"] == "fp8_e4m3fn"
    assert c.graph["7"]["class_type"] == "ConditioningZeroOut"


def test_compile_errors(dev_roster: Roster, object_info: dict):
    with pytest.raises(FileNotFoundError):
        graphs.compile_recipe(T2I(model_id="klein-4b", prompt_text="x"), dev_roster, object_info, 1, "p")
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(T2I(prompt_text="   "), dev_roster, object_info, 1, "p")
    with pytest.raises(graphs.CompileError):                  # M6: i2v compiles, but only with the uploaded start frame
        graphs.compile_recipe(parse_recipe({"kind": "i2v", "start_asset": "ast_1"}), dev_roster, object_info, 1, "p")
    assert graphs.flatten_json_prompt({"a": {"b": "c", "d": ["e", "f"]}, "g": None}) == "a: c, e, f"


def _png(path: Path, w: int = 64, h: int = 32) -> Path:
    Image.new("RGB", (w, h), (200, 30, 30)).save(path)
    return path


def test_catalogue_ingest_thumbs_list_patch_delete_rebuild(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32, 128])
    src = _png(tmp_path / "out.png")
    rec = cat.ingest_file(src, kind="image", move=True, job_id="job_1", suite="generate", model_id="flux2-dev-fp8mixed", seed=5, prompt_text="hello", parents=["ast_parent"])
    assert not src.exists() and (ws.path / rec.path).is_file() and rec.w == 64 and rec.h == 32 and rec.sha256
    assert cat.manifest_path(rec).is_file() and rec.thumb_status == "pending"
    rec = cat.make_thumbs(rec)
    assert rec.thumb_status == "done" and ws.thumb_path(rec.id, 32).is_file() and ws.thumb_path(rec.id, 128).is_file()
    cat.record_job({"id": "job_1", "kind": "t2i", "status": "done", "created_at": "2026", "finished_at": "2026"})
    assert cat.jobs_indexed() == 1
    page = cat.list(limit=10)
    assert [a.id for a in page.items] == [rec.id] and page.next_cursor is None and page.total == 1
    assert cat.list(search="hell").items and not cat.list(search="zzz").items
    assert cat.lineage(rec.id)["parents"][0]["from_id"] == "ast_parent"
    rec2 = cat.patch(rec.id, {"state": "keep", "rating": 4, "tags": ["a"], "path": "hack"})
    assert rec2.state == "keep" and rec2.rating == 4 and rec2.path == rec.path
    # the index is rebuildable from sidecars
    cat.close()
    ws.catalogue_db.unlink()
    cat = Catalogue(ws, [32])
    assert cat.count() == 0 and cat.rebuild() == 1 and cat.get(rec.id).state == "keep"
    assert cat.delete(rec.id) and cat.count() == 0 and not (ws.path / rec.path).exists() and not ws.thumb_path(rec.id, 32).exists()
    assert cat.delete(rec.id) is False
    cat.close()


class _FakeEngine:
    """Enough of EngineSupervisor for queue bookkeeping tests (no engine process)."""
    started_at = None
    jobs_since_start = 0

    class client:  # noqa: N801
        @staticmethod
        async def interrupt():
            pass


async def _queue(tmp_path: Path) -> tuple[JobQueue, Workspace]:
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    app = AppState(tmp_path / "state")
    app.update_settings({"variant": "full"})                       # dev recipes below; C3 gates them under `open`
    q = JobQueue(ws, app, _FakeEngine(), Roster(tmp_path / "none"), Catalogue(ws), EventHub())
    return q, ws


def test_queue_submit_persist_cancel_resume(tmp_path: Path):
    async def run():
        q, ws = await _queue(tmp_path)
        q.load()
        jobs = q.submit({"kind": "t2i", "prompt_text": "x", "seeds": [1, 2]})
        assert len(jobs) == 2 and jobs[0].batch_id == jobs[1].batch_id and all(j.status == "queued" for j in jobs)
        too_big = q.submit({"kind": "t2i", "prompt_text": "x", "model_id": "klein-9b"})[0]
        q.app.update_settings({"vram_budget_gb": 4})
        rejected = q.submit({"kind": "t2i", "prompt_text": "x"})[0]
        assert rejected.status == "failed" and "exceeds" in rejected.error and too_big.status == "queued"
        assert await q.cancel(jobs[0].id) and q.get(jobs[0].id).status == "cancelled"
        assert not await q.cancel(jobs[0].id) and q.delete(jobs[0].id) and q.get(jobs[0].id) is None
        assert not q.delete(jobs[1].id)                                     # queued jobs cannot be deleted
        q.pause()
        assert q.state()["paused"] and json.loads(ws.queue_path.read_text(encoding="utf-8"))["paused"]
        # simulate a crash while a job was running: it comes back queued with a retry count
        q.get(jobs[1].id).status = "running"
        q.persist(clean_shutdown=False)
        q2, _ = await _queue(tmp_path / "other")  # fresh objects, same queue file
        q2.ws = ws
        q2.load()
        j = q2.get(jobs[1].id)
        assert j.status == "queued" and j.retry_count == 1 and q2.paused
        assert q2.counts() == {"queued": 2, "failed": 1}
        with pytest.raises(ValueError):
            q2.submit({"kind": "nope"})
        q2.catalogue.close(); q.catalogue.close()
    asyncio.run(run())
