<!-- markdownlint-disable MD013 -->
# 01 · The build log — "Followed", from an empty project

2026-11-03, on `d7b48c2`. Every step below is the product path (the shell's buttons and fields), driven by a Playwright step script in a visible Edge;
the screenshots are `img/NN-*.png`, the controls each step used are in [02](02-function-register.md) and `data/functions.jsonl`. GPU jobs ran one
at a time on the real engine.

## 1. The project and the Look (07:57–08:00)

1. **Project › New project…** — folder `F:/loom2-projects/propo02-followed`, name *Followed*; the format is fixed (16:9 · 1920×1080 @ 24 · Draft).
   `img/01-new-project-dialog.png`, `img/01b-after-create.png`.
2. **World › Look:** the sample scene (*a narrow cobblestone street in an old European town …*), *Add style*, the tile selected, named *Old town, late
   afternoon*, its fragment written by hand (*photographic, natural light, late afternoon sun low across the street, long soft shadows, muted warm colours,
   35 mm lens look, shallow depth of field, fine film grain*) after trying one Look-words chip (it appended only "painterly storyboard"), ★ default,
   ⚙ *Make a sample image* — 59 s with the engine's cold start. The sample is a cobbled shopping street in low sun: the Look reads right.
   `img/02-look-style-editor.png`, `img/02-look-sample-done.png`.

## 2. Nora (08:00–08:11)

3. **Characters › + New** *Nora*. **Sheet:** label *street coat*; appearance *a woman in her early thirties, slim, pale, dark brown hair tied back in a low
   knot, sharp alert eyes, a straight nose, no make-up*; outfit *a long dark-green wool coat buttoned up, a cream knitted scarf, dark jeans, flat brown
   leather ankle boots, a brown leather shoulder bag on a long strap*; one bound colour `#2F4F3A` *wool coat*; marks *a thin silver ring on her right hand*.
   The *as sent* line composes it to 68 words. `img/03-character-sheet.png`.
4. **Make:** the column read in full (02 §2.3); framing chip *full body*; the note *walking towards the camera on a cobbled street, mid-stride, her coat
   open at the hem*; ⚙ **Give Nora a look ▶ ≈ 3 min** (FLUX.2 dev, 4 pictures) — 205 s. The four are near-identical. `img/03-casting-done.png`.
5. **The bin:** tile 1 right-click › *Make it the hero*; tiles 2–4 › *Use as a reference*. `img/04-tile-menu.png`.
6. **Build › Animation reference:** ⚙ *Make reference candidates ▶*, *back-view*, *side-view* (Klein 9B, 2 each) — 231 s for the six; the first of each
   picked (*Front* ran the body fit, 6 s). **Body:** fitted ♀ 1.66 m · slim. Readiness: *Ready for Clay*. `img/04-apose-candidates.png`, `img/04-apose-picked.png`.

## 3. The street (08:12–08:20)

7. **Places › + New** *Cobbled street*; Sheet: label *late afternoon*, appearance (60 words: the shop fronts, awnings, signs, the three-storey plastered
   houses), marks *a bakery with a blue-green front and a bell over the door*.
8. **Make:** the *set picture* chip (its sentence logged in 02 §3.2); ⚙ **Make Cobbled street's set picture ▶** — 162 s, 4 candidates, all looking down the
   street from the same spot with café tables in the middle. `img/05-place-build-candidates.png`.
9. **Build:** candidate 3 › *Use as the set picture*; ⚙ **Build the set ▶** (MoGe, 10 s) — fitted as a Street by itself, 8 × 30 m, pavements 2 m,
   fronts 3.47 m, camera 1.6 m; status *5 faces to fill · 94 % of the set* (only the far end counted as seen). The faces named (road, fronts; the pavements
   wrongly at first — my script gave them the far-end words); ⚙ **Fill what the picture never saw ▶** — 5 Fills, 85 s; the pavements named again and
   ⚙ *Fill this face ▶* from each face's right-click (12–18 s each). **Bench ▶**: the set in Clay — the fronts read as shop fronts, the road as metre-wide
   slabs. Readiness: *Ready for Clay*. `img/05-set-built.png`, `img/05-set-filled.png`, `img/05-set-bench.png`.

## 4. The passers-by (08:21–08:23)

10. **Man with a newspaper** and **Woman with shopping**, each: + New, the Sheet (label, appearance, outfit; no colours, no marks), then straight to
    **Build › ⚙ Make reference candidates ▶** with no hero and no references — 25 s and 28 s from the words alone; *Front* picked (the fit); the body set by
    hand: ♂ 1.82 m broad, ♀ 1.58 m average (the fit had guessed ♀ 1.75 for both). The man's readiness adds *⚠ carried: folded newspaper*. Both stay *2 to
    go* (hero, references) and Clay takes them. `img/06-man-built.png`, `img/06-woman-built.png`.

## 5. Shot 1, "the street" — Clay (08:24–08:44)

11. **Shots › ＋ New shot ▾ › New shot in a new scene**; the description; **scene ▾ › A new scene at a World place › Cobbled street** (the submenu item
    needed a second click). Clay opens on the set through *Camera 1* (the picture's camera: 26.9 mm at (0.26, 1.6, 5) looking down −z).
    `img/07-scene-menu.png`, `img/07-scene-at-place.png`.
12. **The range** 0–240 (10 s) in the transport. **Figures +** Nora, the man, the woman — all three landed at the same spot (0.68, 0, −14.6), the viewport's
    centre ray. Placed by the editors' position fields: Nora (0.5, 0, −14), the man (−2.6, 0, −4) turned 180°, the woman (2.9, 0, −8). (Nora had first been
    put at z = −18, behind the far end: the street is centred on the origin, z −15 … 15.) `img/08-figures-placed.png`.
13. **Nora's walk:** Walk_Loop (the Godot library) picked; *Draw a path* — three floor clicks aimed by the driver (three calibration clicks read back
    through the API, a 1/depth fit) landed at (0.6, −14.6) → (0.5, −10.0) → (0.3, −0.6); *along Nora's path*, foot lock, feet on the floor; **Apply to Nora at
    the playhead** — a block of 449 frames at ×1 (0.75 m/s), then the block's right-click **Speed ▸ ×1.5** → 316 frames. One wrong pick (my selector took
    *Chest_Open*) was taken back with **Undo**. `img/09-nora-walk-applied.png`, `img/10-block-menu.png`.
14. **The man:** a two-click path (−3.4, −3.3) → (−3.7, −14.6) on the left pavement, Walk_Loop along it (353 frames, walking away). **The woman:**
    Idle_Loop in place, **Loops ▸ 4×** (241 frames).
15. **The camera** leads her, walking backward: Camera 1's editor — frame 0: position (0.3, 1.45, −10), target (0.5, 1.2, −14), 35 mm, **Key camera**;
    frame 240: position (0.3, 1.45, 1.5), target (0.5, 1.2, −2.5), **Key camera**. `img/10-frame-0.png`, `img/10-frame-120.png`, `img/10-frame-240.png`.
16. **The glance:** Nora selected, **Pose Nora**; **Key object** at 112 (the walk as it is); at 135 the joint select › spine, neck, head, each *y = 30°*,
    **Key object**; at 165 the three back to 0, **Key object**; **Done posing**. The key at 135 holds the *stand* preset with only the head turned (02 §5.5):
    she stands and turns while the path carries her. A stray key my exploration had put on the set was removed with *Remove the keys at this frame*.
    `img/11-glance-135-done.png`, `img/11-glance-150.png`.
17. **The back views:** the man's track read *no back view* from 5 s; the mark's right-click › *Make Man with a newspaper's back view in World ▸* opened his
    Build; ⚙ *Make back-view candidates ▶* (28 s), *Back* picked; the same for the woman (her first 2.5 s are back to the camera). The Shots tab reopened the
    shot at Flow; **rail › Clay** back. `img/12-man-back-view.png`.

## 6. Shot 1 — Performance (08:49–)

18. **rail › Performance:** the column read in full (02 §6). **Make the final shot…** › the dialog (*161 frames at 848×480, 5 layers — the plate, 3 figures,
    0 props and the shadows*) › **Split into layers** — the passes rendered in the page (1449 pictures, ≈ 1 min), the plate from the built set at once.
    ⚙ **Perform the owed layers ▶ · ≈ 36 min on the GPU with the plate and the face work** — one Wan Animate job per character batch, about 2 min 10 s each.
    `img/13-final-made.png`, `img/13-performing.png`.

## 7. Shot 2, "the door" — Clay (09:00–09:04), while the GPU performed shot 1

19. **＋ New shot ▾ › New shot in a new scene** (a second *Shot*); the description; the scene at *Cobbled street* again (its own stage); range 0–96 (4 s);
    Camera 1 by its fields: position (2.6, 1.5, 0.5), target (−3.2, 1.1, −5.5), 35 mm — a static camera on the right pavement looking across at the left
    fronts. **Figures + › Nora** landed on the shop front's foot (−3.6, 0.12, −6.3); placed at (1.0, 0, −2.5). Walk_Loop picked; the path: nine calibration
    clicks (two landed on the front and were dropped), a homography fit, then three clicks → (−1.0, −4.0) → (−2.5, −5.2) → (−3.8, −6.0), the last on the
    front's foot. The first *Apply* landed at frame 96 (the playhead); *Remove the clip*, the playhead to 0, *Apply* again, **Speed ▸ ×1.5** → 78 frames:
    she walks into the pharmacy's door, back to the camera, and stands at the wall for the last second. `img/14-shot2-frame-48.png`.

## 8. Shot 1 — the layers, the assembly, Final (09:00–09:27)

20. The seven Wan Animate batches took 11 min (08:56–09:07), not the 36 promised; then three mattes (1 min each) and two face passes (4–5 min each,
    the *face work*). **The layers:** plate done; Nora *done · 1✓ 2✓ 3✓ · identity 0.19 · low · window ×1.9*; the man *identity 0.49 · matte strays
    49/49*; the woman *0.48 · matte strays 80/80*. `img/15-performance-layers.png` (the woman's first take: a studio, a second figure).
21. **Assemble ▶** (64 s): RIFE to 24 fps, the stack man · woman · Nora. **rail › Final:** the composition with every layer and its matte, the blend modes,
    the render settings (02 §7). **Render the finished shot ▶** — 14 s, 241 frames, `clp_2709fd56`. **Mark the shot final ✓** (the dialog), done.
    `img/16-final-level.png`, `img/16-rendered.png`, `img/16-shot1-render-sheet.png`.
22. **What the render shows:** Nora walks the street toward the leading camera in her green coat, stops at 5.6 s with a slight head turn, walks on; the
    passers-by are not in it (their mattes are empty, 03 P19); the road is metre-wide slabs (P5); the top corners are black (P20).

## 9. Shot 2 — Performance (09:28–)

23. Shot 2's card › **rail › Performance › Make the final shot…** (*65 frames at 848×480, 3 layers — the plate, 1 figure, 0 props and the shadows*) ›
    **Split into layers** › **Perform the owed layers ▶ · ≈ 4 min on the GPU with the plate**.

## 10. Shot 2 — the final (09:29–09:34)

24. One Wan Animate batch (1 min 45 s), one matte (28 s); Nora's layer *done*, no strays (`cover_min 0.81`), no face pass (her head is too small
    from behind). **Assemble ▶** (13 s). **rail › Final** opened on **shot 1's composition** (*shot · 161 frames*, the man's and the woman's layers)
    under shot 2's URL, *Mark the shot final* greyed with *no clip yet* (03 P23); back to Performance, Final again, a reload, and shot 2's own
    composition came; **Render the finished shot ▶** (3 s, 97 frames, `clp_fc61eaf3`), **Mark the shot final ✓**. `img/18-shot2-render-sheet.png`.

## 11. Episode — the cut and the movie (09:34–09:38)

25. **tab › Episode:** Finals *✓ 1 · Shot · final*, *✓ 2 · Shot · final*; *Assemble from the Flow…* greyed (*no cut open*). **New cut…** (the dialog)
    › *Followed*. *Assemble from the Flow…* still greyed: the Flow has no Start and no edges (03 P25). Each shot's **+ Add to the end of the cut** →
    2 clips, 338 frames, 14.08 s. **Render the movie** — 11 s: `timelines/tl_2bdc101c/followed/followed.mp4` (1920×1080 @ 24, the mix beside it).
    `img/19-cut-open.png`, `img/19-lane.png`, `img/19-movie-rendered.png`.

## 12. The Bin (09:38)

26. **tab › Bin:** World 55 (Characters 18 · Places 36 · Look 1), Shots 20 (15 · 5), Episode 1, Imports 0. The place's 36 are its set's working files
    beside its four candidates. The project folder is 1.2 GB. `img/19-bin.png`.

## 13. Measured

| What | Time |
| --- | --- |
| The Look's sample (Lumina 2, cold engine) | 59 s |
| Casting, 4 pictures (FLUX.2 dev), promised ≈ 3 min | 205 s |
| Klein 9B reference make, 2 pictures, promised ≈ 24 s | 25–57 s (six jobs 231 s) |
| Body fit (keypoints) | 6 s |
| Set picture, 4 candidates (FLUX.2 dev), promised ≈ 3 min | 162 s |
| Set fit (MoGe) | 10 s |
| Fill, 5 faces · one face again | 85 s · 12–18 s |
| A reference make from the Sheet alone (no hero) | 25–28 s |
| Split into layers (the passes in the page) | ≈ 60 s |
| Wan Animate, one character batch (848×480), promised ≈ 36 min for seven | 1 min 45 s – 2 min 10 s (seven in 11 min) |
| Matte (BiRefNet), 49–161 frames | 28 s – 1 min 40 s |
| Face pass (D164), each | 4–5 min |
| Assemble (RIFE to 24 fps), 161 · 65 frames | 64 s · 13 s |
| Composition render (effectcraft, CPU), 241 · 97 frames | 14 s · 3 s |
| The movie (FilmCraft, CPU, 14 s) | 11 s |
| The app's GPU time, 16 runs | ≈ 50 min; the whole build 07:57–09:38 |
