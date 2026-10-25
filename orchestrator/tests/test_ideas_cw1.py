"""proto01_UIcast CW1–CW2 (D136 U1–U4; 06 §2.1–2.2): ideas in their own store — a name and a sheet read from a prompt; *Prototype ▸*
copies the picture (its page keeps it); variants added and removed; a revision guards the edits; *Make the clay ▶* on a character's
variant runs the A-pose picture, the fit and the shell one after another (the fake engine); *Keep ▶* makes a Cast profile or a new
version with the hero, the drafted sheet, the clay and `from_idea`; results made for an idea are listed on it; a failed step says so."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.ideas import IdeaStore, draft_sheet, name_from_prompt  # noqa: E402

from test_skeleton_bench_cs2 import _client  # noqa: E402

PROMPT = "A woman in a yellow raincoat standing on a quay, cinematic light"


def test_a_name_and_a_sheet_from_the_prompt():
    assert name_from_prompt(PROMPT) == "woman in a yellow raincoat"
    assert draft_sheet(PROMPT) == {"appearance": "woman", "outfit": "a yellow raincoat"}
    assert draft_sheet("an old fisherman wearing oilskins and a knitted cap, at the harbour") == {"appearance": "old fisherman", "outfit": "oilskins and a knitted cap"}
    assert name_from_prompt("the young king standing in a hall") == "young king"                       # "king" is no verb
    assert name_from_prompt("", "prop") == "prop idea" and draft_sheet("") == {}


def _picture(cat, tmp_path: Path, name: str, prompt: str | None = None):
    from PIL import Image
    src = tmp_path / f"{name}.png"
    Image.new("RGB", (64, 48), (120, 120, 120)).save(src)
    return cat.ingest_file(src, kind="image", move=False, suite="generate", prompt_text=prompt, model_id="flux2_klein_9b", seed=7)


def test_the_idea_routes(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        _, cat, _ = svc.require_project()
        groups = svc.require_groups()
        a, b = _picture(cat, tmp_path, "a", PROMPT), _picture(cat, tmp_path, "b", "a woman in a green coat")
        page = groups.create("Image results")
        groups.move([("asset", a.id)], page.id)
        # Prototype ▸ New character idea: the picture copied, the name from its prompt
        idea = cl.post("/story/ideas", json={"cls": "character", "asset_id": a.id}).json()
        assert idea["name"] == "woman in a yellow raincoat" and len(idea["variants"]) == 1
        v1 = idea["variants"][0]
        assert v1["asset_id"] != a.id and idea["focus"] == v1["id"]
        assert v1["made_from"] == {"asset_id": a.id, "prompt": PROMPT, "model": "flux2_klein_9b", "seed": 7, "for_idea": None}
        assert groups.parent[("asset", a.id)] == page.id and groups.parent[("asset", v1["asset_id"])] == idea["group_id"]   # copied, not moved
        assert groups.groups[idea["group_id"]].name == "woman in a yellow raincoat · idea"
        # Add to ‹idea›: a second variant, in focus; a stale edit refused; a rename names the page too
        idea = cl.post(f"/story/ideas/{idea['id']}/variants", json={"asset_id": b.id}).json()
        v2 = idea["variants"][1]
        assert idea["focus"] == v2["id"]
        assert cl.patch(f"/story/ideas/{idea['id']}", json={"revision": idea["revision"] - 1, "name": "x"}).status_code == 409
        idea = cl.patch(f"/story/ideas/{idea['id']}", json={"revision": idea["revision"], "name": "Rain girl", "focus": v1["id"], "variants": [{"id": v2["id"], "note": "the green one"}]}).json()
        assert idea["name"] == "Rain girl" and idea["focus"] == v1["id"] and idea["variants"][1]["note"] == "the green one"
        assert groups.groups[idea["group_id"]].name == "Rain girl · idea"
        assert cl.post("/story/ideas", json={"cls": "prop"}).json()["name"] == "prop idea"
        assert len(cl.get("/story/ideas").json()["items"]) == 2
        # Make the clay ▶: the A-pose picture's job from the variant (the engine is off: it waits in the queue); not twice; not on a prop
        r = cl.post(f"/story/ideas/{idea['id']}/variants/{v1['id']}/clay")
        assert r.status_code == 200, r.text
        job = next(j for j in cl.get("/jobs").json()["items"] if j["id"] == r.json()["job_id"])
        assert job["origin"]["surface"] == "idea_clay" and job["origin"]["payload"] == {"variant": v1["id"], "step": "aref"}
        assert job["recipe"]["refs"][0]["asset_id"] == v1["asset_id"] and "A-pose" in job["recipe"]["prompt_text"] and job["recipe"]["prompt_text"].startswith("woman")
        assert r.json()["idea"]["variants"][0]["clay"]["step"] == "drawing"
        assert cl.post(f"/story/ideas/{idea['id']}/variants/{v1['id']}/clay").status_code == 409
        from loom2.ideas import clay_failed
        clay_failed(svc.queue, svc.queue.jobs[job["id"]], "the engine stopped")                         # the queue's hook when a step's job fails or is cancelled
        failed = cl.get(f"/story/ideas/{idea['id']}").json()["variants"][0]["clay"]
        assert failed["step"] == "failed" and failed["error"] == "the engine stopped" and failed["job_id"] is None
        prop = next(i for i in cl.get("/story/ideas").json()["items"] if i["cls"] == "prop")
        prop = cl.post(f"/story/ideas/{prop['id']}/variants", json={"asset_id": b.id}).json()
        assert cl.post(f"/story/ideas/{prop['id']}/variants/{prop['variants'][0]['id']}/clay").status_code == 422
        # Keep ▶: a new character from the variant — the hero a copy, the sheet drafted, from_idea; then a new version of it
        r = cl.post(f"/story/ideas/{idea['id']}/keep", json={"variant_id": v1["id"]})
        assert r.status_code == 200, r.text
        p, idea = r.json()["profile"], r.json()["idea"]
        ver = p["versions"][0]
        assert p["name"] == "Rain girl" and p["cls"] == "character" and ver["appearance"] == "woman" and ver["outfit"] == "a yellow raincoat"
        assert ver["hero_asset_id"] not in (a.id, v1["asset_id"]) and ver["from_idea"] == {"idea_id": idea["id"], "variant_id": v1["id"]}
        assert groups.parent[("asset", v1["asset_id"])] == idea["group_id"]                               # the variant stays on the idea's page
        assert [k["profile_id"] for k in idea["kept"]] == [p["id"]]
        r = cl.post(f"/story/ideas/{idea['id']}/keep", json={"variant_id": v2["id"], "profile_id": p["id"]})
        assert r.status_code == 200, r.text
        p2 = r.json()["profile"]
        assert [v["id"] for v in p2["versions"]] == ["v1", "v2"] and p2["current"] == "v2"
        assert p2["versions"][1]["from_idea"]["variant_id"] == v2["id"] and p2["versions"][1]["appearance"] == "woman"
        assert cl.post(f"/story/ideas/{prop['id']}/keep", json={"variant_id": prop["variants"][0]["id"], "profile_id": p["id"]}).status_code == 422   # a prop idea is no character
        # a variant removed; the idea deleted — its page stays in the album
        idea = cl.delete(f"/story/ideas/{idea['id']}/variants/{v2['id']}").json()
        assert [v["id"] for v in idea["variants"]] == [v1["id"]]
        assert cl.delete(f"/story/ideas/{idea['id']}").status_code == 200
        assert cl.get(f"/story/ideas/{idea['id']}").status_code == 404 and idea["group_id"] in groups.groups


async def test_make_the_clay_runs_the_chain(tmp_path: Path, object_info: dict, monkeypatch):
    """The whole chain on the fake engine: the A-pose picture (onto the idea's page) → the fit → the shell, the variant's clay at each step;
    then Keep ▶ carries it onto the version (the A-pose picture copied as its animation reference, the body, the shell). CW2: a result
    made for the idea is listed on it."""
    import test_lifecycle
    from loom2.groups import GroupStore
    from loom2.ideas import FOR_IDEA, keep, plan_clay
    from loom2.engine import finishers
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    monkeypatch.setattr(finishers, "stand_upright", lambda path: [0.0, 0.0, 0.0])
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        src = _picture(rig.catalogue, tmp_path, "mara", PROMPT)
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        store = IdeaStore(rig.ws)
        idea = store.create("character", groups, src.id)
        v = idea.variants[0]
        rig.queue.load()
        await rig.queue.start()
        recipe, origin = plan_clay(idea, v, "full", width=256, height=144)
        first = rig.queue.submit(recipe, origin=origin)[0]
        store.set_clay(idea.id, v.id, step="drawing", job_id=first.id)
        j = await rig.wait(first.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        aref = j.result["asset_ids"][0]
        assert groups.parent[("asset", aref)] == idea.group_id                                           # the A-pose picture on the idea's page
        for step in ("fit", "shell"):
            nxt = next(x for x in rig.queue.jobs.values() if x.origin and x.origin.payload and x.origin.payload.get("step") == step)
            j = await rig.wait(nxt.id, timeout=60)
            assert j.status == "done", (step, j.error, j.log_tail[-5:])
        clay = store.get(idea.id).variant(v.id).clay
        assert clay.step == "done" and clay.anim_ref_asset_id == aref and clay.body is not None and clay.body_points and clay.shell_asset_id
        assert rig.catalogue.get(clay.shell_asset_id).params.get("upright_deg") is None                  # front-on, as a shell is made
        p, idea = keep(rig.ws, groups, idea.id, v.id)
        ver = p.version()
        assert ver.anim_ref_asset_id and ver.anim_ref_asset_id != aref and ver.body_fit_from == ver.anim_ref_asset_id
        assert ver.body == clay.body and ver.shell_asset_id == clay.shell_asset_id and ver.shell_from == ver.anim_ref_asset_id
        # CW2: Image's For chip on the idea — the result is listed on it, not a variant
        made = rig.queue.submit({"kind": "t2i", "model_id": recipe["model_id"], "prompt_mode": "text", "prompt_text": "a woman in a red coat", "width": 256, "height": 144, "seeds": [3]},
                                origin={"suite": "generate", "surface": "results", "ref": None, "payload": {FOR_IDEA: idea.id}})[0]
        j = await rig.wait(made.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        after = store.get(idea.id)
        assert after.made_for == j.result["asset_ids"] and len(after.variants) == 1
        assert rig.catalogue.get(after.made_for[0]).origin.payload[FOR_IDEA] == idea.id               # the lineage on the asset too
    finally:
        await rig.close()
