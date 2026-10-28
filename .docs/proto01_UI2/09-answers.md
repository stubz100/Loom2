# 09 · The author's answers → D157

The author, 2026-10-28: "So far, I agree with all of your proposals." Then the answers to [07](07-plan.md) §5:

| # | The question | The answer | What it changes |
| --- | --- | --- | --- |
| Q1 | Logline and synopsis | **the synopsis kept as a Notes field; the logline dropped** | the Project menu gets *Notes* (the synopsis, moved from `world.json`); the logline goes |
| Q2 | One stage per shot or per scene | per scene, one shot per scene by default (as recommended) | — |
| Q3 | Look and Sketches in World's rail | yes | — |
| Q4 | Animation templates | the project's, with *Save to my library* | — |
| Q5 | Image to video | kept as a Performance method fed by a still from the clay | — |
| Q6 | What a new version carries | **the sheet, the body, the A-pose references and the model, as recommended; and the LoRA and Expand taken out altogether**: "it was supposed to be trained on a lot of images, but now we use clay for keeping the character consistent" | §1 |
| Q7 | The ideas store | folded into draft entities and Sketches | — |
| Q8 | Episode's closed lists | opened when its wave touches them | — |
| Q9 | Beside or in place | beside (`?ui=2`), switched at parity | — |
| Q10 | The Library's light, camera and pose entries | Clay's presets; **and the light templates adjustable with a full editor**, as the pose has: "clay already has a skeleton pose designer, a few light templates should also be good" | §2 |
| Q11 | The Shots board | kept as the Flow's *List* view | — |
| Q12 | Voice in the character's header | yes | — |
| Q13 | The order after U2 | World first | — |

"You can start on the U0 fixes": U0 began the same day.

## 1. No Expand, no LoRA (Q6)

The coverage run (*Expand*: a plan of shot sizes × angles × expressions, 36 cells by default) and the character LoRA (training on the reference set,
the trigger, the auto-slot in prompts, the identity check) leave the design. Clay carries the identity from the A-pose references and the body.

**In World ([03](03-ui-world.md)):**

- *Expand ▶*, *a coverage cell* and *Train on the references ▶* are gone from the verbs and the framings;
- *LoRA* is gone from the readiness line and the Inspector;
- the character's references stay as Make's references (they still guide the pictures), with no count to reach.

**In Image's Make inside World:** no LoRA slots. A model's own LoRAs (the Lightning and Turbo LoRAs of its presets) are part of the model, not a choice,
and stay.

**In the backend ([06](06-backend.md) §6, a new G16):** these retire when the old shell does (U8), because the old UI still uses them during the
transition:

- the `train_lora` job, `trainer.py`, `loras.py` and the `story/loras/` registry;
- the LoRA check;
- `ProfileVersion.lora` / `trigger`;
- the mentions' auto-LoRA;
- Expand (`plan_expand`, `expand_spec`, `PRESETS`, the `expand` route) and `coverage_cell`;
- the trainer's venv in `scripts/setup.ps1`.

The weights and the trainer's checkout are deleted then, as unneeded weights are (rule 1).

## 2. Lights with an editor (Q10)

Clay's lights become what its figures already are: **templates and an editor**. [04](04-ui-shots.md) §3 now reads:

- **The templates:** a few ready lights, from today's Window, Sun and Lamp and the Library's lighting words (golden-hour rim, overcast, moonlight,
  candle, neon rim, studio key and fill, backlit). Each is a light with its kind, colour and settings.
- **The editor**, on the selected light, as the pose editor is on a figure:
  - a gizmo in the viewport for position and aim;
  - colour by temperature (K) or by picker;
  - intensity;
  - size and softness;
  - falloff and cone (for a spot);
  - shadows on or off and their softness;
  - the words it gives the shot's pictures, editable.
- *Save as a light template…* adds the light to the templates, in the project or the author's library (as animation templates, Q4).
- Lights can be keyed on their track (a flicker, a door opening), as today.

Today's `LightControls.tsx` (Window / Sun / Lamp, sliders, colour) is the start; the gizmo is the Stage engine's existing transform gizmo.
