# 02 · The structure: three layers, one Bin, no trips

## 1. The layers

```
Top bar   ☰  Project ▾  │  World · Shots · Episode · Bin            (Ctrl+1–4)          engine · queue · disk · weights

World     Characters · Props · Places │ Look · Sketches            what exists, made and readied for Clay
Shots     Flow │ Clay · Performance · Final                         what happens, shot by shot, refined level by level
Episode   (the cut editor)                                          how the finals play together; what leaves loom2
Bin       (the tree of every home)                                  where everything is
```

| Layer | Its question | Its unit | It is done when |
| --- | --- | --- | --- |
| **World** | What exists, and is it ready for a stage? | an entity version (Ines v1) | every entity a shot uses is *Ready for Clay* ([03](03-ui-world.md) §2) |
| **Shots** | What happens, and how far is each shot? | a shot (a camera on a scene) | every shot of a route has a final, marked final |
| **Episode** | How do the shots play together? | a cut (one per route) | the export is written and the movie rendered |

**The work moves down the layers, and back up freely.** Nothing forbids opening Shots before World is complete. A shot's cast row shows which World
entity is not ready yet, and links to it. The layers are an order of refinement, not a wizard.

**Three maker tabs disappear: Image, Animate and the Catalogue.**

- Image's Make and Edit become World's panel (and Edit opens on any still anywhere).
- Animate's three levels become the shot's levels.
- The Catalogue becomes the Bin.

## 2. The records, as the author sees them

```
World                        Shots                                                         Episode
─────                        ─────                                                         ───────
Entity (class, name)         Flow ── Shot node ──────────────┐                              Cut (one per route)
 └─ Version v1, v2 …          │      description, lines       │                               └─ V1: each shot's final
     sheet · body · voice     │      scene ─▶ Scene (a stage) ─┤ camera A · range 0–96             A1: the lines
     roles in its bin          │                set ◀─ Place  │                                   A2–A3, V2 …
                               │                figures ◀─ Characters
                               │                props ◀─ Props
                               │                lights · cameras · tracks (clip blocks, keys)
                               │      versions ─▶ Performance takes (per layer) ─▶ Final (render) ─────▶
                               └─ Choice · Condition · Action · Hub · Jump · Note · Start (logic)
```

**Shots.**

- **A shot is one Flow node.** Its record is the node, whose file already holds its shot (RC2a). Its scene is a stage, and the node names the camera and
  the range. The range is new: today a stage has one range for all its cameras (06 §2.3).
- **A scene is shared by its shots.** One shot per scene is the default ([04](04-ui-shots.md) §1).
- **Versions are the shot's outputs**: a version holds its Performance takes, its final and its approval. Each pins the stage revision it was made from,
  so a change in Clay makes the version's takes stale instead of silently changing them.
- **A scene has revisions** (undo, today's stage revision), and *Duplicate scene* is the way to try a different blocking.

**World.**

- **Entities are today's Cast profiles**, unchanged in kind: character, prop, place. A version holds the sheet, the body, the 3D model or the set, the
  and the voice (on the profile); no LoRA (D157). An entity with nothing ready is a *draft*.

**Episode.**

- **A cut is today's FilmCraft project.** It reads finals only.

## 3. The Bin: one home per asset

Every asset made or imported gets a **home**, the path of the thing it was made for, and optional **roles** inside it ([05](05-ui-episode-and-bin.md)
§2):

| Home | Written by | Roles |
| --- | --- | --- |
| `world/<class>/<name>/<version>` | World's Make and Edit, the A-pose, the set picture, the 3D model | hero, reference, A-pose front / back, set picture, face, model; the rest candidates |
| `world/look` | style samples | sample (per style) |
| `world/sketches` | free Make, moodboard imports | — |
| `shots/<nn name>/<version>` | Shots: stills, passes, layer takes, the final | start still, plate, take (per layer), in use, final |
| `episode/<cut>` | the movie renders, the Resolve folders | movie, export |
| `imports` | files brought from disk | — |
| `trash` | deletes | — |

The batch stays a fact of the queue and of lineage. It is no longer a way of grouping on screen ([01](01-evaluation.md) §4; 06 §1.2).

## 4. Context without chips

There is no For chip. The context of every action is **where the author is**:

- World's Make makes for the entity in the header;
- Shots makes for the open shot;
- Episode edits the open cut.

So a whole family of defects has nowhere to live:

- the For chip's leaks (F25, F29, FE#1, FE#12);
- *Back* going to the wrong place (FE#10);
- a trip landing on a collapsed panel (F26).

**Deep links** name the place, and survive a reload:

- `#world/character/<id>/v1`
- `#shots/<shot-id>/clay`
- `#episode/<cut-id>`
- `#bin/world/place/<id>`

A reload no longer ends a context, because there is no context to end.

## 5. The frame

```
┌─────────────────────────────────────── top bar: ☰ Project ▾ │ World · Shots · Episode · Bin │ status chips ────────────────┐
│     │ (Shots only: the storyboard strip, the route's shots with their level dots)                                           │
│rail ├────────────────────────┬──────────────────────────────────────────────────────────────┬────────────────────────────┤
│     │ LEFT COLUMN            │ CENTRE                                                       │ INSPECTOR                  │
│     │ the header (entity or  │ the bin (World) · the level's viewer (Shots) · the preview    │ the selected thing         │
│     │ shot), then the panel  │ (Episode) · the grid (Bin)                                   │                            │
│     │ (Make / Edit, the      ├──────────────────────────────────────────────────────────────┤                            │
│     │ level's sections)      │ the timeline (Shots: the animation editor; Episode: the cut)  │                            │
│     │ foot: the next step ▶  │                                                              │                            │
├─────┴────────────────────────┴──────────────────────────────────────────────────────────────┴────────────────────────────┤
│ dock: queue · bin drawer                                                                                                  │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Kept from today:**

- **Mouse-first.** Every action is a command with a mouse home; keys are accelerators (rule 3, D32, D72's remapping).
- **Help behind a ?** (rule 11).
- **No native dialogs** (rule 6).
- **One job on the GPU at a time** through the queue (rule 10).

**Changed:**

- **The left column is the layer's panel, always open in its layer.** Clicking the active rail item no longer hides it (F26); ☰ › *Hide the panel*
  and Ctrl+B still do.
- **Focus mode** hides the side columns for real (F5: today they keep their width and overflow). Its key is no longer Tab (F6).
- **The header is fixed at the top of the left column.** It is the entity or the shot being worked on, so it never scrolls away (WF10's lesson).
- **The foot is the next step, with its true cost** (F27: references count).
