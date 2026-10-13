# 17 · Suite F — Story (bible → cast → shots → flow → episode) — UI document and plan

Status: **approved 2026-10-13 (D85) with the §14 defaults; SY0 built 2026-10-13, SY1 next.** Proposed the same day as the output of the refining session
14 §4 asked for, held after every ArtCraft proposal (P1–P19) was built (08 §1). Source: loom's storyboard design (14 §1:
`kb-storyboard01.md` L1–L4 and R1–R170, `kb-loom-p1..p6.md`, `kb-loom-ui.md`), adopted as-is by D23 and now **re-planned on
loom2's shipped foundation** — nothing of loom's intent is dropped, but every piece is mapped onto what already runs: groups and
`@`mentions (D73), the Stage suite (D81), the Animate clips (PNG masters + proxy), the single-lane timeline (D83), the queue with its
origins (D66) and the model registry (D65). Frame rules: 07 (D32 mouse-first, D34 drags, D69 lazy suites, D71 drops explain
themselves, D72 remappable keys). No native dialogs (`askConfirm` / `askText`).

## 0. The refining session — answers to 14 §4

1. **Deltas against the shipped model** — §9. In one line: loom's Story Bundle becomes a `story/` directory of records beside the
   project's `groups/`, `clips/`, `stages/` and `timelines/`; a profile version *is* a group; a shot version *points at* a stage
   camera and a clip; the episode *is* a P17 timeline with shot stamps; `asset@version` pins are the mention stamps that exist.
2. **Which P1 flows are verbs** — Cast → Expand → Curate are **Catalogue and Generate verbs** reached from the Story Cast tab:
   *Cast* = "Make a character / place / prop from this image…" on any image tile (a profile with version 1, its ref set a group
   with the hero as cover); *Expand* = one recipe `Expand` that the server plans as one queued job per coverage cell with the hero as
   the reference (the cost shown first, D79's pattern); *Curate* = the Catalogue's keep / reject and the version's group page, with a
   candidates strip and a live coverage grid in the Cast tab. No second gallery is built.
3. **P3 tiers against the measurements** — the *sketch* tier is LTX-2.3 Draft (141 s per 121 frames at 24 fps, D9) and, from a
   stage, the pass-guided clip (147 s, D76); the *quality* tier is LTX 20 steps (210 s) or Wan 2.2 Quality (900 s at 16 fps,
   conformed by RIFE at export — D27); the *hero* tier is H3 behind its licence confirmation (D17). loom's **drive tier (Wan
   Animate, a driving clip + a character image) is not built**: ST4's guided clip already makes the figures follow the blocking,
   and E11 found the Wan Fun Control fallback unnecessary (D76). Within-shot continuity is Animate's extract-frame → first/last-frame
   chain (11 §7); extension and keyframe chains stay 03 §5 item 4. Voice and lip-sync stay out (03 §5 item 4, loom R95).
4. **Muse against the queue-only rule** — **deferred to a wave of its own after the Story alpha** (§13): loom2 has no language model
   and ComfyUI is for inference only (D2); bringing one in (a llama.cpp sidecar vs a ComfyUI LLM node, Qwen3-VL-4B on ROCm) is a
   spike (E15) and a decision, and every call would be a queue job that runs only when the engine is idle (R141 / R142). Story v1
   ships **without any AI assistance**; its records are typed, stable-id'd and rebuildable, so a project digest (loom R145) is a
   later build, not a migration.
5. The plan with milestones is **this document** (§10); 15 was taken by the click-through, so the number is 17.

## 1. Purpose
Turn the studio's pieces into an **episode**: a bible of the world and its styles, a cast of characters, places and props that can be
`@`mentioned and expanded into consistent reference sets, shots that own one finalized clip each, a branching flow that binds the
shots, and a hand-built episode cut exported to Resolve. The Story suite is the *place* a production is organised; the other suites
do the making. Everything is a file in the project under `story/`, reopened exactly.

## 2. Layout

```
Rail: [World] [Cast] [Shots] [Flow] [Episode]                                             Top bar: … Stage · Story (Ctrl+7) · Models
┌────────────────────────┬──────────────────────────────────────────────────┬──────────────────┐
│ Panel · Cast           │ Strip: v1 ▾ · New version · ☐ locked   Cast ✓ › Expand › Curate › Train ○ › Lock │ Inspector        │
│ ◉ characters ○ places  ├──────────────────────────────────────────────────┤ Profile · Version│
│ ○ props     🔍         │  ┌─ hero ─┐  Mara — character — v1 (open)        │ ───────────────  │
│ ▢ Mara        v1 ●     │  │        │  prompt stub: "Mara, a wiry courier…" │ name  Mara       │
│ ▢ Tomas       v2 ●     │  └────────┘  ref set · 27 kept   candidates · 13  │ class character  │
│ ▢ The tavern  v1 ○     │  coverage (shot × angle)   front ¾L ¾R prof back  │ prompt stub  …   │
│ ▢ Lantern     v1 ●     │     close-up                 3   2   2   1   –    │ trigger   —      │
│                        │     portrait                 2   2   1   1   –    │ lora      — (LT) │
│                        │     waist-up                 2   1   2   2   1    │ ref set ▸ group  │
│                        │     full-body                1   1   –   1   1    │ hero ▸ asset     │
│                        │  candidates ▸ [▣][▣][▣][▣][▣]  keep ✓  reject ✕   │ ───────────────  │
│                        │                                                  │ Open in Catalogue│
│ [ New profile… ]       ├──────────────────────────────────────────────────┤ Expand…  Lock    │
│ [ Expand ▶ ]           │ Dock  ▸ Running: expand klein-9b 7/40 ███░ 00:41  · Queued 33       │ New version      │
└────────────────────────┴──────────────────────────────────────────────────┴──────────────────┘
```

The Rail tabs switch the Panel *and* the Stage: each tab is one of loom's workspaces (`kb-loom-ui.md` §4, D1–D10) folded into the
loom2 frame — the Panel lists, the Stage edits, the Inspector holds the selected record's fields, the Dock keeps the jobs (and the
lane transport on the Episode tab, D8). The primary action at the Panel's foot follows the tab: **Expand** (Cast), **New shot**
(Shots), **Play** (Flow), **Export** (Episode); World has none. The suite loads lazily (D69) and keeps no GPU stage alive, so it is
never released.

## 3. Tabs

### 3a. World (loom L1)
**Panel:** the sections — Logline · Synopsis · Styles · Spine · Variables — as a list; clicking scrolls the Stage to the section.
**Stage:** a document editor over `story/world.json`: two text areas (logline, synopsis); **Styles** — rows of *name · fragment ·
reference group (optional)* with ✚ / ✕ and a *default* radio; **Spine** — an ordered list of beats (title, one line), drag to
reorder, ✚ / ✕, and *Make a Flow node from this beat* on each row (manual, never auto-synced — loom R55); **Variables** — rows of
*name · type (bool | enum) · default*, the Flow's conditions read them (loom R135). Every edit saves after 300 ms with the
document's `revision`; a 409 reloads and says the last change was lost (as documents and stages do).
**Inspector:** the project format (read-only: it is the finalize gate, §3c), counts (profiles, shots, nodes, episodes), the default
style. **Styles reach Generate** as a *Style* picker on the Prompt tab: one style per generation, its fragment **appended** after the
prompt (loom R104 as amended), *none* as the override, stamped `style_id` on the recipe and the asset's manifest (loom lesson 7,
02 §7); Stage shots and Expand take the same picker.

### 3b. Cast (loom L2 · the bootstrap loop)
**Panel:** profiles filtered by class chips (characters · places · props) and a search box; each row shows the current version and a
dot (● open · ○ locked); **New profile…** (`askText` for the name, class chips) makes an empty profile whose version 1 has an empty
ref set, waiting for a hero; the usual way in is the **Catalogue verb** *Make a character / place / prop from this image…* on an
image tile (also in the Inspector's quick card), which creates the profile, version 1 and its ref-set group with the image as hero and
cover, and opens the Cast tab on it.
**Strip:** the version selector (v1, v2, …), **New version** (a full copy of the current one — loom R53: the ref-set group is
duplicated through `POST /groups/{gid}/duplicate`, the fields copied, `derived_from` stamped; assets are immutable, so the copy
shares their files), the lock state, and the **bootstrap strip** *Cast ✓ › Expand › Curate › Train ○ › Lock*: each step a button
that is ✓ when its evidence exists (a hero; candidates; ≥ 1 kept ref per shot-size row; a LoRA — greyed with "LoRA training comes
with the next wave (03 §5)"; locked).
**Stage (the version page):** the hero, the name, class and state; the **prompt stub** (loom R112: the clause a mention of this
profile carries into a prompt — editable while open); counts; the **coverage grid** (shot size × angle, the kept refs' count per
cell from `params.coverage_cell`, thin cells tinted — loom `kb-loom-p1.md` §7.1, advisory only, 02 §7); the **candidates strip**
(the version's candidates group, newest first; *keep* ✓ moves the asset to the ref set, *reject* ✕ marks it rejected, both also on
the tile's context menu; a click opens the Loupe); the ref set itself is a group page in the Catalogue (*Open in Catalogue*
navigates with origin, D66) where the usual drag, order and cover tools apply.
**Expand ▶ (primary action):** `askConfirm` with the preset (loom R111: Comprehensive ≈ 100 · Full-coverage ≈ 40 · Portrait-heavy
≈ 30 · Full-body ≈ 45 · NPC-lite ≈ 20), the model (Klein 9B under `full`, 4B under `open`, from `/capabilities.story`), the tier,
the seeds per cell and the estimated minutes (cells × the model's warm seconds); then **one queued job per cell** in one batch
(`batch_id`, one `warm_group`), each a T2I with the hero as reference 1 ("Image 1 shows <name>"), the cell's sentence appended
("three-quarter left view, waist-up, neutral expression"), the version's style, `params.coverage_cell`, suite `story`, origin
`{suite: story, surface: expand, ref: profile_id, payload: {version, cell}}`; results are placed into the version's candidates
group (as stage passes land on their stage's album page). Angle cells use prompting with the reference (E12 measured Klein at 6–7/10 on
rotations, 9–10/10 on framing); a thin cell can be re-rolled with P14's *New angle* verb from the tile, which lands in the same group.
**Lock** (`askConfirm`): the version becomes `final` — its group is `locked` (every group mutation route returns 423), the stub and
fields are read-only, mentions keep resolving to it; a retake is a new version (loom R58 / R119). **Inspector:** the profile
(name, class, versions, delete), the version (state, stub, trigger and LoRA slots — filled by the LoRA wave, D25 — hero, ref set,
candidates, `derived_from`), *Open in Catalogue*, *Expand…*, *Lock*, *New version*.
**Mentions:** the `@` picker in Generate (D73) lists **profiles first** (name, class, hero thumbnail, current version), then album
groups; a profile mention resolves to its **current version's group** (or a pinned `@mara@v1`), the stamp gains `profile_id` and
`version` beside `{group_id, revision, asset_ids}` — the `asset@version` pin loom wanted (R98) is this stamp, and provenance stays
as it is. The prompt stub is appended once per mention as its note's lead sentence per model family (D73's serialisation).

### 3c. Shots (loom L3 · Shots & Takes)
**Panel:** the shots grouped by their owner node (*Unbound* first), each row with its current version's thumbnail, name and state;
**New shot…** (`askText`) makes an empty shot with version 1. The usual ways in: *New shot from this camera* on the Stage suite's
Cameras and Shot tabs (the version points at `{stage_id, camera_id}`; the camera's ST3 result and ST4 clip become its frame and
clip as they arrive — this closes ST4's "Story L3 link", 08 §8); *Make a shot from this clip* on Animate's Clips tab and clip tiles;
*Use as the shot's clip* / *Use as the shot's frame* on results (origin-aware: a job whose origin is a shot offers them first).
**Stage (the shot board):** the selected shot's versions as cards (frame thumbnail, clip badge with frames and size, state, stale
mark); the current version's **player** (the clip proxy in a `<video>` with the frame image when no clip exists) and its **takes**
(every image and clip tried for this version, newest first, from the version's `takes[]`; *use* ✓ makes one the frame or the clip);
*Open in Stage* / *Open in Animate* (origin, D66) when the version has a source. **Finalize** (`askConfirm`): requires a clip whose
size equals the project format's `w × h` (fps is conformed at export by E9 — D27); the version becomes `final`, its clip is the one
the Flow and the Episode bind; a draft-sized clip shows *why* on the disabled button ("Draft 1024×576 — the format is 1920×1080;
render Full in Animate"). A version whose stage moved after its clip (the stage's `revision` is newer than the stamped one) is
marked **stale** — advisory, still usable (loom R62 / R153). **New version** copies the current one (the source pointers, no files).
**Inspector:** the shot (name, owner node — read-only, set by the Flow; *Release* unbinds; delete), the version (source, frame, clip,
takes, state, `derived_from`, `created_at`), the verbs. No compositor is built: layers live in Edit, blocking in Stage (§9).

### 3d. Flow (loom L4 · the narrative graph)
**Panel:** the outline — nodes by type with search, and the Variables list (from World) with their play-mode values; clicking a row
selects and centres the node. **Strip:** the node palette (✚ Dialogue · Choice · Condition · Action · Shot · Hub · Jump · Comment —
a click places the node at the view's centre, a drag places it where dropped), *Validate*, **Play ▶**, zoom and *Fit*.
**Stage:** a node-graph canvas on **`@xyflow/react`** (React Flow 12, MIT — the library loom chose; a new dependency to approve):
nodes with typed out-ports (a Choice has one per option, a Condition *then* / *else*), edges drawn by drag; pan, zoom, box select,
a minimap; right-click the canvas → add a node here; right-click a node → *Bind shot…*, *New shot*, *Open shot*, *Duplicate*,
*Delete*. Node cards show their title, the speaker chip (a profile mention), the first line and the bound shot's thumbnail with its
state. **One flat graph** with Jump nodes, exactly one Start (loom R74). Layout and edges live in `story/flow/graph.json`, every
node in `story/flow/nodes/<id>.json` (loom R139); the index is rebuilt from the node files when it is missing or disagrees.
**Node ↔ shot (loom R134 / R146):** a Dialogue or Shot node *binds* an **unbound** shot (the picker lists only those) or *spawns* a
new one owned by it; binding transfers **sole ownership** (`owner_node` on the shot) — a look reused elsewhere is a duplicated shot;
deleting a node releases its shot (the shot stays, unbound). The node pins the shot version it shows (`shot_version`, default the
current one). **Inspector:** the node's fields by type — title; Dialogue: lines `[{speaker: profile_id, text}]` with an ✚ row and
a speaker picker; Choice: options `[{label, to, require?: {var, value}, set?: [{var, value}]}]`; Condition: `{var, op, value}` with
*then* / *else*; Action: `set[]`; Jump: the target node; Comment: text; colour; the bound shot card with *Bind* / *Release* /
*Open*. **Validate** lists: no Start / several, a Choice without options, a dangling Jump, an unreachable node, a visual node without
a shot or with a non-final version — advisory rows that select the node on click. **Play ▶** walks the graph from Start in the
Stage: the bound clip plays (its proxy), the lines show under it, choices are buttons, conditions read the variables, actions set
them, *Restart* resets them; **no model is ever invoked** (loom R143) — authored content or nothing.

### 3e. Episode (loom L5 · render list and export)
The **Sequence tab moves here from Animate** (D83 said "until Story's Episode tab exists"): the same lane (`suites/animate/lane.ts`,
the Sequence stage, undo stack, Mediabunny scrubbing, trims, dissolves, draft render, EDL / FCPXML) under the Story rail;
`?suite=animate&tab=sequence` deep links redirect for one release. Three additions:
- **The Shots bin** beside the Clips bin: every shot's current version's clip, grouped by its owner node's title, final ones first;
  dropping or ✚ adds it with **shot stamps** on the lane clip (`shot_id`, `shot_version`, `node_id` — optional fields, so the
  Animate-era timelines load unchanged). The episode is **hand-built** (loom R148): nothing is derived from the graph.
- **Validation before export** (loom R153, kept advisory per 02 §7): the Inspector's checklist — a lane clip that is not a final
  shot version (draft, or a plain clip) and a stale one; *Export* opens `askConfirm` with the count ("2 of 7 clips are not finalized
  shots") and goes on when the author says so.
- **Export adds** `.srt` subtitles from the Dialogue lines of the lane's nodes, timed by the lane (loom R152), and **chapter
  markers** — one per lane clip named by its node's title — in the FCPXML (Resolve reads them) and in a sidecar `markers.txt`
  (loom R158); EDL as before. The author's Resolve import check (D83) is repeated on an export with markers and subtitles.

## 4. Workflows
1. **Bible first.** World: logline, two styles, the spine's beats → *Make a Flow node from this beat* for the first five.
2. **A character, end to end (loom's P1 done-line).** Generate the hero (Klein 9B, the default style) → tile → *Make a character from
   this image…* → Cast opens on Mara v1 → *Expand ▶* Full-coverage (40 jobs, ≈ 4 min warm) → keep / reject in the candidates strip
   until the grid has every shot-size row ≥ 1 → *Lock*. From now on `@mara` in any prompt carries her stub and references.
3. **A shot from a stage.** Stage: block the tavern with `@mara` planes, frame camera 1 → *New shot from this camera* → ST3's
   Generate ▶ makes the frame, ST4's Animate ▶ the guided clip → Shots board shows both on v1 → *Finalize* once the clip is at the
   format (render Full).
4. **A shot from Animate.** A Catalogue image → Animate → a clip → *Make a shot from this clip* → Finalize.
5. **Story-first.** Flow: Dialogue nodes with speakers and lines, a Choice with two options, a Condition on a variable, Jumps; *New
   shot* on each visual node → the Stage suite opens on a new stage with origin; later the clips arrive on the shots; *Validate* is
   clean; *Play ▶* walks the branch.
6. **The cut.** Episode: the Shots bin → the lane in the chosen order, a dissolve at one join, *Render draft* to check, *Export* →
   EDL, FCPXML with markers, `.srt` → Resolve.

## 5. States
- Profile version: `open` (editable, trainable later) · `final` (locked group, read-only fields; mentions still resolve) — loom
  R119's *unsaved* state does not exist: every edit saves (300 ms, `revision`, 409 reload).
- Shot version: `open` · `final` (one clip, at the format) · **stale** flag when its stage moved after the clip.
- Flow: the graph is always valid to save; *Validate* is a list, never a block; Play runs on any graph with one Start.
- Episode export: advisory checklist, `askConfirm` to continue.
- The suite without a project: the Panel says *Open a project*; every tab's empty state carries its first verb (D-P15).

## 6. Keyboard (accelerators; every action has a button or a menu entry — D32)
`Ctrl+7` Story · `Ctrl+Enter` the tab's primary action · `Delete` the selected node / row · `Space` Play / pause (Flow play, Episode)
· `F` Fit the graph · `Ctrl+Z` / `Ctrl+Shift+Z` undo / redo (Flow and Episode) · `Ctrl+B` Bind shot… · the Episode lane's keys as
11 §5b. All remappable (D72).

## 7. Data and API

```
story/
├── world.json                # L1: logline, synopsis, styles[{id, name, fragment, group_id?}], default_style, spine[{id, title, line}], variables[{name, type, values?, default}]; revision
├── profiles/<id>.json        # L2: name, cls (character | place | prop), current, versions[{id, state, group_id, hero_asset_id?, candidates_group_id, stub, trigger?, lora?, derived_from?, created_at}]; revision
├── shots/<id>.json           # L3: name, owner_node?, current, versions[{id, state, source?: {stage_id, camera_id, stage_revision} | {clip_id}, frame_asset_id?, clip_id?, takes[{kind, id, at}], derived_from?, created_at}]; revision
└── flow/
    ├── graph.json            # L4 index (rebuildable): nodes[{id, x, y}], edges[{from, port, to}], start
    └── nodes/<id>.json       # one node per file: type, title, lines[] | options[] | cond | set[] | target | text, speaker?, shot_id?, shot_version?, colour; revision
timelines/<id>.json           # L5 (P17): clips[] gain shot_id?, shot_version?, node_id?
```

Routes (`routes/story.py`, all behind the token, D67): `GET/PUT /story/world` · `GET/POST /story/profiles`, `GET/PATCH/DELETE
/story/profiles/{id}`, `POST /story/profiles/{id}/versions` (copy), `POST /story/profiles/{id}/versions/{v}/lock` ·
`GET/POST /story/shots`, `GET/PATCH/DELETE /story/shots/{id}`, `POST /story/shots/{id}/versions`, `POST /story/shots/{id}/versions/{v}/finalize`,
`POST /story/shots/{id}/take` (record a take) · `GET /story/flow` (index + nodes), `POST/PATCH/DELETE /story/flow/nodes[/{id}]`,
`PUT /story/flow/graph` (layout and edges), `POST /story/flow/validate` · `POST /timelines/{id}/export` gains `srt` and markers.
Recipes: `Expand {profile_id, version, preset, cells?, seeds_per_cell, model_id, tier, style_id?}` planned server-side into T2I jobs
(one per cell, `batch_id`, `warm_group`); `T2I.style_id` and `Mention.profile_id / version` (D73's resolver, profiles first).
Records: `GroupRecord.locked`; `JobOrigin.suite` and `AssetRecord.suite` gain `story`; `/capabilities.story` (the Expand model per
variant, its warm seconds, the presets' cell lists, the coverage vocabulary). Every record has `schema_version` and is written through
`fsio` (temp → fsync → replace); `revision` with 409 like documents. Events: `story.changed {kind, id}` on the socket so open tabs
refresh (a stage shot landing on a shot version, a candidate landing in a group). The API contract (D38) is re-exported and the route
snapshot grows; `scripts/settings_audit.py` learns `story`.

## 8. Frontend
`suites/story/` loaded lazily (D69, no keep-alive): `storyStore.ts` (world, profiles, shots, flow, selection; saves debounced with
revisions), `StoryParts.tsx` (the five Panels / Stages / Inspectors), `storyCommands.ts` (`story.*` commands with placements),
`flow/` (the React Flow canvas, node components, `play.ts` — the pure walker, unit-tested), `coverage.ts` (the grid from
`params.coverage_cell`, pure), `dropRules.ts` (images → hero / candidates, clips → shot version, shots → the lane). The Episode tab
imports the Animate lane modules as they are (moved, not copied). Rail tabs in `railTabs.tsx`; `Ctrl+7` in `TopBar.tsx`; the
Catalogue, Stage and Animate verbs register in their own command files and open Story with origin (`store/origin.ts` case `story`).
New dependency: `@xyflow/react` 12 (MIT) — checked by `scripts/csp_check.py` (DOM and SVG only, no eval).

## 9. Deltas against loom (14 §4 item 1)

| loom (`kb-storyboard01` / P1–P5) | loom2 as shipped | Story does |
| --- | --- | --- |
| Story Bundle with a directory per layer, refs copied per version | `groups/`, `clips/`, `stages/`, `timelines/`, `documents/`; assets immutable by id | `story/` records; a version's ref set **is a group**; copy-on-create = `duplicate` (no file copies) |
| Unsaved · Saved · Finalized (R69 / R119) | every edit saves (`revision`, 409) | `open` · `final`; `final` locks the group (`locked`, 423) |
| `asset@version` pins (R98) | mention stamps `{group_id, revision, asset_ids}` (D73) | + `profile_id`, `version` — the stamp is the pin |
| L3 compositor (Konva layers) + segments + take timeline | Edit (layers, cut-outs D33), Stage (blocking → passes → image → guided clip), Animate (i2v, FLF, extract) | a shot version points at a stage camera and / or a clip; takes recorded; no new compositor |
| node clip = PNG-sequence master + proxy (R161) | `ClipRecord.master_dir` + `proxy_path` | as is |
| sketch LTX → drive Wan Animate (P3 §6) | LTX-2.3 draft 141 s / guided 147 s (D9, D76); Wan 2.2 draft 236 s; E9 RIFE at export | the Animate presets are the tiers; the drive tier is not built |
| L5 render list + single-lane timeline + EDL / FCPXML (R148 / R157 / R151) | P17: lane, dissolves, exporters, draft render (D83) | moves to Story · Episode; shot stamps, `.srt`, markers, the checklist |
| Flow: one file per node + `graph.json` (R139), React Flow | documents / stages / timelines one file per record | the same shape under `story/flow/`; `@xyflow/react` |
| Muse: `llama-server` sidecar, Qwen3-VL-4B + Embedding-8B (R144) | no language model; ComfyUI inference only (D2) | deferred (§13); spike E15 first |
| staged jobs in `jobs/staged.json` (R118 / R123) | the queue's `staged` status (06 §5) | Expand queues after `askConfirm` with the cost (D79); training stays staged (the LoRA wave) |
| project format presets (R45 / R56) | `ProjectFormat` fixed at creation (16:9 · 1920×1080 · 24 fps) | as is; the finalize gate reads it |
| LoRA + trigger per version (P2) | D25 slots: `loras[]` on recipes, roster `role: lora` | the version's `trigger` and `lora` fields reserved, filled by the LoRA wave |
| style: fixed fragment + override checkbox (R104) | Generate presets | a Style picker: one, appended, `style_id` stamped; *none* overrides |
| Muse as an Inspector tab (`kb-loom-ui` D9) | — | the Inspector keeps the slot free; nothing built |

## 10. Milestones (slices; each ends with tests, a smoke scenario, a rig run where the GPU is involved, and a journal entry)

| Slice | Content | Effort |
| --- | --- | --- |
| **SY0 Shell + World** | suite registration (lazy, rail, `Ctrl+7`, `JobOrigin` / `AssetRecord` `story`), `story/world.json` + routes, the World editor (sections, styles, spine, variables), **the Style picker in Generate** (appended, `style_id` stamped, in the manifest), origin case `story` — **built 2026-10-13** (journal of that day): `orchestrator/loom2/story.py` (`World`, `StoryStore`, `resolve_style`) + `routes/story.py`, `T2I.style_id` / `style_text` appended in `serialize_prompt` per family, `frontend/src/suites/story/` (store, parts, commands), `suites/generate/StylePicker.tsx`; the smoke scenario adds a style in World and finds its fragment in the job's manifest | 3 d |
| **SY1 Cast** | profiles + versions (copy, lock → `GroupRecord.locked` and 423), the Catalogue verb, mentions resolving profiles (picker, stamps), the Cast tab (version strip, bootstrap strip, grid, candidates strip, Inspector), `Expand` (planner → one job per cell, placement into the candidates group, `/capabilities.story`); **rig:** one character Full-coverage (40) → curated ≥ 25 with every shot-size row ≥ 1, `@mara` in a Generate prompt carries her stub and references | 6 d |
| **SY2 Shots** | shot records, versions, takes, finalize gate (format), stale mark, the Shots board + player + Inspector, the verbs in Stage (camera → shot; ST3 / ST4 results fill the version), Animate (clip → shot, use as clip / frame) and the Catalogue; `story.changed` events; **rig:** a stage camera → frame + guided clip on one version, finalized at 1920×1080 | 5 d |
| **SY3 Flow** | `@xyflow/react`, node files + index, the eight node types, ports and edges, bind / spawn / release (R146), variables and conditions, `play.ts` + the play Stage (no AI), Validate; unit tests on the walker and the index rebuild | 7 d |
| **SY4 Episode** | the Sequence tab moved (redirect), shot stamps, the Shots bin, the checklist + `askConfirm`, `.srt`, markers in FCPXML + sidecar; parity tests; **author:** Resolve import with markers and subtitles | 4 d |
| **SY5 Alpha** | `scripts/sy_acceptance.py` (§12) through the app on the rig, the smoke scenarios on the fake engine for both variants, docs (this document's built notes, 08 §1, 12, 14), the D85 acceptance mark | 3 d |

≈ 28 d. SY1 and SY3 are independent after SY0; SY2 needs SY1 only for the speaker chips (none in SY2), so SY2 can run beside SY1.

## 11. Tests
- Offline: `StoryStore` durability (atomic writes, 409, index rebuild from node files, a missing `graph.json`); the Expand planner
  (cells per preset, one job per cell, the reference and the appended sentence, placement); `resolve_mentions` with a profile
  (current and pinned versions, a locked one, the stamp fields); the finalize gate (size, fps ignored); `locked` groups on every
  mutation route; the `.srt` timing and markers against the lane; the route snapshot; the contract export.
- Unit (Vitest): `play.ts` (Start, Choice, Condition, Action, Jump, a loop, a dangling target); `coverage.ts`; the flow index diff;
  the lane's stamps survive load / save.
- Smoke (Playwright, fake engine): the six workflows of §4 in one scenario each; variant-aware where a model differs.

## 12. Acceptance checklist (`scripts/sy_acceptance.py`, rig, through the app with the `__loom2Story` dev hook)
1. World: two styles; a Generate job with style B stamps `style_id` and the appended fragment is in the manifest's prompt.
2. Cast: a hero → *Make a character…* → Expand Full-coverage → 40 jobs in one batch, every result in the candidates group with its
   cell; curate to ≥ 25 kept with every shot-size row ≥ 1 (the grid agrees with the group); Lock → the group refuses a move (423);
   `@mara` resolves to the locked version's group (stamp has `profile_id`, `version`).
3. Shots: a stage with `@mara`'s plane → camera → *New shot from this camera* → ST3 frame + ST4 guided clip fill v1; Finalize refused
   at draft size with the reason, accepted after a Full render; the stage moved → stale.
4. Flow: five nodes with a Choice and a Condition; bind the shot; a second bind of the same shot is refused; Validate clean; Play
   walks both branches without a job being queued.
5. Episode: three clips from the Shots bin, one dissolve, the checklist names the non-final clip, Export → EDL + FCPXML (markers) +
   `.srt`; the draft render job lands as a clip.
6. Kill the app mid-Expand → relaunch resumes paused with the remaining cells queued; every record reopens at its revision.

## 13. Later waves (not in this plan; order from 03 §5)
- **LT · LoRA training** (03 §5 item 2, loom P2): ai-toolkit on ROCm as a staged job from a locked version's ref set, template
  captions from `coverage_cell`, the readiness meter (advisory), promote into the version's `lora` + `trigger`; a spike first.
- **SV · Voice and lip-sync** (03 §5 item 4, loom P3 §9): out of v1 (loom R95).
- **SM · Muse** (03 §5 item 5, loom P4 §7–§13): spike **E15** (a local VLM as a queue job on this rig — a llama.cpp sidecar the
  orchestrator starts and stops around jobs vs a ComfyUI node; Qwen3-VL-4B; licence vs D17 / D26), then propose-and-approve
  assistants (prompt drafting, captions, the project digest) as queued jobs that run only when the engine is idle; the Inspector's
  Muse tab (`kb-loom-ui` D9). Never before the Story alpha.
- Continuity: extension and keyframe chains (03 §5 item 4); 3D props beyond P18; engine / DCC export (loom P6).

## 14. Open questions — decided by the author 2026-10-13 (D85): every default below as proposed
1. **One suite, five tabs** (World · Cast · Shots · Flow · Episode) under a *Story* top-bar tab (`Ctrl+7`), the Sequence tab **moved**
   from Animate into Episode with a redirect for one release — rather than scattering Story over the existing suites.
2. **Cast → Expand → Curate as Catalogue / Generate verbs** reached from the Cast tab (§0 item 2); the ref set is a group; no second
   gallery; Expand asks with the cost and queues one job per cell.
3. **`@xyflow/react` 12 (MIT)** for the Flow canvas — a new frontend dependency.
4. **Two states** (`open` · `final`) instead of loom's three; a final version **locks its group** (`GroupRecord.locked`, 423).
5. **The finalize gate is the format's size only**; fps is conformed at export (D27); the Episode's checklist is **advisory**
   (`askConfirm`), not a block (02 §7 over loom R153).
6. **No drive tier, no voice, no Muse in v1** (§0 items 3–4, §13); the version's `trigger` / `lora` slots wait for the LoRA wave.
7. **Styles as a Generate picker** (one per generation, appended, `style_id` stamped, *none* overrides).
