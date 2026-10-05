"""M2 catalogue: filters, FTS, groups, counts, lineage roots, trash/restore/purge, collections, PNG metadata."""
import json
from pathlib import Path

from PIL import Image, PngImagePlugin

from loom2.catalogue import AssetQuery, Catalogue
from loom2.tools.pngmeta import parse_image_metadata
from loom2.workspace import Workspace


def _png(path: Path, w: int = 64, h: int = 32, text: dict | None = None) -> Path:
    im = Image.new("RGB", (w, h), (10, 20, 30))
    info = PngImagePlugin.PngInfo()
    for k, v in (text or {}).items():
        info.add_text(k, v)
    im.save(path, pnginfo=info)
    return path


def _cat(tmp_path: Path) -> Catalogue:
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    return Catalogue(ws, [32], session_id="ses_now")


def _seed(cat: Catalogue, tmp_path: Path) -> dict:
    a = cat.ingest_file(_png(tmp_path / "a.png"), job_id="job_a", batch_id="bat_1", model_id="flux2-dev-fp8mixed", seed=1, prompt_text="rainy alley neon sign", tags=["alley", "night"], state="keep", rating=5)
    b = cat.ingest_file(_png(tmp_path / "b.png"), job_id="job_a", batch_id="bat_1", model_id="flux2-dev-fp8mixed", seed=2, prompt_json={"scene": "harbour market", "mood": "dawn"}, state="reject")
    c = cat.ingest_file(_png(tmp_path / "c.png", 32, 64), job_id="job_c", batch_id=None, model_id="klein-9b", seed=3, prompt_text="portrait grief", parents=[a.id], suite="inpaint", rating=3)
    d = cat.ingest_file(_png(tmp_path / "d.png", 48, 48), suite="import", prompt_text="imported reference", session_id="ses_old")
    return {"a": a, "b": b, "c": c, "d": d}


def test_filters_sort_and_fts(tmp_path: Path):
    cat = _cat(tmp_path)
    x = _seed(cat, tmp_path)
    assert cat.list(AssetQuery()).total == 4
    assert [i.id for i in cat.list(AssetQuery(state="keep")).items] == [x["a"].id]
    assert [i.id for i in cat.list(AssetQuery(search="harbour")).items] == [x["b"].id]           # JSON prompt is searchable
    assert [i.id for i in cat.list(AssetQuery(search="rain alley")).items] == [x["a"].id]        # prefix tokens, ANDed
    assert cat.list(AssetQuery(search='"; DROP TABLE assets; --')).items == []                   # neutralised
    assert [i.id for i in cat.list(AssetQuery(tags_any=["night"])).items] == [x["a"].id]
    assert [i.id for i in cat.list(AssetQuery(aspect="portrait")).items] == [x["c"].id]
    assert [i.id for i in cat.list(AssetQuery(aspect="square")).items] == [x["d"].id]
    assert [i.id for i in cat.list(AssetQuery(has_children=True)).items] == [x["a"].id]
    assert [i.id for i in cat.list(AssetQuery(folder="imported")).items] == [x["d"].id]
    assert [i.id for i in cat.list(AssetQuery(folder="last_session")).items] == [x["d"].id]      # the other session
    assert [i.id for i in cat.list(AssetQuery(sort="rating_desc")).items][:2] == [x["a"].id, x["c"].id]
    assert [i.model_id for i in cat.list(AssetQuery(sort="model")).items][0] == "flux2-dev-fp8mixed"
    page1 = cat.list(AssetQuery(limit=3))
    assert len(page1.items) == 3 and page1.next_cursor
    page2 = cat.list(AssetQuery(limit=3, cursor=page1.next_cursor))
    assert len(page2.items) == 1 and page2.next_cursor is None and page2.total is None
    counts = cat.counts()
    assert counts["all"] == 4 and counts["imported"] == 1 and counts["rejected"] == 1 and counts["trash"] == 0 and counts["last_session"] == 1
    assert cat.tags()[0] == {"tag": "alley", "count": 1} or {"tag": "night", "count": 1} in cat.tags()
    cat.close()


def test_groups_and_lineage_roots(tmp_path: Path):
    cat = _cat(tmp_path)
    x = _seed(cat, tmp_path)
    assert x["c"].root_id == x["a"].id and x["a"].root_id == x["a"].id
    batches = cat.groups(AssetQuery(group="batch"))
    keys = {g.key: g for g in batches}
    assert keys["bat_1"].count == 2 and keys["bat_1"].model_id == "flux2-dev-fp8mixed" and keys["bat_1"].cover_id == x["a"].id   # best rated cover
    assert keys["job_c"].count == 1 and keys[x["d"].id].count == 1                                                            # job / id fallbacks
    lineage = {g.key: g for g in cat.groups(AssetQuery(group="lineage"))}
    assert lineage[x["a"].id].count == 2
    models = {g.key: g.count for g in cat.groups(AssetQuery(group="model"))}
    assert models == {"flux2-dev-fp8mixed": 2, "klein-9b": 1, "": 1}
    tree = cat.lineage_tree(x["a"].id)
    assert {i["id"] for i in tree["items"]} == {x["a"].id, x["c"].id} and tree["edges"][0]["from_id"] == x["a"].id
    assert cat.groups(AssetQuery(group="none")) == []
    # the items of a group are fetched with the same key expression the headers use (single-job batches key on job_id)
    assert [i.id for i in cat.list(AssetQuery(group_by="batch", group_key="job_c")).items] == [x["c"].id]
    assert len(cat.list(AssetQuery(group_by="batch", group_key="bat_1")).items) == 2
    assert [i.id for i in cat.list(AssetQuery(group_by="model", group_key="")).items] == [x["d"].id]
    cat.close()


def test_trash_restore_purge(tmp_path: Path):
    cat = _cat(tmp_path)
    x = _seed(cat, tmp_path)
    cat.trash([x["a"].id, x["b"].id])
    assert cat.list(AssetQuery()).total == 2 and cat.list(AssetQuery(folder="trash")).total == 2
    assert cat.get(x["a"].id).trashed_at and json.loads(cat.manifest_path(x["a"]).read_text(encoding="utf-8"))["trashed_at"]
    cat.restore([x["a"].id])
    assert cat.list(AssetQuery()).total == 3 and cat.get(x["a"].id).trashed_at is None
    assert cat.purge([x["a"].id]) == []                      # not trashed → untouched
    gone = cat.purge(older_than_days=0)
    assert gone == [x["b"].id] and not cat.abs_path(x["b"]).exists() and cat.get(x["b"].id) is None
    assert cat.list(AssetQuery(folder="trash")).total == 0
    cat.close()


def test_collections(tmp_path: Path):
    cat = _cat(tmp_path)
    x = _seed(cat, tmp_path)
    manual = cat.collection_create("Hero shots")
    assert cat.collection_add(manual.id, [x["a"].id, x["c"].id]) == 2
    assert {i.id for i in cat.list(AssetQuery(collection_id=manual.id)).items} == {x["a"].id, x["c"].id}
    smart = cat.collection_create("Rated", kind="smart", filter_={"rating_min": 3})
    cols = {c.id: c for c in cat.collections()}
    assert cols[manual.id].count == 2 and cols[smart.id].count == 2 and cols[smart.id].kind == "smart"
    frozen = cat.collection_update(smart.id, kind="manual")
    assert frozen and frozen.kind == "manual" and frozen.count == 2 and frozen.filter is None
    assert cat.collection_remove(manual.id, [x["a"].id]) == 1
    assert cat.collection_update(manual.id, name="Heroes").name == "Heroes"
    assert cat.collection_delete(manual.id) and not cat.collection_delete(manual.id)
    # the index rebuild keeps collections and lineage roots
    assert cat.rebuild() == 4 and cat.get(x["c"].id).root_id == x["a"].id and len(cat.collections()) == 1
    cat.close()


def test_png_metadata(tmp_path: Path):
    comfy = {"3": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 20}}, "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat on a roof"}},
             "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}, "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors"}}}
    p = _png(tmp_path / "comfy.png", text={"prompt": json.dumps(comfy), "workflow": "{}"})
    m = parse_image_metadata(p)
    assert m["source"] == "comfyui" and m["prompt_text"] == "a cat on a roof" and m["seed"] == 42 and m["steps"] == 20 and m["model"].startswith("flux2_dev")
    a1111 = "masterpiece, a dog\nNegative prompt: blurry\nSteps: 30, Sampler: Euler a, CFG scale: 7, Seed: 1234, Size: 512x768, Model: dreamshaper"
    m = parse_image_metadata(_png(tmp_path / "a1111.png", text={"parameters": a1111}))
    assert m["source"] == "a1111" and m["prompt_text"] == "masterpiece, a dog" and m["negative"] == "blurry" and m["seed"] == 1234 and m["steps"] == 30 and m["model"] == "dreamshaper"
    assert parse_image_metadata(_png(tmp_path / "plain.png")) == {"w": 64, "h": 32}
    assert parse_image_metadata(tmp_path / "missing.png") == {}


def test_stale_index_is_rebuilt(tmp_path: Path):
    import sqlite3
    cat = _cat(tmp_path)
    x = _seed(cat, tmp_path)
    cat.close()
    db = cat.ws.catalogue_db
    con = sqlite3.connect(str(db))
    con.executescript("DROP TABLE assets; DROP TABLE meta; CREATE TABLE assets (id TEXT PRIMARY KEY, kind TEXT, path TEXT, manifest TEXT);")
    con.execute("INSERT INTO assets VALUES ('old', 'image', 'x', '{}')")
    con.commit(); con.close()
    cat2 = Catalogue(cat.ws, [32], session_id="ses_now")        # old columns → drop + rebuild from sidecars
    assert cat2.count() == 4 and cat2.get(x["c"].id).root_id == x["a"].id and cat2.get("old") is None
    cat2.close()
