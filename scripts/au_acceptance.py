"""D127 (proto01_animate 30 §16): every audio track a channel strip, accepted on the rig — the pinned FilmCraft through the app's API on a
fresh project (no take needed: the strip is about sound). The source is a stereo tone pair, 440 Hz on the left and 660 Hz on the right,
each at −60 dBFS, so each side and the strip's every stage can be measured apart by its band in FilmCraft's own mix (loudness off: the mix
as mixed). Parts:

    roles   a new cut's A1–A3 are Dialogue, Music, Effects with Settings › Audio's strips (the music's −6 dB gain heard in the mix); a role
            given to a track names it and sets its strip
    strip   gain +30 dB and volume +18 dB — past FilmCraft's +24 / +15 by a second stage — heard as +48 dB; volume −∞ is silence; pan
            100 % left leaves the right side silent and the left as it was; width 0 % makes both sides one; undo is the cut's; a change's time

CPU only (FilmCraft); no GPU job may run beside it all the same (D97: the rig's checks take turns). Results: engine/spikes/out/au/results.json.

    orchestrator/.venv/Scripts/python.exe scripts/au_acceptance.py [--parts roles,strip]
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
os.environ.pop("LOOM2_FILMCRAFT_CLI", None)

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "au"
SR = 48000
LEVEL = -60.0                                                       # each side's tone, dBFS (+48 dB of strip stays below full scale)
PARTS = ("roles", "strip")


def band(x: np.ndarray, hz: float, t0: float = 0.4, t1: float = 1.6) -> float:
    """The level (dB) of a tone's band between two times — a 40 Hz window around `hz` in the spectrum. Read against the source measured
    the same way (`SOURCE`): the Hann window spreads a sine over three bins, +1.76 dB on its own (the first run compared it to −60 dBFS)."""
    seg = x[int(t0 * SR):int(t1 * SR)]
    w = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg * w)) / (np.sum(w) / 2)
    f = np.fft.rfftfreq(len(seg), 1 / SR)
    return float(20 * np.log10(np.sqrt(np.sum(spec[(f > hz - 20) & (f < hz + 20)] ** 2)) + 1e-12))


def main() -> int:
    parts = PARTS
    if "--parts" in sys.argv:
        parts = tuple(p for p in sys.argv[sys.argv.index("--parts") + 1].split(",") if p)
    checks: list[tuple[str, bool, str]] = []
    res: dict = {"parts": list(parts)}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    state = OUT / "state"
    AppState(state).update_settings({"engine": {"python": str(OUT / "missing.exe"), "health_timeout_s": 1}, "mounted_model_trees": [],
                                     "audio": {"loudness_lufs": None}})
    t = np.arange(int(2.0 * SR)) / SR
    a = 10 ** (LEVEL / 20)
    src = OUT / "pair.wav"
    sf.write(str(src), np.stack([a * np.sin(2 * np.pi * 440 * t), a * np.sin(2 * np.pi * 660 * t)], axis=1).astype(np.float32), SR, subtype="FLOAT")
    pcm0, _ = sf.read(str(src), dtype="float32", always_2d=True)
    src_l, src_r = band(pcm0[:, 0], 440), band(pcm0[:, 1], 660)
    res["source_band_db"] = [round(src_l, 2), round(src_r, 2)]
    app = create_app(state)
    svc = app.state.services
    with TestClient(app, headers={"X-Loom-Token": svc.app.token}) as cl:
        assert cl.post("/project", json={"path": str(OUT / "proj"), "name": "AU", "size_cap_gb": 10}).status_code == 200
        pair = svc.catalogue.ingest_file(src, kind="audio", move=False, suite="import")
        tl = cl.post("/timelines", json={"name": "Strip", "fps": 24, "w": 1920, "h": 1080}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/place", json={"revision": tl["revision"], "asset_id": pair.id, "track": "A2", "frame": 0})
        assert r.status_code == 200, r.text
        rev, tracks = r.json()["timeline"]["revision"], r.json()["tracks"]

        def call(route: str, body: dict) -> dict:
            nonlocal rev, tracks
            t0 = time.perf_counter()
            q = cl.post(f"{base}/{route}", json={"revision": rev, **body})
            assert q.status_code == 200, q.text
            rev, tracks = q.json()["timeline"]["revision"], q.json()["tracks"]
            res.setdefault("change_ms", []).append(round((time.perf_counter() - t0) * 1000, 1))
            return tracks

        def mix() -> np.ndarray:
            m = cl.get(f"{base}/mix")
            assert m.status_code == 200, m.text
            pcm, sr = sf.read(io.BytesIO(m.content), dtype="float32", always_2d=True)
            assert sr == SR and pcm.shape[1] == 2
            return pcm
        a2 = tracks["audio"][1]["id"]
        neutral = {"gain_db": 0, "volume_db": 0, "pan": 0, "width": 100}
        if "roles" in parts:
            got = [(x["name"], x["role"], x["gain_db"]) for x in tracks["audio"]]
            check("a new cut's tracks are the roles", got == [("Dialogue", "dialogue", 0.0), ("Music", "music", -6.0), ("Effects", "effects", -3.0)], str(got))
            pcm = mix()
            lv = (band(pcm[:, 0], 440) - src_l, band(pcm[:, 1], 660) - src_r)
            res["music_default_db"] = [round(x, 2) for x in lv]
            check("the music's −6 dB in the mix", all(abs(x + 6) < 0.5 for x in lv), f"L {lv[0]:+.2f} R {lv[1]:+.2f} dB against the source (want −6)")
            a3 = tracks["audio"][2]
            tr = call("role", {"track": a3["id"], "role": "music"})["audio"][2]
            check("a role names the track and sets its strip", (tr["name"], tr["role"], tr["gain_db"]) == ("Music", "music", -6.0), str((tr["name"], tr["role"], tr["gain_db"])))
        if "strip" in parts:
            call("strip", {"track": a2, **neutral})
            ref = mix()
            r0 = (band(ref[:, 0], 440), band(ref[:, 1], 660))
            check("a neutral strip passes the source", abs(r0[0] - src_l) < 0.1 and abs(r0[1] - src_r) < 0.1, f"L {r0[0] - src_l:+.2f} R {r0[1] - src_r:+.2f} dB against the source")
            tr = call("strip", {"track": a2, "gain_db": 30, "volume_db": 18})["audio"][1]
            pcm = mix()
            up = (band(pcm[:, 0], 440) - r0[0], band(pcm[:, 1], 660) - r0[1])
            res["gain30_volume18_db"] = [round(x, 2) for x in up]
            check("gain +30 and volume +18 past FilmCraft's limits", (tr["gain_db"], tr["volume_db"]) == (30.0, 18.0) and all(abs(x - 48) < 0.5 for x in up),
                  f"+{up[0]:.2f} / +{up[1]:.2f} dB (want +48)")
            call("strip", {"track": a2, **neutral, "volume_db": -96})
            pcm = mix()
            peak = float(np.max(np.abs(pcm))) if len(pcm) else 0.0
            check("volume −∞ is silence", peak < 1e-5, f"peak {peak:.2e}")
            call("strip", {"track": a2, **neutral, "pan": -100})
            pcm = mix()
            lv = (band(pcm[:, 0], 440) - r0[0], band(pcm[:, 1], 660))
            check("pan 100 % left: the right silent, the left as it was", abs(lv[0]) < 0.5 and lv[1] < -100, f"left {lv[0]:+.2f} dB, right {lv[1]:.1f} dBFS")
            call("strip", {"track": a2, **neutral, "width": 0})
            pcm = mix()
            k = int(0.05 * SR)                                       # FilmCraft's Stereo Width glides to its setting over 20 ms from the render's start
            same = float(np.max(np.abs(pcm[k:, 0] - pcm[k:, 1])))
            res["width0_start_glide_max_lr"] = round(float(np.max(np.abs(pcm[:k, 0] - pcm[:k, 1]))), 5)
            half = band(pcm[:, 0], 440) - r0[0]
            check("width 0 %: both sides one", same < 1e-5 and abs(half + 6.02) < 0.5, f"max |L−R| past 50 ms {same:.2e} (the first 50 ms {res['width0_start_glide_max_lr']:.1e}), 440 Hz in L {half:+.2f} dB (want −6.02)")
            r = cl.post(f"{base}/undo", json={"revision": rev}).json()
            rev = r["timeline"]["revision"]
            check("undo is the cut's", r["tracks"]["audio"][1]["width"] == 100.0 and r["tracks"]["audio"][1]["pan"] == -100.0, str({k: r["tracks"]["audio"][1][k] for k in ("pan", "width")}))
            res["change_ms_median"] = float(np.median(res["change_ms"]))
            check("a strip change is quick", res["change_ms_median"] < 500, f"median {res['change_ms_median']:.0f} ms over {len(res['change_ms'])}")
    res["checks"] = [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    n_ok = sum(ok for _, ok, _ in checks)
    print(f"au_acceptance: {n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
