# voices/ — notes for coding agents

Verified at b345d85 on 2026-10-14.

The voice tools of wave CN (`.docs/proto01/19-continuity-and-voice.md`, D87): Kokoro (the draft TTS tier, Apache-2.0) and Qwen3-TTS (the
cloning tier, Apache-2.0) in their own venv `voices/.venv` — never the engine venv, and not `trainers/.venv` either: Qwen3-TTS pins
transformers 4.x while ai-toolkit pins 5.5.3, so the two cannot share one.

- **Setup:** `scripts/voices-setup.ps1` — the venv on Python 3.12 with the engine's ROCm torch wheels from the AMD index, then
  `kokoro`, `misaki[en]`, `soundfile`, `qwen-tts` under `voices/constraints.txt` (torch pinned to the ROCm build). Re-runnable. The models
  land in `HF_HOME` (`F:/HF_HOME`) on first use: `hexgrad/Kokoro-82M` (0.3 GB), `Qwen/Qwen3-TTS-12Hz-0.6B-Base` (2.3 GB).
- **Kokoro** runs on the CPU (`KPipeline(lang_code="a", device="cpu")`, the `af_heart` voice, 24 kHz); it has no German — a DE line is the
  cloning tier's. **Qwen3-TTS Base** runs on the GPU in bf16 without FlashAttention (the package warns and falls back to plain torch), clones
  from a reference clip + its transcript (`create_voice_clone_prompt`, then `generate_voice_clone(text, language, voice_clone_prompt)`), ten
  languages. A reference voice is the author's own or a consenting speaker's — the `voice` record says whose (19 §3b).
- **Spike:** `engine/spikes/e20_voice.py` (the draft and cloning tiers on six lines, timings, RTF, peak VRAM; run with
  `voices/.venv/Scripts/python.exe`); its numbers are in the journal and 19 §2.
- The product's `tts` job (CN2) runs this venv's python as the trainer runs `trainers/.venv` (`Settings.voices`), the cloning tier with the
  engine stopped (`plan().gpu`), the draft tier beside it on the CPU.
