"""D37: the routes split per domain keep exactly the route table they had (method + path, snapshot taken before the move),
no literal path is shadowed by an earlier parameterised route, and the OpenAPI document lists the same paths."""
import json
from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute

from loom2.api import create_app

SNAPSHOT = Path(__file__).parent / "fixtures" / "routes_d37.json"


def test_route_table_matches_the_snapshot(tmp_path: Path):
    app = create_app(tmp_path)
    rows = sorted({row for route in flat_routes(app.routes) for row in route_rows(route)})
    assert rows == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_no_literal_path_is_shadowed(tmp_path: Path):
    """`/assets/counts` must be registered before `/assets/{asset_id}` (and the like), or the parameter route answers."""
    routes = [r for r in flat_routes(create_app(tmp_path).routes) if isinstance(r, APIRoute)]
    shadowed = []
    for i, route in enumerate(routes):
        if "{" in route.path:
            continue
        for earlier in routes[:i]:
            if earlier.methods & route.methods and earlier.path_regex.match(route.path):
                shadowed.append(f"{sorted(route.methods)} {route.path} is caught by {earlier.path}")
    assert shadowed == []


def test_openapi_lists_every_http_path(tmp_path: Path):
    app = create_app(tmp_path)
    paths = {r.path for r in flat_routes(app.routes) if isinstance(r, APIRoute)}
    assert set(app.openapi()["paths"]) == paths


def flat_routes(routes) -> list:
    """Routes in matching order; FastAPI ≥ 0.140 keeps included routers as `_IncludedRouter` wrappers."""
    out = []
    for r in routes:
        inner = getattr(r, "original_router", None)
        out += flat_routes(inner.routes) if inner is not None else [r]
    return out


def route_rows(route) -> list[str]:
    if isinstance(route, APIRoute):
        return [f"{m} {route.path}" for m in sorted(route.methods)]
    if isinstance(route, APIWebSocketRoute):
        return [f"WS {route.path}"]
    return []
