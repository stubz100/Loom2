"""CE3a (proto01_animate 30 §14, D126): sound on a FilmCraft cut, on tests/fake_filmcraft.py (the real binary on the rig) — the lines are
the author's (a line lifted stays out at the next export, a line never placed comes in, a line moved to another audio track keeps its
subtitle there), the sound verbs through the editor's whitelist (gain, fades on either edge, the dialogue / music types and the ducking,
the dialogue's loudness, a track's volume) shown on the tracks, the mix the page plays (a WAV of every audio track, kept per revision),
and the movie normalised to the loudness in Settings."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.cuts import mix_name  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"
TICK = 254_016_000_000


def _client(tmp_path: Path, **audio):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}, "audio": audio})
    return create_app(state)


def _setup(app, cl, tmp_path: Path):
    """A cut of one 2 s take whose Dialogue node has two lines, the first voiced before the cut is made."""
    cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
    ws = Workspace(tmp_path / "proj")
    cs = ClipStore(ws)
    frames = []
    for i in range(48):
        p = tmp_path / f"f{i}.png"
        Image.new("RGB", (32, 24), (200, 0, 0)).save(p)
        frames.append(p)
    clip = cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt="s", seed=1, fps=24, start_asset_id="ast_x"))
    st = StoryStore(ws)
    n = st.create_node("dialogue", title="Gate", with_shot=False)
    n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in."}, {"speaker": None, "text": "Sit down."}]})
    svc = app.state.services

    def voice(k: int, secs: float, hz: float = 440.0) -> str:
        wav = tmp_path / f"l{k}-{hz:g}.wav"
        tone(str(wav), secs, hz=hz)
        a = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n.id, k, a.id, "x")
        return a.id
    voice(0, 0.5)
    tl = cl.post("/timelines", json={"name": "Sound", "fps": 24, "w": 64, "h": 36}).json()
    tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": clip.id, "in": 0, "out": 48, "node_id": n.id}], "overlaps": [0]}).json()
    return ws, tl, voice


def test_the_lines_are_the_authors(tmp_path: Path):
    app = _client(tmp_path)
    with TestClient(app) as cl:
        ws, tl, voice = _setup(app, cl, tmp_path)
        base = f"/timelines/{tl['id']}"
        a1 = cl.get(f"{base}/tracks").json()["audio"][0]["items"]
        assert [(i["kind"], i["line"]) for i in a1] == [("line", 0)]
        rev = cl.get(base).json()["revision"]
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "edit.clear", "params": {"clips": [a1[0]["id"]]}}]}).json()   # the author lifts line 1
        assert r["tracks"]["audio"][0]["items"] == []
        voice(1, 0.25)                                                                              # line 2 voiced: never placed
        srt = cl.post(f"{base}/export", json={"format": "srt"}).json()
        a1 = cl.get(f"{base}/tracks").json()["audio"][0]["items"]
        assert [i["line"] for i in a1] == [1] and srt["text"].count("-->") == 2                   # line 1 stays out (its subtitle stays, laid evenly)
        cl.post(f"{base}/export", json={"format": "edl"})
        assert [i["line"] for i in cl.get(f"{base}/tracks").json()["audio"][0]["items"]] == [1]
        # a line moved to A2 is still that line: no second copy on A1, its subtitle where it sits now
        rev = cl.get(base).json()["revision"]
        cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.move", "params": {"moves": [{"clip": a1[0]["id"], "track": "A2", "time": 36 * TICK // 24}], "insert": False}}]})
        srt = cl.post(f"{base}/export", json={"format": "srt"}).json()
        tr = cl.get(f"{base}/tracks").json()
        assert tr["audio"][0]["items"] == [] and [i["line"] for i in tr["audio"][1]["items"]] == [1]
        assert "00:00:01,500 --> 00:00:01,750\nSit down." in srt["text"]


def test_sound_verbs_the_mix_and_the_movies_loudness(tmp_path: Path):
    app = _client(tmp_path, loudness_lufs=-14.0)
    svc = app.state.services
    with TestClient(app) as cl:
        ws, tl, _ = _setup(app, cl, tmp_path)
        base = f"/timelines/{tl['id']}"
        music_wav = tmp_path / "music.wav"
        tone(str(music_wav), 1.5, hz=220)
        music = svc.catalogue.ingest_file(music_wav, kind="audio", move=False, suite="import")
        rev = cl.get(base).json()["revision"]
        r = cl.post(f"{base}/place", json={"revision": rev, "asset_id": music.id, "track": "A2", "frame": 0}).json()
        line, song = r["tracks"]["audio"][0]["items"][0], r["tracks"]["audio"][1]["items"][0]
        # the mix the page plays: both tracks, kept for the revision
        m1 = cl.get(f"{base}/mix")
        assert m1.status_code == 200 and m1.headers["content-type"] == "audio/wav"
        pcm, sr = sf.read(__import__("io").BytesIO(m1.content), dtype="float32")
        rms = lambda s0, s1: float(np.sqrt(np.mean(pcm[int(s0 * sr):int(s1 * sr)] ** 2)))   # noqa: E731
        music_before = rms(0.7, 1.4)
        assert rms(0.1, 0.4) > 0.1 and music_before > 0.1 and sr == 48000
        mixes = ws.timelines_dir / tl["id"] / "mix"
        assert [p.name for p in mixes.glob("*.wav")] == [mix_name(r["timeline"]["revision"], cl.get("/settings").json()["audio"]["loudness_lufs"])]   # V39: by revision and loudness
        # the verbs: gain, fades on both edges, the music ducked under the dialogue, the dialogue evened out, a track's volume
        steps = [{"id": "clip.audioGain", "params": {"clips": [song["id"]], "db": -12, "mode": "set"}},
                 {"id": "sequence.applyAudioTransition", "params": {"clip": song["id"], "frames": 6, "edge": "in"}},
                 {"id": "sequence.applyAudioTransition", "params": {"clip": song["id"], "frames": 6, "edge": "out"}},
                 {"id": "essentialSound.setType", "params": {"clips": [line["id"]], "type": "dialogue"}},
                 {"id": "essentialSound.setType", "params": {"clips": [song["id"]], "type": "music"}},
                 {"id": "essentialSound.generateDucking", "params": {"clips": [song["id"]]}},
                 {"id": "essentialSound.autoMatch", "params": {"clips": [line["id"]], "target": -23}},
                 {"id": "timeline.setTrack", "params": {"track": "A3", "volumeDb": -6}}]
        r = cl.post(f"{base}/edit", json={"revision": r["timeline"]["revision"], "steps": steps})
        assert r.status_code == 200, r.text
        tr = r.json()["tracks"]
        line, song = tr["audio"][0]["items"][0], tr["audio"][1]["items"][0]
        assert (song["gain_db"], song["sound"], song["ducked"], line["sound"], line["gain_db"]) == (-12.0, "Music", True, "Dialogue", -10.0)
        assert tr["audio"][2]["volume_db"] == -6.0 and len(tr["audio"][1]["transitions"]) == 2
        m2 = cl.get(f"{base}/mix")
        pcm, sr = sf.read(__import__("io").BytesIO(m2.content), dtype="float32")
        assert abs(rms(0.7, 1.4) / music_before - 10 ** (-12 / 20)) < 0.02                           # the music 12 dB down
        assert [p.name for p in mixes.glob("*.wav")] == [mix_name(r.json()["timeline"]["revision"], cl.get("/settings").json()["audio"]["loudness_lufs"])]   # the older mix went
        # the movie: FilmCraft's export at the loudness in Settings
        job = cl.post(f"{base}/render", json={"movie": True}).json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 60:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j.get("error") or j.get("log_tail")
        assert j["result"]["loudness_lufs"] == -14.0
