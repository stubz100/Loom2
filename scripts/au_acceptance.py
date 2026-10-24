"""D127 (proto01_animate 30 §16): every audio track a channel strip, accepted on the rig — the pinned FilmCraft through the app's API on a
fresh project (no take needed: the strip is about sound). The source is a stereo tone pair, 440 Hz on the left and 660 Hz on the right,
each at −60 dBFS, so each side and the strip's every stage can be measured apart by its band in FilmCraft's own mix (loudness off: the mix
as mixed). Parts:

    roles   a new cut's A1–A3 are Dialogue, Music, Effects with Settings › Audio's strips (the music's −6 dB gain heard in the mix); a role
            given to a track names it and sets its strip
    strip   gain +30 dB and volume +18 dB — past FilmCraft's +24 / +15 by a second stage — heard as +48 dB; volume −∞ is silence; pan
            100 % left leaves the right side silent and the left as it was; width 0 % makes both sides one; undo is the cut's; a change's time
    width   the author's law past 100 % (the patched FilmCraft, engine/patches/filmcraft): the left side at 200 % is 1.354 L − 0.646 R (the
            mid 3 dB down, the side doubled) — 440 Hz +2.63 dB and the right's 660 Hz in at −3.80 dB; at 150 % +1.37 / −9.65 dB (FilmCraft's
            own law would give +3.52 / −6.02 at 200 %)
    host    loom2's own VST3 host (AU3, engine/vsthost, the pinned build): every installed bundle scanned, one process each (the time, the
            failures), the scan kept; the SDK's sample effects — AGain at 0.5 is −6.02 dB sample for sample, ADelay at 0.25 s moves an
            impulse by 12000 samples, the two in a chain in order, a bypassed one skipped; a sample with no editor says so
    editor  one of the author's own effects (Kilohearts' free kHs Gain): its editor opened by the host in a window of its own, a screenshot,
            the window closed as the author would (WM_CLOSE), its state written and read back; its default passes the sound unchanged

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
PARTS = ("roles", "strip", "width", "host", "editor")
TOOLS = ROOT / "engine" / "tools" / "vsthost"
GAIN_UID, KHS_GAIN = "C18D3C1E719E4E29924D3ECAA5E4DA18", Path("C:/Program Files/Common Files/VST3/Kilohearts/kHs Gain.vst3")


def law(w: float) -> tuple[float, float]:
    """The left side's two tones at width `w` (1 = 100 %), in dB against the source: (L's own, R's leaking in)."""
    import math
    g = 10 ** (-0.15 * (w - 1)) if w > 1 else 1.0
    return 20 * math.log10(abs(g / 2 + w / 2)), 20 * math.log10(abs(g / 2 - w / 2))


def band(x: np.ndarray, hz: float, t0: float = 0.4, t1: float = 1.6) -> float:
    """The level (dB) of a tone's band between two times — a 40 Hz window around `hz` in the spectrum. Read against the source measured
    the same way (`SOURCE`): the Hann window spreads a sine over three bins, +1.76 dB on its own (the first run compared it to −60 dBFS)."""
    seg = x[int(t0 * SR):int(t1 * SR)]
    w = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg * w)) / (np.sum(w) / 2)
    f = np.fft.rfftfreq(len(seg), 1 / SR)
    return float(20 * np.log10(np.sqrt(np.sum(spec[(f > hz - 20) & (f < hz + 20)] ** 2)) + 1e-12))


def host_checks(parts: tuple[str, ...], check, res: dict, src: Path) -> None:
    """AU3: the real host through loom2's runner (loom2/vsthost.py)."""
    import subprocess
    from loom2.vsthost import VstHost, VstHostError
    app = AppState(OUT / "host-state")
    app.update_settings({"vsthost": {"folders": [str(TOOLS / "test-plugins")]}})
    host = VstHost(app)
    pin = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_vsthost.py"), "--check"], capture_output=True, text=True)
    check("the pinned host", pin.returncode == 0 and "matches its pin" in pin.stdout, pin.stdout.strip())
    gain_b, delay_b = str(TOOLS / "test-plugins" / "again-sample-accurate.vst3"), str(TOOLS / "test-plugins" / "adelay.vst3")
    if "host" in parts:
        t0 = time.perf_counter()
        found = host.plugins()
        t1 = time.perf_counter()
        host.plugins()
        t2 = time.perf_counter()
        names = {p["name"] for p in found["plugins"]}
        res["scan"] = {"effects": len(found["plugins"]), "failed": len(found["failed"]), "seconds": round(t1 - t0, 1), "kept_s": round(t2 - t1, 2),
                       "failures": found["failed"][:10]}
        check("every installed bundle scanned, one process each", {"AGain Sample Accurate", "ADelay"} <= names and len(found["plugins"]) > 2,
              f"{len(found['plugins'])} effects, {len(found['failed'])} failed, {t1 - t0:.1f} s (kept {t2 - t1:.2f} s)")
        st_g, st_d = OUT / "fx" / "gain.vststate", OUT / "fx" / "delay.vststate"
        host.state(gain_b, GAIN_UID, None, st_g, {1: 0.5})
        host.state(delay_b, "", None, st_d, {100: 0.25})
        out = OUT / "fx" / "gain.wav"
        host.render([{"bundle": gain_b, "uid": GAIN_UID, "state": st_g}], src, out)
        x, _ = sf.read(str(src), dtype="float32", always_2d=True)
        y, _ = sf.read(str(out), dtype="float32", always_2d=True)
        diff = float(np.max(np.abs(y - 0.5 * x)))
        check("AGain at 0.5: −6.02 dB, sample for sample", diff < 1e-6, f"max |out − 0.5 in| {diff:.1e}")
        imp = np.zeros((SR, 2), np.float32)
        imp[100] = 1.0
        sf.write(str(OUT / "fx" / "imp.wav"), imp, SR, subtype="FLOAT")
        chain = [{"bundle": gain_b, "uid": GAIN_UID, "state": st_g}, {"bundle": delay_b, "uid": "", "state": st_d},
                 {"bundle": gain_b, "uid": GAIN_UID, "state": st_g, "bypass": True}]
        r = host.render(chain, OUT / "fx" / "imp.wav", OUT / "fx" / "chain.wav")
        z, _ = sf.read(str(OUT / "fx" / "chain.wav"), dtype="float32", always_2d=True)
        nz = np.nonzero(np.abs(z[:, 0]) > 1e-4)[0]
        check("a chain in order: the gain, the delay (0.25 s), a bypassed one skipped",
              list(nz) == [12100] and abs(float(z[12100, 0]) - 0.5) < 1e-6 and r["effects"][2] == {"bypassed": True},
              f"impulse at {list(nz)[:3]} = {float(z[nz[0], 0]) if len(nz) else 0:.3f}; {r['effects']}")
        try:
            host.editor(gain_b, GAIN_UID, None, OUT / "fx" / "e.vststate", "AGain")
            check("a sample with no editor says so", False, "an editor opened")
        except VstHostError as e:
            check("a sample with no editor says so", "no editor" in str(e), str(e))
    if "editor" in parts:
        if not KHS_GAIN.exists():
            check("the author's effect's editor", False, f"{KHS_GAIN} is not installed")
            return
        import ctypes
        import threading
        from ctypes import wintypes
        from PIL import ImageGrab
        user32 = ctypes.windll.user32
        ctypes.windll.shcore.SetProcessDpiAwareness(2)              # the window's rectangle in the screen's own pixels, as the grab takes them
        title = "kHs Gain — AU acceptance (loom2)"
        shot: dict = {}

        def close_it() -> None:
            hwnd = 0
            for _ in range(200):
                hwnd = user32.FindWindowW("loom2-vsthost-editor", title)
                if hwnd:
                    break
                time.sleep(0.1)
            if not hwnd:
                return
            time.sleep(2.0)                                         # the editor paints
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            shot["size"] = (rect.right - rect.left, rect.bottom - rect.top)
            ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).convert("RGB").save(
                ROOT / ".docs" / "proto01_animate" / "img" / "30-au3-editor.jpg", quality=88)
            user32.PostMessageW(hwnd, 0x0010, 0, 0)                  # WM_CLOSE: as the author closes it
        th = threading.Thread(target=close_it)
        th.start()
        st = OUT / "fx" / "khs.vststate"
        t0 = time.perf_counter()
        try:
            host.editor(str(KHS_GAIN), "", None, st, title)
            ok, why = st.is_file() and st.stat().st_size > 12, f"state {st.stat().st_size if st.is_file() else 0} B"
        except VstHostError as e:
            ok, why = False, str(e)
        th.join()
        check("the author's effect: its editor opened and closed, its state written", ok and "size" in shot,
              f"{why}; window {shot.get('size')}; {time.perf_counter() - t0:.1f} s")
        if ok:
            ps = host.params(str(KHS_GAIN), "", st)
            out = OUT / "fx" / "khs.wav"
            host.render([{"bundle": str(KHS_GAIN), "uid": "", "state": st}], src, out)
            x, _ = sf.read(str(src), dtype="float32", always_2d=True)
            y, _ = sf.read(str(out), dtype="float32", always_2d=True)
            n = min(len(x), len(y))
            lv = 20 * np.log10(np.sqrt(np.mean(y[SR // 2:n] ** 2)) / np.sqrt(np.mean(x[SR // 2:n] ** 2)))
            res["khs_params"] = [(q["title"], q["shown"]) for q in ps["params"]][:8]
            check("its state reads back and its default passes the sound", len(ps["params"]) > 0 and abs(lv) < 0.1,
                  f"{len(ps['params'])} parameters ({', '.join(f'{a} {b}' for a, b in res['khs_params'][:3])}); level {lv:+.2f} dB")


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
        if "width" in parts:
            call("strip", {"track": a2, **neutral})
            ref = mix()
            r0 = (band(ref[:, 0], 440), band(ref[:, 1], 660))
            for w in (200, 150):
                call("strip", {"track": a2, **neutral, "width": w})
                pcm = mix()
                got = (band(pcm[:, 0], 440) - r0[0], band(pcm[:, 0], 660) - r0[1])
                want = law(w / 100)
                res[f"width{w}_left_db"] = [round(x, 2) for x in got]
                check(f"width {w} %: the author's law", all(abs(a - b) < 0.1 for a, b in zip(got, want)),
                      f"440 Hz {got[0]:+.2f} / 660 Hz in {got[1]:+.2f} dB (want {want[0]:+.2f} / {want[1]:+.2f})")
    if "host" in parts or "editor" in parts:
        host_checks(parts, check, res, src)
    res["checks"] = [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    n_ok = sum(ok for _, ok, _ in checks)
    print(f"au_acceptance: {n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
