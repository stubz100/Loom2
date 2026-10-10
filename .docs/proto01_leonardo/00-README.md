# loom2 · proto01_leonardo: Leonardo.Ai as a cloud engine

Written 2026-10-08 from (1) the complete Leonardo.Ai API documentation, mirrored into `source/` the same day, and (2) a code
map of the loom2 working tree (`main` at 4e0db08 plus the uncommitted D34 catalogue pass). Everything here is a
**proposal**: it starts only after the author accepts LD1 in 05, and accepted decisions then move into
`../proto01/13-decision-log-and-open-questions.md`.

**Status 2026-10-10: shelved by the author.** Committed for reference; LD1 is not accepted and no slice is scheduled. loom2 stays
local-only (ComfyUI). The `source/` mirror and the model tables date from 2026-10-08 and must be refreshed before any revival.

## Reading order

| # | Document | What it settles |
| --- | --- | --- |
| 01 | [Leonardo API overview](01-leonardo-api-overview.md) | v1 vs v2, the ten calls loom2 needs, lifecycle, moderation, limits, errors, money, privacy; what is still **unverified** |
| 02 | [Model catalogue](02-model-catalogue.md) | the 79 v2 models (generated tables) and the loom2 shortlist per suite |
| 03 | [Integration points](03-integration-points.md) | where Leonardo plugs into the orchestrator and frontend, file by file; invariants that must not break |
| 04 | [Development plan](04-development-plan.md) | slices L0–L6 with gates, effort and live spend; risks |
| 05 | [Decisions and open questions](05-decisions-and-open-questions.md) | LD1–LD12 (proposed), LQ1–LQ8 for the author, volatile facts |

## The plan in one paragraph

Leonardo becomes a **second engine behind loom2's own queue**, never a separate app area: the orchestrator alone calls
`POST /v2/generations`, polls `GET /v1/generations/{id}`, downloads the results into the project and hands them to the
finalisers that already turn ComfyUI outputs into assets, layers and clips, so provenance, lineage, durability and the
loopback-only CSP stay exactly as they are. Cloud jobs run in their own lane (no VRAM gate, a small concurrency cap), are
resumed rather than re-created after a crash, and pass a spend guard modelled on the disk guard; the key lives in Windows
Credential Manager. The gains are the models a 16 GB card cannot offer: **MiniMax H3 (`hailuo-03`) as the Animate hero tier
without local weights**, Kling 3.0, Veo 3.1, Seedance for first/last-frame video, FLUX.2 Pro and Nano Banana Pro for Generate,
Kontext / Nano Banana as instruction editors made mask-exact by loom2's own paste-back, Aurora upscalers and a sync
background remover. Work starts with a paid probe spike (L0) that answers what the documentation leaves open, then extracts
the engine seam that 06 §3d always described but the code never built (L1).

## Folder layout

```
proto01_leonardo/
├── 00-README.md … 05-decisions-and-open-questions.md     # the planning documents (hand-written; 02 §3 generated)
├── source/                                             # Leonardo.Ai's documentation, verbatim (third-party content)
│   ├── llms.txt, llms-v1.0.txt                         #   the readme.io indexes the mirror was built from
│   ├── docs/        (74)                               #   guides: one per model, webhooks, limits, errors, NSFW, PAYG, FAQs
│   ├── recipes/     (60)                               #   worked examples (Python / curl)
│   ├── reference/   (3)                                #   v2 endpoints, OpenAPI embedded
│   ├── reference-v1/ (48)                              #   v1 endpoints (reads, uploads, /me, limits, pricing calculator)
│   └── openapi-v2-*.json                               #   the v2 OpenAPI documents extracted from reference/
└── tools/
    ├── mirror_docs.py                                  # re-captures source/ (stdlib only)
    └── model_matrix.py                                 # regenerates 02 §3 from the v2 OpenAPI
```

Refresh, from the repo root: `python -I .docs/proto01_leonardo/tools/mirror_docs.py` then
`python -I .docs/proto01_leonardo/tools/model_matrix.py`, and review the diff of 02 §3 and `source/docs/deprecations-changes.md`.

## Conventions for this folder

- Same as `../proto01/00-README.md`: numbered documents are specs, amended the same day a decision or a measurement changes
  them; measurements go to `../proto01/90-journal.md` with the exact date.
- Claims about the API cite the mirrored file they come from; claims about loom2 cite the code path. **Unverified** marks a
  fact the documentation does not settle; slice L0 answers each one.
- `source/` is never edited by hand. It is Leonardo.Ai's content, kept for offline reference; the mirror date is in each
  page's `updatedAt` front matter and in this README.
- When LD1 is accepted, the proto01 documents named in 04 L6 are amended and this folder's status lines change from
  "proposal" to the accepted D-numbers.
