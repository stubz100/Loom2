# 05 · Story Flow: every Shot node a recipe

Status: **accepted as D96, 2026-10-18** (the author's answers in §7). Story is built after Animate (D95). The recipe record (RC0) comes
with Animate, because Animate's work writes it.

The author (2026-10-18), on idea C4 of [04](04-catalogue-for-making.md):

> *"I very much like the idea of C4, and it is also in line with our original story-flow idea. Each node in the Story/Flow should
> represent [a shot]: certain elements in combination defining a small shot (max 30 s perhaps), much like how ComfyUI works. These nodes
> in combination would build up the full movie, which is then finalized in a FilmCraft-like editor."*

And on the review: *"We should not sacrifice features for simplicity. Like in ComfyUI, an image generation would still require 4–5
components to connect on a workflow. We should also make sure every important part is taken care of by our shot-flow."*

## 1. The idea

There are three levels:

```
STORY FLOW — the story: what happens, in which order, with which branches
  [Start] ──▶ [Shot · Arrival 0:12] ──▶ [Shot · Mara and Ines 0:24] ──▶ ◇ Choice ──▶ [Shot · The door 0:08] ──▶ …
                                             │ open (in the Flow, or in Animate)
                                             ▼
INSIDE ONE SHOT — its recipe: the elements, and how they become a take (C4 as a plan, not only a record)
  Mara v1 ─▶ anim. ref ─┐                                 ┌─▶ keyframe stills ─┐
  Ines v1 ─▶ anim. ref ─┼─▶ Stage: set · figures · motion ┼─▶ plate ───────────┼─▶ performance (layers) ─▶ composition ─▶ finish ─▶ TAKE
  Lines ──▶ voice ──────┘        · camera                 └────────────────────┘                                              ✓ used
                                                                                                                                │
THE CUT — each Shot's used take rendered onto a video lane of the FilmCraft-like editor, where the movie is finished and rendered ◀┘
```

- **A Shot is a Flow node** of up to about 30 s (a guideline, §3), with **one camera** (§3). Its **recipe** combines the elements
  (characters, a place, lines, motion, a camera) into a take, through the clay pipeline's steps (01, 02).
- **The recipe works like ComfyUI.** It is a dataflow graph: every important part is a step you can see and set, and when an input
  changes, only what depends on it runs again. loom2 never uses ComfyUI itself (D2, D15).
- **The cut:** each Shot's used take is rendered onto a video lane of the cut editor, modelled on FilmCraft. The movie is finished and
  rendered there, as a backend job.

## 2. Why this is right

1. **One object instead of five.** Today a Flow node, a Story shot (versions, takes), Animate's For chip, the composition (03, AE1)
   and the lineage are separate records joined by ids. A Shot node with a recipe is the one thing they all describe.
2. **Lineage becomes a plan, so loom2 knows what is out of date.**
   - Change Mara's animation reference, and her keyframe stills, her layer, the composition and the take are marked stale. Ines's layer
     stays valid.
   - *Run stale* queues only what is needed, with the cost first (D79's pattern).
   - Today staleness exists only for a stage moving after its clip (17 §3c, D93). The recipe generalises it.
3. **It is the original loom's model** (`kb-storyboard01.md`):
   - a node owns its clip, built from segments with continuity *within* the node;
   - transitions *between* nodes;
   - versions with their own clips, and a finalize gate;
   - the render list picks a node version's clip.

   The clay plan's batches are "segments within a node".
4. **Animate is the Shot editor.** Its column (03 §4.2) is the recipe's steps in order. The graph (overview, stale marks) and Animate
   (the work) are two views of one recipe. No new application.

## 3. The decisions in detail

**The name (option B).**

- **The Flow node and the Story shot merge into one Shot.** A Shot node *is* a shot: its versions, frame, clip and takes as today
  (D93).
- The **Shots** tab becomes a list view of the Shot nodes.
- **Episode stays the cut.**
- Dialogue nodes keep their lines and are Shots too: a Dialogue is a Shot with lines.
- The logic nodes (Choice, Condition, Action, Hub, Jump, Comment) keep their meaning and have no recipe.

**ComfyUI's way of working, not ComfyUI.**

- The recipe graph is loom2's own, drawn with `@xyflow/react` like the Flow.
- Each step runs as loom2 jobs, with ComfyUI as the engine underneath.

**About 30 s is a guideline.** Past 30 s the Shot shows a warning; nothing is blocked. 30 s is 720 frames at 24 fps, 10 Wan Animate
batches per layer, and a composition that previews well (03 §5.2a). A longer beat is better as two Shots joined by a transition.

**One camera per Shot.** Cuts happen between Shots. A dialogue in shot / reverse-shot is several Shots, shown in the Flow as one
**scene group** (a frame around them) that shares the stage, cast and lines.

**Nothing is sacrificed for simplicity.** Every important part of making a shot is a step with its settings, as a ComfyUI workflow
needs its 4–5 connected components even for one image:

- **Templates** prefill a recipe: *Image to video* (a frame → a performance → a take), *Clay, one character*, *Clay, two characters*,
  *Dialogue with voice* (and lip-sync, experimental).
- **A template shows every step; it hides none.** Defaults come from the World and the project (D18 Draft first), and the step's
  settings are always one click away.

**Every important part, by step** (the coverage check for RC0 and RC1; each row lists what the step must expose):

| Step | Its important parts | Where they live today |
| --- | --- | --- |
| **Character** | the Cast version; the sheet (appearance, outfit, colours, marks); its references (a group, @mentions); its LoRA and trigger; its voice | Cast (D85, D93 B), LT (D86), CN2 |
| **Place / set** | the stage's set or a Cast place; the World style; the key light and time of day; the Look presets (lighting, mood) | Stage, World, D93 C7, D90 presets |
| **Lines** | speaker, text, voice (Kokoro / a cloned voice), the spoken audio and its timing | Flow Dialogue, CN2 (D87) |
| **Motion** | per figure: library clips, keys, root path, foot lock, trim / speed / blend | Stage ST4, CA1 |
| **Camera** | the camera's lens, keys and moves; the project format | Stage cameras, ProjectFormat |
| **Frame** (an image: the 4–5 components) | model and its preset; prompt (scene, subjects with their actions); references (slots, groups, mentions; bound per subject); Look (style, lighting, mood, camera angle); size / tier; LoRAs; encoder; seed and count | Image's Make column (D90–D93) |
| **Animation reference** | per character version: A-pose, 16:9, colours bound | CA0 |
| **Plate** | still, projection or depth-guided video; model; the World style | 01 step 4, CA3 |
| **Keyframe stills** | method (Exact pose / Clay); references; one per figure per batch (W2) | Stage Render, CA4 |
| **Performance** | method (image-to-video / pose-driven / depth-guided); model and preset (steps, CFG, shift); length and rate (F16 / F24); batches and weld (W1 / W2); mode (Move / Replace); prompt and negative; beats; seed | Animate, CN4, CA4 / CA5 |
| **Lip-sync** (experimental) | the line; the preset | D88 |
| **Composition** | layers, blend modes, mattes, masks, keys, effects and colour; the preview quality (AP1) | 03 AE1–AE3, AP1 |
| **Finish** | per layer: amount and model; the image stream; the polish; healing patches | 01 step 8, E24, AE4 |
| **Take** | render settings (quality, resolution, rate, motion blur, frame blending, colour depth); output modules; the take used; finalize (the format gate) | 03 AE5, 17 §3c |

Cross-cutting, on every step: its cost, its state (fresh / stale / queued / running / missing), its seed, and lineage stamps.

**The recipe graph opens in both places:**

- in the Flow, a Shot opens in place as its sub-graph, with *Run stale* and *Open in Animate*;
- in Animate, a *Graph* view sits beside the viewer's three levels.

The selection is shared: a step selected in the graph opens its section in Animate's column.

**The cut:**

- Each Shot's **used take is rendered onto a video lane** of the cut editor, in the order of a route through the Flow. A branching story
  gives one cut per route.
- When a Shot gets a new used take, its clip on the lane updates, and the cut marks it as changed.
- The movie is finished in that editor (transitions, audio, titles, grading) and **rendered as a backend job**.
- The editor is modelled on FilmCraft (RC4's study), which replaces today's single-lane Episode in the Story pass.

## 4. The model

**Records:**

- A shot version gains a `recipe`: `{template, steps: [{id, kind, ref | settings, inputs: [step ids], outputs: [asset ids], stamps:
  {input: revision}}]}`. It is written through `fsio` with `schema_version`.
- **Running a step writes its lineage edges.** C4's view is the recipe graph with its history.
- **Versions** stay the shot versions (D93): editing a recipe and running it makes the new version's takes.
- **Finalize** stays as it is (17 §3c).

**Staleness:**

- A step is **stale** when an input's revision differs from the one it stamped.
- The orchestrator computes it, generalising the stage-revision stale mark.
- *Run stale* is a planned set of jobs, in dependency order, with its cost, staged by default.

**The Shot node:** today's Flow `FlowNode` (Shot and Dialogue types) and Story's shot merge into one record. The node keeps its Flow
fields (title, lines, place, speaker versions, board, colour); the shot keeps its versions. A migration joins each bound node with its
shot (sole ownership already pairs them, loom R146), and unbound shots become Shot nodes outside any route.

## 5. How the suites fit

| Suite | Role |
| --- | --- |
| **Story › Flow** | the story graph; Shot cards with the used take, length (a warning past 30 s), stale count; scene groups; open a Shot as its recipe graph |
| **Story › Shots** | the Shot nodes as a list (search, sort, state) |
| **Animate** | the Shot editor (D95's layout); the For chip *is* the Shot; the column's sections are the recipe's steps; a *Graph* view beside the viewer's levels |
| **Image** | stills for a Shot (frames, references, animation references), with the For chip as today |
| **Catalogue** | C2's shot page holds a Shot's files; C4 is the recipe graph, opened from any item ("show its recipe") |
| **Episode** (the cut) | each Shot's take on a video lane in route order; finished and rendered as a backend job; the FilmCraft-like editor from RC4 |

## 6. Plan

| Wave | Content | When | Effort |
| --- | --- | --- | --- |
| **RC0 · The recipe record** | the shot version's `recipe` (template, steps, inputs, outputs, stamps), written by Animate's and Image's work for a Shot; the templates; the coverage check of §3 as a test (every step's important parts reach the job that runs, as D60's settings audit does for Settings); staleness; *Run stale* with its cost | with AN1 / AE1 | 4–5 |
| **RC1 · The recipe graph** | a Shot's recipe drawn with `@xyflow/react`, in the Flow (in place) and in Animate (the *Graph* view); states, *Run stale*, a step opens its section in Animate; C4's lineage view becomes this graph | the Story pass | 4–5 |
| **RC2 · The Shot node** | the merge of the Flow node and the Story shot (record, migration, API); Shot cards with take, length, stale count; the 30 s warning; scene groups; the Shots tab as a list of Shot nodes | the Story pass | 4–5 |
| **RC3 · The cut from the Flow** | each Shot's used take placed on a video lane in route order, one cut per route; the lane follows a Shot's new take, with a *changed* mark; the movie render as a backend job | the Story pass | 2–3 |
| **RC4 · The cut editor** | FilmCraft reviewed as 03 reviewed EffectCraft (what to reuse, how), then the multi-track cut editor that replaces the single-lane Episode | after RC3 | 1–2 for the study; the build sized by it |

**Total:** ≈ 15–20 days before RC4's build, of which RC0 (4–5) comes with Animate.

## 7. Questions — answered by the author, 2026-10-18 (D96)

| # | Question | Answer |
| --- | --- | --- |
| 1 | The name | **B**: the node is a **Shot**, the cut stays **Episode** |
| 2 | Cameras per node | **one camera per Shot** |
| 3 | The 30 s cap | **a warning only**, a guideline |
| 4 | Where the recipe graph opens | **both**: in the Flow and in Animate |
| 5 | The cut | **each Shot's content rendered onto a video lane** of the FilmCraft-like edit suite, where the final movie is processed and rendered |
| — | Simplicity | **no features sacrificed**: every important part is a step (§3's coverage table), as in a ComfyUI workflow |
