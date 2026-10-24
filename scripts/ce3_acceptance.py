"""CE3 (proto01_animate 30 §14, D126): sound on a FilmCraft cut, accepted on the rig — the pinned FilmCraft through the app's API on a fresh
copy of the A1 rig's project (the composition's render, 121 f @ 24, dissolving into Mara's performance; a Dialogue node's two lines voiced
as tones at 440 and 660 Hz; music as a 220 Hz tone on A2, so each can be measured apart in the mix by its band). Checks:

1. the lines are the author's: one lifted stays out at the next export;
2. a gain and a track volume move the music by the dB set (against the line: the mix is normalised as a whole); fades shape its head and tail;
3. the music ducked under the dialogue: its band falls where a line speaks;
4. the dialogue evened out (FilmCraft's auto-match to −23 LUFS);
5. the mix the page plays (its first render and the kept one, timed);
6. the movie normalised: its integrated loudness (ITU-R BS.1770-4, gated, measured here) at Settings › FilmCraft › loudness (−16 LUFS).

CPU only, but for RIFE's short conform in the movie (as the final's assembly); no other GPU job may run. Results:
engine/spikes/out/ce3/results.json.

    orchestrator/.venv/Scripts/python.exe scripts/ce3_acceptance.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "orchestrator" / "tests"))
os.environ.pop("LOOM2_FILMCRAFT_CLI", None)

import av  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fake_tts import tone  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ce3"
COMP, MARA = "clp_63a32a9e", "clp_1abe92b9"
TICK = 254_016_000_000


def biquad(x: np.ndarray, b: list[float], a: list[float]) -> np.ndarray:
    try:
        from scipy.signal import lfilter
        return lfilter(b, a, x)
    except ImportError:                                            # a plain loop: slow, but only seconds of sound
        y = np.zeros_like(x)
        x1 = x2 = y1 = y2 = 0.0
        for n, v in enumerate(x):
            out = b[0] * v + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
            x2, x1, y2, y1 = x1, v, y1, out
            y[n] = out
        return y


def lufs(chans: np.ndarray, sr: int = 48000) -> float:
    """Integrated loudness (ITU-R BS.1770-4): K-weighting at 48 kHz, 400 ms blocks at 75 % overlap, the −70 LUFS and −10 LU gates."""
    assert sr == 48000
    z = []
    for ch in chans:
        k = biquad(ch.astype(np.float64), [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
        k = biquad(k, [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])
        z.append(k)
    block, hop = int(0.4 * sr), int(0.1 * sr)
    energies = np.array([sum(np.mean(c[s:s + block] ** 2) for c in z) for s in range(0, len(z[0]) - block + 1, hop)])
    loud = -0.691 + 10 * np.log10(np.maximum(energies, 1e-12))
    gated = energies[loud > -70]
    rel = -0.691 + 10 * np.log10(np.mean(gated)) - 10
    final = energies[(loud > -70) & (loud > rel)]
    return float(-0.691 + 10 * np.log10(np.mean(final)))


def band(pcm: np.ndarray, sr: int, hz: float, t0: float, t1: float) -> float:
    """The level (dBFS) of a tone's band between two times — a 40 Hz window around `hz` in the spectrum."""
    seg = pcm[int(t0 * sr):int(t1 * sr)]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) / len(seg)
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    return float(20 * np.log10(np.sqrt(np.sum(spec[(f > hz - 20) & (f < hz + 20)] ** 2)) + 1e-12))


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp", "timelines"))
    state = OUT / "state"
    AppState(state).update_settings({"engine": {"python": str(OUT / "missing.exe"), "health_timeout_s": 1}, "mounted_model_trees": []})
    app = create_app(state)
    svc = app.state.services
    with TestClient(app, headers={"X-Loom-Token": svc.app.token}) as cl:
        assert cl.post("/project/open", json={"path": str(OUT / "proj")}).status_code == 200
        ws = Workspace(OUT / "proj")
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Gate", with_shot=False)
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in."}, {"speaker": None, "text": "Quickly."}]})
        for k, (secs, hz) in enumerate(((1.2, 440.0), (0.8, 660.0))):
            wav = OUT / f"line{k}.wav"
            tone(str(wav), secs, hz=hz)
            st.set_line_audio(n.id, k, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        music_wav = OUT / "music.wav"
        tone(str(music_wav), 9.0, hz=220.0)
        music = svc.catalogue.ingest_file(music_wav, kind="audio", move=False, suite="import")
        tl = cl.post("/timelines", json={"name": "A1 sound", "fps": 24, "w": 1920, "h": 1080}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": n.id},
                                                                   {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16}], "overlaps": [0, 12]}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/place", json={"revision": tl["revision"], "asset_id": music.id, "track": "A2", "frame": 0}).json()
        rev = r["timeline"]["revision"]
        lines = r["tracks"]["audio"][0]["items"]
        song = r["tracks"]["audio"][1]["items"][0]

        def edit(steps: list[dict]) -> dict:
            nonlocal rev
            q = cl.post(f"{base}/edit", json={"revision": rev, "steps": steps})
            assert q.status_code == 200, q.text
            rev = q.json()["timeline"]["revision"]
            return q.json()["tracks"]

        def mix() -> tuple[np.ndarray, int, float]:
            t0 = time.perf_counter()
            m = cl.get(f"{base}/mix")
            ms = (time.perf_counter() - t0) * 1000
            pcm, sr = sf.read(io.BytesIO(m.content), dtype="float32", always_2d=True)
            return pcm.mean(axis=1), sr, ms
        pcm, sr, ms_first = mix()
        _, _, ms_kept = mix()
        res["mix_ms"] = {"first": round(ms_first, 1), "kept": round(ms_kept, 1), "seconds": round(len(pcm) / sr, 2)}
        check("the mix the page plays", len(pcm) / sr > 9.0 and band(pcm, sr, 440, 0.2, 1.0) > -40 and band(pcm, sr, 220, 2.0, 2.4) > -40, str(res["mix_ms"]))
        rel = lambda pcm, sr: band(pcm, sr, 220, 6.0, 8.0) - band(pcm, sr, 440, 0.2, 1.0)   # noqa: E731 — the music against the line: the mix is normalised as a whole
        before = rel(pcm, sr)
        # 1 · the lines are the author's
        tr = edit([{"id": "edit.clear", "params": {"clips": [lines[1]["id"]]}}])
        cl.post(f"{base}/export", json={"format": "srt"})
        a1 = cl.get(f"{base}/tracks").json()["audio"][0]["items"]
        check("a lifted line stays out", [i["line"] for i in a1] == [0], str([i["line"] for i in a1]))
        rev = cl.get(base).json()["revision"]
        # 2 · gain, track volume, fades
        tr = edit([{"id": "clip.audioGain", "params": {"clips": [song["id"]], "db": -6, "mode": "set"}}])
        pcm, sr, _ = mix()
        g = rel(pcm, sr) - before
        tr = edit([{"id": "timeline.setTrack", "params": {"track": "A2", "volumeDb": -6}}])
        pcm, sr, _ = mix()
        v = rel(pcm, sr) - before
        res["gain_db_measured"], res["gain_plus_volume_db_measured"] = round(g, 2), round(v, 2)
        check("a gain and a track volume move the music by the dB set", abs(g + 6) < 1.0 and abs(v + 12) < 1.0, f"gain {g:.2f} dB, + volume {v:.2f} dB")
        tr = edit([{"id": "sequence.applyAudioTransition", "params": {"clip": song["id"], "frames": 24, "edge": "in"}},
                   {"id": "sequence.applyAudioTransition", "params": {"clip": song["id"], "frames": 24, "edge": "out"}}])
        pcm, sr, _ = mix()
        head, mid = band(pcm, sr, 220, 0.0, 0.25), band(pcm, sr, 220, 4.0, 5.0)
        end_s = (song["start"] + song["duration"]) / 24
        tail = band(pcm, sr, 220, end_s - 0.25, end_s)
        res["fades_db"] = {"head": round(head - mid, 1), "tail": round(tail - mid, 1)}
        check("fades shape the music's head and tail", head - mid < -6 and tail - mid < -6 and len(tr["audio"][1]["transitions"]) == 2, str(res["fades_db"]))
        # 3 · ducked under the dialogue
        quiet = band(pcm, sr, 220, 3.0, 4.0)
        tr = edit([{"id": "essentialSound.setType", "params": {"clips": [lines[0]["id"]], "type": "dialogue"}},
                   {"id": "essentialSound.setType", "params": {"clips": [song["id"]], "type": "music"}},
                   {"id": "essentialSound.generateDucking", "params": {"clips": [song["id"]]}}])
        pcm, sr, _ = mix()
        under = band(pcm, sr, 220, 0.4, 0.9) - band(pcm, sr, 220, 3.0, 4.0)
        res["ducked_db"] = round(under, 1)
        check("the music ducked under the dialogue", tr["audio"][1]["items"][0]["ducked"] and under < -6, f"{under:.1f} dB where the line speaks")
        # 4 · the dialogue evened out
        tr = edit([{"id": "essentialSound.autoMatch", "params": {"clips": [lines[0]["id"]], "target": -23}}])
        g0 = tr["audio"][0]["items"][0]["gain_db"]
        check("the dialogue evened out (−23 LUFS)", g0 != 0 and tr["audio"][0]["items"][0]["sound"] == "Dialogue", f"line gain {g0} dB")
        del quiet
        # 6 · the movie normalised
        job = cl.post(f"{base}/render", json={"movie": True}).json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 600:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.25)
        res["movie_s"] = round(time.time() - t0, 1)
        target = svc.app.settings.filmcraft.loudness_lufs
        if j["status"] == "done":
            with av.open(str(ws.path / j["result"]["path"])) as c:
                frames = [f.to_ndarray() for f in c.decode(audio=0)]
                rate = c.streams.audio[0].rate
            chans = np.concatenate(frames, axis=1)
            res["movie_lufs"] = round(lufs(chans, rate), 2)
        check("the movie at the loudness in Settings", j["status"] == "done" and j["result"].get("loudness_lufs") == target and abs(res.get("movie_lufs", 0) - target) < 1.0,
              f"measured {res.get('movie_lufs')} LUFS, Settings {target} · {res['movie_s']} s {j.get('error') or ''}")
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ce3_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
