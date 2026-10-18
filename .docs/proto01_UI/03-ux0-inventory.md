# 03 · UX0 inventory: every making function in the three-tab model

Status: **UX0 draft, 2026-10-18.** Read from the code at `17cb22c` (D98 built). Nothing is built or decided here. This is part 1 of wave UX0
([proto01_animate 03](../proto01_animate/03-image-and-animate-suites.md) §6): it maps every function of today's **Generate**, **Edit**,
**Animate** and **Stage** suites to its home in the D95 model, **Story · Image · Animate**, so that none is lost when IM1 and AN1 re-house
them. The wireframes and the click paths (UX0 parts 2 and 3) build on it.

Sources:

- the function inventory [01](01-function-inventory.md) (written before D90; its ids G1–G41, E1–E80, A1–A33, S1–S28 are kept);
- the D90 plan [02](02-ui-plan.md), built;
- the new direction: [03](../proto01_animate/03-image-and-animate-suites.md) §3–§4 (D95), [04](../proto01_animate/04-catalogue-for-making.md)
  (the Bin drawer), [05](../proto01_animate/05-flow-nodes-as-shot-recipes.md) (D96: Shots are Flow nodes; the recipe Graph view) and D97
  (one GPU job at a time);
- the current code: `frontend/src/suites/{generate,edit,animate,stage}/`, their `*Commands.ts`, `frame/railTabs.tsx`, `frame/TopBar.tsx`,
  `story/storyCommands.ts` (Make ▸, the For chip), `catalogue/catalogueCommands.ts` (the routes in).

## 0. How to read this

**Today** is where the function lives now, after D90–D98, not where 01 put it. Where the code moved a function since 01, the row says so.

**The new places** (03 §3–§4, 04 C1):

| Place | What it is |
| --- | --- |
| **Image › Make column** | today's Generate column, one scroll with a jump rail: Saved panels · Prompt · Refs · Look · Camera · Model · Size · Preview; the For chip on top |
| **Image › Make › results** | the results grid (this batch / session / all) with the Catalogue's strip, menus and right Inspector, plus interim job cards |
| **Image › Make foot** | Generate n ▶ · Queue · Preview · Fetch · estimate |
| **Image › Edit column** | today's Edit rail tabs as one scrolling column with a jump rail: Tools · Brushes · Selection · AI · Documents |
| **Image › Edit › canvas / strip / right Inspector** | today's Edit centre, strip and Inspector (Layers · Properties · History · Info), unchanged |
| **Image › Edit foot** | Save · Save to Catalogue · PNG · PSD |
| **Animate › column › ‹section›** | one scroll, jump rail, sections Shot · Scene · Motion · Camera · Plate · Performance · Edit · Finish · Selection · Output |
| **Animate › column › Performance (‹card›)** | the method cards: Image to video · Pose-driven · Depth-guided |
| **Animate › viewer** | levels Clay · Performance · Final, Compare, and the Graph view (D96 RC1) |
| **Animate › viewer strip** | the strip above the viewer: level switch, Compare, view options of the level shown |
| **Animate › transport / timeline** | one transport and one timeline under the viewer (Stage's keys + Animate's scrubber) |
| **Animate foot** | the shot's cost · Run ▶ · Queue |
| **Bin drawer** | the Catalogue as a collapsible drawer, like the Dock, in Image and Animate (04 C1, the author's answer 4) |
| **CM / LM / ctx** | Edit's canvas menu / layer-row menu; any other right-click menu |

**Change** is one of:

- **same**: the same region, section and menu; only the host tab is renamed (Generate → Image, Edit → Image's Edit mode);
- **moved**: another region, section or menu;
- **merged**: joins another copy of the same function (one transport, one reference tray, one Bin);
- **renamed**: the same place, a new label;
- **split**: one function lands in two homes;
- **dropped**: removed; the row says why and where the need goes.

IDs: 01's id, or **NEW-G / NEW-E / NEW-A / NEW-S n** for functions that exist in the code but not in 01.

## 1. Generate → Image › Make

D90 already made Generate one column (02 §6). Most rows stay where they are; Image only renames the host.

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| G1 | Prompt mode Tree / Text / JSON | column › Prompt (switch) | Image › Make column › Prompt | same |
| G2 | Word / token counter | Prompt header | Image › Make column › Prompt header | same |
| G3 | Preview: the prompt as sent | column › Preview fold; foot Preview | Image › Make column › Preview; Make foot | same |
| G4 | Upsample ✨ | — (removed in D90) | — | dropped: never built; prompt rewriting would be a Prompt-section action if it ever is |
| G5 | Tree fields: scene, subjects, art style, palette, lighting, mood, background, composition, shot size, angle, lens, depth of field, aperture | Prompt · Look · Camera sections | Image › Make column › Prompt · Look · Camera | same |
| G6 | Lead text (= the Text prompt) | Prompt (Tree) | Image › Make column › Prompt | same (one value, 01 B12 note stands) |
| G7 | Negative prompt | Prompt, where the model honours it | Image › Make column › Prompt | same |
| G8 | Field presets (apply, add, remove) | field tiles from Story › World › Library (D92); field **+**; tile ctx | Image › Make column › each field; written in Story › World | same |
| G9 | JSON: pretty · compact · import clipboard · to Tree | Prompt (JSON) | Image › Make column › Prompt | same |
| G10 | Text prompt | Prompt (Text) | Image › Make column › Prompt | same |
| G11 | Story style (picked by image) | Look › style tiles | Image › Make column › Look | same |
| G12 | @mention a group or profile | @ button; typing @ | Image › Make column › Prompt | same |
| G13 | Mention chips: stop mentioning, LoRA on/off | Refs section | Image › Make column › Refs | same |
| G14 | Add a reference | slot drop; Generate tab drop; Catalogue R | Image › Make column › Refs: drop from results or the Bin drawer; R; Edit's *Use as reference* | same (+ Bin drawer, + Edit's route; tab drop: Q2) |
| G15 | Remove a reference | slot ✕; slot ctx | Image › Make column › Refs | same |
| G16 | Reorder references | slot ◀; slot ctx | Image › Make column › Refs | same |
| G17 | Clear references | slot ctx; section line when the model takes none | Image › Make column › Refs | same |
| G18 | Reference note | under the slots | Image › Make column › Refs | same |
| G19 | Reference downscale | under the slots | Image › Make column › Refs | same |
| G20 | Suggested model / references left out | under the slots | Image › Make column › Refs | same |
| G21 | Pick a model | Model cards | Image › Make column › Model | same |
| G22 | Turbo LoRA + strength | Model | Image › Make column › Model | same |
| G23 | Steps · guidance · CFG | Model › Sampling fold | Image › Make column › Model › Sampling | same |
| G24 | Sampler · scheduler | Model › Sampling fold | Image › Make column › Model › Sampling | same |
| G25 | Seed random / fixed / increment | Model › Sampling fold | Image › Make column › Model › Sampling | same (D90's CountSeed would join it to G29) |
| G26 | Shift · weights · text encoder + device · tiled VAE | Model › Advanced fold | Image › Make column › Model › Advanced | same |
| G27 | LoRA slots 1–4 | Model › LoRAs fold | Image › Make column › Model › LoRAs | same |
| G28 | Aspect · tier · W × H | Size (icons) | Image › Make column › Size | same |
| G29 | Count 1–8 | Size stepper | Image › Make column › Size | same |
| G30 | Estimate (time, VRAM) | Size; foot | Image › Make column › Size; Make foot | same |
| G31 | Save panel | Saved panels header; Ctrl+S | Image › Make column › Saved panels | same (Ctrl+S: §5) |
| G32 | Apply · rename · delete a saved panel | Saved panels tiles + ctx; Story › World | Image › Make column › Saved panels; Story › World | same |
| G33 | New angle: source | the New angle sheet (D90), opened by *New angle…* on an image | Image: the New angle sheet, from a result's ctx, the Inspector, the loupe hub, a Bin item | same (Edit's AI "Angle", D90 Q4: §6) |
| G34 | New angle: move ×5, method, keep, count | New angle sheet | Image: New angle sheet | same |
| G35 | New angle ▶ | New angle sheet foot | Image: New angle sheet | same |
| G36 | **Generate ▶** | foot; Ctrl+Enter | Image › Make foot | same |
| G37 | **Queue** | foot; Ctrl+Shift+Enter | Image › Make foot | same |
| G38 | Fetch missing weights | foot → Models & engine (filtered) | Image › Make foot | same |
| G39 | Cancel / Run now a job | interim cards over the results; Dock | Image › Make › results (interim cards); Dock | same |
| G40 | Show this batch / session / all | strip | Image › Make › results strip | same |
| G41 | Results verbs (judge, loupe, compare, lineage, send…) | the Catalogue's strip, grid, menus, right Inspector | Image › Make › results + right Inspector; **Edit ✎** on hover; double-click → Edit | split: double-click leaves the loupe for Edit (Q1); the loupe keeps Enter and ctx |
| NEW-G1 | For chip: *For: Shot ✕*, *Back to the shot* | column top (`gen.for.*`) | Image › Make column top | same |
| NEW-G2 | Subject from the Cast (hero tiles, *free subject*) | Prompt › subject card | Image › Make column › Prompt | same |
| NEW-G3 | Version chip of a linked subject (costume) | subject card | Image › Make column › Prompt | same |
| NEW-G4 | Sheet view + *Edit the character sheet in Story · Cast* | subject card; ctx | Image › Make column › Prompt | same |
| NEW-G5 | Outfit and *this shot* lines | subject card | Image › Make column › Prompt | same |
| NEW-G6 | *holds ▸* a Cast prop · *Put the prop down* | subject card | Image › Make column › Prompt | same |
| NEW-G7 | *Give the character a look* / *More looks* (casting run) | subject card | Image › Make column › Prompt | same |
| NEW-G8 | Scene from a Cast place (tiles, chip, this shot, *Edit the place in Cast*, unlink) | Prompt › scene | Image › Make column › Prompt | same |
| NEW-G9 | Add a field's words to the World library (+) | each field | Image › Make column › each field | same |
| NEW-G10 | Preset tile ctx: add / remove from field, *Make a new picture*, *Edit in Story · World*, remove from library | tile ctx | Image › Make column › each field | same |
| NEW-G11 | Make the missing sample icons | Look header | Image › Make column › Look | same |
| NEW-G12 | Words under icons (Aa) | section headers | Image › Make column › each section | same |
| NEW-G13 | Subject ↔ reference bindings as sent | Preview fold | Image › Make column › Preview | same |
| NEW-G14 | Jump rail + scroll sync (7 buttons) | Rail | Image › Make column jump rail | same (the rail swaps to Edit's sections in Edit mode, §6) |

## 2. Edit → Image › Edit

Edit's left side today is five rail tabs. Under D95 it becomes one scrolling column inside Image (03 §3). Panel rows are **moved**; the
canvas, strip, right Inspector and menus stay (**same**).

**Document and history**

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E1 | Save | foot; CM › Document; Ctrl+S | Image › Edit foot; CM › Document | same (03 calls it "a new version": Q3) |
| E2 | Save to Catalogue (flatten) | foot; CM › Document | Image › Edit foot; CM › Document | same |
| E3 | Export PNG / PSD | foot; CM › Document | Image › Edit foot; CM › Document | same |
| E4 | Close document | foot; CM › Document | CM › Document; Image › Edit column › Documents | moved: not in 03's foot (Q3) |
| E5 | Compare preview with exact flatten | Info › Diagnostics (dev builds) | Image › Edit › right Inspector › Info › Diagnostics | same |
| E6 | New document | Documents tab; empty state; quick action | Image › Edit column › Documents; ☰ › New document; empty state | moved |
| E7 | Open document | Documents tab; empty-state recents; Dock origin | Image › Edit column › Documents; the Make ⇄ Edit switch (last document) | moved |
| E8 | Delete document | Documents tab 🗑 | Image › Edit column › Documents | moved |
| E9 | Open an asset as a document | Catalogue E / ctx / Inspector; Edit tab drop; Animate *Send to Edit* | Image › Make › results: Edit ✎, double-click, E, Inspector *Edit*; Bin drawer; Animate *Send frame to Image › Edit* | moved |
| E10 | Add a tile or file as a layer | drop on canvas / layer list | Image › Edit › canvas, Layers; also from the Bin drawer | same |
| E11 | Undo / Redo | strip; CM; history | Image › Edit › strip; CM; Inspector › History | same |
| E12 | Step to a history state | Inspector › history | Image › Edit › right Inspector › History | same |

**Tools** (toolbox and CM › Tool ▸; the toolbox shows wand, heal and eyedropper behind *More tools*, D90)

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E13 | Move (+ nudge, flip, rotate) | Tool options; CM › Tool | Image › Edit column › Tools; CM › Tool | moved |
| E14 | Marquee | Tool options; CM › Tool | Image › Edit column › Tools; CM › Tool | moved |
| E15 | Lasso: freehand / polygon / magnetic; Close · Cancel · Remove last point | Tool options; strip; CM | Image › Edit column › Tools; strip; CM | moved |
| E16 | Magic wand | More tools; CM › Tool | Image › Edit column › Tools › More tools | moved |
| E17 | Quick selection | Tool options; CM › Tool | Image › Edit column › Tools | moved |
| E18 | Spot healing | More tools; CM › Tool | Image › Edit column › Tools › More tools | moved |
| E19 | AI select tool (points, box) | Tool options; canvas | Image › Edit column › Tools; canvas | moved |
| E20 | Brush / Eraser | Tool options; CM › Tool | Image › Edit column › Tools | moved |
| E21 | Fill / gradient | Tool options | Image › Edit column › Tools | moved |
| E22 | Eyedropper | More tools | Image › Edit column › Tools › More tools | moved |
| E23 | Crop / canvas (Resize canvas; the crop gesture, D90 B9) | Tool options; canvas | Image › Edit column › Tools; canvas | moved |
| E24 | Hand | Tool options; Space / middle drag | Image › Edit column › Tools | moved |
| E25 | Zoom tool | Tool options | Image › Edit column › Tools | moved |

**Brush and colour**

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E26 | Brush larger / smaller / harder / softer | brush options buttons; [ ] Shift+[ ] | Image › Edit column › Tools (brush options) | moved |
| E27 | Brush opacity 10–100 % | CM › Opacity ▸ (D90); opacity field; 0–9 | CM › Opacity ▸; Image › Edit column › Tools | moved (the field) |
| E28 | Brush presets apply / save / delete | Brushes tab | Image › Edit column › Brushes | moved |
| E29 | Foreground / background colour, swap, default | swatches in brush options, fill options and Brushes tab | Image › Edit column › Brushes (one swatch set) | merged: one column no longer needs three copies |

**Selection**

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E30 | Select all / Deselect / Invert | Selection tab; CM | Image › Edit column › Selection; CM | moved |
| E31 | Select layer transparency | Selection tab; LM; CM; quick actions; Ctrl-click | Image › Edit column › Selection; LM; CM | moved |
| E32 | Expand / Contract / Border / Smooth / Feather | Selection tab; CM › Modify | Image › Edit column › Selection; CM › Modify | moved |
| E33 | Refine edge | Selection tab; CM; AI Select | Image › Edit column › Selection; CM; AI | moved |
| E34 | Quick mask | strip; Selection tab; CM | Image › Edit › strip; column › Selection; CM | moved |
| E35 | Clear selected pixels | CM | CM | same |
| E36 | Crop to selection | Selection tab; CM; Crop options | Image › Edit column › Selection; CM | moved |
| E37 | Load mask as selection | Selection tab; mask options; LM | Image › Edit column › Selection; mask options; LM | moved |

**Clipboard** (CM only)

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E38 | Copy · Cut · Copy merged | CM › Clipboard | CM › Clipboard | same |
| E39 | Paste · Paste in place | CM › Clipboard | CM › Clipboard | same |
| E40 | Layer via copy / cut | CM › Clipboard | CM › Clipboard | same |

**Layers, masks, transform, view** (right Inspector, LM, CM, strip)

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E41 | Select / multi-select layers | Inspector › layers | Image › Edit › right Inspector › Layers | same |
| E42 | New layer | layers footer; CM › Layer | Image › Edit › right Inspector › Layers; CM | same |
| E43 | New empty group | layers footer | Image › Edit › right Inspector › Layers | same |
| E44 | Group / Ungroup | footer; LM; CM | Image › Edit › right Inspector › Layers; LM; CM | same |
| E45 | Duplicate layer | footer; LM; CM; drops | Image › Edit › right Inspector › Layers; LM; CM | same |
| E46 | Merge down / merge selected | footer; LM; CM | Image › Edit › right Inspector › Layers; LM; CM | same |
| E47 | Move up / down / reorder | footer; LM; drag | Image › Edit › right Inspector › Layers | same |
| E48 | Rename layer | LM; double-click | Image › Edit › right Inspector › Layers; LM | same |
| E49 | Hide / Solo | footer; LM; eye | Image › Edit › right Inspector › Layers | same |
| E50 | Lock | footer; LM; row icon | Image › Edit › right Inspector › Layers | same |
| E51 | Delete layer | footer; LM; CM; drop on 🗑 | Image › Edit › right Inspector › Layers; LM; CM | same |
| E52 | Lock transparency · Ink from white | LM; quick actions | LM; Image › Edit › right Inspector › Properties | same |
| E53 | Blend · opacity · fill · group mode · clip | layers active block | Image › Edit › right Inspector › Layers | same |
| E54 | Layer x / y | Inspector › properties | Image › Edit › right Inspector › Properties | same |
| E55 | Add adjustment layer (8) | footer ▾; CM › Layer | Image › Edit › right Inspector › Layers; CM | same |
| E56 | Add filter layer (5) | footer ▾; CM › Layer | Image › Edit › right Inspector › Layers; CM | same |
| E57 | Levels / Curves / Colour balance / params · Reset | Inspector › properties | Image › Edit › right Inspector › Properties | same |
| E58 | Add mask (5 kinds) | footer; LM › Mask; +◐; Selection tab; CM | Image › Edit › right Inspector › Layers; LM; CM; column › Selection | same |
| E59 | Edit mask / pixels | LM; thumbnail click | Image › Edit › right Inspector › Layers; LM | same |
| E60 | Show mask alone · enable · link | LM; mask options | Image › Edit › right Inspector; LM | same |
| E61 | Apply / remove mask · density · feather | mask options; LM; footer | Image › Edit › right Inspector; LM | same |
| E62 | Mask overlay | strip; CM › View | Image › Edit › strip; CM | same |
| E63 | Free transform | Move options; LM; CM | Image › Edit column › Tools (Move); LM; CM | same |
| E64 | Transform mode | LM; CM; transform bar | LM; CM; Image › Edit › strip | same |
| E65 | Box gestures, X/Y/W/H/angle | canvas; transform bar | Image › Edit › canvas; strip | same |
| E66 | Apply / Cancel transform | Move options; transform bar; LM; CM | Image › Edit › strip; LM; CM; column › Tools | same |
| E67 | Flip / rotate layer | Move options; LM; CM | Image › Edit column › Tools (Move); LM; CM | same |
| E68 | Zoom in / out / Fit / 100 % / 200 % / typed | strip; CM › View; Zoom tool | Image › Edit › strip; CM › View | same (Ctrl+1 / Ctrl+2: §5) |
| E69 | Pixel grid | strip; CM › View | Image › Edit › strip; CM | same |
| E70 | Before (click toggles, hold peeks) | strip | Image › Edit › strip | same |
| E71 | Renderer | Info › Diagnostics; strip badge in dev builds | Image › Edit › right Inspector › Info › Diagnostics | same |
| E72 | Modifier latches | strip | Image › Edit › strip | same |

**AI** (D90 made each run a command, `edit.ai.*`)

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| E73 | AI Select ▶ | AI tab; A tool; CM › AI ▸ *Select subject* | Image › Edit column › AI; CM › AI | moved |
| E74 | Inpaint the selection ▶ (Fill, Fill-Match, Fill Hero, Remove, Quick remove) | AI tab; CM › AI ▸ (opens the tab) | Image › Edit column › AI; CM › AI | moved |
| E75 | Outpaint ▶ | AI tab; CM › AI ▸ | Image › Edit column › AI; CM › AI | moved |
| E76 | Refine ▶ (i2i) | AI tab; CM › AI ▸ | Image › Edit column › AI; CM › AI | moved |
| E77 | Upscale ▶ (detailed) | AI tab; CM › AI ▸ | Image › Edit column › AI; CM › AI | moved |
| E78 | Count 1–4 · seed | AI tab | Image › Edit column › AI | moved |
| E79 | Use candidate N / Use all | candidate strip; 1–4; Enter | Image › Edit › canvas candidate strip | same |
| E80 | Re-run (new seed) · Copy recipe JSON | Inspector › properties; LM; CM | Image › Edit › right Inspector › Properties; LM | same |
| NEW-E1 | Flatten image | CM › Layer; LM | CM › Layer; LM | same |
| NEW-E2 | Merge visible | CM › Layer; LM | CM › Layer; LM | same |
| NEW-E3 | Apply / Cancel crop | strip; CM; Tool options | Image › Edit › strip; CM; column › Tools | same |
| NEW-E4 | Queue the AI job | AI tab | Image › Edit column › AI | moved |
| NEW-E5 | More tools ▾ (press menu) | toolbox | Image › Edit column › Tools | moved |
| NEW-E6 | Text encoder per AI operation (D31) | AI tab | Image › Edit column › AI | moved |
| NEW-E7 | Info › Diagnostics fold (ids, memory, renderer, cursor) | Inspector › info | Image › Edit › right Inspector › Info | same |
| NEW-E8 | Empty state: drop zone, *New 1920×1080*, *Open the Catalogue*, recent documents | centre | Image › Edit canvas empty state; *← Results* and the Bin drawer replace *Open the Catalogue* | merged |
| NEW-E9 | Rail tabs Tool options · Brushes · Selection · AI · Documents | Rail | Image › Edit column jump rail | merged: five tabs into one column |

## 3. Animate → Animate (Performance, viewer, timeline)

Today's Animate is the **Image to video** card of the Performance section (03 §4.2). Its player becomes the **Performance** level of the
viewer; its scrubber joins Stage's keyframe timeline. The right Inspector goes (on trial, D95): its contents move to the column's
**Shot** and **Selection** sections.

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| A1 | Set the start frame | S slot drop; Animate tab drop; Catalogue Shift+A | Animate › column › Performance (Image to video card) › S slot; drop from the Bin drawer; tab drop; Shift+A in Image results | moved |
| A2 | Set the end frame | E slot drop; second image of a drop; Shift+Z | Animate › column › Performance (Image to video card) › E slot | moved |
| A3 | Clear start / end | slot ✕; slot ctx | Animate › column › Performance (Image to video card) | moved |
| A4 | Swap start / end | Inputs; slot ctx | Animate › column › Performance (Image to video card) | moved |
| A5 | Reuse a clip's start / end | Inspector › clip › frame thumbnails | Animate › column › Selection (a take selected) › frames | moved |
| A6 | Prompt · motion chips · negative | Inputs | Animate › column › Performance (Image to video card); chips as icon tiles (D90 §6.3) | moved |
| A7 | Keyframe beats (LTX) | Inputs; ♦ on the timeline | Animate › column › Performance (Image to video card); ♦ on the one timeline | moved |
| A8 | Video model (cards + health / fetch) | Model tab | Animate › column › Performance › model | moved |
| A9 | H3 (hero), locked | Model tab | Animate › column › Performance › model | moved (still locked until post-MVP) |
| A10 | Preset draft / motion / quality · steps / CFG / shift | Model tab | Animate › column › Performance › preset + Advanced fold | moved |
| A11 | Tier · orientation · size · frames · fps · seed · count | Length & Size tab | frames, fps, format → Animate › column › Shot; tier, size, seed, count → Performance card | split (Q5) |
| A12 | Saved panels (Animate presets) | Presets tab (browser storage) | Animate › column top: Saved panels tiles, as in Image | renamed: "Saved panels"; storage browser → project (Q5) |
| A13 | **Animate ▶** | foot; Ctrl+Enter | Animate foot › **Run ▶** | renamed |
| A14 | **Queue** | foot; Ctrl+Shift+Enter | Animate foot | same |
| A15 | Fetch missing weights | estimate line; model card badge | Animate › column › Performance; foot | same |
| A16 | Select a clip | Clips tab rows (search, state); lineage siblings; toasts; Story; origin | Bin drawer (type: clip); Animate › column › Shot › takes; timeline layer row | moved |
| A17 | View Player / Filmstrip / Compare | strip; ctx | Animate › viewer strip: Player = the Performance level; Compare = viewer Compare; Filmstrip → timeline thumbnails | split (Q8) |
| A18 | Play · step · ±10 · first · last | transport; ctx | Animate › transport (one); viewer ctx | merged with S26 |
| A19 | Shuttle J / K / L | ctx › Shuttle ▸; keys | Animate › transport ctx | merged with S26 |
| A20 | Speed · Loop · Onion | strip; ctx | speed, loop → Animate › transport; onion → Animate › viewer strip (Performance level) | moved |
| A21 | Scrub (ruler, filmstrip, ▼ pins) | timeline; filmstrip; Inspector › frames | Animate › timeline ruler and markers | merged with S26 |
| A22 | In / Out / Clear | transport; ctx; handle drag | Animate › timeline work area (= Stage's range) | merged with S26 |
| A23 | Extract frame | transport; Inspector › frames; ctx | Animate › transport; viewer ctx; column › Selection | moved |
| A24 | Extract range (every k) | Inspector › frames; ctx | Animate › column › Selection › frames; viewer ctx | moved |
| A25 | Send frame to Edit | transport; Inspector; ctx | Animate › transport; viewer ctx: *Send frame to Image › Edit* | renamed |
| A26 | Use frame as next start | Inspector › clip; ctx | Animate › column › Performance (Image to video card) S slot ctx; viewer ctx | moved |
| A27 | Extend ▶ (experimental) | Inspector › clip › Experimental fold; ctx | Animate › column › Performance › Experimental fold; take ctx | moved |
| A28 | Keep / Reject a clip | Inspector; ctx; Clips row ctx | Animate › column › Shot › takes; Bin drawer; take ctx | moved |
| A29 | Variations · Re-run · Try the other model | Inspector; ctx | Animate › column › Performance (a take selected); take ctx | moved |
| A30 | Measure identity (FaceSim) | Inspector › clip; ctx | Animate › column › Selection (a take) | moved |
| A31 | Make a shot from this clip | transport; ctx; Clips row ctx | Animate › column › Shot (no For chip: *Make a Shot from this take…*); take ctx | moved (D96: the Shot is a Flow node) |
| A32 | Show in Catalogue | Inspector; ctx; Clips row ctx | Bin drawer (*Show in Bin*); Story › Catalogue | merged |
| A33 | Lip-sync (experimental) | Story › Shots Inspector; Animate shows a badge only | Animate › column › Performance › Lip-sync step (E29 decides the route); Story keeps a link | moved (05 §3: a recipe step) |
| NEW-A1 | For chip: *For: Shot ✕*, *Back to the shot* | top of every Animate panel tab (`anim.for.*`) | Animate › column › Shot | moved |
| NEW-A2 | Move a clip to the Trash | Inspector; ctx; Clips row ctx (D90) | Bin drawer; take ctx | moved |
| NEW-A3 | Clips search and state filter (D90) | Clips tab | Bin drawer query chips (type: clip, state) | merged |
| NEW-A4 | Rail tabs Inputs · Model · Length & Size · Presets · Clips | Rail | Animate column jump rail | merged: tabs into one column |
| NEW-A5 | Interim job cards (i2v) | centre, above the player | Animate › column › Shot › takes (running); Dock | moved (Q5) |
| NEW-A6 | Frame counter and format readout | strip; transport | Animate › transport | merged |
| NEW-A7 | Clip facts (state, model, format, seed, prompt, time, ids) | Inspector › clip | Animate › column › Selection (a take) | moved |
| NEW-A8 | Harvested frames | Inspector › frames; ▼ pins | Animate › column › Selection › frames; timeline markers | moved |
| NEW-A9 | Lineage: sources, extracted, siblings | Inspector › lineage | Animate › column › Selection › Lineage fold; later the viewer's Graph view (D96 RC1) | moved |
| NEW-A10 | Empty state ("set a start frame …") | centre | Animate › viewer empty state | same |

## 4. Stage → Animate (Scene, Motion, Camera, Plate, Performance) and Image (From a stage)

Stage's viewport becomes the viewer's **Clay** level; its five rail tabs become Scene, Motion and Camera; its stills (the Render tab) move to
Image as the source *From a stage*; its clips become the Pose-driven and Depth-guided cards (03 §4.2). Stage's right Inspector goes into the
Selection section.

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| S1 | New stage | Library +; foot; empty centre card; ctx › Stage ▸ | Animate › column › Scene (stage picker *New stage…*); viewer empty state | moved |
| S2 | Open stage | Library list; Story *Open in Stage* / *Make … in Stage*; Dock origin | Animate › column › Scene picker; Bin drawer (stage item, 04 C3); Image › From a stage › *Open the stage ▸* | moved |
| S3 | Rename / delete stage | Inspector (stage view); ctx › Stage ▸ | Animate › column › Scene header ⋯; Bin item ctx | moved |
| S4 | Undo / Redo (stage) | gizmo bar; ctx; Ctrl+Z | Animate › viewer (Clay) toolbar; ctx | merged: one shot history? (Q7) |
| S5 | Add figure / set / prop | Library buttons; ctx › Add ▸; empty cards | Animate › column › Scene › library (icon tiles); viewer ctx › Add ▸ | moved |
| S6 | Add a mesh prop | Library › Meshes; drop | Animate › column › Scene › Meshes; drag from the Bin drawer | moved |
| S7 | Add an image plane | drop on the viewport | Animate › viewer (Clay): drop from the Bin drawer; a Scene command for the mouse route (D32) | moved |
| S8 | Select an object | viewport click; Outliner row | Animate › viewer (Clay); column › Scene › outliner; timeline row | moved |
| S9 | Tools Select / Move / Rotate / Scale · Snap | gizmo bar on the viewport; ctx | Animate › viewer (Clay) gizmo bar; ctx | same |
| S10 | Numeric transform · parent · faces camera | Inspector | Animate › column › Selection | moved |
| S11 | Reset transform · Duplicate · Delete | Inspector; ctx | Animate › column › Selection; ctx | moved |
| S12 | Lock · Hide | Inspector; ctx; Outliner icons | Animate › column › Selection; Scene outliner icons; ctx | moved |
| S13 | Rename an object / camera | double-click in Outliner / Cameras | Animate › column › Scene outliner, Camera; + a *Rename…* ctx command (D32) | moved |
| S14 | Orbit / pan / zoom | viewport mouse | Animate › viewer (Clay) | same |
| S15 | Free / camera view · guides · frame all · frame selection | strip row 1; Cameras tab; Inspector; ctx | Animate › viewer strip (Clay level); F / Shift+F | moved |
| S16 | Cameras: add, active, focal, roll, position / target | Cameras tab; Outliner; Inspector | Animate › column › Camera; Selection (position / target) | moved |
| S17 | Set camera from view · delete camera | Cameras tab; Inspector | Animate › column › Camera | moved |
| S18 | New shot from this camera | Cameras tab; Render header; ctx | Animate › column › Camera: *Make a Shot from this camera…*; Shot (For chip) | moved (D96: one camera per Shot) |
| S19 | Pose presets · saved poses (delete) · Mirror · Reset · Save | Poses tab; Inspector pose select; ctx | Animate › column › Motion (pose icons, saved poses); ctx | moved |
| S20 | Joint: select, rotate (FK), drag a hand / foot (IK) | viewport in pose mode; Poses fields | Animate › viewer (Clay, pose mode); column › Motion › joint | moved |
| S21 | Render method (Clay reference / Exact pose) · Image 1 pass · use as is | Render tab; ctx | Image › Make column › *From a stage* (stage, camera, frame, method) | moved |
| S22 | Render references (deck, notes) | Render tab | Image › Make column › Refs (one tray, the method's limit) | merged |
| S23 | Render prompt · Draft / Full · count | Render tab | Image › Make column › Prompt and Size | merged |
| S24 | **Render frame** | foot (Render tab); ctx; Ctrl+Enter | Image › Make foot (Generate ▶ with the source *From a stage*) | merged |
| S25 | Pick a result as the clip start | Render › Results click | Animate › column › Performance (Pose-driven / Depth-guided card) start still, from takes or the Bin drawer | moved |
| S26 | Timeline: play, step, keys, frame, range | strip row 2 | Animate › transport / timeline (one) | merged with A18–A22 |
| S27 | Key camera / Key object / Remove keys | strip row 2; ctx; Inspector | Animate › timeline (a key row per object); column › Selection; ctx | merged |
| S28 | Clip method · guide Depth / Pose · Render sequence · **Render clip ▶** | Render › Clip fold; ctx | Animate › column › Performance (Pose-driven card = Wan Animate; Depth-guided card = IC-LoRA + guide) | moved |
| NEW-S1 | Bind a figure to a Cast character: tiles, version, Outliner tag, *Bind ▸*, *Unbind*, *Open in Cast* (D93 C8) | Inspector; Outliner; ctx | Animate › column › Selection › character; Scene outliner tag; ctx | moved |
| NEW-S2 | Render passes (clay, depth, pose…) | Render tab; ctx | Image › Make column › From a stage; Animate › column › Plate (passes for the plate and guides) | split |
| NEW-S3 | Figure slots: each figure's bound references, figure lines | Render tab › References | Image › Make column › Refs and Preview | merged |
| NEW-S4 | The stage's results (stills) and clips | Render tab › Results, Clips | Bin drawer (the stage's page, 04 C7) | moved |
| NEW-S5 | Saved state (saving · revision) | foot (non-Render tabs); Inspector | Animate › column › Scene header | moved |
| NEW-S6 | Stage facts (frame size, contents) | Inspector (stage view) | Animate › column › Scene header | moved |
| NEW-S7 | Rail tabs Library · Outliner · Cameras · Poses · Render | Rail | Animate jump rail (Scene · Motion · Camera); Image (*From a stage*) | split |
| NEW-S8 | Empty-stage quick cards (*Add set · room*, *Add figure · adult*) | viewport | Animate › viewer (Clay) empty state | same |
| NEW-S9 | Frame field; range fields + fps | timeline | Animate › timeline (work area; the Shot's range and fps) | merged |

## 5. Routes into the makers, and frame items

These rows belong to other suites but name a maker that changes. They are listed so that their labels and targets change with IM1 / AN1.

| ID | Function | Today | New home | Change |
| --- | --- | --- | --- | --- |
| F5 | Switch suite, Ctrl+1–5 | TopBar: Story · Generate · Edit · Animate · Stage | TopBar: Story · Image · Animate, Ctrl+1–3 | merged |
| F6 | Quick drop on a suite tab | Edit tab: open; Generate tab: references; Animate tab: start | Image tab: Q2; Animate tab: start frame (or a stage onto Scene) | merged (Q2) |
| F7 | Spring-load a tab on a held drag | TopBar tabs | TopBar tabs | same |
| F23 | Quick actions *Generate an image* · *New document* · *Animate from an image* | empty states; ⌘K | the same, targets Image › Make, Image › Edit, Animate | renamed |
| F24 | Job: go to origin | Dock | Dock: origins `generate`/`edit` → Image, `stage` → Animate › Scene or Image | same (routing changes) |
| F30 | Keep Edit / Animate loaded N min | Settings › App | Settings › App: Image's Edit mode and Animate (with the Clay viewer) | renamed |
| F33 | Remap keys per scope | Settings › Keyboard (Generate, Edit, Animate, Stage listed) | scopes Image (Make, Edit) and Animate | merged |
| F37 | Deep links `?suite=` | URL | `generate`, `edit` → Image; `stage` → Animate; aliases kept | renamed |
| C60 | Open in Edit (E) | Catalogue ctx, hub, Inspector | Image › Edit | renamed: *Edit* |
| C61 | Use as reference (R) | Catalogue | Image › Make column › Refs | renamed |
| C62–C64 | Re-run · Variations · Load in Generate | Catalogue | Image › Make | renamed: *Load in Image* |
| C65–C66 | Animate start / end frame (Shift+A / Shift+Z) | Catalogue | Animate › Performance (Image to video card) | same |
| C67–C68 | Select subject… · Upscale in Edit… | Catalogue › Start from this image | Image › Edit column › AI | renamed |
| C69 | New angle… | Catalogue › Start from this image | Image: New angle sheet | same |
| C70 | Make a 3D prop… | Catalogue › Start from this image | results land in Image's results; meshes listed in Animate › Scene › Meshes | same |
| Y38 / make | Open in Stage / Animate; *Make frame in Generate / Stage*; *Make clip in Animate / Stage* | Story › Shots strip, Inspector, ctx | *Make frame ▸ Image / From a stage*; *Make clip ▸ Animate*; *Open the stage ▸* Animate › Scene | renamed |

## 6. Functions the new model adds

These have no home today. They come from D95 (03 §3–§4), 04 C1 and D96, and are listed so the wireframes give each one a place.

| ID | Function | Home | Source |
| --- | --- | --- | --- |
| N1 | Make \| Edit switch (returns to the last document) | Image › top of the column | 03 §3 |
| N2 | Edit ✎ on a result tile (hover; also ctx) | Image › Make › results | 03 §3 |
| N3 | ← Results (leave Edit in place) | Image › Edit › strip | 03 §3 |
| N4 | Use as reference (from Edit to Make's Refs) | Image › Edit foot or CM › Document | 03 §3 |
| N5 | *From a stage*: pick a stage, a camera, a frame | Image › Make column (a source section) | 03 §4.2 |
| N6 | Viewer levels Clay · Performance · Final, Compare (side by side or wipe) | Animate › viewer strip | 03 §4.1 |
| N7 | Graph view (the Shot's recipe) | Animate › viewer, beside the levels | D96 |
| N8 | Bin drawer (places, query chips, drag by kind) | Image and Animate, a collapsible drawer | 04 C1 |
| N9 | Plate (still, moving plate) | Animate › column › Plate | 03 §4.2, CA3 |
| N10 | Motion library, root path, foot lock | Animate › column › Motion | CA1 |
| N11 | Composition editing, effects, colour | Animate › column › Edit | AE1–AE3 |
| N12 | Finish (layer passes, healing patches) | Animate › column › Finish | AE4 |
| N13 | Output (final render as a take, export) | Animate › column › Output | AE5 |
| N14 | Preview quality (resolution, Fast Previews, status chip) | Animate › viewer strip | AP1 |

## 7. Keys when the transports and modes merge

01 §11.7 listed keys that change meaning between suites. D90 already moved some: Animate steps on ← →, Stage's *Frame everything*
moved to Shift+F and its previous / next key to Alt+← →, and both use Space, Shift+← →, Home / End, I / O. Merging Stage and Animate into
one scope, and Generate and Edit into one suite, leaves these clashes.

**Animate (Stage + Animate in one scope)**

| Key | Animate today | Stage today | Proposed (mouse home first) |
| --- | --- | --- | --- |
| Space · ← → · Shift+← → · Alt+← → | play · frame · ±10 | play · frame · ±10 · previous / next key | **one transport**: the same keys (transport buttons, ctx) |
| Home / End | first / last frame of the clip | range start / end | work-area start / end (transport buttons) |
| I / O | in / out point | range in / out (alt [ ]) | work-area in / out (timeline handles, ctx); drop the [ ] alternates |
| J / K / L | shuttle back · stop · forward | — | keep (transport ctx › Shuttle ▸) |
| K | shuttle stop | key the camera | **K = shuttle stop** |
| Shift+K | keep the clip | key the object | **Shift+K = Key the selection** (object, figure, camera; nothing selected → the camera), timeline button and ctx; one command replaces Key camera / Key object |
| — | — | Remove keys at this frame (no key) | Alt+Shift+K (timeline button, ctx) |
| Keep / Reject a take | Shift+K / X | — | K / X **in the Bin drawer** (as the Catalogue); in the column, the take buttons |
| L | shuttle forward | lock the object | **L = shuttle**; Lock → Ctrl+L (Selection section, outliner icon, ctx) |
| C | compare view | camera view (look through) | **C = Compare**; look through → `0` (viewer strip *Camera*, Camera section) |
| 1 / 2 / 3 | — | — | viewer level Clay / Performance / Final (viewer strip) |
| F | extract frame | frame the selection | **F = Frame the selection** (viewer); extract frame → Alt+F (transport, ctx) |
| Shift+F | extract range | frame everything | **Shift+F = Frame everything**; extract range → Alt+Shift+F (Selection › frames, ctx) |
| E | send frame to Edit | — | E = *Send frame to Image › Edit* (transport, ctx) |
| W G R S · Q | — | tools · snap | keep (Clay viewer gizmo bar) |
| H · M · Delete · Ctrl+D | — | hide · mirror pose · delete · duplicate | keep, acting on the selection (Selection section, ctx) |
| N | onion skin | — | keep (viewer strip, Performance level) |
| V · Ctrl+R | variations · re-run | — | keep (Performance card, take ctx) |
| Ctrl+Z / Ctrl+Shift+Z | — | stage undo / redo | keep; one history per Shot or per section: Q7 |
| Ctrl+Enter · Ctrl+Shift+Enter | Animate · Queue | Render frame | **Run ▶ · Queue** of the foot; Render frame leaves for Image |

**Image (Make and Edit in one suite; each key is scoped to the mode)**

| Key | Make (Generate + results) | Edit | Proposed |
| --- | --- | --- | --- |
| Ctrl+1 / Ctrl+2 | — (Catalogue loupe: 1:1) | zoom 100 % / 200 % | **Ctrl+1–3 always switch tabs.** Zoom 100 % → Ctrl+Alt+0 (strip *100 %*, CM › View); 200 % CM only; loupe 1:1 → Ctrl+Alt+0 too |
| Ctrl+S | save the panel | save the document | keep, per mode: both are "save what is in front" (Saved panels bookmark; Edit foot) |
| Ctrl+Enter · Ctrl+Shift+Enter | Generate · Queue | — | per mode: Make → Generate / Queue; Edit → the AI section's run / Queue the AI job |
| E | open the result in Edit (cat.edit) | Eraser | keep, per mode: E enters Edit; inside Edit it is the Eraser |
| Esc | close loupe / clear selection | cancel transform, polygon, crop; deselect | never leaves Edit by itself (Q1); *← Results* and the Make \| Edit switch do |
| X · V · Delete · Ctrl+D | reject · variations · trash · duplicate asset | swap colours · Move tool · clear pixels · deselect | keep, per mode (the mode is always visible on the switch) |
| 0–5 · 1–4 · 0–9 | rate | use candidate 1–4 · brush opacity | keep, per mode |
| [ ] | tile size | brush size | keep, per mode |

## 8. Gaps and questions

**Questions for the author** (the wireframes need an answer):

| # | Question | Why it matters |
| --- | --- | --- |
| Q1 | **Double-click on a result:** the loupe (today, C48) or Edit (03 §3)? And may Esc ever leave Edit? | Both are habits today; one gesture can't do both |
| Q2 | **A drop on the Image tab:** add references (Generate today) or open in Edit (Edit today, and 03 §3 "Edit without making")? Proposal: in Make mode references, in Edit mode a new layer, and *New document* in ☰ for "open as a document" | the two old tabs' drops collide on one tab |
| Q3 | **Edit's Save:** 03 says "Save writes a new version beside the original"; today Save writes the `.ora` document and *Save to Catalogue* writes the flattened asset. Do they become one verb? And **Close document** has no place in 03's foot | E1, E2, E4 |
| Q4 | **New angle:** only the sheet is built; D90 Q4 also wanted it in Edit's AI section as "Angle". Both, or the sheet only? | G33–G35 |
| Q5 | **Animate's form:** shot-level frames / fps / format in the Shot section and the card's own length and seed in the Performance card (A11)? Saved panels moved from browser storage to the project (A12)? Running jobs as takes in the Shot section or only in the Dock (NEW-A5)? | the Image to video card must keep everything today's five tabs hold |
| Q6 | **Stills from a stage in Image:** one Make column with a source switch (prompt only / From a stage), or a separate *From a stage* form? Stage's method has its own reference limit and a locked image 1 (S21–S23) | one ReferenceTray (D90 §8.2) vs two forms |
| Q7 | **Undo in Animate:** one history for the Scene (stage edits) and the composition (EffectCraft's engine history, AE2), or one per section? | S4, the Ctrl+Z row of §7 |
| Q8 | **Filmstrip view (A17):** keep as a viewer option, or as a thumbnail track of the timeline? | it is the only frame-overview today |
| Q9 | **The H3 card (A9):** keep a permanently locked card in the model picker, or hide it until H3 is wired? | 01 §11.6 lists it as dead UI |
| Q10 | **The proposed key set (§7):** K stays shuttle stop and Shift+K keys the selection; F frames the selection; extract on Alt+F; look through on 0; Ctrl+1–3 for tabs only | After Effects habits (03 §8) against one meaning per key (D90 §8.3) |

**Homes that are unclear in 03:**

- **Image's jump rail:** one rail that swaps Make's seven buttons for Edit's five with the mode, or both sets at once? The rail must not
  hold twelve buttons.
- **Right Inspector in Image:** Make shows the Catalogue's Inspector, Edit its Layers · Properties · History · Info. Mode-scoped, so two
  Inspectors share one region; 03 assumes this but does not say it.
- **Results of the For chip in Animate:** the For chip moves into the Shot section, which also lists the takes; whether the Bin drawer opens
  on the shot's page depends on 04 C2 (not yet built).
- **Story's *Make frame in Stage* / *Make clip in Stage*** (storyCommands): under D95 they become *Make frame ▸ From a stage* (Image) and
  *Make clip ▸ Animate* with the Pose-driven or Depth-guided card chosen. Story is built after Animate, so the commands need interim labels
  in AN1.
- **Render passes (NEW-S2)** feed two places: Image's *From a stage* and Animate's Plate / guide sequences. Which section owns the
  *Render passes* button and the stale state?

**Duplicates the new layout removes:**

- Edit's three colour-swatch sets (E29) → one in the column.
- Two transports (A18–A22, S26) → one; two frame counters → one (NEW-A6, NEW-S9).
- Two reference decks for stills (G14–G19, S22, NEW-S3) → one Refs section.
- Two still-making forms (Generate, Stage Render) → one Make column (S21–S24).
- Animate's Clips list and the Catalogue's clip view → the Bin drawer (A16, A32, NEW-A3).
- Edit's *Open the Catalogue* empty-state button → *← Results* and the Bin drawer (NEW-E8).
- Key camera and Key object → one *Key the selection* (S27, §7).

**What would be lost if the plan is followed as written:**

- **Close document (E4)** is not in 03's Image › Edit foot. Keep it in CM › Document and the Documents section.
- **The right Inspector's three tabs in Animate** (clip · frames · lineage) have no named place in 03's Selection section; this
  inventory puts them there as folds (A5, A24, A30, NEW-A7–A9). Without that, identity, harvested frames and lineage would have no home.
- **Image planes (S7)** stay drag-only, which breaks D32; AN1 needs a Scene command for them.
- **Rename object / camera (S13)** is double-click only today; AN1 should add the *Rename…* ctx command.
- **Animate's saved panels (A12)** live in the browser: moving the suite must not drop them; a one-time import into the project is needed if
  their storage moves.
- **The drop on the Edit tab** (F6) disappears with the tab; Q2 decides its replacement.

## 9. Counts

Per today's suite, the rows of §1–§4 (01's rows and the NEW rows):

| Suite | Rows | same | moved | merged | renamed | split | dropped |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Generate | 55 | 53 | 0 | 0 | 0 | 1 | 1 |
| Edit | 89 | 49 | 37 | 3 | 0 | 0 | 0 |
| Animate | 43 | 3 | 27 | 8 | 3 | 2 | 0 |
| Stage | 37 | 3 | 24 | 8 | 0 | 2 | 0 |
| **All** | **224** | **108** | **88** | **19** | **3** | **5** | **1** |

Not counted: the 16 routes and frame items of §5 and the 14 new functions of §6. Every inventory row of 01 §4–§7 appears: G1–G41, E1–E80,
A1–A33, S1–S28.
