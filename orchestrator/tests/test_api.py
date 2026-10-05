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
        assert "t2i" in caps["recipes"] and "flux2-dev-fp8mixed" in caps["models"]
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
    # the queue file records a clean shutdown
    q = json.loads((tmp_path / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))
    assert q["clean_shutdown"] is True
