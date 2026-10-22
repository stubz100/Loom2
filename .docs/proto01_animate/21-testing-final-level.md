# 21 · Trying the Final level (for the author)

About 15 minutes. The animation editor (D114, doc 20): a final shot's composition opened inside Animate, scrubbed and played, edited
(layers, properties, masks, the lanes, effects) and rendered to a clip. Revised 2026-10-21 twice: after the author's first look (U1–U3) and
after the second (D116: help behind a ?, more mask tools, the Performance panel as a tree — U4–U7). Wherever a small **?** sits beside an
item, hover it for the words; nothing explanatory is written on the screen any more (house rule 11).

## Set-up

- `scripts/dev.ps1`, then open the project `engine\spikes\out\ps5\project` (the rig's project with doc 18's shot and its composition).
  EffectCraft runs beside the orchestrator from `engine\tools\effectcraft\` (built; nothing to install).
- Animate ▸ **Clay**, open the stage; the Shot section shows the final shot's row with its layers.

## 1. Open it (≈ 1 min)

- In the final's row: **Open in Final**. The viewer switches to the **Final** level (the Clay · Performance · Final switch at the start of
  the strip; keys 1 · 2 · 3).
- **Check:** a frame of the shot appears within a second; the chip at the top right is one number — how much of the shot is cached for
  playback ("4 %"); it brightens when the frame shown is the full-size one. Hover it for the words.

## 2. Scrub and play (≈ 2 min)

- Drag the **slider** under the viewer. Frames at half size follow the drag; when you stop, the frame sharpens to full size at the same
  place and size on screen (the picture fills the view either way; nothing jumps).
- Leave it a moment: the chip's count climbs as the shot fills in the background. Press **play ▶**. The first pass may run slower than
  the shot's 16 fps while frames are still arriving; the second pass is real time.
- **Check:** does the scrub feel immediate? Is the sharpening at rest noticeable or distracting? Is the chip's number enough?
- **Known:** while a generation runs, the filling pauses (the chip gets an accent border; hover: "a job runs: frames on demand only")
  and only the frame you ask for is drawn — one GPU job at a time.

## 3. Render it (≈ 1 min)

- In the final's row: **Render the finished shot**. The Dock shows the render (a few seconds on the CPU, then RIFE to 24 fps). When it
  lands, **Play ▶** plays the finished shot; the row says "rendered at revision n".
- **Check:** is the rendered clip the same picture as the viewer showed?

## 4. Edit it (AE2–AE3, ≈ 5 min)

The rail's **Layers** tab (the column scrolls there). Everything about one layer sits **under its row**: click a row and its editor opens
right beneath it, above the next layer, with three parts — **Properties · Masks · Effects**. Click the row again to fold it.

- **Layers:** the shot's layers, top to bottom — Ines, her matte, the stool, Mara, her matte, the shadows, the room. Click **Shadows**'
  eye (◉) to hide the shadows; the frame redraws without them; click it again. Right-click a row for its menu (hide, solo, lock,
  up / down, keyframes, the mask tools, trim, Before, undo).
- **Move Mara:** click her row, then **drag on the frame** in the viewer: a dashed ghost shows the offset; on release she (and her
  matte) move. Undo with the toolbar's ↶ or Ctrl+Z.
- **Properties** (the first part under her row): set **Opacity** to 50 (Enter). Press **◆** beside Opacity: a keyframe at the playhead;
  scrub a second later, set 100, press ◆ again — now she fades in between; the keys are listed with *ease / hold / linear*.
- **Check:** after each edit, does the frame redraw within a second? Is "one edit, one undo step" how you expect it?
- **Masks** (the second part): the **rectangle** tool, then drag a box on the frame around her. The mask appears in the list **and on
  the frame** — a marching outline with four points, which stays while her row is selected (it is the selected mask: brighter; click
  another mask's outline to select it). Drag a point to reshape it. Set its feather to 30, tick *inverted*, change the mode; the outline
  stays, the picture changes. **Mask fill** (the bucket) shows the masks as filled areas instead of outlines, like Quick mask in Edit;
  press it again for outlines. Then the **pen**: click five or six points around Mara's head and click the first point again (or
  double-click) to close the shape; Esc drops a half-drawn one. Remove with ×.
- **From the layer** (the scan icon): with Mara's row selected, one click — her silhouette at the playhead becomes a mask, traced from her
  matte, and it is keyed on every frame of the shot (the row says *follows*): scrub, and the outline moves with her. The same on the stool
  (its alpha) or on the Shadows layer; the Room refuses (the plate fills the frame). Set its mode to *Subtract* on an *inverted* copy to
  cut everything but her — or, simpler, use it on the Room layer inverted.
- **Follow the motion** (the route icon, or *follow* on the mask's row): draw a rectangle around the stool, press follow — EffectCraft
  tracks what is inside it from the playhead to the end and keys the shape on every frame (less than a second on the CPU).
- **Object** (the click icon): with Mara's row selected, click on her coat. EffectCraft's Object Matte cuts the layer to the thing you
  clicked and follows it across the shot (a second or two); it is an *effect* on the layer — switch to Effects to see it, turn it off or
  remove it. (Only the classical engine is installed; EffectCraft's downloadable MobileSAM would sharpen it — say if you want it.)
- **Check:** are the marching outline and the fill enough to know where a mask is? Does *from the layer* give you Mara's silhouette as you
  pictured it, and does it hold up as she moves? Is the Object Matte useful beside the track matte she already has? Anything from
  EffectCraft's roto brush (strokes to paint a matte) you would want too?
- **The lanes** under the transport: each layer a bar. Drag the end of the stool's bar inwards: it disappears from the frame after that
  time. Drag the bar itself to move it; Alt-drag slides the footage under it. Undo as before.
- **Check:** does trimming by the bar's ends read as expected? Are the lanes enough, or do you want the full timeline (keys per
  property, zoom) here?
- **Effects** (the third part): click **Lumetri Color**; set exposure to 0.5 and temperature to −20 — she warms and brightens against
  the room. Press **Before** under the viewer to see the frame without effects, again for after. Then select the Shadows row and add
  **Gaussian Blur** (blurriness 6) to soften the shadows. Each effect has on / off, reset and ×.

- **Passes** (the fourth part, D118): the four tiles — **Clean up** and **Creative** run now, **Face** and **Lip-sync** say *soon* (AE4c).
  With Mara's row selected pick **Clean up**, leave the strength at 0.10 and press **Run the pass**: a GPU job (≈ 15 min for this shot —
  the Dock shows it; the viewer keeps working). When it lands, the take appears in the list under *Original* as *shown*: the layer now
  shows the pass's frames and the viewer redraws; her transforms, masks, effects and keys stay. **✓ show** on *Original* brings the
  performed frames back; ✓ show on the take again; **×** drops a take and its frames. Try **Creative** at 0.35 on the Room layer (≈ 2 min):
  the repaint you saw in E24.
- **Check:** is the take-as-source model clear — one layer, several versions, one shown? Should a pass run on the shown take (a pass over
  a pass) or always on the performed frames (as it does now: the shown source feeds the next pass)?
- **A line on the lanes** (D118): in the Layers toolbar, **Attach a line…** lists the voiced lines of this shot's Dialogue nodes (voice one in
  Story · Flow with 🎙 first; this rig's shot has none unless you add one). A line attaches at the playhead as an audio layer bound to its
  speaker's layer: a 🔊 row in Layers and a bar with its waveform on the lanes. Drag the bar to move where the speech starts, its ends to
  trim, Alt-drag to slip; **Render the finished shot** carries the lines in the clip. × on the row removes it.
- **Check:** is a line as a layer the right feel — and is the waveform on the bar enough to place it against the picture?

## 4b. The Performance panel and the foot (D116, ≈ 2 min)

Back at the **Clay** level, the rail's **Performance** tab: the panel is now a tree of the shot's steps — **Frame** (method, image 1,
references, prompt, size, count, results, each a labelled row), **Clip**, **Final shot** (the finals, each layer in columns: kind · name ·
status · action). Each step folds by its title; the step's state and its verb sit on the title line. In the **foot**, above *Render frame ▶*,
one strip holds the shot's verbs in order — Passes · Sequence · Clip ▶ · Final… and, for the stage's newest final, Assemble · Composition ·
Open in Final · Render — so they are at hand whatever the column shows.

- **Check:** does the tree read as the pipeline? Is the strip what you meant by "above the render frame button", or should the whole panel
  move into the foot? Which, if any, of the strip's verbs should be the primary there?
- **Check:** are the dials the right few for each effect? Anything you reach for in Resolve that is missing?

## 5. Make it again (optional)

- **Make the composition again** writes the composition afresh from the layers (a confirm: the edits are dropped). The viewer reloads
  at revision 0.

## Notes

| Check | Answer |
| --- | --- |
| The scrub immediate? | |
| The sharpening at rest: fine, or distracting? | |
| The chip understandable? | |
| The rendered clip matches the viewer? | |
| Moving a layer by dragging: right? | |
| One edit, one undo: as expected? | |
| The editor under the row: plain which layer is edited? | |
| The mask outlines on the frame: enough? The pen? | |
| From the layer: Mara's silhouette as pictured; holds as she moves? | |
| Follow the motion, the Object Matte: useful? | |
| The ? everywhere instead of text: right? | |
| The Performance tree and the foot's strip: right place for the verbs? | |
| Passes: the take-as-source model clear? A pass over a pass, or always over the performed frames? | |
| A line as an audio layer on the lanes: the right feel? The waveform enough to place it? | |

## The first look (2026-10-21) and what it changed

The author's notes on the version of this document before AE3, recorded as UX9's register (journal 2026-10-21):

- **U1** — the layer mechanics are good, but it was not clear which layer the Properties / Masks / Effects sections acted on. Now the
  three are the selected layer's editor, under its row and above the next layer; the three separate sections and rail tabs are gone.
- **U2** — the chip's words ("full · cached 62 % · fetching") redrew often and flickered. Now it is the number alone, fixed width; the
  size shown and a running job are styling; the words are its tooltip. The picture also keeps one size on screen at ½ and at full.
- **U3** — a drawn mask vanished from the frame once the tool was off, and only a rectangle and an ellipse were offered. Now the selected
  layer's masks are drawn over the frame with draggable points, a points tool draws any shape, and *How masks work* explains them.
  Further tools EffectCraft offers (roto brush, object matte, tracking) wait for the author's word.

The author's second look (the same day) → **D116**, built as U4–U7:

- **U4** — "all descriptions should only appear when hovered over a small question mark next to the item": a house rule (CLAUDE.md 11)
  and a ? component; the Animate and Stage suites swept, the others follow.
- **U5** — the pen's icon; the outlines march; Lines | Fill; *From the layer* (the visible content traced, keyed over the shot);
  EffectCraft's mask tracking (*Follow the motion*) and Object Matte (a click). The roto brush stays unbuilt until asked.
- **U6** — the Performance panel as a tree of the shot's steps, rows aligned.
- **U7** — the shot's verbs as a strip in the foot above *Render frame ▶* — the builder's reading of "place it above the render frame
  button"; whether the whole panel should move is the author's call (§4b).
