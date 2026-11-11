"""RS2 (D197 G2, proto02 03; Q16): an image → 3D job runs what its run form shows.

- the shell's and the prop model's routes take the form's settings (model, resolution, faces, seed), keep them on the version and queue the
  job with them; with no body they queue the version's kept settings, else the measured defaults (1024, 50 000, seed 0);
- the shell queued by itself after a fit (D183) runs the version's kept settings;
- a model the build does not offer is refused; /capabilities.mesh lists the offered models for the form's tiles.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import MeshSettings, ProfileVersion, mesh_recipe  # noqa: E402


def test_the_recipe_carries_the_versions_settings():
    v = ProfileVersion(id="v1", group_id="g")
    r = mesh_recipe(v, "ast_a", "full")
    assert (r["resolution"], r["faces"], r["seeds"], r["asset_id"]) == (1024, 50000, [0], "ast_a") and r["model_id"]
    v.mesh = MeshSettings(resolution=1536, faces=120000, seed=7)
    r = mesh_recipe(v, "ast_a", "full")
    assert (r["resolution"], r["faces"], r["seeds"]) == (1536, 120000, [7])
    v.mesh = MeshSettings(model_id="no-such-model")
    with pytest.raises(ValueError, match="makes no 3D model"):
        mesh_recipe(v, "ast_a", "full")
    with pytest.raises(ValueError, match="offered in this build"):
        mesh_recipe(ProfileVersion(id="v1", group_id="g"), "ast_a", "open")           # DINOv3 keeps Pixal3D full-only (D17 / D26)


def test_the_routes_keep_and_run_the_forms_settings(tmp_path: Path):
    from test_graph_parity_d64 import _pin_review
    from test_groups_d34 import _png
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        caps = cl.get("/capabilities").json()["mesh"]
        assert [m["id"] for m in caps["models"]] == [caps["model_id"]] and caps["faces_min"] == 2000        # one model today: one tile
        hero = app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        recipe = lambda jid: next(j for j in cl.get("/jobs").json()["items"] if j["id"] == jid)["recipe"]  # noqa: E731
        prop = cl.post("/story/profiles", json={"name": "Crate", "cls": "prop", "hero_asset_id": hero}).json()
        r = cl.post(f"/story/profiles/{prop['id']}/versions/v1/model")                                    # no body: the defaults
        assert r.status_code == 200, r.text
        got = recipe(r.json()["job_id"])
        assert (got["resolution"], got["faces"], got["seeds"]) == (1024, 50000, [0])
        r = cl.post(f"/story/profiles/{prop['id']}/versions/v1/model", json={"resolution": 1536, "faces": 90000, "seed": 3})
        assert r.status_code == 200, r.text
        got = recipe(r.json()["job_id"])
        assert (got["resolution"], got["faces"], got["seeds"]) == (1536, 90000, [3])
        kept = cl.get(f"/story/profiles/{prop['id']}").json()["versions"][0]["mesh"]
        assert (kept["resolution"], kept["faces"], kept["seed"]) == (1536, 90000, 3)                       # Q16: on the version
        r = cl.post(f"/story/profiles/{prop['id']}/versions/v1/model")                                    # no body again: what was kept
        assert recipe(r.json()["job_id"])["faces"] == 90000
        assert cl.post(f"/story/profiles/{prop['id']}/versions/v1/model", json={"faces": 10}).status_code == 422
        assert cl.post(f"/story/profiles/{prop['id']}/versions/v1/model", json={"model_id": "nope"}).status_code == 422
