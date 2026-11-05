"""D193 rig acceptance: the H3 (hero) card through the product path, against a running dev orchestrator with the real engine (Settings'
H3 confirmation on in that orchestrator's state).

Imports bench 03's frames (rooftop: crouch → stand, bench/i2v) and submits I2V recipes through `POST /jobs`, one GPU job at a time:
  flf    H3 Draft, first + last frame · 864×480 × 124 f @ 24 (the card's default) — E64's task through the app
  start  H3 Draft, the start frame alone · the same size (the FL2VA transformer without a last frame: untested before D193)
  hd     (optional, --tasks) H3 at the HD tier · 1024×576
Checks: `/capabilities` lists H3 with its rules (sound, no negative, Draft only, 17n + 5 at a fixed 24 fps, the pixel cap); the preview runs
at what the card says and refuses 1344×768; every job finishes; `clips/<id>/` holds the PNG master, `sound.flac` and a proxy with its
video (the frames at 24) and its sound (AAC, 32 kHz stereo); the Bin's video asset has lineage to the start (and end) frame; the time, the
engine's node times and the lowest free VRAM seen are recorded; a frame sheet per clip lands in engine/spikes/out/h3/ for the look.

    LOOM2_TOKEN=devtoken orchestrator/.venv/Scripts/python.exe scripts/h3_acceptance.py --port 8766 [--tasks flf,start] [--project F:/loom2-projects/h3-acceptance]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path

import av
import numpy as np
import soundfile as sf
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_acceptance import VramWatch, call, sheet, wait_job  # noqa: E402
import m6_acceptance  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "bench" / "i2v"
OUT = REPO / "engine" / "spikes" / "out" / "h3"
RESULTS = OUT / "h3_results.jsonl"
SEED = 64                                                    # E64's first seed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--tasks", default="flf,start")
    ap.add_argument("--project", default="F:/loom2-projects/h3-acceptance")
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    m6_acceptance.OUT = OUT                                  # the sheets beside this run's results
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        results.append((name, bool(ok), info))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + info) if info else ''}", flush=True)

    proj = call(base, "GET", "/project")
    if not proj.get("open") or not str(proj.get("path", "")).replace("\\", "/").lower().startswith(a.project.lower()):
        try:
            call(base, "POST", "/project/open", {"path": a.project})
        except Exception:
            call(base, "POST", "/project", {"path": a.project, "name": "H3 acceptance", "size_cap_gb": 50})
    call(base, "POST", "/queue/unpause")
    caps = call(base, "GET", "/capabilities")["i2v"]["models"]
    h3 = next((mid for mid, m in caps.items() if m.get("sound") and m.get("family") == "minimax_h3"), None)
    check("the H3 card is offered (Settings' confirmation on)", h3 is not None, ", ".join(caps))
    if h3 is None:
        return 1
    m = caps[h3]
    check("H3's weights are present", m["health"] != "missing", m["health"] + (f" missing {m['missing']}" if m["missing"] else ""))
    g = m["geometry"]
    check("H3's rules", m["sound"] and m["takes_negative"] is False and list(m["presets"]) == ["draft"] and g["frame_step"] == 17 and g["frame_base"] == 5
          and g["fps_fixed"] and g["max_px"] == 1024 * 576 and g["tiers"]["draft"] == [864, 480] and g["tiers"]["hd"] == [1024, 576],
          f"{m['label']} · {m['frames']} f @ {m['fps']} · {list(m['presets'])}")
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    task = next(t for t in spec["tasks"] if t["id"].startswith("03"))
    frames_dir = BENCH / "frames"

    def imported(name: str) -> dict:
        return call(base, "POST", "/assets/import", {"paths": [str(frames_dir / name)]})["items"][0]

    s = imported(Path(task["start"]).name)
    e = imported(Path(task["end"]).name)
    big = {"kind": "i2v", "model_id": h3, "start_asset": s["id"], "frames": 124, "fps": 24, "width": 1344, "height": 768, "preset": "draft"}
    try:
        call(base, "POST", "/recipes/preview", {"recipe": big})
        check("1344×768 refused", False, "the preview accepted it")
    except urllib.error.HTTPError as err:
        check("1344×768 refused", err.code == 422, f"{err.code} {err.read().decode()[:160]}")

    def run(label: str, recipe: dict, stills: list[tuple[str, Path]]) -> None:
        print(f"\n== {label}", flush=True)
        pv = call(base, "POST", "/recipes/preview", {"recipe": recipe})
        print(f"    preview: {pv['width']}×{pv['height']} · {pv['frames']} f @ {pv['fps']} · {pv['label']} · ETA {pv['estimate']['seconds']} s · missing {len(pv['missing'])}", flush=True)
        check(f"{label}: the preview runs what the card says", pv["fps"] == 24 and pv["frames"] == 124 and (pv["width"], pv["height"]) == (recipe["width"], recipe["height"]),
              f"{pv['label']}, ETA {pv['estimate']['seconds']} s ({pv['estimate']['source']})")
        watch = VramWatch(base); watch.start()
        t0 = time.time()
        job = call(base, "POST", "/jobs", {"recipe": recipe})["jobs"][0]
        j = wait_job(base, job["id"], a.timeout)
        watch.stop.set()
        wall = round(time.time() - t0, 1)
        row: dict = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "recipe": recipe, "status": j["status"], "wall_s": j.get("wall_s"), "total_s": wall,
                     "eta_s": pv["estimate"]["seconds"], "node_s": j.get("node_times"), "min_vram_free_gb": watch.min_free, "error": j.get("error")}
        ok = j["status"] == "done"
        check(f"{label}: job done", ok, f"{j.get('wall_s')} s engine wall · {wall} s total · lowest free VRAM {watch.min_free} GB" + ("" if ok else f" · {j.get('error')}"))
        if ok:
            cid = j["result"]["clip_id"]
            clip = call(base, "GET", f"/clips/{cid}")
            row |= {"clip_id": cid, "frames": clip["frames"], "fps": clip["fps"], "w": clip["w"], "h": clip["h"], "proxy_bytes": clip["proxy_bytes"], "sound_path": clip.get("sound_path")}
            check(f"{label}: clip master + proxy", clip["frames"] == pv["frames"] and clip["fps"] == 24 and clip["w"] == pv["width"] and clip["h"] == pv["height"] and clip["proxy_path"],
                  f"{clip['frames']} f @ {clip['fps']} · {clip['w']}×{clip['h']} · proxy {clip['proxy_bytes'] / 2**20:.1f} MiB")
            snd = Path(a.project) / (clip.get("sound_path") or "missing")
            if snd.is_file():
                data, sr = sf.read(str(snd), always_2d=True)
                rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
                row |= {"sound_s": round(len(data) / sr, 3), "sound_sr": sr, "sound_ch": data.shape[1], "sound_rms_dbfs": round(20 * np.log10(max(rms, 1e-9)), 1)}
                check(f"{label}: sound.flac kept with the clip", abs(len(data) / sr - clip["frames"] / 24) < 0.1 and data.shape[1] == 2,
                      f"{len(data) / sr:.2f} s · {sr} Hz · {data.shape[1]} ch · {row['sound_rms_dbfs']} dBFS RMS")
            else:
                check(f"{label}: sound.flac kept with the clip", False, str(snd))
            OUT.mkdir(parents=True, exist_ok=True)
            proxy = OUT / f"{cid}.mp4"
            proxy.write_bytes(call(base, "GET", f"/clips/{cid}/proxy.mp4", raw=True))
            with av.open(str(proxy)) as c:
                v = c.streams.video[0]
                rate = float(v.average_rate)
                n = sum(1 for _ in c.decode(v))
            with av.open(str(proxy)) as c:
                au = c.streams.audio[0] if c.streams.audio else None
                ach = au.codec_context.layout.nb_channels if au else 0
                info = f"{n} frames @ {rate:g}" + (f" · {au.codec_context.name} {au.codec_context.sample_rate} Hz {ach} ch" if au else " · no sound")
            check(f"{label}: the proxy carries the frames and the sound", n == clip["frames"] and rate == 24 and ach == 2, info)
            asset = call(base, "GET", f"/assets/{clip['asset_id']}")
            want = {recipe["start_asset"]} | ({recipe["end_asset"]} if recipe.get("end_asset") else set())
            check(f"{label}: the Bin's video asset with lineage", asset["kind"] == "video" and want <= set(asset["parents"]) and asset["thumb_status"] == "done", f"{asset['id']} parents {asset['parents']}")
            p = sheet(label.replace(" ", "_").replace("/", "-").replace("·", "-"), [(k, Image.open(v).convert("RGB")) for k, v in stills], proxy, clip["frames"])
            print(f"      sheet → {p}", flush=True)
            row["sheet"] = str(p)
        OUT.mkdir(parents=True, exist_ok=True)
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stills_se = [("start", frames_dir / Path(task["start"]).name), ("end", frames_dir / Path(task["end"]).name)]
    common = {"kind": "i2v", "model_id": h3, "prompt_text": task["prompt"], "frames": 124, "fps": 24, "preset": "draft", "seeds": [SEED]}
    wanted = a.tasks.split(",")
    if "flf" in wanted:
        run("h3 draft FLF · 03 crouch to stand", {**common, "start_asset": s["id"], "end_asset": e["id"], "width": 864, "height": 480}, stills_se)
    if "start" in wanted:
        run("h3 draft start only · 03", {**common, "start_asset": s["id"], "width": 864, "height": 480}, stills_se[:1])
    if "hd" in wanted:
        run("h3 hd FLF · 03", {**common, "start_asset": s["id"], "end_asset": e["id"], "width": 1024, "height": 576}, stills_se)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nH3 acceptance (D193): {passed}/{len(results)} checks passed · results in {RESULTS}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
