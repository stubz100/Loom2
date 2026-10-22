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
| **C3** the shot, LTX-2.3 locked to its depth, 0.35 | `in_c.mp4` → `c3a.mp4` | flicker 0.98 (0.81) · **detail 740 (1622, much softer)** · identity min 0.09 (0.22) · shadows 1.01 · SSIM 0.837 · **2 min** |
| C3 at 0.55 | `in_c.mp4` → `c3b.mp4` | flicker 0.93 · detail 537 · identity min 0.02 · shadows 1.02 · SSIM 0.785 · 1 min |

- Play each pair side by side at 2×. **Do you see any gain at all** — a cleaner coat, a steadier face, less shimmer — or only a
  slight softening? `c3a.mp4` is the one to judge by eye: the structure holds (the depth pins it), but the surfaces are repainted
  smooth and the faces change.
- `sheet.jpg`: frame 40 of the C3 arms around Mara (the earlier sheet of A2 / C1 was overwritten by the second run; the mp4s stay).

## 2. What it means (≈ 1 min)

- Against the bar of 02 §3 (better detail, identity or light *and* no worse stability *and* faithful): **the low-expert pass fails on
  every count** — it softens, it adds background shimmer, it drifts the face, it keeps the shadows, and it costs ≈ 15 min per 5 s of
  shot. The best post in this family is **none**. The slice is worth having: it rules the cheapest idea out with numbers.
- **C3 ran the same evening** (journal 2026-10-21 20:12): LTX-2.3 with its IC-LoRA on the shot's own Stage depth (the layers' depth
  passes composed), over the flattened clip at 0.35 and 0.55 of the distilled 8-step schedule — fast (2 min, 1 min) and the structure
  pinned, but it repaints the surfaces smooth (detail 1622 → 740 / 537), changes the faces (identity 0.22 → 0.09 / 0.02) and drifts from
  the input (SSIM 0.84 / 0.78). **Out** at these strengths; a lower one would only do less of the same.
- **What the two slices say together:** every whole-clip re-draw by a video model — Wan's expert, LTX locked to depth — costs more than it
  gives on a Move layer at 832×480. The quality levers are upstream: the generation's own preset and size, and close shots where the face
  is large. The arms left (02 §3): **A3**, a face-crop refine with Klein 9B and the character's references (per frame; flicker the risk;
  pointless on a 20-px face — it needs a close shot, as E29b does); **A5**, keyframes refined and propagated (needs optical flow, which the
  venv does not have); **A6**, the healing patch over a region (a repair tool, not a pass). The proposal for the post stages' decision:
  **no pass by default; the final is the assembly + RIFE (B1, D102); A6 as a tool on demand later; A3 measured on a close shot with
  E29b.**

## Notes

| Check | Answer |
| --- | --- |
| Any gain visible in a2a / c1a / c3a over the input? | **a2a / a2b and c1a / c1b improved Mara's hands; the c3 clips introduce a lot of visible distortion — for creative upgrades only** (the author, 2026-10-21) |
| The post stages: no pass by default (assembly + RIFE), A6 as a tool later, A3 on a close shot with E29b — agreed? | **amended → D118**: post-processing attached to each layer (Clean up = the low-expert pass, Creative = the depth-locked LTX pass, off by default), or processing layers over the stack below; the face pass with lip-sync as a pass too |
