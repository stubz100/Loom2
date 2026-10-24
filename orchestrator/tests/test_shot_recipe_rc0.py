"""RC0 (D96, proto01_animate/05 §4): a shot version's recipe — every job made for a shot records a run on its step (the resolved recipe,
its stamps, outputs and wall time); a step is stale when what it read changed (a stage's revision, a reference group, a Cast sheet, the
world style, the frame a clip started from) and a step after a stale one is stale too; the templates show every step; the coverage of
05 §3 (every step's important parts) is carried by the typed recipes."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.origin import JobOrigin  # noqa: E402
from loom2.recipes import I2V, T2I, StageShot  # noqa: E402
from loom2.shot_recipe import COVERAGE, TEMPLATES, RecipeRun, StampReader, add_run, recipe_state, stamps_for, step_of  # noqa: E402
from loom2.story import Profile, ProfileVersion, ShotVersion, StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_lifecycle import Rig  # noqa: E402
from test_makers_ui4_d90 import WAN, _origin  # noqa: E402
from test_groups_d34 import _png  # noqa: E402
from loom2.models import registry  # noqa: E402


class _Story:
    """Profiles and styles as a StoryStore answers them."""

    def __init__(self) -> None:
        self.profiles = {"prf_m": Profile(id="prf_m", name="Mara", current="v1", versions=[ProfileVersion(id="v1", group_id="grp_m", appearance="red coat")])}
        self.styles = {"sty_1": SimpleNamespace(fragment="ink wash")}

    def profile(self, pid):
        return self.profiles.get(pid)

    def style(self, sid):
        return self.styles.get(sid)


def _reader(story, stage_rev=3, group_rev=2):
    stages = SimpleNamespace(get=lambda sid: SimpleNamespace(revision=stage_rev[0] if isinstance(stage_rev, list) else stage_rev))
    groups = SimpleNamespace(groups={"grp_m": SimpleNamespace(revision=group_rev)})
    return StampReader(stages=stages, groups=groups, story=story)


def test_steps_stamps_and_staleness():
    story = _Story()
    frame = {"kind": "stage_shot", "stage_id": "stg_1", "camera_id": "cam_1", "style_id": "sty_1", "style_text": "ink wash",
             "mentions": [{"group_id": "grp_m", "name": "Mara", "revision": 2, "profile_id": "prf_m", "version": "v1"}]}
    assert step_of(frame, None) == ("frame", [])
    st = stamps_for(frame, frame_asset_id=None, stage_id="stg_1", stage_revision=3, story=story)
    assert set(st) == {"stage:stg_1", "group:grp_m", "sheet:prf_m:v1", "style:sty_1"}
    v = ShotVersion(id="v1", stage_id="stg_1", camera_id="cam_1", frame_asset_id="ast_f")
    r = add_run(None, "stage", "frame", [], RecipeRun(kind="stage_shot", settings=frame, stamps=st, outputs=["ast_f"], seconds=30.0))
    clip = {"kind": "i2v", "start_asset": "ast_f"}
    assert step_of(clip, "ast_f") == ("clip", ["frame"]) and step_of({**clip, "audio": {"asset_id": "a"}}, "ast_f")[0] == "lipsync"
    assert step_of({"kind": "train_lora"}, None) is None
    r = add_run(r, "stage", "clip", ["frame"], RecipeRun(kind="i2v", settings=clip, stamps=stamps_for(clip, frame_asset_id="ast_f", stage_id=None, stage_revision=None, story=story),
                                                        outputs=["clp_1"], seconds=120.0))
    v = v.model_copy(update={"recipe": r, "clip_id": "clp_1"})
    out = recipe_state(v, _reader(story))
    assert out["template"] == "stage" and [s["id"] for s in out["steps"]] == ["frame", "clip"]
    assert [s["state"] for s in out["steps"]] == ["fresh", "fresh"] and out["stale"] == 0
    # the stage moved on → the frame is stale, and the clip after it
    out = recipe_state(v, _reader(story, stage_rev=5))
    assert [s["state"] for s in out["steps"]] == ["stale", "stale"]
    assert out["steps"][0]["reasons"] == ["the stage moved on (revision 3 → 5)"] and out["steps"][1]["reasons"] == ["after start still (the stage)"]
    assert out["stale"] == 2 and out["stale_seconds"] == 150.0
    # Mara's sheet changed; her references changed; the style changed
    story.profiles["prf_m"].versions[0].appearance = "blue coat"
    out = recipe_state(v, _reader(story, group_rev=4))
    why = out["steps"][0]["reasons"]
    assert "the references of @Mara changed" in why and "Mara v1's sheet changed" in why
    story.profiles["prf_m"].versions[0].appearance = "red coat"
    story.styles["sty_1"].fragment = "oil paint"
    assert recipe_state(v, _reader(story))["steps"][0]["reasons"] == ["the world style changed"]
    story.styles["sty_1"].fragment = "ink wash"
    # another frame used → the clip read the old one
    out = recipe_state(v.model_copy(update={"frame_asset_id": "ast_g"}), _reader(story))
    assert out["steps"][1]["state"] == "stale" and out["steps"][1]["reasons"] == ["the frame changed"]


def test_used_run_and_templates():
    v = ShotVersion(id="v1")
    out = recipe_state(v, _reader(_Story()))
    assert out["template"] == "i2v" and [(s["id"], s["state"]) for s in out["steps"]] == [("frame", "missing"), ("clip", "missing")]
    # the clay templates name every step; RC1: their waves are built (the route reads them from its graph), the start still waits for W3
    v = v.model_copy(update={"recipe": add_run(None, "clay1", "frame", [], RecipeRun(kind="t2i", outputs=["a1"]))})
    v.recipe.template = "clay1"
    rows = {s["id"]: s for s in recipe_state(v, _reader(_Story()))["steps"]}
    assert rows["frame"]["state"] == "fresh" and rows["plate"]["state"] == "missing" and rows["plate"]["wave"] is None
    assert [t.wave for t in TEMPLATES["clay1"].steps if t.id == "frame"] == ["CA5 (W3)"]
    assert set(TEMPLATES) == {"i2v", "stage", "clay1", "clay2", "dialogue"}
    # the run whose output is used decides, else the last; the history is capped
    r = None
    for i in range(9):
        r = add_run(r, "i2v", "frame", [], RecipeRun(kind="t2i", outputs=[f"a{i}"], stamps={"group:grp_m": 2 if i == 3 else 1}))
    assert len(r.step("frame").runs) == 6
    rows = recipe_state(ShotVersion(id="v1", frame_asset_id="a3", recipe=r), _reader(_Story(), group_rev=2))["steps"]
    assert rows[0]["state"] == "fresh" and rows[0]["outputs"] == ["a3"]


def test_the_coverage_of_05_s3_reaches_the_typed_recipes():
    """Every important part of a runnable step is a field of the recipe the job runs (scripts/settings_audit.py proves each field reaches
    the compiler, D60)."""
    models = {"t2i": T2I, "stage_shot": StageShot, "i2v": I2V}
    assert set(COVERAGE) == set(models)
    for kind, parts in COVERAGE.items():
        fields = set(models[kind].model_fields)
        for part, names in parts.items():
            missing = [n for n in names if n not in fields]
            assert not missing, f"{kind} · {part}: {missing} are not fields of the recipe"
    runnable = {t.id for tpl in TEMPLATES.values() for t in tpl.steps if t.wave is None}
    from loom2.shot_graph import CLAY_STEPS                                     # RC1: the clay steps' parts live in the final's records
    assert runnable - set(CLAY_STEPS) == {"frame", "clip", "lipsync"}


@pytest.mark.asyncio
async def test_jobs_for_a_shot_record_their_runs(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        rig.queue.load()
        await rig.queue.start()
        st = StoryStore(rig.ws)
        shot = st.create_shot("Gate")
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path)
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "a gate at dawn", "width": 64, "height": 64, "seeds": [3]},
                               origin=_origin(shot.id))[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        frame = done.result["asset_ids"][0]
        v = st.shot(shot.id).version("v1")
        run = v.recipe.step("frame").runs[0]
        assert v.recipe.template == "i2v" and run.job_id == job.id and run.outputs == [frame] and run.settings["prompt_text"] == "a gate at dawn" and run.seconds is not None
        job = rig.queue.submit({"kind": "i2v", "model_id": WAN, "start_asset": frame, "prompt_text": "the gate opens", "frames": 9, "fps": 16, "width": 832, "height": 480},
                               origin=_origin(shot.id, suite="animate"))[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        v = st.shot(shot.id).version("v1")
        clip = v.recipe.step("clip")
        assert clip.inputs == ["frame"] and clip.runs[0].stamps == {"frame": frame} and clip.runs[0].outputs == [done.result["clip_id"]]
        # a new version carries the plan and its history
        v2 = st.new_shot_version(shot.id).version()
        assert v2.recipe is not None and [s.id for s in v2.recipe.steps] == ["frame", "clip"]
    finally:
        await rig.close()


def test_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        assert [t["id"] for t in cl.get("/story/recipe-templates").json()] == ["i2v", "stage", "clay1", "clay2", "dialogue"]
        sh = cl.post("/story/shots", json={"name": "Gate"}).json()
        r = cl.get(f"/story/shots/{sh['id']}/recipe").json()
        assert r["version"] == "v1" and r["template"] == "i2v" and [s["state"] for s in r["steps"]] == ["missing", "missing"]
        assert cl.put(f"/story/shots/{sh['id']}/versions/v1/template", json={"template": "dialogue"}).status_code == 200
        r = cl.get(f"/story/shots/{sh['id']}/recipe").json()
        assert [s["id"] for s in r["steps"]] == ["voice", "frame", "clip", "lipsync"] and r["steps"][3]["experimental"]
        assert cl.put(f"/story/shots/{sh['id']}/versions/v1/template", json={"template": "nope"}).status_code == 422
        assert cl.get("/story/shots/sht_gone/recipe").status_code == 404
        assert cl.get(f"/story/shots/{sh['id']}/recipe", params={"version": "v9"}).status_code == 404


def test_rerun_recipe_and_the_plan():
    from loom2.shot_recipe import how_to_run, rerun_recipe, stale_plan
    settings = {"kind": "t2i", "seeds": [7], "style_id": "sty_1", "style_text": "ink wash", "loras": [{"model_id": "lora_old", "strength": 1.0}, {"model_id": "mine", "strength": 0.5}],
                "mentions": [{"group_id": "grp_m", "name": "Mara", "revision": 2, "asset_ids": ["a1"], "profile_id": "prf_m", "version": "v1", "lora": "lora_old", "composed": "x", "skipped": 1}]}
    run = RecipeRun(kind="t2i", settings=settings, stamps={"group:grp_m": 2}, outputs=["ast_f"])
    r = rerun_recipe(run, ShotVersion(id="v1"))
    m = r["mentions"][0]
    assert m["revision"] is None and m["asset_ids"] == [] and m["composed"] is None and m["version"] == "v1" and m["profile_id"] == "prf_m"   # the pin stays
    assert r["loras"] == [{"model_id": "mine", "strength": 0.5}] and r["style_text"] is None and r["seeds"] == [7]
    assert settings["mentions"][0]["revision"] == 2                                                          # the record is untouched
    clip = RecipeRun(kind="i2v", settings={"kind": "i2v", "start_asset": "ast_old"}, stamps={"frame": "ast_old"})
    assert rerun_recipe(clip, ShotVersion(id="v1", frame_asset_id="ast_new"))["start_asset"] == "ast_new"
    still = RecipeRun(kind="stage_shot", settings={"kind": "stage_shot", "passes": {"clay": "old"}})
    assert rerun_recipe(still, ShotVersion(id="v1"), {"clay": "new", "pose": "p"})["passes"] == {"clay": "new", "pose": "p"}
    assert [how_to_run(x) for x in (run, clip, still, RecipeRun(kind="i2v", settings={"guide": {"asset_id": "g"}}), RecipeRun(kind="inpaint"))] == ["server", "server", "passes", "stage", "manual"]
    # the plan: the frame first, the clip after it
    story = _Story()
    rec = add_run(None, "stage", "frame", [], RecipeRun(kind="stage_shot", settings={"kind": "stage_shot"}, stamps={"stage:stg_1": 3}, outputs=["ast_f"], seconds=30.0))
    rec = add_run(rec, "stage", "clip", ["frame"], RecipeRun(kind="i2v", settings={"kind": "i2v", "start_asset": "ast_f"}, stamps={"frame": "ast_f"}, outputs=["clp_1"], seconds=90.0))
    v = ShotVersion(id="v1", stage_id="stg_1", camera_id="cam_1", frame_asset_id="ast_f", clip_id="clp_1", recipe=rec)
    plan = stale_plan(v, _reader(story, stage_rev=6))
    assert [(p["id"], p["how"], p["after"]) for p in plan] == [("frame", "passes", []), ("clip", "server", ["frame"])]
    assert stale_plan(v, _reader(story)) == []


@pytest.mark.asyncio
async def test_run_stale_runs_the_frame_then_the_clip(tmp_path: Path, object_info: dict):
    """A reference group changes after the frame and clip were made: the frame and the clip after it are stale; Run stale (as the route
    queues it) makes the frame again with the group of now, its result becomes the version's frame, the clip follows from it by itself,
    and the recipe is fresh again."""
    from loom2.shot_recipe import rerun_recipe, stale_plan, used_run
    from loom2.stages import StageStore
    from loom2.story import FOR_SHOT
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        rig.queue.load()
        await rig.queue.start()
        g = groups.create("Mara · refs")
        a1 = rig.catalogue.ingest_file(_png(tmp_path / "m1.png"), move=False)
        groups.move([("asset", a1.id)], g.id)
        st = StoryStore(rig.ws)
        shot = st.create_shot("Gate")
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path and sp.inputs.refs_max > 0)
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "Mara at the gate", "width": 64, "height": 64, "seeds": [3],
                                "mentions": [{"group_id": g.id, "name": "Mara"}]}, origin=_origin(shot.id))[0]
        assert (await rig.wait(job.id)).status == "done"
        frame = st.shot(shot.id).version().frame_asset_id
        job = rig.queue.submit({"kind": "i2v", "model_id": WAN, "start_asset": frame, "prompt_text": "she turns", "frames": 9, "fps": 16, "width": 832, "height": 480},
                               origin=_origin(shot.id, suite="animate"))[0]
        assert (await rig.wait(job.id, timeout=60)).status == "done"
        reader = lambda: StampReader(stages=StageStore(rig.ws), groups=groups, story=st)   # noqa: E731
        v = st.shot(shot.id).version()
        assert [s["state"] for s in recipe_state(v, reader())["steps"]] == ["fresh", "fresh"]
        a2 = rig.catalogue.ingest_file(_png(tmp_path / "m2.png"), move=False)
        groups.move([("asset", a2.id)], g.id)                                                              # her references changed
        plan = stale_plan(v, reader())
        assert [(p["id"], p["how"]) for p in plan] == [("frame", "server"), ("clip", "server")]
        assert plan[0]["reasons"] == ["the references of @Mara changed"]
        old_clip = v.clip_id
        # what POST …/run-stale queues: the frame now, the clip in the chain
        jobs = rig.queue.submit(rerun_recipe(used_run(v.recipe.step("frame"), v), v),
                                origin=JobOrigin(suite="animate", surface=FOR_SHOT, ref=None, payload={"shot_id": shot.id, "version": "v1", "use": True, "chain": ["clip"]}))
        assert (await rig.wait(jobs[0].id)).status == "done"
        v = st.shot(shot.id).version()
        assert v.frame_asset_id != frame and v.frame_asset_id in v.recipe.step("frame").runs[-1].outputs
        assert a2.id in v.recipe.step("frame").runs[-1].settings["mentions"][0]["asset_ids"]                 # resolved against the group of now
        chained = [j for j in rig.queue.jobs.values() if j.recipe.get("kind") == "i2v" and j.recipe.get("start_asset") == v.frame_asset_id]
        assert len(chained) == 1 and chained[0].origin.payload["chain"] == []
        assert (await rig.wait(chained[0].id, timeout=60)).status == "done"
        v = st.shot(shot.id).version()
        assert v.clip_id != old_clip
        assert [s["state"] for s in recipe_state(v, reader())["steps"]] == ["fresh", "fresh"]
    finally:
        await rig.close()


def test_run_stale_route(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        sh = cl.post("/story/shots", json={"name": "Gate"}).json()
        r = cl.post(f"/story/shots/{sh['id']}/versions/v1/run-stale", json={"dry": True}).json()
        assert r == {"plan": [], "queued": [], "then": [], "elsewhere": [], "seconds": 0.0}
        assert cl.post("/story/shots/sht_gone/versions/v1/run-stale", json={}).status_code == 404
