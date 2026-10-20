# 16 · Props like characters, the scene in 3D first (D108–D110)

The author, 2026-10-20: *"We should have a separate menu besides the character generation, where we can pre-generate props (same way as a
character - image(s) first, then 3d model, which we can then place on the scene). Then the scene should work as a coherent 3d scene, with
lighting and camera control - and when the whole scene is complete in the Animate editor, then should we start separating different
entities to layers and start creating the final shot."*

## Where it stands (2026-10-20)

- **Cast** has three kinds of profile, `character`, `place` and `prop`, shown together with a filter. A prop already has a sheet (its
  look, colours, marks), references, versions and an animation reference (the prop alone, ¾ view, CA0).
- **The 3D model** is a separate Catalogue action (P18, "Make a 3D prop…", Pixal3D). Its GLB lands in Stage's Meshes list, unlinked to
  any Cast prop. Stage binds only figures to Cast entries.
- **Spikes:** E28 (props as layers), E28b (the room cleaned, D108: a set is architecture), E28c (props as real models, D109: R1 rendered,
  R2 drawn on the model; a model must be stood upright).

## The build

| Step | What | Done when |
| --- | --- | --- |
| **PS1 · Props tab** | Story's rail gains **Props** beside Cast (World · Cast · Props · Catalogue · Shots · Flow · Episode). It lists the props, has *New prop…*, and opens the same version page as a character. Cast keeps characters and places | a prop is made, versioned and referenced from its own tab; Cast no longer lists props |
| **PS2 · The prop's 3D model** | On a prop version: **Make the 3D model** (from its reference; Pixal3D, a background job of some minutes, its cost shown). The model is **stood upright** (every image → 3D result, E28c's search) and kept on the version (`model_asset_id`, `model_from`). The page shows it **turning**, with mouse drag to turn it by hand. A model made from an older reference is marked stale | the version shows its own model turning; a new reference marks it stale; the `open` variant explains why the button is off (Q22) |
| **PS3 · Props in Animate** | Animate's library gains **Props**: the Cast props with a model, placed with a click or a drag. A placed prop is a Stage mesh **bound to the prop and its version** (as a figure is to a character); its model follows the version and a remade model | a prop placed from the library keeps its binding through saves, version changes and a remade model |
| **PS4 · The 3D scene** | The viewport shows the models **textured and lit** (a room environment, as E28c's R1), not clay. The **lights** are scene objects with their direction, intensity, colour and softness in the Inspector; the **camera** moves are keyed and previewed in 3D (the camera-move check runs here) | a scene with a set, two figures, three props, a key light and a camera move plays back in 3D |
| **PS5 · Make the final shot** (CA2) | Only a complete scene is split into **layers**: each character by Wan Animate on its pose, each prop rendered or drawn on its model (R1 / R2), the set as the plate; then the composition (D106 shadows, D107 contact offsets) | — (the CA2 wave) |

Mouse-first (D32): every verb is a button and a right-click entry; drags are accelerators.

## Status (2026-10-20)

- **PS1–PS3 built** (d27e7ef, c647f22): the Props tab; *Make the 3D model…*, stood upright, turning on the prop's page; props placed from
  Animate's library and bound to the prop.
- **PS4 built:**
  - **Look:** the viewport shows the models textured and lit (a room environment).
  - **Lights:** each light is a scene object with a look (Window, Sun, Lamp), intensity, colour, shadow softness, shadows on or off, and
    an aim (a point, or an object from a list), drawn as a dashed line. *Add light* is in the library and the Add menu.
  - **Ambient:** the stage's level is in its Inspector.
  - **Camera:** keys and playback were already in the timeline (*Key camera*).
- **Owed:**
  - the camera-move check on a finished scene, rendered into layers, which belongs to PS5 (CA2);
  - the author's look at a scene built this way.
