"""CE5 (proto01_animate 30 §5, D126): captions and delivery on a FilmCraft cut, accepted on the rig — the pinned FilmCraft through the
app's API on a fresh copy of the A1 rig's project (the composition dissolving into Mara's performance), a Dialogue node on the composition
with two lines, the first voiced (a tone). Checks:

1. *Captions from the lines*: two captions — the voiced line where its clip sits, the other across its shot; FilmCraft's viewer draws them;
2. a caption edited and moved by FilmCraft's commands; the SRT export is the caption track's;
3. the author's marker kept through a change (the chapters rebuilt), renamed, in markers.txt and FilmCraft's FCPXML, removed;
4. the movie with the captions burned in (the caption's region against the plain movie at the same frame; nothing elsewhere);
5. ProRes 422 HQ (.mov, the prores codec) with the captions beside it as SRT and as WebVTT.

CPU only but for RIFE's short conform in each movie (as the final's assembly); no other GPU job may run. Results:
engine/spikes/out/ce5/results.json; frames in engine/spikes/out/ce5/.

    orchestrator/.venv/Scripts/python.exe scripts/ce5_acceptance.py
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
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from fake_tts import tone  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ce5"
COMP, MARA = "clp_63a32a9e", "clp_1abe92b9"
TICK = 254_016_000_000


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
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in, quickly."}, {"speaker": None, "text": "Close the door behind you."}]})
        wav = OUT / "line0.wav"
        tone(str(wav), 1.4, hz=440.0)
        st.set_line_audio(n.id, 0, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        tl = cl.post("/timelines", json={"name": "A1 captions", "fps": 24, "w": 1920, "h": 1080}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": n.id},
                                                                   {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16}], "overlaps": [0, 12]}).json()
        base = f"/timelines/{tl['id']}"
        rev = cl.get(base).json()["revision"]

        def call(route: str, body: dict) -> dict:
            nonlocal rev
            r = cl.post(f"{base}/{route}", json={"revision": rev, **body})
            assert r.status_code == 200, r.text
            rev = r.json()["timeline"]["revision"]
            return r.json()

        def frame(t: float, name: str) -> np.ndarray:
            r = cl.get(f"{base}/frame", params={"t": t, "side": 960})
            assert r.status_code == 200, r.text
            (OUT / f"{name}.png").write_bytes(r.content)
            return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=np.float64)
        band = lambda a: a[int(a.shape[0] * 0.80):int(a.shape[0] * 0.97), int(a.shape[1] * 0.2):int(a.shape[1] * 0.8)]   # noqa: E731 — where a bottom caption sits
        top = lambda a: a[:int(a.shape[0] * 0.5)]   # noqa: E731
        # 1 · captions from the lines
        r = call("captions", {})
        tr = r["tracks"]
        line = tr["audio"][0]["items"][0]
        caps = tr["captions"][0]["captions"]
        res["captions"] = [(c["text"], c["start"], c["duration"]) for c in caps]
        check("captions from the lines: the voiced line where its clip sits, the other across its shot",
              [c["text"] for c in caps] == ["Come in, quickly.", "Close the door behind you."] and (caps[0]["start"], caps[0]["duration"]) == (line["start"], line["duration"]) and caps[1]["start"] >= caps[0]["start"] + caps[0]["duration"],
              str(res["captions"]))
        t_cap = (caps[0]["start"] + caps[0]["duration"] / 2) / 24
        with_cap = frame(t_cap, "1-caption")
        call("edit", {"steps": [{"id": "captions.setTrack", "params": {"track": tr["captions"][0]["id"], "enabled": False}}]})
        hidden = frame(t_cap, "1-hidden")
        call("edit", {"steps": [{"id": "captions.setTrack", "params": {"track": tr["captions"][0]["id"], "enabled": True}}]})
        d_band, d_top = float(np.abs(band(with_cap) - band(hidden)).mean()), float(np.abs(top(with_cap) - top(hidden)).mean())
        check("FilmCraft's viewer draws them (hidden: not)", d_band > 4 and d_top < 0.5, f"bottom band {d_band:.1f} levels, top half {d_top:.2f}")
        # 2 · edited and moved; the SRT is the caption track's
        r = call("edit", {"steps": [{"id": "captions.setText", "params": {"caption": caps[1]["id"], "text": "Shut the door."}},
                                    {"id": "captions.move", "params": {"captions": [caps[1]["id"]], "deltaFrames": 6}}]})
        moved = r["tracks"]["captions"][0]["captions"][1]
        srt = cl.post(f"{base}/export", json={"format": "srt"}).json()["text"]
        check("a caption edited and moved; the SRT is the caption track's", moved["text"] == "Shut the door." and moved["start"] == caps[1]["start"] + 6 and "Shut the door." in srt and "Close the door" not in srt,
              f"{moved['text']!r} at {moved['start']}; SRT {srt.count('-->')} cues")
        # 3 · the author's marker
        r = call("edit", {"steps": [{"id": "markers.add", "params": {"target": "program", "time": 48 * TICK // 24, "name": "fix the light", "comment": "too dark here"}}]})
        r = call("edit", {"steps": [{"id": "timeline.setTrack", "params": {"track": "V2", "name": "Inserts"}}]})
        mine = [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"]
        chapters = [m["name"] for m in r["tracks"]["markers"] if m["kind"] == "Chapter"]
        check("the author's marker kept through a change, the chapters rebuilt", [(m["name"], m["frame"]) for m in mine] == [("fix the light", 48.0)] and "Gate" in chapters, f"{[m['name'] for m in mine]}; chapters {chapters}")
        r = call("edit", {"steps": [{"id": "markers.edit", "params": {"target": "program", "marker": mine[0]["id"], "name": "warmer light"}}]})
        folder = Path(cl.post(f"{base}/export", json={"format": "resolve"}).json()["path"])
        folder = folder if folder.is_absolute() else ws.path / folder
        mtxt = (folder / "markers.txt").read_text(encoding="utf-8")
        fcpxml = next(folder.glob("*.fcpxml")).read_text(encoding="utf-8")
        check("renamed, in markers.txt and FilmCraft's FCPXML", "warmer light — too dark here" in mtxt and "warmer light" in fcpxml and "Gate" in mtxt, mtxt.strip().replace("\n", " | "))
        mine = [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"]
        r = call("edit", {"steps": [{"id": "loom2.removeMarker", "params": {"marker": mine[0]["id"]}}]})
        check("removed, the chapters stay", not [m for m in r["tracks"]["markers"] if m["kind"] != "Chapter"] and any(m["kind"] == "Chapter" for m in r["tracks"]["markers"]), "")

        def movie(body: dict) -> dict:
            job = cl.post(f"{base}/render", json={"movie": True, **body}).json()["jobs"][0]
            cl.post("/queue/unpause")
            t0 = time.time()
            while time.time() - t0 < 600:
                j = cl.get(f"/jobs/{job['id']}").json()
                if j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(0.25)
            j["wall_s"] = round(time.time() - t0, 1)
            return j

        def movie_frame(path: Path, k: int) -> tuple[np.ndarray, str]:
            with av.open(str(path)) as c:
                codec = c.streams.video[0].codec_context.name
                img = next(f.to_ndarray(format="rgb24") for i, f in enumerate(c.decode(video=0)) if i == k)
            return img.astype(np.float64), codec
        # 4 · burned in
        k_cap = int(round(t_cap * 24))
        plain = movie({})
        p_path = ws.path / plain["result"]["path"]
        shutil.copyfile(p_path, OUT / "plain.mp4")
        burned = movie({"burn_captions": True})
        b_path = ws.path / burned["result"]["path"]
        a, _ = movie_frame(OUT / "plain.mp4", k_cap)
        b, _ = movie_frame(b_path, k_cap)
        Image.fromarray(b.astype(np.uint8)).save(OUT / "4-burned.png")
        a2, _ = movie_frame(OUT / "plain.mp4", 200)
        b2, _ = movie_frame(b_path, 200)
        db_, dt_, dn_ = float(np.abs(band(b) - band(a)).mean()), float(np.abs(top(b) - top(a)).mean()), float(np.abs(b2 - a2).mean())
        res["burn"] = {"band": round(db_, 1), "top": round(dt_, 2), "no_caption_frame": round(dn_, 2), "wall_s": [plain["wall_s"], burned["wall_s"]]}
        check("the movie with the captions burned in", burned["status"] == "done" and burned["result"]["burn_captions"] and db_ > 4 and dt_ < 1.0 and dn_ < 1.0, str(res["burn"]))
        # 5 · ProRes with the captions beside it (SRT, then WebVTT)
        pro = movie({"delivery": "prores", "captions_file": "srt"})
        ok_pro = pro["status"] == "done"
        codec = movie_frame(ws.path / pro["result"]["path"], 10)[1] if ok_pro else ""
        side = ws.path / pro["result"]["captions_file"] if ok_pro and pro["result"].get("captions_file") else None
        srt_side = side.read_text(encoding="utf-8") if side else ""
        vtt = movie({"delivery": "prores", "captions_file": "vtt"})
        vtt_side = (ws.path / vtt["result"]["captions_file"]).read_text(encoding="utf-8") if vtt["status"] == "done" and vtt["result"].get("captions_file") else ""
        res["prores"] = {"path": pro["result"].get("path") if ok_pro else None, "codec": codec, "bytes": (ws.path / pro["result"]["path"]).stat().st_size if ok_pro else 0,
                         "wall_s": pro["wall_s"]}
        check("ProRes 422 HQ (.mov) with the captions beside it as SRT and WebVTT",
              ok_pro and pro["result"]["path"].endswith(".mov") and codec == "prores" and "Shut the door." in srt_side and "-->" in srt_side and vtt_side.startswith("WEBVTT") and "Shut the door." in vtt_side,
              f"{res['prores']}; SRT {srt_side.count('-->')} cues, VTT {vtt_side.count('-->')} cues")
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ce5_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
