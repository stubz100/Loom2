# 09 · Suite A — Generate (FLUX.2 text-to-image with JSON prompting) — UI document

Status: proposed; approval gates M3. Frame: 07. Models and prompting rules: 04 §3. Engine: 06 §3.

## 1. Purpose
Produce starting images with FLUX.2 (Klein tiers for iteration, dev for hero frames) using BFL's structured
JSON prompt, in batches, with optional reference images, streaming into the Catalogue with full provenance.

## 2. Layout

```
Rail: [Prompt] [Model] [Size & Batch] [References] [Presets]
┌────────────────────────┬──────────────────────────────────────────────────┬──────────────────┐
│ Panel · Prompt         │ Strip: show ◉ this batch ○ session ○ all   grid|loupe|compare  zoom │ Inspector      │
│ ◉ Tree ○ JSON ○ Text   ├──────────────────────────────────────────────────┤ Image · Params · │
│ scene ______________   │ ▾ Batch 14:02 · klein-9b · 8 · 4 steps · 1024²    │ Lineage          │
│ subjects (2)   [+]     │ ┌────┐┌────┐┌────┐┌────┐┌──62%┐┌ ░░ ┐┌ ░░ ┐┌ ░░ ┐  │ [thumb]          │
│  ▸ 1 description…      │ │    ││    ││    ││    ││ prev││    ││    ││    │  │ seed 8812        │
│    position · action   │ └────┘└────┘└────┘└────┘└─────┘└────┘└────┘└────┘  │ 6.4 s · 1024²    │
│    pose ▾ · color_match│ ▸ Batch 13:40 · flux2-dev · 4 · 8 st · 768²  (cover)│ prompt diff ▸    │
│  ▸ 2 …                 │                                                  │ ───────────────  │
│ style ______________   │                                                  │ Keep ✓ Reject ✗  │
│ color_palette ■ ■ ■ [+]│                                                  │ Use as reference │
│ lighting ___________   │                                                  │ Variations (4)   │
│ mood · background      │                                                  │ Send to Edit     │
│ composition            │                                                  │ Send to Animate  │
│ camera ▸ angle ▾ lens  │                                                  │ Re-run · Pin     │
│   dof · f-number · dist│                                                  │                  │
│ ── 64 words · OK ──    │                                                  │                  │
│ Preview (dev: JSON)    │                                                  │                  │
│ {"scene":"…",…}        │                                                  │                  │
│ [ Generate 8 ▶ ] ~52 s │                                                  │                  │
└────────────────────────┴──────────────────────────────────────────────────┴──────────────────┘
Dock: Running klein-9b 5/8 ████░░ · Queued 1 · Recent
```

## 3. Panel tabs

### 3a. Prompt
- **Tree** (default): form over the BFL schema (04 §3c). Sections: `scene` (textarea), `subjects[]` (cards
  with description, position, action, pose, `color_match`; add/remove/reorder; pose and position offer picker
  chips from loom's directive vocabulary: angles ¾-left…, shot sizes, framing), `style`, `color_palette`
  (hex swatches with a colour picker; hint "bind colours to objects in subject descriptions"), `lighting`,
  `mood`, `background`, `composition`, `camera` (angle picker, lens, depth of field, f-number, distance).
  Suggestion chips per field (lighting: "golden hour rim light", camera angle: "low angle"); free text always
  allowed. **Word counter** with the 30–80 ideal band and a warning above ~120 (token budget 512).
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
  3–4.5, sampler `res_multistep` + `sgm_uniform` default (the author's working ComfyUI setting). Advanced
  disclosure: sampler, scheduler, Turbo LoRA toggle (dev), shift.
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

### 3d. References (FLUX.2 unified editing)
Up to 4 (Klein) / 10 (dev) slots; drop from Catalogue, Edit, or OS. Each slot: thumbnail, order number (the
prompt refers to "reference image 1"), optional note, remove. Token-cost hint ("a 1024² reference ≈ 4 096
tokens; references are downscaled to ≤ 1024² by default", toggle). Klein 9B-KV is auto-suggested when
≥ 2 references are present.

### 3e. Presets
Save/load the whole Panel state (prompt + model + size) as named presets; "last used" restored per project.
A **prompt snippet library** (style blocks, lighting blocks, camera blocks) inserts into tree fields.

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

## 9. Data and API
`POST /jobs` with `T2I{model_id, prompt: {mode: tree|json|text, tree?, json?, text?}, serialized, width,
height, seeds[], steps, guidance, sampler, scheduler, turbo_lora, refs: [asset_id|blob], ref_max_px}`;
`GET /capabilities` for per-variant controls; WS `job.progress` (step, preview), `asset.created`.
Manifests record the exact serialised prompt and the compiled engine graph hash.

## 10. Acceptance checklist
- [x] Tree ↔ JSON round-trip is lossless for schema fields; preview shows the exact string sent — `treeFromJson` /
  `cleanTree` in the store, `/recipes/preview` returns `serialized_prompt` (2026-10-05).
- [~] Klein receives prose, dev receives JSON (tested: `serialize_prompt`); the 10-prompt bench ran on dev Turbo
  through the API (10/10 done, mean 45 s at 960×544) — adherence scoring by eye is pending.
- [x] Distilled variants show fixed steps/CFG disabled with reasons; base variants enable CFG + negative — `effective_params`, acceptance checks.
- [x] A batch of 8 streams previews and lands 8 assets with seeds, params and lineage — `scripts/m3_acceptance.py` (17/17).
- [~] Reference slots work on dev (done 55.7 s ); Klein 4B/9B references wait for M5; the token hint is shown in the panel.
- [~] Missing weights → the primary action is disabled with the reason and a Fetch button opens Models; "after fetch the same job runs" is not automated yet.
- [~] Timings on the rig for dev recorded in the journal; Klein 4B/9B follow in M5.

## 11. Open questions
- Whether to expose per-subject "reference binding" UI (prompt convention only) or keep it textual.
- Upsample model: Qwen3-8B (already a Klein TE) vs Mistral GGUF (dev TE) for the LLM pass.
