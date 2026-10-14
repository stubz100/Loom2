# trainers/ — notes for coding agents

Verified at 8d380e5 on 2026-10-14.

The LoRA trainer of wave LT (`.docs/proto01/18-lora-training.md`, D86): ai-toolkit (MIT) as the pinned submodule `trainers/ai-toolkit`,
run from its own venv `trainers/.venv` — never from the engine venv, never with the engine running (16 GB first).

- **Setup:** `scripts/trainer-setup.ps1` — the submodule at its pin, the venv on Python 3.12 (ai-toolkit pins SciPy 1.12, which has no 3.13
  wheel) with the engine's ROCm torch wheels from the AMD index, the requirements filtered under `trainers/constraints.txt` (no `bitsandbytes` —
  no ROCm / Windows build, AdamW instead of adamw8bit —, no `torchcodec` — video only; `torchao` 0.10.0's pure-Python wheel stays, because
  `layer_offloading` turns qfloat8 into its `float8` and that is the 9B base's only fit on this card — E16d, 2.8 s/it at 8.7 GB), then `trainers/patches/*.patch` applied inside the submodule (`git apply`, skipped when already applied). Re-runnable.
- **Patches** are seams, never the training algorithm: `trainers/patches/0001-torchao-optional.patch` guards the three eager `torchao`
  imports (kept although torchao is installed: the 4B path runs without it) (`toolkit/config_modules.py`, `toolkit/util/quantize.py`, `toolkit/models/lokr.py`). loom's other seams of 2026-06 (the
  `torch.distributed.is_initialized` predicate, the Diffusers FSDP shim) are not needed on torch 2.13 + ROCm 10 — its `torch.distributed`
  is complete. Moving the pin: `git -C trainers/ai-toolkit checkout <sha>`, re-check every patch, run the setup, run E16's smoke.
- **Models:** Klein base (`flux2_klein_4b` / `_9b`) reads the transformer from a folder holding `flux-2-klein-base-4b.safetensors` — the
  models root's `diffusion_models/` as it is; the encoder is the `Qwen/Qwen3-4B` (8B) transformers folder in `HF_HOME` (`F:/HF_HOME`,
  offline after the fetch; ComfyUI's single-file encoder is not loadable there); the autoencoder is the hub's `ae.safetensors`
  (`ai-toolkit/flux2_vae`) — loom2's `vae/flux2-vae.safetensors` is the diffusers-named repack its loader does not read (LT2 remaps it).
- **Runs:** every run's `training_folder` is a temp dir of the job (the spike: `engine/spikes/out/e16/`); ai-toolkit resumes by itself
  from the newest checkpoint found there (`save_every`, `optimizer.pt`), so a killed job is relaunched on the same config. Logs go to a
  file, never an unread pipe; VRAM is sampled from Windows' GPU adapter counter (no CUDA context of its own).
- **Spike:** `engine/spikes/e16_klein_lora.py` (refs → train → load) is the record of what works on this card; its numbers are in the
  journal and 18 §2: Klein base-4B, 37 refs at 512, rank 16 → 1.07 s/it, 13.6 GB peak (9B base: 70 s/it paging without, 2.8 s/it at
  8.7 GB with `layer_offloading`), the adapter on distilled klein-4b with 0 unmatched
  keys and FaceSim 0.38 to the hero (controls 0.11). ComfyUI names a subfolder's file with the OS separator (`e16\\x.safetensors`).
