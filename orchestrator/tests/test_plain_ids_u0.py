"""U0 (BE#1, the UI2 study's register): ids from URLs become file and folder names, and `DELETE /timelines/..%5Cproject` deleted a
throwaway project's project.json. The API refuses a decoded path segment with a backslash, a NUL, a drive or a dot segment, and the
stores' path builders refuse the same names (`fsio.plain_name`)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app, plain_path
from loom2.config import AppState
from loom2.fsio import StateError, plain_name

BS = chr(92)


def test_plain_name_refuses_what_leaves_a_folder():
    for ok in ("tl_1a2b3c4d", "stg_00", "root", "v1"):
        assert plain_name(ok) == ok
    for bad in ("", ".", "..", "a/b", f"..{BS}project", f"a{chr(0)}b", "C:x", "x:y"):
        with pytest.raises(StateError):
            plain_name(bad)


def test_plain_path_reads_the_decoded_segments():
    assert plain_path("/timelines/tl_1/export")
    assert plain_path("/story/profiles/prf_1/versions/v1/poses/hold")
    assert not plain_path(f"/timelines/..{BS}project")
    assert not plain_path("/stages/..")
    assert not plain_path("/finals/./x")
    assert not plain_path("/documents/C:evil")
    assert not plain_path(f"/clips/a{chr(0)}b")


def test_a_backslash_id_never_reaches_the_project(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as client:
        assert client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Guard", "size_cap_gb": 10}, headers=H).status_code == 200
        project_json = tmp_path / "proj" / "project.json"
        assert project_json.is_file()
        for url in ("/timelines/..%5Cproject", "/stages/..%5Cproject", "/story/flow/nodes/..%5Cproject", "/finals/%2E%2E", "/stages/C:%5Cx", "/finals/..%2Fx"):
            assert client.delete(url, headers=H).status_code == 400, url
        assert client.get("/stages/..%5Cproject", headers=H).status_code == 400
        assert project_json.is_file()
        assert client.get("/stages", headers=H).status_code == 200                          # a plain path still passes
