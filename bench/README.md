# loom2 benchmark set (binding for "done", 04 §6 / D14)

Fixed inputs that every model, format and milestone is measured against on the rig. Results go to the
journal (`.docs/proto01/90-journal.md`) with the exact stack and synchronised timings; never edit a bench
file after results exist for it — add a new numbered file instead.

## t2i/ — 10 BFL-schema JSON prompts (FLUX.2)

One recurring character (red braids, freckles, green hooded wool cloak, brass compass) and one recurring
secondary (grey-bearded captain) so identity consistency across prompts can be judged, plus deliberate
stress axes.

| # | File | Stresses |
| --- | --- | --- |
| 01 | `01-alley-rain.json` | multi-source lighting, palette, legible sign text, low angle, shallow DoF |
| 02 | `02-captain-cabin.json` | two subjects with distinct poses, interior, single practical light |
| 03 | `03-cliff-chase.json` | extreme wide, tiny subjects, motion, group of extras, deep DoF |
| 04 | `04-wanted-poster.json` | typography (two text strings), flat graphic style, straight-on insert |
| 05 | `05-rooftop-night.json` | silhouette + rim light, profile pose, negative space, low angle |
| 06 | `06-fish-market.json` | crowd, depth layering, sign text, hood-up identity |
| 07 | `07-portrait-grief.json` | expression, tight close-up, 85 mm / f1.8 look |
| 08 | `08-storm-deck.json` | action, water, dutch angle, two subjects, hard key from lightning |
| 09 | `09-lighthouse-map.json` | readable handwritten label, high angle over the shoulder, lit from below |
| 10 | `10-dawn-departure.json` | wide, warm/cool split, small distant secondary subject, mist |

### Scoring (per image, 0–2 each; record the sum and the misses)

| Axis | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Subject identity | wrong character | partial (e.g. braid but no freckles/cloak) | all listed traits |
| Position & pose | ignored | roughly | as specified (thirds, orientation, action) |
| Camera (angle, lens feel, DoF) | ignored | one of three | all three read correctly |
| Lighting | generic | key present | key + fill/rim as described |
| Palette | unrelated | dominant colours match | all listed hexes recognisable |
| Background & text | missing | present, text garbled | present, text legible |
| Style | off | close | painterly concept-art / stated style |
| Artefacts | severe (hands, faces, duplication) | minor | none at 100 % |

Always record: model, format, size, steps, guidance, sampler/scheduler, seed, engine exec time, sampling
time, VRAM free after, ComfyUI commit, torch version.

## inpaint/ — 5 tasks (to be added in M0 close-out)
object removal on texture · clothing change · background swap · outpaint 25 % · face-region fix. Each task =
source PNG + mask PNG + prompt + expected outcome; scored on seam visibility, colour match, identity, time.

## i2v/ — 5 tasks (to be added before E4)
character turn · walk cycle · two-board FLF with pose change · camera push · dialogue gesture. Each task = start
PNG (+ end PNG) + prompt; scored on identity (ArcFace FaceSim across frames, advisory), motion plausibility,
end-frame reach, time.
