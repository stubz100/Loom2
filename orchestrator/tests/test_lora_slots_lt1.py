"""LT1 (18 §3b / §3e, D25): the LoRA slots — the roster's free LoRAs and the files under the loras folders, the fit check at submission
(a sentence, HTTP 422), the chain in the t2i / i2i / inpaint graphs after the preset's own LoRA, GET /loras, the engine's listing refreshed
for a file it has not seen, and a job on the fake engine whose manifest and compiled summary record the slots."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import loras as L  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.graphs import compile_recipe  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import LoraRef, T2I  # noqa: E402
from loom2.roster import ROSTER, ROSTER_BY_ID, Roster, RosterEntry  # noqa: E402

from fake_comfy import list_loras  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_lifecycle import Rig  # noqa: E402


def _lora_tree(root: Path) -> None:
    for rel in ("loras/e16/mara.safetensors", "loras/own.safetensors", "loras/projects/prj/lora-1.safetensors"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)


def _t2i_model(roster: Roster) -> str:
    return next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and roster.resolve(i).path)


# ---- the sources and the fit -------------------------------------------------------------------------------------------------------
def test_lora_files_and_options(models_tree: Path):
    _lora_tree(models_tree)
    r = Roster(models_tree).scan()
    assert [f["rel"] for f in r.lora_files()] == ["e16/mara.safetensors", "own.safetensors"]       # the Turbo file is the roster's, LT2's cache is the registry's
    assert not any(u["name"] == "lora-1.safetensors" for u in r.unlisted_files())
    assert L.model_base("klein-4b") == "klein-4b" == L.model_base("klein-base-4b") and L.model_base("klein-9b-kv") == "klein-9b" == L.model_base("klein-base-9b")
    assert L.model_base("nope") is None
    opts = L.lora_options(r, "klein-4b", "full")
    assert [o["id"] for o in opts] == ["file:e16/mara.safetensors", "file:own.safetensors"]
    assert all(o["fits"] and o["source"] == "file" and o["base"] is None and "family not declared" in o["why"] for o in opts)
    assert "flux2-turbo-lora" not in {o["id"] for o in L.lora_options(r, "flux2-dev", "full")}        # the toggle's LoRA is not a slot
    assert all(not o["fits"] and "open variant" in o["why"] for o in L.lora_options(r, "klein-4b", "open"))
    assert L.lora_name(r, "file:e16/mara.safetensors") == "e16/mara.safetensors" and L.lora_name(r, "flux2-turbo-lora") == "Flux2TurboComfyv2.safetensors"
    with pytest.raises(FileNotFoundError):
        L.lora_name(r, "file:e16/gone.safetensors")


def test_roster_lora_fit_and_the_check(models_tree: Path, monkeypatch: pytest.MonkeyPatch):
    _lora_tree(models_tree)
    e = RosterEntry(id="test-k9-lora", name="k9.safetensors", folder="loras", family="klein", role="lora", license="apache-2.0", variants=["full", "open"], base="klein-9b")
    monkeypatch.setattr(L, "ROSTER", [*ROSTER, e])
    monkeypatch.setattr("loom2.roster.ROSTER", [*ROSTER, e])
    monkeypatch.setitem(ROSTER_BY_ID, e.id, e)
    (models_tree / "loras" / "k9.safetensors").write_bytes(b"x")
    r = Roster(models_tree).scan()
    for9 = {o["id"]: o for o in L.lora_options(r, "klein-9b", "full")}
    assert for9["test-k9-lora"]["fits"] and for9["test-k9-lora"]["source"] == "roster" and for9["test-k9-lora"]["health"] == "present"
    for4 = {o["id"]: o for o in L.lora_options(r, "klein-4b", "full")}
    assert not for4["test-k9-lora"]["fits"] and for4["test-k9-lora"]["why"] == "trained for Klein 9B"
    assert "k9.safetensors" not in {f["name"] for f in r.lora_files()}                              # claimed by the roster now
    ok = [LoraRef(model_id="test-k9-lora", strength=0.8), LoraRef(model_id="file:e16/mara.safetensors")]
    L.check_loras(r, ok, "klein-9b", "full")
    L.check_loras(r, ok, "klein-base-9b", "full")
    cases = [
        ([LoraRef(model_id="test-k9-lora")], "klein-4b", "full", "trained for Klein 9B; this job runs Klein 4B"),
        ([LoraRef(model_id="flux2-turbo-lora")], "flux2-dev", "full", "the Turbo toggle"),
        ([LoraRef(model_id="refcontrol-v2-poses")], "klein-base-9b", "full", "the Stage pose method"),
        ([LoraRef(model_id="file:e16/mara.safetensors")] * 2, "klein-4b", "full", "in two slots"),
        ([LoraRef(model_id=f"file:own.safetensors")] + [LoraRef(model_id=f"file:{i}.safetensors") for i in range(4)], "klein-4b", "full", "at most 4 slots"),
        ([LoraRef(model_id="nope")], "klein-4b", "full", "unknown model id"),
        ([LoraRef(model_id="klein-4b")], "klein-4b", "full", "unknown model id"),                    # a transformer is not a LoRA
        ([LoraRef(model_id="file:e16/mara.safetensors")], "klein-4b", "open", "open variant"),
    ]
    for refs, mid, variant, why in cases:
        with pytest.raises(ValueError, match=why):
            L.check_loras(r, refs, mid, variant)
    with pytest.raises(FileNotFoundError):
        L.check_loras(r, [LoraRef(model_id="file:e16/gone.safetensors")], "klein-4b", "full")
    with pytest.raises(ValidationError):
        LoraRef(model_id="file:own.safetensors", strength=3.0)                                        # 0–2 by the schema


# ---- the chain in the graphs ----------------------------------------------------------------------------------------------------
def test_chain_after_the_preset_lora_in_t2i_i2i_inpaint(tmp_path: Path, object_info: dict):
    pr = _pin_review()
    roster = pr.full_roster(tmp_path)
    _lora_tree(roster.models_root)
    roster.scan()
    oi = json.loads(json.dumps(object_info))
    added = list_loras(oi, roster.models_root)                                                          # the engine lists the folder with the OS separator
    assert os.sep.join(["e16", "mara.safetensors"]) in added and "own.safetensors" in added
    slots = [LoraRef(model_id="file:e16/mara.safetensors", strength=0.7), LoraRef(model_id="file:own.safetensors")]
    seen = set()
    for name, recipe, inputs in pr.recipes():
        if name not in ("t2i dev turbo", "i2i refine", "inpaint fill"):
            continue
        recipe = recipe.model_copy(update={"loras": slots})
        c = compile_recipe(recipe, roster, oi, 1, "loom2/lt1", ref_files=inputs.get("refs"), inputs=inputs)
        assert c.problems == [], (name, c.problems)
        ids = [k for k, n in c.graph.items() if n["class_type"] == "LoraLoaderModelOnly"]
        nodes = [c.graph[k] for k in ids]
        names = [n["inputs"]["lora_name"].replace("\\", "/") for n in nodes]
        mara, own = ids[names.index("e16/mara.safetensors")], ids[names.index("own.safetensors")]
        if name == "t2i dev turbo":
            assert names[0] == "Flux2TurboComfyv2.safetensors" and c.graph[mara]["inputs"]["model"] == [ids[0], 0], name   # the toggle's LoRA first, the slots after it
        assert c.graph[mara]["inputs"]["strength_model"] == 0.7 and c.graph[own]["inputs"]["model"] == [mara, 0], name   # chained in slot order …
        consumers = [k for k, n in c.graph.items() if n["inputs"].get("model") == [own, 0]]
        assert consumers and c.graph[consumers[0]]["class_type"] != "LoraLoaderModelOnly", name                   # … and the last one feeds the sampler / guider
        assert c.summary["loras"] == [{"model_id": "file:e16/mara.safetensors", "strength": 0.7, "lora_name": "e16/mara.safetensors"},
                                      {"model_id": "file:own.safetensors", "strength": 1.0, "lora_name": "own.safetensors"}], name
        seen.add(name)
    assert seen == {"t2i dev turbo", "i2i refine", "inpaint fill"}


# ---- the route --------------------------------------------------------------------------------------------------------------------
def test_loras_route(tmp_path: Path):
    state, models = tmp_path / "state", tmp_path / "models"
    _lora_tree(models)
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(models),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        r = cl.get("/loras", params={"model_id": "klein-4b"}, headers=H)
        assert r.status_code == 200
        body = r.json()
        assert body["base"] == "klein-4b" and body["max_slots"] == 4 and [o["id"] for o in body["items"]] == ["file:e16/mara.safetensors", "file:own.safetensors"]
        assert body["items"][0]["strength"] == 1.0 and body["items"][0]["fits"] is True
        assert cl.get("/loras", params={"model_id": "nope"}, headers=H).status_code == 422
        # the submission gate answers 422 with the sentence
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "L", "size_cap_gb": 10}, headers=H)
        bad = {"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_mode": "text", "prompt_text": "x", "seeds": [1], "width": 64, "height": 64,
                          "loras": [{"model_id": "flux2-turbo-lora", "strength": 1.0}]}, "stage": False}
        r = cl.post("/jobs", json=bad, headers=H)
        assert r.status_code == 422 and "Turbo toggle" in r.json()["detail"]


# ---- a job on the fake engine -----------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_job_with_a_slot_records_it(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        lora = tmp_path / "models" / "loras" / "e16" / "mara.safetensors"
        lora.parent.mkdir(parents=True, exist_ok=True)
        lora.write_bytes(b"x" * 16)
        rig.roster.scan()
        rig.queue.load()
        await rig.queue.start()
        mid = _t2i_model(rig.roster)
        base = {"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "a courier", "seeds": [3], "width": 64, "height": 64}
        for refs, why in ((["file:e16/nope.safetensors"], "not in a loras folder"), (["flux2-turbo-lora"], "Turbo toggle"), (["file:e16/mara.safetensors"] * 2, "in two slots")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit({**base, "loras": [{"model_id": m, "strength": 1.0} for m in refs]})
        await rig.queue.object_info_fresh()                               # the queue's cached listing predates the file …
        list_loras(rig.fake.object_info, tmp_path / "models")             # … the engine lists it now: finalize refreshes before the contract check
        job = rig.queue.submit({**base, "loras": [{"model_id": "file:e16/mara.safetensors", "strength": 0.7}]})[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        assert done.result["compiled"]["loras"] == [{"model_id": "file:e16/mara.safetensors", "strength": 0.7, "lora_name": "e16/mara.safetensors"}]
        g = rig.fake.prompts[-1]["graph"]
        node = next(n for n in g.values() if n["class_type"] == "LoraLoaderModelOnly" and n["inputs"]["strength_model"] == 0.7)
        assert node["inputs"]["lora_name"] == os.sep.join(["e16", "mara.safetensors"])     # resolve_names handed over the engine's own spelling
        a = rig.catalogue.get(done.result["asset_ids"][0])
        assert a.params["recipe"]["loras"] == [{"model_id": "file:e16/mara.safetensors", "strength": 0.7}]
    finally:
        await rig.close()
