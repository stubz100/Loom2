"""RC2f (06 O3, proto01_animate 31 §3b): a Shot's grade made independent of its scene's, accepted on the rig — the pinned FilmCraft through
the app's API on a fresh copy of the A1 rig's project (the composition's render, then Mara's performance), both shots' Flow nodes in one
scene group. Measured on FilmCraft's own frames (the viewer's):

1. *Grade the scene* takes the scene group: one adjustment layer over both shots, named after the scene;
2. the scene graded (*Golden Dusk*, exposure +1): both shots warmer and brighter;
3. *Make its grade independent* on Mara's shot: the scene's layer cut away over it (it covers the composition alone now) and her shot
   carries the scene's Lumetri as its own — its look and values, and her frame as it was under the scene's layer;
4. the scene's grade changed after (exposure back to 0) moves the composition and leaves Mara's shot as it is.

CPU only; no other GPU job may run. Results: engine/spikes/out/rc2f/results.json; frames in engine/spikes/out/rc2f/.

    orchestrator/.venv/Scripts/python.exe scripts/rc2f_acceptance.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
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
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "rc2f"
COMP, MARA = "clp_63a32a9e", "clp_1abe92b9"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

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
        nodes = [st.create_node("dialogue", title=t, with_shot=False) for t in ("Mara waits", "Mara comes in")]
        st.create_scene("The room", [n.id for n in nodes])
        tl = cl.post("/timelines", json={"name": "A1 scene grade", "fps": 24, "w": 1920, "h": 1080}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": COMP, "in": 0, "out": 121, "node_id": nodes[0].id},
                                                                   {"id": "y", "clip_id": MARA, "in": 0, "out": 77, "fps": 16, "node_id": nodes[1].id}],
                                                   "overlaps": [0, 0]}).json()
        base = f"/timelines/{tl['id']}"
        v1 = cl.get(f"{base}/tracks").json()["video"][0]["items"]
        comp, mara = v1[0], v1[1]
        t_comp, t_mara = (comp["start"] + 24) / 24, (mara["start"] + mara["duration"] - 24) / 24

        def frame(t: float, name: str) -> np.ndarray:
            r = cl.get(f"{base}/frame", params={"t": t, "side": 960})
            assert r.status_code == 200, r.text
            (OUT / f"{name}.png").write_bytes(r.content)
            return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=np.float64)

        def call(route: str, body: dict) -> dict:
            r = cl.post(f"{base}/{route}", json=body)
            assert r.status_code == 200, r.text
            return r.json()
        warmth = lambda a: float(a[..., 0].mean() - a[..., 2].mean())   # noqa: E731 — red over blue
        before = {"comp": frame(t_comp, "0-comp"), "mara": frame(t_mara, "0-mara")}
        r = call("grade/scene", {"clip": mara["id"]})
        res, grade_track = r["results"][0], r["tracks"]["video"][-1]
        layer = next(i for i in grade_track["items"] if i["id"] == res["clip"])
        check("Grade the scene takes the scene group", res["made"] and res["shots"] == 2 and layer["name"] == "Grade · The room",
              f"{res['shots']} shots, {layer['name']!r}")
        call("grade", {"clip": layer["id"], "preset": "Golden Dusk"})
        call("grade", {"clip": layer["id"], "values": {"exposure": 1.0}})
        graded = {"comp": frame(t_comp, "1-comp"), "mara": frame(t_mara, "1-mara")}
        check("the scene graded: both warmer and brighter",
              all(warmth(graded[k]) - warmth(before[k]) > 3 and graded[k].mean() - before[k].mean() > 3 for k in graded),
              ", ".join(f"{k} warmth +{warmth(graded[k]) - warmth(before[k]):.1f} mean +{graded[k].mean() - before[k].mean():.1f}" for k in graded))
        r = call("grade/own", {"clip": mara["id"]})
        tracks = r["tracks"]
        spans = [(i["start"], i["start"] + i["duration"]) for i in tracks["video"][-1]["items"]]
        own = next(i for i in tracks["video"][0]["items"] if i["id"] == mara["id"])["grade"]
        check("the scene's layer cut away over Mara's shot", spans == [(comp["start"], comp["start"] + comp["duration"])], str(spans))
        check("her shot carries the scene's grade as its own", own is not None and abs(own["values"].get("exposure", 0) - 1.0) < 1e-6,
              str(own and {k: own["values"].get(k) for k in ("exposure", "temperature")}))
        alone = frame(t_mara, "2-mara-own")
        d = float(np.abs(alone - graded["mara"]).mean())
        check("her frame as it was under the scene's layer", d < 2.0, f"mean diff {d:.2f} levels")
        layer2 = next(i for i in tracks["video"][-1]["items"])
        call("grade", {"clip": layer2["id"], "values": {"exposure": 0.0}})
        after = {"comp": frame(t_comp, "3-comp"), "mara": frame(t_mara, "3-mara")}
        dc, dm = after["comp"].mean() - graded["comp"].mean(), float(np.abs(after["mara"] - alone).mean())
        check("the scene's change moves the composition, not her shot", dc < -3 and dm < 2.0, f"composition {dc:+.1f} levels, Mara {dm:.2f}")
    out = {"checks": [{"name": a, "ok": b, "detail": c} for a, b, c in checks]}
    (OUT / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"rc2f_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
