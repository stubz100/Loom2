"""D93 phase B · the live character sheet and the version chip: (B4) a profile version holds appearance, outfit, bound colours and marks
(schema 2; a schema-1 stub reads as the appearance without the file being rewritten until the next save); the PATCH route takes them with
the revision guard (`stub` still taken as the appearance, the label editable on a final version); one composition rule (the shared cases
in fixtures/sheet_compose.json) is what Expand, the LoRA captions, a mention's note and a linked subject carry — the subject composed at
resolve from the sheet and the card's per-shot override, stamped on the mention; (B5) the mention's version picks the sheet, the
references and the LoRA of that version (a costume), and a version has a label."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.graphs import effective_params, serialize_prompt  # noqa: E402
from loom2.mentions import resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import T2I, Mention, SubjectShot, TrainLora  # noqa: E402
from loom2.story import PROFILE_SCHEMA_VERSION, Profile, ProfileVersion, StoryStore, compose_sheet, plan_expand  # noqa: E402
from loom2 import trainer as T  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402
from test_lifecycle import Rig  # noqa: E402

TESTS = Path(__file__).resolve().parent
CASES = json.loads((TESTS / "fixtures" / "sheet_compose.json").read_text(encoding="utf-8"))["cases"]
KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max == 4 and s.inputs.bind_refs)
DEV = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and s.sampling.json_prompt and s.inputs.refs_max >= 6)   # the D93 rig turned its default off: the tests ask for the binding
SHEET = {"appearance": "Mara, a wiry woman, cropped black hair", "outfit": "a long grey coat", "colours": [{"hex": "#c0392b", "object": "rain jacket"}], "marks": "a scar over the left eyebrow"}
COMPOSED = "Mara, a wiry woman, cropped black hair, wearing a long grey coat, #C0392B rain jacket, a scar over the left eyebrow"


# ---- the rule --------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("c", CASES, ids=[c["case"] for c in CASES])
def test_the_composition_rule(c: dict):
    v = ProfileVersion.model_validate({"id": "v1", "group_id": "g", **c["sheet"]})
    shot = SubjectShot(**c["shot"]) if c["shot"] else None
    assert compose_sheet(v, shot, c["name"], c.get("cls", "character")) == c["out"]


# ---- the record: migration on read, fields, PATCH ---------------------------------------------------------------------------------------
V1 = {"schema_version": 1, "id": "prf_8dc86277", "name": "char01", "cls": "character", "current": "v1",
      "versions": [{"id": "v1", "state": "open", "group_id": "grp_f81311f5", "candidates_group_id": None, "hero_asset_id": None, "stub": "char01, a diver.",
                    "trigger": None, "lora": None, "derived_from": None, "created_at": "2026-10-16T21:25:10+00:00", "locked_at": None}],
      "voice_id": None, "revision": 0, "created_at": "2026-10-16T21:25:10+00:00", "updated_at": "2026-10-16T21:25:10+00:00"}


def test_a_schema_1_stub_reads_as_the_appearance_and_the_file_waits_for_the_next_save(tmp_path: Path):
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    g = groups.create("char01 · v1")
    rec = {**V1, "versions": [{**V1["versions"][0], "group_id": g.id}]}
    st.profiles_dir.mkdir(parents=True, exist_ok=True)
    path = st.profile_path(rec["id"])
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    before = path.read_bytes()
    p = st.profile(rec["id"])
    v = p.version()
    assert p.schema_version == PROFILE_SCHEMA_VERSION == 2 and v.appearance == "char01, a diver." and v.label == "v1" and v.outfit == "" and v.colours == []
    assert v.stub == "char01, a diver" and "stub" not in v.model_dump()                                     # the composed clause; no stub in the new shape
    assert [x.id for x in st.profiles()] == [rec["id"]] and path.read_bytes() == before                      # reads write nothing
    p2 = st.patch_profile(p.id, {"revision": 0, "versions": [{"id": "v1", "outfit": "a yellow wetsuit"}]})
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == 2 and "stub" not in on_disk["versions"][0] and on_disk["versions"][0]["appearance"] == "char01, a diver."
    assert on_disk["versions"][0]["outfit"] == "a yellow wetsuit" and p2.revision == 1
    # a mention of it carries the composed sheet on its references' note
    hero = cat.ingest_file(_png(tmp_path / "h.png")).id
    groups.move([("asset", hero)], g.id)
    out = resolve_mentions(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="@char01 at the pier", mentions=[Mention(profile_id=p.id, name="char01")]), groups, cat, 4, st)
    assert out.refs[0].note == "char01, a diver, wearing a yellow wetsuit"


def test_the_sheet_round_trips_through_the_routes_with_revisions(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        hero = svc.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, **SHEET, "label": "rain gear"}).json()
        v = p["versions"][0]
        assert p["schema_version"] == 2 and v["label"] == "rain gear" and v["colours"] == [{"hex": "#c0392b", "object": "rain jacket"}] and v["marks"] == SHEET["marks"]
        assert cl.post("/story/profiles", json={"name": "Bad", "colours": [{"hex": "red", "object": "coat"}]}).status_code == 422      # a colour is a hex code
        assert cl.post("/story/profiles", json={"name": "Old", "stub": "Old, a sailor"}).json()["versions"][0]["appearance"] == "Old, a sailor"   # the schema-1 word
        # PATCH: each field, with the revision; a stale one is refused; `stub` is the appearance
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"], "versions": [{"id": "v1", "outfit": "a yellow oilskin", "colours": [{"hex": "#F2A93B", "object": "oilskin"}, {"hex": "#1E8449", "object": ""}]}]})
        assert r.status_code == 200 and r.json()["revision"] == p["revision"] + 1
        v = r.json()["versions"][0]
        assert v["outfit"] == "a yellow oilskin" and [c["hex"] for c in v["colours"]] == ["#F2A93B", "#1E8449"] and v["appearance"] == SHEET["appearance"]
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"], "versions": [{"id": "v1", "marks": "x"}]}).status_code == 409
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": r.json()["revision"], "versions": [{"id": "v1", "stub": "Mara, older", "colours": [{"hex": "#zzzzzz"}]}]})
        assert r.status_code == 422                                                                              # a bad colour: nothing saved
        cur = cl.get(f"/story/profiles/{p['id']}").json()
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": cur["revision"], "versions": [{"id": "v1", "stub": "Mara, older", "label": ""}]})
        assert r.json()["versions"][0]["appearance"] == "Mara, older" and r.json()["versions"][0]["label"] == "v1"   # a blank label is the id
        # a new version copies the sheet and gets a label of its own; a final one keeps its sheet but can be renamed
        p2 = cl.post(f"/story/profiles/{p['id']}/versions").json()
        v2 = p2["versions"][1]
        assert v2["id"] == "v2" and v2["label"] == "v2" and v2["outfit"] == "a yellow oilskin" and v2["appearance"] == "Mara, older" and len(v2["colours"]) == 2
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/lock").status_code == 200
        cur = cl.get(f"/story/profiles/{p['id']}").json()
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": cur["revision"], "versions": [{"id": "v1", "outfit": "x"}]}).status_code == 422
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": cur["revision"], "versions": [{"id": "v1", "label": "rain gear"}]})
        assert r.status_code == 200 and r.json()["versions"][0]["label"] == "rain gear"


# ---- the composition where the sheet is read ------------------------------------------------------------------------------------------
def _mara(tmp_path: Path):
    ws, cat, groups, _ = _setup(tmp_path)
    ids = [cat.ingest_file(_png(tmp_path / f"c{i}.png")).id for i in range(6)]
    st = StoryStore(ws)
    p = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], **SHEET, label="rain gear")
    groups.move([("asset", ids[1])], p.version().group_id)
    return ws, cat, groups, ids, st, p


def test_expand_and_the_lora_captions_use_the_composed_sheet(tmp_path: Path, object_info: dict):
    _, _, _, _, st, p = _mara(tmp_path)
    planned = plan_expand(p, p.version(), "npc", "full", width=960, height=544, group_id="g")
    assert planned[0][0]["prompt_text"].startswith(COMPOSED + ". ")
    rig = Rig(tmp_path / "rig", object_info)
    try:
        from test_train_lora_lt2 import _cast as lora_cast, _trainable_base
        store, groups, prof, v, ids = lora_cast(rig, 4)
        store.patch_profile(prof.id, {"versions": [{"id": v.id, "outfit": "a grey coat", "colours": [{"hex": "#c0392b", "object": "scarf"}]}]})
        recipe = TrainLora(profile_id=prof.id, version=v.id, model_id=_trainable_base(rig.roster), trigger="mara_1a2b", steps=300)
        T.materialise(rig.ws, rig.catalogue, groups, store, recipe, tmp_path / "set")
        hero_caption = next((tmp_path / "set").glob(f"*_{ids[0]}.txt")).read_text(encoding="utf-8")
        assert hero_caption == "mara_1a2b, Mara, a wiry courier in a long grey coat, wearing a grey coat, #C0392B scarf"
    finally:
        import asyncio
        asyncio.run(rig.close())


def _linked(model: str, p: Profile, **mention) -> T2I:
    tree = {"scene": "a quay at dusk", "subjects": [{"description": "Mara, a copy of an old stub", "position": "left", "action": "running"}, {"description": "a gull", "position": "top"}]}
    return T2I(model_id=model, prompt_mode="tree", prompt_json=tree, mentions=[Mention(profile_id=p.id, name="Mara", subject=0, **mention)])


def test_a_linked_subject_is_composed_at_resolve_and_stamped(tmp_path: Path):
    _, cat, groups, ids, st, p = _mara(tmp_path)
    out = resolve_mentions(_linked(KLEIN, p, shot=SubjectShot(outfit="", note="soaked, hood up")), groups, cat, 4, st)
    sub = out.prompt_json["subjects"][0]
    assert sub == {"description": f"{COMPOSED}, soaked, hood up", "position": "left", "action": "running"}       # the card's own words give way to the sheet
    assert out.prompt_json["subjects"][1]["description"] == "a gull"                                            # a free subject keeps its words
    m = out.mentions[0]
    assert m.composed == sub["description"] and m.version == "v1" and m.shot.note == "soaked, hood up" and m.revision is not None   # lineage
    text, _ = serialize_prompt(out, registry.SPECS[KLEIN])
    assert f"Mara (reference images 1–2), a wiry woman, cropped black hair, wearing a long grey coat, #C0392B rain jacket" in text   # T8: bound and composed
    ep = effective_params(out)
    assert ep["serialized_prompt"] == text and ep["bindings"][0]["version"] == "v1"
    # the shot's outfit replaces the sheet's; dev's JSON carries the composed description in the field
    out = resolve_mentions(_linked(DEV, p, shot=SubjectShot(outfit="a yellow oilskin")).model_copy(update={"bind_refs": True}), groups, cat, registry.SPECS[DEV].inputs.refs_max, st)
    tree = json.loads(serialize_prompt(out, registry.SPECS[DEV])[0])
    assert tree["subjects"][0]["description"] == "Mara, a wiry woman, cropped black hair, wearing a yellow oilskin, #C0392B rain jacket, a scar over the left eyebrow"
    assert tree["subjects"][0]["reference"] == "reference images 1–2"
    # a stored (stamped) recipe is not composed again: a later Cast edit does not change what it re-runs
    st.patch_profile(p.id, {"versions": [{"id": "v1", "outfit": "a red dress"}]})
    again = resolve_mentions(out, groups, cat, 4, st)
    assert again.prompt_json == out.prompt_json
    # … while a fresh submit follows the edit (the panel stores the link, not a copy)
    fresh = resolve_mentions(_linked(KLEIN, p), groups, cat, 4, st)
    assert "wearing a red dress" in fresh.prompt_json["subjects"][0]["description"]


def test_the_version_on_the_mention_picks_its_sheet_references_and_lora(tmp_path: Path):
    _, cat, groups, ids, st, p = _mara(tmp_path)
    p = st.new_version(p.id, groups)                                                                             # v2: a copy, current
    v2 = p.version("v2")
    st.patch_profile(p.id, {"versions": [{"id": "v2", "label": "winter", "outfit": "a padded parka", "colours": []}]})
    groups.move([("asset", ids[4])], v2.group_id)
    st.set_version_lora(p.id, "v1", "lora_v1abc", "mara_v1")
    from types import SimpleNamespace
    from loom2.loras import model_base
    roster = SimpleNamespace(trained={"lora_v1abc": {"base": model_base(KLEIN)}})                               # v1 has a trained LoRA for this model
    current = resolve_mentions(_linked(KLEIN, p), groups, cat, 4, st, roster)                                   # no version: the current one (v2)
    assert current.loras == [] and current.mentions[0].lora_available is None
    assert current.mentions[0].version == "v2" and current.mentions[0].group_id == v2.group_id
    assert "wearing a padded parka" in current.prompt_json["subjects"][0]["description"] and "#C0392B" not in current.prompt_json["subjects"][0]["description"]
    assert {r.mention for r in current.refs} == {v2.group_id} and ids[4] in [r.asset_id for r in current.refs]
    pinned = resolve_mentions(_linked(KLEIN, p, version="v1"), groups, cat, 4, st, roster)                      # the chip: v1 (rain gear)
    m = pinned.mentions[0]
    assert m.version == "v1" and m.group_id == p.version("v1").group_id and [r.asset_id for r in pinned.refs] == [ids[0], ids[1]]
    assert pinned.prompt_json["subjects"][0]["description"] == COMPOSED and m.composed == COMPOSED
    assert m.lora == m.lora_available == "lora_v1abc" and [l.model_id for l in pinned.loras] == ["lora_v1abc"]     # the LoRA follows the version
    with pytest.raises(ValueError, match="no version v9"):
        resolve_mentions(_linked(KLEIN, p, version="v9"), groups, cat, 4, st)


def test_the_preview_route_shows_the_composed_subject(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        hero = app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, **SHEET}).json()
        pv = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "tree", "prompt_json": {"subjects": [{"position": "left"}]},
                                                           "mentions": [{"profile_id": p["id"], "name": "Mara", "subject": 0, "shot": {"note": "laughing"}}]}}).json()
        assert pv["mentions"][0]["composed"] == f"{COMPOSED}, laughing" and pv["mentions"][0]["shot"] == {"outfit": "", "note": "laughing"}
        assert f"Mara (reference image 1), {COMPOSED[len('Mara, '):]}, laughing" in pv["serialized_prompt"]
        assert pv["bindings"][0]["version"] == "v1"
