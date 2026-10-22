# tools/lipsync/ — notes for coding agents

Verified at cbfde7f on 2026-10-22.

The lip-sync model as a tool (D118 AE4d, `.docs/proto01_animate/20-animation-editor-build.md` §6, from spike E29b's L3a — journal
2026-10-21 22:14): LatentSync 1.5 (ByteDance) in its own venv `tools/lipsync/.venv` — never the engine venv (torch pins differ, and the
model wants Python 3.11: `decord` has no 3.12 wheel). The code is Apache-2.0; the 1.5 weights are OpenRAIL++, so the tool is offered under
the `full` variant only (D26).

- **Setup:** `scripts/lipsync-setup.ps1` — the checkout `tools/lipsync/LatentSync` at the pinned commit, the venv on Python 3.11 with the
  engine's ROCm torch wheels from the AMD index, the requirements minus the CUDA ONNX runtime (the CPU one for insightface; the face
  detector's provider patched to CPU), gradio, lpips and scenedetect; ffmpeg from `imageio-ffmpeg` copied beside the venv's python under
  the name the code calls; the weights into `checkpoints/` (the U-Net 4.8 GB, whisper tiny, insightface's buffalo_l, face-alignment's
  files — the syncnet and the eval models left out) from the spike's checkout when it is there, else from the hub; the SD VAE
  (`stabilityai/sd-vae-ft-mse`, MIT) into `HF_HOME` on first use. Re-runnable; skips what exists. Both folders are git-ignored.
- **The runner's contract:** `python tools/lipsync/sync.py <request.json>` — checkout, video (the head clip at 25 fps), audio (a WAV),
  out, steps, guidance, seed, result; prints `loading …`, `syncing …`, `done in N s`; exit ≠ 0 fails the job with its last lines. It
  calls LatentSync's own inference script (scripts/inference.py in the checkout, its `main(config, args)`) in-process with `configs/unet/stage2.yaml`.
  The model stops at the first frame its detector finds no face in; the runner patches `ImageProcessor.affine_transform` so such a frame
  (a head turned away — 11 of 127 on the rig) takes the last detected face's landmarks and the clip keeps its length; the count is in
  the result and on the job's log. The first frame must have a face.
- **The product's `mouth` step (AE4d):** `orchestrator/loom2/lipsync.py` — the face pass's chain (`LayerPass` with `step.stage == "mouth"`)
  runs it as a CPU-path job with the engine stopped (`plan().gpu`), like the trainer: the kept rendered heads (`passes/<take>/work/head/`)
  stitched and resampled to 25 fps as one mp4, the layer's lines mixed over the shot (`final_assembly.mix_audio`), the request JSON in
  `_temp/lipsync/<job>/`, the log in `state/logs/lipsync-<job>.log`, the output decoded, resampled back to the final's rate under the
  heads' own silhouettes, then the paste (`finish_face_take` in `orchestrator/loom2/engine/finishers.py`). `Settings.lipsync`: python, run, checkout, steps (20),
  guidance (1.5). `orchestrator/tests/fake_lipsync.py` stands in for the runner in the tests and the e2e smoke (it tints the mouth).
- **Measured (E29b, 2026-10-21):** 77 head frames (120 at 25 fps) in 104 s; identity kept (FaceSim 0.48–0.56); the most natural mouth of
  the heads to the eye. The detector finds no face in a smeared crop: the input is the face pass's sharp head, never the layer's own crop.
- **Rig check:** `orchestrator/.venv/Scripts/python.exe engine/spikes/ae4c_rig.py --arms mouth` (the PS5 final through the app).
