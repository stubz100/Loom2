# 21 · Trying the Final level (for the author)

About 5 minutes. The first slice of the animation editor (D114, doc 20): a final shot's composition opened inside Animate, scrubbed and
played, then rendered to a clip. No editing controls yet — those come with AE2; this is the viewer to judge before they are designed.

## Set-up

- `scripts/dev.ps1`, then open the project `engine\spikes\out\ps5\project` (the rig's project with doc 18's shot and its composition).
  EffectCraft runs beside the orchestrator from `engine\tools\effectcraft\` (built; nothing to install).
- Animate ▸ **Clay**, open the stage; the Shot section shows the final shot's row with its layers.

## 1. Open it (≈ 1 min)

- In the final's row: **Open in Final**. The viewer switches to the **Final** level (the Clay · Performance · Final switch at the start of
  the strip; keys 1 · 2 · 3).
- **Check:** a frame of the shot appears within a second; the chip at the top right says what you see ("½ · cached 4 %").

## 2. Scrub and play (≈ 2 min)

- Drag the **slider** under the viewer. Frames at half size follow the drag; when you stop, the frame sharpens to full size and the chip
  says "full".
- Leave it a moment: the chip's "cached" count climbs as the shot fills in the background. Press **play ▶**. The first pass may run
  slower than the shot's 16 fps while frames are still arriving; the second pass is real time.
- **Check:** does the scrub feel immediate? Is the sharpening at rest noticeable or distracting? Is the chip understandable?
- **Known:** while a generation runs, the filling pauses ("· a job runs: on demand") and only the frame you ask for is drawn — one GPU
  job at a time.

## 3. Render it (≈ 1 min)

- In the final's row: **Render the finished shot**. The Dock shows the render (a few seconds on the CPU, then RIFE to 24 fps). When it
  lands, **Play ▶** plays the finished shot; the row says "rendered at revision n".
- **Check:** is the rendered clip the same picture as the viewer showed?

## 4. Make it again (optional)

- **Make the composition again** writes the composition afresh from the layers (a confirm: the edits are dropped). The viewer reloads
  at revision 0.

## Notes

| Check | Answer |
| --- | --- |
| The scrub immediate? | |
| The sharpening at rest: fine, or distracting? | |
| The chip understandable? | |
| The rendered clip matches the viewer? | |
