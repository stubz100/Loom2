"""D170 (E46, the market walk's M12): a street's fronts seen more than 45° off square are the Fill's, and a facade's Fill paints a flat
elevation of its material, the elevation first.

- a facade's texel under a cosine of 0.7 counts as unseen; every other face keeps 0.05 (stage/setBake.ts unseenCos is the twin);
- the Fill plan masks a facade by its own cosine;
- the lead: "A flat elevation of ‹material›, seen square on …"; unnamed, the noun and the place's words; a room's and a road's unchanged.
"""
import numpy as np


def test_a_facade_seen_off_square_is_the_fills():
    from loom2.place_sets import FACADE_COS, UNSEEN_COS, fill_mask, unseen_cos
    assert unseen_cos("facade_right") == unseen_cos("facade_left") == FACADE_COS == 0.7
    assert unseen_cos("road") == unseen_cos("wall_left") == unseen_cos("floor") == unseen_cos("end") == UNSEEN_COS
    cov = np.zeros((2, 4, 3), np.uint8)
    cov[:, :, 0] = [10, 100, 160, 230]                                   # cosines 0.04, 0.39, 0.63, 0.90, every pixel fine (green 0)
    assert fill_mask(cov).tolist() == [[True, False, False, False]] * 2
    assert fill_mask(cov, unseen_cos("facade_left")).tolist() == [[True, True, True, False]] * 2   # E46's band (0.35–0.64) included
    cov[0, 3, 1] = 255                                                   # a coarse pixel is the Fill's at any angle
    assert fill_mask(cov, unseen_cos("facade_left"))[0, 3]


def test_a_facade_is_painted_as_an_elevation():
    from loom2.place_sets import fill_prompt
    named = fill_prompt("facade_right", "Fish market stalls: counters of fish on ice, crates below, lamps above", "a covered market hall", "street")
    assert named.startswith("A flat elevation of fish market stalls: counters of fish on ice, crates below, lamps above, seen square on — no perspective")
    assert "no vanishing point" in named and "hall" not in named                               # a named material is the whole subject
    unnamed = fill_prompt("facade_left", "", "an old town street", "street")
    assert unnamed.startswith("A flat elevation of the buildings' fronts, seen square on") and unnamed.endswith("The place: an old town street.")
    assert fill_prompt("facade_left", "UPVC shopfronts", "", "street").startswith("A flat elevation of UPVC shopfronts")   # an acronym kept
    assert "elevation" not in fill_prompt("road", "", "x", "street") and "elevation" not in fill_prompt("wall_left", "", "x", "corridor")
    assert fill_prompt("wall_left", "", "", "room").startswith("A wall, seen straight on: its surface continued plain")


def test_the_fill_masks_a_facade_by_its_own_cosine(tmp_path):
    """Through the routes: a facade and a road baked with the same coverage (half unseen, half seen at a cosine of 0.47) — the
    facade's Fill selects the whole face and paints an elevation; the road's only its unseen half."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_ideas_cw1 import _picture
    from test_place_sets_cw6 import _png, relief
    from test_skeleton_bench_cs2 import _client
    from loom2.place_sets import fit_landed
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        _, cat, _ = svc.require_project()
        pid = cl.post("/story/profiles", json={"name": "Fish market", "cls": "place"}).json()["id"]
        pic = _picture(cat, tmp_path, "market", "a fish market")
        assert cl.put(f"/story/profiles/{pid}/versions/v1/anim-ref", json={"asset_id": pic.id}).status_code == 200
        job = cl.post(f"/story/profiles/{pid}/versions/v1/set/fit", json={}).json()["job_id"]
        relief(tmp_path / "r.glb")
        fit_landed(svc.queue, svc.queue.jobs[job], "ast_relief", tmp_path / "r.glb")
        tex = np.full((40, 60, 4), 180, np.uint8)
        tex[:, :30, 3] = 0
        cov = np.zeros((40, 60, 3), np.uint8)
        cov[:, 30:, 0] = 120
        sha_t, data_t = _png(tex)
        sha_c, data_c = _png(cov)
        for sha, data in ((sha_t, data_t), (sha_c, data_c)):
            assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
        face = lambda fid: {"id": fid, "image": sha_t, "coverage": sha_c, "texel_m": 0.04, "seen": 0.5, "bad": 1.0 if fid.startswith("facade") else 0.5}  # noqa: E731
        r = cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json={"key": "k", "faces": [face("facade_right"), face("road")]})
        assert r.status_code == 200, r.text
        docs = svc.require_documents()
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={"faces": ["facade_right"]})
        assert r.status_code == 200, r.text
        fj = svc.queue.jobs[r.json()["job_id"]]
        assert docs.get(fj.origin.payload["document_id"]).selection.all()                         # the grazing half too (0.47 < 0.7)
        assert fj.recipe["prompt_text"].startswith("A flat elevation of the buildings' fronts, seen square on")
        from loom2.place_sets import fill_failed
        fill_failed(svc.queue, fj, "cancelled")
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={"faces": ["road"]})
        assert r.status_code == 200, r.text
        sel = docs.get(svc.queue.jobs[r.json()["job_id"]].origin.payload["document_id"]).selection
        assert sel[:, :30].all() and not sel[:, 30:].any()                                          # a road keeps 0.05
