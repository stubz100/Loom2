"""loom2's TTS runner (CN2, 19 §3b): runs in voices/.venv (scripts/voices-setup.ps1) — never the engine venv.

    python voices/tts.py <request.json>

The request: tier (draft | cloning), model (the hub repo), voice (a Kokoro voice, draft), language, speed (draft), items [{i, text, out}],
reference {audio, text} (cloning), result (the JSON to write). Prints one line per step ("loading …", "item k/n: …") for the job card;
the result lists every line's file, duration and seconds, the load time and the GPU peak. The draft tier (Kokoro-82M) runs on the CPU;
the cloning tier (Qwen3-TTS Base) on the GPU in bf16 without FlashAttention — E20's recipe (engine/spikes/e20_voice.py).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf


def say(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str]) -> int:
    req = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    items = req["items"]
    tier = req["tier"]
    import torch
    t0 = time.time()
    results = []
    peak = None
    if tier == "draft":
        from kokoro import KPipeline
        # one thread: the ROCm wheel's OpenBLAS has 100 ms cliffs on small multiplies when threaded (a 2 s line took 7–8 s at 4–16
        # threads, 0.8 s at one — journal 2026-10-15), and one core leaves the rest to a running engine
        torch.set_num_threads(1)
        voice = req.get("voice") or "af_heart"
        say(f"loading {req['model']} ({voice}) on the CPU")
        pipe = KPipeline(lang_code=voice[0] if voice[:1] in ("a", "b") else "a", repo_id=req["model"], device="cpu")
        load_s = round(time.time() - t0, 1)
        say(f"loaded in {load_s} s")
        speed = float(req.get("speed") or 1.0)
        for n, it in enumerate(items, 1):
            t1 = time.time()
            chunks = [np.asarray(r.audio, dtype=np.float32) for r in pipe(it["text"], voice=voice, speed=speed)]
            audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
            sr = 24000
            sf.write(it["out"], audio, sr, subtype="PCM_16")
            secs = round(time.time() - t1, 2)
            results.append({"i": it["i"], "file": it["out"], "duration_s": round(len(audio) / sr, 3), "seconds": secs, "sample_rate": sr})
            say(f"item {n}/{len(items)}: {results[-1]['duration_s']} s of speech in {secs} s")
    else:
        from qwen_tts import Qwen3TTSModel
        dev = "cuda:0" if torch.cuda.is_available() else "cpu"
        say(f"loading {req['model']} on {dev}")
        model = Qwen3TTSModel.from_pretrained(req["model"], device_map=dev, dtype=torch.bfloat16 if dev != "cpu" else torch.float32)
        load_s = round(time.time() - t0, 1)
        say(f"loaded in {load_s} s")
        ref = req["reference"]
        if dev != "cpu":
            torch.cuda.reset_peak_memory_stats()
        t1 = time.time()
        prompt = model.create_voice_clone_prompt(ref_audio=ref["audio"], ref_text=ref["text"])
        say(f"cloned the reference in {time.time() - t1:.1f} s")
        language = req.get("language") or "English"
        for n, it in enumerate(items, 1):
            t1 = time.time()
            wavs, sr = model.generate_voice_clone(text=it["text"], language=language, voice_clone_prompt=prompt)
            audio = np.asarray(wavs[0], dtype=np.float32)
            sf.write(it["out"], audio, int(sr), subtype="PCM_16")
            secs = round(time.time() - t1, 2)
            results.append({"i": it["i"], "file": it["out"], "duration_s": round(len(audio) / int(sr), 3), "seconds": secs, "sample_rate": int(sr)})
            say(f"item {n}/{len(items)}: {results[-1]['duration_s']} s of speech in {secs} s")
        peak = round(torch.cuda.max_memory_allocated() / 2**30, 2) if dev != "cpu" else None
    out = {"tier": tier, "model": req["model"], "load_s": load_s, "peak_vram_gb": peak, "items": results, "wall_s": round(time.time() - t0, 1)}
    Path(req["result"]).write_text(json.dumps(out), encoding="utf-8")
    say("done")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
