"""19 §5 (D87) acceptance of wave CN on the rig, through the app's API — the parts land with their slices. `voice` (CN2): a project with a
character (Mara) → a draft voice (Kokoro, the CPU) speaks a Flow line and then every line of the node → a cloning voice (Qwen3-TTS, the
GPU, the engine stopped) made from a draft line as its reference (the consent note says it is a synthetic voice) speaks an English and a
German line → the audio assets with their length and waveform thumbnails, the lines' stamps, the voice records' measured figures, against
E20's bars (a draft line ≤ 5 s on the CPU, a cloned line ≤ 15 s on the GPU, the clone's peak ≤ 4 GB). The Episode export's audio lane
is covered offline and in the smoke; CN5's chain gives it real clips on the rig.

`animate` (CN4): a stage with one camera, E11's walk_dolly pose sequence (77 frames, one figure) uploaded through the app's guide route
with its keypoints, the hero (bench/angles/07.jpg) as the character -> an `i2v` job on the Stage's animate method through the queue -> the
clip scored as E19 did (PCK@0.1 with SDPose against the mapped keypoints >= 0.8, FaceSim to the hero advisory, <= 300 s warm); the
reference padded; E11's run_track pass (two figures) refused with the sentence (422).

The voice part never touches the engine (its orchestrator points the engine at a free port). The animate part needs port 8188 free (the
orchestrator starts the engine). Needs the voices venv (scripts/voices-setup.ps1) and the TTS models in HF_HOME (fetched on first use); E11's
outputs under engine/spikes/out/e11 for the animate part. Results: engine/spikes/out/cn/results.jsonl, the WAVs under
engine/spikes/out/cn/voice/, the clip under engine/spikes/out/cn/animate/, the orchestrator log.

    orchestrator/.venv/Scripts/python.exe scripts/cn_acceptance.py --parts voice,animate,episode [--tier draft|cloning|both]

`extend` / `lipsync` (D88, experimental — measured, not gated): an LTX clip of the hero continued through the app, the seam ratio
and FaceSim at both ends (E17's metric); an English line voiced, Lip-sync at Fast (CN_LIPSYNC_PRESET) on a shot with the hero's frame,
the take, the line in the proxy, the sync proxy (E18's metric). Copies under engine/spikes/out/cn/extend/ and lipsync/.

`episode` (CN5): the animate part's clip as a shot bound to a Dialogue node with two lines voiced by a draft voice, on an Episode lane;
the FCPXML carries both lines on the audio lane (lane −1, their WAVs on disk), the EDL their AX events, the SRT the text; copies of the
three exports under engine/spikes/out/cn/episode/ for the author's Resolve import.
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


def animate_part(a, check, row: dict, tmp: Path) -> None:
    import hashlib
    import av
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from e10_stage import pck, sdpose_graph
    from e12_angles import Engine
    from loom2.tools.facesim import FaceSim
    caps = api("GET", "/capabilities")["stage"].get("animate")
    check(bool(caps) and caps["health"] != "missing", f"the Stage's animate method is offered with its weights ({caps and caps['model_id']}, {caps and caps['missing']})")
    if not caps:
        return
    e11 = ROOT / "engine" / "spikes" / "out" / "e11"
    hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
    st = api("POST", "/stages", {"name": "CN4 walk"})
    cam = st["cameras"][0]["id"]

    def upload_guide(shot: str, revision: int) -> tuple[dict, dict]:
        kp = json.loads((e11 / shot / "keypoints.json").read_text(encoding="utf-8"))
        n = min(int(caps["frames_max"] or 77), len(kp["frames"]))
        shas = []
        with av.open(str(e11 / shot / "pose.mp4")) as c:
            for i, fr in enumerate(c.decode(video=0)):
                if i >= n:
                    break
                buf = tmp / f"pose_{shot}_{i:03d}.png"
                fr.to_image().save(buf)
                data = buf.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/blobs/{sha}", data=data, method="PUT", headers={"X-Loom-Token": TOKEN})
                urllib.request.urlopen(req, timeout=60).read()
                shas.append(sha)
        w, h = kp["size"]
        doc = api("POST", f"/stages/{st['id']}/guide", {"camera_id": cam, "revision": revision, "kind": "pose", "fps": int(kp.get("fps") or 24), "size": {"w": w, "h": h},
                                                         "range": {"start": 0, "end": n - 1}, "frames": shas, "keypoints": kp["frames"][:n]})
        entry = next(x for x in doc["passes"] if x["camera_id"] == cam)
        return doc, {**entry["guides"]["pose"], "kp": kp, "n": n}

    doc, g2 = upload_guide("run_track", st["revision"])
    two = {"kind": "i2v", "model_id": caps["model_id"], "start_asset": hero, "prompt_text": "the runner sprints along the street", "frames": g2["n"], "fps": 24,
           "width": 848, "height": 480, "preset": "draft", "guide": {"asset_id": g2["asset_id"], "kind": "pose"}}
    try:
        api("POST", "/jobs", {"recipe": two})
        check(False, "a two-figure pose pass is refused")
    except urllib.error.HTTPError as ex:
        body = ex.read().decode("utf-8", "replace")
        check(ex.code == 422 and "figures" in body, f"a two-figure pose pass is refused (422: {body[:140]})")
    doc, g = upload_guide("walk_dolly", doc["revision"])
    recipe = {**two, "prompt_text": "the character walks towards the camera through a bright empty room, steady camera", "frames": g["n"],
              "guide": {"asset_id": g["asset_id"], "kind": "pose"}}
    t0 = time.time()
    job = api("POST", "/jobs", {"recipe": recipe, "origin": {"suite": "stage", "surface": "clip", "ref": st["id"], "payload": {"camera_id": cam}}})["jobs"][0]
    j = wait_job(job["id"], timeout_s=3600)
    check(j["status"] == "done", f"the Animate job: {j['status']} {j.get('error') or ''} ({time.time() - t0:.0f} s wall)")
    if j["status"] != "done":
        return
    check(any("reference padded into 848×480" in x for x in j.get("log_tail", [])), "the reference was padded into the clip (never cropped)")
    clip_id = j["result"]["clip_id"]
    asset = api("GET", f"/assets/{j['result']['asset_ids'][0]}")
    check(set(asset["parents"]) == {hero, g["asset_id"]} and asset["frames"] == g["n"], f"the clip: {asset['frames']} frames, lineage to the hero and the pose pass")
    frames = sorted((tmp / "proj" / "clips" / clip_id / "master").glob("*.png"))
    dest = OUT / "animate"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmp / "proj" / asset["path"], dest / "walk_dolly.mp4")
    eng = Engine("127.0.0.1:8188")                                                   # SDPose on the orchestrator's own engine (a plain prompt)
    kp = g["kp"]
    sw, sh = kp["size"]
    W, H = Image.open(frames[0]).size
    s = max(W / sw, H / sh)
    ox, oy = (sw * s - W) / 2, (sh * s - H) / 2
    hit = tot = 0
    for idx in range(0, len(frames), 10):
        hp, _, _ = eng.run(sdpose_graph(eng.upload(frames[idx])))
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        figs = [[[x * s - ox, y * s - oy, v] for x, y, v in fig] for fig in kp["frames"][idx]]
        h_, t_ = pck(figs, people)
        hit += h_
        tot += t_
    pck_v = round(hit / tot, 3) if tot else None
    fs = FaceSim(Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")))

    def emb(p):
        arr = np.asarray(Image.open(p).convert("RGB"))
        faces = fs.detect(arr)
        return fs.embed(arr, max(faces, key=lambda x: x.area).kps) if faces else None
    he = emb(HERO)
    sims = []
    for i in (0, len(frames) // 2, len(frames) - 1):
        x = emb(frames[i])
        sims.append(round(fs.similarity(he, x), 3) if he is not None and x is not None else None)
    check(pck_v is not None and pck_v >= 0.8, f"the clip follows the pose: PCK@0.1 {pck_v} (bar >= 0.8)")
    engine_s = float((j.get("timings") or {}).get("engine_wall_s") or 0) or None
    row["animate"] = {"clip_id": clip_id, "job": j["id"], "frames": len(frames), "pck": pck_v, "facesim": sims, "wall_s": j.get("wall_s"), "engine_s": engine_s, "size": [W, H],
                      "node_times": (j.get("node_times") or {})}
    log(f"animate: {len(frames)} f at {W}×{H}, PCK {pck_v}, FaceSim {sims} (advisory), wall {j.get('wall_s')} s")


def episode_part(a, check, row: dict, tmp: Path) -> None:
    """CN5: the Animate clip becomes a shot bound to a Dialogue node with two lines; the lines are voiced (draft); the Episode lane takes the
    shot; the FCPXML carries the voiced lines on the audio lane at the SRT's ticks and the EDL their AX events; the WAVs exist."""
    clip_id = (row.get("animate") or {}).get("clip_id")
    if not clip_id:
        check(False, "the episode part needs the animate part's clip (run --parts animate,episode)")
        return
    clip = next(c for c in api("GET", "/clips")["items"] if c["id"] == clip_id)
    sh = api("POST", "/story/shots", {"name": "Mara walks in", "clip_id": clip_id})
    n = api("POST", "/story/flow/nodes", {"type": "dialogue", "title": "Mara walks in", "x": 0, "y": 0})
    n = api("PATCH", f"/story/flow/nodes/{n['id']}", {"revision": n["revision"], "lines": [{"speaker": None, "text": "I came as soon as I heard."},
                                                                                            {"speaker": None, "text": "Tell me everything, slowly."}]})
    api("POST", f"/story/flow/nodes/{n['id']}/bind", {"shot_id": sh["id"]})
    voice = api("POST", "/story/voices", {"name": "Episode narrator", "tier": "draft", "voice": "bf_emma"})
    r = api("POST", f"/story/flow/nodes/{n['id']}/voice", {"voice_id": voice["id"]})
    j = wait_job(r["job_ids"][0])
    check(j["status"] == "done" and len(j["result"]["asset_ids"]) == 2, f"both lines voiced ({j['status']}, {j.get('error') or ''})")
    tl = api("POST", "/timelines", {"name": "CN episode", "fps": int(clip["fps"])})
    body = {**tl, "clips": [{"id": "c1", "clip_id": clip_id, "in": 0, "out": int(clip["frames"]), "fps": None, "shot_id": sh["id"], "shot_version": "v1",
                             "node_id": n["id"]}], "overlaps": [0]}
    api("PUT", f"/timelines/{tl['id']}", body)
    fx = api("POST", f"/timelines/{tl['id']}/export", {"format": "fcpxml"})
    edl = api("POST", f"/timelines/{tl['id']}/export", {"format": "edl"})
    srt = api("POST", f"/timelines/{tl['id']}/export", {"format": "srt"})
    import re
    srcs = re.findall(r'<asset id="au\d+"[^>]*><media-rep kind="original-media" src="file:///([^"]+)"', fx["text"])
    from urllib.parse import unquote
    files = [Path(unquote(s)) for s in srcs]
    check(fx["audio"] == 2 and fx["text"].count('lane="-1"') == 2 and len(files) == 2 and all(f.is_file() for f in files),
          f"the FCPXML: {fx['audio']} voiced lines on lane −1, their WAVs on disk ({[f.name for f in files]})")
    check('value="Mara walks in"' in fx["text"], "the FCPXML's chapter marker names the node")
    check(edl["audio"] == 2 and edl["text"].count("AX       A     C") == 2, "the EDL carries the two lines as AX audio events")
    check(srt["text"].count("-->") == 2 and "slowly" in srt["text"], "the SRT carries the two lines")
    dest = OUT / "episode"
    dest.mkdir(parents=True, exist_ok=True)
    for fmt, x in (("fcpxml", fx), ("edl", edl), ("srt", srt)):
        (dest / f"cn_episode.{fmt}").write_text(x["text"], encoding="utf-8")
    row["episode"] = {"timeline": tl["id"], "audio": fx["audio"], "files": [str(f) for f in files], "export": str(tmp / "proj" / fx["path"])}
    log(f"episode: {fx['path']} with {fx['audio']} voiced lines; copies in {dest} (the author's Resolve import check)")


def extend_part(a, check, row: dict, tmp: Path) -> None:
    """D88 XE (experimental): an LTX clip of the hero, then Extend through the app; the join scored as E17 did (the seam ratio: the first
    new frame after the lead-in against the clip's own inter-frame difference) and FaceSim to the hero at both ends (advisory)."""
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from loom2.tools.facesim import FaceSim
    ex = api("GET", "/capabilities")["experimental"]["extend"]
    ltx = next((m for m, lead in ex["models"].items() if lead > 1), None)
    check(ltx is not None, f"an LTX model continues clips ({ex['models']})")
    if not ltx:
        return
    hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
    base = {"kind": "i2v", "model_id": ltx, "start_asset": hero, "prompt_text": "the character walks slowly towards the camera, steady camera, soft light",
            "frames": 121, "fps": 24, "width": 1024, "height": 576, "preset": "draft"}
    j1 = wait_job(api("POST", "/jobs", {"recipe": base})["jobs"][0]["id"], timeout_s=1800)
    check(j1["status"] == "done", f"the first clip: {j1['status']} {j1.get('error') or ''}")
    if j1["status"] != "done":
        return
    c1 = j1["result"]["clip_id"]
    t0 = time.time()
    x = api("POST", f"/clips/{c1}/extend", {"prompt_text": "the character keeps walking towards the camera and stops, steady camera, soft light"})
    j2 = wait_job(x["job_id"], timeout_s=1800)
    check(j2["status"] == "done", f"the extension: {j2['status']} {j2.get('error') or ''} ({time.time() - t0:.0f} s wall)")
    if j2["status"] != "done":
        return
    c2 = j2["result"]["clip_id"]
    rec = next(c for c in api("GET", "/clips")["items"] if c["id"] == c2)
    check(rec["chained_from"] == c1 and rec["overlap"] == x["lead"] == 9, f"the continuation records its parent and overlap ({rec['chained_from']}, {rec['overlap']})")
    f1 = sorted((tmp / "proj" / "clips" / c1 / "master").glob("*.png"))
    f2 = sorted((tmp / "proj" / "clips" / c2 / "master").glob("*.png"))
    size = (256, 144)
    g = lambda p: np.asarray(Image.open(p).convert("L").resize(size, Image.BILINEAR), dtype=np.float32)  # noqa: E731
    within = float(np.median([np.mean(np.abs(g(f1[i]) - g(f1[i + 1]))) for i in range(len(f1) - 1)]))
    lead = rec["overlap"]
    seam = float(np.mean(np.abs(g(f2[lead - 1]) - g(f2[lead]))))
    pinned = float(np.mean(np.abs(g(f1[-1]) - g(f2[lead - 1]))))
    ratio = round(seam / max(1e-6, within), 2)
    fs = FaceSim(Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")))

    def emb(p):
        arr = np.asarray(Image.open(p).convert("RGB"))
        faces = fs.detect(arr)
        return fs.embed(arr, max(faces, key=lambda z: z.area).kps) if faces else None
    he = emb(HERO)
    ends = []
    for p in (f1[0], f2[-1]):
        e = emb(p)
        ends.append(round(fs.similarity(he, e), 3) if he is not None and e is not None else None)
    log(f"extend: seam {seam:.2f} vs within {within:.2f} -> ratio {ratio} (E17 bar <= 1.5), pinned diff {pinned:.2f}; FaceSim start / end {ends} (advisory)")
    row["extend"] = {"clip": c1, "continuation": c2, "seam_ratio": ratio, "pinned_diff": round(pinned, 2), "facesim_ends": ends, "wall_s": j2.get("wall_s")}
    dest = OUT / "extend"
    dest.mkdir(parents=True, exist_ok=True)
    for cid, name in ((c1, "segment1.mp4"), (c2, "segment2.mp4")):
        shutil.copy2(tmp / "proj" / "clips" / cid / "proxy.mp4", dest / name)


def lipsync_part(a, check, row: dict, tmp: Path) -> None:
    """D88 XL (experimental): an English line voiced (draft tier), a shot with the hero as its frame, Lip-sync through the app at Fast; the
    clip scored as E18 did (the mouth crop's motion against the line's RMS envelope, best lag ±3) and FaceSim to the hero (advisory)."""
    import numpy as np
    import soundfile as sf
    from PIL import Image
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from loom2.tools.facesim import FaceSim
    from e18_lipsync import mouth_energy, rms_envelope, sync_score
    lip = api("GET", "/capabilities")["experimental"]["lipsync"]
    check(lip["available"], f"the lip-sync model is available ({lip.get('why')})")
    if not lip["available"]:
        return
    hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
    voice = api("POST", "/story/voices", {"name": "Lip narrator", "tier": "draft", "voice": "af_heart"})
    n = api("POST", "/story/flow/nodes", {"type": "dialogue", "title": "Mara speaks", "x": 0, "y": 600})
    n = api("PATCH", f"/story/flow/nodes/{n['id']}", {"revision": n["revision"], "lines": [{"speaker": None, "text": "I came as soon as I heard. Tell me everything."}]})
    tj = wait_job(api("POST", f"/story/flow/nodes/{n['id']}/lines/0/voice", {"voice_id": voice["id"]})["job_ids"][0])
    check(tj["status"] == "done", "the line voiced")
    sh = api("POST", "/story/shots", {"name": "Mara speaks", "frame_asset_id": hero})
    api("POST", f"/story/flow/nodes/{n['id']}/bind", {"shot_id": sh["id"]})
    preset = os.environ.get("CN_LIPSYNC_PRESET", "fast")
    q = api("POST", f"/story/shots/{sh['id']}/versions/v1/lipsync", {"node_id": n["id"], "index": 0, "preset": preset, "stage": True})
    check(q["staged"], f"the lip-sync job is staged ({q['frames']} frames, ≈ {q['seconds']} s at {preset})")
    api("POST", f"/jobs/{q['job_id']}/release")
    t0 = time.time()
    j = wait_job(q["job_id"], timeout_s=3600)
    check(j["status"] == "done", f"the lip-sync job: {j['status']} {j.get('error') or ''} ({time.time() - t0:.0f} s wall)")
    if j["status"] != "done":
        return
    cid = j["result"]["clip_id"]
    shot = api("GET", f"/story/shots/{sh['id']}")
    check(any(tk["kind"] == "clip" and tk["id"] == cid for tk in shot["versions"][0]["takes"]), "the talking clip is a take on the version")
    import av
    proxy = tmp / "proj" / "clips" / cid / "proxy.mp4"
    with av.open(str(proxy)) as c:
        check(len(c.streams.audio) == 1, "the proxy carries the line")
    frames = sorted((tmp / "proj" / "clips" / cid / "master").glob("*.png"))
    line = api("GET", f"/assets/{q['audio_asset_id']}")
    audio, sr = sf.read(str(tmp / "proj" / line["path"]), dtype="float32", always_2d=True)
    fs = FaceSim(Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")))
    motion, ok = mouth_energy(fs, frames)
    env = rms_envelope(audio.mean(axis=1), sr, 16, len(frames))
    r, lag = sync_score(motion, env) if ok else (None, None)

    def emb(p):
        arr = np.asarray(Image.open(p).convert("RGB"))
        faces = fs.detect(arr)
        return fs.embed(arr, max(faces, key=lambda z: z.area).kps) if faces else None
    he = emb(HERO)
    sims = []
    for i in (0, len(frames) // 2, len(frames) - 1):
        e = emb(frames[i])
        sims.append(round(fs.similarity(he, e), 3) if he is not None and e is not None else None)
    log(f"lipsync: {len(frames)} f, sync r {r} (lag {lag}; E18 bar >= 0.5), FaceSim {sims}, wall {j.get('wall_s')} s at {preset}")
    row["lipsync"] = {"clip": cid, "frames": len(frames), "sync_r": r, "lag": lag, "facesim": sims, "wall_s": j.get("wall_s"), "preset": preset, "line_s": line.get("duration_s")}
    dest = OUT / "lipsync"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(proxy, dest / f"mara_{preset}.mp4")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="voice")
    ap.add_argument("--tier", default="both", choices=["draft", "cloning", "both"])
    ap.add_argument("--vram-headroom", type=float, default=None, help="force --vram-headroom for every model through Settings.engine.flags (D98 / D100; 0 = none) — an A/B of the engine's headroom")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-cn-"))
    from loom2.config import AppState, EngineSettings
    engine_port = 8188 if any(x in a.parts for x in ("animate", "extend", "lipsync")) else ENGINE_PORT   # the voice part never starts the engine
    if engine_port == 8188:
        try:
            urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
            print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)")
            return 2
        except Exception:
            pass
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": engine_port, **({"flags": [*EngineSettings().flags, "--vram-headroom", f"{a.vram_headroom:g}"]} if a.vram_headroom is not None else {})}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    argv = [sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")]
    orch = subprocess.Popen(argv, cwd=str(ROOT / "orchestrator"), env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    log(f"orchestrator on {PORT}, state {tmp} (engine port {engine_port})")
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
        if "animate" in a.parts:
            animate_part(a, check, row, tmp)
        if "episode" in a.parts:
            episode_part(a, check, row, tmp)
        if "extend" in a.parts:
            extend_part(a, check, row, tmp)
        if "lipsync" in a.parts:
            lipsync_part(a, check, row, tmp)
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
