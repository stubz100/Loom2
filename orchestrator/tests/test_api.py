"""API smoke test through the real lifespan, no engine: the engine python is pointed at a missing file so a
submitted job fails fast instead of starting ComfyUI."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    state = tmp_path / "state"
    app_state = AppState(state)
    app_state.update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1},
                               "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    return client, app.state.services.app.token


def test_api_flow(tmp_path: Path):
    client, token = _client(tmp_path)
    H = {"X-Loom-Token": token}
    with client:
        assert client.get("/health").json()["ok"] is True
        assert client.post("/project/close").status_code == 401                      # token gate
        assert client.get("/project").json() == {"open": False}
        assert client.get("/assets").status_code == 409                               # no project
        r = client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Smoke", "size_cap_gb": 10}, headers=H)
        assert r.status_code == 200 and r.json()["name"] == "Smoke"
        assert client.get("/projects").json()["last"].endswith("proj")
        caps = client.get("/capabilities").json()
        assert "t2i" in caps["recipes"] and "klein-4b" in caps["models"]                        # Klein 4B is in both variants (D26)
        assert ("flux2-dev-fp8mixed" in caps["models"]) == (caps["variant"] == "full")        # dev is non-commercial: full only
        models = client.get("/models").json()["items"]
        assert any(m["id"] == "klein-4b" and m["health"] == "missing" for m in models)
        # imports go straight into the catalogue with thumbnails
        png = tmp_path / "in.png"
        Image.new("RGB", (48, 48), (0, 120, 200)).save(png)
        r = client.post("/assets/import", json={"paths": [str(png)]}, headers=H)
        asset = r.json()["items"][0]
        assert asset["suite"] == "import" and asset["thumb_status"] == "done"
        assert client.get(f"/assets/{asset['id']}/file").status_code == 200
        assert client.get(f"/thumbs/{asset['id']}/256").headers["content-type"] == "image/webp"
        assert client.patch(f"/assets/{asset['id']}", json={"rating": 5}, headers=H).json()["rating"] == 5
        assert client.get("/assets", params={"search": "nothing"}).json()["items"] == []
        # queue: pause, submit, inspect, cancel
        assert client.post("/queue/pause", headers=H).json()["paused"] is True
        r = client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "a cat", "seeds": [3]}}, headers=H)
        job = r.json()["jobs"][0]
        assert job["status"] == "queued" and job["seed"] == 3
        assert client.post("/jobs", json={"recipe": {"kind": "bogus"}}, headers=H).status_code == 422
        assert client.get("/queue").json()["counts"] == {"queued": 1}
        assert client.post(f"/jobs/{job['id']}/cancel", headers=H).status_code == 200
        assert client.get(f"/jobs/{job['id']}").json()["status"] == "cancelled"
        assert client.delete(f"/jobs/{job['id']}", headers=H).status_code == 200
        # blobs are content addressed
        body = b"mask-bytes"
        import hashlib
        sha = hashlib.sha256(body).hexdigest()
        assert client.put(f"/blobs/{sha}", content=body, headers=H).json()["bytes"] == len(body)
        assert client.put(f"/blobs/{'0' * 64}", content=body, headers=H).status_code == 400
        assert client.get(f"/blobs/{sha}").content == body
        # events: hello frame carries recent history
        with client.websocket_connect(f"/events?token={token}") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello" and any(e["type"] == "project.opened" for e in hello["data"]["recent"])
        assert client.get("/engine").json()["running"] is False
        assert client.post("/project/close", headers=H).json() == {"open": False}
    # a relaunch on the same state reopens the last project (reopen_last_project default)
    client2 = TestClient(create_app(tmp_path / "state"))
    with client2:
        assert client2.get("/project").json()["name"] == "Smoke"
    # the queue file records a clean shutdown
    q = json.loads((tmp_path / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))
    assert q["clean_shutdown"] is True


def test_api_error_codes_and_alpha_thumbs(tmp_path: Path):
    """B11: unknown ids and malformed cursors are the caller's errors (4xx); transparent sources keep alpha in their thumbs."""
    client, token = _client(tmp_path)
    H = {"X-Loom-Token": token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Codes", "size_cap_gb": 10}, headers=H)
        assert client.post("/models/nope/verify", headers=H).status_code == 404
        r = client.post("/recipes/preview", json={"recipe": {"kind": "t2i", "prompt_text": "x", "loras": [{"model_id": "nope"}]}}, headers=H)
        assert r.status_code == 422 and "nope" in r.json()["detail"]
        assert client.post("/jobs", json={"recipe": {"kind": "t2i", "prompt_text": "x", "model_id": "nope"}}, headers=H).status_code == 422
        assert client.get("/assets", params={"cursor": "garbage"}).status_code == 400
        assert client.get("/assets", params={"cursor": "12x", "sort": "rating_desc"}).status_code == 400
        assert client.put("/settings", json={"vram_budget_gb": "lots"}, headers=H).status_code == 422
        png = tmp_path / "alpha.png"
        Image.new("RGBA", (64, 64), (200, 40, 40, 0)).save(png)                 # fully transparent red
        asset = client.post("/assets/import", json={"paths": [str(png)]}, headers=H).json()["items"][0]
        thumb = client.get(f"/thumbs/{asset['id']}/256")
        import io
        with Image.open(io.BytesIO(thumb.content)) as im:
            assert im.mode == "RGBA" and im.getextrema()[3] == (0, 0)             # alpha survived (not flattened to black)
        client.post("/project/close", headers=H)


def test_empty_trash_purges_everything_with_one_event(tmp_path: Path):
    """Emptying a big trash is one purge call and one catalogue.changed frame, not thousands of asset.deleted frames."""
    client, token = _client(tmp_path)
    H = {"X-Loom-Token": token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "T", "size_cap_gb": 10}, headers=H)
        paths = []
        for i in range(60):
            png = tmp_path / f"in{i}.png"
            Image.new("RGB", (8, 8), (i, 0, 0)).save(png)
            paths.append(str(png))
        items = client.post("/assets/import", json={"paths": paths}, headers=H).json()["items"]
        ids = [a["id"] for a in items]
        client.post("/assets/trash", json={"ids": ids[:55]}, headers=H)
        with client.websocket_connect(f"/events?token={token}") as ws:
            ws.receive_json()                                                       # hello
            r = client.post("/assets/purge", json={"ids": None}, headers=H).json()
            assert r["purged"] == 55 and r["ids"] == []
            frame = ws.receive_json()
            assert frame["type"] == "catalogue.changed" and frame["data"]["purged"] == 55
        assert client.get("/assets", params={"folder": "trash"}).json()["total"] == 0
        assert client.get("/assets").json()["total"] == 5
        for aid in ids[:55]:
            assert client.get(f"/assets/{aid}").status_code == 404
        # a small purge still names its ids and emits per-asset frames
        client.post("/assets/trash", json={"ids": ids[55:57]}, headers=H)
        r = client.post("/assets/purge", json={"ids": None}, headers=H).json()
        assert r["purged"] == 2 and sorted(r["ids"]) == sorted(ids[55:57])
        client.post("/project/close", headers=H)
