"""D61 (PC26, PhotoCraft's `panic_hunt`): every route in the OpenAPI document, fed junk — bodies, path and query parameters — answers
without a 500 and within 4 s. The app runs as the tests run it (a temporary project with a document and an imported image, the
engine's python missing so nothing reaches a GPU); /shutdown is skipped, and the routes that end the session go last."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState

SKIP = {("POST", "/shutdown")}
LAST = {("POST", "/project/close"), ("POST", "/project/open"), ("POST", "/project")}
BUDGET_S = 4.0


def _junk_for(schema: dict) -> object:
    t = schema.get("type")
    return {"string": 12345, "integer": "not a number", "number": "NaN?", "boolean": "maybe", "array": {"not": "a list"}, "object": ["not", "an", "object"]}.get(t, {"nested": True})


def _resolve(spec: dict, schema: dict) -> dict:
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
    return schema


def _bodies(spec: dict, op: dict) -> list[tuple[str, object]]:
    rb = op.get("requestBody")
    if not rb:
        return [("none", None)]
    content = rb.get("content", {})
    if "application/json" not in content:                               # octet-stream uploads: wrong sizes and garbage
        return [("none", None), ("bytes", b"\x00\xffjunk"), ("empty", b"")]
    schema = _resolve(spec, content["application/json"].get("schema", {}))
    props = schema.get("properties", {})
    wrong = {k: _junk_for(_resolve(spec, v)) for k, v in props.items()} or {"x": {"nested": True}}
    return [("none", None), ("{}", {}), ("list", [1, 2, 3]), ("not-json", b"{not json"), ("wrong-types", wrong)]


@pytest.fixture
def client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    c = TestClient(app, raise_server_exceptions=False)
    with c:
        H = {"X-Loom-Token": app.state.services.app.token}
        assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "fuzz", "size_cap_gb": 10}, headers=H).status_code == 200
        c.post("/queue/pause", headers=H)
        img = tmp_path / "in.png"
        Image.fromarray((np.random.default_rng(0).random((48, 64, 3)) * 255).astype(np.uint8)).save(img)
        asset = c.post("/assets/import", json={"paths": [str(img)]}, headers=H).json()["items"][0]["id"]
        doc = c.post("/documents", json={"w": 64, "h": 48, "name": "fuzz"}, headers=H).json()["id"]
        yield c, H, {"doc_id": doc, "asset_id": asset}


def test_no_route_answers_500_or_hangs(client):
    c, H, real = client
    spec = c.app.openapi()
    ops = [(m.upper(), path, op) for path, item in spec["paths"].items() for m, op in item.items() if m in ("get", "post", "put", "patch", "delete")]
    ops = [o for o in ops if (o[0], o[1]) not in SKIP]
    ops.sort(key=lambda o: ((o[0], o[1]) in LAST, o[0] == "DELETE"))     # the session enders last
    failures: list[str] = []
    calls = 0
    for method, path, op in ops:
        params = op.get("parameters", [])
        path_names = [p["name"] for p in params if p["in"] == "path"]
        query = {p["name"]: "-1" if _resolve(spec, p.get("schema", {})).get("type") in ("integer", "number") else "../../x" for p in params if p["in"] == "query"}
        variants = [{n: real.get(n, "x") for n in path_names}]            # real ids where we have them, junk otherwise …
        for junk in ("0", "..%2F..%2Fetc", "a" * 300, "%00"):              # … then junk everywhere
            variants.append({n: junk for n in path_names})
        bodies = _bodies(spec, op)
        for vi, values in enumerate(variants if path_names else variants[:1]):
            url = path
            for n, v in values.items():
                url = url.replace("{" + n + "}", v)
            for bi, (bname, body) in enumerate(bodies):
                if vi and bi > 1:                                          # junk paths: two bodies are enough
                    continue
                for q in ({}, query) if query else ({},):
                    kw: dict = {"headers": dict(H), "params": q}
                    if isinstance(body, (bytes, bytearray)):
                        kw["content"] = body
                        kw["headers"]["Content-Type"] = "application/json" if bname == "not-json" else "application/octet-stream"
                    elif body is not None:
                        kw["json"] = body
                    t0 = time.perf_counter()
                    r = c.request(method, url, **kw)
                    dt = time.perf_counter() - t0
                    calls += 1
                    if r.status_code >= 500 and r.status_code != 503 or dt > BUDGET_S:
                        failures.append(f"{method} {url[:80]} body={bname} query={bool(q)} → {r.status_code} in {dt:.2f} s: {r.text[:160]}")
    print(f"\nroute fuzz: {len(ops)} operations, {calls} requests, {len(failures)} failures")
    assert not failures, "\n".join(failures[:40])
