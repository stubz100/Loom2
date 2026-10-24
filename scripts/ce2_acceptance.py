"""CE2a (proto01_animate 30 §12, D126): the editor's server on the rig — the pinned FilmCraft through the app's API on a fresh copy of the A1
rig's project (the composition's render, 121 f @ 24, dissolving into Mara's performance, 77 f @ 16; Ines's performance as a third take; a
voiced line on the first). The same flow as tests/test_cuts_ce2.py on the real binary, so the fake's reading of FilmCraft is checked:

1. the tracks read from the project (two takes on V1 with the dissolve, D126's five tracks);
2. edits as FilmCraft commands under the cut's revision: a track named, a refused command and a stale base; the dissolve removed with
   the clip kept in place; razor, a piece to V2, speed, the cut's undo (the whole change); a ripple delete FilmCraft refuses (A1's sync
   lock) answered with its message and the cut unchanged — each edit's round trip timed;
3. *Update* in place (Ines for the first take, its start and length kept); a Catalogue picture on V2 and a sound on A2;
4. the viewer's frame; FilmCraft's FCPXML (carrying the shot's chapter marker) and EDL, the SRT from the project; the draft through
   FilmCraft.

CPU only (Mara stays a proxy: no movie here). Results: engine/spikes/out/ce2/results.json.

    orchestrator/.venv/Scripts/python.exe scripts/ce2_acceptance.py
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
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

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from fake_tts import tone  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.filmcraft import TICK  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ce2"
COMP, MARA, INES = "clp_63a32a9e", "clp_1abe92b9", "clp_def006ad"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {"edit_ms": {}}

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
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in."}]})
        wav = OUT / "line.wav"
        tone(str(wav), 1.0)
        st.set_line_audio(n.id, 0, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "Come in.")
        tl = cl.post("/timelines", json={"name": "A1 edit", "fps": 24, "w": 1920, "h": 1080}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": n.id},
                                                                   {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16}], "overlaps": [0, 12]}).json()
        base = f"/timelines/{tl['id']}"
        tr = cl.get(f"{base}/tracks").json()
        v1 = tr["video"][0]
        check("the tracks read from the project", [i["clip_id"] for i in v1["items"]] == [COMP, MARA] and v1["transitions"][0]["effect"] == "cross_dissolve"
              and (len(tr["video"]), len(tr["audio"])) == (2, 3) and [i["kind"] for i in tr["audio"][0]["items"]] == ["line"],
              str([(i["start"], i["duration"]) for i in v1["items"]]))
        rev = tl["revision"]

        def edit(name: str, steps: list[dict]) -> dict:
            nonlocal rev
            t0 = time.perf_counter()
            r = cl.post(f"{base}/edit", json={"revision": rev, "steps": steps})
            res["edit_ms"][name] = round((time.perf_counter() - t0) * 1000, 1)
            assert r.status_code == 200, r.text
            rev = r.json()["timeline"]["revision"]
            return r.json()["tracks"]
        trk = edit("name", [{"id": "timeline.setTrack", "params": {"track": "V1", "name": "Shots"}}])
        stale = cl.post(f"{base}/edit", json={"revision": rev - 1, "steps": [{"id": "timeline.setTrack", "params": {"track": "V1", "name": "x"}}]}).status_code
        refused = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "file.saveAs", "params": {"path": str(OUT / "x.fcproj")}}]}).status_code
        check("a track named; a stale base and a foreign command refused", trk["video"][0]["name"] == "Shots" and (stale, refused) == (409, 422), f"{stale} {refused}")
        before = [(i["clip_id"], i["start"], i["duration"], i["source_in"]) for i in trk["video"][0]["items"]]
        trk = edit("remove the dissolve", [{"id": "loom2.removeTransition", "params": {"transition": trk["video"][0]["transitions"][0]["id"]}}])
        after = [(i["clip_id"], i["start"], i["duration"], i["source_in"]) for i in trk["video"][0]["items"]]
        check("the dissolve removed, the clip kept in place", trk["video"][0]["transitions"] == [] and after == before, str(after))
        trk = edit("razor", [{"id": "timeline.razor", "params": {"time": 60 * TICK // 24, "track": "V1"}}])
        pieces = [(i["start"], i["duration"]) for i in trk["video"][0]["items"]]
        check("razor", len(pieces) == 3 and pieces[0] == (0, 60), str(pieces))
        piece = trk["video"][0]["items"][1]["id"]
        trk = edit("move to V2 + speed", [{"id": "timeline.move", "params": {"moves": [{"clip": piece, "track": "V2", "time": 140 * TICK // 24}], "insert": False}},
                                          {"id": "clip.speedDuration", "params": {"clips": [trk["video"][0]["items"][0]["id"]], "speed": 50, "ripple": False}}])
        check("a piece to V2, speed 50 %", [i["id"] for i in trk["video"][1]["items"]] == [piece] and trk["video"][0]["items"][0]["speed"] == 0.5)
        lane = cl.get(base).json()
        check("the lane: V1's takes in order", [c["clip_id"] for c in lane["clips"]] == [COMP, MARA] and lane["clips"][0]["node_id"] == n.id)
        t0 = time.perf_counter()
        r = cl.post(f"{base}/undo", json={"revision": rev})
        res["edit_ms"]["undo"] = round((time.perf_counter() - t0) * 1000, 1)
        rev, trk = r.json()["timeline"]["revision"], r.json()["tracks"]
        check("undo: the whole last change (the move and the speed)", trk["video"][0]["items"][0]["speed"] == 1.0 and trk["video"][1]["items"] == [] and trk["redo"] == 1)
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "edit.rippleDelete", "params": {"clips": [trk["video"][0]["items"][0]["id"]]}}]})
        same = cl.get(f"{base}/tracks").json()
        check("a ripple delete FilmCraft refuses: its message, the cut unchanged", r.status_code == 422 and r.json()["detail"].startswith("edit failed: this edit would break sync")
              and [i["id"] for i in same["video"][0]["items"]] == [i["id"] for i in trk["video"][0]["items"]] and same["undo"] == trk["undo"], r.json().get("detail", "")[:120])
        first = trk["video"][0]["items"][0]
        t0 = time.perf_counter()
        r = cl.post(f"{base}/replace", json={"revision": rev, "clip": first["id"], "clip_id": INES, "shot_id": "sht_x", "shot_version": "v2", "node_id": n.id})
        res["edit_ms"]["update in place"] = round((time.perf_counter() - t0) * 1000, 1)
        rev = r.json()["timeline"]["revision"]
        now = r.json()["tracks"]["video"][0]["items"][0]
        check("Update in place", (now["clip_id"], now["start"], now["duration"]) == (INES, first["start"], first["duration"]), str((now["clip_id"], now["start"], now["duration"])))
        pic = OUT / "title.png"
        Image.new("RGB", (1920, 1080), (240, 240, 240)).save(pic)
        pa = svc.catalogue.ingest_file(pic, kind="image", move=False, suite="import")
        music = OUT / "music.wav"
        tone(str(music), 3.0, hz=220)
        sa = svc.catalogue.ingest_file(music, kind="audio", move=False, suite="import")
        r = cl.post(f"{base}/place", json={"revision": rev, "asset_id": pa.id, "track": "V2", "frame": 0})
        ok_pic = r.status_code == 200
        r = cl.post(f"{base}/place", json={"revision": r.json()["timeline"]["revision"] if ok_pic else rev, "asset_id": sa.id, "track": "A2", "frame": 4})
        rev = r.json()["timeline"]["revision"]
        trk = r.json()["tracks"]
        check("a picture on V2, a sound on A2", ok_pic and trk["video"][1]["items"][0]["kind"] == "picture" and trk["audio"][1]["items"][0]["kind"] == "sound",
              str([(i["kind"], i["start"], i["duration"]) for i in trk["video"][1]["items"] + trk["audio"][1]["items"]]))
        ms = []
        for k in range(12):
            t0 = time.perf_counter()
            fr = cl.get(f"{base}/frame", params={"t": 1.0 + k / 24, "side": 960})
            ms.append((time.perf_counter() - t0) * 1000)
        res["frame_ms"] = {"median": round(statistics.median(ms), 1), "max": round(max(ms), 1)}
        check("the viewer's frame over HTTP", fr.status_code == 200 and fr.content[:4] == b"\x89PNG" and res["frame_ms"]["median"] < 80, str(res["frame_ms"]))
        fx = cl.post(f"{base}/export", json={"format": "fcpxml"}).json()
        ed = cl.post(f"{base}/export", json={"format": "edl"}).json()
        sr = cl.post(f"{base}/export", json={"format": "srt"}).json()
        check("FilmCraft's FCPXML (the chapter marker) and EDL, the SRT from the project", "<fcpxml" in fx["text"] and "chapter-marker" in fx["text"] and "Gate" in fx["text"]
              and ed["text"].startswith("TITLE:") and sr["text"].count("Come in.") == 1,
              f"fcpxml {len(fx['text'])} B, edl {len(ed['text'])} B")
        job = cl.post(f"{base}/render").json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 300:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.25)
        res["draft_s"] = round(time.time() - t0, 1)
        rec = ClipStore(ws).get(j.get("result", {}).get("clip_id", "")) if j["status"] == "done" else None
        check("the draft through FilmCraft", rec is not None and rec.w == 960 and any("render (FilmCraft)" in x for x in j.get("log_tail", [])),
              f"{res['draft_s']} s {rec.frames if rec else j.get('error')} frames {rec.w if rec else ''}×{rec.h if rec else ''}")
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("edit round trips (ms):", res["edit_ms"])
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ce2_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
