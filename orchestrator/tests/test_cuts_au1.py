"""AU1 (proto01_animate 30 §16, D127): Settings › Audio and the track roles, on tests/fake_filmcraft.py (the real binary on the rig) — the
loudness target moved from Settings › FilmCraft (an app.json from before keeps its value), a new cut's A1–A3 are dialogue, music and effects
with the roles' strips, an audio track's strip written as FilmCraft holds it (the fader and pan, Amplify stages past +24 dB and past the
fader's +15 dB, a Stereo Width after the track's other pre-fader effects) and read back from it, a role given and cleared, the mix through
the strip, and the 5-insert limit said in loom2's words."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState, Settings, TrackStrip  # noqa: E402
from loom2.cuts import CutError, strip_of, strip_steps  # noqa: E402

from fake_tts import tone  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def _client(tmp_path: Path, **audio):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}, "audio": audio})
    return create_app(state)


def _cut(cl, tmp_path: Path) -> dict:
    """A FilmCraft cut of one 1 s take."""
    cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
    from loom2.workspace import Workspace
    cs = ClipStore(Workspace(tmp_path / "proj"))
    frames = []
    for i in range(24):
        p = tmp_path / f"f{i}.png"
        Image.new("RGB", (32, 24), (0, 90, 200)).save(p)
        frames.append(p)
    clip = cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt="s", seed=1, fps=24, start_asset_id="ast_x"))
    tl = cl.post("/timelines", json={"name": "Mix", "fps": 24, "w": 64, "h": 36}).json()
    return cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": clip.id, "in": 0, "out": 24}], "overlaps": [0]}).json()


def test_settings_audio_and_the_moved_loudness(tmp_path: Path):
    s = Settings()
    assert s.audio.loudness_lufs == -16.0 and (s.audio.dialogue.gain_db, s.audio.music.gain_db, s.audio.effects.gain_db) == (0.0, -6.0, -3.0)
    assert not hasattr(s.filmcraft, "loudness_lufs")
    # an app.json from before D127 kept its loudness under filmcraft
    state = tmp_path / "old"
    state.mkdir()
    (state / "app.json").write_text(json.dumps({"schema_version": 1, "settings": {"filmcraft": {"loudness_lufs": -23.0}}}), encoding="utf-8")
    app = AppState(state)
    assert app.settings.audio.loudness_lufs == -23.0
    app.update_settings({"audio": {**app.settings.audio.model_dump(), "music": {"gain_db": -50, "volume_db": 40, "pan": -300, "width": 999}}})
    assert app.settings.audio.music.model_dump() == {"gain_db": -36.0, "volume_db": 18.0, "pan": -100.0, "width": 200.0}   # the ranges hold
    assert AppState(state).settings.audio.loudness_lufs == -23.0                                                          # and it stays


def test_strip_steps_keep_the_authors_effects():
    eq = {"effect": "parametric_eq", "enabled": True, "params": {}}
    lim = {"effect": "hard_limiter", "enabled": True, "params": {}, "post_fader": True}
    old = {"effect": "amplify", "enabled": True, "params": {"gain": {"value": {"Float": 3.0}}}}
    t = {"id": 7, "volume_db": 0.0, "pan": 0.0, "effects": [old, eq, lim]}
    steps = strip_steps(t, TrackStrip(gain_db=20, volume_db=18, width=150, pan=-25))
    assert steps[0] == {"id": "mixer.removeInsert", "params": {"strip": 7, "slot": 0}}                 # the strip's old stage out
    adds = [(s["params"]["slot"], s["params"]["effect"], s["params"]["postFader"]) for s in steps if s["id"] == "mixer.addInsert"]
    # the vector after: [amp 20, eq, width, amp +3 (post), limiter (post)] — gain first, the width after the EQ, the volume's stage after the fader
    assert adds == [(0, "amplify", False), (2, "stereo_width", False), (3, "amplify", True)]
    sets = [s["params"]["params"] for s in steps if s["id"] == "mixer.setInsert"]
    assert sets == [{"gain": 20.0}, {"width": 150.0}, {"gain": 3.0}]
    assert steps[-1] == {"id": "mixer.setStrip", "params": {"strip": 7, "volumeDb": 15.0, "pan": -25.0}}
    # read back the way FilmCraft would hold it
    held = {"id": 7, "volume_db": 15.0, "pan": -25.0, "effects": [
        {"effect": "amplify", "params": {"gain": {"value": {"Float": 24.0}}}}, {"effect": "amplify", "params": {"gain": {"value": {"Float": 6.0}}}}, eq,
        {"effect": "stereo_width", "params": {"width": {"value": {"Float": 150.0}}}}, {"effect": "amplify", "post_fader": True, "params": {"gain": {"value": {"Float": 3.0}}}}, lim]}
    assert strip_of(held).model_dump() == {"gain_db": 30.0, "volume_db": 18.0, "pan": -25.0, "width": 150.0}
    assert strip_of({"id": 1, "volume_db": -96.0, "effects": []}).volume_db == -96.0                          # the floor is −∞, nothing added to it
    assert [s["params"]["params"]["gain"] for s in strip_steps({"id": 9, "effects": []}, TrackStrip(gain_db=36)) if s["id"] == "mixer.setInsert"] == [24.0, 12.0]
    full = {"id": 8, "effects": [eq] * 4}
    try:
        strip_steps(full, TrackStrip(gain_db=30))
        raise AssertionError("five inserts fit")
    except CutError as e:
        assert "5 effects" in str(e)


def test_roles_strips_and_the_mix(tmp_path: Path):
    app = _client(tmp_path, effects={"gain_db": -3.0, "volume_db": 0.0, "pan": 40.0, "width": 100.0})
    svc = app.state.services
    with TestClient(app) as cl:
        tl = _cut(cl, tmp_path)
        base = f"/timelines/{tl['id']}"
        tr = cl.get(f"{base}/tracks").json()
        # a new cut: the roles, named, with Settings › Audio's strips
        assert [(t["name"], t["role"], t["gain_db"], t["pan"]) for t in tr["audio"]] == [("Dialogue", "dialogue", 0.0, 0.0), ("Music", "music", -6.0, 0.0), ("Effects", "effects", -3.0, 40.0)]
        assert all(t["role"] is None for t in tr["video"])
        # the strip: past FilmCraft's limits by a second stage, read back from the project
        rev = cl.get(base).json()["revision"]
        r = cl.post(f"{base}/strip", json={"revision": rev, "track": tr["audio"][1]["id"], "gain_db": 30, "volume_db": 18, "width": 150})
        assert r.status_code == 200, r.text
        a2 = r.json()["tracks"]["audio"][1]
        assert (a2["gain_db"], a2["volume_db"], a2["width"], a2["pan"]) == (30.0, 18.0, 150.0, 0.0)
        raw = json.loads((Path(tmp_path / "proj") / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))
        seq = next(it["kind"]["Sequence"] for it in raw["project"]["items"].values() if "Sequence" in it["kind"])
        held = seq["audio_tracks"][1]
        assert held["volume_db"] == 15.0 and [(e["effect"], bool(e.get("post_fader"))) for e in held["effects"]] == [("amplify", False), ("amplify", False), ("stereo_width", False), ("amplify", True)]
        # one setting at a time keeps the others; −96 is the floor
        r = cl.post(f"{base}/strip", json={"revision": r.json()["timeline"]["revision"], "track": a2["id"], "volume_db": -200}).json()
        assert (r["tracks"]["audio"][1]["volume_db"], r["tracks"]["audio"][1]["gain_db"]) == (-96.0, 30.0)
        # undo is the cut's
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert r["tracks"]["audio"][1]["volume_db"] == 18.0
        # a role: named after it, the role's strip; none clears it and keeps the strip
        a3 = r["tracks"]["audio"][2]
        r = cl.post(f"{base}/role", json={"revision": r["timeline"]["revision"], "track": a3["id"], "role": "music"}).json()
        a3 = r["tracks"]["audio"][2]
        assert (a3["name"], a3["role"], a3["gain_db"], a3["pan"]) == ("Music", "music", -6.0, 0.0)
        r = cl.post(f"{base}/role", json={"revision": r["timeline"]["revision"], "track": a3["id"], "role": None}).json()
        assert (r["tracks"]["audio"][2]["role"], r["tracks"]["audio"][2]["gain_db"]) == (None, -6.0)
        assert cl.post(f"{base}/strip", json={"track": 999, "gain_db": 1}).status_code == 422                  # not an audio track
        assert cl.post(f"{base}/strip", json={"track": tr["video"][0]["id"], "gain_db": 1}).status_code == 422
        # the mix goes through the strip: a sound on A1 panned hard left leaves the right channel silent
        wav = tmp_path / "s.wav"
        tone(str(wav), 0.8, hz=330)
        a = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="import")
        r = cl.post(f"{base}/place", json={"revision": r["timeline"]["revision"], "asset_id": a.id, "track": "A1", "frame": 0}).json()
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32")
        both = float(np.sqrt(np.mean(pcm[:, 1] ** 2)))
        r = cl.post(f"{base}/strip", json={"revision": r["timeline"]["revision"], "track": tr["audio"][0]["id"], "pan": -100}).json()
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32")
        assert both > 0.05 and float(np.sqrt(np.mean(pcm[:, 1] ** 2))) < 1e-4 and float(np.sqrt(np.mean(pcm[:, 0] ** 2))) > 0.05
