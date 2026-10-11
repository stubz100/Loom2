import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def object_info() -> dict:
    return json.loads((FIXTURES / "object_info.json").read_text(encoding="utf-8"))["object_info"]


@pytest.fixture
def models_tree(tmp_path: Path) -> Path:
    """A fake ComfyUI-layout models root with a few roster files present (empty files are enough for the scan)."""
    root = tmp_path / "models"
    for rel in ("diffusion_models/flux2_dev_fp8mixed.safetensors", "text_encoders/mistral_3_small_flux2_fp8.safetensors",
                "vae/flux2-vae.safetensors", "loras/Flux2TurboComfyv2.safetensors", "diffusion_models/stray-model.safetensors"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
    (root / "roster.index.json").write_text(json.dumps({"files": [
        {"path": str(root / "vae" / "flux2-vae.safetensors"), "size": 16, "sha256": "ab" * 32}]}), encoding="utf-8")
    return root


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--parity-update", action="store_true", default=False, help="rewrite fixtures/graph_parity.json (D64: intended graph changes only)")


@pytest.fixture(autouse=True)
def _authenticated_test_clients(monkeypatch):
    """D67: every route but /health needs the token. A TestClient built without `headers` sends the app's token by default, so a test
    reads like the frontend's typed client; the gate itself is tested with explicit `headers={}` (test_auth_d67.py)."""
    from fastapi.testclient import TestClient
    orig = TestClient.__init__

    def init(self, app, *a, headers=None, **kw):
        if headers is None:
            st = getattr(getattr(getattr(app, "state", None), "services", None), "app", None)
            headers = {"X-Loom-Token": st.token} if st is not None else None
        orig(self, app, *a, headers=headers, **kw)
    monkeypatch.setattr(TestClient, "__init__", init)
