"""AE5 (03 §AE5, proto01_animate 31 §4): the finished shot's render settings and output modules, accepted on the rig — the pinned
EffectCraft through the app's API on a fresh copy of the A1 rig's project (its final's composition):

1. the default settings render through EffectCraft's render queue (`run renderQueue.add … renderQueue.render`) frame for frame as AE1's
   `render` command did (the same frame, ≤ 1 level apart);
2. Draft at half the size, the alpha kept, a ProRes 4444 beside the master: the take's clip at half the size, its PNG master RGBA (opaque
   where the plate covers the frame) after RIFE's conform to 24 fps, the ProRes 4444 a 4:4:4 stream with alpha of as many frames;
3. the times of both renders.

RIFE's short conform is the only GPU use (D97: no other GPU job may run). Results: engine/spikes/out/ae5/results.json; frames there.

    orchestrator/.venv/Scripts/python.exe scripts/ae5_acceptance.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
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
os.environ.pop("LOOM2_EFFECTCRAFT_CLI", None)

import av  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.compositions import CompositionStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.finals import FinalStore  # noqa: E402
from loom2.mcp_session import cli_head  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
OUT = ROOT / "engine" / "spikes" / "out" / "ae5"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    state = OUT / "state"
    AppState(state).update_settings({"engine": {"python": str(OUT / "missing.exe"), "health_timeout_s": 1}, "mounted_model_trees": []})
    app = create_app(state)
    svc = app.state.services
    with TestClient(app, headers={"X-Loom-Token": svc.app.token}) as cl:
        assert cl.post("/project/open", json={"path": str(OUT / "proj")}).status_code == 200
        ws = Workspace(OUT / "proj")
        f = next(x for x in FinalStore(ws).list() if x.clip_id)
        cs = CompositionStore(ws)
        comp = cs.get(f)
        cl.post("/queue/unpause")

        def render(settings: dict) -> dict:
            assert cl.put(f"/finals/{f.id}/render", json=settings).status_code == 200
            jid = cl.post(f"/finals/{f.id}/composition/render").json()["job_id"]
            t0 = time.time()
            while time.time() - t0 < 1800:
                j = cl.get(f"/jobs/{jid}").json()
                if j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(0.5)
            j["took_s"] = round(time.time() - t0, 1)
            return j
        clips = ClipStore(ws)
        # 1 · the default settings, against AE1's `render` command on the same composition
        j = render({})
        check("the default render is done", j["status"] == "done", j.get("error") or "")
        new = clips.get(j["result"]["clip_id"])
        old_dir = OUT / "ae1"
        old_dir.mkdir()
        argv = [*cli_head(svc.app.settings.effectcraft), "render", "--project", str(cs.ecproj(f.id)), "--comp", comp.comp, "--out", str(old_dir / "f_[####].png"),
                "--format", "png", "--quality", "best", "--resolution", "full", "--channels", "rgb", "--start", "0", "--end", "0.0625"]
        subprocess.run(argv, check=True, capture_output=True, env={**os.environ, "RAYON_NUM_THREADS": str(svc.app.settings.effectcraft.threads)})
        a = np.asarray(Image.open(sorted(old_dir.glob("*.png"))[0]).convert("RGB"), dtype=np.float64)
        b = np.asarray(Image.open(clips.frame_path(new.id, 0)).convert("RGB"), dtype=np.float64)
        d = float(np.abs(a - b).max()) if a.shape == b.shape else 255.0
        check("the default render equals AE1's render (frame 0)", d <= 1.0, f"max diff {d:.0f} levels; {new.w}×{new.h}, {new.frames} f @ {new.fps}; {j['took_s']} s")
        res["default"] = {"took_s": j["took_s"], "max_diff": d, "frames": new.frames, "fps": new.fps}
        # 2 · Draft, half, the alpha kept, a ProRes 4444 beside the master
        j = render({"quality": "draft", "resolution": "half", "alpha": True, "prores": True})
        check("the half-size render with alpha and ProRes is done", j["status"] == "done", j.get("error") or "")
        half = clips.get(j["result"]["clip_id"])
        check("the clip is half the size", (half.w, half.h) == (new.w // 2, new.h // 2), f"{half.w}×{half.h} against {new.w}×{new.h}")
        im = Image.open(clips.frame_path(half.id, half.frames // 2))
        al = np.asarray(im.getchannel("A")) if im.mode == "RGBA" else None
        check("its master keeps the alpha through the conform", al is not None and half.fps == new.fps and half.frames == new.frames,
              f"{im.mode}, alpha {int(al.min()) if al is not None else '-'}…{int(al.max()) if al is not None else '-'}, {half.frames} f @ {half.fps}")
        mov = ws.path / j["result"]["prores"]
        with av.open(str(mov)) as c:
            s = c.streams.video[0]
            n = sum(1 for _ in c.decode(video=0))
            check("the ProRes 4444 beside the master", s.codec_context.name == "prores" and s.codec_context.pix_fmt.startswith("yuva444p") and n == half.frames and s.width == half.w,
                  f"{s.codec_context.pix_fmt}, {n} frames, {s.width}×{s.height}, {mov.stat().st_size // 1024} KiB")
        res["half"] = {"took_s": j["took_s"], "prores_bytes": mov.stat().st_size}
        check("the times", True, f"default {res['default']['took_s']} s, half + alpha + ProRes {j['took_s']} s")
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"ae5_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
