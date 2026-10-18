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
| [03](03-image-and-animate-suites.md) | **Image and Animate, and an animation editor** | the author's 2026-10-18 direction: three top tabs (Story · Image · Animate); Generate → Image with Edit in place; Stage moves into Animate, which takes Generate's one-column layout with one timeline and a three-level viewer (Clay · Performance · Final); an animation (compositing) editor on EffectCraft's engine (reviewed: a Rust After Effects, MIT/Apache, alpha; its egui UI not reusable); a UI/UX review before and after the build; waves UX0, IM1, AN1, E27, AE1–AE5, UX9 |

Background reading, in this order:

- [16 · the Stage suite](../proto01/16-ui-suite-stage.md): figures, poses, cameras, keyframes, passes, the clip methods.
- [19 · continuity and voice](../proto01/19-continuity-and-voice.md): E17 (extending clips), E19 (Wan Animate driven by a Stage pose pass).
- The journal of 2026-10-17 ([90](../proto01/90-journal.md)): D93 (Cast ↔ subjects ↔ Stage figures), E21 (two characters by layers),
  D94 (two-shots as one still animated once), E22 (complex action: one clip takes turns, layers act at once but cannot touch).
