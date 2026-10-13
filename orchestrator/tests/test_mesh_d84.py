"""P18 (D79 / D84): image → mesh props — the frozen Pixal3D graph compiles against the engine's contract with the roster's names in its loaders,
the recipe plans as a background job with E14's warm and cold figures, the weights are the five files (DINOv3 keeps it full-only), the finisher
makes a `mesh` asset with lineage and licences, `/capabilities.mesh` describes it and the Models suite's unlisted view keeps Hunyuan3D out."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.pipeline import placeholder_inputs, plan, preview_problems  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import ImageToMesh, parse_recipe, warm_group  # noqa: E402
from loom2.roster import ROSTER_BY_ID, ignore_reason  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402

IMG = "alley-rain_s20261004.png"


def test_recipe_and_registry():
    r = parse_recipe({"kind": "image_to_mesh", "asset_id": "ast_src"})
    assert isinstance(r, ImageToMesh) and r.model_id == "pixal3d-int8" and r.resolution == 1024 and r.faces == 50000
    assert registry.default_model("mesh") == "pixal3d-int8" and [s.id for s in registry.mesh_specs()] == ["pixal3d-int8"]
    assert warm_group(r) == "pixal3d-int8"
    with pytest.raises(ValueError):
        parse_recipe({"kind": "image_to_mesh", "asset_id": "a", "resolution": 512})
    assert set(graphs.recipe_weights(r)) == {"pixal3d-int8", "trellis2-shape-vae", "trellis2-texture-vae", "dinov3-l", "moge2-vitl", "birefnet"}
    assert ROSTER_BY_ID["dinov3-l"].variants == ["full"] and ROSTER_BY_ID["pixal3d-int8"].variants == ["full"] and "open" in ROSTER_BY_ID["moge2-vitl"].variants
    assert not registry.offered(registry.get("pixal3d-int8"), "open")                        # D17 / D26: full only while DINOv3 is
    assert ignore_reason("hunyuan3d-dit-v2-0.safetensors") and ignore_reason("flux-2-klein-9b.safetensors") is None


def test_frozen_graph_compiles_against_the_engine(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    fx = graphs.mesh_graph_fixture()
    assert len(fx["graph"]) >= 35 and set(fx["roles"].values()) >= {"model", "shape_vae", "texture_vae", "dino", "moge", "matte", "image", "decimate", "upsample", "save", "final_mesh"}
    for k, v in fx["graph"].items():                                                            # D65: no file names in the fixture
        for name in ("unet_name", "vae_name", "clip_name", "model_name", "bg_removal_name", "image"):
            if name in v["inputs"] and v["class_type"] in ("UNETLoader", "VAELoader", "CLIPVisionLoader", "LoadMoGeModel", "LoadBackgroundRemovalModel", "LoadImage"):
                assert v["inputs"][name] == "", (k, name)
    r = ImageToMesh(asset_id="ast_src", faces=40000, resolution=1024)
    c = graphs.compile_recipe(r, roster, object_info, 7, "loom2/mesh", inputs={"image": IMG})
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    for want in ("Pixal3DConditioning", "Trellis2ShapeStage", "Trellis2UpsampleStage", "Trellis2TextureStage", "DecimateMesh", "Save3DAdvanced", "RenderMesh", "SaveImage", "MoGeInference"):
        assert want in kinds, want
    assert "ComfySwitchNode" not in kinds and "PreviewImage" not in kinds and "Trellis2Conditioning" not in kinds
    loaders = {n["class_type"]: n["inputs"] for n in c.graph.values() if n["class_type"] in ("UNETLoader", "CLIPVisionLoader", "LoadMoGeModel", "LoadBackgroundRemovalModel")}
    assert loaders["UNETLoader"]["unet_name"].endswith("pixal3d_int8_convrot.safetensors") and loaders["CLIPVisionLoader"]["clip_name"].endswith("dino_v3_L_naf_fp32.safetensors")
    vaes = sorted(n["inputs"]["vae_name"] for n in c.graph.values() if n["class_type"] == "VAELoader")
    assert [v.split("/")[-1].split("\\")[-1] for v in vaes] == ["trellis_2_shape_vae_bf16.safetensors", "trellis_2_texture_vae_bf16.safetensors"]
    dec = next(n for n in c.graph.values() if n["class_type"] == "DecimateMesh")
    assert dec["inputs"]["target_face_count"] == 40000
    assert all(n["inputs"]["seed"] == 7 for n in c.graph.values() if n["class_type"] == "KSampler")
    assert next(n for n in c.graph.values() if n["class_type"] == "LoadImage")["inputs"]["image"] == IMG
    assert c.graph[c.output_node]["class_type"] == "Save3DAdvanced" and c.graph[c.output_node]["inputs"]["filename_prefix"] == "loom2/mesh"
    assert c.graph["901"]["inputs"]["filename_prefix"] == "loom2/mesh_view" and c.summary["faces"] == 40000 and c.summary["resolution"] == 1024
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(r, roster, object_info, 7, "x", inputs={})


def test_plan_preview_and_capabilities(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    r = ImageToMesh(asset_id="ast_src")
    p = plan(r)
    assert p.kind == "image_to_mesh" and p.engine and p.needs == ["source"] and p.warm_group == "pixal3d-int8"
    assert p.estimate["seconds"] == 243.0 and p.estimate["cold_seconds"] == 361.0 and p.vram_gb >= 14
    assert placeholder_inputs(r, object_info)["image"] and preview_problems(r, roster, object_info) == []
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    for variant in ("full", "open"):
        state = tmp_path / variant / "state"
        AppState(state).update_settings({"models_root": str(tmp_path / variant / "models"), "mounted_model_trees": [], "variant": variant})
        _pin_review().full_roster(tmp_path / variant / "models")
        with TestClient(create_app(state)) as cl:
            mc = cl.get("/capabilities").json()["mesh"]
            if variant == "full":
                assert mc["model_id"] == "pixal3d-int8" and mc["seconds"] == 243.0 and mc["cold_seconds"] == 361.0 and mc["health"] != "missing"
                assert mc["licences"]["dinov3-l"].startswith("dinov3") and mc["resolutions"] == [1024, 1536]
                pv = cl.post("/recipes/preview", json={"recipe": {"kind": "image_to_mesh", "asset_id": "ast_x"}}).json()
                assert pv["kind"] == "image_to_mesh" and pv["estimate"]["seconds"] == 243.0 and "dinov3-l" in pv["weights"]
            else:
                assert mc["model_id"] is None and mc["health"] == "unavailable" and "DINOv3" in (mc["why"] or "")
            u = cl.get("/models/unlisted").json()
            assert "ignored" in u and isinstance(u["ignored"], list)


def test_mesh_finisher_makes_a_mesh_asset(tmp_path: Path):
    """The fake engine's GLB through the real finisher: a `mesh` asset with lineage, licences and a thumbnail from the view."""
    from fake_comfy import minimal_glb
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    from PIL import Image
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32], session_id="ses_test")
    glb = tmp_path / "m_00001_.glb"
    glb.write_bytes(minimal_glb())
    assert glb.read_bytes()[:4] == b"glTF"
    view = tmp_path / "m_view_00001_.png"
    Image.new("RGB", (64, 64), (90, 90, 100)).save(view)
    rec = cat.ingest_file(glb, kind="mesh", move=True, suite="generate", model_id="pixal3d-int8", params={"licences": {"dinov3-l": "dinov3 (Meta custom)"}, "format": "glb"},
                          parents=[], lineage_kind="image-to-mesh")
    rec = cat.make_thumbs(rec, view)
    got = cat.get(rec.id)
    assert got is not None and got.kind == "mesh" and got.path.endswith(".glb") and got.thumb_status == "done" and got.params["licences"]["dinov3-l"].startswith("dinov3")


async def test_mesh_job_end_to_end_on_the_fake_engine(tmp_path: Path, object_info: dict, monkeypatch):
    """The whole path the Catalogue's "Make a 3D prop…" takes: submit → upload → the frozen graph → the fake engine's GLB and view → a mesh asset."""
    import io
    import test_lifecycle
    from PIL import Image
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))      # every roster file, Pixal3D's included
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        src = tmp_path / "photo.png"
        Image.new("RGB", (96, 64), (200, 120, 40)).save(src)
        photo = rig.catalogue.ingest_file(src, kind="image", move=False, suite="generate")
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "image_to_mesh", "asset_id": photo.id}, origin={"suite": "catalogue", "surface": "mesh", "ref": photo.id})[0]   # type: ignore[arg-type]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a and a.kind == "mesh" and a.path.endswith(".glb") and a.lineage_kind == "image-to-mesh" and a.parents == [photo.id] and a.thumb_status == "done"
        assert a.params["licences"]["dinov3-l"].startswith("dinov3") and a.params["format"] == "glb" and rig.catalogue.abs_path(a).read_bytes()[:4] == b"glTF"
        assert not list((rig.state / "engine_out" / "loom2").glob("*.glb"))                            # moved into the project
    finally:
        await rig.close()


def test_output_collector_takes_the_glb_record_and_skips_the_bare_result():
    """The engine's history for Save3DAdvanced (rig 2026-10-13): a record under "3d" and a bare path list under "result"."""
    from loom2.engine.follow import EngineFollower
    hist = {"outputs": {"202": {"text": ["Faces: 6,188,984"]},
                        "322": {"result": ["loom2/job_x_00001.glb", None, []], "3d": [{"filename": "job_x_00001.glb", "subfolder": "loom2", "type": "output"}]},
                        "901": {"images": [{"filename": "job_x_view_00001_.png", "subfolder": "loom2", "type": "output"}]}}}
    files = EngineFollower.outputs(hist)
    assert files == [{"filename": "job_x_00001.glb", "subfolder": "loom2"}, {"filename": "job_x_view_00001_.png", "subfolder": "loom2"}]


def test_client_thumbnail_route(tmp_path: Path):
    """A PNG put on an asset becomes its thumbnails and the record says so; anything else is refused."""
    import io
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from PIL import Image
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "a.png"
        Image.new("RGB", (40, 30), (10, 20, 30)).save(src)
        a = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        buf = io.BytesIO()
        Image.new("RGB", (512, 512), (200, 180, 40)).save(buf, "PNG")
        r = cl.put(f"/assets/{a['id']}/thumbnail", content=buf.getvalue(), headers={**H, "Content-Type": "image/png"})
        assert r.status_code == 200, r.text
        assert r.json()["thumb_status"] == "done" and r.json()["params"]["thumb_source"] == "client"
        t = cl.get(f"/thumbs/{a['id']}/256", headers=H)
        assert t.status_code == 200
        with Image.open(io.BytesIO(t.content)) as im:
            assert im.size == (256, 256) and im.convert("RGB").getpixel((128, 128))[0] > 150        # the yellow view, not the dark photo
        assert cl.put(f"/assets/{a['id']}/thumbnail", content=b"not a png", headers=H).status_code == 400
        assert cl.put("/assets/ast_nope/thumbnail", content=buf.getvalue(), headers=H).status_code == 404
