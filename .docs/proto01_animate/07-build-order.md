# 07 · The build order — one list for 02, 03, 05 and 06

Status: **the plan, 2026-10-18.** It orders the waves of [02](02-implementation-plan.md) (the clay pipeline, CA), [03](03-image-and-animate-suites.md)
(the suites and the animation editor: UX, IM, AN, AE, AP), [05](05-flow-nodes-as-shot-recipes.md) (the shot-flow, RC) and
[06](06-continuity-across-shots.md) (continuity, O). The documents hold the content; this one holds the order.

**The author's rules for the whole plan (2026-10-18):**

- **The UI/UX review comes first.**
- **Strictly one job on the GPU at a time** (D97). Spikes and rig checks run one after another, never side by side; the preview server
  leaves the GPU while a job runs.
- **Everything is kept, inside the project directory.** Masters, layers, takes, start stills, compositions, and the preview's disk cache
  all stay in the project. A retention setting may come later.
- **Sound is voice only:** no music and no sound effects. The author's library at `D:\_soundPacks` is used only for testing if needed,
  never linked to a project or the repo.
- **Testing help from the author comes as small testing documents.** Each says what to click, what to look at and what to report.
- **Spikes and tests use CC0 motion only** (the Quaternius starter set). Mixamo's Additional Terms §1 forbid using Mixamo-derived data
  to "create, train, test, or otherwise improve" AI systems (01 step 5). The author's Mixamo clips are their own creative input at use
  time, never test data, and never in a LoRA's training frames.

## The order

| # | Phase | Waves | GPU | Days |
| --- | --- | --- | --- | --- |
| **0** | **UI/UX review** | **UX0**: the inventory for three tabs, wireframes of Image and Animate (column, viewer levels, timeline, Bin drawer, Graph view), the click paths; the author's corrections | no | 2–3 |
| 1 | **Re-house** what exists | **IM1** Image (Make ⇄ Edit, Edit's one column) · **AN1** Animate shell (Stage moves in, one column, one timeline and transport, Clay level, the Bin drawer C1) · **RC0** the recipe record (05) | headed checks only | 13–17 |
| 2 | **Foundations without the GPU** | **CA0** animation references and the body on the Cast sheet (characters and props) · **CA1** the motion library (FBX / glTF import, two-level dummy, root paths, foot lock) | rig check at the end | 8–11 |
| 3 | **Spikes**, one at a time | **E23a** frame rate and seamless joins → **E23b** Move vs Replace → **E28** props → **E29** lip-sync → **E25** hands in the guide → **E27** the EffectCraft preview server → **E24** post-processing (E26 only if creatures are wanted) | yes, serial | ≈ 8 |
| — | **Decision gate** | a D-number per spike group: rate and joins, mode and plates, props, lip-sync, the preview route, the post stages | — | — |
| 4 | **The animation editor** | **AE1** the composition · **AP1** the preview server and its quality controls · **AE2** viewer and timeline · **AE3** effects and colour | AP1, AE3 rig checks | 16–21 |
| 5 | **The clay pipeline** | **CA2** layers, light and props · **CA3** the plate (projection, depth-guided video) · **CA4** the batch planner · **CA5** layer jobs · **CA6** assembly into an AE1 composition · **AE4** AI passes on layers (CA7's post stages) · **AE5** the output as a take | yes, each wave's acceptance | 20–25 |
| 6 | **Review** | **UX9**: the paths in the built app; the author's testing documents; the register fixed | headed checks | 1–2 |
| 7 | **Story pass** | **RC1** the recipe graph (in the Flow and in Animate) · **RC2** the Shot node (Flow node + shot), templates (06 O2), linked copies within a scene with *Make independent* (O3) · **RC3** the cut from the Flow (voice only) · **RC4** the FilmCraft study, then the cut editor (with O6) | rig checks | 15–20 + RC4's build |

**Roughly 85–110 working days** before RC4's build. Phases 1 and 2 need no GPU beyond short headed checks, so they can be built while
the author reviews UX0's results. Phase 3's spikes are the only long GPU work before phase 5.

## Where each wave is described

| Wave | Document |
| --- | --- |
| UX0, IM1, AN1, E27, AE1–AE5, AP1, UX9 | 03 §6, §7 |
| CA0–CA7, E23a/b, E24, E25, E26, E28, E29 | 02 §3, §5 (with 01 for the reasoning) |
| RC0–RC4 | 05 §6 |
| O1–O7 | 06 §3, §4 |
| C1–C7 (Catalogue ideas) | 04 |
