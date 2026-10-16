"""D67 (ArtCraft P9): every route is authenticated.

- the route matrix: every route of the OpenAPI document refuses a caller without credentials (401) except /health; the media GETs take
  the read-only key `?k=`, no other route does, and no mutating route accepts it;
- the WebSocket closes with 4401 unless its first message authenticates;
- the interactive docs are off unless LOOM2_DEV=1; GET /session hands the client its media key.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from loom2.api import MEDIA_PATH, create_app
from loom2.config import AppState

MEDIA = {"/thumbs/{asset_id}/{size}", "/assets/{asset_id}/file", "/clips/{clip_id}/proxy.mp4", "/clips/{clip_id}/frames/{name}",
         "/documents/{doc_id}/thumbnail", "/blobs/{sha}", "/preset-icons/{key}/file"}


def _app(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    return create_app(state)


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def test_the_route_matrix(tmp_path: Path):
    app = _app(tmp_path)
    svc = app.state.services.app
    spec = app.openapi()
    bare = TestClient(app, headers={}, raise_server_exceptions=False)               # no credentials at all
    with bare:
        seen_media = set()
        for path, ops in spec["paths"].items():
            url = _concrete(path)
            for method in ops:
                r = bare.request(method.upper(), url)
                if path == "/health":
                    assert r.status_code == 200, path
                    continue
                assert r.status_code == 401, (method, path, r.status_code)          # nothing else answers without the token
                media = method == "get" and path in MEDIA
                if method == "get":
                    assert bool(MEDIA_PATH.match(url)) == media, path                  # the key's path list is exactly the media GETs
                with_key = bare.request(method.upper(), url, params={"k": svc.media_key})
                if media:
                    seen_media.add(path)
                    assert with_key.status_code != 401, (path, with_key.status_code)   # the key opens pixels (404 for a missing id is fine)
                else:
                    assert with_key.status_code == 401, (method, path)              # and nothing else: settings, jobs, prompts, mutations
                assert bare.request(method.upper(), url, params={"k": "wrong"}).status_code == 401 or path == "/health"
        assert seen_media == MEDIA                                                  # every media route exists and was exercised
        assert bare.get("/settings").status_code == 401                            # the acceptance line: curl /settings → 401
        assert bare.get("/settings", headers={"X-Loom-Token": svc.token}).status_code == 200


def test_the_session_hands_out_the_media_key(tmp_path: Path):
    app = _app(tmp_path)
    with TestClient(app) as c:                                                       # the default test client carries the token
        s = c.get("/session").json()
        assert s["media_key"] == app.state.services.app.media_key and len(s["media_key"]) == 32
        assert s["media_key"] != app.state.services.app.token


def test_the_websocket_needs_an_auth_message(tmp_path: Path):
    app = _app(tmp_path)
    token = app.state.services.app.token
    with TestClient(app) as c:
        for first in ({"type": "auth", "token": "wrong"}, {"type": "hello"}):
            with c.websocket_connect("/events") as ws:
                ws.send_json(first)
                with pytest.raises(WebSocketDisconnect) as e:
                    ws.receive_json()
                assert e.value.code == 4401
        with c.websocket_connect("/events") as ws:                                   # silence: closed after the 2 s window
            with pytest.raises(WebSocketDisconnect) as e:
                ws.receive_json()
            assert e.value.code == 4401
        with c.websocket_connect("/events") as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json()["type"] == "hello"


def test_docs_only_in_development(tmp_path: Path, monkeypatch):
    with TestClient(_app(tmp_path)) as c:
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    monkeypatch.setenv("LOOM2_DEV", "1")
    with TestClient(_app(tmp_path / "dev"), headers={}) as c:
        assert c.get("/openapi.json").status_code == 200 and c.get("/docs").status_code == 200
