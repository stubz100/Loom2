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
| 3 | **Spikes**, one at a time | **E23a** frame rate and seamless joins (D102) → **E23b** Move vs Replace (D103) → **CA1b** the skeleton fitted to the character (D104; SDPose at casting, the body's neck / hands / feet, the neck point and the foot markers fixed) → **E23c** the white set (the author's: floor and blocks kept white in a Move layer for contact and shadows) → **E28** props → **E29** lip-sync → **E25** hands in the guide → **E27** the EffectCraft preview server → **E24** post-processing (E26 only if creatures are wanted) | yes, serial | ≈ 8 |
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

## Status at 2026-10-20 17:12 (D114) — what the order above became

The table above is the plan of 2026-10-18. Three days of building changed its shape: phase 5 was largely built early under D110 and D111
(the author's direction on props and the 3D scene, doc 16), phase 4 had not started, and two spikes were never run. This section is the
truth from here; the table above stays as written.

### Delivered against the plan

| Phase | Planned | Delivered | Still open |
| --- | --- | --- | --- |
| 0–2 | UX0 · IM1 · AN1 · RC0 · CA0 · CA1 | all built and rig-checked (D99, D101, D104); UX0 and CA0 accepted by the author | — |
| 3 · spikes | E23a → E23b → CA1b → E23c → E28 → E29 → E25 → E27 → E24 | E23a–e, CA1b, E25, E28 / E28b / E28c, E27 (D102–D113) | **E29 lip-sync and E24 post-processing not run** — moved before AE4 |
| gate | a D-number per group | rate and joins D102 · mode D103 · shadows D105–D107 · props D108–D110 · the preview route D113 | lip-sync and the post stages: undecided until E29 / E24 |
| 4 · the editor | AE1 · AP1 · AE2 · AE3 | nothing | **the whole phase — starts now (D114)** |
| 5 · the clay pipeline | CA2 → CA6, AE4, AE5 | built as **PS1–PS5** (doc 16), see the mapping below | CA3's depth-guided plate for large moves · CA5's seam repair (W3) · CA7 / AE4 (wait E24) · AE5 |
| 6 · review | UX9 | begun 2026-10-21 with the author's look at 21: U1–U3 (journal 2026-10-21 13:58), U4–U7 (D116, journal 2026-10-21 16:42); the ? sweep over the whole app (journal 2026-10-21 18:24) | 15, 17, 18 closed by the author (D117); 21's second look owed; the rest of the register after it |
| 7 · Story pass | RC1–RC4 · O1–O7 · C1–C7 | RC0 only; the author chose C4 | all of it |

### The mapping: 02's CA waves → 16's PS steps

| 02 wave | Where it was built | Not covered |
| --- | --- | --- |
| CA2 · layers and light | PS1–PS4 (D110): Cast props with 3D models, bound in Animate; LightSpec lights and the ambient; the viewport environment; PS5a (D111): the scene split into layers with Stage's passes | a prop parented to a hand (Q23) |
| CA3 · the plate | PS5b: the Klein still of the bare set, projected by Stage along the camera path | the depth-guided plate video for large camera moves |
| CA4 · the batch planner | PS5c: `plan_batches` (77 frames, 5 carried, the 4k + 1 grid) | the plan shown with its cost; staging |
| CA5 · layer jobs | PS5c: chained Wan Animate runs per character, a re-take with a new seed | re-take a batch and the ones after it; the W3 healing patch at a seam |
| CA6 · assembly | PS5d mattes + PS5e `assemble_final` (depth order, contact offsets, RIFE) — the automatic first composite (D112) | — (hand finishing is the editor's) |
| CA7 · the final | — | waits E24; becomes AE4 |
| CA8 · UI | the final's panel in Animate (PS5f slim) | the rest is the editor (AE2) |

### The order from here

| # | Phase | Waves | GPU | Days |
| --- | --- | --- | --- | --- |
| 4 | **The animation editor** (D114) | **AE1** the composition (the pin and its build script; the `.ecproj` record written from a final and from a single clip; `comp_render` through the CLI) → **AP1** the preview server (thin first: start, frames over loopback, the D97 rule; then the tiers, caches and the chip) → **AE2** viewer and timeline → **AE3** effects and colour | AP1, AE3 rig checks | 16–21 |
| — | **The author's looks** | docs 15, 17, 18, 19 — before AE2's viewer is designed (Q22, Q23) | no | ½ h |
| 6 | **Review** | **UX9** | headed checks | 1–2 |
| 3b | **The two spikes left** | **E29** lip-sync (ran 2026-10-21: L1 out, L2 keeps the pose — Q25 for the author, doc 23) → **E24** post-processing (two slices ran the same day: the low-expert pass and the depth-locked LTX pass are both out, doc 24; the proposal: no pass by default, A3 on a close shot with E29b), then their D-number | yes, serial | ≈ 2.5 |
| 5b | **The pipeline's rest** | **AE4** AI passes on layers (CA7) · **AE5** the output as a take · CA3's depth-guided plate · CA5's W3 repair | yes | 8–11 |
| 7 | **Story pass** | RC1–RC4 · O1–O7 · C1–C3, C5–C7 as the author picks | rig checks | 15–20 + RC4 |

**The first slice of phase 4** is AE1 plus a thin AP1: the rig's final shot opened in Animate and scrubbed there, before any editing control
exists, so the viewer's feel can be judged early. The steps are in [20](20-animation-editor-build.md).

### What the review of 2026-10-20 noted (journal 2026-10-20 17:12)

- The cost per shot is real: the 5 s two-character shot took ≈ 13 min of GPU (two Wan Animate batches per character at 5–6 min each); a
  30 s shot with two characters is ≈ 80 min before any post stage.
- The `open` variant is drifting to second class (no image → 3D for props, Q22; BiRefNet for mattes; clay stand-ins): within D26, but
  each step widens the gap without a decision saying so.
- EffectCraft is alpha (v0.12.0): the pin and the build script contain it; its `.ecproj` format is the editor's foundation.
- Two assemblies will exist (PS5e's automatic composite and the editor's composition): one must be the reference the other derives from.
- Loose ends: the Wan chain's deprecated `ImageBatch` node; Wan Animate's non-determinism at a fixed seed; Q15 and Q18 untouched since
  the first week; `engine/spikes/out` large and holding losers.
