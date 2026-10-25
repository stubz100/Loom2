# proto01_UIcast · Cast as a prototyping workshop: from a picture to clay, a skeleton and a set

Status: **proposal, 2026-10-25; answered the same day → D136** ([06](06-answers.md)). The author changed or extended nine of the recommendations, and
06 holds where it differs from 02–05. The build order, explained as a workflow in 06 §3, was accepted as D137 (the skeleton first);
stage 1 (CW0, CS1) was built on 2026-10-25, and stage 2 (E36 → D138, CS2, CS3; D139: the shell only from an A-pose) the same day. Read from the code at `6cafacc`.

## The request

The author, 2026-10-25:

> I'd like you to revise how Cast is currently working. Cast should be a prototyping suite, where you could easily experiment with
> different ideas for characters/props/places. Currently you do free generations in image, and I'm missing a link between a generated
> image and a clay object you are using in the first stage of animate. It could be a good place to generate a clay dummy from an image
> and fit a skeleton to it. I'd also like if places (stage backgrounds) could be generated from an image here. Backgrounds usually simple
> geometry objects, perhaps a basic 3d suite could be helpful here, where you could "skin" an image to a room or a street… The main goal
> should be the streamlining of the user workflow and unlocking creative diversity.

And, during the study:

> I like where you going with the fitting of the body to mesh when casting a character, but I'd like to go a step further - we've
> noticed during Mara's test animations that her body and the skeleton doesn't match, which causes her movement and posture to look out
> of place - like her neck missing from the skeleton, or her feet and hands look proportionately larger than her body. Her hands were
> also held in an unnatural manner, with her fingers bending outwards, which is probably because her skeleton didn't fit her model
> exactly. I should be able to do these skeletal fine-tunings here in cast

## The documents

| # | Document | What it holds |
| --- | --- | --- |
| 01 | [Today](01-today.md) | what exists from a picture to clay (Cast, Image's routes into it, Clay, picture sets, the body fit); the skeleton Wan Animate gets, measured on Mara and Ines (§1.6); seven journeys counted; the friction register CF1–CF25; six defects CB1–CB6; 15 screenshots and sheets |
| 02 | [The workshop](02-the-workshop.md) | the proposal: eight principles, ideas and variants, *Prototype ▸* on every picture, For: ‹idea› in Image, *Make the clay ▶* per class, the skeleton bench, the line-up, places, Cast in Clay, the commands; six wireframes |
| 03 | [Clay from a picture](03-clay-from-a-picture.md) | a character's clay dummy (the A-pose picture, the fit, a shell, the shadow proxy's skinning); **the skeleton: eight fixes that need nobody (S1–S8) and the skeleton bench for the author's fine-tuning**; a prop's quick and good models and its size; spikes E36 and E37 |
| 04 | [Places and the set builder](04-places-and-the-set-builder.md) | the set as a few faces with sizes (room, street, corridor, open ground; openings); the camera match from MoGe's planes; skinning by projection, bake and Fill; the built set as the final shot's plate; the editing UI; spike E38 |
| 05 | [The plan](05-plan.md) | the journeys' numbers, the waves (CS1–CS2, CW0–CW7) with days, the risks, the decisions U1–U19 with recommendations |
| 06 | [The answers](06-answers.md) | **the author's answers (D136)** and what they change: a separate ideas store, lineage instead of auto-variants, no TripoSR, the skeleton fitted inside the shell, the pose pass from the shell, Cast's bench as bound clay with Clay free, the Detailed figure only, a pose editor in Animate, skeleton keys on the timeline; the order as a workflow (Q30); the revised waves |

`img/cur-*.jpg` are screenshots of today's app on copies of four rig projects (A1, E28, CE4, SC3f), and measurement sheets from A1's
records (`cur-13` to `cur-15`). `img/ui-*.jpg` are wireframes, rendered from `mock/cast-mock.html` by `mock/render.cjs` (a static
mock, not the app).

## What was found

1. **Cast is built to fix an identity, not to try ideas.** A version is a full copy that drops the animation references, the model and
   the LoRA; there is no light variant and no board of ideas (CF7, CF18).
2. **A picture reaches clay by long routes, or not at all.** An Image result becomes a clay character in 13 clicks and two tab switches,
   and the result is a grey dummy with eight of the character's proportions (J1). Three takes compared in clay cost about 36 (J2). A
   room with a picture on its walls, and the character's look in clay, are dead ends (J5, J6).
3. **The pieces for both requests exist and are unused or apart.** The shadow proxy skins a mesh of the character to the figure's joints,
   but nothing sets it (`StageObject.shadow_proxy`). The set presets are geometry without a picture; the picture set is a picture without
   geometry beyond a relief; PF1's projector and Fill sit between them.
4. **Mara's skeleton faults are measured, and most are not the fit's numbers** (01 §1.6):
   - the Detailed figure's guide draws **two bodies**: the fitted dummy's points, and hands and feet riding on a mannequin that follows
     the fit only in its limbs. Each hand starts 0.033 of the height below its wrist and reaches about twice as far as the reference's
     (CB5);
   - the hands keep the GLB's **flat, fanned rest hand**, which Wan paints as fingers bent outwards;
   - the dummy's neck is short by construction, so the fit stretches it to ×2.3, and the Simple dummy draws nothing there (CB6);
   - the feet are never fitted; the references stand arms-down, though the prompt asks for an A-pose;
   - the turn test checks the Simple figure's guide, with no hands or feet, which the shots never use.
5. **Four defects worth fixing on their own** besides the two above: a broken "Go to origin" (CB1), Clay's Meshes list not updating
   (CB2), a stale help line (CB3) and a *parent* select with no effect (CB4).

## The proposal in one picture

```
Story › Cast         ┌ Characters ┐ ┌ Props ┐ ┌ Places ┐
  ideas board  ─────▶ an idea: its variants ─ Make the clay ▶ ─ the bench (clay · skeleton · set) ─ Keep ▶ a version (today's Cast)
        ▲                     ▲                                  │            │
        │ Prototype ▸         │ For: ‹idea› (Image lands variants)  └▶ Line-up    └▶ the skeleton bench: reference · figure · guide · parts
   any picture          Image › Make                                                          └▶ Clay: cards in the Scene panel
```

- **Characters:** the A-pose picture, the fit, a quick shell (TripoSR, ≈ 4 s) or a good one (Pixal3D, ≈ 4 min), bound to the skeleton.
  The skeleton bench shows SDPose's points and the figure's over the reference, the figure's bones, and the guide Wan will get on a
  short motion with no GPU job; every part is a length in centimetres with an adult range, a lock and a rest hand.
- **Props:** a quick model in seconds, the good one when kept, at a real height.
- **Places:** a set built from the picture (room, street, corridor, open ground), the picture projected and baked onto its faces, what it
  never saw filled by Klein; the built set is its own plate in the final shot.

## The numbers

| Journey | Today | Proposed |
| --- | --- | --- |
| J1–J5 (four countable) | ≈ 67 clicks, 9 tab switches | ≈ 19–23 clicks, 3 tab switches |
| J7 · the skeleton matched | 12 clicks + a GPU wait + 7 per figure and stage; two dead ends | 5–8 clicks, no tab, no GPU |
| Dead ends | J5, J6, two in J7 | none |

## The plan

CW0 (fixes and bridges) → **CS1 (the skeleton's fixes, with E37 on A1)** → **CS2 (the skeleton bench)** → CW1–CW2 (ideas, variants,
For: ‹idea›; no GPU) → E36 → CW3 (the character's clay) → CW4 (props) → CW5 (the line-up) → E38 → CW6 (the set builder) → CW7 (places
in Clay, the built set as the plate). About 8½ weeks with the spikes; the skeleton first because its faults spoil the shots made now.

## Method

- **The code** at `6cafacc`, read by three mapping passes (Cast and its routes into it; Clay and the stage engine; the body fit, the
  proxy and the picture sets), with the key claims checked by hand. File references are to that commit.
- **The clicks** by UX0's rules ([proto01_UI/03](../proto01_UI/03-ux0-review.md) §2), as in proto01_UIcomp.
- **The screenshots** from a throwaway Playwright walk on copies of four rig projects (real pictures).
- **The skeleton** measured from A1's own records: the SDPose points its two fit jobs kept, the fitted bodies, the walk shot's pose
  guide and Wan's frames (`finals/fin_d5461443/fig_m`), and Stage's renders of Mara's dummy in the turn test's pose. No GPU job was
  run for the study.
