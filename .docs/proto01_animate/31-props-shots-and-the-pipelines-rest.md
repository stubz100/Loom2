# 31 · Props as models, the Shot node and the pipeline's rest

Status: **the plan, 2026-10-24.** The author, after D126 was built: *"Q22: all props have to have a 3D model / Q23: I don't like a prop
that is a part of the character, we should scrub that / Let's build the remaining two items"*. The two answers are **D128** and **D129**;
the two items are **RC2** (the Shot node, [05](05-flow-nodes-as-shot-recipes.md) §6 with [06](06-continuity-across-shots.md)'s O2 and O3)
and **phase 5b** ([07](07-build-order.md): the clay pipeline's rest). This document holds their waves and their order.

## 1. D128 — every prop has a 3D model, in both builds

A prop is never a cut-out, a depth-guided picture or a clay stand-in in a shot. Two ways give a Cast prop's version its model:

| Way | Build | What it is |
| --- | --- | --- |
| **Import a GLB** | both | the author's own 3D work, or a store's model whose licence the author vouches for: a binary glTF 2.0 file into the Catalogue as a mesh (as it is: its orientation and scale), set on the version |
| **Image → 3D** | `full`: Pixal3D (D84) · `open`: spike **E33** | made from the version's animation reference (else its hero), stood upright (D110) |

**PM1 · the import** ✓ built 2026-10-24: `POST /story/profiles/{pid}/versions/{vid}/model/import` (the header checked: `glTF` magic,
version 2; a character or a place refused), the Catalogue's own *Import* takes `.glb` as a mesh (its thumbnail drawn by the client's 3D
view, P18), *Import a 3D model (GLB)…* on the prop's 3D model block, its right-click and the readiness row; the readiness row owes a
prop's model in **any** shot it is in (it was only a prop bound in Stage). The `open` build's refusal of *Make the 3D model* now points to
the import.

**E33 · open image → 3D** (a spike, its downloads asked for when it runs): candidates, their licences read against D17 / D26 first — **TRELLIS**
(Microsoft; MIT as last read, a textured mesh) and **TripoSR** (Stability AI + Tripo; MIT as last read, a fast mesh with vertex colours).
Stable Fast 3D's community licence and Hunyuan3D's EU exclusion keep them out. Measured on the
rig on the props of the A1 project against Pixal3D's results (silhouette IoU from six views, the texture's colour error, seconds, peak
VRAM). The winner becomes `open`'s image → 3D, the losers' weights deleted (house rule 1).

## 2. D129 — a held prop is its own model in the hand

E28's P3 (a prop drawn inside its holder's Wan Animate layer from a reference holding it) is dropped. A held prop is D109's 3D model
**parented to the holder's hand** in Stage:

**HP1 · in the hand** (Stage, no GPU but the rig check):

- `StageObject.parent_joint` (`r_hand` | `l_hand`) beside `parent` (the figure): a bound mesh parented to a figure follows the hand's
  world transform every frame, with the offset the author sets (the transform is local to the hand). The Simple figure's hand is the
  wrist marker past the elbow; the Detailed figure's `hand_r` / `hand_l` bone.
- *Put it in the hand ▸ right / left* on a prop's right-click and in its Inspector, with the figure picked from the stage's figures;
  *Take it out of the hand* (the prop stays where it is in the world). The outliner shows it under its figure.
- The final's layers (PS5a) treat it as any prop: its own layer from Stage's passes, rendered in the hand's motion; its depth order per
  frame as for every layer (PS5e), so a cup in front of the body sits in front of it.
- Rig: a figure walking a library clip with a cup in its right hand → the cup's layer follows the wrist within 2 px per frame at Draft;
  the final's composite holds it in the hand.

Generate's still-image wording (*holding …*, D93 C6) is a picture's prompt, not a layer, and stays.

## 3. RC2 — the Shot node

D96: *a Shot is a Flow node with a recipe*. D125 built the interface (a visual node has its shot from the start, one panel for both, the
board) without merging the records. RC2 merges them and adds what the merge makes possible.

The waves are in §3a; the model they change is mapped in §3b.

### 3a. The waves

| Wave | Content | Days |
| --- | --- | --- |
| **RC2a · one record** | the Flow node and its Story shot as one Shot (the record, the migration, the API kept for one release); a node without a shot stays a story node | 2 |
| **RC2b · Shot cards** | the Flow's card shows the used take (its first frame), the length, the stale count; the 30 s warning (a guideline: nothing is blocked) | 1 |
| **RC2c · scene groups** | a frame around Shots in the Flow (made from a selection, named, moved together); *New coverage shot* on a Shot makes a sibling in its group; CE4's *Grade the scene* takes the group (the place's run stays the fallback) | 2 |
| **RC2d · the Shots list** | the Shots tab's board rows are the Shot nodes, grouped by scene, with search, sort and the state filters | 1 |
| **RC2e · templates (O2)** | *New Shot from this Shot* (the scene's parts linked, the Shot's own copied); *Save as a template…* into the World Library; *New Shot from a template…* | 2 |
| **RC2f · linked copies (O3)** | within a scene the shared parts (set, plate, light, cast versions, props, grade) are linked by default: one item, several users, a badge; *Make independent* breaks a part away (an independent copy is the Catalogue's *Duplicate*) | 2–3 |

### 3b. The model today and the merge

**Today** (the code map of 2026-10-24): two records in two id spaces, written separately. A node (`story/flow/nodes/node_*.json`)
points at its shot by `shot_id` + `shot_version`; the shot (`story/shots/sht_*.json`) back by `owner_node`. Ownership is checked only in
`bind_shot`, so the two pointers can disagree: *Release* patches `owner_node` alone, a deleted shot leaves its node pointing at nothing, a
node turned into a Choice keeps its shot, and lookups try one pointer and fall back to the other. A node *shows* a version
(`shot_version`) besides the shot's `current`. Both kinds of id are saved far outside Story: finals, legacy timelines, the FilmCraft cut's
item metadata (`loom2.shot`, `loom2.node`), job origins in the queue and in Catalogue manifests, voice and audio-layer records.

**The merge (RC2a):**

- **One file per Shot: the node's.** A visual node's file holds its shot (`FlowNode.shot`: the versions, `current`, its own revision); the
  shot files go. The two pointers become one containment, so they cannot disagree.
- **Both ids stay.** The shot keeps its `sht_*` id inside the node, so every saved reference (finals, cuts, origins, manifests) still
  resolves; `story/flow/shots.json` is a rebuildable index from a shot id to its node (checked on use, rebuilt when wrong).
- **One name, one shown version.** The shot's name is the node's title; the version the node shows is the shot's `current`.
- **Every shot has a node.** A shot made elsewhere (*New shot from this camera…*, *Make a shot from this clip…*) is a Shot node outside
  any route, placed beside the graph; the board lists it under *Not on a route*. *Bind* moves a shot from such a node into another
  (the bare node goes; the receiving node's own shot, if it has takes, moves out to a node of its own); *Unbind* and *Release* move the
  shot out to a node of its own and leave a fresh shot behind. Nothing is lost by either.
- **Deleting:** a node's shot is deleted with it or moved out to a node of its own (the question as today); *Delete shot* on a routed
  node empties its shot (the lines and the place stay), on a bare node outside the routes deletes the node.
- **A node turned into a non-visual type** keeps nothing it cannot show: refused while its shot has takes or a source, else its empty
  shot is dropped.
- **The API is kept for one release:** `/story/shots…` reads and writes the shot inside its node (`owner_node` and the node's
  `shot_id` / `shot_version` computed), so the clients and the external references go on working; both `story.changed` kinds are sent.
- **The migration** runs once when the project opens, with a recovery note: each node's shot joins it (the owner wins where two nodes
  point at one shot; the other gets a fresh shot); a shot without a node becomes a Shot node outside the routes; a pointer to nothing is
  cleared; the old shot files are moved to `story/shots-rc2/` (not deleted). Flow schema 2.

**The scene (RC2c):** `story/flow/scenes.json` (schema 1) holds the scene groups (id, name, colour, and the parts the scene shares:
§RC2f); a node names its scene (`FlowNode.scene_id`). The frame around a scene is drawn from its nodes' positions and moves them together.

**Linked parts (RC2f), part by part:**

| Part | Linked (the default within a scene) | *Make independent* |
| --- | --- | --- |
| **Set, props, lights** | one stage, several cameras: the new Shot points at the scene's stage with a camera of its own | the stage duplicated with this Shot's camera; the Shot points at the copy |
| **Cast versions** | the scene's pins (`Scene.cast_versions`); a Shot without its own pins uses them, and setting one on a linked Shot sets the scene's | the scene's pins copied into the node (`speaker_versions`) |
| **Plate** | on a picture set the plate is the set's (one stage); a Klein plate is the camera's, so a Shot on a copied camera keeps the first plate as its reference (O4) | the plate made again from this Shot's camera alone |
| **Grade** | the scene's grade (CE4's adjustment layer over the scene's run) — the scene record keeps it, so a re-assembled cut grades the scene again | the Shot leaves the scene's layer: its clip gets the scene's grade as its own Lumetri and the layer is split around it |

A part shows a *linked · N Shots* badge with its users; the Catalogue's *Duplicate* stays the independent copy of an item.

## 4. Phase 5b — the clay pipeline's rest

| Wave | Content | GPU | Days |
| --- | --- | --- | --- |
| **AE5 · the output** | the finished shot's **render settings** (quality, resolution, frame rate, motion blur, frame blending, colour depth; proxy use off) and **output modules** (the PNG master always; ProRes 4444 with alpha beside it; the H.264 proxy) on the final, shown in the Final mode's foot and the render's Inspector; `comp_render` runs EffectCraft's render queue with them (`renderQueue.add` takes every one) | no (CPU, D113) | 1–2 |
| **CA4 · the plan with its cost** | each character layer's batches (77 frames, 5 carried) with the frames each covers and its minutes from the measured runs; the shot's total; *Stage the runs* (the queue's *staged* jobs, released by *Run staged*) for an overnight start | no | 1 |
| **CA5 · re-take from a batch** | *Re-take from this batch* on a layer's batch: that batch and the ones after it again with a new seed, the batches before kept (the carried frames come from the kept batch) | yes (rig) | 1–2 |
| **HP1 · in the hand** | D129, §2 | rig check | 2 |
| **CA3 · the plate for large moves** | spike **E34** first: the depth-guided plate video — LTX-2.3's IC-LoRA union control (Stage's guided method already loads it) with the plate still as the first frame and the bare set's depth along the camera path as the control; measured on an orbit and a long dolly against the projection (stretch, the still's match at frame 1, seconds, VRAM). If it holds: the final's plate gets a method (*projected* for small moves, *generated along the path* for large ones, chosen by the camera's travel), its frames a plate layer like the projection's | yes (spike, then rig) | 3–4 |
| **E33** | D128's open image → 3D (§1), downloads asked for first | yes | 1–2 |

D102 retired CA5's W3 (a per-frame refine at a seam made the hold worse); A6's healing patch stays for regions.

## 5. The order

1. **PM1** (built) → **RC2a → RC2f** (no GPU: tests, the e2e, screenshots).
2. **AE5 → CA4 → CA5 → HP1** (CPU and short rig checks, one GPU job at a time, D97).
3. **E34 → CA3** (GPU), then **E33** (GPU; downloads asked for first).

Each wave: offline tests, Vitest, the e2e under both variants, the rig where a GPU path changes, screenshots of every section it
touches, a journal entry and a local commit.
