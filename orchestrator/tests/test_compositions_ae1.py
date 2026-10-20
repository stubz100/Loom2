"""AE1 step 3 (proto01_animate 20 §2, D114): the composition — the assembly writes the composition's footage from its own rules; the
composition is written from the final through the EffectCraft session (the fake), its footage relative; edits are commands and properties,
each saved; a frame; made again after another assembly."""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

FAKE = Path(__file__).parent / "fake_effectcraft.py"
N, S = 3, 128


def _img(p: Path, value: int, rect: tuple[int, int, int, int] | None = None, inside: int = 0, mode: str = "L") -> Path:
    im = Image.new(mode, (S, S), value)
    if rect:
        im.paste(inside, rect)
    im.save(p)
    return p


def _final_assembled(ws, stage_id: str, camera_id: str, tmp: Path):
    """A final with a plate, the shadows, a prop (a box, further, to the left) and a figure (near), their frames on disk, assembled."""
    from loom2 import final_assembly
    from loom2.finals import FinalStore
    tmp.mkdir(parents=True, exist_ok=True)
    grey = _img(tmp / "grey.png", 128, mode="RGB")
    bare_d = _img(tmp / "bare_d.png", 100)
    fig_d = _img(tmp / "fig_d.png", 100, (51, 25, 77, 115), 180)
    box_d = _img(tmp / "box_d.png", 100, (10, 70, 40, 110), 140)
    shade = _img(tmp / "shade.png", 64, mode="RGB")                                   # the lit clay at half the bare set's: ratio 0.5
    matte = _img(tmp / "matte.png", 0, (53, 27, 75, 113), 255)
    data = {"name": "Shot", "stage_id": stage_id, "camera_id": camera_id, "stage_revision": 0, "range": {"start": 0, "end": 3}, "rate": 16,
            "size": {"w": S, "h": S}, "frames": N,
            "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"},
                       {"id": "box", "kind": "prop", "name": "Box", "object_id": "box", "method": "rendered"},
                       {"id": "fig", "kind": "figure", "name": "Mara", "object_id": "fig_1", "method": "move"},
                       {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
    store = FinalStore(ws)
    f = store.create(data, {"plate": {"depth": [bare_d] * N, "clay": [grey] * N}, "box": {"beauty": [grey] * N, "depth": [box_d] * N},
                            "fig": {"pose": [grey] * N, "depth": [fig_d] * N}, "shadows": {"clay": [shade] * N}}, {})
    store.set_frames(f.id, "plate", [grey] * N)
    store.set_frames(f.id, "fig", [grey] * N)
    md = store.pass_dir(f.id, "fig", "matte")
    md.mkdir(parents=True, exist_ok=True)
    for i in range(N):
        (md / f"{i:04d}.png").write_bytes(matte.read_bytes())
    stats = final_assembly.assemble_frames(store, store.get(f.id), tmp / "assembled", None, store.folder(f.id) / "comp")
    return store.set_result(f.id, "clip_fake", stats), stats


def test_the_assembly_writes_the_compositions_footage(tmp_path: Path):
    from loom2.stages import StageStore
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "proj", name="P")
    st = StageStore(ws).create("Room")
    f, stats = _final_assembled(ws, st.id, st.cameras[0].id, tmp_path / "src")
    assert stats["stack"] == ["box", "fig"] and stats["stack_frames"] == N and f.assembly["stack"] == ["box", "fig"]   # far to near
    comp = ws.path / "finals" / f.id / "comp"
    assert sorted(p.name for p in comp.iterdir()) == ["box", "fig_matte", "shadow"] and len(list((comp / "shadow").glob("*.png"))) == N
    shadow = np.asarray(Image.open(comp / "shadow" / "0000.png").convert("L"))
    assert abs(int(shadow[5, 5]) - 128) <= 1 and shadow[70, 64] == 255                 # the ratio 0.5 off the actors, 1 on them
    box = Image.open(comp / "box" / "0001.png")
    assert box.mode == "RGBA" and box.getpixel((20, 90))[3] == 255 and box.getpixel((100, 20))[3] == 0
    m = Image.open(comp / "fig_matte" / "0002.png").convert("L")
    assert m.getpixel((64, 70)) == 255 and m.getpixel((10, 10)) == 0                   # her matte in her own frame, not moved
    assert Image.open(tmp_path / "src" / "assembled" / "000000.png").size == (S, S)


def test_relativise():
    from loom2.compositions import relativise
    root = Path("F:/x/finals/fin_1") if Path("F:/").exists() else Path("/x/finals/fin_1")
    inner = str(root / "plate" / "frames" / "0000.png")
    doc = {"path": str(root / "comp.ecproj.tmp"), "items": {"2": {"kind": {"type": "Footage", "path": inner.upper() if inner[0].isalpha() else inner,
                                                                          "sequence": [inner, str(root.parent / "other.png")]}}}}
    out = json.loads(relativise(json.dumps(doc), root))
    assert out["path"] == doc["path"]                                                   # the project's own path (top level) is left alone
    k = out["items"]["2"]["kind"]
    assert k["path"].lower() == "plate/frames/0000.png" and k["sequence"] == ["plate/frames/0000.png", str(root.parent / "other.png")]


def test_composition_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "effectcraft": {"cli": str(tmp_path / "none.exe")}})
    app = create_app(state)
    svc = app.state.services
    H = {"X-Loom-Token": svc.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        f, stats = _final_assembled(svc.ws, st["id"], st["cameras"][0]["id"], tmp_path / "src")
        url = f"/finals/{f.id}/composition"
        assert cl.get(url, headers=H).status_code == 404
        assert cl.post(url, headers=H).status_code == 503                               # EffectCraft not built: said so
        svc.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        r = cl.post(url, headers=H)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["stack"] == ["box", "fig"] and [l["id"] for l in c["layers"]] == ["plate", "shadows", "box", "fig"] and c["revision"] == 0
        assert c["layers"][3]["matte"] and c["layers"][3]["offset_px"] == stats["offsets_px"]["fig"] and c["stale"] is False and c["effectcraft"]
        d = tmp_path / "proj" / "finals" / f.id
        assert (d / "comp.json").is_file() and (d / "comp.ecproj").is_file() and not (d / "comp.ecproj.tmp").exists()
        proj = json.loads((d / "comp.ecproj").read_text(encoding="utf-8"))
        paths = [it["path"] for it in proj["items"].values() if it.get("type") == "Footage"]
        assert paths and all(not Path(p).is_absolute() and ".." not in p for p in paths)   # relative, under the final's folder
        assert "plate/frames/0000.png" in paths and "comp/fig_matte/0000.png" in paths and "comp/shadow/0000.png" in paths and "comp/box/0000.png" in paths
        comp = next(iter(proj["comps"].values()))
        layers = comp["layers"]                                                          # top first
        assert [l["name"] for l in layers] == ["Mara", "Mara · matte", "Box", "Shadows", "Room"]
        assert layers[3]["blendMode"] == "Multiply" and layers[0]["trackMatte"] == {"layer": layers[1]["id"], "kind": "Luma Matte"}
        assert layers[1]["parent"] == layers[0]["id"] and not layers[1]["video"]
        dx, dy = stats["offsets_px"]["fig"]
        assert layers[0]["position"] == [S / 2 + dx, S / 2 + dy] == layers[1]["position"]
        assert svc.effectcraft.project == str(d / "comp.ecproj")                        # the session holds the written file
        assert cl.get(url, headers=H).json()["revision"] == 0
        # edits: a property, then a command; each saved, the revision counting
        r = cl.post(f"{url}/property", json={"layer": "Mara", "path": "transform/opacity", "value": 50}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["composition"]["revision"] == 1 and r.json()["result"]["value"] == 50
        proj = json.loads((d / "comp.ecproj").read_text(encoding="utf-8"))
        assert next(iter(proj["comps"].values()))["layers"][0]["opacity"] == 50
        r = cl.post(f"{url}/command", json={"id": "layer.setBlendMode", "params": {"layers": ["Shadows"], "mode": "Normal"}}, headers=H)
        assert r.status_code == 200 and r.json()["composition"]["revision"] == 2
        r = cl.post(f"{url}/command", json={"id": "layer.fly"}, headers=H)
        assert r.status_code == 422 and "unknown command" in r.text
        assert cl.get(url, headers=H).json()["revision"] == 2
        # a frame: the viewer's preview, also through the media key
        r = cl.get(f"{url}/frame?t=0.5&side=64", headers=H)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        im = Image.open(io.BytesIO(r.content))
        assert im.size == (64, 64) and im.getpixel((0, 0))[0] == 8                       # 0.5 s at 16 fps
        wrong = {"X-Loom-Token": "not the token"}                                        # the media key alone opens the frame route (an <img>)
        assert cl.get(f"{url}/frame?t=0&side=32&k={svc.app.media_key}", headers=wrong).status_code == 200
        assert cl.get(f"{url}/frame?t=0&side=32", headers=wrong).status_code == 401
        # assembled again: the composition is stale; made again: fresh, the edits dropped
        from loom2.finals import FinalStore
        FinalStore(svc.ws).set_result(f.id, "clip_2", stats)
        assert cl.get(url, headers=H).json()["stale"] is True
        c = cl.post(url, headers=H).json()
        assert c["revision"] == 0 and c["stale"] is False
        proj = json.loads((d / "comp.ecproj").read_text(encoding="utf-8"))
        assert next(iter(proj["comps"].values()))["layers"][0]["opacity"] == 100.0
        # a final never assembled has nothing to compose
        from loom2.finals import FinalStore as FS
        grey = tmp_path / "src" / "grey.png"
        bare = FS(svc.ws).create({"name": "Bare", "stage_id": st["id"], "camera_id": st["cameras"][0]["id"], "stage_revision": 0, "range": {"start": 0, "end": 3},
                                  "rate": 16, "size": {"w": S, "h": S}, "frames": N,
                                  "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"},
                                             {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]},
                                 {"plate": {"depth": [grey] * N, "clay": [grey] * N}, "shadows": {"clay": [grey] * N}}, {})
        assert cl.post(f"/finals/{bare.id}/composition", headers=H).status_code == 409
        assert cl.get(f"/finals/{bare.id}/composition/frame?t=0", headers=H).status_code == 404
        assert cl.post(f"/finals/{bare.id}/composition/command", json={"id": "edit.undo"}, headers=H).status_code == 404
        assert cl.post(f"/finals/{bare.id}/composition/render", headers=H).status_code == 404
        r = cl.post(f"{url}/render", headers=H)                                          # the finished shot: a queued CPU job
        assert r.status_code == 200 and r.json()["job_id"]


async def test_comp_render_job(tmp_path: Path, object_info: dict, monkeypatch):
    """The finished shot: `comp_render` runs the (fake) CLI on the composition, the frames a clip (no RIFE here) — the final's clip and the
    composition's; the final's revision does not move, so the composition stays fresh; a final without a composition fails with its reason."""
    import test_lifecycle
    from loom2 import final_assembly
    from loom2.clips import ClipStore
    from loom2.compositions import CompositionStore
    from loom2.effectcraft import EffectCraft
    from loom2.finals import FinalStore
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_assembled(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        ec, cs = EffectCraft(rig.app), CompositionStore(rig.ws)
        cs.make(f, ec)
        ec.stop()
        monkeypatch.setattr(final_assembly, "rife_binary", lambda: None)
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "comp_render", "final_id": f.id}, origin=JobOrigin(suite="stage", surface="comp_render", ref=f.id))[0]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        clips = ClipStore(rig.ws)
        clip = clips.get(j.result["clip_id"])
        assert clip.frames == N and clip.fps == 16 and clip.w == S and clip.model_id == "composition"
        assert Image.open(clips.frame_path(clip.id, 2)).getpixel((0, 0))[0] == 2            # the fake's frames: R = the frame number
        f2 = FinalStore(rig.ws).get(f.id)
        assert f2.clip_id == clip.id and f2.revision == f.revision
        c2 = cs.get(f2)
        assert c2.clip_id == clip.id and c2.rendered_revision == 0 and c2.render_job_id == job.id and not c2.stale
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a.kind == "video" and a.lineage_kind == "final"
        assert any("composition rendered" in line for line in j.log_tail)
        grey = tmp_path / "src" / "grey.png"
        bare = FinalStore(rig.ws).create({"name": "Bare", "stage_id": st.id, "camera_id": st.cameras[0].id, "stage_revision": 0, "range": {"start": 0, "end": 3},
                                          "rate": 16, "size": {"w": S, "h": S}, "frames": N,
                                          "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"},
                                                     {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]},
                                         {"plate": {"depth": [grey] * N, "clay": [grey] * N}, "shadows": {"clay": [grey] * N}}, {})
        jb = await rig.wait(rig.queue.submit({"kind": "comp_render", "final_id": bare.id})[0].id, timeout=30)
        assert jb.status == "failed" and "no composition" in (jb.error or "")
    finally:
        await rig.close()
