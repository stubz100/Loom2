"""AU4 (proto01_animate 30 §16, D127): an audio track's chain of VST3 effects and its print, on tests/fake_filmcraft.py and
tests/fake_vsthost.py (the real FilmCraft, host and plug-ins on the rig) — an effect added from GET /audio/plugins, set in its editor (a new
state file per edit), the track printed before the mix (its gain and chain by the host, on a companion track the cut does not show, the
source into a muted submix), the companion following the source's pan and mute without printing again, a bypass taking the print away, the
FCPXML exported with the prints standing for their sources, undo."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402

from fake_tts import tone  # noqa: E402

TESTS = Path(__file__).resolve().parent


def _client(tmp_path: Path):
    state = tmp_path / "state"
    gain = tmp_path / "vst3" / "Gain.vst3"
    gain.mkdir(parents=True)
    (gain / "fake.json").write_text(json.dumps({"classes": [{"uid": "A" * 32, "name": "Gain", "vendor": "Fake", "version": "1.0", "sub": "Fx"}]}), encoding="utf-8")
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(TESTS / "fake_filmcraft.py"), "timeout_s": 30.0},
                                     "audio": {"loudness_lufs": None}, "vsthost": {"cli": str(TESTS / "fake_vsthost.py"), "folders": [str(tmp_path / "vst3")]}})
    return create_app(state), gain


def _rms(pcm: np.ndarray, c: int, t0: float = 0.2, t1: float = 0.8, sr: int = 48000) -> float:
    return float(np.sqrt(np.mean(pcm[int(t0 * sr):int(t1 * sr), c] ** 2)))


def test_a_chain_prints_and_the_mix_hears_it(tmp_path: Path):
    app, gain_bundle = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        wav = tmp_path / "music.wav"
        tone(str(wav), 1.0, hz=220)
        music = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="import")
        tl = cl.post("/timelines", json={"name": "Fx", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/place", json={"revision": tl["revision"], "asset_id": music.id, "track": "A2", "frame": 0}).json()
        a2 = r["tracks"]["audio"][1]["id"]
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32", always_2d=True)
        plain = _rms(pcm, 0)                                                   # the music at its role's −6 dB, no effect yet
        # an effect from the list, set in its editor (the author turns it to 0.5)
        plugin = cl.get("/audio/plugins").json()["plugins"][0]
        r = cl.post(f"{base}/fx", json={"revision": r["timeline"]["revision"], "track": a2, "op": "add", "plugin": {k: plugin[k] for k in ("bundle", "uid", "name", "vendor")}})
        assert r.status_code == 200, r.text
        tr = r.json()["tracks"]["audio"][1]
        assert [e["name"] for e in tr["chain"]] == ["Gain"] and tr["printed"] == "stale"
        fx = tr["chain"][0]["id"]
        (gain_bundle / "edit.json").write_text(json.dumps({"gain": 0.5}), encoding="utf-8")
        r = cl.post(f"{base}/fx/editor", json={"track": a2, "fx": fx}).json()
        st = r["tracks"]["audio"][1]["chain"][0]["state"]
        assert st == f"fx/{fx}-1.vststate" and json.loads((tmp_path / "proj" / "timelines" / tl["id"] / st).read_text(encoding="utf-8"))["gain"] == 0.5
        # the mix prints the track first: its gain and the effect, on a companion the cut does not show
        m = cl.get(f"{base}/mix")
        assert m.status_code == 200, m.text
        pcm, _ = sf.read(io.BytesIO(m.content), dtype="float32", always_2d=True)
        assert abs(20 * np.log10(_rms(pcm, 0) / plain) + 6.02) < 0.1                # the effect's 0.5 on top of the role's −6 dB
        tracks = cl.get(f"{base}/tracks").json()
        assert len(tracks["audio"]) == 3 and tracks["audio"][1]["printed"] == "current"
        raw = json.loads((tmp_path / "proj" / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))
        seq = next(it["kind"]["Sequence"] for it in raw["project"]["items"].values() if "Sequence" in it["kind"])
        src = next(t for t in seq["audio_tracks"] if t["id"] == a2)
        bus = seq["submix_tracks"][0]
        assert len(seq["audio_tracks"]) == 4 and bus["muted"] and src["mixer"]["output"] == bus["id"]
        printed_file = json.loads(next(it["metadata"]["loom2.prints"] for it in raw["project"]["items"].values() if "Sequence" in it["kind"]))[str(a2)]["file"]
        # the source's pan and mute reach the companion; no new print for them
        rev = cl.get(base).json()["revision"]
        cl.post(f"{base}/strip", json={"revision": rev, "track": a2, "pan": -100})
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32", always_2d=True)
        assert _rms(pcm, 1) < 1e-4 < _rms(pcm, 0)
        assert cl.get(f"{base}/tracks").json()["audio"][1]["printed"] == "current" and Path(printed_file).is_file()
        rev = cl.get(base).json()["revision"]
        cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.setTrack", "params": {"track": a2, "muted": True}}]})
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32", always_2d=True)
        assert float(np.max(np.abs(pcm))) < 1e-4
        rev = cl.get(base).json()["revision"]
        cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.setTrack", "params": {"track": a2, "muted": False}}]})
        # the FCPXML: the prints stand for their sources
        assert cl.post(f"{base}/export", json={"format": "fcpxml"}).status_code == 200
        # bypassed: no print, the source back in the mix at its role's gain
        rev = cl.get(base).json()["revision"]
        r = cl.post(f"{base}/fx", json={"revision": rev, "track": a2, "op": "bypass", "fx": fx, "bypass": True}).json()
        assert r["tracks"]["audio"][1]["printed"] == "none"
        pcm, _ = sf.read(io.BytesIO(cl.get(f"{base}/mix").content), dtype="float32", always_2d=True)
        assert abs(20 * np.log10(_rms(pcm, 0) / plain)) < 0.1
        raw = json.loads((tmp_path / "proj" / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))
        seq = next(it["kind"]["Sequence"] for it in raw["project"]["items"].values() if "Sequence" in it["kind"])
        assert len(seq["audio_tracks"]) == 3 and next(t for t in seq["audio_tracks"] if t["id"] == a2)["mixer"]["output"] is None
        # the chain's undo is the cut's: the bypass goes back, and four steps on, the editor's state
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert r["tracks"]["audio"][1]["chain"][0]["bypass"] is False
        for _ in range(4):                                                     # the unmute, the mute, the pan, then the editor's state
            r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert r["tracks"]["audio"][1]["chain"][0]["state"] is None
        # move and remove; a wrong id is said
        assert cl.post(f"{base}/fx", json={"track": a2, "op": "remove", "fx": "fx_nope"}).status_code == 422
        r = cl.post(f"{base}/fx", json={"track": a2, "op": "remove", "fx": fx}).json()
        assert r["tracks"]["audio"][1]["chain"] == []


def test_without_the_host_a_print_is_said(tmp_path: Path):
    app, _ = _client(tmp_path)
    AppState(tmp_path / "state").update_settings({"vsthost": {"cli": str(tmp_path / "no-host.exe")}})
    app = create_app(tmp_path / "state")
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        tl = cl.post("/timelines", json={"name": "Fx", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        a1 = cl.get(f"{base}/tracks").json()["audio"][0]["id"]
        r = cl.post(f"{base}/fx", json={"track": a1, "op": "add", "plugin": {"bundle": str(tmp_path / "vst3" / "Gain.vst3"), "uid": "A" * 32, "name": "Gain"}})
        assert r.status_code == 200
        m = cl.get(f"{base}/mix")
        assert m.status_code == 422 and "build_vsthost" in m.json()["detail"]
