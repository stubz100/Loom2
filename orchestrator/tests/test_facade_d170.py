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


def baked_set(cl, svc, tmp_path, kind: str, seen_byte: int, faces: tuple[str, ...]) -> str:
    """A place whose set is fitted, turned into `kind`, and baked with `faces` alike: the left half unseen, the right half seen at a cosine
    of seen_byte / 255 through a fine pixel — the place's id."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_ideas_cw1 import _picture
    from test_place_sets_cw6 import _png, relief
    from loom2.place_sets import fit_landed
    _, cat, _ = svc.require_project()
    pid = cl.post("/story/profiles", json={"name": "Fish market", "cls": "place"}).json()["id"]
    pic = _picture(cat, tmp_path, "market", "a fish market")
    assert cl.put(f"/story/profiles/{pid}/versions/v1/anim-ref", json={"asset_id": pic.id}).status_code == 200
    job = cl.post(f"/story/profiles/{pid}/versions/v1/set/fit", json={}).json()["job_id"]
    relief(tmp_path / "r.glb")
    fit_landed(svc.queue, svc.queue.jobs[job], "ast_relief", tmp_path / "r.glb")
    p = cl.get(f"/story/profiles/{pid}").json()
    ps = {**p["versions"][0]["place_set"], "kind": kind}
    assert cl.put(f"/story/profiles/{pid}/versions/v1/set", json={"revision": p["revision"], "place_set": ps}).status_code == 200
    tex = np.full((40, 60, 4), 180, np.uint8)
    tex[:, :30, 3] = 0
    cov = np.zeros((40, 60, 3), np.uint8)
    cov[:, 30:, 0] = seen_byte
    shas = []
    for arr in (tex, cov):
        sha, data = _png(arr)
        assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
        shas.append(sha)
    body = [{"id": fid, "image": shas[0], "coverage": shas[1], "texel_m": 0.04, "seen": 0.5, "bad": 0.5} for fid in faces]
    r = cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json={"key": "k", "faces": body})
    assert r.status_code == 200, r.text
    return pid


def fill_selection(cl, svc, pid: str, fid: str) -> tuple[np.ndarray, str]:
    """The selection and the prompt of a face's Fill (the job then stopped, so the next can be asked)."""
    from loom2.place_sets import fill_failed
    r = cl.post(f"/story/profiles/{pid}/versions/v1/set/fill", json={"faces": [fid]})
    assert r.status_code == 200, r.text
    fj = svc.queue.jobs[r.json()["job_id"]]
    sel = svc.require_documents().get(fj.origin.payload["document_id"]).selection.copy()
    fill_failed(svc.queue, fj, "cancelled")
    return sel, fj.recipe["prompt_text"]


def test_the_fill_masks_a_facade_by_its_own_cosine(tmp_path):
    """Through the routes: a street's facade and its road baked alike (half unseen, half seen at a cosine of 0.47) — the facade's Fill
    selects the whole face and paints an elevation; the road's only its unseen half (0.47 is over the ground's 0.35, D172)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        pid = baked_set(cl, svc, tmp_path, "street", 120, ("facade_right", "road"))
        sel, prompt = fill_selection(cl, svc, pid, "facade_right")
        assert sel.all() and prompt.startswith("A flat elevation of the buildings' fronts, seen square on")
        sel, _ = fill_selection(cl, svc, pid, "road")
        assert sel[:, :30].all() and not sel[:, 30:].any()
