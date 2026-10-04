# loom2 · proto01 planning documents

Written 2026-10-04 from (1) the loom / Loreweave Studio source and `.docs` at
`F:\source\repos\stubz-002-tripo-sf\loom\loom-loreweave-studio\`, (2) an inventory of this machine, and
(3) web research on the 2026 model and frontend-engine landscape. Everything here is a **proposal** until the
author approves it; decisions and their status live in 13.

## Reading order

| # | Document | What it settles |
| --- | --- | --- |
| 01 | [Rig and existing assets](01-rig-and-existing-assets.md) | the hardware/software facts every choice is bounded by; weights already on disk |
| 02 | [loom retrospective](02-loom-retrospective.md) | what loom was, which rules to keep, what to leave, measured FLUX.2 facts, lessons, code reuse map |
| 03 | [Vision, principles, MVP scope](03-vision-scope-and-mvp.md) | what loom2 is, its tenets, the four MVP suites, non-goals, success measures |
| 04 | [Model strategy](04-model-strategy.md) | **sourcing anchor** (ComfyUI convention), ROCm runtime policy, model picks for t2i / inpaint / i2v, licences, benchmark protocol |
| 05 | [Frontend engine evaluation](05-frontend-engine-evaluation.md) | Tauri 2 + PixiJS v8 compositor, loopback transport, video stack, formats, spikes |
| 06 | [Architecture](06-architecture.md) | processes, **ComfyUI as headless engine**, storage layout, data model, API, key flows |
| 07 | [UI frame](07-ui-frame.md) | the shell all suites share: regions, selection, verbs, keys, states |
| 08 | [Suite D · Catalogue UI](08-ui-suite-catalogue.md) | browse / group / judge / route |
| 09 | [Suite A · Generate UI](09-ui-suite-generate.md) | FLUX.2 t2i with the BFL JSON prompt tree (target a) |
| 10 | [Suite B · Edit UI](10-ui-suite-edit.md) | layered inpaint / refine editor (target b) |
| 11 | [Suite C · Animate UI](11-ui-suite-animate.md) | image-to-video with start/end frames (target c) |
| 12 | [Roadmap](12-roadmap.md) | spikes E0–E8, milestones M1–M7, gates, estimates |
| 13 | [Decision log and open questions](13-decision-log-and-open-questions.md) | D1–D27, Q1–Q14 (all resolved as of 2026-10-04) |
| 14 | [Post-MVP · Story workspace](14-post-mvp-story-workspace.md) | loom's storyboard design adopted as-is for the first post-MVP phase (D23) |

Planned companions (created when work starts): `90-journal.md` (append-only implementation journal with
real timestamps), `bench/` (the binding benchmark prompts and tasks from 04 §6).

## The plan in one paragraph

loom2 keeps loom's hard-won foundation (durable queue, atomic records, weights roster, token gate, lineage,
disk guard) and drops its storyboard domain layers for now. Model sourcing is anchored on the **ComfyUI
convention**, and a fresh, pinned checkout of Comfy-Org/ComfyUI runs headless as the engine so any model that runs there runs in loom2;
loom's proven FLUX.2 torch worker stays as the fallback. The frontend is Tauri 2 + React with a **PixiJS v8
WebGPU tiled compositor** for a true layered editor, all pixels moving over loopback HTTP. MVP = four suites
on one frame: **Generate** (FLUX.2 dev with the BFL JSON prompt first, Klein tiers later), **Edit** (layers,
masks, brushes, AI inpaint via Klein / LanPaint / FLUX.1 Fill / dev / Qwen-Edit, refine, PSD export),
**Animate** (Wan 2.2 I2V-A14B with first-last-frame, LTX-2.3 for speed and beats, MiniMax H3 as the hero tier)
and **Catalogue**, shipped as two build variants (`full`, `open`). Work starts
with eight spikes that retire the engine, renderer, transport and model risks on the actual RX 9070 XT, then
proceeds milestone by milestone with each suite's UI document approved first and a rig acceptance run
required to close.

## Conventions for this folder
- Numbered documents are specs; amend them the same day a decision changes and note it in 13.
- Measurements replace estimates in place, with the date and the exact stack (torch, ROCm, ComfyUI commit).
- Links to loom use repository-relative paths under `.docs/` and `orchestrator/`.
