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
| [05](05-flow-nodes-as-shot-recipes.md) | **Story Flow: every Shot node a recipe** | accepted as D96 (2026-10-18): Shot = Flow node (option B), one camera, ≈ 30 s guideline, recipe graph in the Flow and in Animate, every important part a step; the author's idea reviewed: each Flow node a ≤ 30 s shot whose recipe (C4 as a plan) combines the elements into a take, ComfyUI-like (stale steps re-run); the nodes along a route make the cut, finished in a FilmCraft-like editor; naming options, the model, how the suites fit, waves RC0–RC4 |
| [06](06-continuity-across-shots.md) | **Continuity across Shots** | options (2026-10-18): O1 a Scene record Shots link to, O2 Shot templates, O3 linked / independent copies, O4 locking the look when generating, O5 a continuity check, O6 matching in the cut, O7 state over story time; a suggested combination |
| [07](07-build-order.md) | **The build order** | one list for 02, 03, 05 and 06, UX0 first; the author's rules (one GPU job at a time, everything kept in the project, voice only, small testing documents, CC0 motion for tests) |
| [08](08-testing-ca1.md) | **Testing CA1** (for the author) | a Mixamo clip from the local folder, a walk along a path into a turn and a point in under 2 min, the Detailed level |
| [09](09-testing-e23a.md) | **Looking at E23a** (for the author) | F16 + RIFE or F24 in compare.mp4, the joins while walking and in a still hold (Q20) |
| [10](10-testing-e23b.md) | **Looking at E23b** (for the author) | Move against Replace in compare.mp4: the light, the black left around Mara, the joins (Q21) |
| [11](11-testing-ca1b.md) | **Looking at CA1b** (for the author) | the skeletons fitted to the characters: before / after on E23b's Move shot |
| [12](12-testing-e23c.md) | **Looking at E23c** (for the author) | the white set: grey · Stage's shadows · the model's shadows in compare.mp4, the feet ×0.85 |
| [13](13-testing-e23d.md) | **Looking at E23d** (for the author) | a dummy shaped like the character: its shadows against the dummy's, a card's and the white set's |
| [14](14-testing-e23e.md) | **Looking at E23e** (for the author) | shadows that start at the feet: the shadow moved, Replace in the proxy, the character nudged (anchor pins) |
| [15](15-testing-e28.md) | **Looking at E28, E28b and E28c** (for the author) | props: the chest slid, the door opened, the mug in her hand (P1 / P2 / P3); the room cleaned up (D108); props as 3D models, rendered or drawn on (D109) |
| [16](16-props-and-scene.md) | **Props like characters, the scene in 3D first** (D108–D110) | the build: PS1 Props tab · PS2 the prop's 3D model · PS3 props in Animate · PS4 the 3D scene · PS5 the final shot (CA2) |
| [17](17-testing-props.md) | **Trying the props and the 3D scene** (for the author) | make a prop and its 3D model in Story · Props; build a lit scene in Animate with props, figures, a light and a camera move |
| [18](18-testing-final-shot.md) | **Looking at the final shot** (for the author) | E23's shot made through loom2's own path: layers, plate, characters, mattes, assembly (D111) |
| [19](19-testing-e27.md) | **Looking at E27** (for the author) | the final shot as an EffectCraft composition, edited and rendered back; where to finish it (Q24, D113) |
| [20](20-animation-editor-build.md) | **The animation editor's build** (D114) | phase 4 cut into steps: AE1 the composition (pin, client, record, `comp_render`), AP1 thin then full, AE2, AE3; the first slice; what E27 settled |
| [21](21-testing-final-level.md) | **Trying the Final level** (for the author) | a final's composition opened in Animate, scrubbed, played from the cache, edited (the layer's editor under its row: properties, masks drawn on the frame, effects; the lanes), rendered to a clip; revised after the first look (UX9 U1–U3) |
| [22](22-testing-expand.md) | **Trying Expand from Image** (for the author) | D115: a character's coverage expanded with the poses picked as icons; the images as its candidates |

Background reading, in this order:

- [16 · the Stage suite](../proto01/16-ui-suite-stage.md): figures, poses, cameras, keyframes, passes, the clip methods.
- [19 · continuity and voice](../proto01/19-continuity-and-voice.md): E17 (extending clips), E19 (Wan Animate driven by a Stage pose pass).
- The journal of 2026-10-17 ([90](../proto01/90-journal.md)): D93 (Cast ↔ subjects ↔ Stage figures), E21 (two characters by layers),
  D94 (two-shots as one still animated once), E22 (complex action: one clip takes turns, layers act at once but cannot touch).
