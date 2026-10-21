# 24 · Looking at E24 — post-processing, the first slice (for the author)

About 4 minutes. Spike E24 (01 step 8, 02 §3) asks which post pass makes the performance the final without flicker, faithful, with the
shadows and light kept. Its first slice (journal 2026-10-21 20:00) measured the one mechanism both stages share — **Wan 2.2's low-noise
expert run over the clip as a video at a low strength** — on the PS5 rig's shot: Mara's performed layer (stage A) and the final assembled
afresh (stage C). Everything is under `engine\spikes\out\e24\`.

## 1. The clips (≈ 3 min)

| Pair | Files | The numbers (the baseline's in brackets) |
| --- | --- | --- |
| the layer, strength 0.10 | `in_a.mp4` → `a2a.mp4` | background flicker 0.33 (0.18, worse) · detail 2029 (2179, softer) · identity min 0.19 (0.20) · SSIM to the input 0.986 · **15 min** |
| the layer, strength 0.20 | `in_a.mp4` → `a2b.mp4` | flicker 0.30 (worse) · detail 1997 (softer) · identity min 0.14 (worse) · SSIM 0.980 · 16 min |
| the shot, strength 0.10 | `in_c.mp4` → `c1a.mp4` | flicker 1.36 (0.81, worse) · detail 1419 (1622, softer) · identity min 0.12 (0.22, worse) · shadows kept (0.99) · SSIM 0.941 · 16 min |
| the shot, strength 0.20 | `in_c.mp4` → `c1b.mp4` | flicker 1.37 · detail 1301 · identity min 0.14 · shadows 0.99 · SSIM 0.928 · 16 min |

- Play each pair side by side at 2×. **Do you see any gain at all** — a cleaner coat, a steadier face, less shimmer — or only a
  slight softening?
- `sheet.jpg`: frame 40 of each arm around Mara.

## 2. What it means (≈ 1 min)

- Against the bar of 02 §3 (better detail, identity or light *and* no worse stability *and* faithful): **the low-expert pass fails on
  every count** — it softens, it adds background shimmer, it drifts the face, it keeps the shadows, and it costs ≈ 15 min per 5 s of
  shot. The best post in this family is **none**. The slice is worth having: it rules the cheapest idea out with numbers.
- What is left to try, in order of promise (02 §3): **C3**, the structure-locked polish — LTX-2.3 with its IC-LoRA on the shot's own
  Stage depth sequence over the flattened clip at a low strength (a temporal model with the scene's structure pinned); **A3**, a face-crop
  refine with Klein 9B and the character's references (identity, per frame — flicker is the risk); **A5**, keyframes refined and
  propagated. Each is half a day with about an hour of rig time; they run next, one at a time.

## Notes

| Check | Answer |
| --- | --- |
| Any gain visible in a2a / c1a over the input? | |
| Run C3 and A3 next, or stop E24 here? | |
