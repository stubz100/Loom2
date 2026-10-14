"""E20 — the voice tiers (19 §2, D87): can this rig speak a Flow line in seconds, in the author's languages, from a short reference?

Runs in voices/.venv (scripts/voices-setup.ps1: the ROCm torch, Kokoro, Qwen3-TTS — its own venv because Qwen3-TTS pins transformers 4.x
while ai-toolkit pins 5.5.3).
  draft     Kokoro-82M (Apache-2.0) on the CPU: fixed voices, English (Kokoro has no German) — six lines (four EN; the two DE lines are
            spoken by Qwen3-TTS only)
  cloning   Qwen3-TTS-12Hz-0.6B-Base (Apache-2.0) on the GPU: a 3-s clone from a reference clip with its transcript — EN and DE lines;
            the reference here is a Kokoro line (a synthetic speaker: the mechanics are measured; a real voice needs its owner's consent, 19 §3b)
Measures per line: seconds, the real-time factor (seconds of compute per second of speech), the GPU's peak allocation (torch), the WAV's
length; bars (19 §2): the draft tier ≤ 5 s per 5-s English line on the CPU; the cloning tier installs without FlashAttention and speaks a
5-s DE and EN line ≤ 15 s on the GPU; by ear (the author): intelligible, the clone recognisable. Outputs under engine/spikes/out/e20/:
one WAV per line and tier, results.jsonl. The engine should be idle for the GPU timings.

    voices/.venv/Scripts/python.exe engine/spikes/e20_voice.py [--tiers draft,cloning] [--qwen Qwen/Qwen3-TTS-12Hz-0.6B-Base]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "engine" / "spikes" / "out" / "e20"
RESULTS = OUT / "results.jsonl"
os.environ.setdefault("HF_HOME", "F:/HF_HOME")
LINES = [
    ("en1", "English", "Mara", "I know the way through the lower gate. Stay close and keep your lantern low."),
    ("en2", "English", "Mara", "The courier never came back. If the seal is broken, we leave before the bells."),
    ("en3", "English", "Mara", "You don't owe me anything. But if you follow, you follow all the way."),
    ("en4", "English", "Mara", "Listen. The rain hides our steps, not our voices."),
    ("de1", "German", "Mara", "Ich kenne den Weg durch das untere Tor. Bleib dicht hinter mir und halte die Laterne niedrig."),
    ("de2", "German", "Mara", "Der Kurier ist nie zurückgekommen. Wenn das Siegel gebrochen ist, gehen wir vor den Glocken."),
]
BARS = {"draft_s": 5.0, "cloning_s": 15.0}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def record(row: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def draft(lines: list[tuple[str, str, str, str]]) -> dict[str, Path]:
    """Kokoro on the CPU, the 'af_heart' voice; a line may come back in several chunks — concatenated."""
    import torch
    from kokoro import KPipeline
    torch.set_num_threads(max(4, os.cpu_count() // 2))
    t0 = time.time()
    pipe = KPipeline(lang_code="a", device="cpu")
    load_s = round(time.time() - t0, 1)
    log(f"draft: Kokoro loaded in {load_s} s")
    out: dict[str, Path] = {}
    for lid, lang, who, text in lines:
        if lang != "English":
            continue
        t0 = time.time()
        chunks = [np.asarray(r.audio) for r in pipe(text, voice="af_heart", speed=1.0)]
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        secs = round(time.time() - t0, 2)
        dur = round(len(audio) / 24000, 2)
        p = OUT / f"{lid}_draft.wav"
        sf.write(p, audio, 24000)
        out[lid] = p
        record({"tier": "draft", "model": "hexgrad/Kokoro-82M", "line": lid, "language": lang, "text": text, "seconds": secs, "speech_s": dur,
                "rtf": round(secs / max(0.01, dur), 3), "device": "cpu", "load_s": load_s, "wav": str(p), "bar": secs <= BARS["draft_s"], "stamp": time.strftime("%Y-%m-%d %H:%M")})
        log(f"  {lid}: {dur} s of speech in {secs} s (bar ≤ {BARS['draft_s']} s)")
    return out


def cloning(lines: list[tuple[str, str, str, str]], refs: dict[str, Path], repo: str) -> None:
    """Qwen3-TTS Base: a voice-clone prompt from one reference (a Kokoro line and its transcript), then every line in its language."""
    import torch
    from qwen_tts import Qwen3TTSModel
    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(repo, device_map=dev, dtype=torch.bfloat16 if dev != "cpu" else torch.float32)
    load_s = round(time.time() - t0, 1)
    log(f"cloning: {repo} loaded on {dev} in {load_s} s")
    ref_id = next((k for k in ("en1", "en2") if k in refs), None)
    if ref_id is None:
        log("cloning: no reference line from the draft tier — skipped")
        return
    ref_text = next(t for i, _, _, t in LINES if i == ref_id)
    if dev != "cpu":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    prompt = model.create_voice_clone_prompt(ref_audio=str(refs[ref_id]), ref_text=ref_text)
    log(f"  clone prompt from {ref_id} in {time.time() - t0:.1f} s")
    for lid, lang, who, text in lines:
        t0 = time.time()
        wavs, sr = model.generate_voice_clone(text=text, language=lang, voice_clone_prompt=prompt)
        secs = round(time.time() - t0, 2)
        audio = np.asarray(wavs[0], dtype=np.float32)
        dur = round(len(audio) / sr, 2)
        p = OUT / f"{lid}_clone.wav"
        sf.write(p, audio, sr)
        peak = round(torch.cuda.max_memory_allocated() / 2**30, 2) if dev != "cpu" else None
        record({"tier": "cloning", "model": repo, "line": lid, "language": lang, "text": text, "seconds": secs, "speech_s": dur, "rtf": round(secs / max(0.01, dur), 3),
                "device": dev, "load_s": load_s, "peak_vram_gb": peak, "reference": ref_id, "wav": str(p), "bar": secs <= BARS["cloning_s"], "stamp": time.strftime("%Y-%m-%d %H:%M")})
        log(f"  {lid} ({lang}): {dur} s of speech in {secs} s, peak {peak} GB (bar ≤ {BARS['cloning_s']} s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="draft,cloning")
    ap.add_argument("--qwen", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tiers = [t for t in a.tiers.split(",") if t]
    refs: dict[str, Path] = {}
    if "draft" in tiers:
        refs = draft(LINES)
    else:
        refs = {k: OUT / f"{k}_draft.wav" for k in ("en1", "en2") if (OUT / f"{k}_draft.wav").is_file()}
    if "cloning" in tiers:
        try:
            cloning(LINES, refs, a.qwen)
        except Exception as e:  # noqa: BLE001 — recorded, the spike's verdict
            record({"tier": "cloning", "model": a.qwen, "error": f"{type(e).__name__}: {str(e)[:500]}", "stamp": time.strftime("%Y-%m-%d %H:%M")})
            log(f"cloning FAILED: {type(e).__name__}: {str(e)[:300]}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
