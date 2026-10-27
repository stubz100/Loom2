"""AE5 (03 §AE5, proto01_animate 31 §4): the finished shot's render settings and output modules — the final keeps them (its revision
stays), the render job carries them to EffectCraft's render queue (quality, resolution, motion blur, frame blending, depth, alpha), an F16
conform keeps the alpha (RIFE runs on the colour and on the alpha as a grey picture), and a ProRes 4444 is written beside the master."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import av
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_compositions_ae1 import FAKE, N, S, _final_assembled  # noqa: E402


async def test_settings_reach_the_render_and_the_prores(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from loom2 import final_assembly
    from loom2.clips import ClipStore
    from loom2.compositions import CompositionStore
    from loom2.effectcraft import EffectCraft
    from loom2.finals import FinalStore
    from loom2.recipes import RenderSettings
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
        rs = RenderSettings(resolution="half", depth=16, alpha=True, prores=True, motion_blur="off")
        f2 = FinalStore(rig.ws).set_render(f.id, rs)
        assert f2.render == rs and f2.revision == f.revision                                       # settings are not the shot's content
        rig.queue.load()
        await rig.queue.start()
        j = await rig.wait(rig.queue.submit({"kind": "comp_render", "final_id": f.id, "settings": f2.render.model_dump()})[0].id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        clips = ClipStore(rig.ws)
        clip = clips.get(j.result["clip_id"])
        assert clip.w == S // 2 and clip.frames == N
        assert Image.open(clips.frame_path(clip.id, 1)).mode == "RGBA" and Image.open(clips.frame_path(clip.id, 1)).getpixel((0, 0))[3] == 128   # the alpha kept
        assert any("half, 16-bit, alpha, no motion blur" in line for line in j.log_tail)
        mov = rig.ws.path / j.result["prores"]
        with av.open(str(mov)) as c:
            s = c.streams.video[0]
            assert s.codec_context.name == "prores" and s.codec_context.pix_fmt.startswith("yuva444p") and s.width == S // 2
            assert sum(1 for _ in c.decode(video=0)) == N
        assert any("ProRes 4444 beside the master" in line for line in j.log_tail)
        assert rig.catalogue.get(j.result["asset_ids"][0]).params["render"]["settings"]["resolution"] == "half"
    finally:
        await rig.close()


def test_the_conform_keeps_the_alpha(tmp_path: Path, monkeypatch):
    """RIFE writes RGB: the colour and the alpha conform apart (a stand-in RIFE here: every frame repeated, 3 → 4) and meet again."""
    from loom2 import final_assembly
    src = tmp_path / "f16"
    src.mkdir()
    for i in range(3):
        im = Image.new("RGBA", (8, 4), (40 * i, 10, 10, 60 * (i + 1)))
        im.save(src / f"f_{i:04d}.png")

    def fake_conform(s: Path, d: Path, n16: int, cancelled=None):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        frames = sorted(s.glob("*.png"))
        out = []
        for k in range(round((n16 - 1) * 24 / 16) + 1):
            q = d / f"{k:06d}.png"
            shutil.copyfile(frames[min(len(frames) - 1, k * 2 // 3)], q)
            out.append(q)
        assert all(Image.open(p).mode == "RGB" for p in out)                                      # RIFE's side sees RGB only
        return out
    monkeypatch.setattr(final_assembly, "conform_24", fake_conform)
    out = final_assembly.conform_24_alpha(src, tmp_path / "f24", 3)
    assert out is not None and len(out) == 4
    a = [np.asarray(Image.open(p))[0, 0] for p in out]
    assert all(Image.open(p).mode == "RGBA" for p in out) and [int(x[3]) for x in a] == [60, 60, 120, 180] and int(a[2][0]) == 40
    assert sorted(x.name for x in tmp_path.iterdir()) == ["f16", "f24"]                            # the halves cleaned up


def test_the_render_settings_route(tmp_path: Path):
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import FinalStore
    from loom2.stages import StageStore
    from loom2.workspace import Workspace
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        st = StageStore(ws).create("Room")
        f, _ = _final_assembled(ws, st.id, st.cameras[0].id, tmp_path / "src")
        assert cl.get(f"/finals/{f.id}").json()["render"] == {"quality": "best", "resolution": "full", "motion_blur": "comp", "frame_blending": "comp", "depth": 8,
                                                             "alpha": False, "prores": False}                       # AE1's render, as before
        r = cl.put(f"/finals/{f.id}/render", json={"quality": "draft", "resolution": "quarter", "motion_blur": "off", "frame_blending": "off", "depth": 32, "alpha": True, "prores": True})
        assert r.status_code == 200 and r.json()["render"]["depth"] == 32 and r.json()["revision"] == f.revision
        assert cl.put(f"/finals/{f.id}/render", json={"depth": 12}).status_code == 422
        assert cl.put("/finals/fin_nope/render", json={}).status_code == 404
        assert FinalStore(ws).get(f.id).render.resolution == "quarter"


def test_an_opaque_alpha_stays_opaque(tmp_path: Path, monkeypatch):
    """RIFE shifts a flat grey a few levels (the rig: 255 came back 250) — an opaque sequence keeps 255 without the alpha's run, and the
    alpha's near-ends are snapped back."""
    from loom2 import final_assembly
    src = tmp_path / "f16"
    src.mkdir()
    for i in range(3):
        Image.new("RGBA", (8, 4), (40 * i, 10, 10, 255)).save(src / f"f_{i:04d}.png")
    runs = []

    def dim(s: Path, d: Path, n16: int, cancelled=None):                                                         # a stand-in RIFE that darkens by 5 levels
        runs.append(s.name)
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        out = []
        for k, p in enumerate(sorted(s.glob("*.png"))):
            q = d / f"{k:06d}.png"
            Image.fromarray((np.asarray(Image.open(p).convert("RGB")).astype(int) - 5).clip(0, 255).astype(np.uint8)).save(q)
            out.append(q)
        return out
    monkeypatch.setattr(final_assembly, "conform_24", dim)
    out = final_assembly.conform_24_alpha(src, tmp_path / "f24", 3)
    assert len(runs) == 1 and all(Image.open(p).getchannel("A").getextrema() == (255, 255) for p in out)
    for i in range(3):                                                                           # one transparent, one opaque corner
        im = Image.new("RGBA", (8, 4), (0, 0, 0, 255))
        im.putpixel((0, 0), (0, 0, 0, 0))
        im.save(src / f"f_{i:04d}.png")
    out = final_assembly.conform_24_alpha(src, tmp_path / "f24", 3)
    assert len(runs) == 3 and all(Image.open(p).getchannel("A").getextrema() == (0, 255) for p in out)   # 250 → 255; 0 stays 0
