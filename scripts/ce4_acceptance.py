"""CE4 (proto01_animate 30 §5, D126, O6): colour on a FilmCraft cut, accepted on the rig — the pinned FilmCraft through the app's API on a
fresh copy of the A1 rig's project (the composition's render, 121 f @ 24, dissolving into Mara's performance, 77 f @ 16), both shots in
one place (a Flow node each, the same Cast place). Measured on FilmCraft's own frames (the viewer's) and the movie:

1. the presets and looks are FilmCraft's (18 and 8);
2. *Grade the scene*: an adjustment layer on the top Grade track over both shots, named after the place; asked again, the same grade;
3. a preset (*Golden Dusk*) warms both shots (red over blue up), a value (exposure +1) brightens, a look (*Teal & Orange*) and a LUT file
   of ours (red and blue swapped) change the picture as they should;
4. Mara's shot matched to the composition: FilmCraft's distance falls, and her frame's mean colour moves toward the composition's;
5. reset and the cut's undo;
6. the movie carries the grade (its frame against the viewer's);
7. a frame with the grades, warm, at ½.

CPU only but for RIFE's short conform in the movie (as the final's assembly); no other GPU job may run. Results:
engine/spikes/out/ce4/results.json; frames in engine/spikes/out/ce4/.

    orchestrator/.venv/Scripts/python.exe scripts/ce4_acceptance.py
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

import av  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ce4"
COMP, MARA = "clp_63a32a9e", "clp_1abe92b9"


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
        room = st.create_profile("The room", "place", GroupStore(ws, svc.catalogue))
        nodes = []
        for title in ("Mara waits", "Mara comes in"):
            n = st.create_node("dialogue", title=title, with_shot=False)
            nodes.append(st.patch_node(n.id, {"revision": n.revision, "place_id": room.id}))
        tl = cl.post("/timelines", json={"name": "A1 colour", "fps": 24, "w": 1920, "h": 1080}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": nodes[0].id},
                                                                   {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16, "node_id": nodes[1].id}],
                                                   "overlaps": [0, 12]}).json()
        base = f"/timelines/{tl['id']}"
        v1 = cl.get(f"{base}/tracks").json()["video"][0]["items"]
        comp, mara = v1[0], v1[1]
        t_comp, t_mara = (comp["start"] + 24) / 24, (mara["start"] + mara["duration"] - 24) / 24      # a frame well inside each shot

        def frame(t: float, name: str | None = None, side: int = 960) -> np.ndarray:
            r = cl.get(f"{base}/frame", params={"t": t, "side": side})
            assert r.status_code == 200, r.text
            if name:
                (OUT / f"{name}.png").write_bytes(r.content)
            return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=np.float64)

        def call(route: str, body: dict) -> dict:
            r = cl.post(f"{base}/{route}", json=body)
            assert r.status_code == 200, r.text
            return r.json()
        warmth = lambda a: float(a[..., 0].mean() - a[..., 2].mean())   # noqa: E731 — red over blue
        # 1 · FilmCraft's lists
        looks = cl.get("/colour/looks").json()
        check("the presets and looks are FilmCraft's", len(looks["presets"]) == 18 and len(looks["looks"]) == 8,
              f"{len(looks['presets'])} presets in {len({p['folder'] for p in looks['presets']})} folders, {len(looks['looks'])} looks")
        before = {"comp": frame(t_comp, "0-comp"), "mara": frame(t_mara, "0-mara")}
        # 2 · the scene
        r = call("grade/scene", {"clip": mara["id"]})
        made = r["results"][0]
        grade_track = r["tracks"]["video"][-1]
        adj = grade_track["items"][0]
        end = max(i["start"] + i["duration"] for i in r["tracks"]["video"][0]["items"])
        check("Grade the scene: one layer over both shots, named after the place",
              made["made"] and made["shots"] == 2 and grade_track["name"] == "Grade" and adj["name"] == "Grade · The room" and adj["start"] == comp["start"] and abs(adj["start"] + adj["duration"] - end) < 1e-6,
              f"{made}; {adj['name']} {adj['start']}–{adj['start'] + adj['duration']} of {end} frames")
        again = call("grade/scene", {"clip": comp["id"]})["results"][0]
        check("asked again, the same grade", again["clip"] == adj["id"] and not again["made"], str(again))
        # 3 · preset, value, look, LUT file
        call("grade", {"clip": adj["id"], "preset": "Golden Dusk"})
        dusk = {"comp": frame(t_comp, "1-dusk-comp"), "mara": frame(t_mara, "1-dusk-mara")}
        dw = {k: warmth(dusk[k]) - warmth(before[k]) for k in dusk}
        res["golden_dusk_warmth"] = {k: round(v, 1) for k, v in dw.items()}
        check("a preset grades both shots (Golden Dusk: warmer)", all(v > 3 for v in dw.values()), f"red−blue +{dw['comp']:.1f} / +{dw['mara']:.1f} levels")
        call("grade", {"clip": adj["id"], "values": {"exposure": 1.0}})
        bright = frame(t_comp)
        lift = bright.mean() - dusk["comp"].mean()
        check("a value: exposure +1 brightens", lift > 5, f"mean +{lift:.1f} levels")
        call("grade", {"clip": adj["id"], "values": {"exposure": 0.0}, "look": "builtin:look-teal-orange"})
        teal = frame(t_comp, "2-teal")
        check("a look: Teal & Orange", float(np.abs(teal - dusk["comp"]).mean()) > 3, f"mean change {float(np.abs(teal - dusk['comp']).mean()):.1f} levels")
        cube = OUT / "swap-rb.cube"
        rows = [f"{b} {g} {r}" for b in (0, 1) for g in (0, 1) for r in (0, 1)]      # red fastest: the output is (b, g, r) — red and blue swapped
        cube.write_text("TITLE \"swap red and blue\"\nLUT_3D_SIZE 2\n" + "\n".join(rows) + "\n", encoding="utf-8")
        call("grade", {"clip": adj["id"], "preset": "Neutral Mono"})                 # out of the way: a grey picture, then the LUT alone
        call("grade", {"clip": adj["id"], "reset": True})
        call("grade/scene", {"clip": comp["id"]})
        call("grade", {"clip": adj["id"], "look_file": str(cube)})
        swapped = frame(t_comp, "3-swap")
        res["lut_swap"] = {"before_rb": [round(before["comp"][..., 0].mean(), 1), round(before["comp"][..., 2].mean(), 1)],
                           "after_rb": [round(swapped[..., 0].mean(), 1), round(swapped[..., 2].mean(), 1)]}
        check("a LUT file of ours (red and blue swapped)", abs(swapped[..., 0].mean() - before["comp"][..., 2].mean()) < 8 and abs(swapped[..., 2].mean() - before["comp"][..., 0].mean()) < 8,
              str(res["lut_swap"]))
        call("grade", {"clip": adj["id"], "reset": True})
        # 4 · Mara matched to the composition
        r = call("grade", {"clip": mara["id"], "match": comp["id"]})
        m = r["results"][0]["match"]
        matched = frame(t_mara, "4-matched")
        dist = lambda a, b: float(np.abs(a.reshape(-1, 3).mean(0) - b.reshape(-1, 3).mean(0)).sum())   # noqa: E731 — mean colours apart
        d0, d1 = dist(before["mara"], before["comp"]), dist(matched, before["comp"])
        res["match"] = {"filmcraft": m, "mean_rgb_apart": [round(d0, 1), round(d1, 1)]}
        check("Mara matched to the composition", m["after"] < m["before"] and d1 < d0, f"FilmCraft {m['before']} → {m['after']}; mean colours {d0:.1f} → {d1:.1f} apart")
        # 5 · reset and undo
        r = call("grade", {"clip": mara["id"], "reset": True})
        gone = next(i for i in r["tracks"]["video"][0]["items"] if i["id"] == mara["id"])["grade"] is None
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        back = next(i for i in r["tracks"]["video"][0]["items"] if i["id"] == mara["id"])["grade"]
        check("reset, and the cut's undo", gone and back is not None and back["matched"], f"reset {gone}, undone {bool(back and back['matched'])}")
        # the scene graded again for the movie
        call("grade", {"clip": adj["id"], "preset": "Golden Dusk"})
        view = frame(t_comp, "5-view", side=1920)
        # 7 · frames with the grades
        times = []
        for k in range(12):
            t0 = time.perf_counter()
            frame(t_comp + k / 24)
            times.append((time.perf_counter() - t0) * 1000)
        res["graded_frame_ms"] = {"median": round(float(np.median(times[2:])), 1), "max": round(max(times[2:]), 1)}
        # 6 · the movie
        job = cl.post(f"{base}/render", json={"movie": True}).json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 600:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.25)
        res["movie_s"] = round(time.time() - t0, 1)
        if j["status"] == "done":
            with av.open(str(ws.path / j["result"]["path"])) as c:
                want = int(round(t_comp * 24))
                img = next(f.to_ndarray(format="rgb24") for k, f in enumerate(c.decode(video=0)) if k == want).astype(np.float64)
            Image.fromarray(img.astype(np.uint8)).save(OUT / "6-movie.png")
            diff = float(np.abs(img - view).mean())
            check("the movie carries the grade", diff < 6 and warmth(img) - warmth(before["comp"]) > 3, f"mean diff to the viewer {diff:.1f}; warmth +{warmth(img) - warmth(before['comp']):.1f}; {res['movie_s']} s")
        else:
            check("the movie carries the grade", False, j.get("error") or j["status"])
        check("frames with the grades are quick (½)", res["graded_frame_ms"]["median"] < 60, str(res["graded_frame_ms"]))
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ce4_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
