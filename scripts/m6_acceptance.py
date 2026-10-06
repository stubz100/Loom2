"""M6 Animate acceptance (11 §11 items 1–3 and the Catalogue half of 5; 12 §7) against a running dev orchestrator with
the real engine.

Imports the frozen i2v bench frames (bench/i2v, 04 §6) and submits I2V recipes through `POST /jobs`:
  01   Wan 2.2 Draft (Lightning 2 + 2) · task 01 character turn · 832×480 × 81 f @ 16 fps
  03   Wan 2.2 Draft first/last-frame · task 03 rooftop crouch → stand (start + end)
  ltx  LTX-2.3 distilled · task 03 with the standing frame as a mid beat at 60 (strength 0.5) and as the end · 1024×576 × 121 f @ 24
For every clip: the job finishes, `clips/<id>/` holds the PNG master and a proxy that decodes to the requested frame
count at the requested fps, the Catalogue has a video asset with lineage to the start (and end) frame, three frames
extract with `frame-extract` lineage; time, engine node times and the lowest free VRAM seen are recorded; a frame sheet
(start / end stills + 6 frames) lands in engine/spikes/out/m6/ for scoring by eye (identity, motion, end-frame reach).

    LOOM2_TOKEN=devtoken python scripts/m6_acceptance.py --port 8766 [--tasks 01,03,ltx] [--project F:/loom2-projects/m6-acceptance]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

import av
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "bench" / "i2v"
OUT = REPO / "engine" / "spikes" / "out" / "m6"
RESULTS = OUT / "m6_results.jsonl"
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
SEED = 20261005


def call(base: str, method: str, path: str, body=None, raw: bool = False):
    data = None
    headers = {"X-Loom-Token": TOKEN}
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        payload = r.read()
        return payload if raw else (json.loads(payload) if payload else None)


class VramWatch(threading.Thread):
    """Polls /engine while a job runs; keeps the lowest free VRAM seen (the peak the clip needed)."""

    def __init__(self, base: str) -> None:
        super().__init__(daemon=True)
        self.base, self.min_free, self.stop = base, None, threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                e = call(self.base, "GET", "/engine")
                v = e.get("vram_free_gb")
                if isinstance(v, (int, float)) and (self.min_free is None or v < self.min_free):
                    self.min_free = v
            except Exception:
                pass
            self.stop.wait(2.0)


def wait_job(base: str, jid: str, timeout_s: float) -> dict:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout_s:
        j = call(base, "GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        msg = f"{j['progress_text']} {round((j['progress'] or 0) * 100)}%" if j["status"] == "running" else j["status"]
        if msg != last:
            print(f"      … {msg} ({round(time.time() - t0)} s)", flush=True); last = msg
        time.sleep(3)
    raise TimeoutError(f"job {jid} did not finish in {timeout_s} s")


def sheet(name: str, stills: list[tuple[str, Image.Image]], proxy: Path, frames: int, samples: int = 6) -> Path:
    wanted = sorted({int(round(i * (frames - 1) / (samples - 1))) for i in range(samples)})
    got: dict[int, Image.Image] = {}
    with av.open(str(proxy)) as c:
        for i, fr in enumerate(c.decode(video=0)):
            if i in wanted:
                got[i] = fr.to_image()
            if i >= wanted[-1]:
                break
    tiles = stills + [(f"frame {i}", got[i]) for i in wanted if i in got]
    tw = 400
    scaled = [(l, t.resize((tw, int(t.height * tw / t.width)), Image.LANCZOS)) for l, t in tiles]
    th = max(t.height for _, t in scaled)
    cols = min(4, len(scaled))
    rows = (len(scaled) + cols - 1) // cols
    img = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 30) + 6), (30, 30, 30))
    d = ImageDraw.Draw(img)
    for k, (label, t) in enumerate(scaled):
        x, y = 6 + (k % cols) * (tw + 6), 6 + (k // cols) * (th + 30)
        d.text((x + 4, y + 4), label, fill=(240, 240, 240))
        img.paste(t, (x, y + 24))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    img.save(p)
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--tasks", default="01,03,ltx")
    ap.add_argument("--project", default="F:/loom2-projects/m6-acceptance")
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        results.append((name, bool(ok), info))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + info) if info else ''}", flush=True)

    proj = call(base, "GET", "/project")
    if not proj.get("open") or not str(proj.get("path", "")).replace("\\", "/").lower().startswith(a.project.lower()):
        try:
            call(base, "POST", "/project/open", {"path": a.project})
        except Exception:
            call(base, "POST", "/project", {"path": a.project, "name": "M6 acceptance", "size_cap_gb": 50})
    call(base, "POST", "/queue/unpause")
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    tasks = {t["id"][:2]: t for t in spec["tasks"]}
    frames_dir = BENCH / "frames"
    caps = call(base, "GET", "/capabilities")["i2v"]["models"]
    for mid, m in caps.items():
        check(f"weights present for {mid}", m["health"] != "missing", f"{m['health']}" + (f" missing {m['missing']}" if m["missing"] else ""))

    def imported(name: str) -> dict:
        items = call(base, "POST", "/assets/import", {"paths": [str(frames_dir / name)]})["items"]
        return items[0]

    def run(label: str, recipe: dict, stills: list[tuple[str, Path]]) -> None:
        print(f"\n== {label}", flush=True)
        pv = call(base, "POST", "/recipes/preview", {"recipe": recipe})
        print(f"    preview: {pv['width']}×{pv['height']} · {pv['frames']} f @ {pv['fps']} · {pv['label']} · ETA {pv['estimate']['seconds']} s · missing {len(pv['missing'])}", flush=True)
        watch = VramWatch(base); watch.start()
        t0 = time.time()
        job = call(base, "POST", "/jobs", {"recipe": recipe})["jobs"][0]
        j = wait_job(base, job["id"], a.timeout)
        watch.stop.set()
        wall = round(time.time() - t0, 1)
        row: dict = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "recipe": recipe, "status": j["status"], "wall_s": j.get("wall_s"), "total_s": wall,
                     "node_s": j.get("node_times"), "min_vram_free_gb": watch.min_free, "error": j.get("error")}
        ok = j["status"] == "done"
        check(f"{label}: job done", ok, f"{j.get('wall_s')} s engine wall · {wall} s total · lowest free VRAM {watch.min_free} GB" + ("" if ok else f" · {j.get('error')}"))
        if ok:
            cid = j["result"]["clip_id"]
            clip = call(base, "GET", f"/clips/{cid}")
            row |= {"clip_id": cid, "frames": clip["frames"], "fps": clip["fps"], "w": clip["w"], "h": clip["h"], "proxy_bytes": clip["proxy_bytes"]}
            check(f"{label}: clip master + proxy", clip["frames"] == pv["frames"] and clip["w"] == pv["width"] and clip["h"] == pv["height"] and clip["proxy_path"],
                  f"{clip['frames']} f · {clip['w']}×{clip['h']} · proxy {clip['proxy_bytes'] / 2**20:.1f} MiB")
            proxy = OUT / f"{cid}.mp4"
            OUT.mkdir(parents=True, exist_ok=True)
            proxy.write_bytes(call(base, "GET", f"/clips/{cid}/proxy.mp4", raw=True))
            with av.open(str(proxy)) as c:
                s = c.streams.video[0]
                n = sum(1 for _ in c.decode(s))
                check(f"{label}: proxy decodes", n == clip["frames"] and float(s.average_rate) == clip["fps"] and s.codec_context.name == "h264", f"{n} frames @ {s.average_rate} {s.codec_context.name}")
            asset = call(base, "GET", f"/assets/{clip['asset_id']}")
            check(f"{label}: Catalogue video asset with lineage", asset["kind"] == "video" and asset["frames"] == clip["frames"] and recipe["start_asset"] in asset["parents"] and asset["thumb_status"] == "done",
                  f"{asset['id']} parents {asset['parents']}")
            picks = [0, clip["frames"] // 2, clip["frames"] - 1]
            ex = call(base, "POST", f"/clips/{cid}/extract", {"frames": picks})["items"]
            check(f"{label}: frames extracted with lineage", len(ex) == 3 and all(e["suite"] == "animate" and e["parents"] == [clip["asset_id"]] for e in ex), f"frames {picks}")
            lin = call(base, "GET", f"/lineage/{ex[0]['id']}") if ex else {}
            row["extract_lineage"] = lin
            p = sheet(label.replace(" ", "_").replace("/", "-"), [(k, Image.open(v).convert("RGB")) for k, v in stills], proxy, clip["frames"])
            print(f"      sheet → {p}", flush=True)
            row["sheet"] = str(p)
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    wanted = a.tasks.split(",")
    if "01" in wanted:
        t = tasks["01"]
        s = imported(Path(t["start"]).name)
        run("wan draft · 01 character turn", {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "start_asset": s["id"], "prompt_text": t["prompt"], "frames": 81, "fps": 16, "width": 832, "height": 480, "preset": "draft", "seeds": [SEED]},
            [("start", frames_dir / Path(t["start"]).name)])
    if "03" in wanted:
        t = tasks["03"]
        s = imported(Path(t["start"]).name); e = imported(Path(t["end"]).name)
        run("wan draft FLF · 03 crouch to stand", {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "start_asset": s["id"], "end_asset": e["id"], "prompt_text": t["prompt"], "frames": 81, "fps": 16, "width": 832, "height": 480, "preset": "draft", "seeds": [SEED]},
            [("start", frames_dir / Path(t["start"]).name), ("end", frames_dir / Path(t["end"]).name)])
    if "ltx" in wanted:
        t = tasks["03"]
        s = imported(Path(t["start"]).name); e = imported(Path(t["end"]).name)
        run("ltx draft · 03 with a beat at 60", {"kind": "i2v", "model_id": "ltx23-distilled-fp8", "start_asset": s["id"], "end_asset": e["id"], "prompt_text": t["prompt"], "frames": 121, "fps": 24, "width": 1024, "height": 576, "preset": "draft",
                                                 "beats": [{"frame": 60, "asset_id": e["id"], "strength": 0.5}], "seeds": [SEED]},
            [("start", frames_dir / Path(t["start"]).name), ("end / beat 60", frames_dir / Path(t["end"]).name)])

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nM6 acceptance: {passed}/{len(results)} checks passed · results in {RESULTS}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
