# 06 · The author's answers, and the plan they make

Status: **the author's answers to U1–U19, 2026-10-25 → D136; the order (Q30) → D137, the skeleton first.** Where this document
differs from [02](02-the-workshop.md)–[05](05-plan.md), this one holds.

## 1. The answers

| # | The question ([05](05-plan.md) §4) | The author's answer | What it changes |
| --- | --- | --- | --- |
| U1 | An idea: a Cast profile in a state `idea`, or a separate store? | "I think a separate idea store would be better" | §2.1 |
| U2 | *Prototype ▸* copies the picture? | "copy" | as proposed |
| U3 | An idea's name optional, from the prompt? | "yes" | as proposed |
| U4 | With For: ‹idea› on, every Image result lands as a variant? | "no, but lineage should be recorded" | §2.2 |
| U5 | TripoSR as `full`'s quick tier? | "don't need tripoSR" | §2.3 |
| U6 | The character's clay is its shell bound to the fitted skeleton? | "yes" | as proposed |
| U7 | The skeleton check over the A-pose picture? | "skeleton check should be fitted over the shadow proxy clay shell" | §2.4 |
| U8 | The passes use the shell; the pose pass stays the joints'? | "pose should also use the clay shell" | §2.5 |
| U9 | The set builder's first kinds? | "more kinds later, skyboxes, balconies, hillsides, nature, etc" | §2.6 |
| U10 | A built set is its own plate? | "yes" | as proposed |
| U11 | Cast in Clay: sets bound to places, Cast cards in the Scene panel? | "yes" | as proposed |
| U12 | Where sets are edited? | "cast's bench should have all the clay functions but bound to a char/prop/place. Clay should remain as free experimentation area - same as with image and char." | §2.7 |
| U13 | The line-up? | "yes" | as proposed |
| U14 | The order? | "explain that as a workflow for me" | §3 → Q30 |
| U15 | The skeleton's fixes first (CS1)? | "yes" | as proposed |
| U16 | ×1 is an adult? | "yes" | as proposed |
| U17 | The skeleton bench in Cast? | "yes" | with §2.4 |
| U18 | A rest hand per character? | "every character will get a hand and that makes the simple dummy redundant - we should only keep the advanced one. As for poses, we need to find a way to adjust and fit poses to a custom character skeleton - perhaps a pose editor in animate?" | §2.8, §2.9 |
| U19 | Shots learn that the skeleton changed? | "skeleton changes can happen during the animation process, they should apply as deliberate transformations - the complete re-render should be an option, but also a keyframe for skeleton changes on the timeline." | §2.10 |

## 2. What the answers change

### 2.1 Ideas live in their own store (U1)

An idea is **not** a Cast profile. It becomes one only when it is kept.

```
story/ideas/<id>.json   Idea    { schema_version, id, cls: character|prop|place, name, note, focus,
                                  variants [Variant], kept [{profile_id, version_id, variant_id, at}], created_at, updated_at }
                        Variant { id, asset_id (a copy of the picture, U2), made_from {asset_id, prompt, model, seed, for_idea},
                                  clay {kind: figure|model|set, body?, shell_asset_id?, set?} | null, note, created_at }
```

- **Written through `fsio`**, with lineage stamped at write time (rule 4). The pictures sit on the idea's own album page.
- **Ideas stay out of production.** They have no `@mention`, no place in Flow's pickers or Shots, and no LoRA. Cast shows them on a
  board of their own, **Ideas**, beside **Cast** (the kept profiles), one board per class.
- ***Keep ▶*** makes a new Cast profile (v1), or a new version of a chosen profile:
  - the variant's picture becomes the hero;
  - the sheet is drafted from the picture's prompt;
  - the clay carries over (the body, the shell, the model, the set).

  The idea records where it went, and the version records `from_idea`, so the lineage runs both ways. The idea stays on the board,
  marked kept, for more variants.

[02](02-the-workshop.md) §4 described ideas as profiles in an `idea` state; that is replaced. Its board, card and right-click verbs stay.

### 2.2 Image stays free; what is made for an idea is recorded (U4)

- **No result becomes a variant by itself.** Image's chip **For: ‹idea›** sets context only. Each result made while it is on records
  `for_idea` in its lineage.
- **The idea's bench lists those results** as *Made for this idea* (newest first). *Add as a variant* takes one, as *Prototype ▸* does
  from anywhere.
- **A variant keeps where it came from:** the source picture, its prompt, model and seed, and the idea it was made for.

This replaces [02](02-the-workshop.md) §5's landing rule. The chip, *Explore in Image* and *Back to ‹idea›* stay.

### 2.3 No TripoSR (U5)

- **Characters.** The fitted figure comes in seconds and is usable at once. The **shell** is Pixal3D's (≈ 4 min), queued in the
  background by *Make the clay ▶*. Until it lands, the bench shows the figure without it.
- **Props.** The model is Pixal3D's, or a GLB import (D128).
- **Places.** MoGe's relief stays the quick look; the set builder is the full one.

So P4's "quick, then good" now reads: **the figure and the relief in seconds, the shell, model and set in minutes, in the background.**
D134 (`open`'s image → 3D is TripoSR) is superseded: `open` keeps GLB import only (the author works in `full`; `open` stays green in
CI). E33's checkout, venv and weights (`engine/tools/e33`, 12 GB) are unneeded (rule 1: deleted, not kept), awaiting the author's OK.

### 2.4 The skeleton is fitted inside the shell (U6, U7, U17)

The shell comes first. The skeleton is fitted in it, and the check is made over it.

1. **The shell.** Pixal3D on the A-pose reference, stood upright and scaled to the height (D110). This is E23d's proxy source.
2. **SDPose's points, lifted into the shell.** Each 2D joint from the reference is cast along the front camera's ray into the shell. The
   joint sits at the middle of the shell's thickness there, between where the ray enters and where it leaves. So shoulders, elbows,
   wrists, hips, knees and ankles get their depth from the character's own body.
3. **What the shell measures directly:**
   - the neck at its narrowest section between the chin and the shoulders;
   - the head from the head's volume;
   - the hands' and feet's lengths from the tips beyond the wrists and ankles;
   - the hips and shoulders from the shell's width at their joints.

   The body's factors are taken from these 3D joints. The 2D fit (D104) stays for a figure whose shell has not landed yet.
4. **The binding** follows the fit. E36 compares proximity weights with heat diffusion.

**The bench** ([03](03-clay-from-a-picture.md) §3.2) changes in its figure pane:

- the shell is shown in x-ray (semi-transparent clay) with the skeleton inside;
- front and side views share the pane, and a joint is dragged in either;
- a joint that leaves the shell's volume is ringed.

The reference pane (SDPose's points) and the guide pane stay. *Fit again* refits inside the shell.

**E36 changes with it.** It uses Pixal3D only, and it measures the skeleton fitted in the shell against the 2D fit: the front points
against SDPose's, a side-view check, and the joints left outside the volume.

### 2.5 The pose pass comes from the shell (U8)

- **The clay, depth and mask passes** render the bound shell.
- **The pose pass's points become landmarks on the shell.** They are picked when the skeleton is fitted, as the surface points SDPose
  would read: the nose tip, eyes and ears on the head, the heels and toes on the feet. They are skinned with the shell, so in every pose
  the guide follows the character's own body. The shoulders, elbows, wrists, hips, knees and ankles stay the fitted joints, which sit
  inside the same shell.
- **The hands come from the character's hand rig** (§2.8), sized to the shell's hand and attached at its wrist. Pixal3D's hands are
  mittens (E23d), so its fingers cannot carry the finger points.
- **Posing in Clay happens on the visible shell**, with the joints' pickers inside it.

**The reading to confirm:** "pose should also use the clay shell" means that the guide's points sit on the shell; it does not mean that
the shell's picture replaces the skeleton guide. Wan Animate needs the skeleton guide.

### 2.6 The set builder's kinds (U9)

- **First:** room, street, corridor, open ground, with doors, windows and arches ([04](04-places-and-the-set-builder.md) §2).
- **Later, each a small wave after CW6:**
  - **skybox:** a dome or cube carrying a picture, for exteriors and the views through windows;
  - **balcony:** a slab with a railing, with a façade behind;
  - **hillside:** sloped ground from a height map (MoGe's relief as the height);
  - **nature:** open ground with terrain, its trees and rocks as props (D108).

### 2.7 Cast's bench is bound clay; Clay stays free (U12)

**The pattern is Image and Cast, repeated in 3D:**

| | Free | Bound to a character, prop or place |
| --- | --- | --- |
| **Pictures** | Image | Cast's references and sheet |
| **3D** | Clay | Cast's bench |

- **Cast's bench has all of Clay's functions**, on a scratch scene bound to its profile, version or idea:
  - for a character: the figure, its skeleton, shell, rest hand, poses and motions, cameras and light to look at it, the turn test;
  - for a prop: its model, height, pivot and grip;
  - for a place: the set builder, its props, and cameras and light to judge the skinning.

  These are Stage's own engine and panels, not a copy.
- **Clay stays a free area.**
  - Cast's characters, props and places come in as cards (U11) and **follow Cast**: their body, shell, model or set is read from Cast,
    and Clay offers *Edit in Cast* instead of editing it.
  - *Make a free copy* detaches one to experiment with.
  - A free figure, mesh or set goes the other way with *Prototype ▸* (a new idea, its clay as the variant's), as a picture does.

U12's original question is answered by this: a place's set is edited in Cast's bench, and a free set in Clay.

### 2.8 One figure: the Detailed mannequin only (U18)

Every character gets a hand (its rest hand, [03](03-clay-from-a-picture.md) §3.2), so the Simple dummy has no job left. **It is
retired.**

- Every figure is the Detailed one: ♀ or ♂ from the character's sheet, the stage's choice for an unbound figure.
- Existing figures with `detail: null` migrate on open.
- What the Simple dummy did moves over:
  - blocking: the Detailed figure, with its shell hidden;
  - the turn test: S4 already moves it;
  - the hand marker for held props: the Detailed hand.
- CS1 measures the cost of many figures at once (the GLB is heavier than the boxes).
- S3's neck on the Simple dummy falls away. ×1 being an adult (U16) still holds, for the fit and the Detailed figure.

### 2.9 Poses fitted to each character: a pose editor in Animate (U18)

A pose today is the default skeleton's joint rotations. On Mara's proportions the same rotations put the feet through the floor,
the hands off the hips and the head somewhere else.

- **A pose becomes rotations plus contacts.** A contact is a foot on the floor, a hand on a hip, a prop or another figure, or the gaze
  on a target. On a character's skeleton the rotations are applied first; then an IK pass restores the contacts, with the feet locked
  where they were planted. Motion clips are fitted the same way, frame by frame.
- **The pose editor in Animate › Clay** opens on a figure with *Edit the pose…* (button and right-click). It shows:
  - the pose on the character's shell;
  - the contacts as pins, each moved by dragging;
  - the joints with their gizmo, as the Pose tab has today.

  *Save for ‹character›* keeps the fitted pose in the character's own pose library, which the starter poses and clips fall back on. The
  same editor is in Cast's bench (§2.7), where a character's library is built.
- **Spike E39** comes first. It takes the starter poses and motion clips onto Mara, Ines, a child and a heavy build, and measures foot
  sliding, contact error and limbs passing through the body. It decides whether contacts and IK are enough, or whether clips need a
  retargeting model (licence read against D17 first).

### 2.10 Skeleton changes in a shot are deliberate (U19)

**The skeleton can be keyed.** A **skeleton key** on a figure's timeline track says: from this frame, the figure's body is this one,
reached over a transition (0 frames for a cut, n frames for a change in between). Between keys the body's factors are interpolated. This
covers a character who grows or transforms, and a correction from a frame on.

When the Cast skeleton changes under a shot that was already rendered, its character layer shows *the skeleton changed*, with two
choices and nothing done by itself:

- ***Re-render with the new skeleton:*** the whole guide again, then the layer;
- ***Apply from a frame…:*** a skeleton key at the playhead. Only the segments after it are rendered again; chained Wan Animate (D111)
  resumes at the key's segment.

The guide stamps the body's hash per segment, so the layer knows which segments are stale.

## 3. The order, as a workflow (U14 → Q30)

**Each stage ends with something to use** in your own work, and each builds on the one before.

| Stage | What you can do when it is done | Waves | About |
| --- | --- | --- | --- |
| **1 · The characters you have animate right** | Nothing new to learn: Mara's and Ines's next renders have one body in the guide, relaxed hands, a neck, and feet at their size. Cast's *Test it* shows the guide the shots use. The Simple dummy is gone | CW0, CS1 (with E37 on A1's walk and sit) | 1 week |
| **2 · Tune a character's body in Cast** | In Cast › a character › *Skeleton…*: make the shell from the animation reference, see the skeleton inside it, drag a joint, set a length in centimetres, pick the rest hand, and watch the guide walk with no GPU. In Clay the figure is the shell, and the passes are the shell's. A skeleton change mid-shot is a key on the timeline, or a re-render | E36, CS2, CS3 | 2½ weeks |
| **3 · Poses fit every character** | In Animate › Clay a pose or a clip put on Mara keeps her feet on the floor and her hands where they belong. *Edit the pose…* fixes the rest and saves Mara's own version | E39, AP1 | 1 week |
| **4 · Try ideas freely** | Image stays free. *Prototype ▸* on any result copies it into a new idea on Cast's Ideas board. What Image makes for an idea is listed on its bench; *Make the clay ▶* gives a variant its figure (and, minutes later, its shell); *Keep ▶* makes it a Cast character | CW1, CW2 | 1 week |
| **5 · Cast's bench is bound clay, Clay is free** | Props get their model at a real height. The line-up compares ideas in 3D. In Clay, Cast's characters, props and places are cards that follow Cast; experiments stay free until *Prototype ▸* | CW3, CW4, CW5 | 1½ weeks |
| **6 · Places from a picture** | In Cast › a place, *Build the set ▶* gives a room or a street fitted to the picture, the picture skinned onto it, and what it never saw filled. In Clay the set is bound, and the final shot uses it as its plate. Then the later kinds: skyboxes, balconies, hillsides, nature | E38, CW6, CW7 | 2½ weeks |

About 9½ weeks in all, the spikes included.

**When it is all built, a character's way from an idea to a shot:**

1. **Image** (free): generate.
2. ***Prototype ▸*** makes an idea, with variants.
3. ***Make the clay ▶*** gives the figure, and then the shell.
4. **The skeleton bench:** check the skeleton inside the shell, tune it, watch the guide.
5. ***Keep ▶*** makes a Cast character.
6. **Clay** (free): stage it with Cast's cards.
7. **The pose editor:** fit the poses to the character.
8. **The final shot,** whose guide is the character's own body.

**Why this order and not another:**

- **The skeleton first** because it is wrong in the shots being made now, and every later stage stands on it. The ideas, the line-up and
  the shell all show the figure.
- **Poses before ideas** because a tuned skeleton is only useful once poses fit it.
- **Places last** because they are the largest piece (E38 plus about 7 days), and they depend on nothing above except Cast's bench.

**The other orders, if you prefer:**

- **(b) Ideas first** (stage 4, then 1–3, 5, 6): the fastest way to the prototyping feel, but Mara's shots stay wrong for about two
  weeks longer.
- **(c) Places first** (stage 6 after stage 1): the largest piece early; the ideas board waits.

## 4. The revised waves

| Wave | What it builds | GPU | Days |
| --- | --- | --- | --- |
| **CW0 · Fixes and bridges** | as [05](05-plan.md) §2 | no | 1.5 |
| **CS1 · One figure, one body** | the Simple dummy retired and its figures migrated (§2.8); the Detailed figure follows the whole fit (S1); a rest hand on every character (S2); ×1 an adult (S3's rebase, U16); the turn test on the shots' guide (S4); the feet, elbows and knees fitted (S5, S6); the fit's pull (S7); the A-pose check (S8); E37's steps 1–3 on A1 | yes (rig) | 4 |
| **E36 · The shell and the skeleton inside it** | Pixal3D shells of A1's two and six new characters; the skeleton fitted in the shell against the 2D fit; proximity against heat-diffusion weights; the guide's landmarks on the shell | yes | 1.5 |
| **CS2 · The skeleton bench** | [03](03-clay-from-a-picture.md) §3.2 with §2.4: the shell job from the reference, the fit in the shell, the x-ray front and side pane, the reference and guide panes, the parts panel, the refit route, *Fine-tune the skeleton in Cast…* from Clay, `shadow_proxy` filled | yes (the shell) | 5 |
| **CS3 · The shell in the shots, the skeleton over time** | the passes from the shell, the pose pass's landmarks (§2.5); skeleton keys on the timeline, *the skeleton changed* with its two choices, the guide's hash per segment (§2.10) | yes (rig) | 4 |
| **E39 → AP1 · The pose editor** | §2.9: E39 first; then contacts and IK on every pose and clip, the pose editor in Animate › Clay and Cast's bench, the character's pose library | yes (rig) | 1.5 + 4 |
| **CW1 · The ideas store** | §2.1: the store, the Ideas board, *Prototype ▸* (copy, U2) with a name from the prompt (U3), variants, *Make the clay ▶* on a variant, *Keep ▶* | no | 3 |
| **CW2 · Lineage from Image** | §2.2: `for_idea` on results, *Made for this idea*, *Add as a variant* | no | 1 |
| **CW3 · Bound clay, free Clay** | §2.7: Cast's bench on Stage's engine for all three classes; Clay's cards follow Cast (U11), *Edit in Cast*, *Make a free copy*, *Prototype ▸* on Clay's free objects | no | 3 |
| **CW4 · Props** | Pixal3D's model, a height in metres, the prop's bench | yes (rig) | 1.5 |
| **CW5 · The line-up** | as [05](05-plan.md) §2 | no | 2 |
| **E38 → CW6 · The set builder** | as [05](05-plan.md) §2, in Cast's place bench | yes | 3 + 7 |
| **CW7 · Places in Clay, the set as the plate** | as [05](05-plan.md) §2 (U10, U11) | yes (rig) | 2.5 |
| **Later · More set kinds** | skybox, balcony, hillside, nature (§2.6) | — | — |

## 5. Settled the same day

The author, 2026-10-25: "I agree with your proposals in 06, Q30 is yes to all three questions."

- **Q30 → D137:** the order of §3, the skeleton first. Stage 1 (CW0, CS1) started.
- **U8's reading** (§2.5) is confirmed: the guide's points sit on the shell, and the hands come from the hand rig.
- **E33's leftovers are deleted** (rule 1): `engine/tools/e33` (12 GB) and TripoSR's and DINO ViT-B/16's Hugging Face downloads (2.3 GB).

## 6. Built

| Wave | Built | Where it is recorded |
| --- | --- | --- |
| **CW0 · Fixes and bridges** | 2026-10-25: CB1–CB4 (parenting works), CF17's labels, *Add to Cast* with versions, the reference set's pictures in Cast, *Make it a Cast prop ▸* on every mesh, the Bin's Meshes filter and Cast verbs, Clay's Meshes named by source | journal 2026-10-25 09:20; `img/cw0-*.jpg` |
| **CS1 · One figure, one body** | 2026-10-25: S1–S8 and U18 (the Simple dummy retired); E37's steps 1–3 on A1 as its rig, 11/11 — the guide's hand at the wrist (0.033 → 0.002 of the height), Wan's hands nearer the reference (Mara's reach 0.140 → 0.115, the reference 0.106) | journal 2026-10-25 10:16; `img/cs1-*.jpg` |
