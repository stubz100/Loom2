# proto01_animate · animation from clay — documents

Status: **proposal for the author to refine, 2026-10-17; revised the same evening after the author's six notes** (01 §8). Nothing here
is decided or built. The direction is recorded as a D-number
only after the author's review and after the spikes in 02 §2 (the house rule: a change in direction is a decision, written before the
work).

The idea, in the author's words (2026-10-17): *"create animations out of the clay dummies … use that animation along with the single
character image as an input of wan-animate and create very precise movement and camera control, then layer and blend them together."*

| # | Document | What it holds |
| --- | --- | --- |
| [01](01-clay-animation.md) | **The pipeline** | the author's eight-step workflow, reviewed step by step; the motion library; the refined pipeline; what exists in loom2 today and what is new; the measurements this rests on; risks; open questions, incl. §9 detailed and non-human dummies |
| [02](02-implementation-plan.md) | **The implementation plan** | a licence check for the motion (the CC0 starter set fetched), spikes first (E23a frame rate and weld, E23b Move vs Replace, E24 the post-processing in three stages; E25 hands in the guide, E26 a non-human performance), the decision gate, nine build waves (CA0–CA8) with acceptance bars, estimates, the rig runs |
| [03](03-image-and-animate-suites.md) | **Image and Animate, and an animation editor** | accepted as D95 (2026-10-18) except the preview route; the author's direction: three top tabs (Story · Image · Animate); Generate → Image with Edit in place; Stage moves into Animate, which takes Generate's one-column layout with one timeline and a three-level viewer (Clay · Performance · Final); an animation (compositing) editor on EffectCraft's engine (reviewed: a Rust After Effects, MIT/Apache, alpha; its egui UI not reusable); a UI/UX review before and after the build; waves UX0, IM1, AN1, E27, AE1–AE5, UX9 |
| [04](04-catalogue-for-making.md) | **The Catalogue for the making suites** | ideas mocked up (2026-10-18): C1 a Bin inside Image and Animate, C2 work made for a shot landing on an automatic shot page with lanes, C3 every object an item (stages, motion, compositions, layers, characters, voices), C4 lineage across media; C5–C7 smaller; a suggested order |
| [05](05-flow-nodes-as-shot-recipes.md) | **Story Flow: every node a shot recipe** | the author's idea (2026-10-18) reviewed: each Flow node a ≤ 30 s shot whose recipe (C4 as a plan) combines the elements into a take, ComfyUI-like (stale steps re-run); the nodes along a route make the cut, finished in a FilmCraft-like editor; naming options, the model, how the suites fit, waves RC0–RC4 |

Background reading, in this order:

- [16 · the Stage suite](../proto01/16-ui-suite-stage.md): figures, poses, cameras, keyframes, passes, the clip methods.
- [19 · continuity and voice](../proto01/19-continuity-and-voice.md): E17 (extending clips), E19 (Wan Animate driven by a Stage pose pass).
- The journal of 2026-10-17 ([90](../proto01/90-journal.md)): D93 (Cast ↔ subjects ↔ Stage figures), E21 (two characters by layers),
  D94 (two-shots as one still animated once), E22 (complex action: one clip takes turns, layers act at once but cannot touch).
