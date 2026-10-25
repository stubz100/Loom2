"""CA1b (D104): a figure's skeleton fitted to its character — the dummy's front view (body.dummy_ratios, kept in step with the frontend's
builders.ts), the reference's proportions from SDPose (reference_ratios), the fit (fit_body), the `keypoints` job (SDPose wholebody on
RT-DETR boxes; its graph compiles against the pinned engine) and the Cast route that queues it; the first animation reference of an
untouched body is fitted by itself."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.body import Body, body_points, dummy_ratios, fit_body, rebase_body, reference_ratios, stance_note  # noqa: E402
from loom2.engine.graphs import compile_recipe  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.recipes import Keypoints  # noqa: E402
from loom2.story import StoryStore, body_fit_origin  # noqa: E402

from fake_comfy import fake_person  # noqa: E402
from test_groups_d34 import _png, _setup  # noqa: E402
from test_lifecycle import Rig  # noqa: E402


def test_the_dummy_front_view():
    d = dummy_ratios(Body())
    # the default adult: the nose 0.18 above the shoulders' midpoint (builders.ts: 0.04·torso + 0.12·neck + 0.02·head, S3) over 1.55 nose → ankles
    assert d["head_neck"] == pytest.approx(0.18 / 1.55, abs=1e-3) and d["leg"] == pytest.approx(0.87 / 1.55, abs=1e-3)
    assert dummy_ratios(Body(neck=2.0))["head_neck"] > d["head_neck"] and dummy_ratios(Body(shoulders=0.8))["shoulders"] < d["shoulders"]
    assert dummy_ratios(Body(hands=0.5))["palm"] == pytest.approx(d["palm"] / 2)


def test_the_fit_finds_the_body_back():
    want = Body(height_m=1.62, build="slim", head=1.1, neck=1.6, torso=1.05, shoulders=0.85, arms=0.95, legs=0.9, hands=0.75, elbow=0.55, knee=0.48, feet=1.15)
    kept = Body(height_m=1.62, build="slim", feet=1.2, figure="male", hand_rest={"preset": "fist", "curl": 0.5})
    body, report = fit_body(dummy_ratios(want), kept, locks=("hips",))
    for k in ("head", "neck", "torso", "shoulders", "arms", "legs", "hands", "elbow", "knee", "feet"):   # the hips held: every factor comes back (S5: the feet too)
        assert getattr(body, k) == pytest.approx(getattr(want, k), abs=0.01), k
    assert (body.height_m, body.build, body.figure, body.hand_rest.preset) == (1.62, "slim", "male", "fist")   # the author's: kept
    assert all(abs(v["reference"] - v["fitted"]) < 1e-3 for v in report.values())
    free, report = fit_body(dummy_ratios(want), kept)                                              # S7: the hips free too — the ratios still met
    assert all(abs(v["reference"] - v["fitted"]) / v["reference"] < 0.01 for v in report.values())
    assert free.head == pytest.approx(want.head, abs=0.1) and free.neck == pytest.approx(want.neck, abs=0.15)   # the loose scale held near an adult
    drift, _ = fit_body({k: v for k, v in dummy_ratios(want).items() if k != "head_w"})            # without the ears the scale is looser still: the ratios met
    assert all(dummy_ratios(drift)[k] == pytest.approx(dummy_ratios(want)[k], abs=2e-3) for k in ("head_neck", "torso", "shoulders", "leg", "arm"))
    wild, _ = fit_body({"head_neck": 0.9, "shoulders": 0.01})                                     # out of reach: held at the bounds
    assert wild.neck == 3.0 and wild.shoulders == 0.6
    locked, _ = fit_body(dummy_ratios(want), Body(neck=1.2), locks=("neck", "hips"))              # CS2's locks: a locked factor is the author's
    assert locked.neck == 1.2


def test_a_body_from_before_cs1_reads_as_an_adult_rig(tmp_path: Path):
    """S3: ×1 an adult — a body stored before CS1 (the 6 cm neck, the pivot 8 cm under the nose) converts on read, every point where it
    was; in a profile record (schema 2 → 3) and in a stage's figure (schema 2 → 3); a body made now is never touched."""
    from loom2.fsio import atomic_write_json
    from loom2.stages import StageStore
    from loom2.story import Profile
    from loom2.workspace import Workspace
    old = {"head": 0.889, "torso": 1.225, "neck": 2.317, "legs": 0.88}
    b = Body.model_validate(rebase_body(old))
    assert b.neck == pytest.approx((2.317 + 0.889) / 2, abs=1e-4)                                   # Mara's ×2.32 is ×1.60
    nose_old = 0.44 * 1.225 + 0.06 * 2.317 + 0.08 * 0.889                                          # rig 1's nose over the spine
    nose_new = 0.44 * b.torso + 0.12 * b.neck + 0.02 * b.head
    top_old, top_new = 0.06 * 2.317 + 0.221 * 0.889, 0.12 * b.neck + 0.161 * b.head                 # and the head's top (bodyDims)
    assert nose_new == pytest.approx(nose_old, abs=1e-4) and top_new == pytest.approx(top_old, abs=1e-4)
    assert rebase_body({}) == {"neck": 1.0} and Body(neck=1.4).neck == 1.4 and Body.model_validate(Body(neck=1.4).model_dump()).neck == 1.4
    v1 = {"id": "v1", "label": "v1", "state": "open", "group_id": "grp_x", "body": old}
    p = Profile.model_validate({"schema_version": 2, "id": "prf_x", "name": "Mara", "cls": "character", "current": "v1", "versions": [v1]})
    assert p.schema_version == 3 and p.version("v1").body.neck == pytest.approx(1.603, abs=1e-3)
    assert Profile.model_validate(p.model_dump()).version("v1").body.neck == pytest.approx(1.603, abs=1e-3)   # read again: not again
    ws = Workspace.create(tmp_path / "p", name="P")
    store = StageStore(ws)
    st = store.create("A1")
    raw = st.model_dump() | {"schema_version": 2, "objects": [{"id": "fig_m", "kind": "mannequin", "name": "Mara", "body": old}]}
    atomic_write_json(store.dir / f"{st.id}.json", raw)
    again = store.get(st.id)
    assert again.schema_version == 3 and again.objects[0].body.neck == pytest.approx(1.603, abs=1e-3)


def test_the_reference_measured():
    r = reference_ratios(fake_person({"head_neck": 0.17, "shoulders": 0.24, "palm": 0.07}))
    assert r["head_w"] == pytest.approx(32 / 400, abs=1e-3)                                       # the fake's ears 32 px apart
    assert r["head_neck"] == pytest.approx(0.17, abs=2e-3) and r["shoulders"] == pytest.approx(0.24, abs=2e-3) and r["palm"] == pytest.approx(0.07, abs=2e-3)
    assert r["elbow_at"] == pytest.approx(0.5, abs=1e-3) and r["knee_at"] == pytest.approx(0.5, abs=1e-3)   # S6: the fake's joints halfway
    assert "toes" not in r                                                                         # no feet found
    f = fake_person()
    f["foot_keypoints_2d"] = [400, 444, 0.8, 410, 446, 0.8, 405, 438, 0.7, 430, 444, 0.8, 442, 446, 0.6, 436, 438, 0.7]
    assert reference_ratios(f)["toes"] == pytest.approx(float(sorted([(10 ** 2 + 2 ** 2) ** 0.5, (12 ** 2 + 2 ** 2) ** 0.5])[1] if False else ((10 ** 2 + 2 ** 2) ** 0.5 + (12 ** 2 + 2 ** 2) ** 0.5) / 2) / 400, abs=1e-4)   # S5: big ↔ small toe, the median of both
    p = fake_person()
    p["pose_keypoints_2d"][10 * 3 + 2] = 0.0                                                      # an ankle not found: not a whole figure
    with pytest.raises(ValueError, match="whole figure"):
        reference_ratios(p)


def test_the_keypoints_graph_compiles(tmp_path: Path, object_info: dict):
    from loom2.roster import Roster
    roster = Roster(tmp_path, [], "full")
    for rid, folder, name in (("sdpose-wholebody", "checkpoints", "sdpose_wholebody_fp16.safetensors"), ("rtdetr-v4", "diffusion_models", "rt_detr_v4-x-hgnet_fp16.safetensors")):
        (tmp_path / folder).mkdir(exist_ok=True); (tmp_path / folder / name).write_bytes(b"x")
    roster.scan()
    c = compile_recipe(Keypoints(asset_id="a"), roster, object_info, 0, "loom2/j", inputs={"image": "0000.png"})
    assert c.problems == [] and [n["class_type"] for n in c.graph.values()] == ["CheckpointLoaderSimple", "UNETLoader", "LoadImage", "RTDETR_detect",
                                                                                   "SDPoseKeypointExtractor", "PreviewAny"]


@pytest.mark.asyncio
async def test_a_reference_fits_the_body(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        ref = rig.catalogue.ingest_file(_png(tmp_path / "ref.png")).id
        p = st.create_profile("Ines", "character", groups, appearance="Ines")
        rig.fake.people = [fake_person({"head_neck": 0.167, "shoulders": 0.234, "torso": 0.334, "leg": 0.499, "arm": 0.344, "palm": 0.06})]
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "keypoints", "asset_id": ref}, origin=body_fit_origin(p.id, "v1"))[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        assert len(done.result["people"]) == 1 and done.result["fit"]["head_neck"]["fitted"] == pytest.approx(0.167, abs=0.002)
        v = st.profile(p.id).version("v1")
        assert v.body_fit_from == ref and v.body.neck > 1.4 and v.body.shoulders < 0.95 and v.body.height_m == 1.75   # ×1 an adult's neck (S3): the fake's long one
        assert len(v.body_points["pose"]) == 18 and len(v.body_points["hand_left"]) == 21 and v.body_points["canvas"]   # CS1: the points kept
        assert v.anim_ref_note is None                                                               # the fake stands in the A-pose (S8)
        assert done.result.get("asset_ids") is None                                                  # nothing new in the Catalogue
    finally:
        await rig.close()


def test_the_fit_route(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "open"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ref = app.state.services.catalogue.ingest_file(_png(tmp_path / "r.png")).id
        p = cl.post("/story/profiles", json={"name": "Ines", "cls": "character", "appearance": "Ines"}).json()
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/body/fit").status_code == 422             # no reference to fit to yet
        cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "asset_id": ref})
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/body/fit")
        assert r.status_code == 200, r.text                                                             # under `open` too: MIT / Apache weights
        j = next(x for x in cl.get("/jobs").json()["items"] if x["id"] == r.json()["job_id"])
        assert j["recipe"] == {"kind": "keypoints", "asset_id": ref, "model_id": "sdpose-wholebody"} and j["origin"]["surface"] == "body_fit"
        assert cl.post(f"/story/profiles/{p['id']}/versions/v9/body/fit").status_code == 404
        prop = cl.post("/story/profiles", json={"name": "Box", "cls": "prop"}).json()
        assert cl.post(f"/story/profiles/{prop['id']}/versions/v1/body/fit").status_code == 422


@pytest.mark.asyncio
async def test_the_first_reference_fits_an_untouched_body(tmp_path: Path, object_info: dict):
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.story import plan_anim_ref
    rig = Rig(tmp_path, object_info)
    try:
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        p = st.create_profile("Mara", "character", groups, appearance="Mara")
        p, gid, _ = st.ensure_candidates(p.id, "v1", groups)
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path)
        r, o = plan_anim_ref(p, p.version(), "front", "full", width=64, height=64, count=1, group_id=gid)[0]
        done = await rig.wait(rig.queue.submit({**r, "model_id": mid}, origin=JobOrigin.model_validate(o))[0].id)
        assert done.status == "done", done.error
        fit = next(j for j in rig.queue.jobs.values() if j.origin and j.origin.surface == "body_fit")
        assert (await rig.wait(fit.id)).status == "done"
        v = st.profile(p.id).version("v1")
        assert v.body_fit_from == v.anim_ref_asset_id and v.body is not None and v.body.neck != 1.0
    finally:
        await rig.close()


def test_the_stance_check():
    """S8: a reference whose wrists sit at the hips (A1's two: arms down, hands on the coat) is noted; the A-pose is not."""
    assert stance_note(fake_person()) is None                                                      # 22° out: the wrists well clear
    down = fake_person()
    b = down["pose_keypoints_2d"]
    for w, hp in ((4, 8), (7, 11)):                                                                # the wrists over the hips
        b[w * 3] = b[hp * 3] + (6 if w == 4 else -6)
    assert stance_note(down) == "arms_close"
    pts = body_points(down, [832, 480])
    assert pts["canvas"] == [832, 480] and len(pts["pose"]) == 18 and pts["pose"][4][0] == round(b[12], 2) and pts["feet"] == []
