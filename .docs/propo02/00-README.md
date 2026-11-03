# propo02 · A scene from scratch, and the record of every control it took

Started 2026-11-03 at `d7b48c2`. **Status: built, 07:57–09:38; the record is complete; the author's look, the rethink [04](04-rethink.md) and its answers [05](05-answers.md) → D181 the same day; nothing built yet.**
Nothing in the code was changed; nothing is committed.

**What came out:** two shots, 14 s, `F:/loom2-projects/propo02-followed/timelines/tl_2bdc101c/followed/followed.mp4` — Nora walking the cobbled
street toward a leading camera, a stop with a slight head turn, then walking up to the pharmacy front. The passers-by were performed but their
mattes came out empty, so the finished shot has one person in it; the glance over the shoulder could not be blocked as a correction on the walk.
Twenty-eight findings, P1–P28, are in [03](03-findings.md); every control is in [02](02-function-register.md).

## The request

The author, 2026-11-03:

> Loom2 has a great range of functionality, but somehow it is packaged wrong. I think the world/shot/episode structure is good, but the
> underlying functionality needs refinement. A lot of functionality is restricted to quickly tackle a specific problem — like if they were
> presets. The world builder part should be working like artcraft — with the obvious differences reflected, like the generation is local,
> not API, etc…
>
> Assemble a scene from scratch, where a woman is walking steadily on a cobblestone street, and checking behind her shoulder if anybody
> is following her. The street has a lot of storefronts and a few pedestrians. Eventually she storms into one of the stores.
>
> While you're assembling this scene, please make a record of every function (button / setting) you use in the application — we will
> investigate later if these functions could have been broadened to get a better or a more diverse result.

## The documents

| # | Document | What it holds |
| --- | --- | --- |
| 00 | this file | the request, the setup, the scene as planned, the status |
| 01 | [The build log](01-build-log.md) | what was done, step by step, with what came out and the timings |
| 02 | [The function register](02-function-register.md) | **every control used**, by layer: what it is, what it took, what it offered, what it did not — the material for the later broadening study |
| 03 | [Findings](03-findings.md) | what got in the way (P1…), what the scene still lacks, the author's look |
| 04 | [The rethink](04-rethink.md) | **the proposal:** Clay as a layer of its own on the top rail (the 3D Library made from World's pictures, the scene editor with Build \| Record), the shot as a card that lists what it owns, the Bin's homes by kind; the questions Q1–Q13, the waves C0–C6, the spikes E59–E60 |
| 05 | [The answers](05-answers.md) | Q1–Q13 answered as recommended → D181; the order of the waves and their rig checks |
| `data/functions.jsonl` | | the raw record: one line per use of a control, timestamped, written by the driver as it clicked |
| `img/` | | screenshots of every screen touched |

## The setup

- The project `F:/loom2-projects/propo02-followed` ("Followed"), new and empty; its app state in `F:/loom2-projects/_propo02-state` (the author's
  `.loom2_state` was not touched; the state's settings are the market walk's, the same engine and model roots).
- Its own orchestrator on 8766 (`python -m loom2.main --port 8766 --state …`), Vite dev on 1420, driven in a visible Edge over CDP
  (`--remote-debugging-port=9333`, its own profile) by small Playwright step scripts — the same method as the two walkthroughs and the
  market walk (proto01_UI2 12, 13).
- The real engine, one job at a time (rule 10). The author shut their own app down at the start.
- The product path only: everything through the shell's buttons and fields. Where a mouse control cannot do it, the record says so
  and the workaround is named (the register's *reach* column).

## The scene, as planned

| Shot | What happens | Clay / Performance |
| --- | --- | --- |
| 1 · The street | A woman walks steadily down a cobbled street lined with storefronts; a few pedestrians. The camera leads her, walking backward. | a walk along a path; two extras; a tracking camera |
| 2 · The glance | Mid-walk she looks back over her shoulder: is anyone following? | the walk continues; a head turn / look-back key |
| 3 · The door | She quickens and storms into one of the stores; the door swings. | a turn off the path into a doorway; the camera holds |

The world: one character (the woman), two or three passers-by, one place (the street with storefronts), the Look.
