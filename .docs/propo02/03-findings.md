<!-- markdownlint-disable MD013 -->
# 03 · Findings — what got in the way, and what the scene still lacks

The register P1… is what this build met. It is written for the broadening study the author asked for: each item names the control, what it did, and the
kind of change the study might weigh (a question, not a decision). Earlier walkthrough numbers (W…, M…) are cited where the finding is the same one.

## 1. The register

| # | Where | Finding |
| --- | --- | --- |
| P1 | World › Make (casting) | **Four pictures, one picture.** A 4-count casting with FLUX.2 dev gave four near-identical frames: the same pose, framing, light and crop (`img/03-casting-done.png`); the set picture's four likewise (`img/05-place-build-candidates.png`). The count is "one seed each" with everything else held; nothing varies the framing, the lens, the light or the words across the four. An exploration tool would spread the four on purpose. |
| P2 | World › Look | **The Look-words chips are their own names.** "painterly storyboard" appends the words *painterly storyboard*; the mood chips the same. The Library behind them is one-word entries, so the chips are presets with no body. The style's fragment is the only real lever and it is prose. |
| P3 | World › Make › the set picture | **The framing sentence is not obeyed** (M5, M7 again). *…nothing standing in the middle of the floor, the camera level…* gave four pictures with a café's tables in the street and the same viewpoint; the model takes no camera direction from the sentence, and nothing else offers one (a sketch, a plan, a reference). |
| P4 | World › Build › The set | **The set is almost all Fill.** After the fit the road, both pavements and both fronts were "100 % to fill" and only the far end *seen* (*5 faces to fill · 94 % of the set*), although the picture shows them all. The set picture ends up as the layout and the far end; what the shot sees is painted by five Fills from one line of words each. |
| P5 | World › Build › The set › Fill | **A ground Fill paints at the picture's scale.** *worn grey cobblestones* became slabs about a metre across on the 8 × 30 m road (`img/05-set-bench.png`, and shot 1's plate). The Fill does not know the face's metres; a texel is 4 cm but the painted stones are not. |
| P6 | World › Build › Animation reference | **One thing, three names:** *reference* (Build's button), *A-pose front* (the readiness line, Make's chip), *animation reference* (Build's heading). The promise "≈ 24 s" ran 35–57 s a job. |
| P7 | Shots › Clay › Figures + | **A figure lands where the centre ray hits** (W34, M10): all three at (0.68, 0, −14.6) in shot 1; on the shop front's foot in shot 2. Every placement then goes through the position fields. |
| P8 | Shots › Clay › pose keys | **A pose key is the whole pose, not a correction.** Keying a head turn at frame 135 on a figure walking a clip block stored the *stand* preset with the head turned (legs together, arms down); the walk's pose came back at the next key. And only the last joint edited survived (spine 0, neck 0, head 30 of the three set to 30). The spec's "layer keys inside it are corrections" (proto01_UI2 04 §3.2) is not what the editor does. The glance became a two-second stop that glides along the path. |
| P9 | Shots › Clay › the path | **A path is only floor clicks.** No numeric point, no edit of a point after the click, no snap to the pavement or the kerb; a click on a front lands on its foot. The driver had to aim its clicks from calibration clicks read back through the API — a person would aim by eye and get what they get. |
| P10 | Shots › Clay › Apply | **A clip lands at the playhead,** silently: shot 2's first walk went to frames 96–174 of a 0–96 shot because the playhead was at 96. |
| P11 | Shots › Clay › Key object | **It keys whatever is selected:** a right-click in the viewport had selected the set, and *Key object* put a key on the set. |
| P12 | Shots › storyboard, header | **Shots have no names.** Both are *Shot*; the header reads *1 · Shot* on the second one; no name is asked at *New shot*. |
| P13 | Shots › header › scene | **Re-scening leaves stages behind.** Each *New shot in a new scene* makes a bare stage ("Scene"), and binding the place makes another; four stages exist for two shots. |
| P14 | Shots › Clay › Motion library | **The library has walks and idles, nothing for the story:** no look over the shoulder, no hurried walk, no push through a door; speed is six fixed steps (×0.5 … ×2); Walk_Loop at ×1 is a 0.75 m/s stroll. |
| P15 | World › Characters › readiness | **"carried" is read from one phrasing:** *a folded newspaper under his arm* raised *⚠ carried*; *a canvas shopping bag in each hand* did not. |
| P16 | Shots › Performance › Make the final shot | **The final's size, fps and plate source are told, not offered:** 848×480 at 16 fps from the built set. The dialog states them; nothing chooses them. |
| P17 | frame | **The Shots tab reopens at Flow,** not at the level the shot was left (Clay), after a trip to World. |
| P18 | World › Characters › Build › Body | **The fit guesses ♀ 1.75 m for everyone** (M9 still): the man and the elderly woman alike; set by hand. |

| P19 | Shots › Performance › the extras | **The passers-by vanished.** Both extras were performed only on the frames they are in view (the man 112–160, the woman 81–160: a good economy), but their mattes cover nothing (`cover_min 0.0`, every frame a stray, the BiRefNet retry no better) and the composition dropped them. Their takes read *done · 1✓ 2✓ 3✓*; the finished shot has one person in it. The woman's first take shows her standing full-frame in a studio with a second small figure walking away — Wan Animate on a far, small figure (W46 again; the D163 window did not take: `window []`). |
| P20 | Shots › Performance › the plate | **Black sky.** The street set has fronts 3.47 m high and nothing above them; the plate's top corners are black (`img/16-shot1-render-sheet.png`). A street needs a sky or the picture's own upper storeys. |
| P21 | Shots › Final | **The glance reads as a stand.** In the render Nora stops at frame 135, hands at her sides, the head turned a little; the walk resumes after. The over-the-shoulder look the scene asked for is not there (P8). |
| P22 | Shots › Performance › identity | **Nora scores 0.19,** the lowest of the three, in a ×1.9 window, and the row only says *low*. At 848×480 her face is a few dozen pixels for most of the shot; the two face passes (4–5 min each) ran and the number stayed. |

| P23 | Shots › Final | **Shot 2's Final showed shot 1's composition.** After shot 2's assembly, rail › Final opened on *shot · 161 frames at 16 fps* with shot 1's layers (the man, the woman) under shot 2's URL; *Mark the shot final* read *no clip yet — Make clip ▸*. A trip to Performance and back, then a reload, brought shot 2's own. (W50 / W53 for stages that are not shared.) |
| P24 | Episode | **A cut before the assembly, and no reason when it is disabled.** *Assemble from the Flow…* is greyed until *New cut…* is used (*no cut open*), and stays greyed with the cut open; its hover says only what it would do. |
| P25 | Shots › Flow, Episode | **A Flow made from the storyboard has no route.** *＋ New shot* adds Shot nodes with no edges and no Start node, so *Assemble from the Flow…* has nothing to walk; the cut was made with each shot's *+ Add to the end of the cut*. |

## 2. What the scene still lacks

- **Pedestrians as a place's own life.** The street's faces offer *Crowd ▶* and *Walkers ▶ (experimental)*; the build performed two extras instead
  (each a Wan Animate layer). Both are "a few pedestrians" — the study should say which is the default for a street.
- **A glance while walking** (P8, P14). The scene's middle beat is the one Clay cannot block as a correction.
- **The door.** Shot 2 walks Nora into a painted front; there is no door to open, no threshold, no interior. A place is one set picture and its fills.

## 3. What the performances and the cut showed

- **Shot 1** (`img/16-shot1-render-sheet.png`): Nora walks the street toward the leading camera, the coat, scarf and bag as cast; the set's fronts
  pass on both sides; she stops at 5.6 s with a slight head turn and walks on. No passers-by (P19), metre-wide slabs (P5), black top corners (P20),
  her face small and scored *low* (P22).
- **Shot 2** (`img/18-shot2-render-sheet.png`): Nora walks across the pavement, back to the camera, to the pharmacy front and stands at the wall for the
  last second. It reads as "walks up to the shop", not "storms in": there is no door to open and nothing behind it.
- **The cut:** the two finals end to end, 14.08 s at 24 fps, rendered in 11 s; no sound. The Flow could not assemble it (P25).
- **The author's look (2026-11-03):** "this isn't very good — I'm assuming this is a draft created as an input to the final version. The
  passers-by are almost completely invisible, the street plain cuts into the main character's legs on the frontal shot. There are no shadows and
  everything feels like it is a computer game from the '90s." Three more findings from it:

| # | Where | Finding |
| --- | --- | --- |
| P26 | Shots › Performance › the assembly | **The road cuts her legs.** In shot 1's first 80 frames Nora's shins and feet vanish below the road's far edge (`clips/clp_2709fd56/master/000040.png`): she walks at z −14.6 … −12 against the set's far end at z −15, where the road face ends in a black band before the end face, and the assembly's depth test hides her behind it. |
| P27 | Shots › Performance | **No shadows.** The Shadows layer stayed at *passes ready*: *Perform the owed layers ▶* did not count it, the assembly's stack held only the figures, and nothing on the final said a layer was left out. The plate itself has no light either — its faces are Fills asked for *even light*, and the Look's low sun reaches nothing. |
| P28 | the product path | **There is no later "final version".** The layered final is made once at 848×480 / 16 fps (P16) and Final renders that composition; the Draft tier (D18) is the only tier the path took, and no upscale or higher-size pass was offered on the way. The '90s look is the built set as the plate: five flat Fills (P4, P5), no sky (P20), cut-out figures without contact shadows (P27). |

- **The GPU time:** about 50 min over 16 runs (the engine's cold start, three castings, nine reference makes, five fills, two set-picture runs, eight
  Wan Animate batches, four mattes, two face passes) for 14 s of picture.
