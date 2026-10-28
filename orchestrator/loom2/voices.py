"""CN2 (19 §3b, D87): voices — the `voice` records (`story/voices/<id>.json`: the tier, the fixed Kokoro voice or the reference clip with
its transcript, the language, whose voice it is and that they consented) and the `tts` job: the runner `voices/tts.py` in its own venv
`voices/.venv` (scripts/voices-setup.ps1, voices/AGENTS.md) — the draft tier (Kokoro) on the CPU beside a running engine, the cloning tier
(Qwen3-TTS) on the GPU with the engine stopped, as training is (`plan().gpu`); every spoken line an `audio` asset placed on its Flow line.
E20 (`engine/spikes/e20_voice.py`, journal 2026-10-14) and CN2's rig run (2026-10-15) are the record of the figures: Kokoro on one CPU
thread ≈ 0.35 s per second of speech, Qwen3-TTS-0.6B ≈ 1 s per second of speech at a 2.6 GB peak, the loads 5 s and 11 s.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, plain_name, read_json, utc_now
from .recipes import TTS

if TYPE_CHECKING:
    from .config import Settings
    from .queue import JobQueue, JobRecord

VOICE_SCHEMA_VERSION = 1
Tier = Literal["draft", "cloning"]
# Kokoro's fixed voices (`voices/<id>.pt` in the hub repo, fetched into HF_HOME on first use — 0.5 MB each); the first letter is the
# pipeline's language code (a: American, b: British English). Kokoro has no German — a DE line is the cloning tier's.
DRAFT_VOICES: list[dict[str, str]] = [
    {"id": "af_heart", "label": "Heart · American, female"}, {"id": "af_bella", "label": "Bella · American, female"},
    {"id": "af_nicole", "label": "Nicole · American, female (soft)"}, {"id": "af_sarah", "label": "Sarah · American, female"},
    {"id": "am_adam", "label": "Adam · American, male"}, {"id": "am_michael", "label": "Michael · American, male"},
    {"id": "am_fenrir", "label": "Fenrir · American, male (deep)"}, {"id": "bf_emma", "label": "Emma · British, female"},
    {"id": "bm_george", "label": "George · British, male"}, {"id": "bm_fable", "label": "Fable · British, male"},
]
DRAFT_LANGUAGES = ["English"]
CLONING_LANGUAGES = ["English", "German", "French", "Spanish", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]   # Qwen3-TTS's ten
REFERENCE_S = (3.0, 10.0)                            # 19 §6 item 6: a 3–10 s reference clip
# E20's figures on this machine: a line takes ≈ its speech seconds × the tier's real-time factor, plus the model's load
RATES: dict[str, dict[str, float]] = {"draft": {"rtf": 0.35, "load_s": 5.0, "vram_gb": 0.0}, "cloning": {"rtf": 1.0, "load_s": 11.0, "vram_gb": 2.6}}   # CN2 rig 2026-10-15
WORDS_PER_S = 2.5                                    # speech at a reading pace: the estimate's speech seconds from the words
ITEM_RE = re.compile(r"^item (\d+)/(\d+)", re.M)


class VoiceRecord(BaseModel):
    """`story/voices/<id>.json`: a voice of the project — the draft tier's fixed Kokoro voice, or the cloning tier's reference clip (an
    `audio` asset of 3–10 s with its transcript) with the note of whose voice it is and that they consented (19 §6 item 6)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = VOICE_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("voc"))
    name: str
    tier: Tier = "draft"
    voice: str | None = None                       # draft: one of DRAFT_VOICES
    language: str = "English"
    reference_asset_id: str | None = None          # cloning: the reference clip (an audio asset)
    reference_text: str = ""                       # cloning: its transcript
    speaker: str = ""                              # cloning: whose voice
    consent: str = ""                              # cloning: the consent note (required)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    measured: dict[str, Any] = Field(default_factory=dict)     # the last job's figures: rtf, load_s, peak_vram_gb, lines


def check_voice(rec: VoiceRecord, reference: dict[str, Any] | None) -> None:
    """One sentence at creation and at submission: the tier's voice or reference, the language, the consent note."""
    if not rec.name.strip():
        raise ValueError("a voice needs a name")
    if rec.tier == "draft":
        if rec.voice not in {v["id"] for v in DRAFT_VOICES}:
            raise ValueError(f"the draft tier needs one of Kokoro's voices ({', '.join(v['id'] for v in DRAFT_VOICES)})")
        if rec.language not in DRAFT_LANGUAGES:
            raise ValueError(f"the draft tier speaks {' / '.join(DRAFT_LANGUAGES)} only — a {rec.language} line is the cloning tier's")
        return
    if rec.language not in CLONING_LANGUAGES:
        raise ValueError(f"the cloning tier speaks {', '.join(CLONING_LANGUAGES)}")
    if not rec.reference_asset_id:
        raise ValueError("the cloning tier needs a reference clip: an audio asset of 3–10 s (a recording, or a draft line)")
    if reference is None:
        raise ValueError(f"the reference clip {rec.reference_asset_id} is not in the Catalogue")
    if reference.get("kind") != "audio":
        raise ValueError("the reference clip must be an audio asset")
    d = reference.get("duration_s")
    if d is not None and not (REFERENCE_S[0] <= float(d) <= REFERENCE_S[1] + 0.5):
        raise ValueError(f"the reference clip is {float(d):.1f} s — a reference is {REFERENCE_S[0]:.0f}–{REFERENCE_S[1]:.0f} s")
    if not rec.reference_text.strip():
        raise ValueError("the cloning tier needs the reference clip's transcript")
    if not rec.consent.strip():
        raise ValueError("a cloned voice records whose voice it is and that they consented (19 §6 item 6)")


class VoiceStore:
    def __init__(self, ws: Any) -> None:
        self.dir: Path = ws.story_dir / "voices"

    def path(self, vid: str) -> Path:
        return self.dir / f"{plain_name(vid)}.json"

    def list(self) -> list[VoiceRecord]:
        out = []
        if self.dir.is_dir():
            for p in sorted(self.dir.glob("*.json")):
                try:
                    out.append(VoiceRecord.model_validate(read_json(p)))
                except Exception:  # noqa: BLE001 — a torn record is skipped, never fatal (files are truth, the index is this listing)
                    continue
        return sorted(out, key=lambda r: r.created_at)

    def get(self, vid: str) -> VoiceRecord | None:
        p = self.path(vid)
        return VoiceRecord.model_validate(read_json(p)) if p.is_file() else None

    def save(self, rec: VoiceRecord) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path(rec.id), rec.model_dump())

    def delete(self, vid: str) -> bool:
        p = self.path(vid)
        if not p.is_file():
            return False
        p.unlink()
        return True


# ---- what the submission checks -----------------------------------------------------------------------------------------------------
def voices_available(settings: "Settings") -> str | None:
    """None when the runner can run; else the sentence (the venv, the runner)."""
    v = settings.voices
    if not Path(v.python).is_file():
        return f"the voices venv is missing ({v.python}) — run scripts/voices-setup.ps1"
    if not Path(v.run).is_file():
        return f"the TTS runner is missing ({v.run})"
    return None


def model_cached(settings: "Settings", repo: str) -> bool:
    """Whether the hub model's snapshot is in HF_HOME (a first run fetches it: Kokoro 0.3 GB, Qwen3-TTS-0.6B 2.3 GB)."""
    d = Path(settings.hf_home) / "hub" / ("models--" + repo.replace("/", "--")) / "snapshots"
    return d.is_dir() and any(d.iterdir())


def tier_languages(tier: str) -> list[str]:
    return DRAFT_LANGUAGES if tier == "draft" else CLONING_LANGUAGES


def validate_tts(q: "JobQueue", recipe: TTS) -> None:
    """B11 for a voice job: the venv, the voice record (and its reference), the tier the recipe says, the language, the lines."""
    why = voices_available(q.app.settings)
    if why:
        raise ValueError(why)
    rec = VoiceStore(q.ws).get(recipe.voice_id)
    if rec is None:
        raise ValueError(f"unknown voice {recipe.voice_id!r}")
    if recipe.tier != rec.tier:
        raise ValueError(f"{rec.name} is a {rec.tier} voice; the job says {recipe.tier}")
    ref = q.catalogue.get(rec.reference_asset_id) if rec.reference_asset_id else None
    check_voice(rec, ref.model_dump() if ref else None)
    if recipe.language not in tier_languages(rec.tier):
        raise ValueError(f"the {rec.tier} tier does not speak {recipe.language} ({', '.join(tier_languages(rec.tier))})")
    if not any(it.text.strip() for it in recipe.items):
        raise ValueError("nothing to say: every line is empty")


def estimate_seconds(recipe: TTS) -> float:
    """E20: the words at a reading pace × the tier's real-time factor, plus the model's load."""
    words = sum(len(it.text.split()) for it in recipe.items)
    r = RATES[recipe.tier]
    return round(words / WORDS_PER_S * r["rtf"] + r["load_s"], 1)


# ---- the job -----------------------------------------------------------------------------------------------------------------------
def run_dir(ws: Any, job_id: str) -> Path:
    return ws.temp_dir / "tts" / job_id


def parse_progress(chunk: str) -> tuple[int, int] | None:
    m = None
    for m in ITEM_RE.finditer(chunk):
        pass
    return (int(m.group(1)), int(m.group(2))) if m else None


async def run_tts(job: "JobRecord", recipe: TTS, q: "JobQueue") -> bool:
    """The job: the request written, the runner run in the voices venv with its log in a file and its progress on the job card, a cancel
    killing the process tree, an exit ≠ 0 failing the job with its last lines; every spoken line an `audio` asset (lineage to the
    reference clip on the cloning tier) placed on its Flow line; the voice record keeps the measured figures. Returns True."""
    from .engine.pipeline import JobCancelled
    from .engine.supervisor import _assign_to_job
    from .story import StoryStore
    from .trainer import VramSampler, _kill
    settings = q.app.settings
    why = voices_available(settings)
    if why:
        raise ValueError(why)
    vstore = VoiceStore(q.ws)
    voice = vstore.get(recipe.voice_id)
    if voice is None:
        raise ValueError(f"unknown voice {recipe.voice_id!r}")
    ref = q.catalogue.get(voice.reference_asset_id) if voice.reference_asset_id else None
    rdir = run_dir(q.ws, job.id)
    shutil.rmtree(rdir, ignore_errors=True)
    rdir.mkdir(parents=True, exist_ok=True)
    items = [{"i": k, "text": it.text.strip(), "out": str(rdir / f"line_{k:02d}.wav")} for k, it in enumerate(recipe.items) if it.text.strip()]
    model = settings.voices.draft_model if recipe.tier == "draft" else settings.voices.cloning_model
    request = {"tier": recipe.tier, "model": model, "voice": voice.voice, "language": recipe.language, "speed": float(recipe.speed), "items": items,
               "reference": {"audio": str(q.catalogue.abs_path(ref)), "text": voice.reference_text} if ref else None, "result": str(rdir / "result.json")}
    atomic_write_json(rdir / "request.json", request)
    log_path = q.app.logs_dir / f"tts-{job.id}.log"
    env = {**os.environ, "HF_HOME": settings.hf_home, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    q.check_cancel(job)
    t0 = time.time()
    sampler = VramSampler() if recipe.tier == "cloning" else None
    if sampler:
        sampler.start()
    with log_path.open("ab") as lf:
        lf.write(f"==== launch {utc_now()} job {job.id} {recipe.tier} {model} {len(items)} line(s)\n".encode("utf-8"))
        lf.flush()
        start_pos = lf.tell()
        proc = subprocess.Popen([settings.voices.python, settings.voices.run, str(rdir / "request.json")], cwd=str(Path(settings.voices.run).parent), env=env,
                                stdout=lf, stderr=subprocess.STDOUT)
        in_job = _assign_to_job(proc)                                   # the orchestrator's job object: a kill takes the runner along
    job.log_tail.append(f"tts pid {proc.pid}" + (" in the job object" if in_job else ""))
    q.progress(job, f"voice: loading the {recipe.tier} model" + (" (the engine stopped)" if recipe.tier == "cloning" else ""))
    pos = start_pos
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
                got = parse_progress(chunk.decode("utf-8", "replace"))
                if got:
                    k, n = got
                    job.progress = min(1.0, k / max(1, n))
                    q.progress(job, f"voice: line {k} of {n}")
            if done:
                break
            if job.id in q._cancel_requested:
                _kill(proc.pid)
                await asyncio.to_thread(proc.wait)
                raise JobCancelled(job.id)
    finally:
        if sampler:
            sampler.stop()
    rc = proc.returncode
    text = log_path.read_text(encoding="utf-8", errors="replace").split("==== launch")[-1]
    if rc != 0:
        tail = [ln.strip() for ln in text.replace("\r", "\n").splitlines() if ln.strip()][-6:]
        raise ValueError(f"the TTS runner exited with {rc}: " + " | ".join(tail)[-900:])
    result_path = rdir / "result.json"
    if not result_path.is_file():
        raise ValueError("the TTS runner finished but wrote no result")
    result = read_json(result_path)
    by_i = {int(r["i"]): r for r in result.get("items", [])}
    await q.irreversible(job)                                           # C8: the assets below land once
    store = StoryStore(q.ws)
    out: list[dict[str, Any]] = []
    touched: set[str] = set()
    for k, it in enumerate(recipe.items):
        r = by_i.get(k)
        if r is None or not Path(r["file"]).is_file():
            continue
        src = Path(r["file"])
        asset = await asyncio.to_thread(
            q.catalogue.ingest_file, src, kind="audio", move=True, job_id=job.id, batch_id=job.batch_id, suite="story", prompt_text=it.text.strip(),
            params={"recipe": recipe.model_dump(), "voice_id": voice.id, "voice_name": voice.name, "tier": recipe.tier, "voice": voice.voice, "language": recipe.language,
                    "model": model, "line": {"node_id": it.node_id, "index": it.index}, "seconds": r.get("seconds")},
            timings={"wall_s": r.get("seconds"), "load_s": result.get("load_s")}, parents=[ref.id] if ref else [],
            **({"lineage_kind": "voice-clone"} if ref else {}), duration_s=r.get("duration_s"), variant=job.variant, origin=job.origin)
        asset = await asyncio.to_thread(q.catalogue.make_thumbs, asset)
        q.hub.broadcast("asset.created", asset.model_dump())
        if it.node_id is not None and it.index is not None:
            try:
                n = await asyncio.to_thread(store.set_line_audio, it.node_id, int(it.index), asset.id, it.text.strip())
                touched.add(n.id)
            except KeyError as e:                                       # the node or the line went while the job ran: the asset stays in the Catalogue
                job.log_tail.append(f"line not stamped: {e}")
        out.append({"asset_id": asset.id, "duration_s": r.get("duration_s"), "seconds": r.get("seconds"), "node_id": it.node_id, "index": it.index})
    for nid in touched:
        q.hub.broadcast("story.changed", {"kind": "flow", "id": nid, "revision": 0})
    speech = sum(float(x["duration_s"] or 0) for x in out)
    spoken = sum(float(x["seconds"] or 0) for x in out)
    voice.measured = {"rtf": round(spoken / speech, 2) if speech else None, "load_s": result.get("load_s"), "peak_vram_gb": result.get("peak_vram_gb"),
                      "lines": len(out), "at": utc_now()}
    voice.updated_at = utc_now()
    vstore.save(voice)
    q.hub.broadcast("story.changed", {"kind": "voice", "id": voice.id, "revision": 0})
    job.result = {"asset_ids": [x["asset_id"] for x in out], "voice_id": voice.id, "tier": recipe.tier, "items": out, "load_s": result.get("load_s"),
                  "peak_vram_gb": result.get("peak_vram_gb"), "wall_s": round(time.time() - t0, 1), "log": str(log_path)}
    job.log_tail.append(f"{len(out)} line(s): {speech:.1f} s of speech in {spoken:.1f} s" + (f", peak {result.get('peak_vram_gb')} GB" if result.get("peak_vram_gb") else ""))
    shutil.rmtree(rdir, ignore_errors=True)
    return True
