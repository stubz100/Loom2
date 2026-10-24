"""RC1 (D96, proto01_animate 28): a shot version's recipe as a graph built from its records — an image-to-video shot (its speakers and place
into the frame, the frame into the clip, the clip into the take; a stale frame spreads), a dialogue's lines, and a clay final shot (each
character's animation reference and motion into her layer, the plate, the composition, the finish, the take; the stage moved on makes the
plate and the layers stale and everything after them; a render behind its composition). The final a version reads, the route, and RC0's
list of a clay version read from the graph. Then the route on a project."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.compositions import Composition  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.finals import Final, FinalLayer, ProcessingLayer  # noqa: E402
from loom2.shot_graph import clay_rows, final_for, shot_graph  # noqa: E402
from loom2.stages import Stage, StageCamera, StageObject  # noqa: E402
from loom2.story import FlowLine, FlowNode, Profile, ProfileVersion, Shot, ShotVersion  # noqa: E402


def _prof(pid: str, name: str, cls: str = "character", **v) -> Profile:
    return Profile(id=pid, name=name, cls=cls, current="v1", versions=[ProfileVersion(id="v1", group_id=f"grp_{pid}", **v)])


def _rc0(template: str, **rows) -> dict:
    steps = [{"id": sid, "label": sid.capitalize(), "inputs": ["frame"] if sid == "clip" else [], "state": st, "reasons": [], "wave": None,
              "runs": 1 if st == "fresh" else 0, "kind": None, "seconds": 12.0, "job_id": None, "outputs": out, "at": None}
             for sid, (st, out) in rows.items()]
    return {"template": template, "label": template, "steps": steps, "stale": 0, "stale_seconds": 0}


def _by(g) -> dict:
    return {n.id: n for n in g.nodes}


def _edges(g) -> set:
    return {(e.from_, e.to) for e in g.edges}


MARA = _prof("prf_m", "Mara", hero_asset_id="ast_hm", anim_ref_asset_id="ast_rm")
INES = _prof("prf_i", "Ines", hero_asset_id="ast_hi")
QUAY = _prof("prf_q", "Quay", cls="place", hero_asset_id="ast_hq")
PROFILES = {p.id: p for p in (MARA, INES, QUAY)}
asset = lambda cid: f"ast_of_{cid}"  # noqa: E731


def test_an_image_to_video_shot():
    node = FlowNode(id="node_a", type="dialogue", title="Talk", place_id="prf_q",
                    lines=[FlowLine(speaker="prf_m", text="Hi."), FlowLine(speaker="prf_i", text="Come in.", audio_asset_id="ast_v", audio_text="Come in.")])
    v = ShotVersion(id="v1", clip_id="clp_1")
    shot = Shot(id="sht_a", name="Talk", versions=[v], current="v1")
    g = shot_graph(shot, v, rc0=_rc0("i2v", frame=("fresh", ["ast_f"]), clip=("fresh", ["clp_1"])), node=node, profiles=PROFILES, stage=None,
                   final=None, composition=None, clip_asset=asset)
    n = _by(g)
    assert g.route == "i2v" and g.final_id is None
    assert {"character:prf_m", "character:prf_i", "place:prf_q", "lines", "step:frame", "step:clip", "take"} <= set(n)
    assert n["character:prf_m"].thumb == "ast_hm" and n["step:frame"].thumb == "ast_f" and n["step:clip"].thumb == "ast_of_clp_1" and n["take"].thumb == "ast_of_clp_1"
    assert {("character:prf_m", "step:frame"), ("place:prf_q", "step:frame"), ("step:frame", "step:clip"), ("step:clip", "take")} <= _edges(g)
    assert n["lines"].state == "owed" and n["lines"].sub == "1 of 2 voiced"
    assert "anim_ref:prf_m" not in n                                                   # not a clay route
    # a stale frame spreads to the clip and the take
    g = shot_graph(shot, v, rc0=_rc0("i2v", frame=("stale", ["ast_f"]), clip=("fresh", ["clp_1"])), node=node, profiles=PROFILES, stage=None,
                   final=None, composition=None, clip_asset=asset)
    n = _by(g)
    assert n["step:clip"].state == "stale" and "after frame" in n["step:clip"].reasons and n["take"].state == "stale" and g.stale == 3
    # a job of the shot's queued: its frame runs
    job = SimpleNamespace(id="job_1", status="running", kind="t2i", recipe={}, origin=SimpleNamespace(surface="for_shot", payload={"shot_id": "sht_a"}))
    g = shot_graph(shot, v, rc0=_rc0("i2v", frame=("fresh", ["ast_f"]), clip=("fresh", ["clp_1"])), node=node, profiles=PROFILES, stage=None,
                   final=None, composition=None, clip_asset=asset, jobs=[job])
    assert _by(g)["step:frame"].state == "running" and _by(g)["step:clip"].state == "done"


def _stage(revision: int) -> Stage:
    return Stage(id="stg_1", name="Room", revision=revision, cameras=[StageCamera(id="cam_1", name="Camera 1", focal_mm=35)],
                 objects=[StageObject(id="fig_m", kind="mannequin", name="Mara", profile_id="prf_m"), StageObject(id="fig_i", kind="mannequin", name="Ines", profile_id="prf_i"),
                          StageObject(id="stool", kind="prop", name="Stool")],
                 keyframes={"camera": {}, "objects": {"fig_m": [{"t": 0}, {"t": 40}]}})


def _final(**extra) -> Final:
    layers = [FinalLayer(id="plate", kind="plate", name="Plate", method="projected", status="done", still_asset_id="ast_plate", frames_done=81),
              FinalLayer(id="fig_m", kind="figure", name="Mara", object_id="fig_m", method="move", profile_id="prf_m", status="done",
                         batches=[{"k": 0, "job_id": "j0", "clip_id": "clp_m0"}, {"k": 1, "job_id": "j1", "clip_id": "clp_m1"}]),
              FinalLayer(id="fig_i", kind="figure", name="Ines", object_id="fig_i", method="move", profile_id="prf_i", status="done"),
              FinalLayer(id="stool", kind="prop", name="Stool", object_id="stool", method="rendered", status="done"),
              FinalLayer(id="shadows", kind="shadows", name="Shadows", method="rendered", status="done")]
    return Final(id="fin_1", stage_id="stg_1", camera_id="cam_1", stage_revision=5, range={"start": 0, "end": 120}, size={"w": 832, "h": 480}, frames=81,
                 shot_id="sht_c", shot_version="v1", layers=layers, clip_id="clp_render", assembled_at="2026-10-24T01:24:00Z", revision=3, **extra)


def test_a_clay_final_shot():
    v = ShotVersion(id="v1", stage_id="stg_1", camera_id="cam_1", clip_id="clp_render")
    shot = Shot(id="sht_c", name="Mara comes in", versions=[v], current="v1")
    comp = Composition(final_id="fin_1", effectcraft="0.12.0", final_revision=3, revision=2, clip_id="clp_render", rendered_revision=2)
    rc0 = _rc0("stage", frame=("missing", []), clip=("missing", []))
    g = shot_graph(shot, v, rc0=rc0, node=None, profiles=PROFILES, stage=_stage(5), final=_final(), composition=comp, clip_asset=asset)
    n = _by(g)
    assert g.route == "clay2" and g.final_id == "fin_1"
    assert "step:frame" not in n and "step:clip" not in n                            # the clay route makes no frame or clip of its own
    assert {"character:prf_m", "anim_ref:prf_m", "anim_ref:prf_i", "stage", "camera", "motion:fig_m", "motion:fig_i", "plate",
            "layer:fig_m", "layer:fig_i", "composition", "finish", "take"} == set(n) - {"character:prf_i"}
    assert "layer:stool" not in n and "layer:shadows" not in n                        # a stand-in prop and the shadows are passes, not parts
    assert n["anim_ref:prf_i"].state == "owed" and n["anim_ref:prf_m"].thumb == "ast_rm"
    assert n["motion:fig_m"].state == "done" and n["motion:fig_i"].state == "none" and n["motion:fig_i"].sub == "stands still"
    assert n["layer:fig_m"].thumb == "ast_of_clp_m1" and n["layer:fig_m"].sub == "2 batches" and n["plate"].thumb == "ast_plate"
    assert n["finish"].state == "none" and n["take"].state == "done" and n["take"].thumb == "ast_of_clp_render"
    assert {("anim_ref:prf_m", "layer:fig_m"), ("motion:fig_m", "layer:fig_m"), ("camera", "plate"), ("plate", "composition"),
            ("layer:fig_i", "composition"), ("composition", "finish"), ("finish", "take")} <= _edges(g)
    # the stage moved on since the final: the plate and the layers, then everything after them
    g = shot_graph(shot, v, rc0=rc0, node=None, profiles=PROFILES, stage=_stage(7), final=_final(), composition=comp, clip_asset=asset)
    n = _by(g)
    assert n["plate"].state == "stale" and n["plate"].reasons == ["the stage moved on (revision 5 → 7)"]
    assert n["layer:fig_i"].state == "stale" and n["composition"].state == "stale" and n["take"].state == "stale"
    assert n["motion:fig_m"].state == "done" and n["anim_ref:prf_m"].state == "done"
    # a render behind its composition; a processing layer whose layers changed
    comp2 = comp.model_copy(update={"revision": 4, "processing_stale": {"proc_fig_m": True}})
    f2 = _final(processing=[ProcessingLayer(id="proc_fig_m", above="fig_m", preset="cleanup", strength=0.3, model_id="m", job_id="j", frames=81, made_at="t", signature="s")])
    g = shot_graph(shot, v, rc0=rc0, node=None, profiles=PROFILES, stage=_stage(5), final=f2, composition=comp2, clip_asset=asset)
    n = _by(g)
    assert n["finish"].state == "stale" and n["finish"].sub == "1 pass" and n["take"].state == "stale" and "edits since the render" in n["take"].reasons
    # RC0's list of a clay version reads its states from the graph
    rows = clay_rows([{"id": i, "state": "missing", "reasons": [], "wave": None} for i in ("character", "anim_ref", "plate", "frame", "performance", "take")], g)
    st = {r["id"]: r["state"] for r in rows}
    assert st == {"character": "fresh", "anim_ref": "missing", "plate": "fresh", "frame": "missing", "performance": "fresh", "take": "stale"}


def test_the_final_a_version_reads():
    v = ShotVersion(id="v2", stage_id="stg_1", camera_id="cam_1")
    old = _final().model_copy(update={"id": "fin_old", "shot_id": None, "shot_version": None, "created_at": "2026-10-20T00:00:00Z"})
    mine = _final().model_copy(update={"id": "fin_mine", "shot_version": "v2", "created_at": "2026-10-21T00:00:00Z"})
    other = _final().model_copy(update={"id": "fin_other", "shot_id": "sht_x", "created_at": "2026-10-22T00:00:00Z"})
    assert final_for("sht_c", v, [old, mine, other]).id == "fin_mine"
    assert final_for("sht_c", v, [old, other]).id == "fin_old"                         # on its camera, made for no other shot
    assert final_for("sht_c", ShotVersion(id="v1"), [old]) is None


def test_the_route(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10})
        n = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Gate"}).json()
        r = cl.get(f"/story/shots/{n['shot_id']}/graph")
        assert r.status_code == 200, r.text
        g = r.json()
        assert g["route"] == "i2v" and {x["id"] for x in g["nodes"]} >= {"step:frame", "step:clip", "take"}
        assert {"from": "step:frame", "to": "step:clip"} in g["edges"] and g["owed"] == 3
        assert cl.get("/story/shots/sht_nope/graph").status_code == 404
        cl.put(f"/story/shots/{n['shot_id']}/versions/v1/template", json={"template": "clay1"})
        g = cl.get(f"/story/shots/{n['shot_id']}/graph").json()
        assert {x["id"] for x in g["nodes"]} >= {"plate", "composition", "take"} and all(x["state"] == "owed" for x in g["nodes"] if x["id"] in ("plate", "composition"))
        rec = cl.get(f"/story/shots/{n['shot_id']}/recipe").json()
        assert {s["id"]: s["state"] for s in rec["steps"]}["plate"] == "missing" and {s["id"]: s["wave"] for s in rec["steps"]}["frame"] == "CA5 (W3)"


def test_a_layer_goes_stale_only_with_its_own_parts():
    """UX0 W6: an edit marks what depends on it — with the final's stamps, a figure moved stales her layer (then the composition and the
    take), not the other's nor the plate; the camera moved stales the plate and every layer; a renamed figure changes nothing."""
    from loom2.shot_graph import stage_stamps
    v = ShotVersion(id="v1", stage_id="stg_1", camera_id="cam_1", clip_id="clp_render")
    shot = Shot(id="sht_c", name="Mara comes in", versions=[v], current="v1")
    comp = Composition(final_id="fin_1", effectcraft="0.12.0", final_revision=3, revision=0, clip_id="clp_render", rendered_revision=0)
    rc0 = _rc0("stage", frame=("missing", []), clip=("missing", []))
    st0 = _stage(5)
    f = _final(stamps=stage_stamps(st0, "cam_1"))
    graph = lambda st: _by(shot_graph(shot, v, rc0=rc0, node=None, profiles=PROFILES, stage=st, final=f, composition=comp, clip_asset=asset))  # noqa: E731
    st = st0.model_copy(deep=True)
    st.revision = 6
    st.objects[1].transform.pos = [0.3, 0.0, 0.0]                                    # Ines moved
    n = graph(st)
    assert n["layer:fig_i"].state == "stale" and n["layer:fig_i"].reasons == ["Ines moved or was re-keyed"]
    assert n["layer:fig_m"].state == "done" and n["plate"].state == "done"
    assert n["composition"].state == "stale" and n["composition"].reasons == ["after ines layer"] and n["take"].state == "stale"
    st = st0.model_copy(deep=True)
    st.keyframes["objects"]["fig_m"].append({"t": 80})                               # Mara re-keyed
    n = graph(st)
    assert n["layer:fig_m"].state == "stale" and n["layer:fig_i"].state == "done"
    st = st0.model_copy(deep=True)
    st.cameras[0].focal_mm = 50                                                      # the camera moved
    n = graph(st)
    assert n["plate"].reasons == ["the camera moved"] and n["layer:fig_m"].state == "stale" and n["layer:fig_i"].state == "stale"
    st = st0.model_copy(deep=True)
    st.objects[0].name = "Mara (hero)"; st.revision = 9                              # a name changes nothing rendered
    assert all(x.state != "stale" for x in graph(st).values())
