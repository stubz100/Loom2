# 05 · Story Flow: every node a shot recipe

Status: **proposal, 2026-10-18, the author's idea reviewed.** Nothing decided. Story is built after Animate (D95), but the recipe model
is designed now, because Animate's work is done per node.

The author (2026-10-18), on idea C4 of [04](04-catalogue-for-making.md):

> *"I very much like the idea of C4, and it is also in line with our original story-flow idea. Each node in the Story/Flow should
> represent an 'Episode', and an episode should be what you just described in C4: certain elements in combination defining a small shot
> (max 30 s perhaps), much like how ComfyUI works. These nodes (episodes) in combination would build up the full movie, which is then
> finalized in a FilmCraft-like editor."*

## 1. The idea

There are two levels of graph:

```
STORY FLOW — the story: what happens, in which order, with which branches
  [Start] ──▶ [Node · Arrival 0:12] ──▶ [Node · Mara and Ines 0:24] ──▶ ◇ Choice ──▶ [Node · The door 0:08] ──▶ …
                                             │ open
                                             ▼
INSIDE ONE NODE — its recipe: the elements, and how they become a take (C4, as a plan instead of a record)
  Mara v1 ─▶ anim. ref ─┐                                 ┌─▶ keyframe stills ─┐
  Ines v1 ─▶ anim. ref ─┼─▶ Stage: set · figures · motion ┼─▶ plate ───────────┼─▶ performance (layers) ─▶ composition ─▶ finish ─▶ TAKE
  Lines ──▶ voice ──────┘        · camera                 └────────────────────┘                                              ✓ used
                                                                                                                                │
THE MOVIE — the nodes' takes along a route of the flow ─▶ the cut, finished in a FilmCraft-like editor ◀────────────────────────┘
```

- **Each node is a small shot of up to about 30 s.** Its *recipe* combines the elements (characters, a place, lines, motion, a camera)
  into a take, through the steps the clay pipeline defined (01, 02).
- **The recipe works like ComfyUI.** It is a dataflow graph: change an input, and only what depends on it needs to run again.
- **The nodes along a route make the movie.** Their takes become the cut, which is finished in an editor modelled on FilmCraft
  (Episode's later enrichment, D95).

## 2. Review

### What it gets right

1. **One object instead of five.** Today a Flow node, a Story shot (versions, takes), Animate's For chip, the composition (03, AE1) and
   the lineage are separate records joined by ids. They are all facets of one thing: *this bit of the film and how it is made*. A node
   with a recipe is that thing.
2. **Lineage becomes a plan, so loom2 knows what is out of date.**
   - C4 recorded how a take *was* made. A recipe says how it *is* made, so it can say what has gone stale.
   - Change Mara's animation reference, and her keyframe stills, her layer, the composition and the take are marked stale. Ines's layer
     stays valid. *Run stale* queues only what is needed, with the cost first (D79's pattern).
   - Today staleness exists only for a stage moving after its clip (17 §3c, D93). The recipe generalises it.
3. **It is the original loom's model** (`kb-storyboard01.md`):
   - **A node owns its clip.** It is built from chained segments with "pixel-identical" continuity *within* the node.
   - **Between nodes** there are deliberate transitions.
   - Node versions each keep their own clip, with a finalize gate.
   - The render list picks a node version's clip.

   The clay plan's batches are exactly "segments within a node".
4. **Animate becomes the node editor.** Its column (03 §4.2: Shot · Scene · Motion · Camera · Plate · Performance · Edit · Finish ·
   Output) *is* the recipe's steps in order. The graph and Animate are two views of one recipe:
   - the **graph** for the overview, the stale marks and alternatives;
   - **Animate** for doing the work.

   No new application.
5. **The cut follows naturally.** A route through the flow gives the order of the nodes, so a first cut can be assembled from it, then
   finished by hand in the cut editor.

### What needs care

1. **The name.** In loom2 today, **Episode is the cut** (Story › Episode, the lane). In film and TV language an *episode* is an
   instalment, and a ≤ 30 s unit is a **shot** (one camera) or a **beat**. Two clean options:
   - **A. The author's words.** The node is an **Episode**; the cut is renamed **Movie** (or *Film*), finished in the FilmCraft-like
     editor.
   - **B. Today's words.** The node is a **Shot**: the Flow node and the Story shot merge, and the Shots tab becomes a list view of the
     nodes. **Episode** stays the cut.

   *Recommendation: B.* The shot record already has versions, a frame, a clip, takes, a stage and a camera, and the author's own
   description says "a small shot". **A** works just as well technically; it is a naming choice for the author.
2. **The paradigm of ComfyUI, not ComfyUI itself.**
   - loom2 never uses ComfyUI's UI (D2, D15). The recipe graph is loom2's own, drawn with `@xyflow/react` like the Flow.
   - Its steps are **coarse** (a character, a stage, a performance), not ComfyUI's fine nodes (samplers, encoders).
   - Each step runs as loom2 jobs, which use ComfyUI underneath.
   - The author never wires a sampler; the graph shows *what* a shot is made of, not *how* a model runs.
3. **About 30 s.**
   - It is a good unit: 720 frames at 24 fps is 10 Wan Animate batches per layer; one composition stays light enough to preview
     (03 §5.2a); and a re-take stays affordable.
   - Propose a **soft cap**: a warning past 30 s, not a block.
   - A longer beat is two nodes joined by a transition, the original loom's rule ("split it into two clips and join them at the episode
     level").
4. **One camera per node?**
   - In the original loom, cuts happen *between* nodes. A dialogue in shot / reverse-shot is then several nodes. The Flow can show them
     as one **scene group** (a frame around the nodes), sharing the stage, cast and lines.
   - The alternative, several cameras inside one node, makes the recipe a small edit of its own.
   - *Recommendation:* one continuous camera per node, scene groups for coverage.
5. **The branches stay.** The Flow's logic nodes (Choice, Condition, Action, Hub, Jump) keep their meaning; they have no recipe. A
   branching story has several routes, so a **cut per route** (one per ending, say).
6. **The quick way must stay quick.** A node made from one image by image-to-video has a two-step recipe (start image → performance →
   take). The graph must never make the simple case slower than Animate is today.

## 3. The model

**Recipe steps** (coarse; each with inputs, settings, outputs, a state and a cost):

| Group | Step | Holds / makes | Exists as |
| --- | --- | --- | --- |
| Elements | **Character** | a Cast version (look, sheet, colours) | Cast (D85, D93 B) |
| | **Place / set** | the stage's set, or a Cast place | Stage, D93 C7 |
| | **Lines** | Dialogue lines → voiced audio | Flow Dialogue, CN2 (D87) |
| | **Motion** | library clips, keys, root paths per figure | Stage ST4, CA1 |
| | **Camera** | the shot camera and its moves | Stage cameras |
| Making | **Animation reference** | per character version | CA0 |
| | **Plate** | the empty set rendered from the camera; still or moving | 01 step 4, CA3 |
| | **Keyframe stills** | per figure per batch (W2) | Exact pose with binding |
| | **Performance** | image-to-video, pose-driven (Wan Animate per layer) or depth-guided | Animate, CN4, CA5 |
| | **Lip-sync** (experimental) | S2V on a line | D88 |
| Finishing | **Composition** | the EffectCraft composition: layers, mattes, effects, colour | 03 AE1–AE3 |
| | **Finish** | the post stages that E24 keeps | 01 step 8, AE4 |
| Output | **Take** | a rendered clip; one is *used* | D93 takes, finalize (17 §3c) |

**States:**

- **fresh**: the outputs match the inputs;
- **stale**: an input's revision differs from the one stamped when the step ran;
- **running** or **queued**;
- **missing**: never run.

A node card in the Flow shows the take, its length and "3 stale".

**Records:**

- A shot version gains a `recipe`: `{steps: [{id, kind, ref | settings, inputs: [step ids], outputs: [asset ids], stamps: {input:
  revision}}]}`. It is written through `fsio` with `schema_version`.
- **Running a step writes its lineage edges.** C4's view becomes the recipe graph with its history.
- **Versions** stay the shot versions (D93): editing a recipe and running it makes a new version's takes.
- **Finalize** stays as it is.

**The node:**

- Option B: the Flow's Shot and Dialogue nodes *are* shots (today they bind one, with sole ownership, loom R146).
- Option A: the same records under the name Episode.

## 4. How the suites fit

| Suite | Role |
| --- | --- |
| **Story › Flow** | the story graph; node cards with their take, length and stale count; **open a node** to see its recipe graph (in place, as a sub-graph), with *Run stale* and *Open in Animate* |
| **Animate** | the node editor (D95's layout); the For chip *is* the node; the column's sections are the recipe's steps; the viewer's three levels (Clay, Performance, Final) are the recipe's stages |
| **Image** | stills for a node (frames, references, the animation references), with the For chip as today |
| **Catalogue** | C2's shot page is the node's page (its files); C4 is the recipe graph view, opened from any item ("show its recipe") |
| **Episode** (or Movie) | a cut assembled from a route of the Flow, then finished by hand; the FilmCraft-like editor is a later study, as 03 is for EffectCraft |

## 5. Plan

Story is built after Animate (D95). One piece has to come first, because Animate writes it:

| Wave | Content | When | Effort |
| --- | --- | --- | --- |
| **RC0 · The recipe record** | the shot version's `recipe` (steps, inputs, outputs, stamps), written by Animate's and Image's work for a node; staleness computed by the orchestrator (generalising the stage-revision stale mark); *Run stale* as a planned set of jobs with its cost; tests | with AN1 / AE1 | 3–4 |
| **RC1 · The recipe graph** | a node's recipe drawn with `@xyflow/react` (read, states, run stale, open a step in Animate); C4's lineage view becomes this graph | the Story pass | 3–4 |
| **RC2 · Node = shot in the Flow** | the naming (A or B); node cards with take, length, stale count; the soft 30 s cap; scene groups; the Shots tab as a list of nodes | the Story pass | 3–4 |
| **RC3 · A cut from a route** | assemble the first cut from a route (Start → the chosen options) into the Episode lane; a cut per route | the Story pass | 2 |
| **RC4 · The cut editor study** | review FilmCraft as 03 reviewed EffectCraft: what to reuse, how, and the multi-track cut | after RC3 | 1–2 (study) |

**Total:** ≈ 12–16 days, of which RC0 (3–4) comes with Animate.

## 6. Questions for the author

1. **The name:** A (the node is an *Episode*, the cut a *Movie*) or B (the node is a *Shot*, the cut stays *Episode*)?
2. **One continuous camera per node,** with scene groups for shot / reverse-shot, or several cameras inside one node?
3. **The 30 s cap:** soft (a warning) or hard?
4. **Where the recipe graph opens:** inside the Flow (a node opens as its sub-graph), in Animate (a *Graph* view beside the viewer), or
   both?
5. **The cut:** assembled from a route automatically as a first cut, then edited by hand, or always hand-built (today's rule, loom
   R148)?
