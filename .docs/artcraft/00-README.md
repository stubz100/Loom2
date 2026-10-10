# ArtCraft study — documentation index

A study of **ArtCraft** ("the IDE for artists", `F:\source\repos\artcraft`, `main` at `3e5793b693`, 2026-10-06, v0.41.0), written
2026-10-08 for loom2. Its two purposes:

1. a thorough overview of how ArtCraft is built, and a plan for how to build such an application from the ground up;
2. a comparison with loom2 and concrete, prioritised proposals for improving loom2.

Method: the source was read directly (Rust crates, frontend apps and libraries, docs, scripts, CI, git history); claims cite repo-relative
paths so they can be re-checked. Nothing in the ArtCraft checkout was modified.

## Reading order

| # | Document | What it covers |
| --- | --- | --- |
| 01 | [Overview](01-overview.md) | what ArtCraft is, feature map, model catalogue, architecture at a glance, stack, size, strengths and weaknesses |
| 02 | [Backend architecture](02-backend-architecture.md) | the Tauri/Rust app: startup, state, commands and envelope, job pipeline, task DB, pollers, events, accounts; the provider layer (`artcraft_router`, hosted API, third-party clients) |
| 03 | [Frontend](03-frontend.md) | Nx workspace, shell and pages, state, Rust bridge, model catalogue, generation UX, library, settings and keybinds, the adapter seam, tests |
| 04 | [Creative surfaces](04-creative-surfaces.md) | 2D canvas (pagedraw), 3D stage (pagescene), video editor (OpenCut port), moodboard and smaller libraries |
| 05 | [Engineering practices](05-engineering-practices.md) | dev loop, build and release, CI, performance method, agent conventions, **licence** |
| 06 | [Ground-up implementation plan](06-ground-up-implementation-plan.md) | **deliverable 1** — how to build ArtCraft's scope from an empty repository: decisions, principles, architecture, phases 0–9, cross-cutting plans, risks |
| 07 | [loom2 comparison and improvements](07-loom2-comparison.md) | **deliverable 2** — side-by-side, where loom2 is ahead, proposals P1–P19 with effort and order, what not to copy |
| 08 | [Delivery plans](08-delivery-plans.md) | one plan per proposal (goal, today, design, slices, tests, executable acceptance, docs, risks, effort), waves H1–H4 / X1, spikes E10–E14, the Stage suite milestone, decisions to record |

## Five things to know first

1. **ArtCraft runs no models locally.** It is a rich desktop client for cloud generation (its own hosted API with 62 models, fal, and the
   user's own Midjourney / Grok / Sora / World Labs sessions); the media library lives on its backend.
2. Its lead is in **creative surfaces** (3D staging with cameras and posing, a full timeline editor, moodboards) and **model breadth**,
   not in the core engineering loom2 cares about.
3. Its best ideas are structural: **editors as libraries behind host adapters**, **models as served capability descriptors**, a **pure
   plan → finalize → send** request pipeline with an explicit mismatch policy, and **opaque origin ids echoed from request to completion**.
4. Its debt is instructive: three state paradigms, eight polling loops, a task DB reset on every schema change, permissive security
   settings, no PR CI, and an editor whose projects are never reopened.
5. **Licence:** its code may be used privately but not to build a competing product — borrow ideas, not files (05 §7).

## Conventions

- Proposals in 07 are proposals; decisions belong in [`../proto01/13-decision-log-and-open-questions.md`](../proto01/13-decision-log-and-open-questions.md).
- Facts are dated to the commits above; re-verify before acting on a detail that may have changed upstream.
