"""CE5 (proto01_animate 30 §5, D126): captions and delivery on a FilmCraft cut, on tests/fake_filmcraft.py (the real binary on the rig) —
*Captions from the lines* (a voiced line where its clip sits, the others laid across their shot; made again, the track is replaced), the
captions edited by FilmCraft's commands and the SRT taken from them, the author's markers kept beside loom2's chapters (added, renamed,
removed, in markers.txt), and the movie delivered as ProRes with the captions burned in and written beside it."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from test_cuts_ce3 import TICK, _client, _setup


def test_captions_markers_and_delivery(tmp_path: Path):
    app = _client(tmp_path)
    with TestClient(app) as cl:
        ws, tl, voice = _setup(app, cl, tmp_path)
        base = f"/timelines/{tl['id']}"
        line = cl.get(f"{base}/tracks").json()["audio"][0]["items"][0]
        # captions from the lines
        r = cl.post(f"{base}/captions", json={"revision": cl.get(base).json()["revision"]})
        assert r.status_code == 200, r.text
        assert r.json()["results"][0]["captions"] == 2
        ct = r.json()["tracks"]["captions"][0]
        assert (ct["name"], ct["size"], ct["background"], ct["anchor"]) == ("Lines", 42.0, True, "bottom")
        first, second = ct["captions"]
        assert (first["text"], first["start"], first["duration"]) == ("Come in.", line["start"], line["duration"])   # the voiced line where its clip sits
        assert second["text"] == "Sit down." and second["start"] >= 24                                              # the other laid across its shot
        # edited by FilmCraft's commands; the SRT is the caption track's
        rev = r.json()["timeline"]["revision"]
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "captions.setText", "params": {"caption": second["id"], "text": "Sit, please."}},
                                                                     {"id": "captions.move", "params": {"captions": [second["id"]], "deltaFrames": -6}}]})
        assert r.status_code == 200, r.text
        moved = r.json()["tracks"]["captions"][0]["captions"][1]
        assert (moved["text"], moved["start"]) == ("Sit, please.", second["start"] - 6)
        assert "Sit, please." in cl.post(f"{base}/export", json={"format": "srt"}).json()["text"]
        # made again: replaced from the lines
        r = cl.post(f"{base}/captions", json={}).json()
        assert len(r["tracks"]["captions"]) == 1 and [c["text"] for c in r["tracks"]["captions"][0]["captions"]] == ["Come in.", "Sit down."]
        # the author's markers beside the chapters: kept through a change, renamed, in markers.txt, removed
        rev = r["timeline"]["revision"]
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "markers.add", "params": {"target": "program", "time": 12 * TICK // 24, "name": "fix the light", "comment": "too dark"}}]}).json()
        mine = [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"]
        assert [(m["name"], m["frame"]) for m in mine] == [("fix the light", 12.0)] and any(m["kind"] == "Chapter" and m["name"] == "Gate" for m in r["tracks"]["markers"])
        r = cl.post(f"{base}/edit", json={"revision": r["timeline"]["revision"], "steps": [{"id": "timeline.setTrack", "params": {"track": "V2", "name": "Inserts"}}]}).json()
        mine = [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"]
        assert [m["name"] for m in mine] == ["fix the light"]                                                       # the chapters rebuilt, the author's kept
        r = cl.post(f"{base}/edit", json={"revision": r["timeline"]["revision"], "steps": [{"id": "markers.edit", "params": {"target": "program", "marker": mine[0]["id"], "name": "warmer"}}]}).json()
        cl.post(f"{base}/export", json={"format": "resolve"})
        folder = next((ws.path / "exports").rglob("markers.txt")) if (ws.path / "exports").exists() else next(ws.path.rglob("markers.txt"))
        assert "warmer — too dark" in folder.read_text(encoding="utf-8")
        mine = [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"]
        r = cl.post(f"{base}/edit", json={"revision": r["timeline"]["revision"], "steps": [{"id": "loom2.removeMarker", "params": {"marker": mine[0]["id"]}}]}).json()
        assert [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"] == [] and any(m["kind"] == "Chapter" for m in r["tracks"]["markers"])
        assert cl.post(f"{base}/edit", json={"steps": [{"id": "loom2.removeMarker", "params": {"marker": 999999}}]}).status_code == 422
        # the movie: ProRes, the captions burned in and beside it
        job = cl.post(f"{base}/render", json={"movie": True, "delivery": "prores", "burn_captions": True, "captions_file": "srt"}).json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 60:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j.get("error") or j.get("log_tail")
        res = j["result"]
        assert res["path"].endswith(".mov") and res["delivery"] == "prores" and res["burn_captions"] is True
        side = ws.path / res["captions_file"]
        assert side.suffix == ".srt" and "Come in." in side.read_text(encoding="utf-8")
