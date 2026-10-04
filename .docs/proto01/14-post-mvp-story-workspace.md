# 14 · Post-MVP · Story workspace — adopted as-is from loom (D23)

Decision D23 (2026-10-04): loom's storyboard design was analysed in depth and never built, so loom2 adopts it
**unchanged** as the first post-MVP phase, then holds a refining session once it runs on loom2's foundation.
This document is a pointer and an adoption checklist, not a re-specification.

## 1. Source documents (loom repository, `.docs/`)

| Document | What it defines | Adopt |
| --- | --- | --- |
| `kb-storyboard01.md` §1–§9, §10.0 (R1–R170) | product intent, four layers L1 StoryBible → L2 Asset Library → L3 Shots & Takes → L4 Narrative graph, Story Bundle layout, AssetProfile versioning (R46–R61), character bootstrap loop (§4.1), Muse (§7), phases P0–P6 (§9.2) and every numbered rule | as-is; rules already kept by loom2 are listed in 02 §2 |
| `kb-loom-p1.md` | L1 Bible + L2 Assets + casting / expansion / curation; coverage-cell vocabulary (§7.1) and dataset recipes | as-is, layered over the Catalogue (collections → AssetProfiles) |
| `kb-loom-p2.md` | LoRA training (ai-toolkit on ROCm), template captions, proxy readiness, promote-to-version | as-is; uses D25's LoRA slots |
| `kb-loom-p3.md` | Shots & Takes: compositor + take timeline, LTX sketch → Wan Animate drive tier, frame-continuity R&D, voice/lip-sync tiers, finalize gate, PNG-seq masters (R161) | as-is; the Animate suite and Clip model are its substrate |
| `kb-loom-p4.md` | Flow graph (flat + Jump nodes, R74/R146), Muse full (R14/R136), VLM online (Qwen3-VL-4B + Embedding-8B, R137/R144), `project_context.json` / facts / GraphRAG (R145/R170) | as-is; every AI call stays a queued job (R141/R142) |
| `kb-loom-p5.md` | Episode / export: render list (R148), single-lane timeline with overlap transitions (R157), EDL + FCPXML + srt to Resolve (R151/R152) = alpha gate (R165/R167) | as-is |
| `kb-loom-p6.md` | overflow: 3D (`trellis2`), effect plugin API, engine export | as-is, lowest priority |
| `kb-loom-ui.md` §4 (D1–D10) | the workspace tabs World · Assets · Shots · Flow · Episode and their panels | the loom2 frame (07) already reserves the Top-bar tab slots and the Dock timeline zone (D8) |

## 2. What loom2's MVP must keep open for it (checked in 06 §5)

- Collections can become AssetProfiles with versions; assets keep stable ids and `asset@version`-style lineage.
- Clips are PNG-sequence masters + proxy; `format.target` is the finalize gate; fps conform policy from E9.
- Every AI/LLM call is a queue job; nothing auto-spends GPU (R141/R142); staged-then-queued stays (R118).
- Style handling: one style per generation, appended not prepended (R47/R104), stamped as `style_id` at write
  time (loom lesson 7) — the Generate suite's presets/snippets are the seed of L1 style fragments.
- Project format fixed at creation (R45/R56); project cap and disk guard (R72/R96).

## 3. Lessons from loom to carry into the refining session (02 §7)

LoRA identity holds only at the trained resolution; photo-tuned heuristics misjudge stylised sets, keep meters
advisory; provenance must be stamped at write time; verify on the rig, not in CI; append-only journals.

## 4. Refining session agenda (after MVP acceptance)

1. Re-read §1 documents against the shipped loom2 data model and API; list deltas.
2. Decide which loom P1 flows (Cast → Expand → Curate) become Catalogue/Generate verbs vs a separate workspace.
3. Re-plan P3 video tiers against the measured Wan / LTX / H3 results and E9.
4. Re-scope Muse (P4) against current local VLMs and the queue-only rule.
5. Produce `15-story-workspace-plan.md` with milestones; until then this pointer stands.
