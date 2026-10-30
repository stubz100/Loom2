<!-- markdownlint-disable MD024 -->
# 13 · A build from scratch: a walker in profile through a busy fish market — M1–M16

The author asked, 2026-10-30: "can you run another build from scratch? a character walking through a busy fishmarket, where the camera
moves parallel the character's path and constantly recording its face from the side. Is this possible?"

Their answers:

- the crowd painted into the market, plus two performed extras;
- spike E44 (Q32, a head in profile) before the walker is performed;
- about 10 s.

The project is `F:/loom2-projects/market-walk`, with its app state in `F:/loom2-projects/_market-state`. It ran on its own orchestrator
on 8766 and Vite on 1420, driven in a visible Edge over CDP, on the real engine, one job at a time (rule 10).

## 1. What was built

- **World:**
  - the Look (*Market morning*: no "cinematic", which letterboxed W65's set pictures);
  - three characters, each from Sheet to casting, hero and references, Build's Klein A-pose front and back, and the body fitted:
    - **Mira**, the walker: a yellow oilskin, a long braid;
    - **Bram**, a fishmonger: a white rubber apron;
    - **Hanne**, a passer-by: a dark-red coat, a basket;
  - the place **Fish market**: a set picture, then a Street set (5.5 × 30 m), its 5 faces filled.
- **Shots:** one shot, *Market walk*, its scene at the place.
- **Clay:**
  - Mira walks 8 m down the aisle in 10 s (`Walk_Loop` along a path);
  - the camera is keyed to track 2.4 m to her side on 24 mm, her face in profile;
  - Hanne walks the other way behind her and crosses her at about 5 s;
  - Bram works at his counter (`PickUp_Table`, looped).
- **Performance:** the final (161 frames at 16 fps), each character in its D163 window (×1.7, ×2.2, ×2.4), three batches each, queued
  by *Perform the owed layers ▶* (D164). The matte check retried Hanne's and Bram's strays once with BiRefNet; the first was kept both
  times.
- **Final:** the composition, the render (`clp_4d72b989`, 241 frames at 24 fps), and the shot marked final.

Where the mouse lost to the selectors (M8), the cast's places, the walk paths and the camera keys were written into the stage file
through `PUT /stages/{id}`. The clips were applied in Clay's motion panel, so the app timed the walks itself.

**E44 → D166** came first, as asked. Under D158's eye-order rule Mira's true profile read as facing away on 159 of 161 frames: she
would have been performed from behind, her face turned away on 3 of 3 seeds. Read by the ears instead (D166), she walks in clean profile
on 3 of 3, and the final shot shows it.

## 2. The register

- **M1:** a colour row starts red (#C0392B) whatever the outfit says. Mira's "mustard-yellow oilskin jacket" got a red "oilskin jacket"
  chip, and the subject line carries "#C0392B oilskin jacket" beside "mustard-yellow"; the sheet contradicts itself until the swatch is
  noticed.
- **M2** (= W3): opening a character's Make logs a 422 for `GET /loras?model_id=`.
- **M3:** Bram's casting pictures (the hero, the references) show an olive apron, his A-pose the white one the sheet asks for. The swatch
  was set right after the colour row was added, and the casting went out before it took. The hero and the animation reference disagree,
  and nothing says so; the performance follows the A-pose (white).
- **M4:** Hanne's basket ("a wicker shopping basket on her arm") is dropped by her A-pose. It appears in her performance anyway, from the
  prompt's words, so it comes and goes with the words, not with a prop.
- **M5 · high:** the set picture's framing words ("a wide view … the floor and the walls in view from side to side") override the place's
  own point of view. Asked for "a long row of fish stalls … seen straight on from across a wide aisle", all 4 candidates look down the hall.
- **M6 · high:** a busy place has no way in. The set picture must be "nobody in it … nothing moving" (it is projected, so people would be
  painted on the walls), and nothing in World offers a painted crowd or extras for a place; a few people came anyway, standing at the
  counters.
- **M7:** editing the set-picture framing words (D162) turns the run into an ordinary look: the foot becomes "Give Fish market a look ▶"
  and the pictures land in the bin, not among Build's candidates. They still looked down the hall (4 of 4): the picture model takes no
  camera direction from the words, and nothing else asks for one.
- **M8** (≈ W36): Clay's Figures + popover and the selected figure's Inspector show the same name buttons. After the first figure is
  added, a second click re-binds it instead of adding one, and the figure keeps its first name (one "Mira" bound to Hanne).
- **M9 · high:** every fitted body is "female · 1.75 m · average", Bram (a heavy-set man) and Hanne (a small elderly woman) included. The
  fit takes no height, build or figure from the pictures or the sheet, and nothing flags it; Bram would be performed on a woman's skeleton.
  Set by hand in Build › Body.
- **M10** (= W34): a figure added from Figures + lands where the viewport's centre ray hits: Hanne stood at y = 2.10 m, in the air.
- **M11:** Build › Body's figure buttons (♀ / ♂) have no label and no tooltip.
- **M12 · high:** the tracking camera looks straight at the street set's stall fronts, which the set picture saw only at a grazing angle.
  In the shot they are a heavy smear of stretched people and crates. Fill leaves them ("seen"), and the plate (the built set, D143) shows
  them as they are.
- **M13:** Mira's long braid, the most distinctive thing in her casting, is gone in profile. She is performed from her front A-pose,
  which does not show what hangs behind; a character seen from the side has no reference for the side.
- **M14:** the street set's floor fill carries bright white ovals (lamp reflections painted in), which slide across the floor as the
  camera tracks.
- **M15:** Bram faces the aisle with his counter behind him, so the fishmonger's work reads as a man standing in front of his stall. The
  clip's own facing is not shown before it is applied.
- **M16:** after the render a red banner reads "B4: 12 things on no page went to a home (world/place/prf_6d0533e5/v1 12)": housekeeping
  shown to the author as an alarm.

## 3. Measured

| What | Time |
| --- | --- |
| Look sample | 37 s |
| Casting, 4 pictures a character (FLUX.2 dev) | 2.7–3.4 min |
| Klein A-pose candidates · back-view candidates | ≈ 30 s · ≈ 70 s |
| Set picture, 4 candidates | 2.6–2.7 min (twice: M5, M7) |
| Set fit · 5 faces filled | 4 s · 80 s |
| E44 (15 takes of 77 frames, the spike's own engine) | 116–195 s each, ≈ 33 min |
| A performance, 3 batches in its window | 286–364 s |
| Mattes (3, then 2 automatic retries) | 62–107 s each |
| Assembly · composition render | 65 s · 9 s |
| The app's GPU time, 58 jobs | ≈ 48 min |

## 4. Is it possible?

Yes. The walker is performed whole in her window, side-on, her face in profile all the way, the camera keeping pace. The crossing and the
stall work hold their layers.

What it does not give yet:

- a market that looks busy (M6);
- a background the camera can look at side-on (M5, M12);
- the side of a character its references never showed (M13).
