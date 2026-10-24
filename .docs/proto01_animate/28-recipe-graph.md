# 28 · RC1 — the Shot's recipe graph

Status: **plan, 2026-10-24; building.** D96 accepted RC1 on 2026-10-18 ([05](05-flow-nodes-as-shot-recipes.md) §6: "a Shot's recipe drawn
with `@xyflow/react`, in the Flow (in place) and in Animate (the *Graph* view); states, *Run stale*, a step opens its section in Animate;
C4's lineage view becomes this graph"). The wireframes are UX0's W6 ([03-ux0-review](../proto01_UI/03-ux0-review.md) §W6) and C4
([04](04-catalogue-for-making.md) §C4). D125 (proto01_UIcomp) kept RC1 as planned; it built RC2's interface and RC3's cut without them.

## 1. Why it is needed now

- **The recipe today is a list, and for the clay route it is empty.** RC0's record keeps the runs of the jobs made *for* a shot: the
  frame, the clip, the lip-sync. A clay final shot's work (the plate, each character's layer, the assembly, the composition, the render)
  lives in the final's record, the stage and the Cast — so the A1 rig's shot (journal 2026-10-24 01:25) has a take, a clip and *no
  recipe*. Its template still lists the clay steps as *planned* behind waves (CA0–AE5) that are built and rig-checked.
- **"What does a change touch?"** (UX0's P5): a character's motion edited should mark her layer, the composition, the finish and the take
  stale and leave the other character's layer fresh. Nothing shows that today.

## 2. The graph

Built on the server from the records, on request; nothing is stored (as RC0's state is). `GET /story/shots/{sid}/graph?version=`.

| Node | One per | Picture | Done when | Stale when | Opens |
| --- | --- | --- | --- | --- | --- |
| **character** | Cast character in the shot (the node's speakers, the stage's bound figures) | its version's hero | the version has a hero | — | Story › Cast, the version |
| **anim ref** | character on a clay route; prop with one | the reference | set | — | Story › Cast, the version |
| **place** | the node's place | its hero | the version has a hero | — | Story › Cast |
| **lines** | Dialogue node | — | every line voiced | a line changed since its voice | Story › Flow, the node |
| **stage** | the version's stage | — | linked | — | Animate › Clay |
| **motion** | figure with keys on the stage | — | keyed | — | Animate › Clay › Motion, the figure |
| **camera** | the version's camera | — | linked | — | Animate › Clay › Camera |
| **frame**, **clip**, **lip-sync** | RC0 step | its output | a run counts | RC0's reasons | Image (frame), Animate › Performance (clip) |
| **plate** | the final | its still | still and frames made | the stage moved since the final | Animate › Performance › Final shot |
| **layer** | final layer of a figure or a prop | its first frame (the last batch's clip) | done | the stage moved since the final | Animate › Performance › Final shot |
| **composition** | the final | the assembly | assembled and composed | the final changed since (`Composition.stale`) | Animate › Final › Layers |
| **finish** | the final | — | a pass on a layer or a processing layer | a processing layer's layers changed | Animate › Final › Layers |
| **take** | the version | the version's clip | the version has a clip | the render saw an older composition revision | Story › Shots, the shot |

**The final** is the one made for this shot version (A1), else the newest on its stage and camera. **States:** done, stale (with why),
owed (the route needs it, nothing made), running (a job of it queued or running), none (optional and not used — a finish with no pass).
**Edges** follow what a step reads: character → anim ref → its figure's layer; motion → its figure's layer; camera → plate and layers;
plate and layers → composition → finish → take; for the image-to-video routes, characters and place → frame → clip → take; lines →
lip-sync. **Stale spreads** along the edges as in RC0 ("after <step>").

The clay template's steps lose their *planned* waves (all built); a clay version's RC0 list reads its states from the graph, so the
Shot section in Animate and the shot page agree with it.

## 3. Where it opens

- **Animate:** a **Graph** pill beside *Clay · Performance · Final* (key 4). It replaces the viewer with the For chip's shot's graph in
  whichever mode is on; the mode's column stays. Selecting a node switches to the mode that owns it and opens its section (a figure's
  motion selects the figure). Without a For chip the Graph says so and offers the stage's newest final's shot when there is one.
- **Story › Flow:** *Open its recipe* on a Dialogue or Shot node (Inspector, right-click) shows the graph in place of the canvas, with
  *← The Flow* and *Open in Animate*.
- **Story › Shots:** the shot page's recipe list becomes the graph (compact); a node click does what it does in Animate.
- **Catalogue (C4):** *Show its recipe* on a take of a shot (an image or a clip the version holds) opens Story › Shots on that shot.
- **Run stale ▶** sits on the graph's strip: RC0's plan for the steps the server can run again (asks with the cost); the clay steps that
  are made again by hand (a layer performed again, the assembly, the render) are listed with their verbs.

## 4. Waves

| Wave | Content | Checks |
| --- | --- | --- |
| **RC1a · The graph record** | `shot_graph` (pure) and its route; the final found for a version; states and reasons; stale along the edges; the clay template's waves cleared, the clay steps in RC0's list read from it | pytest: an i2v shot, a dialogue shot, a clay shot from a final (each node and edge, a stage edit making the plate and layers stale, a render behind its composition) |
| **RC1b · The view and Animate's Graph** | `RecipeGraph` (@xyflow/react, ranked columns like W6, a picture and a badge per node), the Graph pill and key 4, a node opening its mode and section, Run stale on the strip | Vitest (the ranks, the node → section map); e2e: the A1-like shot on the fake engine — Graph shows its nodes, a click opens Clay › Motion on the figure |
| **RC1c · Story and the Catalogue** | the Flow in place, the shot page's graph, *Show its recipe* | e2e: each place opens the same graph; screenshots |
| **RC1d · Rig** | the A1 project's real final, its graph and a stage edit making the plate and layers stale | the graph against the rig's records |

About 4–5 days, as 05 §6 sized it. No GPU until RC1d's look at a real final (no new job).

## 5. Not in RC1

- **Editing in the graph.** The graph shows and opens; settings live in their sections (D96: no feature hidden, one place to edit).
- **RC2's record merge** (a Flow node and its shot as one record): D125 made a node own its shot; the merge waits until something needs it.
- **The movie render** (RC3's rest) and **the cut editor** (RC4).
