# 04 · Places and the set builder: a picture skinned onto a room or a street

Status: **proposal, 2026-10-25 — answered the same day → D136; where [06](06-answers.md) differs, it holds** (sets edited in Cast's
bench, free sets in Clay; skyboxes, balconies, hillsides and nature as later kinds). The workshop it serves is
[02](02-the-workshop.md) §8. Characters and props are
[03](03-clay-from-a-picture.md).

## 1. What loom2 already has

| Piece | What it does | Where / measured |
| --- | --- | --- |
| **Set presets** | grey boxes of fixed size: the room (a 9 × 9 m floor, a back wall and a left wall, 3.2 m high), the street (a 9 × 30 m road, façades at ±3.6 m, 5 m high), the deck, the empty floor. Architecture only (D108); nothing editable | `builders.ts:112-125` |
| **The picture set** | MoGe-2's metric point map of a picture becomes a textured relief: the camera at the origin, the floor fitted by RANSAC and laid level, the lens read back. Exact from where the picture was taken; ±0.25 m / ±5° / orbit ±10° before its edge shows | D120, D123; `relief.py`, `graphs.py:1186-1211` |
| **The picture set's things** | objects picked with SAM 3, the plate cleaned under them (Klein's Fill, shadows included), a Pixal3D model of each stood on the relief | D123, D124; `set_things.py` |
| **The plate projector** | casts a picture from a camera onto any geometry (`renderProjected`); its **coverage** mode gives, per pixel, the cosine at which the picture saw the surface (0 outside its view) | PS5b; D132, D133 |
| **Project and fill** | where no picture saw a surface well, Klein's Fill paints it on an Edit document, prompted to continue the place's surfaces and add nothing | PF1, D135 (rig 8/8: on the set like the projection, 3–7 Fills a 5 s shot) |

The pieces for "skin an image onto a room" are all here, in two separate halves:

- the presets are the geometry, with no picture;
- the picture set is the picture, with no geometry beyond a relief.

The set builder joins them.

## 2. The set: a few faces with sizes

A place version gets a **set**: a parametric piece of architecture in one of four kinds. It holds what bounds the space; whatever stands
in it is a prop (D108).

| Kind | Its sizes | Its parts |
| --- | --- | --- |
| **Room** | width, depth, height | floor; walls back · left · right · front, each on or off; a ceiling on or off |
| **Street** | road width, length; pavement width and kerb; façade heights, left and right | road, pavements, two façades, the far end |
| **Corridor** | width, height, length | floor, two walls, a ceiling, the two ends |
| **Open ground** | floor size; backdrop distance | a floor and a backdrop (a cylinder or dome) for land and sky |

**Openings** go on any wall: a door, a window or an arch, each with a size, an offset along the wall and a sill height. Behind an opening
is a backdrop card, which takes its texture from the picture or the Fill.

The record:

```
PlaceSet { kind, sizes {…}, parts {wall_back: true, …}, openings [{part, kind, x, y, w, h}],
           faces [{id, texture_asset_id, texel_m, filled_mask_asset_id}],              // baked: one texture a face
           sources [{asset_id, camera {pos, target, focal_mm, sensor_mm}, made_at}] }  // the pictures it was skinned from
```

It sits on the place version, beside the sheet and the references.

In Stage, the set is an object with `kind: 'set'` and `preset: 'built'`, bound to the place version (`profile_id`, `version`; the
server's rule at `stages.py:211-212` gains `set`). The engine builds the faces from the sizes and maps their baked textures, unlit as the
relief is, with shadow-catching copies so figures cast onto it (`engine.ts:589-626`'s pattern).

## 3. Fitting the set to a picture: the camera match

The author's case: a room or a street exists as a picture (generated, or a photo), and the set should be that place.

1. **MoGe-2 on the picture.** The metric point map and the lens. This is the `image_to_set` graph's first two nodes, about a second.
   The lens can be given, as D123's dialog does.
2. **Planes.** RANSAC fits:
   - the floor (`relief.py:94-175` does this today);
   - the vertical planes (normals at right angles to the floor's): the walls of a room or corridor, the façades of a street;
   - a ceiling when one is seen.
3. **The set from the planes.** The camera's height and tilt come from the floor plane (`_level` does this today). The room's back wall is
   the farthest vertical plane facing the camera. The side walls are the vertical planes facing each other. From these come the width,
   the depth to the back wall and the height (the ceiling, or 3 m when no ceiling is seen). Some parts the picture never saw:
   - the depth behind the camera defaults to a third of the room;
   - a street's length defaults to 30 m;
   - the author sets either with a drag.
4. **The overlay.** The set's edges are drawn over the picture (the floor's corners, the walls' tops, the openings), each corner a handle.
   Dragging a corner moves a wall or the camera, re-solved by least squares with the lens held (the fSpy way). It is mouse-first, and
   nothing has to be adjusted when the fit is right.
5. **Openings from the picture.** A window or door the picture shows is offered from where the wall's points leave the plane (the point
   map goes through the opening). The author confirms it with one click, or draws it with a drag on the wall.

## 4. Skinning: projection, bake, fill

1. **Project.** Stage's plate projector casts the picture from its matched camera onto the set's faces (`renderProjected`, PS5b).
2. **Bake.** Each face is rendered straight on, orthographically, in its own frame with the projector's material. The result is the
   face's texture, a frontal picture of that wall or floor, at a texel size fixed per set (default 1 cm). The coverage mode gives each
   texel the cosine at which the picture saw it.
3. **Mark.** Texels seen badly are unseen or magnified (D133's rule: below 0.05, or seen twice as head-on from the face's front as by the
   picture, below 70°). They are the face's **fill mask**.
4. **Fill.** Each face's texture becomes an Edit document with the mask as its selection, and gets Klein's Fill:
   - the prompt is PF1's lead, "continue the surrounding surfaces … add nothing", plus the place's sheet;
   - faces go in order of how much each already has, so a corner's neighbour gives the next one its edge;
   - the server side is PF1's keyframe route, with the face as the frame.
5. **More pictures, fewer holes.** Each further source is matched to the same set (its corners on the same edges) and projected, and each
   texel takes the source that saw it most head-on (E35d's composite). The second picture can be:
   - another generation of the place;
   - New angle (P14) from the first, which turns the camera so the walls behind come into view.

**What comes out:**

- a set any camera can move through. It does not tear (it is real faces) and it does not drift (the textures stay on them);
- after an edit (a wall moved, a door added), the bake runs again from the kept sources. Only texels that became unseen need a new Fill.

## 5. The set in the final shot

A built set changes what the final shot's plate is. Today:

- the plate is a Klein still projected along the path (PS5b), filled at keyframes on a large move (PF1, D135);
- or it is a picture set rendered through its relief (SC3e).

With a built set, **the plate is the set rendered** through each frame's camera:

- its beauty pass is the textured faces, with the shadows of the figures as the relief's copies catch them today;
- there is no Klein still to make, no projection to smear and no drift on any move;
- the clay, depth, normal and mask passes are exact, because the faces are the geometry.

What it does not give is relighting. The textures carry the picture's light. A different time of day is a new source picture, or a pass
over the plate (Final's passes, D118).

PF1 stays for sets that are presets or reliefs.

## 6. The editing UI: a basic 3D suite (mouse-first)

The place bench ([02](02-the-workshop.md), wireframe ui-5) has two views of one set:

**The picture view.** The source picture with the set's edges over it:

- corners to drag, to fit the set;
- *Next picture ▸* to add a source and match it;
- the unseen texels hatched.

**The 3D view.** Stage's engine on a scratch scene:

- the set from a free camera, with *Look through the picture's camera*;
- handles on the walls: drag a wall to resize the room, drag the top edge for the height;
- *+ Door*, *+ Window*, *+ Arch*: click a wall to place, drag to size;
- each part a row in the set's outline, with on/off;
- a 1 m floor grid and a 1.75 m figure for scale;
- the kind's sizes as number fields, for exactness.

**The foot:**

- *Build the set ▶* (match, project, bake);
- *Fill what the picture never saw ▶*, which says how much and the minutes;
- *Keep* (the place's version takes it);
- *Send to a stage ▸*.

The quick tier stays: *Just the picture (a relief)* makes today's picture set in about a minute, for a look from where the picture was
taken. *Make it a Cast place…* on an existing picture set makes it a place's quick set ([02](02-the-workshop.md) §9).

## 7. Spike E38 · the set builder (GPU, 2–3 days)

**The truth to measure against.** Stage's own presets have known sizes. Each test place is:

1. a stage with a set of known size: a room of three sizes, a street, a corridor;
2. its plate still made by Klein's clay method from the clay pass (PS5b's route);
3. that still fed back to the builder as if it were a found picture.

This gives the true camera and sizes to compare against.

**Plus found pictures:**

- A1's room still;
- four Klein places: a kitchen, an alley, a long hall, a field with a fence.

**Measures:**

| What | How |
| --- | --- |
| The camera match | the lens, the height and the tilt against the truth |
| The sizes | width, depth and height against the truth, in %; how many corner drags fix them |
| The skin | seams at the corners (colour steps across an edge, in levels); how much was unseen, before and after a second picture from New angle |
| The Fill | time per face; consistency (no repeated features — D135's rig found a window growing on a wall the picture never saw: the prompt is the lever) |
| The move | E34's orbit and E35d's crane through the built set, measured as PF1: travel against the set's clay; how much each frame was never seen at all |
| The cost | seconds for each step |

**Decides:**

- whether the builder works without hand fitting on most pictures, or needs the overlay every time;
- the texel size;
- the Fill's order and prompt;
- whether a second picture should be made by default.
