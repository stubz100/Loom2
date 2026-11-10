"""RS0b (D197, proto02 03): the findings that were faults today, fixed before the restructure.

- PG22: the A-pose buttons make what Make's reference framing makes (D177) — a character's front, back and side a 2:3 portrait of about the
  pixels of the project's frame at the Draft height (`make.ts`'s `to23`), a prop's view and a set picture the project's frame at that height,
  a hand or feet picture 1024²;
- PG26: a stage made with no size asked (*New shot*, a re-scene, a bench, the line-up) takes the project's format, as Clay's *New stage…* did;
- PG20: a stage a shot looks at cannot be deleted — a 409 naming the shot; a stage nobody uses still can.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import anim_ref_frame  # noqa: E402


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    return app, TestClient(app, headers={"X-Loom-Token": app.state.services.app.token})


def test_the_reference_frame_is_makes():
    assert anim_ref_frame("character", "front", 1920, 1080) == (784, 1168)       # `to23(1280, 720)` in make.ts
    assert anim_ref_frame("character", "back", 1920, 1080) == (784, 1168)
    assert anim_ref_frame("character", "side", 1920, 1080) == (784, 1168)
    assert anim_ref_frame("prop", "front", 1920, 1080) == (1280, 720)            # D177: a prop's view and a set picture stay the project's frame
    assert anim_ref_frame("place", "front", 1920, 1080) == (1280, 720)
    assert anim_ref_frame("character", "hand", 1920, 1080) == (1024, 1024)       # RG1
    assert anim_ref_frame("character", "feet", 1280, 720) == (1024, 1024)
    for fw, fh in [(1920, 1080), (1440, 1080), (1080, 1080), (2560, 1080)]:     # any project frame: a 2:3 portrait of about its pixels
        w, h = anim_ref_frame("character", "front", fw, fh)
        base = round(720 * fw / fh / 16) * 16 * 720
        assert w % 16 == 0 and h % 16 == 0 and abs(w / h - 2 / 3) < 0.02 and abs(w * h - base) / base < 0.05, (fw, fh, w, h)


def test_the_route_makes_the_portrait(tmp_path: Path):
    from test_graph_parity_d64 import _pin_review                               # the roster the clay-reference model needs, as CA0's route test
    from test_groups_d34 import _png
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        hero = app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        sizes = {}
        for cls, side in [("character", "front"), ("character", "back"), ("prop", "front")]:
            p = cl.post("/story/profiles", json={"name": f"{cls} {side}", "cls": cls, "hero_asset_id": hero, "appearance": "a test"}).json()
            r = cl.post(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": side, "count": 1, "stage": True})
            assert r.status_code == 200, r.text
            jobs = {j["id"]: j for j in cl.get("/jobs").json()["items"]}
            rec = jobs[r.json()["job_ids"][0]]["recipe"]
            sizes[(cls, side)] = (rec["width"], rec["height"])
        assert sizes == {("character", "front"): (784, 1168), ("character", "back"): (784, 1168), ("prop", "front"): (1280, 720)}


def test_a_stage_takes_the_projects_format_and_a_used_one_stays(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        fmt = {"aspect": [16, 9], "width": 1280, "height": 720, "fps": 16}
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10, "format": fmt}).status_code == 200
        a = cl.post("/story/flow/shots", json={"title": "Wide", "scene": "new"}).json()
        v = cl.get(f"/story/shots/{a['shot_id']}").json()["versions"][0]
        st = cl.get(f"/stages/{v['stage_id']}").json()
        assert st["size"] == {"w": 1280, "h": 720, "fps": 16} and st["length"] == 5 * 16     # PG26: not 1920×1080 at 24
        made = cl.post("/stages", json={"name": "By hand"}).json()
        assert made["size"] == {"w": 1280, "h": 720, "fps": 16}
        r = cl.delete(f"/stages/{v['stage_id']}")                                            # PG20: Wide still looks at it
        assert r.status_code == 409 and "Wide" in r.json()["detail"]
        assert cl.get(f"/stages/{v['stage_id']}").status_code == 200
        assert cl.delete(f"/stages/{made['id']}").status_code == 200                        # nobody's: deleted as before
