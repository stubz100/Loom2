# 19 · Wave CN — Continuity and voice: extension, keyframe chains, pose-driven shots, lip-sync — plan

Status: **accepted 2026-10-14** (D87, the author: §6 as written, the four spikes and the downloads); E20 GO → **CN2 built and rig-checked 2026-10-15**; E17 / E18 / E19 in progress, each gating its slice. 03 §5 item 4 ("video extension, keyframe chains, pose/VACE control,
lip-sync; fps conform per spike E9"), 11 §3d's *Extend*, 13 §… item 6 (Animate: native LTX extension, camera control), 17 §13's SV line
(voice and lip-sync, out of the Story v1 by loom R95 — the author asked for it in this wave, 2026-10-14), loom P3 (02 §2: "continuity is
unsolved", the make-or-break R&D; two TTS tiers + lip-sync as node-level voice).

A clip longer than one generation, a character who keeps their face across the joins, a shot that follows the Stage's blocking with the
Cast's own character, and a line of dialogue spoken by that character with the lips following the voice. All of it on 16 GB, with the
pinned engine's own nodes, measured before it is called done.

## 0. What exists

| Where | What | State |
| --- | --- | --- |
| Animate (11, D8 / D9 / D27) | Wan 2.2 I2V-A14B fp8 experts + Lightning (Draft 2+2: 312–366 s per 81 f at 832×480 — E4), FLF on the same weights; LTX-2.3 distilled fp8 (141 s per 121 f at 1024×576 — E5) with keyframe **beats** (`LTXVAddGuide` at any frame) and the end frame; extract → first / last frame; RIFE v4.6 fps conform at export (E9: 81 → 121 f in ≈ 2 s, judder 1.22 vs 2.63, no ghosting) | the chain today = extract the last frame → the next clip's start: the pose carries, the motion does not |
| Stage → clip (16 §8, D76) | ST4: LTX-2.3 + its IC-LoRA Union on the Stage's rendered depth pass (pose followed 4/5), the pose pass weaker (3/5); 147 s = 1.22× plain | loom2 renders its own pose / depth passes — no DWPose node needed for a Stage-driven shot |
| Story (17, D85) | shots with versions and **takes** (a frame and / or a clip; a stage camera's results land as takes), Flow nodes with **Dialogue lines**, the Episode lane with the SRT and chapter markers | the voice has nowhere to live yet: no audio asset kind, no audio in the lane's exports |
| Cast + LoRA (18, D86) | a character's LoRA + trigger; `@Mara` adds them to any Generate recipe | the identity source for a talking take and for a pose-driven shot |
| The pinned engine (ComfyUI 0.39.0, core) | `WanSoundImageToVideo` + `…Extend` (Wan2.2 **S2V**: a reference image + audio → a talking clip, 77 f per chunk, chained), `WanInfiniteTalkToVideo` (dubbing from a still; the video-to-video form needs a wrapper), `WanAnimateToVideo` / `WanAnimate2ToVideo` (Wan2.2 **Animate**: a reference image + pose / face videos → *Move* or *Mix*, `continue_motion_max_frames`), `WanVaceToVideo` / `Wan22FunControlToVideo` (control + extension), `WanCameraImageToVideo`, `LTXVAudioVAEEncode` / `LTXVConcatAVLatent` (LTX's joint audio-video latent — loom2's LTX graph already builds it with an *empty* audio latent), `LTXVAddGuide` on an image **or a frame sequence** (E11), `AudioEncoderLoader` (`audio_encoders/`), `LoadAudio` / `SaveAudio*` / `TrimAudioDuration` | every method below is a core node — no custom node (house rule 2) |
| Weights (`F:/loom2-models`, 714 GB free) | Wan 2.2 I2V experts fp8 (13.3 GB each), umT5 fp8, Wan 2.1 VAE, Lightning LoRAs; LTX-2.3 distilled transformer fp8 (23.5 GB), Gemma-3 fp8, the video **and audio** VAEs | nothing audio-driven, no Animate, no VACE, no TTS |
| Repacks (Apache-2.0, `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`, `Kijai/WanVideo_comfy_fp8_scaled`, `Comfy-Org/Wan_2.1_ComfyUI_repackaged`) | `wan2.2_s2v_14B_fp8_scaled` 15.3 GB · `wav2vec2_large_english_fp16` 0.6 GB · `Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ` 17.1 GB (the ComfyUI template's file) · `clip_vision_h` 1.2 GB · `wan2.2_animate_14B_relight_lora` 1.3 GB · VACE: the Fun-VACE experts 16.2 GB ×2 or Kijai's 2.8 GB modules | S2V and Animate are single 14B transformers — the same footprint as one Wan expert loom2 streams today |
| TTS (2026) | **Kokoro-82M** (Apache-2.0, 0.3 GB, CPU, fixed voices), **Chatterbox** (MIT, English cloning from 5–10 s, a few GB of VRAM), **Qwen3-TTS-0.6B / 1.7B** (Apache-2.0, 2.3 GB, ten languages incl. DE / FR / ES / IT / PT, a 3-s clone; GPU; FlashAttention recommended, not required) | loom P3's "Piper / Kokoro draft · XTTS / F5 cloning" — XTTS and F5 are non-commercial, out under D17 / D26 |

## 1. Purpose and scope

- **In:** (1) **Extend** — a clip continued by another whose first frames are the previous clip's last frames, as many times as the shot
  needs, with the seam measured; the chain recorded (`chained_from`, loom R98) and the Episode welding the joins at export. (2) **Keyframe
  chains** — LTX beats across a chain (a beat beyond the first segment lands in the segment that holds its frame). (3) **Pose-driven shots** —
  the Cast's character performing the Stage's blocking: Wan2.2 Animate *Move* on loom2's own rendered pose pass, beside ST4's LTX IC-LoRA.
  (4) **Voice** — a Flow node's Dialogue line spoken by a TTS tier (draft: fixed voices on the CPU; cloning: from a short reference clip),
  as an audio asset on the node, in the Episode's exports. (5) **Lip-sync** — a talking take of a shot version: the character's frame (or
  hero) + the line's voice clip → a clip whose lips follow the audio, by the engine's own nodes (LTX IA2V or Wan S2V), with FaceSim as the
  identity measure.
- **Out:** camera-control LoRAs / VACE as a product (E19 records VACE only if Animate fails), InfiniteTalk's video-to-video dubbing (a
  wrapper node — a decision, not a convenience), singing, multi-speaker clips, voice *design* beyond a reference clip, the Episode's audio mix
  (one voice lane; music and effects stay in the NLE), lip-sync of clips not made in loom2.

## 2. Spikes first — E20 · E17 · E18 · E19 (7 d, each a GO / NO-GO; 08 §7's kill rule)

Every spike is a script under `engine/spikes/`, its numbers in the journal, D87's row revised by its verdict; losers' weights deleted (D30).

### E20 · Voice (1 d) — the TTS tiers, before E18 needs lines

| Candidate | Tier | Why | Bar |
| --- | --- | --- | --- |
| Kokoro-82M (Apache-2.0, `pip kokoro`, 0.3 GB) | draft | CPU, seconds, 50+ fixed voices (EN; other languages need espeak-ng) | a 5-s English line ≤ 5 s on the CPU; intelligible by ear |
| Qwen3-TTS-0.6B (Apache-2.0, `pip qwen-tts`, 2.3 GB) | cloning | ten languages with DE / FR / ES / IT / PT (the author is EU-based), a 3-s clone with a transcript | installs in `trainers/.venv` on torch 2.13 ROCm without FlashAttention; a 5-s DE and EN line ≤ 15 s on the GPU; the clone recognisable by ear (3 / 3 listeners of one) |
| Chatterbox (MIT, `pip chatterbox-tts`, the English model ≈ 1–2 GB) | cloning (alternate) | the blind-test favourite for English | the same bars; chosen over Qwen3-TTS only if Qwen3 fails to install or sounds worse |

**Run 2026-10-14 (`engine/spikes/e20_voice.py`, journal) — GO on both tiers.** Kokoro 0.9.4 loads in 2 s and speaks a 3.5–5 s English line in 2.5–4.7 s on the CPU (one 13 s outlier while the engine and two 15 GB downloads shared the machine); Qwen3-TTS-0.6B-Base loads in 167 s cold (the 2.3 GB fetch included), makes a clone prompt from a 4.6 s Kokoro reference in 20 s and speaks EN and DE lines of 3.4–5.4 s in 3.0–5.1 s on the GPU at a 2.6 GB peak — without FlashAttention (the package's plain-torch path). Chatterbox was not needed. **One change to §6 item 3:** the voice tools got their own venv `voices/.venv` (`scripts/voices-setup.ps1`, `voices/AGENTS.md`) — Qwen3-TTS pins transformers 4.x and ai-toolkit 5.5.3, so they cannot share `trainers/.venv`; the venv also carries pip and spaCy's `en_core_web_sm` for Kokoro's English G2P.

The winner of the cloning tier is one model; the draft tier is Kokoro unless it fails to install. Both run as queue jobs without the engine
(the cloning tier with the engine stopped, as training — `plan().gpu`). The reference clip for a clone is the author's own voice or a
consenting speaker's; the job records whose (a `voice` record, §3b).

### E17 · Extend (2 d) — continuity across the join

| Method | Weights | How | Bar |
| --- | --- | --- | --- |
| **A · LTX guide-frame extension** | none new (the distilled 1.1 on disk) | the previous clip's last **9 frames** (8n+1) as an `LTXVAddGuide` frame sequence at frame 0 of the next (strength 1.0), E11's graph with a sequence instead of a pass; the prompt carries the motion | the join's seam score ≤ 1.5× the clip's own median inter-frame difference (mean absolute pixel difference at the join vs within the clip); FaceSim to the start frame ≥ 0.45 at both ends of a three-segment chain; ≤ 1.3× a plain clip (≤ 185 s per 121 f) |
| **B · Wan last-frame chaining + a RIFE weld** | none new | today's extract → start, then 2–4 bridging frames synthesised at the join with rife-ncnn-vulkan (E9's tool) | the same seam bar *after* the weld; FaceSim the same; the weld ≤ 5 s |
| C · S2V `Extend` / Animate `continue_motion` | from E18 / E19 | recorded as the by-product of those spikes (the audio-driven and pose-driven chains) | recorded, no bar |

Bench: three chains × three segments at the Draft tier from `bench/i2v` (alley-rain, rooftop-night, captain-cabin — the bench character),
one motion prompt per chain; scored by the seam metric, FaceSim and nine sheets by eye (motion continuity ≥ 7 / 9). The winner is CN1's
`extend_from`; a loser that passes stays as the model's own path (Wan clips chain by B, LTX by A) if both pass.

### E18 · Lip-sync (2 d)

| Method | Weights | How | Bar |
| --- | --- | --- | --- |
| **A · LTX-2.3 IA2V on the distilled 1.1** | none new | `LoadAudio` → `LTXVAudioVAEEncode` into the AV latent in place of the empty audio latent (one node of loom2's LTX graph), the hero as the start frame, 121 f at 24 fps; the template uses the dev fp8 checkpoint — the spike says whether the distilled transformer follows the audio | a mouth-motion proxy (the lower-face region's temporal variance against the audio's RMS envelope, Pearson r ≥ 0.5 — the detector gives no mouth opening); FaceSim to the start frame ≥ 0.45; ≤ 240 s per 5-s line; by eye the lips move with the words ≥ 5 / 6 |
| **B · Wan2.2 S2V-14B fp8** (15.3 GB + wav2vec2 0.6 GB, Apache-2.0) | fetched | `AudioEncoderLoader` / `AudioEncoderEncode` → `WanSoundImageToVideo` 77 f at 16 fps, 20 steps CFG 6 (the template warns the Lightning LoRA hurts S2V), `…Extend` for a line over 4.8 s | the same bars at 832×480; VRAM no OOM (one 14B transformer streamed as the I2V experts are) |

Inputs: six lines (four EN, two DE) from E20's draft tier, two faces (Mara's hero from E16's run and `portrait-grief`), fixed seeds; the
sheets and the clips with audio muxed (`ffmpeg`, as the proxies are) for the author's ear and eye. Licences: S2V Apache (both variants);
LTX as the roster tags it today.

### E19 · Pose-driven shots (2 d)

| Method | Weights | How | Bar |
| --- | --- | --- | --- |
| **A · Wan2.2 Animate *Move*** (`Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ` 17.1 GB + `clip_vision_h` 1.2 GB + the LightX2V I2V 4-step LoRA ≈ 0.7 GB, Apache-2.0) | fetched | `WanAnimateToVideo` with the Cast hero as `reference_image` and the Stage's **own rendered pose pass** as `pose_video` (E10's scenes, 77 f at 832×480; no DWPose, no face video) | PCK@0.1 ≥ 0.8 against the rendered keypoints (E10's SDPose scorer); FaceSim to the hero ≥ 0.45; ≤ 2× ST4's guided clip (≤ 300 s per 77 f); no OOM |
| B · ST4's LTX IC-LoRA pose (measured: 3 / 5) and depth (4 / 5) | none | the baseline | — |
| C · VACE (Fun-VACE experts 16.2 GB ×2 or Kijai's 2.8 GB modules) | only if A fails | `WanVaceToVideo` on the pose pass | A's bars |

The *Mix* mode (replace a person in a real video; needs SAM2 masks) is out of this wave.

**Run 2026-10-14 / 15 (`engine/spikes/e19_animate.py`, journal) — GO for one character per pose pass; FaceSim advisory.** With Mara's hero **padded** into the 832×480 frame (a centre-cropped portrait was painted into the background as a ghost) and the score fixed (E11's keypoints mapped from its 1024×576 render into the scaled, cropped frame — the first scores of 0.0 compared two coordinate spaces): walk_dolly PCK 0.958, turn_orbit 0.805, wave_static 1.0, crouch_crane 0.972, each 77 f in 264–297 s (bar ≤ 300 s), no OOM — the LTX IC-LoRA baseline followed 3 / 5. **run_track fails (0.0):** its pass holds two small overlapping runners and Animate read them as hands over a close-up face — one character per pose pass. FaceSim to the hero is 0.38–0.49 where the face is big enough to score (turn, wave; the bar 0.45 missed narrowly) and meaningless on the wide shots (0.07–0.33); by eye the character holds (face, red braids, the green hood). CN4 shows FaceSim as advisory (as 18 §3h) and refuses a pose pass with more than one figure. VACE (C) is not needed.

**Downloads and installs the spikes need (the author's approval, D87):** `wan2.2_s2v_14B_fp8_scaled` 15.3 GB + `wav2vec2_large_english_fp16`
0.6 GB; `Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ` 17.1 GB + `clip_vision_h` 1.2 GB + the LightX2V I2V 4-step LoRA ≈ 0.7 GB (the relight LoRA
1.3 GB only with *Mix*, later); Kokoro 0.3 GB; Qwen3-TTS-0.6B 2.3 GB; Chatterbox's English model ≈ 1–2 GB only if Qwen3 fails — **≈ 38 GB**,
all Apache-2.0 / MIT (D17 / D26), via `scripts/fetch_weights.py` (new spike tags `e18`, `e19`) and the TTS packages into `trainers/.venv`
(the one venv with the ROCm torch beside the engine's — it becomes the *tools* venv; no new venv). Losers deleted. VACE fetched only on E19's
NO-GO.

## 3. Design (built after the spikes, to their winners)

### 3a. Extend and the chain (CN1)
`I2V.extend_from: {clip_id, overlap}` — the previous clip's last `overlap` frames (A: 9 for LTX; B: 1 for Wan) are the new clip's lead-in;
`prepare_i2v` uploads them as a frame sequence (A) or the last frame (B); the new clip's record carries `chained_from` and `overlap` and
lineage to the previous clip; the Episode lane, when two chained clips sit back to back, **welds the join at export** (RIFE bridging frames
on the overlap, flagged in the export log) — the masters stay what the engine made (house rule 4). Animate: *Extend ▶* on a clip (11 §3d)
pre-fills the Inputs with the lead-in and the previous prompt; the transport shows the chain (clip 1 › 2 › 3). Beats past the first segment
land in the segment that holds their frame (the chain's frame arithmetic in `timelines`-like helpers, pure, tested).

### 3b. Voice (CN2)
A new asset kind `audio` (WAV masters, an Opus proxy, waveform thumbnails; the Catalogue's tile and the Inspector's player), a `voice`
record (`story/voices/<id>.json`: tier, model, reference clip, consent note, language) and the `tts` job (`kind: tts`: text, voice id, language,
speed; the draft tier on the CPU, the cloning tier with the engine stopped) placed on the Flow node's line (`FlowLine.audio_asset_id`); the
node Inspector's *Voice ▶* per line and *Voice all lines*; the Episode's FCPXML / EDL gain an audio lane from the nodes' lines at their
ticks, the SRT unchanged. Loom R95: voice is per node line, never a project-wide track.

**Built 2026-10-15 (CN2, journal).** `AssetKind` + `audio` (a 16-bit WAV master, `duration_s` probed at ingest, the waveform drawn as the
thumbnail — no Opus proxy: a line is a few hundred kB and the browser plays the WAV; the Catalogue's 🔊 badge, Type · Audio, the
Inspector's `<audio>` player; WAV / FLAC importable as a recorded reference). `orchestrator/loom2/voices.py`: `VoiceRecord` in
`story/voices/<id>.json` (draft: one of ten Kokoro voices, English only; cloning: the reference asset of 3–10 s, its transcript, the
speaker and the **required** consent note — one sentence each at creation and submission), the `tts` recipe (`voice_id`, `tier`
stamped from the record and checked against it, `language`, `speed`, `items` [{text, node_id, index}]), the job running
`voices/tts.py` in `voices/.venv` (`Settings.voices`) with its lines on the job card and its log in `state/logs/tts-<job>.log`, the
cloning tier behind `plan().gpu` (the engine stopped, 2.6 GB), every line an audio asset (lineage `voice-clone` to the reference)
stamped on its line (`FlowLine.audio_asset_id` + `audio_text`; a changed text shows the ▶ as stale; a client patch that never saw the
stamp keeps it on an unchanged line). `Profile.voice_id`: a character's voice, which its lines take; the request's voice is the fallback
for a speakerless line (*Voice all lines*: one job per voice) and the choice for a single line. Routes `GET/POST /story/voices`,
`GET/PATCH/DELETE /story/voices/{id}`, `POST /story/flow/nodes/{id}/lines/{i}/voice`, `POST /story/flow/nodes/{id}/voice`;
`/capabilities.voice` (the tiers with their figures, whether the models are cached, the voices, the languages). The exports: the
SRT's line layout (`timelines.line_spans`) places each voiced line as an FCPXML connected audio clip on lane −1 and an EDL `AX` event;
the reply counts them. UI: the Cast Inspector's Voice block (*speaks with*, *New voice…* with the tier's form and estimate, *Delete the
voice*), the Flow Inspector's ▶ / 🎙 per line, the fallback voice and *Voice all lines* (also in the node's right-click menu).
**One finding:** the ROCm wheel's OpenBLAS has 100 ms cliffs on small threaded multiplies — a 2 s Kokoro line took 7–8 s at 4–16 threads
(E20's 13 s outlier) and 0.8 s at one; the draft tier runs on **one CPU thread** (0.34 s per second of speech).

### 3c. Lip-sync (CN3)
The `lipsync` job (`kind: lipsync`: shot id + version, the frame (the version's frame or the profile's hero), the line's audio asset, the
method from E18) → a **take** on the shot version (SY2's takes: `kind: clip`, `lipsync: true`, lineage to the frame and the audio) — never an
edit of an existing clip; the Shots tab's *Lip-sync ▶* with the line / voice picker on a version whose node has lines; the take's clip is
muxed with the audio (the proxy carries it; the master stays PNG + WAV). FaceSim against the hero on the take (advisory, as 18 §3h).

### 3d. Pose-driven shots (CN4)
`StageShot` clip methods gain `animate` (Wan2.2 Animate *Move*: the Stage's pose pass + the shot's reference — the Cast hero through the
camera's "character" binding, or the version's frame) beside `guided` (LTX IC-LoRA); the Shot tab's method picker with E19's measured
seconds; the result lands as a take as ST4's do. `WanAnimateToVideo.continue_motion_max_frames` for a chain of pose-driven segments (E17 C).

### 3e. Data and API (sketch; the slices fix them)
`I2V.extend_from`, `ClipRecord.chained_from / overlap`, `AssetKind` + `audio`, `story/voices/`, `FlowLine.audio_asset_id`, `TTS` / `Lipsync`
recipes with `plan().engine` False and `plan().gpu` per tier, `ShotTake.lipsync`, `StageShot.method = "animate"`; routes `POST /story/voices`,
`POST /story/flow/nodes/{id}/lines/{i}/voice`, `POST /story/shots/{id}/versions/{v}/lipsync`, `POST /clips/{id}/extend`; `/capabilities.voice`
(tiers, languages, seconds) and `.lipsync` (method, seconds); the export's audio lane. Every field through `scripts/settings_audit.py`.

## 4. Slices

| Slice | What | Days |
| --- | --- | --- |
| **E20 · E17 · E18 · E19** | the spikes (§2) | 1 + 2 + 2 + 2 |
| **CN1 · Extend** | `extend_from`, the lead-in upload, the chain record and lineage, Animate's *Extend ▶* and the transport's chain, beats across a chain, the Episode's seam weld at export; tests (the fake engine; the chain arithmetic), the smoke scenario, the rig | 3 |
| **CN2 · Voice** ✓ 2026-10-15 | the `audio` asset kind with player and waveform, the `voice` record, the `tts` job (two tiers), the Flow line's *Voice ▶*, the Episode's audio lane; tests (a fake TTS), smoke, rig | 4 |
| **CN3 · Lip-sync** | the `lipsync` job to a shot take, the Shots tab's verb and picker, the muxed proxy, FaceSim advisory; tests, smoke, rig | 3 |
| **CN4 · Pose-driven shots** | the `animate` clip method on the Stage's pose pass with the Cast hero, the Shot tab's picker; tests, smoke, rig | 3 |
| **CN5 · Acceptance and docs** | `scripts/cn_acceptance.py` (a chain of three, a voiced talking take, a pose-driven shot, the Episode export with audio and welded joins — through the app on the rig); 11 / 16 / 17 updated, D87 closed | 2 |

≈ 22 d. Gate: D87 approved; each spike's GO before its slice (E17 → CN1, E20 → CN2, E18 → CN3, E19 → CN4); CN2 before CN3.

## 5. Tests and acceptance

- **Offline:** the chain arithmetic (beats across segments, overlaps), `extend_from` through the fake engine (the lead-in uploaded, the record
  linked), the `tts` job on a fake synthesiser (a WAV of the right length), the `lipsync` job on the fake engine (a take with lineage to the
  frame and the audio, the proxy muxed), the `animate` method's graph (parity snapshot), the export's audio lane in the FCPXML / EDL, the
  audio asset kind end to end (ingest, proxy, thumbnail, delete), every new route and capability (snapshot, audit).
- **Smoke:** "a chain", "a voice", "a talking take", "a pose-driven shot" on the fake engine and the fake synthesiser, both variants.
- **Rig (`scripts/cn_acceptance.py`):** a three-segment chain of Mara (E16's LoRA via `@Mara`) with the seam score and FaceSim at both ends;
  a Flow line voiced in the draft and the cloning tier; the talking take on a shot (the mouth-motion proxy ≥ 0.5, FaceSim ≥ 0.45); a shot
  performed from a Stage pose pass (PCK ≥ 0.8); the Episode exported with the audio lane and the welded joins, imported in Resolve by the author.

## 6. Defaults to approve (D87)

1. **The four spikes first**, in the order E20 → E17 → E18 → E19; a spike's NO-GO drops its slice from the wave and is recorded, the wave
   goes on with the rest.
2. **Downloads** as listed in §2 (≈ 38 GB, Apache-2.0 / MIT; VACE only on E19's NO-GO), through `scripts/fetch_weights.py`; losers deleted.
3. ~~The TTS packages go into `trainers/.venv`~~ **The TTS packages have their own venv `voices/.venv`** (E20: Qwen3-TTS pins transformers 4.x, ai-toolkit 5.5.3 — they cannot share one; the ROCm torch wheels beside the engine's); no change to the engine venv. The cloning tier and the GPU lip-sync methods run with the engine stopped, as training does; the draft tier on the CPU
   beside a running engine.
4. **A chain is N clips** with `chained_from` / `overlap` links and native fps; the join is welded by the Episode at export (RIFE), never in
   the masters; the first segment's model decides the chain's model.
5. **Lip-sync is a take** on a shot version, from the version's frame (or the hero) and a line's voice clip; never an edit of a clip.
6. **Voice is per Flow node line** (loom R95), two tiers: draft (fixed voices, CPU) and cloning (a 3–10 s reference of the author or a
   consenting speaker, recorded on the `voice` record); the Episode's exports carry one audio lane from the lines.
7. **Pose-driven shots take loom2's own rendered pose pass** (no DWPose node); *Mix* (replacing a person in a real video) stays out.
8. **Both variants:** S2V, Animate, Kokoro, Qwen3-TTS, Chatterbox are Apache-2.0 / MIT; LTX paths keep the roster's tags.
9. **Out (§1):** camera-control LoRAs, InfiniteTalk's video-to-video dubbing, singing, multi-speaker clips, the audio mix beyond one lane,
   lip-sync of clips not made here.
