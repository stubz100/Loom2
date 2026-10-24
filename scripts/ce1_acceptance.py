"""CE1 (proto01_animate 30 §10, D126): the cut editor's engine accepted on the rig — the pinned FilmCraft (engine/tools/filmcraft, built by
scripts/build_filmcraft.py) through the app's API, on a fresh copy of the A1 rig's project (engine/spikes/out/a1/project: the composition's
render, 121 f @ 24, dissolving over 12 ticks into Mara's performance, 77 f @ 16; two voiced lines on the first — tones, the project has no
voice). Checks:

1. today's cut (a record with its lane, made without FilmCraft) is converted on its first change: the file is the project, the lane comes
   back exactly (clips, rates, the dissolve, the node's stamp), both lines on A1;
2. the movie is FilmCraft's export run by the queue: Mara's take conformed by the local RIFE and swapped in, the lane unchanged; 225
   frames at 1920×1080, the lines where A1 holds them;
3. it matches RC3's own movie of the same lane (a second, unconverted cut): mean difference per frame, the sound;
4. an edit (Mara trimmed to 70 frames, the dissolve 8) round-trips through the project;
5. the export's peak memory (a process of its own) and the session's warm frames at ½;
6. D97: the session and the export decode in software.

Runs on the CPU but for RIFE's short conform (as the final's assembly); no other GPU job may run. Results: engine/spikes/out/ce1/results.json.

    orchestrator/.venv/Scripts/python.exe scripts/ce1_acceptance.py
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from ctypes import wintypes
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
from fastapi.testclient import TestClient  # noqa: E402

from fake_tts import tone  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.cuts import CUT_FILE, lines, read  # noqa: E402
from loom2.filmcraft import TICK, export_argv, export_script  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import TimelineStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ce1"
COMP, MARA = "clp_63a32a9e", "clp_1abe92b9"


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def peak_gb(proc: subprocess.Popen) -> float:
    pmc = PMC()
    pmc.cb = ctypes.sizeof(pmc)
    ctypes.windll.psapi.GetProcessMemoryInfo(int(proc._handle), ctypes.byref(pmc), pmc.cb)   # type: ignore[attr-defined]
    return round(pmc.PeakWorkingSetSize / 2**30, 2)


def frames_of(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


def pcm_of(path: Path) -> np.ndarray:
    with av.open(str(path)) as c:
        return np.concatenate([f.to_ndarray().reshape(f.to_ndarray().shape[0], -1).mean(axis=0) for f in c.decode(audio=0)])


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    pin = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_filmcraft.py"), "--check"], capture_output=True, text=True)
    check("the pinned binary", pin.returncode == 0 and "matches its pin" in pin.stdout, pin.stdout.strip())
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
        for i, secs in enumerate((1.2, 0.8)):
            wav = OUT / f"line{i}.wav"
            tone(str(wav), secs, hz=330 + 110 * i)
            st.set_line_audio(n.id, i, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        lane = [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": n.id}, {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16}]
        legacy = TimelineStore(ws)                                     # today's cuts: records with their lanes, made without FilmCraft
        frames = {COMP: 121, MARA: 77}
        old, rc3 = legacy.create("A1 cut", 24, 1920, 1080), legacy.create("A1 cut (RC3)", 24, 1920, 1080)
        for t in (old, rc3):
            legacy.put(t.id, {**t.model_dump(by_alias=True), "clips": lane, "overlaps": [0, 12]}, frames)
        # 1 · converted on its first change
        before = cl.get(f"/timelines/{old.id}").json()
        check("today's cut is a record", before["file"] is None and len(before["clips"]) == 2)
        t0 = time.time()
        conv = cl.put(f"/timelines/{old.id}", json=before)
        res["convert_s"] = round(time.time() - t0, 2)
        conv = conv.json()
        same = [(c["clip_id"], c["in"], c["out"], c["fps"], c["node_id"]) for c in conv["clips"]] == [(c["clip_id"], c["in"], c["out"], c["fps"], c["node_id"]) for c in before["clips"]]
        check("converted on its first change", conv["file"] == CUT_FILE and same and conv["overlaps"] == [0, 12], f"{res['convert_s']} s")
        project = ws.timelines_dir / old.id / CUT_FILE
        ls = lines(read(project))
        check("both lines on A1", [(round(x["start"] * 24 / TICK), x["line"]) for x in ls] == [(0, 0), (60, 1)], str([(round(x["start"] * 24 / TICK), x["line"]) for x in ls]))

        def movie(tl_id: str) -> dict:
            job = cl.post(f"/timelines/{tl_id}/render", json={"movie": True}).json()["jobs"][0]
            cl.post("/queue/unpause")
            t1 = time.time()
            while time.time() - t1 < 600:
                j = cl.get(f"/jobs/{job['id']}").json()
                if j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(0.25)
            j["_wall"] = round(time.time() - t1, 1)
            return j
        # 2 · FilmCraft's movie
        j = movie(old.id)
        res["filmcraft_movie"] = {"wall_s": j["_wall"], "log": j.get("log_tail"), "error": j.get("error")}
        check("the movie is FilmCraft's export", j["status"] == "done" and j["result"].get("engine") == "filmcraft", f"{j['_wall']} s {j.get('error') or ''}")
        doc = read(project)
        kinds = {it["metadata"]["loom2.clip"]: it["metadata"]["loom2.media"] for it in doc["project"]["items"].values() if "loom2.clip" in it["metadata"]}
        after = cl.get(f"/timelines/{old.id}").json()
        check("Mara conformed and swapped in, the lane unchanged", kinds == {COMP: "master", MARA: "conform24"} and after["clips"] == conv["clips"], str(kinds))
        fc_movie = ws.path / j["result"]["path"]
        ff = frames_of(fc_movie)
        with av.open(str(fc_movie)) as c:
            size = (c.streams.video[0].codec_context.width, c.streams.video[0].codec_context.height)
        check("225 frames at 1920×1080", len(ff) == 225 and size == (1920, 1080), f"{len(ff)} {size}")
        # 3 · against RC3's own movie of the same lane
        j3 = movie(rc3.id)
        res["rc3_movie"] = {"wall_s": j3["_wall"], "log": j3.get("log_tail")}
        lf = frames_of(ws.path / j3["result"]["path"])
        diffs = {f: round(float(np.abs(ff[f].astype(int) - lf[f].astype(int)).mean()), 2) for f in (48, 114, 160, 224)}
        res["parity"] = diffs
        check("matches RC3's movie (mean ≤ 6 levels a frame)", len(lf) == 225 and max(diffs.values()) <= 6.0, str(diffs))
        fp, lp = pcm_of(fc_movie), pcm_of(ws.path / j3["result"]["path"])
        rms = lambda p, a, b: float(np.sqrt(np.mean(p[int(a * 48000):int(b * 48000)] ** 2)))   # noqa: E731
        spans = ((0.2, 1.0), (1.3, 2.4), (2.6, 3.2), (4.0, 8.0))
        res["audio_rms"] = {"filmcraft": [round(rms(fp, *s), 4) for s in spans], "rc3": [round(rms(lp, *s), 4) for s in spans]}
        check("the lines where RC3 puts them", all((x > 0.05) == (y > 0.05) for x, y in zip(*res["audio_rms"].values())), str(res["audio_rms"]))
        # 4 · an edit
        edit = cl.put(f"/timelines/{old.id}", json={**after, "clips": [after["clips"][0], {**after["clips"][1], "out": 70}], "overlaps": [0, 8]}).json()
        back = cl.get(f"/timelines/{old.id}").json()
        check("an edit round-trips", [c["out"] for c in back["clips"]] == [121, 70] and back["overlaps"] == [0, 8] and edit["revision"] == back["revision"])
        # 5 · the export's memory and the session's frames
        script = OUT / "export.jsonl"
        script.write_text(export_script(OUT / "direct.mp4", "h264", 24), encoding="utf-8")
        t1 = time.time()
        proc = subprocess.Popen(export_argv(svc.app.settings.filmcraft, svc.app, project, script), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        res["export"] = {"wall_s": round(time.time() - t1, 2), "peak_gb": peak_gb(proc), "returncode": proc.returncode}
        check("the export's memory", proc.returncode == 0 and res["export"]["peak_gb"] < 4.0, str(res["export"]))
        fc = svc.filmcraft
        fc.open(project)
        fc.frame(1.0, 960)
        ms = []
        for k in range(24):
            t1 = time.perf_counter()
            fc.frame(k / 24 + 2.0, 960)
            ms.append((time.perf_counter() - t1) * 1000)
        res["frames_half_ms"] = {"median": round(statistics.median(ms), 1), "max": round(max(ms), 1)}
        check("warm frames at ½", res["frames_half_ms"]["median"] < 60, str(res["frames_half_ms"]))
        # 6 · D97
        hw = fc.command("prefs.get", {"key": "playback.hardwareDecoding"})
        check("the session decodes in software", "off" in json.dumps(hw), json.dumps(hw)[:120])
        check("the export decodes in software", '"playback.hardwareDecoding": "off"' in script.read_text(encoding="utf-8"))
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ce1_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
