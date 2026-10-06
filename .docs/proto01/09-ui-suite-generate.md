# 09 · Suite A — Generate (FLUX.2 text-to-image with JSON prompting) — UI document

Status: **implemented — M3 closed 2026-10-05**, Klein and the ComfyUI configuration surface added in M5 / 2026-10-06; amendments dated inline. Originally: proposed; approval gates M3. Frame: 07. Models and prompting rules: 04 §3. Engine: 06 §3.

## 1. Purpose
Produce starting images with FLUX.2 (Klein tiers for iteration, dev for hero frames) using BFL's structured
JSON prompt, in batches, with optional reference images, streaming into the Catalogue with full provenance.

## 2. Layout

```
Rail: [Prompt] [Model] [Size & Batch] [Presets]        (References live inside Prompt since 2026-10-06)
┌────────────────────────┬──────────────────────────────────────────────────┬──────────────────┐
│ Panel · Prompt         │ Strip: show ◉ this batch ○ session ○ all   grid|loupe|compare  zoom │ Inspector      │
│ ◉ Tree ○ JSON ○ Text   ├──────────────────────────────────────────────────┤ Image · Params · │
│ scene ___________ [✦]  │ ▾ Batch 14:02 · klein-9b · 8 · 4 steps · 1024²    │ Lineage          │
│ ▾ reference images 0/10│ ┌────┐┌────┐┌────┐┌────┐┌──62%┐┌ ░░ ┐┌ ░░ ┐┌ ░░ ┐  │ [thumb]          │
│  [1][2][3][4][5]…      │ │    ││    ││    ││    ││ prev││    ││    ││    │  │ seed 8812        │
│ SUBJECTS · optional [+]│ └────┘└────┘└────┘└────┘└─────┘└────┘└────┘└────┘  │ 6.4 s · 1024²    │
│  subject 1      remove │ ▸ Batch 13:40 · flux2-dev · 4 · 8 st · 768²  (cover)│ prompt diff ▸    │
│   description ___ [✦]  │                                                  │ ───────────────  │
│   position · action [✦]│                                                  │ Keep ✓ Reject ✗  │
│ LOOK  style _____ [✦]  │                                                  │ Use as reference │
│ color_palette ■ ■ ■ [+]│                                                  │ Variations (4)   │
│ lighting · mood … [✦]  │                                                  │ Send to Edit     │
│ CAMERA angle · lens [✦]│                                                  │ Send to Animate  │
│   dof · f-number · dist│                                                  │ Re-run · Pin     │
│ EXTRAS lead · negative │                                                  │                  │
│ ── 64 words · OK ──    │                                                  │                  │
│ Preview (dev: JSON)    │                                                  │                  │
│ {"scene":"…",…}        │                                                  │                  │
│ [ Generate 8 ▶ ] ~52 s │                                                  │                  │
└────────────────────────┴──────────────────────────────────────────────────┴──────────────────┘
Dock: Running klein-9b 5/8 ████░░ · Queued 1 · Recent
```

## 3. Panel tabs

### 3a. Prompt
- **Tree** (default): form over the BFL schema (04 §3c), in sections: `scene`; **reference images** (the slots
  of §3d, right under the scene because subject descriptions refer to "reference image N"); `subjects[]` —
  **optional, none by default** (2026-10-06): cards with description, position, action, pose, `color_match`,
  each removable; `style`, `color_palette` (hex swatches with a colour picker; hint "bind colours to objects in
  subject descriptions"), `lighting`, `mood`, `background`, `composition`; `camera` (angle, lens, depth of field,
  f-number, distance); lead text and the negative. **Every text field has one ✦ icon** (`ListPlus`) and no inline
  chips: the icon opens a menu with the built-in vocabulary for that field (loom's directives: angles, shot sizes,
  poses, lighting…), the user's own presets for that field, "Remove a preset ▸" and "Save current text as
  preset…" (an inline name box, no native prompt). Single-valued fields (lens, f-number, distance, depth of field)
  replace; the rest append with a comma. Free text is always allowed. **Word counter** with the 30–80 ideal band
  and a warning above ~120 (token budget 512).
- **JSON**: raw editor with validation against the schema (unknown keys allowed with a hint), pretty/compact,
  import from clipboard, "to Tree" (lossless for known fields).
- **Text**: plain prompt. Switching tabs never loses data; the active tab decides what is sent.
- **Serialisation preview** (read-only, collapsible): exactly the string the engine will receive — compact
  JSON for dev, **flattened prose for Klein** (ordered subject + action + style + context), per 04 §3c.
- **Negative prompt** field appears only for CFG-capable variants (Klein *base*); hidden with a reason otherwise.
- **Upsample ✨**: queues an LLM pass with BFL's upsampling system prompt; shows before/after; user accepts or
  discards. Never automatic.

### 3b. Model
- **Model** segmented, in build order (D21): **dev · JSON** (FLUX.2 dev — default, first-built, labelled slow)
  · Klein 9B / 9B-base / 9B-KV (later) · Klein 4B / 4B-base (later; default in the `open` variant). The variant
  select shows format (fp8 / GGUF Qn), licence badge, health (ready / fetch N GB). Models not yet wired are
  shown greyed with "coming in M5" rather than hidden, so the picker's final shape is visible from M3.
- **Sampling preset**: per variant from `/capabilities` — distilled: steps fixed (4) and CFG fixed (1.0), shown
  disabled with the reason; base: steps 20–50, CFG 3–5; dev: steps 8 (Turbo LoRA on) / 20–28 (off), guidance
  3–4.5, sampler `res_multistep` + `sgm_uniform` default (the author's working ComfyUI setting). **Sampler and
  scheduler lists are the engine's own** (45 / 9 in v0.38.2 and v0.39.0, served live by `/capabilities`), plus loom2's
  `flux2` scheduler = BFL's resolution-shifted sigmas (`Flux2Scheduler` through `SamplerCustomAdvanced`,
  `CFGGuider` when CFG > 1). A value the engine does not offer is an error in the preview, never a silent fall-back.
  Turbo LoRA toggle (dev) with its **strength**.
- **Advanced · ComfyUI model and decode settings** (disclosure, 2026-10-06 audit): **shift** (model default — FLUX.2
  2.02 — or `ModelSamplingFlux` base/max, resolution-dependent), **weight dtype** (`UNETLoader`: default /
  fp8_e4m3fn / fp8_e4m3fn_fast / fp8_e5m2), **text encoder device** (GPU / cpu, with E0's 170 s warning),
  **tiled VAE decode** (`VAEDecodeTiled`, tile size) for Full-tier headroom. Everything the UI shows is what runs:
  the preview echoes the effective values (`effective_params`) and the manifest records them. Post-MVP candidates
  that need a measured spike first: `EasyCache` / `LazyCache` step skipping, `PerturbedAttentionGuidance`,
  `SkipLayerGuidanceDiT`, `CFGZeroStar` / `CFGNorm`, `APG`, two-stage `KSamplerAdvanced`.
- **Seed**: random / fixed / increment; batch shows per-image seeds.
- **LoRA slots** (D25): the section exists in the Panel from M3 — up to 4 slots (roster `kind: lora` for the
  selected family, strength 0–1.5) — rendered disabled with "post-MVP" until loading is wired; the recipe and
  manifest already carry `loras[]`.

### 3c. Size & Batch
- Aspect from the project format by default (16:9); override presets (1:1, 3:2, 2:3, 9:16, 21:9) and custom
  sizes, always snapped to multiples of 16 within the model's 64 px – 4 MP range (capabilities).
- **Tiers** (D18, 04 §9c): **Thumb** 896×512 · **Draft** 1280×720 (default; dev defaults to 960×544) ·
  **Full** 1920×1088 → auto-crop to 1080 (Klein; on dev the UI proposes "Draft + Refine/Upscale in Edit"
  instead and warns about time). Each tier shows its token count and the measured time estimate.
- Count 1–8. **Estimate line** under the primary button: ETA from engine estimate × rolling measured average
  for this variant/size, and VRAM fit (green/amber/red).

### 3d. References (FLUX.2 unified editing) — inside the Prompt tab since 2026-10-06
Up to 4 (Klein) / 10 (dev) numbered slots in a compact grid directly under `scene` (also shown in the JSON and
Text modes); drop Catalogue tiles or press `R` on a selection. Each slot: thumbnail, order number (the prompt refers
to "reference image 1"), remove, move left; right-click: remove / move first / left / right / clear all. Downscale
select (≤ 512² / 768² / 1024² / original) with the token-cost hint ("a 1024² reference ≈ 4 096 tokens"). Klein 9B-KV
is suggested when ≥ 2 references are present.

### 3e. Presets
Save/load the whole Panel state (prompt + model + size) as named **panel presets**; "last used" restored per
project. **Field presets** (the former snippet library) are created from each field's ✦ menu and listed here
(field · name · text, remove); they are stored per project in `/snippets` with the field key
(`scene`, `subject.pose`, `camera.lens`, …).

Foot: **[Generate N ▶]** (primary, `Ctrl+Enter`); **Stage** (adds to `staged.json` without running, for
batching hero jobs overnight); the button is disabled with a reason when weights are missing (offers Fetch),
VRAM estimate is red, or the disk guard is at hard-stop.

## 4. Stage
- **Grid of this suite's results** grouped by batch (newest first); interim tiles show step progress and the
  engine's preview JPEG; finished tiles are catalogue assets (keyboard, states, verbs as in 08).
- Filter: this batch / this session / all Generate assets. View: grid · loupe · compare (same components as
  the Catalogue).
- **Pin**: a result pinned to the Strip stays visible while iterating (compare target or reference candidate).

## 5. Inspector
- **Image**: thumbnail, model/variant/format, seed, size, steps, guidance, time; verbs: Keep/Reject, Rate,
  Use as reference, **Variations (N)** (same prompt, new seeds), **Re-run** (identical), Send to Edit, Send to
  Animate, Delete.
- **Params**: the prompt as sent (JSON or prose) and a **diff against the current Panel** (what changed since);
  "Load into Panel" restores everything.
- **Lineage**: references used, children (edits, clips).

## 6. Workflows
1. **Iterate**: Tier Iterate → tree prompt → Generate 8 → triage on the Stage → pin the best → tweak fields →
   Generate again; the diff in Params shows what changed between batches.
2. **Hero**: switch to Hero tier (dev) with the same tree (serialised as JSON now) → 2 images at 0.5 MP → Stage
   for later or run → Send to Edit for refine/upscale.
3. **Reference-driven**: pin a hero → Use as reference → prompt "the same character as reference image 1,
   seen from behind…" → Klein 9B-KV.
4. **Re-use**: from the Catalogue, `Ctrl+R` opens Generate with the asset's parameters loaded.

## 7. States
Model loading (chip "loading klein-9b… 23 s" with the Stage still usable); first job after a model switch
shows a longer ETA; queue paused (banner); failed job (tile with error, "Open log", "Retry").

## 8. Keyboard
`Ctrl+Enter` generate · `Ctrl+Shift+Enter` stage · `Ctrl+J` focus JSON · `Ctrl+T` focus Tree · `Ctrl+S` save
preset · `P` pin selected · `V` variations · `Ctrl+R` re-run · plus the catalogue keys on the Stage.
All of these are registry commands (07 §3c) with buttons in the Panel (Generate, Stage, Save preset) or the
results grid's tile menu; reference slots have a right-click menu (remove, move first/left/right, clear all).

## 9. Data and API
`POST /jobs` with `T2I{model_id, prompt: {mode: tree|json|text, tree?, json?, text?}, serialized, width,
height, seeds[], steps, guidance, sampler, scheduler, turbo_lora, refs: [asset_id|blob], ref_max_px}`;
`GET /capabilities` for per-variant controls; WS `job.progress` (step, preview), `asset.created`.
Manifests record the exact serialised prompt and the compiled engine graph hash.

## 10. Acceptance checklist
- [x] Tree ↔ JSON round-trip is lossless for schema fields; preview shows the exact string sent — `treeFromJson` /
  `cleanTree` in the store, `/recipes/preview` returns `serialized_prompt` (2026-10-05).
- [~] Klein receives prose, dev receives JSON (tested: `serialize_prompt`); the 10-prompt bench ran on dev Turbo
  through the API (10/10 done, mean 45 s at 960×544); adherence checked by eye on the contact sheet (journal 16:1x): consistent character, literal text and bound colours in every frame.
- [x] Distilled variants show fixed steps/CFG disabled with reasons; base variants enable CFG + negative — `effective_params`, acceptance checks.
- [x] A batch of 8 streams previews and lands 8 assets with seeds, params and lineage — `scripts/m3_acceptance.py` (17/17).
- [x] Reference slots work on dev (done 55.7 s); Klein 4B/9B references arrived with the Klein graphs in M5 (D21, ≤ 4 refs on Klein); the token hint is shown in the panel.
- [~] Missing weights → the primary action is disabled with the reason and a Fetch button opens Models; "after fetch the same job runs" is not automated yet.
- [x] Timings on the rig for dev recorded in the journal; Klein 4B t2i 1280×720 measured 2026-10-07 on the v0.39.0 engine: 20.1 s (sampler 8.0 s, decode 5.4 s, text encode 5.3 s); Klein inpaint times are in the M5 entries.

## 11. Open questions
- Whether to expose per-subject "reference binding" UI (prompt convention only) or keep it textual.
- Upsample model: Qwen3-8B (already a Klein TE) vs Mistral GGUF (dev TE) for the LLM pass.
