# 15 · Looking at E28, E28b and E28c — props, the room cleaned up, props as 3D objects (for the author)

About 12 minutes. The files are local, under `engine/spikes/out/e28/`, `e28b/` and `e28c/` (not in git).

## 1. E28 · three ways to perform a prop (`out/e28/`)

| Clip | The prop | How it is made |
| --- | --- | --- |
| `box.mp4` | a red chest slid across the floor | **P1:** its reference cut out and put where Stage's block stands in each frame, on Stage's shadow; no generation |
| `door.mp4` | a green door opening (left), Stage's depth (right) | **P2:** a Stage shot of the first frame, then LTX-2.3 guided by the door's depth; 49 s + 147 s |
| `cup.mp4` | a white mug in Mara's hand: P1 (left), P3 (right) | **P1:** the mug's cut-out at her detected wrist. **P3:** Mara's reference made holding it, so Wan Animate draws it in her layer |

- **Check:** does the door open like a door? Measured against Stage's door it overlaps 0.79 on average, 0.61 at worst (edge-on).
- **Check:** the chest never shows a new side (it is one still). Is that acceptable for a slid or carried prop?
- **Check:** the mug: P3 turns with her hand (in 39 of 41 frames), P1 stays flat. Which reads better?

## 2. E28b · the room cleaned up (`out/e28b/`)

Your note: "all objects should be props and not part of the background" (now D108). E22's room had four objects baked into its
picture: the crate and the table the model drew, and the two grey blocks of the old room preset.

- **The empty room.** The app's own Fill (Klein, Edit ▸ AI) removed all four and their shadows in 64 s. `layers.jpg` shows the old picture,
  the empty room, the props on their own layers, and the room put back together.
- **Each object is a prop.** A Stage box was fitted to each one (`fit.jpg`), and the object's own pixels are its layer. A character in
  front of a prop or behind it is decided by Stage's depth, frame by frame.
- **The crate moved.** Mara's walk, blocked before Stage knew of any crate, went through the spot where the model drew it, and her boots
  vanished behind its corner. With the crate a prop, Stage sees it, so I moved it 0.7 m left (yellow in `fit.jpg`).

`compare.mp4` (24 fps, three panels):

| left | middle | right |
| --- | --- | --- |
| before: the objects baked into the picture | **the props as layers, Stage's shadows** | the props as layers, their own shadows (from the old picture) |

- **Check:** does the room still look like the same room?
- **Check:** shadows: the middle's are crisp (Stage's light), the right's are soft (the model's own). Which suits the room?
- **Check:** Ines on the stool and Mara walking past the crate: does each stay in front of the props?
- **Known:** a faint mark on the wall where the big block's top edge was, and a thin light seam at some prop edges.

## 3. E28c · the props as real 3D objects (`out/e28c/`)

Your note: "props should be real 3d objects - very similar to characters, but without the human skeleton" (now D109). In 1 and 2 a
prop in Stage was a grey stand-in box, and its picture was flat. Now each prop is a **3D model** made from its reference by the app's
image → 3D job (Pixal3D, 3.6–6.4 min each, made once), stood upright and placed in Stage. The chest slides and turns a quarter, and the
door opens.

- `models.jpg`: each reference beside its model from four sides.
- `compare.mp4` (24 fps; full size in `r1.mp4` and `r2.mp4`):

| left · R1 | right · R2 |
| --- | --- |
| the models themselves, rendered by Stage (no AI, instant) | the chest and the door drawn by the video model on their 3D shapes (≈ 50 s + 150 s each); the others from the old picture |

- **Check:** do the props now read as solid objects? The chest shows its other sides as it turns.
- **Check:** R1 or R2 for the chest and the door? R1 is exact and free but looks rendered: the door too dark, the grey blocks pale and
  teal. R2 looks photographic and follows the 3D shape closely (0.93 of the chest's outline, 0.89 of the door's, against 0.79 for E28's
  stand-in door), but the door comes out lighter green.
- **Known:** the models are made in the reference's camera view, so I stand them upright (the chest leaned 21°). The crate floats a
  little (its contact shadow is faint); the door casts a long shadow on the wall from Stage's light.

## Notes

| Check | Answer |
| --- | --- |
| The door's swing | |
| The chest as one still | |
| The mug: P1 or P3 | |
| The same room? | |
| Stage's or the props' own shadows | |
| In front of the props | |
| Solid 3D props? | |
| R1 or R2 (chest, door) | |
