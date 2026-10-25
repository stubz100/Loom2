# 05 · The plan: the numbers, the waves, the decisions

Status: **proposal, 2026-10-25 — answered the same day → D136. The answers and the revised waves are [06](06-answers.md), which holds
where it differs; the order is Q30 (06 §3).** Today's state is [01](01-today.md), the proposal [02](02-the-workshop.md), its technique
[03](03-clay-from-a-picture.md) and [04](04-places-and-the-set-builder.md).

## 1. The numbers

The journeys of [01](01-today.md) §2, counted by the same rules (clicks; typing and waiting not counted).

### J1 · An Image result becomes a clay character on a stage

| Today | | The workshop | |
| --- | --- | --- | --- |
| *Start from this image ▸ › Make a character…* + OK | 4 | *Prototype ▸* (tile's hover button) › *New character idea* | 2 |
| (Story › Cast opens; the picture moves; the sheet is empty) | tab | (Image stays; a toast offers *Open*) | — |
| readiness *Animation reference* | 1 | the idea card's *Make the clay ▶*: A-pose, fit, quick shell, bind | 1 |
| Animate, Clay | 2 · tab | *Send to a stage ▸* › the open stage: a figure bound, with its shell | 1 · tab |
| a stage | 2 | | |
| Figures `+` › *Adult* | 2 | | |
| the figure › the character's tile | 2 | | |
| **13 clicks · 2 tabs** — a grey dummy with the proportions | | **4 clicks · 1 tab** — a clay dummy with the character's outline and a checked skeleton | |

### J2 · Three takes on a character, compared in clay

| Today | | The workshop | |
| --- | --- | --- | --- |
| *Variations* | 2 | *More like this* on the idea | 1 |
| J1's steps 1–2 three times (three profiles) | 15 | *Make the clay ▶* on three variants | 3 |
| Animate › Clay, a stage | 4 | select the three on the strip, *Line-up* | 2 |
| add and bind three figures | 12 | | |
| drag them side by side | 3 | | |
| **≈ 36 · 2 tabs** — three alike dummies | | **6 · 0 tabs** — three outlines side by side, posed together | |

### J3 · An Image result becomes a prop on a stage

| Today | | The workshop | |
| --- | --- | --- | --- |
| *Make a prop…* + OK | 4 | *Prototype ▸ › New prop idea* (its quick model is made by itself) | 2 |
| *Make the 3D model…* + confirm, ≈ 4–6 min | 2 | (≈ 4 s) | — |
| Animate, Clay, a stage | 3 | *Send to a stage ▸* › the open stage | 2 |
| Props `+` › the prop | 2 | | |
| **11 · 2 tabs** | | **4 · 1 tab** — seconds, at its real height; Pixal3D on *Keep* | |

### J4 / J5 · A picture becomes a place to move through, on a stage

| Today | | The workshop | |
| --- | --- | --- | --- |
| Animate, Clay, a stage | 3 | *Prototype ▸ › New place idea* | 2 |
| Sets › *From an image…*, find it in the Bin, its corner button | 2 + search | *Build the set ▶* (match, project, bake) | 1 |
| the lens dialog | 1 | corner drags when the fit is off | 0–4 |
| | | *Fill what the picture never saw ▶* | 1 |
| | | *Send to a stage ▸* | 1 |
| **7 + the search** — a relief, ±0.25 m / ±5°, not the place; a room to move through: **dead end** | | **5–9** — a set to orbit, bound to its place | |

### J6 · The character's look in clay

**Today:** a dead end. **The workshop:** part of J1 (the shell).

### J7 · Make the skeleton match the character

| Today | | The skeleton bench | |
| --- | --- | --- | --- |
| see the skeleton over the reference | **dead end** | Cast's body › *Skeleton…* | 1 |
| shorten the neck, shrink the hands and feet: drags on sliders, against a 2D silhouette | 3 | drag a bone's end or a row's slider, the guide replaying beside it | 3 |
| see what Wan will get: *Test it* + OK, a GPU wait, the Simple guide without hands | 2 + GPU | the guide pane's motion chip, no GPU | 1 |
| relax the hands: in Clay, per figure, per stage, keyed with the pose | 7 · tab, each time | nothing (CS1's default rest hand) or *From the picture* | 0–1 |
| fit the elbows, knees and feet to the picture | **dead end** | fitted by CS1; a dragged point and *Fit again* when off | 0–2 |
| **12 + a GPU wait + 7 per figure and stage · two dead ends** | | **5–8 · 0 tabs · no GPU** | |

**In total.** The four countable journeys of J1–J5 go from about 67 clicks to about 19–23. Three dead ends open (J5, J6 and J7's).
Nine tab switches drop to three.

## 2. The waves

Each wave ends with tests (offline, Vitest, the e2e under both variants), the rig where a GPU path changes, screenshots of every section it
touches, a journal entry and a local commit. Estimates are working days.

| Wave | What it builds | GPU | Days |
| --- | --- | --- | --- |
| **CS1 · The skeleton's fixes** | S1–S8 ([03](03-clay-from-a-picture.md) §3.1): one body in the guide (CB5); a neck on the Simple dummy, with ×1 an adult's (CB6; stored bodies converted); relaxed rest hands; the turn test on the Detailed guide, in the reference's stance; the feet, elbows and knees fitted; the fit's pull toward an adult; the A-pose check on new references. E37's steps 1–3 on A1 are its rig | yes (rig) | 3 |
| **CS2 · The skeleton bench** | the Skeleton view ([03](03-clay-from-a-picture.md) §3.2) on today's Cast versions (variants join with CW1): the reference with both point sets, draggable; the figure with its bones; the guide on the starter motions with the onion skin; the parts panel in centimetres with adult ranges and locks; the rest hand (*From the picture*, presets, curl and spread); the refit route without a job; *Fine-tune the skeleton in Cast…* from Clay; the guide's body hash and *the skeleton changed* on shots | no | 4 |
| **CW0 · Fixes and bridges** | CB1–CB4 ([01](01-today.md) §4); CF17's labels; the Bin gets a Meshes filter, mesh verbs and Cast verbs; *Make it a Cast prop…* on a loose mesh (the existing `PUT …/model`); Clay's Meshes list named by source and updated live; *Add to character* becomes *Add to Cast*; Cast shows its reference set's pictures (CF6) | no | 1.5 |
| **CW1 · Ideas and variants** | the profile state `idea` and `ProfileVariant` (one record, [02](02-the-workshop.md) §4); each class's board, idea cards and their right-click; *Prototype ▸* on every picture (the tile's hover button and right-click, loupe, Bin, Inspector), copying not moving, a name from the prompt; *Keep* (a variant becomes a version, its sheet drafted from the prompt) | no | 3 |
| **CW2 · For: ‹idea› in Image** | `MakeFor { kind: 'idea' }`; an `idea` origin, so Generate, Variations, New angle, Re-run and Expand land as variants; the chip, *Explore in Image*, *Back to ‹idea›* | no | 1.5 |
| **E36 → CW3 · The character's clay** | E36 ([03](03-clay-from-a-picture.md) §5) first. Then: *Make the clay ▶* (the A-pose picture on a variant, the fit, the shell quick or good, the binding); TripoSR as a tool (its own venv, a setup script, an `image_to_mesh` model in the specs, D65); the shell on figures in Clay (and in the passes, per U8), `shadow_proxy` filled; the shell in the skeleton bench's figure pane; E37's steps 4–5 on E36's subjects | yes | 1 + 4 |
| **CW4 · Props: the quick model and a size** | TripoSR's quick model for props; a height in metres, prefilled from the sheet; the scale in Stage and the line-up | yes (rig) | 1.5 |
| **CW5 · The line-up** | Stage's engine on a scratch scene in Cast: characters, props and places side by side; pose them all; turntable; *Send to a stage ▸* | no | 2 |
| **E38 → CW6 · The set builder** | E38 ([04](04-places-and-the-set-builder.md) §7) first. Then: `PlaceSet` (room, street, corridor, open ground; openings); the camera match (MoGe's planes and the camera); the picture view's overlay; the bake (client, the plate projector); the per-face Fill (PF1's route); more sources; the 3D view's handles and fields | yes | 3 + 7 |
| **CW7 · Places in Clay, and the built set as the plate** | sets bound to places; Clay's Sets `+` and Figures `+` with Cast's cards; *Make it a Cast place…* on a picture set, and its things as prop ideas; the final shot's plate from a built set (a method `set`) | yes (rig) | 2.5 |

**The order.** CW0 → CS1 → CS2 → CW1 → CW2 → E36 → CW3 → CW4 → CW5 → E38 → CW6 → CW7.

- **The skeleton comes first.** Its faults spoil the shots being made now (Mara's hands, neck and feet, [01](01-today.md) §1.6). CS1 is
  about 3 days including E37's renders on A1; CS2 is about 4 more and needs no GPU.
- **Then the streamlining, with no GPU:** CW0–CW2, about 6 days, and J1–J3's clicks already fall there.
- **Then clay, then places.** In all, about 8½ weeks with the spikes.

## 3. Risks

| Risk | What it would cost | Where it is caught |
| --- | --- | --- |
| The shell's skinning stretches long clothes and capes too much to judge a design by | a better weighting (heat diffusion), or an auto-rigging model to vet against D17 | E36 |
| TripoSR's quick shell is too soft for a character's face and hands | the quick tier for props and silhouettes only; characters wait for Pixal3D | E36 |
| MoGe's planes are wrong on stylised pictures (ink, painterly, flat perspective) | the overlay's corners are dragged every time; the relief stays the quick look | E38 |
| Klein's Fill repeats features on large unseen walls (D135's rig: a second window) | the Fill's prompt (the place's surfaces, never its features) and the face order; a second source picture | E38 |
| Baked textures weigh 4–8 MB a face at 1 cm texels; a street has many | a texel size per kind; textures as Catalogue assets, made once per version | CW6 |
| Ideas multiply: thousands of variants | variants are pictures already on pages; the board pages and filters; a delete for a whole idea | CW1 |
| S1's whole-fit Detailed figure deforms UAL2's mesh visibly (a stretched neck, a squashed chest) | the mesh is only the clay pass's and the author's view; the guide is points. A limit on the stretch; the shell (CW3) replaces the look anyway | E37 |
| Klein's references keep fashion proportions (small heads, long necks): a faithful fit looks odd in clay but is right for Wan | the adult range warns, and S7's pull is weak: the picture wins unless the author moves it | E37, CS2 |
| S3's conversion changes what an existing shot's guide would render | the guide's body hash: earlier shots show *the skeleton changed*, and nothing re-renders by itself | CS1 |

## 4. The decisions for the author

Each comes with a recommendation. They become D-numbers when answered.

| # | Question | Recommended |
| --- | --- | --- |
| **U1** | **What an idea is.** A Cast profile in a new first state `idea`, with light variants (one name, one `@mention`, in Flow's pickers from the first minute), or a separate ideas store promoted into Cast? | a profile in `idea` |
| **U2** | *Prototype ▸* **copies** the picture (its page keeps it), unlike today's *Make a character…*, which moves it? | copy |
| **U3** | An idea's **name optional**, taken from the picture's prompt and editable? | yes |
| **U4** | **For: ‹idea›** in Image: while the chip is on, every result lands as a variant? | yes |
| **U5** | **TripoSR in `full` as the quick tier** (props' models, characters' shells; ≈ 4 s), Pixal3D when an idea is kept? The author works only in `full`, so D134's `open` build (OM1) is dropped | yes |
| **U6** | **The character's clay is its shell bound to the fitted skeleton** (E23d's shadow proxy made visible), decided after E36? | yes, after E36 |
| **U7** | **The skeleton check**: the fitted markers over the A-pose picture, draggable, with *Fit again*? | folded into U17 |
| **U8** | **The passes use the shell** (clay, depth, mask) when a figure has one; the pose pass stays the joints' | yes |
| **U9** | **The set builder's first kinds**: room, street, corridor, open ground, with doors, windows and arches; more kinds later | yes |
| **U10** | **A built set is its own plate** in the final shot (rendered through each camera; PF1 stays for presets and reliefs)? | yes |
| **U11** | **Cast in Clay**: sets bound to places; Cast's characters and places as cards in the Scene panel's `+` | yes |
| **U12** | **Where sets are edited**: in Cast's place bench, with Clay's set editor offering *Edit in Cast* (one editor), or in Clay too? | Cast's bench |
| **U13** | **The line-up** as a Cast view on a scratch scene, with *Send to a stage ▸*? | yes |
| **U14** | **The order**: CW0 and the skeleton (CS1, CS2) first, then the streamlining (CW1–CW2, no GPU), then the characters' clay, then places? | yes |
| **U15** | **The skeleton's fixes first** (CS1): one body in the guide, a visible neck, relaxed hands by default, the turn test on the shots' own guide, the feet, elbows and knees fitted — because they spoil the shots made now? | yes |
| **U16** | **×1 is an adult** (S3): the dummy's neck and head rebased, stored bodies converted exactly, and the fit pulled gently toward an adult unless the picture insists (S7)? | yes |
| **U17** | **The skeleton bench** in Cast ([03](03-clay-from-a-picture.md) §3.2): both point sets draggable, the figure's bones, the guide on a motion with no GPU, the parts in centimetres with an adult range and locks? It replaces U7's check | yes |
| **U18** | **A rest hand per character** (from the picture or a preset), the default for every pose of its figures, with a key's preset still on top? | yes |
| **U19** | **Shots learn that the skeleton changed** (the guide's body hash) and offer *Render the guide again*, with nothing re-rendered by itself? | yes |
