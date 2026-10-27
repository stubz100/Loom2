"""D118 (AE4d, from spike E29b's L3a): the lip-sync model as a tool — LatentSync 1.5 (ByteDance: the code Apache-2.0, the 1.5 weights
OpenRAIL++, so `full` only) in its own venv `tools/lipsync/.venv` (scripts/lipsync-setup.ps1, tools/lipsync/AGENTS.md), never the
engine's, run as the face pass's `mouth` step on the heads Wan Animate rendered: the head clip at 25 fps and the layer's lines over the
shot go in, the clip with the mouth redrawn comes out, back at the final's rate under the heads' own silhouettes, then the paste. The
engine is stopped for it (plan().gpu — one job on the card, D97), as for the trainer.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from .fsio import atomic_write_json, read_json, utc_now

if TYPE_CHECKING:
    from .config import Settings
    from .queue import JobQueue, JobRecord
    from .recipes import LayerPass

MODEL_FPS = 25                                      # LatentSync works at 25 fps (its training rate)
SECONDS_PER_77 = 104.0                              # E29b 2026-10-21: 77 head frames at 512² (120 at 25 fps), 20 steps, on this card


def lipsync_available(settings: "Settings") -> str | None:
    """None when the mouth step can run; else the sentence (the variant, the venv, the runner, the weights)."""
    if settings.variant == "open":
        return "the lip-sync model's weights (OpenRAIL++) are not offered under the open variant"
    s = settings.lipsync
    if not Path(s.python).is_file():
        return f"the lip-sync venv is missing ({s.python}) — run scripts/lipsync-setup.ps1"
    if not Path(s.run).is_file():
        return f"the lip-sync runner is missing ({s.run})"
    if not (Path(s.checkout) / "checkpoints" / "latentsync_unet.pt").is_file():
        return f"the LatentSync weights are missing under {s.checkout} — run scripts/lipsync-setup.ps1"
    return None


def run_dir(ws: Any, job_id: str) -> Path:
    return ws.temp_dir / "lipsync" / job_id


def nearest(n_src: int, src_fps: float, dst_fps: float) -> list[int]:
    """The source frame index for every frame at the destination rate (nearest; E29b's resampling between 16 and 25 fps)."""
    n_dst = int(round(n_src * dst_fps / src_fps))
    return [min(n_src - 1, int(round(i * src_fps / dst_fps))) for i in range(n_dst)]


def encode_rgb(frames: list[Path], out: Path, fps: int) -> None:
    """The head frames as one near-lossless h264 for the model (RGB; the silhouette stays with the PNGs)."""
    import av
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(frames[0]) as im:
        w, h = im.size
    w, h = w - w % 2, h - h % 2
    with av.open(str(out), "w", format="mp4", options={"movflags": "+faststart"}) as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
        stream.options = {"crf": "10", "preset": "veryfast", "g": "24"}
        for p in frames:
            with Image.open(p) as im:
                a = np.asarray(im.convert("RGB"))[:h, :w]
            for packet in stream.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(a), format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def decode_rgb(path: Path) -> list[np.ndarray]:
    import av
    with av.open(str(path)) as c:
        return [fr.to_ndarray(format="rgb24") for fr in c.decode(video=0)]


async def run_mouth(job: "JobRecord", recipe: "LayerPass", q: "JobQueue") -> bool:
    """The job (the engine already stopped by the queue): the kept heads stitched and resampled to 25 fps as one mp4, the layer's lines
    mixed over the shot, the runner run in the lip-sync venv with its log in a file, a cancel killing the process tree, an exit ≠ 0
    failing the job with its last lines; the output back at the final's rate under the heads' silhouettes, then the take finished as
    the face pass finishes it (the paste, the matte, the record). Returns True."""
    from .compositions import CompositionStore
    from .engine.finishers import finish_face_take
    from .engine.pipeline import JobCancelled
    from .engine.supervisor import _assign_to_job
    from .final_assembly import mix_audio
    from .finals import FinalStore, stitch
    from .trainer import _kill
    settings = q.app.settings
    why = lipsync_available(settings)
    if why:
        raise ValueError(why)
    step = recipe.step
    if step is None or step.stage != "mouth":
        raise ValueError("the mouth step runs inside the face pass's chain")
    store = FinalStore(q.ws)
    f = store.get(recipe.final_id)
    if f is None:
        raise ValueError(f"the final {recipe.final_id} is gone")
    layer = next((x for x in f.layers if x.id == recipe.layer_id), None)
    if layer is None:
        raise ValueError(f"the final has no layer {recipe.layer_id}")
    take_dir = store.pass_dir(f.id, layer.id, f"passes/{step.take_id}")
    work = take_dir / "work"
    try:
        plan = read_json(work / "plan.json")
        n, rate = f.frames, f.rate
        heads = stitch([sorted((work / "head" / str(k)).glob("*.png")) for k in range(len(plan["batches"]))], n)
        cs = CompositionStore(q.ws)
        c = cs.get(f)
        timing = [t for t in (cs.audio_timing(f, c) if c else []) if t.get("final_layer") == layer.id and t.get("path")]
        if not timing:
            raise ValueError(f"no line is attached to {layer.name} — the mouth follows the lines on the layer")
        rdir = run_dir(q.ws, job.id)
        shutil.rmtree(rdir, ignore_errors=True)
        rdir.mkdir(parents=True, exist_ok=True)
        q.progress(job, "mouth: the head clip at 25 fps and the lines")

        def prepare() -> tuple[Path, Path, int]:
            idx = nearest(n, rate, MODEL_FPS)
            src = [heads[i] for i in idx]
            encode_rgb(src, rdir / "head_25.mp4", MODEL_FPS)
            wav = mix_audio(timing, n / rate, rdir / "lines.wav")
            if wav is None:
                raise ValueError("the lines mixed to nothing")
            return rdir / "head_25.mp4", wav, len(src)
        video, wav, n25 = await asyncio.to_thread(prepare)
        request = {"checkout": settings.lipsync.checkout, "video": str(video), "audio": str(wav), "out": str(rdir / "out_25.mp4"), "steps": int(settings.lipsync.steps),
                   "guidance": float(settings.lipsync.guidance), "seed": int(job.seed or 1247), "temp_dir": str(rdir / "temp"), "result": str(rdir / "result.json")}
        atomic_write_json(rdir / "request.json", request)
        log_path = q.app.logs_dir / f"lipsync-{job.id}.log"
        env = {**os.environ, "HF_HOME": settings.hf_home, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
        q.check_cancel(job)
        t0 = time.time()
        with log_path.open("ab") as lf:
            lf.write(f"==== launch {utc_now()} job {job.id} {n25} frames at {MODEL_FPS} fps, {settings.lipsync.steps} steps\n".encode("utf-8"))
            lf.flush()
            start_pos = lf.tell()
            proc = subprocess.Popen([settings.lipsync.python, settings.lipsync.run, str(rdir / "request.json")], cwd=str(Path(settings.lipsync.run).parent), env=env,
                                    stdout=lf, stderr=subprocess.STDOUT)
            in_job = _assign_to_job(proc)                               # the orchestrator's job object: a kill takes the runner along
        job.log_tail.append(f"lip-sync model pid {proc.pid}" + (" in the job object" if in_job else ""))
        q.progress(job, "mouth: loading the model (the engine stopped)")
        pos = start_pos
        est = SECONDS_PER_77 * n25 / 120.0
        try:
            while True:
                done = proc.poll() is not None
                if not done:
                    await asyncio.sleep(1.0)
                    done = proc.poll() is not None
                try:
                    with log_path.open("rb") as rf:
                        rf.seek(pos)
                        chunk = rf.read()
                    pos += len(chunk)
                except OSError:
                    chunk = b""
                if chunk:
                    text = chunk.decode("utf-8", "replace")
                    if "syncing" in text:
                        q.progress(job, "mouth: the model runs")
                elapsed = time.time() - t0
                job.progress = min(0.95, elapsed / max(est, 30.0))
                if done:
                    break
                if job.id in q._cancel_requested:
                    _kill(proc.pid)
                    await asyncio.to_thread(proc.wait)
                    raise JobCancelled(job.id)
        finally:
            pass
        rc = proc.returncode
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:]
        except OSError:
            pass
        if rc != 0:
            last = [ln for ln in tail.splitlines() if ln.strip()][-4:]
            raise ValueError(f"the lip-sync model exited with {rc}: " + " | ".join(last))
        out = rdir / "out_25.mp4"
        if not out.is_file():
            raise ValueError("the lip-sync model wrote no video")
        q.progress(job, "mouth: the heads back at the final's rate")

        def back() -> list[Path]:
            frames25 = decode_rgb(out)
            if not frames25:
                raise ValueError("the lip-sync model's video has no frames")
            idx = nearest(len(frames25), MODEL_FPS, rate)
            d = work / "head_mouth"
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
            res = []
            for i in range(n):
                j = idx[min(i, len(idx) - 1)]
                with Image.open(heads[i]) as him:
                    him = him.convert("RGBA")
                    size = him.size
                    alpha = him.getchannel("A")
                rgb = Image.fromarray(frames25[j]).convert("RGB")
                if rgb.size != size:
                    rgb = rgb.resize(size, Image.LANCZOS)
                rgb.putalpha(alpha)
                p = d / f"{i:04d}.png"
                rgb.save(p)
                res.append(p)
            return res
        mouth_heads = await asyncio.to_thread(back)
        seconds = round(time.time() - t0, 1)
        reused = 0
        try:
            reused = int((read_json(rdir / "result.json") or {}).get("reused_face_frames") or 0)
        except (OSError, ValueError):
            pass
        job.log_tail.append(f"mouth by the model: {n25} frames at {MODEL_FPS} fps in {seconds} s → {n} heads"
                            + (f"; {reused} frame(s) without a detectable face took the last face's geometry" if reused else ""))
        lines = [{"layer": t.get("layer"), "text": t.get("text"), "f0": max(0, int(round(float(t["in"]) * rate))), "f1": min(n, int(round(float(t["out"]) * rate)))} for t in timing]
        await finish_face_take(job, recipe, q, store, f, layer, take_dir, work, plan, mouth_heads,
                               {"mouth": "model", "mouth_s": seconds, "mouth_steps": int(settings.lipsync.steps), "lines": lines})
        shutil.rmtree(rdir, ignore_errors=True)                                 # V37: the run folder goes with the take finished
        return True
    except Exception:
        shutil.rmtree(take_dir, ignore_errors=True)
        raise
