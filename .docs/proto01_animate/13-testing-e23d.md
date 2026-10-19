# 13 · Looking at E23d — a dummy shaped like the character (for the author)

About 5 minutes. This is your idea: make the clay dummy look like the character, so Stage's shadows have her outline. The files are
local, under `engine/spikes/out/e23d/` (not in git).

## What was made

- **The meshes.** The app's image → 3D job (Pixal3D) turned each animation reference into a mesh: Mara's in 4.2 min, Ines' in 3.6 min.
- **The binding.** Stage bound each mesh to its figure's twelve joints, in the A-pose the reference shows. Each point of the mesh
  follows its two nearest limbs, so the mesh walks, sits and points with the figure. The light sees it; the camera never does.
  `proxy_check.jpg` shows the meshes as the light sees them, at three moments.
- **The test.** E23c's shot again (still camera, the window light, the same characters). Only the shadows differ:

| Panel | The shadow |
| --- | --- |
| top left | Stage's shadow of the plain dummy (E23c) |
| **top right** | **Stage's shadow of the character-shaped mesh** |
| bottom left | the character's cut-out on a flat card turned to the light (no 3D at all) |
| bottom right | the white set: the model's own shadow (E23c) |

## 1. compare.mp4 (≈ 3 min)

24 fps, the four panels above, seed 20261021.

- **Check:** do the top-right shadows (the mesh) read as Mara's and Ines' own: coat, hair, the pointing arm?
- **Check:** which of the four would you keep?

## 2. proxy_check.jpg

The meshes as the light sees them: Mara walking and standing, Ines sitting and pointing. They stretch where a sitting pose bends the
jacket. Close enough for a shadow?

## Notes

| Check | Answer |
| --- | --- |
| The mesh's shadows look like the characters'? | |
| The one to keep | |
| The meshes close enough? | |
