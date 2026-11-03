<!-- markdownlint-disable MD013 MD024 -->
# 02 · The function register — every control the scene took

How to read it:

- **Used** is what the build actually clicked, typed or set, in the order of the build ([01](01-build-log.md)). The raw record is `data/functions.jsonl`
  (one line per use, timestamped, written by the driver as it went).
- **Offered** is what the control gave to choose from, read from the screen at the time (chips, menu items, select options, presets).
- **Remarks** is what stood out for the later broadening study: what the control did *not* offer, where it is a preset in disguise, where
  the mouse could not reach and the driver had to aim for it, and what a "like ArtCraft" world builder would want here. They are
  observations, not decisions.
- ⚙ marks a GPU job. The timings are in [01](01-build-log.md) §5.

The build used **167 distinct controls** (by layer and name; about 120 once per-entity repeats are folded) across the frame, World, Shots, Episode and the Bin, listed below by layer. Everything offered but not used is
listed at the end of each layer under *Offered, not used*, so the study sees the whole surface, not just the path taken.

## 0. The frame

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| Project ▾ (top bar) | opened | New project…, Open project…, Recent | |
| New project › Folder, Name | `F:/loom2-projects/propo02-followed`, *Followed* | a text field (the OS folder picker only in the Tauri shell) | |
| New project › Format | — | fixed: *16:9 · 1920×1080 @ 24 fps · default tier Draft (D18)* | **Not a control.** The format, fps and tier cannot be chosen at creation; a vertical or 2.39 project is not offered. |
| New project › Create | clicked | | the page shows "none open" for a second after Create, then the project |
| tabs World · Shots · Episode · Bin | World, Shots | the four layers, Ctrl+1–4 | the Shots tab reopens a shot at **Flow**, not at the level it was left |

## 1. World › Look

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| rail › Look | clicked | Characters · Props · Places · Look · Sketches | |
| sample scene | *a narrow cobblestone street in an old European town, lined with small storefronts…* | a textarea | one sample scene for the project; a style cannot have its own |
| Add style | clicked | | a tile *Style 1* with no words |
| style tile › click | selected | the grid of styles, ★ on the default | |
| style › name | *Old town, late afternoon* | | |
| style › prompt fragment | *photographic, natural light, late afternoon sun low across the street, long soft shadows, muted warm colours, 35 mm lens look, shallow depth of field, fine film grain* | a textarea, appended after every prompt | the only way to say what the look is is prose; nothing structured (palette, grain, lens, time of day) |
| Look words › art style (chips) | *painterly storyboard* tried, then replaced | painterly storyboard · cinematic film still · graphic-novel ink and wash · oil painting · watercolour sketch · photoreal · charcoal concept sketch · anime key visual | **a preset in disguise:** a chip appends the chip's own name ("painterly storyboard") and nothing more; the Library entries are one-word |
| Look words › mood (chips) | not used | tense · melancholic · hopeful · eerie · serene · triumphant · lonely · playful | same: the name is the words |
| style › ★ the project's default | on | a checkbox | |
| ⚙ Make a sample image | clicked (59 s with the engine's cold start) | | the sample model is fixed in Settings (*lumina-image-2*); the sample's size and seed are not offered; one sample per click, no comparison across seeds |

*Offered, not used:* Open the samples in the Bin · Remove (the style) · drop a picture from the Bin onto the style's sample.

## 2. World › Characters

### 2.1 The entity

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| header › New entity… (+) | ×3 (Nora, Man with a newspaper, Woman with shopping) | an askText dialog: *A draft until its pictures, A-pose and body are made — the header says what it still needs* | the only input is a name; nothing about the class of person (age, build) at creation |
| header › Pick a character ▾ | not needed | the class's entities, New… | |
| mode › Make · Edit · Clay · Build | Make, Build | the segmented row | Edit and Clay (*See in clay ▶*) not used |
| readiness line | read | ✓/○/– hero · references · A-pose front · back · side · body fitted · voice · *N to go* / *Ready for Clay* | the Man's line adds *⚠ carried: folded newspaper*; the Woman's "a canvas shopping bag in each hand" raised no warning |

### 2.2 The Sheet

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| version label | *street coat* / *grey coat* / *red coat* | | |
| appearance | prose (34 words for Nora) | a textarea | free prose is the whole model of a character: no fields for age, build, hair, face; the body's build is set separately in Build |
| outfit | prose | a text field | |
| colours › + (bind a colour) | one row: `#2F4F3A` *wool coat* | up to N rows, each a swatch + "what it colours" | the swatch starts grey/unset (M1's red is gone); the hex lands in the prompt as "#2F4F3A wool coat" |
| marks | *a thin silver ring on her right hand* | | |
| *as sent* line | read | the composed sentence every @mention carries | useful; the only place the composed prompt is visible before a run |

### 2.3 Make (the casting run)

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| Prompt › mode | Tree (default) | Tree · Text · JSON | |
| Prompt › this picture (note) | *walking towards the camera on a cobbled street, mid-stride, her coat open at the hem* | a textarea for this run only | |
| Prompt › framing chips | *full body* | portrait · waist-up · full body; then the switches A-pose front · A-pose back · A-pose side | a chip writes two or three words ("full body, head to feet in frame"); the A-pose chips turn the run into a reference make (2:3, no Look) |
| Prompt › framing words | left as the chip filled | a textarea | |
| ⚙ Give Nora a look ▶ ≈ 3 min | clicked | *4 pictures of Nora; they land as its candidates* | the estimate held (205 s). **The four pictures are near-identical** (same pose, framing, light); a seed changes almost nothing with FLUX.2 dev and a 125-word prompt — the casting offers no diversity lever (a "vary the framing / the light / the lens across the four" is what ArtCraft-style exploration would want) |

*Offered, not used (read from the column):*

- **Prompt:** *what to keep out of the image* (negative) with *negative presets*; the word/token counter; *Show the words under the preset icons*.
- **References · 0 of 4:** *Stop mentioning Nora*; the size cap (≤ 512² · ≤ 768² · ≤ 1024² · original).
- **Look:** *Default · Old town, late afternoon* / *No style* / the style tiles; five preset rows (lighting · mood · art style · background · composition), each a text field with a presets button; *Add a colour*; *Generate a small sample image for every look preset that has none yet* (61 presets without a sample).
- **Camera:** five preset rows (shot size · camera angle · lens · depth of field · aperture), each a text field with presets.
- **Model:** FLUX.2 dev · JSON (default, "slow, best adherence") · Klein 9B · Klein 9B base · Klein 9B KV · Klein 4B · Klein 4B base · Krea 2 Turbo · Krea 2 Raw · Z-Image · Chroma1-HD · Lumina 2 · SD 3.5 Medium; steps 8 · cfg 4 · ×1; sampler (45 entries) and scheduler (11) selects; seed random · fixed · increment; four LoRA slots (the Krea 2 style LoRAs, one trained file); precision *model (2.02)* / custom (default · fp8_e4m3fn · fp8_e4m3fn_fast · fp8_e5m2); encoder GPU/CPU; one unnamed checkbox.
- **Size · 960×544:** 16:9 ★ · 1:1 · 3:2 · 2:3 · 9:16 · 21:9 · custom; count *fewer* / *more* ("one seed each").
- **Preview:** the prompt as sent; *Make from: Prompt · From a stage*; the saved panels (*Save the current panel*).

So the Make column is wide (twelve models, every sampler, LoRAs, precision) and shallow where it matters for diversity: the count is "one seed each" with everything else identical.

### 2.4 The bin (the version's pictures)

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| picture tile › right-click | ×4 | Edit · Make it the hero · Use as a reference · Back to the candidates · Use as the A-pose front · …back · …side · Use as the set picture · Trash · Back to the entity | the menu lists every role of every class (a character's tile offers *Use as the set picture*) |
| tile menu › Make it the hero | tile 1 | | |
| tile menu › Use as a reference | tiles 2–4 | | four near-identical references |
| role chips (all · hero · references · A-pose · set · model · candidates) | not used | | |

### 2.5 Build › Animation reference

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| ⚙ Make reference candidates ▶ · Klein 9B · 2 · ≈ 24 s | ×3 (Nora, and each extra **with no hero and no references**) | | works from the Sheet's words alone, 25–28 s. **Three names for one thing:** "reference" here, "A-pose front" in the header and in Make's chips. The promise "≈ 24 s" ran 35–57 s a job |
| ⚙ Make back-view candidates ▶ | Nora; later the two extras from the track mark | | |
| ⚙ Make side-view candidates ▶ | Nora | | |
| candidate › Front · Back · Side · ✕ | the first of each | 2 candidates a make | picking the front runs the body fit (a *keypoints* job, 6 s) |
| Test it: a turn on the spot… | not used | ⚙ a test animation | |
| Clear the animation reference / back view / side view | not used | icon-only buttons | |

### 2.6 Build › Body

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| figure ♀ / ♂ | ♂ for the man, ♀ for the woman | two icon buttons | the fit guessed ♀ for both extras; the icons have no label (M11 still) |
| height in metres | 1.82 · 1.58 | | the fit left 1.75 for the man and the woman alike; Nora was read as 1.66 |
| build | broad · average | slim · average · broad · heavy | |
| sliders | read | head size · neck length · torso length · shoulder width · hip width · arm length · leg length · hand size · foot size (×0.75–1.35) | filled by the fit |
| hands at rest | not used | relaxed · open · fist · point · grip · pinch | |
| attachments | not used | *+ attachment* (a rigid part that follows the figure) | the man's newspaper could have been one; the readiness line says *carried* but offers *Make what it carries a prop…*, not an attachment |
| Fit the body to the animation reference · Skeleton… · Bench ▶ · Reset proportions · Remove the body · Make the shell ▶ · Line-up ▶ | not used | | |

## 3. World › Places

### 3.1 The entity and its Sheet

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| rail › Places · New entity… (+) | *Cobbled street* | the dialog: *A draft until its set picture and set are made* | |
| Sheet › version label · appearance · marks | *late afternoon*; 60 words of prose; *a bakery with a blue-green front and a bell over the door* | the same sheet as a character minus the outfit | |

### 3.2 Make (the set picture)

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| framing chips | *set picture* (the switch) | wide · empty, eye level · a detail · **set picture** | |
| framing words (filled by the chip) | left as filled: *The place itself, empty: a wide view from eye level, the camera level and about 1.6 m above the ground, the floor and the walls … in view from side to side, nobody in it, no animals, nothing moving, nothing standing in the middle of the floor, even light, the picture filling the whole frame edge to edge with no black bars, no text.* | | the sentence decides the picture's camera; **the model takes no camera direction from it** (M5/M7 again: all four candidates look down the street from the same spot, a café's tables in the middle of the floor regardless) |
| ⚙ Make Cobbled street's set picture ▶ ≈ 3 min | clicked (162 s) | 4 candidates | the four are again near-identical in layout |

### 3.3 Build › Set picture candidates and The set

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| candidate › Use as the set picture · ✕ | candidate 3 | 4 | |
| ⚙ Build the set ▶ | clicked (MoGe fit, 10 s) | | the fit chose **Street** by itself (width 8.0 · length 30 · pavement 2 · fronts 3.47 m · camera 1.6 m); the set is centred on the origin, so the picture's camera sits at z = 5 inside it, 10 m from the near end |
| the set's kind | read (Street) | Room · Corridor · Street · Open ground | |
| sizes | read | width · length · pavement · left fronts · right fronts · camera height (number fields) | the handles on the picture (drag a wall's foot) not used |
| parts | read | six checkboxes (road · pavements · fronts · far end) | |
| Bake again ▶ · Fill what the picture never saw ▶ · Bench ▶ · Clear the set… | Fill; Bench | | after the fit the status read *5 faces to fill · 94 % of the set*: the road, both pavements and both fronts were "100 % to fill" although the picture shows them — only the far end counted as *seen*. The set is therefore almost all Fill, the picture only its layout |
| faces › its material for the Fill (text, one a face) | road: *worn grey cobblestones…*; fronts: *a row of small shop fronts seen square on: a bakery, a bookshop, a café…*; pavements (second pass): *a worn flagstone pavement…* | a placeholder per face kind | my first pass gave the pavements the far-end words by mistake; the fix was the face's own menu |
| ⚙ Fill what the picture never saw ▶ | clicked: 5 Fills in 85 s | | **the fill paints at the picture's scale, not the set's:** the road came out as slabs about a metre across (the Bench shows it) |
| face › right-click | ×2 | Fill this face ▶ · Crowd along this face ▶… · Remove the crowd · Walkers along this face ▶… · Fill what the picture never saw ▶ · Bake again ▶ | |
| ⚙ face menu › Fill this face ▶ | both pavements | | 12–18 s a face |
| Bench ▶ | clicked | the set in Clay inside World | the bench column is Clay's column (figures, sets, props, stand-ins, meshes, lights, image planes, cameras, templates, the motion library, the lenses) |
| Crowd ▶ / Walkers ▶ (experimental) on a face | not used | *People walking along this face — a loop made from the face itself (about 4 min)* / *Shoppers walking in front of this face … experimental (E53)* | **this is where "a few pedestrians" lives for a place** (D173/D174); the scene used performed extras instead |
| Pick a thing that moves… | not used | | |

## 4. Shots › the storyboard and the header

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| ＋ New shot ▾ | ×2 | New shot in a new scene · New shot in the same scene | no name is asked: both shots are called *Shot*; the header numbers the open shot *1 ·* for the second one too |
| shot card (click) | shot 2 | | |
| description | prose for each shot | a textarea | |
| lines › + line | not used | | |
| scene ▾ | *A new scene at a World place › Cobbled street* | New scene · Same scene as the shot before · A new scene at a World place ▸ (the places) | a new shot's scene is a bare stage ("Scene"); binding the place afterwards makes a second stage and leaves the first orphaned (four stages for two shots by the end) |
| camera ▾ | read | the stage's cameras | |
| range start – end | read (the stage's) | | the stage's range was set in the transport instead (W40 still: the shot takes the stage's) |
| cast | read | each member with its readiness, *open in World* | the extras read *2 to go* (hero, references) and Clay took them all the same |
| Show the words ▸ | not used | | |

## 5. Shots › Clay

### 5.1 The Scene outliner and the editors under a row

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| Figures + (figure presets) | ×4 | Nora · Man with a newspaper · Woman with shopping · Adult (1.75 m) · Child (1.2 m) · the starter mannequins | a figure lands **where the viewport's centre ray hits**: all three at (0.68, 0, −14.6) in shot 1, and on the shop front's foot (y = 0.12) in shot 2 (W34/M10 still) |
| a figure's row (click) | each | the editor opens under the row | |
| figure editor › position (x, y, z) · rotation · scale | typed for every figure | three number fields each | **the only precise placement**; no "stand here" on the floor, no snap to the pavement |
| figure editor › character · body · pose · parent | read | pose: stand · point · arms_crossed · walk · run · reach · sit · crouch · wave · look_left; parent: the other objects | *look_left* is a whole-body preset, not a key |
| Cameras › Camera 1 (row) · editor | typed | position · target · focal (24 · 35 · 50 · 85 or a number) · sensor (fixed 36 mm) · roll · Back to the free view · Set from view · Key the camera here · New shot from this camera… · rename · delete | |
| Sets + · Props + · Stand-ins + · Meshes + · Add light · Add image plane… · Add camera · Templates + | not used | | |

### 5.2 The transport and the keys

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| the stage's range end | 240; 96 | two number fields | the header's range followed |
| frame (playhead) | typed throughout | | |
| Key camera | at 0 and 240 | | an ease key of position, target and focal |
| Key object (Shift+K) | at 112, 135, 165 on Nora; once by mistake on the set | | **it keys whatever is selected** — the set got a key because a right-click in the viewport had selected it |
| Remove the keys at this frame | once | | |
| play · step · in/out points | not used | | |

### 5.3 The motion library and the picked clip

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| file › ▸ expand | UAL2_Standard, AnimationLibrary_Godot_Standard | three CC0 files (UAL1 Godot 45 clips · Mannequin_F · UAL2 42 clips); filters All · Starter · Local · Mine; a search | the Godot file is where the plain **Walk_Loop · Jog_Fwd_Loop · Idle_Loop · Sprint_Loop** are; UAL2 has Walk_Carry_Loop and the idles. No "look over the shoulder", no "hurry", no "push a door" |
| clip (list item) | Walk_Loop ×3, Idle_Loop | | a file folds again when the selection changes |
| trim start / end · speed (range ×0.25–2) · foot lock · feet on the floor · in place / along X's path · blend in | along the path on, in place for the idle; the rest as defaulted | | |
| Draw a path (click the floor) / Add to the path · Clear the path | both | | **the path is drawn by clicking the floor in the viewport**: there is no numeric point, no edit of a point, no snap; a click on a shop front lands on its foot. The driver aimed the clicks from calibration clicks read back through the API |
| Apply to X at the playhead | ×5 | | a block lands **at the playhead** — shot 2's first apply landed at frame 96 because the playhead was there |

### 5.4 The timeline's blocks and marks

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| clip block › right-click | ×5 | *WALK_LOOP · FRAMES 0–448* · Speed ▸ (×0.5 · ×0.75 · ×1 · ×1.25 · ×1.5 · ×2) · Loops ▸ (1× · 2× · 3× · 4× · 6× · 8×) · Blend in ▸ · Mirror · In place · Foot lock · Feet on the floor · Along X's path · Bake to keys · Save as animation… · Remove the clip | speed is six fixed steps; Walk_Loop at ×1 walks 0.75 m/s (449 frames for 14 m), ×1.5 = 1.1 m/s; "fill the shot" is not a loop option |
| Speed ▸ ×1.5 | Nora (both shots) | | |
| Loops ▸ 4× | the woman's idle | | |
| Remove the clip | ×2 | | |
| track mark *no back view* › right-click | ×2 | *Make X's back view in World ▸* | works: it opens Build for the figure; the make, the pick, and the Shots tab back — which reopens at Flow |
| Undo (toolbar) | once | | |

### 5.5 The pose editor (Pose Nora)

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| Pose Nora (pill) · Done posing | on, off | | the pill exists only with a figure selected |
| joint select | spine, neck, head | — click one in the viewport — · root · spine · neck · head · r/l shoulder · r/l elbow · r/l hip · r/l knee | the mouse way in (the other is a click on the joint in the viewport) |
| joint › x · y · z ° | y = 30 on each, then 0 | three number fields, step 5 | |
| looks at · Look at the camera · Stop looking | read | — the pose's own head — · the camera · Cobbled street · Man with a newspaper · Woman with shopping | a gaze constraint, not a glance |
| hands (open · relaxed · fist · point · grip · pinch, each side) · pose presets · Mirror · Reset · Save pose… · Save for Nora… · pins (R/L hand, R/L foot) | read | | |
| **what the keys did** | | | **a pose key is the whole pose, not a correction:** at frame 135 Nora stands in the *stand* preset with the head turned, legs together, while the walk block keeps carrying her along the path; and only the last joint edited survived (spine 0, neck 0, head 30). The glance became a stop-and-glide. See [03](03-findings.md) P8 |

### 5.6 The toolbar

Select (W) · Move (G) · Rotate (R) · Scale (S) · Path (P) · Snap (0.25 m · 15°) (Q) · Undo · Redo · Remove the keys at this frame. Used: Path, Select, Undo. The
gizmos were not used: every placement went through the number fields, because a gizmo drag cannot be aimed at a metre.

## 6. Shots › Performance

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| rail › Performance | clicked | | |
| Recipe › template | read: *stage* | Image to video · From the stage · Clay, one character · Clay, two characters · Dialogue with voice | |
| method card | Final shot (default) | Image to video · Stage clip · Final shot | |
| Make the final shot… | clicked | the dialog: *The scene through Camera 1, frames 0–240 at 16 fps: 161 frames at 848×480. 5 layers — the plate, 3 figures, 0 props and the shadows. Stage renders their passes here (a minute or two), and the plate from the built set …* → **Split into layers** | the size (848×480), the fps (16) and the plate's source are decided here and not offered; the passes render in the page (1449 pictures) |
| ⚙ Perform the owed layers ▶ · ≈ 36 min on the GPU with the plate and the face work | clicked | | the queue: the plate (CPU, done at once), then one i2v job per character batch |
| Clips · To Final ▸ | — | | |

### 6.1 The layers after the performances

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| the final's rows | read | *Final 1 · 161 frames at 16 fps · 848×480 · frames 0–240*; plate *done · 161 frames*; each character *done · 161 frames · 1✓ 2✓ 3✓ · identity N · Re-take*; shadows *passes ready* | **identity:** Nora 0.19 (*low*, in a *window ×1.9*), the man 0.49, the woman 0.48 — Nora's own layer scores lowest, below the "same person" band; nothing but the number says so |
| matte strays ▾ | expanded | the man *49/49*, the woman *80/80* | every frame of both extras is a stray: their mattes cover nothing (`cover_min 0.0`), the retry ran, and **the composition dropped them** — the finished shot has no passers-by (03 P19) |
| Clips (the takes' cards) | read | each take: *Clip · Variations (new seeds) · Re-run (same seed) · Try the other model · Show in the Bin · Move to trash*; model, format, seed, prompt, rendered | the layer's prompt is the Sheet plus *moving exactly as the pose shows. Plain studio background, static camera.* |
| Assemble ▶ | clicked (64 s, CPU) | *the next step* | the assembly: RIFE conform to 24 fps, the stack, the offsets (Nora −21 px) |

## 7. Shots › Final

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| rail › Final | clicked | | the composition opens with every layer: the plate, each character and its matte, the shadows (Multiply) |
| a layer's row | read | ◉ video · S solo · 🔒 lock · blend mode (Normal · Multiply · Screen · Overlay · Add · Darken · Lighten · Soft Light · Hard Light · Difference) · track matte (any layer, luma / luma inverted / alpha / alpha inverted) · parent | a full compositor; the character layers come matted by their own matte layers |
| Trim in / out to the playhead · Attach a line… | not used | | |
| Voice and lip-sync | read | *No line on a character's layer yet* | |
| Render settings | left as defaulted | quality Best · Draft; resolution Full 848×480 · Half · Third · Quarter; motion blur and frame blending *as the layers ask* / off; depth 8 · 16 · 32 bits | |
| Output | left as defaulted | keep the alpha; ProRes 4444 beside the master | |
| Play ▶ · Make the composition again | not used | | |
| Render the finished shot ▶ | clicked (14 s) | *effectcraft-cli renders the composition on the CPU with the Output section's settings; the clip becomes the final's and a take on its shot* | 241 frames at 24 fps, 848×480, a PNG master and a proxy |
| Mark the shot final ✓ | clicked | the dialog: *The clip becomes the one the Flow and the Episode bind; the frame and clip are fixed. A retake is a new version.* → Mark final | enabled right after the render (W49 fixed) |

## 8. Episode

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| tab › Episode | clicked | | the left column: Finals (each shot's final, ✓ and *final*), Cuts, Shots, Sound, Clips |
| Finals | read | *✓ 1 · Shot · final*, *✓ 2 · Shot · final* (a click opens the shot) | |
| Cuts › New cut… | clicked | the dialog: *One cut of the episode: a single lane at the project frame rate; shots and clips come from the bins* | **needed first:** *Assemble from the Flow…* was disabled with *no cut open* |
| Assemble from the Flow… | tried | *A new cut of one route of the Flow, every shot at its approved take* | **still disabled with the cut open**, no reason shown: the Flow made from the storyboard has two Shot nodes, no edges and no Start, so there is no route (03 P25) |
| Shots › + (Add to the end of the cut, stamped with the shot) | ×2 | the shots *in the Flow's order — drag onto the lane, or +* | the way the cut was made: 2 clips, 338 frames, 14.08 s |
| Clips | read | every clip of the project (the finals, every character take, every batch) with its first words and length | 14 clips for two shots; the takes are listed beside the finals, named by their prompt's first words (W62 still, in part) |
| the cut editor | read | select · ripple trim · roll · slip · slide · razor; V2 · V1 · A1 Dialogue · A2 Music (−6 dB) · A3 Effects (−3 dB); add a video / audio track; zoom; Assemble again…; Rename the cut…; Delete the cut; Export for Resolve ▶ (FCPXML + markers, EDL, SRT); Render draft; Render the movie | FilmCraft's editor whole; nothing of it was needed for two shots in a row |
| Render the movie | clicked (11 s) | | `timelines/tl_2bdc101c/followed/followed.mp4`, 1920×1080 at 24 fps, the mix at −16 LUFS beside it |

## 9. Bin

| Control | Used | Offered | Remarks |
| --- | --- | --- | --- |
| tab › Bin | clicked | the tree: World 55 (Characters 18 · Places 36 · Look 1) · Shots 20 (15 · 5) · Episode 1 · Imports 0 · trash 0; the kind chips (all · pictures · clips · audio · models); the role chips | **the place holds 36 things** for one set picture: the bakes, the coverage masks, the fills, the depth, the cut-outs (W57's working files, now homed to the place) — the Bin shows them beside the four candidates |
| search · See it large · Detach ↗ · Move to… · Tag… · Trash | not used | | |

## 10. The count

`data/functions.jsonl` holds 279 uses: 167 distinct controls by layer and name, 16 of them GPU runs, plus 24 dumps of what a panel offered at the time. Of
the 167, about 40 are per-entity repeats of the same control (a Sheet field for each of three characters, a position field for each figure); the distinct
surface the scene touched is about 120 controls, against the several hundred the dumps list as offered.
