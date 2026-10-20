"""D115: several recipes as one batch — `POST /jobs/batch` (Image's Expand ▶: one job per pose cell, each with its origin and cell)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_jobs_batch(tmp_path: Path):
    from e2e_setup import fake_models
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    models = state / "models"
    fake_models(models)                                                      # the fake tree: every roster weight present
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(models), "mounted_model_trees": []})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        model = cl.get("/capabilities", headers=H).json()["defaults"]["t2i"]        # the variant's own default (the open build offers no FLUX.2 dev)
        cells = [{"shot": "close-up", "angle": "front", "expression": "neutral"}, {"shot": "waist-up", "angle": "back", "expression": "smile"}]
        items = [{"recipe": {"kind": "t2i", "model_id": model, "prompt_mode": "text", "prompt_text": f"Mara. {c['shot']}, {c['angle']}, {c['expression']} expression.", "width": 512, "height": 512, "seeds": [0, 1]},
                  "origin": {"suite": "generate", "surface": "cast", "ref": "prf_m", "payload": {"version": "v1", "group_id": "grp_c", "cell": c}}} for c in cells]
        r = cl.post("/jobs/batch", json={"items": items, "stage": True}, headers=H)
        assert r.status_code == 200, r.text
        jobs = r.json()["jobs"]
        assert len(jobs) == 4 and len({j["batch_id"] for j in jobs}) == 1               # two seeds a cell, one batch for all
        assert all(j["status"] == "staged" for j in jobs)
        assert [j["origin"]["payload"]["cell"]["shot"] for j in jobs] == ["close-up", "close-up", "waist-up", "waist-up"]
        assert all(j["origin"]["surface"] == "cast" and j["origin"]["ref"] == "prf_m" for j in jobs)
        before = len(cl.get("/jobs", headers=H).json()["items"])
        bad = [items[0], {"recipe": {"kind": "t2i", "model_id": model, "prompt_mode": "text", "prompt_text": "x", "width": 7, "height": 7}, "origin": None}]
        r = cl.post("/jobs/batch", json={"items": bad}, headers=H)
        assert r.status_code == 422                                                      # a refused item refuses the submit …
        assert len(cl.get("/jobs", headers=H).json()["items"]) == before               # … and leaves no job behind (every item checked first)
        assert cl.post("/jobs/batch", json={"items": []}, headers=H).status_code == 422
