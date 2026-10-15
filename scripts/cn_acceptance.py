"""19 §5 (D87) acceptance of wave CN on the rig, through the app's API — the parts land with their slices. `voice` (CN2): a project with a
character (Mara) → a draft voice (Kokoro, the CPU) speaks a Flow line and then every line of the node → a cloning voice (Qwen3-TTS, the
GPU, the engine stopped) made from a draft line as its reference (the consent note says it is a synthetic voice) speaks an English and a
German line → the audio assets with their length and waveform thumbnails, the lines' stamps, the voice records' measured figures, against
E20's bars (a draft line ≤ 5 s on the CPU, a cloned line ≤ 15 s on the GPU, the clone's peak ≤ 4 GB). The Episode export's audio lane
is covered offline and in the smoke; CN5's chain gives it real clips on the rig.

Never touches the engine: the orchestrator it starts points its engine at a free port and queues no engine job, so a spike's engine on
8188 is left alone. Needs the voices venv (scripts/voices-setup.ps1) and the TTS models in HF_HOME (fetched on first use).
Results: engine/spikes/out/cn/results.jsonl, the WAVs under engine/spikes/out/cn/voice/, the orchestrator log.

    orchestrator/.venv/Scripts/python.exe scripts/cn_acceptance.py --parts voice [--tier draft|cloning|both]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

PORT, TOKEN, ENGINE_PORT = 8777, "cn", 8199
OUT = ROOT / "engine" / "spikes" / "out" / "cn"
HERO = ROOT / "bench" / "angles" / "07.jpg"
STUB = "Mara, a wiry courier in a long grey coat with a red scarf"
LINES = {"en_long": "Hi there, come in and sit by the fire while I fetch the kettle; the roads were wet tonight.",
         "en_short": "Thank you, that is kind of you.", "de": "Guten Abend. Kommen Sie herein, der Tee ist gleich fertig."}
BARS = {"draft_s": 5.0, "cloning_s": 15.0, "clone_vram_gb": 4.0}


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def status_of(method: str, path: str, body=None) -> int:
    try:
        api(method, path, body, raw=True)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def wait_job(job_id: str, timeout_s: float = 1800) -> dict:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout_s:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == job_id), None)
        if j is None:
            raise RuntimeError(f"job {job_id} vanished")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        if j.get("progress_text") and j["progress_text"] != last:
            last = j["progress_text"]
            log(f"  {job_id}: {last}")
        time.sleep(1.0)
    raise TimeoutError(job_id)


def voice_part(a, check, row: dict, tmp: Path) -> None:
    caps = api("GET", "/capabilities")["voice"]
    check(caps["available"], f"the voice tools are available ({caps['why']})")
    log(f"draft {caps['draft']['model']} cached={caps['draft']['cached']} · cloning {caps['cloning']['model']} cached={caps['cloning']['cached']}")
    hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
    p = api("POST", "/story/profiles", {"name": "Mara", "cls": "character", "hero_asset_id": hero, "stub": STUB})
    narrator = api("POST", "/story/voices", {"name": "Narrator", "tier": "draft", "voice": "af_heart"})
    check(narrator["tier"] == "draft" and narrator["voice"] == "af_heart", "a draft voice record (Kokoro af_heart)")
    api("PATCH", f"/story/profiles/{p['id']}", {"revision": p["revision"], "voice_id": narrator["id"]})
    n = api("POST", "/story/flow/nodes", {"type": "dialogue", "title": "At the door", "x": 0, "y": 0})
    n = api("PATCH", f"/story/flow/nodes/{n['id']}", {"revision": n["revision"], "lines": [{"speaker": p["id"], "text": LINES["en_long"]}, {"speaker": None, "text": LINES["en_short"]}, {"speaker": p["id"], "text": LINES["de"]}]})
    check(status_of("POST", f"/story/flow/nodes/{n['id']}/voice", {}) == 422, "Voice all lines refused while a speakerless line has no fallback voice (422)")
    wavs = OUT / "voice"
    wavs.mkdir(parents=True, exist_ok=True)
    lines = lambda: next(x for x in api("GET", "/story/flow")["nodes"] if x["id"] == n["id"])["lines"]  # noqa: E731

    def land(j: dict, label: str, bar: float) -> dict:
        check(j["status"] == "done", f"{label}: {j['status']} {j.get('error') or ''}")
        out = []
        for it in (j.get("result") or {}).get("items", []):
            a_ = api("GET", f"/assets/{it['asset_id']}")
            thumb = status_of("GET", f"/thumbs/{a_['id']}/256")
            secs = float(it["seconds"] or 0)
            check(a_["kind"] == "audio" and a_["duration_s"] and a_["duration_s"] > 0.5 and a_["thumb_status"] == "done" and thumb == 200,
                  f"{label} line {it['index']}: an audio asset of {a_['duration_s']} s with a waveform thumbnail")
            check(secs <= bar, f"{label} line {it['index']}: spoken in {secs} s (bar ≤ {bar} s; load {j['result'].get('load_s')} s apart)")
            dest = wavs / f"{label}_line{it['index']}.wav"
            shutil.copy2(tmp / "proj" / a_["path"], dest)
            out.append({"index": it["index"], "duration_s": a_["duration_s"], "seconds": secs, "wav": str(dest)})
        return {"job": j["id"], "load_s": (j.get("result") or {}).get("load_s"), "peak_vram_gb": (j.get("result") or {}).get("peak_vram_gb"), "wall_s": j.get("wall_s"), "lines": out}

    if a.tier in ("draft", "both"):
        t0 = time.time()
        r = api("POST", f"/story/flow/nodes/{n['id']}/lines/0/voice", {})
        j = wait_job(r["job_ids"][0])
        row["draft_line"] = land(j, "draft", BARS["draft_s"])
        ln = lines()[0]
        check(ln["audio_asset_id"] == j["result"]["asset_ids"][0] and ln["audio_text"] == LINES["en_long"], "the line carries its audio and the text it spoke")
        log(f"draft line 0 in {time.time() - t0:.1f} s wall")
        # every line of the node: Mara's lines by her voice, the speakerless one by the fallback (the same draft voice here) — one job
        r = api("POST", f"/story/flow/nodes/{n['id']}/voice", {"voice_id": narrator["id"]})
        check(r["lines"] == 3 and len(r["job_ids"]) == 1, f"Voice all lines: {r['lines']} lines in {len(r['job_ids'])} job (one voice)")
        j = wait_job(r["job_ids"][0])
        row["draft_all"] = land(j, "draft_all", BARS["draft_s"])
        check(all(x["audio_asset_id"] for x in lines()), "every line carries its audio after Voice all lines")
        vrec = api("GET", f"/story/voices/{narrator['id']}")
        check(vrec["measured"].get("rtf") is not None and vrec["measured"].get("lines") == 3, f"the voice record measured: {vrec['measured']}")
        row["draft_measured"] = vrec["measured"]
    if a.tier in ("cloning", "both"):
        # the reference: a draft line of 3–10 s (made here when the draft part did not run)
        ref_id = lines()[0].get("audio_asset_id")
        if not ref_id:
            j = wait_job(api("POST", f"/story/flow/nodes/{n['id']}/lines/0/voice", {})["job_ids"][0])
            ref_id = j["result"]["asset_ids"][0]
        ref = api("GET", f"/assets/{ref_id}")
        check(3.0 <= (ref["duration_s"] or 0) <= 10.5, f"the reference clip is {ref['duration_s']} s (3–10 s)")
        bad = status_of("POST", "/story/voices", {"name": "Mara (clone)", "tier": "cloning", "reference_asset_id": ref_id, "reference_text": LINES["en_long"], "language": "German"})
        check(bad == 422, "a cloning voice without the consent note is refused (422)")
        clone = api("POST", "/story/voices", {"name": "Mara (clone)", "tier": "cloning", "reference_asset_id": ref_id, "reference_text": LINES["en_long"], "language": "German",
                                              "speaker": "Narrator (Kokoro af_heart)", "consent": "a synthetic Kokoro line as the reference — no person's voice"})
        p2 = api("GET", f"/story/profiles/{p['id']}")
        api("PATCH", f"/story/profiles/{p['id']}", {"revision": p2["revision"], "voice_id": clone["id"]})
        t0 = time.time()
        r = api("POST", f"/story/flow/nodes/{n['id']}/voice", {"voice_id": narrator["id"]})                      # Mara's two lines by the clone (DE), the speakerless one by the draft
        check(len(r["job_ids"]) == 2 and set(r["voice_ids"]) == {clone["id"], narrator["id"]}, f"Voice all lines: {r['lines']} lines in {len(r['job_ids'])} jobs (two voices)")
        jobs = {jid: wait_job(jid) for jid in r["job_ids"]}
        jc = next(j for j in jobs.values() if j["recipe"]["voice_id"] == clone["id"])
        row["cloning"] = land(jc, "cloning", BARS["cloning_s"])
        peak = (jc.get("result") or {}).get("peak_vram_gb")
        check(peak is not None and peak <= BARS["clone_vram_gb"], f"the clone's peak VRAM {peak} GB (bar ≤ {BARS['clone_vram_gb']} GB)")
        check(jc["recipe"]["tier"] == "cloning" and jc["recipe"]["language"] == "German", "the clone job spoke German on the cloning tier")
        a0 = api("GET", f"/assets/{jc['result']['asset_ids'][0]}")
        check(a0["parents"] == [ref_id] and a0["lineage_kind"] == "voice-clone", "the cloned line's lineage leads to the reference clip")
        log(f"cloning lines in {time.time() - t0:.1f} s wall (the load {row['cloning']['load_s']} s included)")
        vrec = api("GET", f"/story/voices/{clone['id']}")
        row["cloning_measured"] = vrec["measured"]
        assert status_of("DELETE", f"/story/voices/{clone['id']}") == 200
        check(api("GET", f"/story/profiles/{p['id']}")["voice_id"] is None, "Delete: the character lost the deleted voice")
    audio = api("GET", "/assets?kind=audio&limit=50")["items"]
    row["audio_assets"] = len(audio)
    check(len(audio) >= 1, f"{len(audio)} audio assets in the Catalogue")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="voice")
    ap.add_argument("--tier", default="both", choices=["draft", "cloning", "both"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-cn-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": ENGINE_PORT}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    argv = [sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")]
    orch = subprocess.Popen(argv, cwd=str(ROOT / "orchestrator"), env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    log(f"orchestrator on {PORT}, state {tmp} (engine port {ENGINE_PORT}: never started)")
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "parts": a.parts, "tier": a.tier}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CN", "size_cap_gb": 60})
        if "voice" in a.parts:
            voice_part(a, check, row, tmp)
    except Exception as e:  # noqa: BLE001
        check(False, f"exception: {type(e).__name__}: {e}")
    finally:
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=30)
        except Exception:
            orch.kill()
        orch_log.close()
    row["failures"] = failures
    (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(row) + "\n")
    print(json.dumps(row, indent=1))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
