"""proto01_UIcast CW6 (04 §3–4; D143): a place's set on its Cast version — *Build the set ▶* queues MoGe on the set picture, its landing
fits the set (a synthetic room relief ray-cast as MoGe gives it, scaled by the camera's height); the author's edits are guarded by the
profile's revision; the client's bake becomes the faces (Catalogue images, their seen and bad shares); *Fill ▶* fills the faces most seen
first, each on an Edit document with the bad texels selected and its material named, one after another (the fake engine); the place's
bench is Clay on its set from the picture's camera."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.place_sets import FILL_MIN, fill_mask, fill_order, fill_prompt, place_set_from_fit  # noqa: E402
from loom2.stages import PlaceSet, SetFace  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_ideas_cw1 import _picture  # noqa: E402
from test_set_fit_cw6 import cast  # noqa: E402
from test_set_things_d123 import _glb  # noqa: E402
from test_skeleton_bench_cs2 import _client  # noqa: E402

ROOM = {"x0": -2.5, "x1": 2.5, "z0": -5.0, "z1": 1.0, "height": 2.8}                  # 5 m × 6 m × 2.8 m


def relief(path: Path, scale: float = 0.7) -> None:
    """MoGe's relief of ROOM from near its front, at a scale short of the truth (D143: MoGe's ran 1.06–2× short)."""
    w, h = 96, 54
    pos, uv = cast(ROOM, (0.4, 1.6, 0.8), yaw=0.0, pitch=-8.0, fov=75.0, w=w, h=h)
    pos = pos * scale
    k = np.arange(w * h).reshape(h, w)
    a, b, c, d = k[:-1, :-1].ravel(), k[:-1, 1:].ravel(), k[1:, :-1].ravel(), k[1:, 1:].ravel()
    _glb(path, np.nan_to_num(pos, nan=0.0), uv, np.stack([a, c, b, b, c, d], -1).ravel())


def _png(arr: np.ndarray) -> tuple[str, bytes]:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    data = buf.getvalue()
    return hashlib.sha256(data).hexdigest(), data


def test_the_prompt_the_mask_and_the_order():
    named = fill_prompt("wall_left", "pale ochre plaster", "a farmhouse kitchen")
    assert named.startswith("Pale ochre plaster, seen straight on: its surface continued plain") and "farmhouse" not in named   # the material alone (the rig's floor)
    assert "no window" in fill_prompt("wall_left", "", "") and fill_prompt("wall_left", "", "").startswith("A wall")
    assert "no window" not in fill_prompt("facade_left", "", "an old town street", "street") and fill_prompt("facade_left", "", "x", "street").endswith("The place: x.")
    assert "no window" not in fill_prompt("wall_left", "", "a narrow alley", "corridor")                        # an alley's walls are building fronts
    cov = np.zeros((4, 4, 3), np.uint8)
    cov[:, 2:, 0] = 200                                                              # the right half seen …
    cov[0, 3, 1] = 255                                                               # … but one texel through a pixel 8 texels wide
    m = fill_mask(cov)
    assert m[:, :2].all() and not m[1:, 2:].any() and m[0, 3]
    ps = PlaceSet(kind="room", sizes={}, faces=[SetFace(id="floor", baked_asset_id="a", coverage_asset_id="b", bad=0.4), SetFace(id="wall_back", baked_asset_id="a", coverage_asset_id="b", bad=0.05),
                                                SetFace(id="ceiling", baked_asset_id="a", coverage_asset_id="b", bad=FILL_MIN / 2), SetFace(id="wall_left", baked_asset_id="a", coverage_asset_id="b", bad=0.6, filled=True)])
    assert fill_order(ps) == ["wall_back", "floor"]                                  # the most seen first; nothing to fill, or filled: left out
    assert fill_order(ps, ["floor"]) == ["floor"]
    assert fill_order(ps, ["wall_left"]) == ["wall_left"]                            # a filled face named: filled again from its bake


def test_a_fit_becomes_the_set(tmp_path: Path):
    from loom2.set_fit import fit_set
    from loom2.relief import glb_read, lens_of, mesh_arrays
    relief(tmp_path / "r.glb")
    pos, uv, _ = mesh_arrays(*glb_read(tmp_path / "r.glb"))
    f = fit_set(pos, uv, (lens_of(pos, uv) or {}).get("fov_x"), camera_height_m=1.6)
    assert f["kind"] == "room" and f["sizes"]["width"] == pytest.approx(5.0, rel=0.08)  # the short scale put right by the camera's height
    keep = PlaceSet(kind="room", sizes={}, parts={"ceiling": False}, faces=[SetFace(id="wall_left", material="pale ochre plaster")])
    ps = place_set_from_fit(f, "ast_pic", "ast_relief", keep)
    assert ps.kind == "room" and ps.parts == {"ceiling": False} and ps.sources[0].asset_id == "ast_pic" and ps.sources[0].relief_asset_id == "ast_relief"
    assert ps.sources[0].camera.pos[1] == pytest.approx(1.6, abs=0.01) and "front" in ps.sources[0].assumed
    assert [(x.id, x.material, x.texture_asset_id) for x in ps.faces] == [("wall_left", "pale ochre plaster", None)]   # the author's words kept; no bake yet


def test_the_set_routes(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        place = cl.post("/story/profiles", json={"name": "Kitchen", "cls": "place"}).json()
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        pid = place["id"]
        pic = _picture(cat, tmp_path, "kitchen", "an empty farmhouse kitchen")
        # the set picture is the place's reference slot; Build the set ▶ queues MoGe on it (the engine off: it waits)
        assert cl.post(f"/story/profiles/{pid}/versions/v1/set/fit", json={}).status_code == 422             # no picture yet
        assert cl.put(f"/story/profiles/{pid}/versions/v1/anim-ref", json={"asset_id": pic.id}).status_code == 200
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fit", json={"camera_height_m": 1.7})
        assert r.status_code == 200, r.text
        job = next(j for j in cl.get("/jobs").json()["items"] if j["id"] == r.json()["job_id"])
        assert job["recipe"]["kind"] == "image_to_set" and job["recipe"]["asset_id"] == pic.id
        assert job["origin"]["surface"] == "set_fit" and job["origin"]["payload"] == {"version": "v1", "from": pic.id, "camera_height_m": 1.7}
        assert cl.post(f"/story/profiles/{mara['id']}/versions/v1/set/fit", json={}).status_code == 422     # a character has no set
        # the relief lands: the set fitted, on the version
        from loom2.place_sets import fit_landed
        relief(tmp_path / "r.glb")
        qjob = svc.queue.jobs[job["id"]]
        fit_landed(svc.queue, qjob, "ast_relief", tmp_path / "r.glb")
        ps = cl.get(f"/story/profiles/{pid}").json()["versions"][0]["place_set"]
        assert ps["kind"] == "room" and ps["sources"][0]["asset_id"] == pic.id and ps["sources"][0]["camera"]["pos"][1] == pytest.approx(1.7, abs=0.01)
        assert qjob.result["set"]["kind"] == "room"
        # the author's edit, guarded by the profile's revision
        p = cl.get(f"/story/profiles/{pid}").json()
        ps["sizes"]["height"] = 3.1
        assert cl.put(f"/story/profiles/{pid}/versions/v1/set", json={"revision": p["revision"] - 1, "place_set": ps}).status_code == 409
        p = cl.put(f"/story/profiles/{pid}/versions/v1/set", json={"revision": p["revision"], "place_set": ps}).json()
        assert p["versions"][0]["place_set"]["sizes"]["height"] == 3.1
        # the bake: a texture and a coverage a face (the floor's left half unseen; the back wall all seen)
        tex = np.full((40, 60, 4), 180, np.uint8)
        tex[:, :30, 3] = 0
        cov = np.zeros((40, 60, 3), np.uint8)
        cov[:, 30:, 0] = 220
        full = np.zeros((40, 60, 3), np.uint8)
        full[..., 0] = 230
        blobs = {}
        for name, arr in (("tex", tex), ("cov", cov), ("full", full)):
            sha, data = _png(arr)
            assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
            blobs[name] = sha
        body = {"key": "k1", "faces": [{"id": "floor", "image": blobs["tex"], "coverage": blobs["cov"], "texel_m": 0.01, "seen": 0.5, "bad": 0.5},
                                       {"id": "wall_back", "image": blobs["tex"], "coverage": blobs["full"], "texel_m": 0.01, "seen": 1.0, "bad": 0.0}]}
        r = cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json=body)
        assert r.status_code == 200, r.text
        ps = r.json()["versions"][0]["place_set"]
        floor = next(f for f in ps["faces"] if f["id"] == "floor")
        assert ps["baked_key"] == "k1" and floor["texture_asset_id"] == floor["baked_asset_id"] and floor["coverage_asset_id"] and floor["bad"] == 0.5
        assert cat.get(floor["baked_asset_id"]).parents == [pic.id]                                       # lineage: set-bake ← the picture
        # Fill ▶: the floor (the wall has nothing to fill) on a document with its left half selected, the material named
        ps["faces"] = [{**f, "material": "worn terracotta tiles"} if f["id"] == "floor" else f for f in ps["faces"]]
        p = cl.get(f"/story/profiles/{pid}").json()
        cl.put(f"/story/profiles/{pid}/versions/v1/set", json={"revision": p["revision"], "place_set": ps})
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={})
        assert r.status_code == 200, r.text
        assert r.json()["faces"] == ["floor"]
        fj = svc.queue.jobs[r.json()["job_id"]]
        assert fj.origin.surface == "set_fill" and fj.origin.payload["face"] == "floor" and fj.origin.payload["rest"] == []
        assert fj.recipe["prompt_text"].startswith("Worn terracotta tiles, seen straight on")
        od = svc.require_documents().get(fj.origin.payload["document_id"])
        assert od.selection[:, :30].all() and not od.selection[:, 30:].any()
        assert next(f for f in cl.get(f"/story/profiles/{pid}").json()["versions"][0]["place_set"]["faces"] if f["id"] == "floor")["fill_job_id"] == fj.id
        assert cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={}).status_code == 409          # one Fill at a time
        from loom2.place_sets import fill_failed
        fill_failed(svc.queue, fj, "cancelled")
        assert next(f for f in cl.get(f"/story/profiles/{pid}").json()["versions"][0]["place_set"]["faces"] if f["id"] == "floor")["fill_job_id"] is None
        # the place's bench: its set bound, a 1.75 m figure, the picture's camera
        r = cl.post("/stages/bench", json={"profile_id": pid})
        assert r.status_code == 200, r.text
        st = r.json()["stage"]
        s = st["objects"][0]
        assert s["kind"] == "set" and s["preset"] == "built" and s["profile_id"] == pid and s["place_set"]["kind"] == "room"
        assert st["objects"][1]["kind"] == "mannequin" and st["cameras"][0]["pos"] == ps["sources"][0]["camera"]["pos"]
        # a new version takes the set; the set cleared
        assert cl.post(f"/story/profiles/{pid}/versions", json={}).json()["versions"][1]["place_set"]["kind"] == "room"
        p = cl.delete(f"/story/profiles/{pid}/versions/v1/set").json()
        assert p["versions"][0]["place_set"] is None
        assert StoryStore(ws).profile(pid).version("v2").place_set is not None


async def test_the_fill_runs_face_after_face(tmp_path: Path, object_info: dict, monkeypatch):
    """The Fill chain on the fake engine: two faces, the most seen first; each landing flattens its document into the face's texture
    (lineage set-fill ← the bake) and queues the next."""
    import test_lifecycle
    from loom2.place_sets import queue_fill
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        from loom2.groups import GroupStore
        store = StoryStore(rig.ws)
        p = store.create_profile("Kitchen", "place", GroupStore(rig.ws, rig.catalogue))
        faces = []
        for fid, bad_cols in (("floor", 40), ("wall_left", 10)):
            tex = np.full((32, 48, 4), 150, np.uint8)
            tex[:, :bad_cols, 3] = 0
            cov = np.zeros((32, 48, 3), np.uint8)
            cov[:, bad_cols:, 0] = 220
            for name, arr in (("t", tex), ("c", cov)):
                Image.fromarray(arr).save(tmp_path / f"{fid}_{name}.png")
            t = rig.catalogue.ingest_file(tmp_path / f"{fid}_t.png", kind="image", move=False, suite="story")
            c = rig.catalogue.ingest_file(tmp_path / f"{fid}_c.png", kind="image", move=False, suite="story")
            faces.append(SetFace(id=fid, texture_asset_id=t.id, baked_asset_id=t.id, coverage_asset_id=c.id, bad=bad_cols / 48))
        store.set_place_set(p.id, "v1", PlaceSet(kind="room", sizes={}, faces=faces))
        rig.queue.load()
        await rig.queue.start()
        order = fill_order(store.profile(p.id).version("v1").place_set)
        assert order == ["wall_left", "floor"]
        first = await queue_fill(rig.queue, p.id, "v1", order)                  # V22: submitted on the loop, staged until the face names it
        j = await rig.wait(first.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        nxt = rig.queue.jobs[j.result["next_job_id"]]
        j2 = await rig.wait(nxt.id, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        got = {f.id: f for f in store.profile(p.id).version("v1").place_set.faces}
        assert all(f.filled and f.fill_job_id is None and f.texture_asset_id != f.baked_asset_id for f in got.values())
        assert rig.catalogue.get(got["floor"].texture_asset_id).parents == [got["floor"].baked_asset_id]
    finally:
        await rig.close()
