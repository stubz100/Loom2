# 21 · Trying the Final level (for the author)

About 10 minutes. The animation editor (D114, doc 20): a final shot's composition opened inside Animate, scrubbed and played, edited
(layers, properties, masks, the lanes, effects) and rendered to a clip. Revised 2026-10-21 after the author's first look (the three notes
at the end, fixed as UX9 U1–U3).

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
  the frame** — a dashed outline with four points, which stays while her row is selected (it is the selected mask: brighter; click
  another mask's outline to select it). Drag a point to reshape it. Set its feather to 30, tick *inverted*, change the mode; the outline
  stays, the picture changes. Then the **points** tool: click five or six points around Mara's head on the frame and click the first
  point again (or double-click) to close the shape — a mask that follows her outline instead of a box; Esc drops a half-drawn shape.
  Remove with ×. **How masks work** under the list explains Add / Subtract / Intersect, inverted, feather, expand and opacity, and that
  her cut-out itself is not a mask but her *track matte* (the row's matte select), made when she was performed.
- **Check:** is the outline on the frame enough to know where the mask is? Are rectangle, ellipse and points enough for the finishing
  you expect here? (EffectCraft also has a roto brush, an object matte by a click and mask tracking — later tools if the shapes fall
  short; say which you would reach for.)
- **The lanes** under the transport: each layer a bar. Drag the end of the stool's bar inwards: it disappears from the frame after that
  time. Drag the bar itself to move it; Alt-drag slides the footage under it. Undo as before.
- **Check:** does trimming by the bar's ends read as expected? Are the lanes enough, or do you want the full timeline (keys per
  property, zoom) here?
- **Effects** (the third part): click **Lumetri Color**; set exposure to 0.5 and temperature to −20 — she warms and brightens against
  the room. Press **Before** under the viewer to see the frame without effects, again for after. Then select the Shadows row and add
  **Gaussian Blur** (blurriness 6) to soften the shadows. Each effect has on / off, reset and ×.
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
| The mask outlines on the frame: enough? The points tool? | |

## The first look (2026-10-21) and what it changed

The author's notes on the version of this document before AE3, recorded as UX9's register (journal 2026-10-21):

- **U1** — the layer mechanics are good, but it was not clear which layer the Properties / Masks / Effects sections acted on. Now the
  three are the selected layer's editor, under its row and above the next layer; the three separate sections and rail tabs are gone.
- **U2** — the chip's words ("full · cached 62 % · fetching") redrew often and flickered. Now it is the number alone, fixed width; the
  size shown and a running job are styling; the words are its tooltip. The picture also keeps one size on screen at ½ and at full.
- **U3** — a drawn mask vanished from the frame once the tool was off, and only a rectangle and an ellipse were offered. Now the selected
  layer's masks are drawn over the frame with draggable points, a points tool draws any shape, and *How masks work* explains them.
  Further tools EffectCraft offers (roto brush, object matte, tracking) wait for the author's word.
