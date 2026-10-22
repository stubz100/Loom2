"""A stand-in for tools/lipsync/sync.py (AE4d's tests and the e2e smoke): reads the request, prints the runner's lines, writes the output
mp4 as the input's frames with the mouth region (the lower middle) painted red, at the input's rate, and the result JSON. Runs under the
orchestrator's python (it needs `av` and numpy); never touches a GPU. FAKE_LIPSYNC_FAIL=1 exits 1 after loading.

    python fake_lipsync.py <request.json>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    import av
    import numpy as np
    req = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    print("loading LatentSync 1.5 (fake)", flush=True)
    time.sleep(0.05)
    if os.environ.get("FAKE_LIPSYNC_FAIL"):
        print("boom: the fake runner was told to fail", flush=True)
        return 1
    if not Path(req["audio"]).is_file():
        print(f"no audio at {req['audio']}", flush=True)
        return 1
    print(f"syncing {Path(req['video']).name} to {Path(req['audio']).name}: {req.get('steps')} steps (fake)", flush=True)
    t0 = time.time()
    with av.open(str(req["video"])) as c:
        rate = c.streams.video[0].average_rate or 25
        frames = [fr.to_ndarray(format="rgb24") for fr in c.decode(video=0)]
    out = Path(req["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(out), "w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=rate)
        stream.width, stream.height, stream.pix_fmt = frames[0].shape[1], frames[0].shape[0], "yuv420p"
        stream.options = {"crf": "10", "preset": "veryfast"}
        for a in frames:
            h, w = a.shape[:2]
            a = a.copy()
            a[int(h * 0.6):int(h * 0.8), int(w * 0.35):int(w * 0.65)] = (255, 0, 0)       # the mouth, "redrawn"
            for packet in stream.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(a), format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    if req.get("result"):
        Path(req["result"]).write_text(json.dumps({"seconds": round(time.time() - t0, 2), "out": str(out), "frames": len(frames)}), encoding="utf-8")
    print(f"done in {time.time() - t0:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
