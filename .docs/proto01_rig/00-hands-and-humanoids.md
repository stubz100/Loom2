# proto01_rig · Rigging the hands, and humanoids that are not human

Status: **proposal, 2026-11-04**, for the author's answers (§7). Nothing is built. Read from the code at `055315e`.

## 1. The request

The author, 2026-11-04, after the shells' doubled hands were fixed:

> Initially we wanted to create a rigging screen, where we can allocate the joints to the correct place — perhaps we should think about
> this, particularly for the hands. Bear in mind that some characters will not be human — only humanoid, they should also be able to pose
> and move. Hands can also vary in size and shape — ghosts and ghouls have large hands with elongated fingers, dwarfs have chunky fingers, etc.

## 2. What loom2 has

| Part | Today |
| --- | --- |
| **The body** | 12 joints, fitted from SDPose's 18 body points on the A-pose picture, then shaped by the body's factors (head, neck, torso, shoulders, hips, arms, legs, the elbow's and the knee's place, hands, feet). The skeleton bench is the rigging screen for it: any of the 12 joints is dragged onto the shell in the front or side view (D183, `body.joint_offsets`), the shell is bound again from the placed joints. |
| **The hands** | No joints of their own. The hand rig is the dummy's: UAL2's mannequin hand — five human fingers in the mannequin's proportions — scaled by one factor, `hands`, fitted from the palm. The rest hand is a preset with curl, spread and thumb. The shell's own hands are folded away (`055315e`; Pixal3D's hands are mittens). |
| **The guide** | The pose pass draws 21 points a hand from that rig's finger bones (D101). Wan Animate is told a scaled mannequin's hand, whoever the character is. |
| **The bench and the hands** | It shows SDPose's 21 points a hand on the reference and lets them be dragged — they correct the palm's fit and pick the rest preset; they do not shape a finger. |
| **Creatures** | Attachments — a tail, horns, ears, wings, a backpack — as rigid parts riding on a joint (CA0). No joint beyond the 12; D183 left "joints the rig does not have (a tail)" for later. The bench warns when a part leaves an adult's range and blocks nothing ("a child or a creature is the author's call"). |

## 3. What a measurement says (Followed's three characters)

SDPose's hand points on each A-pose picture, in centimetres through the picture's own scale (the shell's placement), against the rig's hand
at the character's height and `hands` factor:

| Character | palm length, picture / rig | middle finger, picture / rig |
| --- | --- | --- |
| Nora | 9.0 / 10.2 | 3.9 / 9.2 |
| Man with a newspaper | 12.3 / 14.3 | 4.8 / 13.0 |
| Woman with shopping | 6.5 / 8.5 | 5.5 / 7.8 |

- The rig's hand is 13–31 % larger than these palms even after its factor.
- **The A-pose picture is a poor ruler for fingers.** Relaxed fingers are foreshortened toward the camera (Nora's middle finger reads 3.9 cm),
  and a hand among bags is misread (the woman's right palm reads 0.4 cm wide). A small hand in a full-figure picture is 40–60 pixels.
- For a ghoul or a dwarf the difference is the **shape**, not the size: no single factor makes long thin fingers or short thick ones.

## 4. Proposal

**R1 · A hand reference picture.** A fourth reference beside the A-pose's front, back and side (D161, D175): *Hand* —
"‹character›'s right hand alone, palm to the camera, fingers straight and spread, plain light background". It is made in World › Make with
the character's sheet, so its words carry the shape ("long bony fingers with black claws", "short thick fingers"), and picked by hand like
the others. SDPose reads 21 points far better on a large flat hand than on a small relaxed one, and BiRefNet's matte of it gives each
finger's width.

**R2 · A hand skeleton per character.** Each hand gets its own joints — the wrist and four a finger, the 21 the guide draws — stored on the
body: the palm's length and width, each finger's three segment lengths, its thickness and where its knuckle sits, and a claw's length. The
proportions come from the hand reference, the size from the A-pose's palm. Both hands are the same unless unlinked. Five fingers by default;
four or three hide fingers (Q4).

**R3 · The clay hand, built from that skeleton.** Instead of the mannequin's human hand: a rounded palm slab between the wrist and the
knuckles, each finger tapered capsules of its own length and thickness, a claw a cone at the tip. It poses with the same presets and keys
(open, relaxed, fist, point, grip, pinch, D129's holds). A ghoul's fingers are long because its skeleton's are; a dwarf's are thick because
its thickness says so. The mannequin stays only for the animation bench's dummy, which is nobody's (D183).

**R4 · The rigging screen's *Hands* view.** The skeleton bench gains *Hands* beside the body:

- the hand reference with its 21 points, each dragged to correct what SDPose read (*Fit again* refits; *Mirror to the other hand*);
- a row per finger — length, thickness, claw — each a field with a drag and a lock, as the body's parts are;
- the clay hand in 3D beside it, with the presets to try and a prop held, so a bad knuckle shows before a shot does;
- the guide playing the *hands* clip, as the bench's guide pane does for the body.

Help behind a ?, every action a button or a right-click (D32, D116).

**R5 · The guide carries the character's hands.** The pose pass draws the fitted hand's 21 points, so Wan Animate is told a ghoul's long
fingers, not a mannequin's. (E62 b measures whether it listens.)

**R6 · Humanoid characters.** The body already follows the same rule — fitted, then placed by hand. For non-humans:

- a *Humanoid* switch on the character widens the parts' ranges (arms to 1.8, legs from 0.4, head to 3) and drops the adult-range warnings;
- a body SDPose cannot read (a ghoul's face, a troll's) starts from the parametric body, and the author places the joints (D183's drags);
- not in this proposal: joints the rig does not have — a tail that moves, wings that flap, a third arm, a digitigrade leg (Q7).

## 5. A spike first: E62

Two answers decide the build:

- **E62 a · Can the hands be read?** The hand reference made through the product path for Followed's three and three humanoids — a ghoul
  with long bony fingers and claws, a dwarf with short thick fingers, a goblin with four fingers. SDPose's 21 points and BiRefNet's widths a
  finger, checked against points placed by hand. About a dozen small GPU jobs, one at a time.
- **E62 b · Does Wan Animate listen to a hand?** The ghoul made through the product path (its picture, A-pose, body and shell), then
  waving twice: once with the mannequin's hands in the guide, once with its own. If Wan draws the long fingers either way, R5 is dropped and
  R3 serves the clay alone. One 77-frame batch each, a few minutes apiece, after the ghoul's shell (about 4 minutes).

No weights to fetch: SDPose, BiRefNet and Wan Animate are installed.

## 6. Waves, after E62

| Wave | What | Ends usable as |
| --- | --- | --- |
| **RG1** | The hand reference framing (R1); the hand skeleton fitted and stored (R2) | the body record carries hands; nothing drawn differently yet |
| **RG2** | The clay hand (R3) on shells; the guide from it (R5, if E62 b keeps it) | every shell's hands are its own shape |
| **RG3** | The *Hands* view on the skeleton bench (R4) | the author corrects a hand by hand |
| **RG4** | The *Humanoid* switch (R6) | a ghoul's arms and a dwarf's legs without warnings |

## 7. Questions for the author

| # | Question | Recommendation |
| --- | --- | --- |
| **Q1** | Fit the hands from a hand reference picture (R1), or from the A-pose picture and by hand only? | The hand reference: the A-pose's hands are too small and too relaxed to measure fingers. |
| **Q2** | One hand fitted and mirrored to the other, or both fitted separately? | Mirrored, with *Unlink* for a character whose hands differ (one claw, one prosthetic). |
| **Q3** | The clay hand built from capsules (R3), or the mannequin's hand stretched bone by bone? | Capsules: any proportion, no stretched skin, one look in every pass. |
| **Q4** | Four- or three-fingered hands: supported as hidden fingers? | Yes, a finger count a hand; E62 a shows what SDPose makes of four fingers and the guide draws only those shown. |
| **Q5** | Claws and long nails: a length a finger, or one a hand? | One a hand with an override a finger. |
| **Q6** | The *Humanoid* switch (R6)? | Yes. |
| **Q7** | Joints the rig does not have (a moving tail, wings, extra arms, digitigrade legs): now or later? | Later, a study of its own; attachments stay rigid until then. |
| **Q8** | Run E62 (GPU jobs only, one at a time, no downloads)? | Yes, before any wave. |
