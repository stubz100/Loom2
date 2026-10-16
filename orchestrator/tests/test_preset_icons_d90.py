"""D90 (02 §6.3): the preset swatch pack — app state, not the project. The key, the index round trip (and a torn index moved aside),
make (one staged t2i job per item on the variant's swatch model, origin `generate / swatch`, 409 without a project), the finisher storing
the first result under the key against the fake engine, the file route and delete."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import preset_icons
from loom2.api import create_app
from loom2.config import AppState
from loom2.models import registry
from loom2.preset_icons import PresetIconStore, icon_key, swatch_recipe

from test_lifecycle import Rig


def _png(p: Path, size=(512, 512), colour=(200, 80, 40)) -> Path:
    Image.new("RGB", size, colour).save(p)
    return p


def _client(tmp_path: Path, variant: str = "full") -> TestClient:
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": variant})
    return TestClient(create_app(state))


def test_the_key_is_sha1_of_field_newline_value():
    assert icon_key("lighting", "golden hour") == hashlib.sha1("lighting\ngolden hour".encode("utf-8")).hexdigest()[:16]
    assert icon_key("lighting", "golden hour") != icon_key("mood", "golden hour") != icon_key("lighting", "golden hour ")   # as given, no trimming
    assert preset_icons.KEY_RE.match(icon_key("style", "ukiyo-e, ink wash — 浮世絵"))


def test_the_index_round_trip_and_a_torn_index(tmp_path: Path):
    store = PresetIconStore(tmp_path)
    assert store.list() == []
    a = store.store_from("lighting", "golden hour", _png(tmp_path / "a.png", (768, 512)), model_id="m", seed=9, asset_id="ast_1")
    b = store.store_from("mood", "eerie", _png(tmp_path / "b.png"))
    with Image.open(store.path(a.key)) as im:
        assert im.format == "WEBP" and im.size[0] == preset_icons.ICON_PX and im.size[1] < preset_icons.ICON_PX   # the long side
    data = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == preset_icons.PRESET_ICONS_SCHEMA_VERSION and set(data["items"]) == {a.key, b.key}
    assert [(i.field, i.value, i.seed, i.asset_id) for i in store.list()] == [("lighting", "golden hour", 9, "ast_1"), ("mood", "eerie", None, None)]
    again = store.store_from("lighting", "golden hour", _png(tmp_path / "c.png"))          # re-made: the same key, a newer record
    assert again.key == a.key and len(store.list()) == 2 and store.list()[0].seed is None
    store.path(b.key).unlink()                                                            # a missing file is not listed
    assert [i.key for i in store.list()] == [a.key]
    assert store.delete(a.key) and not store.path(a.key).exists() and store.list() == []
    assert not store.delete(a.key)
    with pytest.raises(KeyError):
        store.path("../../etc")
    store.index_path.write_text("{torn", encoding="utf-8")
    assert store.list() == [] and list(store.dir.glob("index.json.corrupt-*"))           # moved aside, never trusted


@pytest.mark.parametrize("variant", ["full", "open"])
def test_make_plans_one_staged_job_per_item(tmp_path: Path, variant: str):
    with _client(tmp_path, variant) as c:
        body = {"items": [{"field": "lighting", "value": "golden hour"}, {"field": "mood", "value": "eerie"}, {"field": "my-snippet", "value": "wet asphalt"}]}
        r = c.post("/preset-icons/make", json=body)
        assert r.status_code == 409 and "open a project" in r.json()["detail"]
        assert c.get("/preset-icons").json() == {"items": []}                             # app state: listed without a project
        assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "P"}).status_code == 200
        c.post("/queue/pause")
        swatch = c.get("/capabilities").json()["defaults"]["swatch"]
        assert swatch == registry.default_model("swatch", variant) and "open" in registry.ROSTER_BY_ID[swatch].variants   # D26: both variants
        r = c.post("/preset-icons/make", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["batch_id"] and len(out["items"]) == len(out["jobs"]) == 3
        for it, job, asked in zip(out["items"], out["jobs"], body["items"]):
            assert it["key"] == icon_key(asked["field"], asked["value"]) and it["job_id"] == job["id"]
            assert job["status"] == "staged" and job["batch_id"] == out["batch_id"] and job["seed"] == preset_icons.SWATCH_SEED
            assert job["origin"] == {"suite": "generate", "surface": "swatch", "ref": it["key"], "payload": {"key": it["key"], **asked}}
            rec = job["recipe"]
            assert rec["kind"] == "t2i" and rec["model_id"] == swatch and rec["width"] == rec["height"] == preset_icons.SWATCH_PX
            assert asked["value"] in rec["prompt_text"]
        assert out["jobs"][0]["recipe"]["prompt_text"] == "a simple still life of a white sphere on a table, golden hour"
        assert out["jobs"][2]["recipe"]["prompt_text"] == "wet asphalt"                     # an unknown field: the value alone
        queued = c.post("/preset-icons/make", json={"items": [{"field": "style", "value": "ink wash"}], "stage": False, "seed": 0}).json()
        assert queued["batch_id"] is None and queued["jobs"][0]["status"] == "queued" and queued["jobs"][0]["seed"] > 0   # 0 = a random seed
        assert c.post("/preset-icons/make", json={"items": []}).status_code == 422
        assert c.post("/preset-icons/make", json={"items": [{"field": "mood", "value": ""}]}).status_code == 422
        # D90: Settings › Samples — a changed scene reaches the next swatch job; a scene without {value} gets it; blank is the default again
        s = c.put("/settings", json={"samples": {"swatch_prompts": {"mood": "a quiet harbour at {value}", "lighting": "a chair"}}}).json()["samples"]
        assert s["swatch_prompts"]["mood"] == "a quiet harbour at {value}" and s["swatch_prompts"]["lighting"] == "a chair, {value}"
        assert s["swatch_prompts"]["style"] == "a lighthouse on a cliff, {value}" and s["style_prompt"].startswith("a woman in a long coat")
        made = c.post("/preset-icons/make", json={"items": [{"field": "mood", "value": "dusk"}, {"field": "lighting", "value": "moonlight"}]}).json()
        assert [j["recipe"]["prompt_text"] for j in made["jobs"]] == ["a quiet harbour at dusk", "a chair, moonlight"]
        s = c.put("/settings", json={"samples": {"style_prompt": "  ", "swatch_prompts": {"mood": ""}}}).json()["samples"]
        assert s["swatch_prompts"]["mood"] == "an empty street corner, {value} mood" and s["style_prompt"].startswith("a woman in a long coat")


def test_file_and_delete_routes(tmp_path: Path):
    with _client(tmp_path) as c:
        st = c.app.state.services.app
        rec = PresetIconStore(st.state_dir).store_from("background", "foggy moor", _png(tmp_path / "x.png"))
        assert c.get("/preset-icons").json()["items"][0] | {"updated_at": ""} == {"key": rec.key, "field": "background", "value": "foggy moor",
                                                                              "updated_at": "", "model_id": None, "seed": None, "asset_id": None}
        f = c.get(f"/preset-icons/{rec.key}/file")
        assert f.status_code == 200 and f.headers["content-type"] == "image/webp" and "no-cache" in f.headers["cache-control"]
        bare = TestClient(c.app, headers={})
        assert bare.get(f"/preset-icons/{rec.key}/file").status_code == 401
        assert bare.get(f"/preset-icons/{rec.key}/file", params={"k": st.media_key}).status_code == 200   # D67: a media GET
        assert c.get("/preset-icons/nothex/file").status_code == 404 and c.get("/preset-icons/0123456789abcdef/file").status_code == 404
        assert c.delete(f"/preset-icons/{rec.key}").json() == {"deleted": rec.key}
        assert c.get("/preset-icons").json() == {"items": []} and c.delete(f"/preset-icons/{rec.key}").status_code == 404
        assert any(f["type"] == "preset_icons.changed" and f["data"] == {"keys": [rec.key], "deleted": True} for f in c.app.state.services.hub.recent)


async def test_the_finisher_stores_the_swatch(tmp_path: Path, object_info):
    swatch = registry.default_model("swatch", "full")
    spec = registry.SPECS[swatch]
    models = tmp_path / "models"
    for rid in (swatch, spec.roles.te.default, spec.roles.vae):                     # the swatch model's weights in the fake tree
        e = registry.ROSTER_BY_ID[rid]
        p = models / e.folder / e.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.load()
        await rig.queue.start()
        from loom2.origin import JobOrigin
        key = icon_key("lighting", "candlelight")
        origin = JobOrigin(suite="generate", surface="swatch", ref=key, payload={"key": key, "field": "lighting", "value": "candlelight"})
        job = rig.queue.submit(swatch_recipe("lighting", "candlelight", "full", 5), origin=origin)[0]
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        assert j.result["preset_icon"] == key
        store = PresetIconStore(rig.state)
        [icon] = store.list()
        assert (icon.key, icon.field, icon.value, icon.model_id, icon.seed, icon.asset_id) == (key, "lighting", "candlelight", swatch, 5, j.result["asset_ids"][0])
        with Image.open(store.path(key)) as im:
            assert im.format == "WEBP" and max(im.size) <= preset_icons.ICON_PX
        a = rig.catalogue.get(icon.asset_id)                                          # the result stays in the Catalogue with its lineage
        assert a and a.origin and a.origin.surface == "swatch" and rig.catalogue.abs_path(a).is_file()
        assert any(f["type"] == "preset_icons.changed" and f["data"]["keys"] == [key] for f in rig.hub.recent)
    finally:
        await rig.close()
