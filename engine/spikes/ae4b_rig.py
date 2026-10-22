"""AE4b rig (D118): a line as an audio layer on the PS5 rig's final through the app — E29b's English line ingested as an audio asset of the
rig's project, attached to Mara's layer at 1.0 s, moved by the lanes' command, the composition rendered (effectcraft-cli on the CPU, RIFE)
and the proxy checked for the audio stream; the line then removed. Outputs under engine/spikes/out/ae4b/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/ae4b_rig.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from m1_acceptance import Orch  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ae4b"
PROJECT = ROOT / "engine" / "spikes" / "out" / "ps5" / "project"
FID = "fin_0f41f551"
WAV = ROOT / "engine" / "spikes" / "out" / "e29b" / "en1.wav"
PORT = 8795


def log(m: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
    print(line, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    cat = Catalogue(Workspace(PROJECT))
    a = cat.ingest_file(WAV, kind="audio", suite="story", prompt_text="Hello, this is Mara.", params={"rig": "ae4b", "source": "E20 en1 draft"})
    a = cat.make_thumbs(a, WAV)
    log(f"audio asset {a.id} · {a.duration_s} s")
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    o = Orch(state, PORT, PROJECT).start(timeout=180)
    results: dict = {}
    try:
        h = o.http
        c0 = h.get(f"/finals/{FID}/composition").json()
        log(f"composition rev {c0['revision']} audio {len(c0.get('audio') or [])}")
        r = h.post(f"/finals/{FID}/composition/audio", json={"asset_id": a.id, "layer_id": "fig_m", "t": 1.0}, timeout=300)
        r.raise_for_status()
        c1 = r.json()
        au = c1["audio"][-1]
        log(f"attached: layer {au['layer']} file {au['file']} · composition rev {c1['revision']}")
        lay = next(l for l in h.get(f"/finals/{FID}/composition/layers").json()["items"] if l["id"] == au["layer"])
        log(f"  the layer: {lay['name']} in {lay['in']} out {lay['out']} start {lay['start']}")
        r = h.post(f"/finals/{FID}/composition/batch", json={"steps": [{"id": "layer.timing", "params": {"layers": [au["layer"]], "delta": 0.5}}]}, timeout=300)
        lay = next(l for l in h.get(f"/finals/{FID}/composition/layers").json()["items"] if l["id"] == au["layer"])
        log(f"  moved by the lanes' command: in {lay['in']} out {lay['out']} start {lay['start']}")
        t0 = time.time()
        jid = h.post(f"/finals/{FID}/composition/render", timeout=60).json()["job_id"]
        j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=1800)
        log(f"render {j['status']} in {time.time() - t0:.0f} s: {j.get('error') or ''} {j.get('log_tail', [])[-3:]}")
        results["render"] = {"status": j["status"], "wall_s": round(time.time() - t0), "clip_id": j.get("result", {}).get("clip_id")}
        if j["status"] == "done":
            import av
            clip = h.get(f"/clips/{j['result']['clip_id']}").json()
            proxy = PROJECT / clip["proxy_path"]
            with av.open(str(proxy)) as cont:
                streams = {"video": len(cont.streams.video), "audio": len(cont.streams.audio)}
                adur = float(cont.streams.audio[0].duration * cont.streams.audio[0].time_base) if cont.streams.audio else None
            log(f"  proxy {proxy.name}: streams {streams}, audio {adur} s, clip audio_asset_id {clip.get('audio_asset_id')}")
            results["proxy"] = {**streams, "audio_s": adur}
            shutil.copyfile(proxy, OUT / "final_with_line.mp4")
        r = h.delete(f"/finals/{FID}/composition/audio/{au['layer']}", timeout=300)
        log(f"removed: {r.status_code} composition rev {r.json().get('revision')} audio {len(r.json().get('audio') or [])}")
        results["removed"] = r.status_code
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        log(f"done: {json.dumps(results)}")
    finally:
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
