"""D38: the OpenAPI document is the frontend's contract. Every JSON route declares its reply model, the committed openapi.json
equals what the app exports, and every JSON GET answers 200 on a populated project (a reply that does not fit its model is a
500, so this is where a wrong field type shows up)."""
import subprocess
import sys
from pathlib import Path

from fastapi.routing import APIRoute
from PIL import Image

from loom2.api import create_app
from loom2.config import REPO_ROOT

from test_api import _client
from test_routes_d37 import flat_routes

# replies that are bytes or files, not JSON — they have no response model on purpose
NOT_JSON = {"GET /assets/{asset_id}/file", "GET /thumbs/{asset_id}/{size}", "GET /documents/{doc_id}/layers/{lid}/pixels",
            "GET /documents/{doc_id}/thumbnail", "GET /documents/{doc_id}/selection", "POST /documents/{doc_id}/export",
            "GET /clips/{clip_id}/proxy.mp4", "GET /clips/{clip_id}/frames/{name}", "GET /blobs/{sha}", "POST /heal"}   # D62: /heal answers raw RGBA


def test_every_json_route_declares_its_reply(tmp_path: Path):
    missing = []
    for r in flat_routes(create_app(tmp_path).routes):
        if not isinstance(r, APIRoute):
            continue
        for m in r.methods:
            key = f"{m} {r.path}"
            if key not in NOT_JSON and r.response_model is None:
                missing.append(key)
    assert sorted(missing) == []


def test_committed_openapi_is_current():
    """In a fresh interpreter, like CI: the export pins environment-dependent defaults before `loom2` is imported."""
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "export_openapi.py"), "--check"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_json_get_answers_on_a_populated_project(tmp_path: Path):
    client, token = _client(tmp_path)
    H = {"X-Loom-Token": token}
    with client:
        assert client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Contract"}, headers=H).status_code == 200
        pngs = []
        for i, colour in enumerate(("red", "blue")):
            p = tmp_path / f"in{i}.png"
            Image.new("RGB", (96, 64), colour).save(p)
            pngs.append(str(p))
        assets = client.post("/assets/import", json={"paths": pngs}, headers=H).json()["items"]
        a, b = assets[0]["id"], assets[1]["id"]
        g = client.post("/groups", json={"name": "Shots"}, headers=H).json()
        assert client.post("/groups/move", json={"items": [{"kind": "asset", "id": b}], "to": g["id"]}, headers=H).status_code == 200
        doc = client.post("/documents", json={"from_asset": a}, headers=H).json()
        gets = ["/health", "/version", "/capabilities", "/settings", "/snippets", "/project", "/project/presets", "/projects",
                "/assets", "/assets/groups?group=batch", "/assets/counts", "/assets/tags", f"/assets/{a}", f"/lineage/{a}", f"/lineage/tree/{a}",
                "/groups/tree", f"/groups/where?ids={a}&ids={b}", f"/groups/{g['id']}", "/documents", f"/documents/{doc['id']}",
                "/clips", "/jobs", "/queue", "/models", "/models/unlisted", "/engine"]
        bad = {path: r.status_code for path in gets if (r := client.get(path)).status_code != 200}
        assert bad == {}
        put = client.put(f"/documents/{doc['id']}", json=client.get(f"/documents/{doc['id']}").json(), headers=H)
        assert put.status_code == 200 and {"missing_pixels", "missing_masks"} <= set(put.json())
        preview = client.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": "klein-4b", "prompt_text": "a lighthouse"}}, headers=H)
        assert preview.status_code == 200 and preview.json()["serialized_prompt"]
        assert client.get("/project").json()["assets"] == 2
