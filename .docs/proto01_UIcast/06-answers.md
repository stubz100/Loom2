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

**As built (CW1–CW2, 2026-10-25).**

- **The store.** `orchestrator/loom2/ideas.py` keeps `story/ideas/<id>.json` with a revision; the routes are under `/story/ideas`.
  - A variant is a copy on the idea's own album page, "‹name› · idea". Its `made_from` is read from the source: the picture, its prompt,
    model and seed, and `for_idea`.
  - A name left out is the prompt's first noun phrase ("woman in a yellow raincoat").
  - Deleting an idea keeps its page and pictures in the album, as deleting a profile does.
- **Cast's panel** has a *Cast · Ideas* switch above the class chips. The Ideas board lists each idea with:
  - its picture in focus;
  - its variants' count;
  - its clay's state;
  - *kept ✓* once kept.

  A picture dropped on a row is a variant; dropped on the list, it starts an idea of the class shown.
- **The idea's bench:**
  - the picture in focus with its prompt, model and seed;
  - the verbs: *Make the clay ▶*, *Keep ▶*, *Keep as a new version ▾*, *Explore in Image*;
  - the variant strip (a click puts one in focus, the right-click keeps it or removes it);
  - the clay;
  - *Made for this idea* (newest first, each with *＋ variant*).

  The Inspector edits the name, the class, the note and the variant's note.
- ***Make the clay ▶*** (a character's variant) runs three jobs one after another, each queued when the one before lands:
  - the A-pose picture, drawn by the clay-reference model from the variant as reference 1, with the subject and CA0's reference
    sentence;
  - D104's fit on it (an arms-down picture stops, D140);
  - Pixal3D's shell, front-on as CS2 makes it; `full` only, so in `open` the figure is the clay.

  The variant's `clay` follows each step. A failed or cancelled job marks it *failed*, through a queue hook on the job's origin. A
  prop's model and a place's set come with CW4 and CW6.
- ***Keep ▶*** makes a new Cast profile, or a new version of one of the same class:
  - the hero is a copy of the variant;
  - the sheet is drafted from the prompt (the subject phrase is the appearance, what it wears the outfit);
  - the clay is carried: the A-pose picture is copied onto the version as its animation reference, with the fitted body and its points,
    and the shell;
  - the version records `from_idea {idea_id, variant_id}`, and the idea records `kept`.

  Cast then opens on the version.
- ***Prototype ▸*** offers *New character / prop / place idea* and *Add to an idea ▸* (made-for first, then the newest). It is:
  - the first entry of a picture tile's right-click, which the loupe shares;
  - a hover button 🧪 on the Catalogue's and Image's tiles;
  - in the Bin's right-click;
  - a *Prototype ▾* button in the Inspector.
- **CW2.**
  - *Explore in Image* sets Image's For chip on the idea (Image is for a shot or for an idea, not both), puts the variant as reference 1
    and its prompt as a text prompt.
  - Every job submitted while the chip is on carries `payload.for_idea` on its own origin: Generate, Expand, a new angle, Re-run,
    Variations.
  - The finisher lists the results on the idea (`made_for`), and the assets' origins keep it.
  - *Back to ‹idea›* ends the chip.

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

1. **The shell.** Pixal3D on the A-pose reference, scaled to the height (D110). This is E23d's proxy source. *As built (D138, D139):* never
   stood upright (the smallest box tilts arms held out), its +X the character's left, bound by bone heat; and **only from an A-pose
   picture** — the reference fitted, its arms clear of the body. Arms held against the body come out fused to it (A1's Mara and Ines), so
   *Make the shell* waits for an A-pose, and a shell made from an arms-down picture says so.
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

**As built (CW3–CW5, 2026-10-25; D142).**

- **The bench is Clay opened for the Cast version** (D142).
  - *Bench ▶* is in a character's body row and a prop's 3D model section, and on the profile's right-click.
  - It opens Animate › Clay on a **bench stage**: `purpose: bench`, with `bound` naming the profile and version. The stage is made once and
    kept, so the camera and light the author sets stay.
  - A character's bench holds its figure, bound (body, shell, poses). A prop's bench holds its model at its height, beside an unbound
    1.75 m figure for scale.
  - A chip in the Shot section says *Bench: ‹name› v1* with *Back to Cast*.
  - Benches and the line-up stay out of `GET /stages` (asked for with `?purpose=`) and out of the stage picker.
- **Clay's cards follow Cast.**
  - Figures' "+" lists Cast's characters first. A click adds the character's figure, bound and named, or selects it when it is already
    there.
  - *Edit in Cast* is the bound figure's and the bound mesh's way to Cast.
  - ***Make a free copy*** puts a copy beside it, free, with the body and shell, or the model and height, as they are now.
  - ***Prototype ▸ a new idea*** on a free figure or mesh makes a character or prop idea. Clay's view of the object alone is its picture
    (on the idea's page, lineage to the model). The object is its clay: a figure's body and shell, or a mesh's model and height. *Keep ▶*
    carries it, a body without an A-pose picture counting as fitted by hand.
- **Props have a height** (CW4, 03 §4).
  - `ProfileVersion.height_m` is prefilled from the prop's name and look by `sizes.prop_height` (143 common things; a cup 0.1 m, a door
    2.1 m), else 1 m. It is edited in the prop's 3D model section.
  - `StageObject.height_m` scales a mesh's model to that height: Cast's for a bound one, the author's for a free one (the mesh's editor).
  - Not built: the pivot and the grip (held props keep D129's hand placement).
- **The line-up** (CW5, 02 §7):
  - *Line-up ▶* on the Cast board lines up the characters and props shown, twelve at most. On the Ideas board it lines up the ideas picked
    (Ctrl-click), else those shown that have clay.
  - It makes the project's one line-up stage (`purpose: lineup`, made again each time): side by side at their sizes, before a wall
    marked every 0.5 m, with a camera framing them. Clay opens on it.
  - The chip offers *Pose all ▾* (stand, walk, sit, wave, point), *Send to a stage ▾* (a new stage, or one of the project's: the
    things copied where they stand; a second figure of a character there stands free) and *Back*.
  - Not built: a place's set in the line-up (CW6), and the textured shell as an alternative to the clay one.

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

**As built (AP1, 2026-10-25; E39 → D141).**

- **Feet on the floor (AP1a).** Every pose preset and every clip put on a figure stands on that figure's feet. A preset gets the drop that
  sets its lower foot on the floor (a pose's `ground`). A clip gets the vertical contact through each stance. Either way, a foot still
  under the floor is bent up by leg IK.
- **The pose editor is Animate's Pose.** The pill over the viewport, or the figure's right-click, opens it on the figure's shell; the
  joints keep their gizmos.
- **The contacts are pins.** A pinned hand or foot is held at a point in the figure's own space; a red ring marks it in Pose.
  - When the hips, the spine or another limb turns, the pinned limbs bend back onto their pins.
  - The limb the author turns or drags takes its pin along.
  - The IK keeps the limb's twist: knees bend forward, elbows back.
- **Where to pin.** The Poses panel has a *Pins* row: a toggle per hand and foot, and *Unpin*. *Pin the feet* and *Pin the hands* are on
  the right-click. Mirror swaps the pins; a preset clears them.
- ***Save for ‹character›…*** keeps the pose on the character's Cast version, in `ProfileVersion.poses`, with its drop and its pins.
  - A new version takes the poses with it.
  - A pose saved under a starter pose's name (*crouch*) is what that preset gives on the character's figures.
  - The character's other poses appear beside the presets.
- **Cast's bench lists the library.** Each pose can be deleted there. Editing a pose in the bench waits for CW3, which puts the bench
  on Stage's engine.
- **Not built.**
  - Contacts to a prop or another figure, and the gaze: a pin holds a point in the figure's space.
  - Clips falling back on the character's poses: the contact fits clips frame by frame.
  - An automatic arm clearance: the sitting hands E39 found inside a broad shell are set with hand pins.

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
| **CS3 · The shell in the shots, the skeleton over time** | 2026-10-25: a bound figure is its shell in the viewport and every pass (clay, depth, masks), the hand rig's hands at its wrists (the mittens folded in), the guide's face and feet landmarks on it; every guide (the shots', the bench's, the turn test's) drawn on it; skeleton keys on Clay's timeline (*Hold the skeleton from here*, *Cast's skeleton from here*, a transition); a final's character layer stamps its body per frame — *the skeleton changed* with *Re-render with the new skeleton* and *Apply from the playhead…* (only the batches after it again). D139: the shell only from an A-pose picture. Rig `scripts/cs3_acceptance.py` 9/9 and `--apose` 4/4 | journal 2026-10-25 (CS3's entry); `img/cs3-*.jpg` |
| **D140 · The fit on an A-pose, the bench in two panes** | 2026-10-25: the fit (and *Fit again*) only on an A-pose — an arms-down read fits nothing; the prompt asks for open hands, the wrists straight; the whole hand measured and not kept (SDPose reads it 12–24 % short of the palm's estimate); *From a picture ▾* reads the rest hand from a reference-set picture; the figure pane folded into the reference pane (the shell in x-ray and the skeleton over the picture, *side* in 3D); a shell placed by its picture again (it lies on it; 82/96 joints inside). Rig `cs3_acceptance.py --fingers` | journal 2026-10-25 13:50; `img/d140-*.jpg` |
| **E39 · Poses and clips on characters' skeletons** | 2026-10-25 → D141: ten presets and ten starter clips on seven skeletons; slides 0 cm; the deep knee bends miss the floor by 3–7 cm already on the default adult, proportions move it; a vertical contact plus leg IK puts every foot within 0.3 cm; hands through the body only sitting on broad or dressed shells — contacts and IK, no retargeting model | journal 2026-10-25 14:05; `img/e39-*.jpg` |
| **CS3 · The shell in the shots, the skeleton over time** | the passes from the shell, the pose pass's landmarks (§2.5); skeleton keys on the timeline, *the skeleton changed* with its two choices, the guide's hash per segment (§2.10) | yes (rig) | 4 |
| **AP1 · Feet on the floor, the pose editor** | 2026-10-25 (§2.9 as built): AP1a — presets and clips on the character's feet (the pose's drop, the stances' vertical contact, leg IK); AP1b — pins on hands and feet held by twist-keeping two-bone IK in the figure's own space, red rings in Pose, the Pins row; *Save for ‹character›* into the Cast version's own poses, a starter pose's name standing in for the preset; the bench lists them | no | 1 |
| **CW3–CW5 · The bench, Clay's cards, props' height, the line-up** | 2026-10-25 (§2.7 as built, D142): *Bench ▶* opens Clay on a bench stage bound to the version (a character's figure; a prop at its height beside a 1.75 m figure); Cast's characters as figure cards; *Make a free copy*; *Prototype ▸* on free figures and meshes; `height_m` on props (from their words) and meshes; *Line-up ▶* on both boards with *Pose all* and *Send to a stage* | no | 1 |
| **CW1–CW2 · Ideas** | 2026-10-25 (§2.2 as built): the ideas store and its routes; Cast's *Cast · Ideas* switch, the board, the idea's bench and Inspector; *Prototype ▸* on every picture (copied, named from the prompt); *Make the clay ▶* (the A-pose picture, the fit, the shell, chained); *Keep ▶* (a profile or a version: hero, drafted sheet, clay, `from_idea`); Image's For chip on an idea, `for_idea` on the results, *Made for this idea*, *＋ variant* | no (the clay's jobs: yes, through the queue) | 1 |
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
| **E36 · The shell and the skeleton inside it** | 2026-10-25 → D138: eight Pixal3D shells (A1's two, six new arms-out references); bone heat the weighting; shells never stood upright, +X the left; 85 / 96 joints inside; placing by the picture's box tried and not kept (the box kept in the GLB for CS3); E37 step 5 run | journal 2026-10-25 11:42; `img/e36-*.jpg` |
| **CS2 · The skeleton bench** | 2026-10-25: *Skeleton…* in Cast (and from Clay) — the reference cropped with SDPose's rings and the figure's dots, the red ticks, both draggable; the figure or the shell in x-ray with the joints outside ringed; the guide on six motions with the onion skin; *Fit again* without a job (locks, SDPose's read kept), *Make the shell*, the parts in centimetres with locks, the carriage, the hands at rest; a bound figure's shadow from its shell | journal 2026-10-25 11:42; `img/cs2-*.jpg` |
