# 05 · Engineering practices — build, release, CI, conventions, performance, licence

Source: `F:\source\repos\artcraft` at `3e5793b693`. How the project is built, shipped and kept coherent by a small team working with AI
agents (the latest commit is co-authored by an AI model).

## 1. Repository facts

- **History:** `main` has 19 commits because the repository was restarted on 2026-09-11 ("ArtCraft Desktop (fresh start)": 5,677
  files, ~520k lines). The old monorepo (web API, job services, SRE tooling) moved to `storytold/artcraft-services`, which is *not*
  part of this checkout — the hosted backend described in [02](02-backend-architecture.md) is only visible through its client crates.
  The clone also carries 1,288 remote branches (20,198 commits reachable, `.git` 1.4 GB).
- **Size** (git-tracked files only):

| Kind | Files | Lines |
| --- | --- | --- |
| Rust | 3,212 | 257,733 |
| TypeScript | 1,207 | 114,281 |
| TSX | 452 | 92,631 |
| JSON | 308 | 39,341 |
| Markdown | 101 | 4,560 |
| Other (JS, TOML, CSS, Python, shell, SQL) | ~130 | ~10,000 |

| Area | Lines |
| --- | --- |
| `crates/api_clients` | 194,578 (router 76.9k, fal 54.3k, kinovi 18.4k) |
| `crates/desktop/artcraft` | 30,197 |
| `crates/schema` / `lib` / `vendor` | 25.9k / 5.6k / 1.3k |
| `frontend/libs` | 180,611 (component libs 162.6k; video-editor alone ~71k) |
| `frontend/apps/artcraft` | 25,927 |

- **Tests:** ~5,950 Rust `#[test]`s (~720 of them `#[ignore]` live tests), ~77–134 TS spec files (Vitest), Playwright scripts for
  session and performance checks.
- **Key dependencies:** tauri 2.11, sqlx 0.7.4 (pinned, TODO to upgrade), tokio 1.50, reqwest 0.12 + **wreq** 6 rc (BoringSSL browser
  fingerprints), image 0.25, utoipa 5; Nx 21, React 18.3, Vite 6, TypeScript 5.8, Zustand 5, Three 0.171, Spark, Konva, mediabunny,
  opencut-wasm, Tailwind 3.4, Vitest 3, Playwright 1.63.

## 2. Dev loop

- Prerequisites: Rust stable, Node 20+, npm (a preflight script refuses pnpm leftovers), `tauri-cli` 2, and native tools for wreq's
  BoringSSL (cmake, perl, nasm, llvm on Windows).
- **macOS/Linux:** `script/artcraft/unix_dev.sh` → preflight → `frontend/scripts/unix-dev.mjs`: starts Vite on the first free
  loopback port from 5193, *then* spawns `cargo tauri dev` with an in-memory config override (dev URL, CSP `connect-src` amended),
  tears down the whole tree on Ctrl-C. **The launcher has its own tests** (`node --test` with real Vite listeners and a fake cargo
  process tree).
- **Windows:** two terminals — `windows_frontend_dev.ps1` (Vite on 5173) and `windows_rust_dev.ps1` (`cargo tauri dev` with
  `SQLX_OFFLINE=true`).
- Browser-only dev: a throwaway Chrome profile with web security off; Playwright fixtures mock IPC.

## 3. Build and release

- Frontend: `nx build artcraft` → `frontend/apps/artcraft/dist`; libs resolve to source via path aliases (no lib build step).
- Tauri `bundle.targets: "all"` → NSIS `setup.exe` + MSI on Windows; universal binary on macOS.
- **Version** lives in three files (`src/version.rs`, `tauri.conf.json`, `tauri-mac.conf.json`); `bump_artcraft_desktop_version.py`
  reads all three, takes the highest, bumps the minor. Each release is a small PR touching exactly those files ("ArtCraft 0.41").
- **Release flow:** merge the bump → `push_artcraft_release_branch.sh` recreates `artcraft-release` from `main` and pushes → two
  publish workflows build and create **draft** GitHub releases (`artcraft-v<ver>`) → a human publishes.
- **About pane** shows version, build timestamp, git commit and time (`crates/lib/build_metadata`), OS and data directories.
- macOS is signed and notarised in CI; **Windows is unsigned**; **no auto-updater** (users download releases).
- Pitfall found: the release profile (`lto`, `codegen-units=1`, `panic=abort`, `strip`) sits in the desktop crate's `Cargo.toml`,
  where Cargo ignores it in a workspace member — none of it applies.

## 4. CI

| Workflow | Trigger | Does |
| --- | --- | --- |
| `artcraft-windows-publish.yml` | push to `release` / `artcraft-release` / `artcraft-windows` | `npm ci`, pre-build the frontend (8 GB heap), blank `beforeBuildCommand`, `tauri-action` with `+crt-static` and `SQLX_OFFLINE`, draft release |
| `artcraft-macos-publish.yml` | same, macOS | copy the mac config over the main one, import the certificate, sign, notarise, draft release |

**Nothing runs on pull requests** — no test, lint, typecheck or `cargo check` job. Dependabot covers cargo weekly. The local lint and
test scripts (`script/rust/execute_lints.sh` with `cargo cranky`, `execute_tests.sh`) still name crates from the old monorepo.

## 5. Performance work as a documented experiment

`docs/performance.md` with raw data in `docs/performance/2026-09-26-{before,after}.json`:

- **Method:** Playwright headless Chrome, mocked Tauri IPC, HTTP blocked, 1440×1000, 7 samples, medians, fixed fixture (four 1024² PNGs
  + 80 strokes of 200 points); `npm run perf:desktop -- --baseline-ref <sha>` builds a baseline from only the changed files;
  `compare.mjs` diffs runs; `dist/performance-bundle.json` ranks retained modules. The doc states what it does *not* measure (native
  WebView) and gives a native validation protocol.
- **Result:** startup to first frame 566 → 351 ms (−38 %), startup JS 9.05 → 6.47 MB, long tasks 336 → 184 ms.
- **Changes:** 15 pages to `React.lazy` (the drawing page stayed eager because deferring it measured worse); stop serialising the
  drawing store to JSON on every tab switch (the store already survived unmount); remove an unused startup GPU probe that cost a WebGL
  context.
- **Open items** listed honestly: 6.5 MB still in the shell graph (Spark, Three, an FBX→GLB worker, PostHog, mediabunny), 5 s task
  polling, ~86 ms to return to a populated canvas.

The same dated, evidence-first style is used for incidents: `docs/desktop-session-regression.md` (what broke, why, the fix, the
follow-up crate, a console probe, Rust tests) and `docs/website-login.md` (the native login design).

## 6. Conventions for humans and agents

- **`AGENTS.md` hierarchy**: root, `crates/`, and per-subsystem files (`artcraft_router/.../generate_video`, `storyteller/commands`,
  the `enums` and `tokens` crates, `pagescene`). Sibling `CLAUDE.md` files are git symlinks to `AGENTS.md` — on Windows with
  `core.symlinks=false` they check out as 9-byte text files containing "AGENTS.md", i.e. useless. `.claude/rules/` holds API, style and
  testing rules (partly about the server, now stale here).
- **Rules worth noting:**
  - *Newspaper file layout*: constants → primary type → supporting types → Request/Response/Error → impls (constructors, public,
    private; callers above callees); tests first, helpers last; sub-modules only for 2+ tests.
  - *One Tauri command per file; one HTTP endpoint binding per file*; transport separate from endpoints.
  - *Stored enums*: never change an existing string value; add variants; clients carry `Unknown(String)`. Step-by-step "add an
    enum / add a token" recipes.
  - *Add a model*: the router's five-step checklist (module → register → enum variant → `build2` arm → tests).
  - *Frontend 3D*: a 513-line living spec with ⚠ footguns ("never unmount the canvas hosts"), the one-way data-flow rule, the keybind
    registry rule (no raw keydown listeners), one undo step per edit, and a DONE / NOT STARTED status table (which has drifted from
    the code).
  - Two-space indentation (rustfmt), `log` macros not `println!`, `maybe_` prefix for options, import aliasing with a source suffix,
    space-padded Markdown tables, a `Cranky.toml` clippy policy (`unsafe_code`, `await_holding_lock`, `unused_*` denied).
  - Credentials never cross IPC; the frontend never calls the auth API directly.

## 7. Licence (read before borrowing anything)

`LICENSE.md` is an unfinished "fair source" text ("ArtCraft License (WIP)"):

- **Permits:** free use; copying, modifying and compiling the code **for private personal purposes**; generated media belongs to the
  user.
- **Forbids:** selling ArtCraft; **using the code to build a competing product or business** ("e.g. selling AI image and video
  tools"); forks that strip community/donation links; use of the name, logo or mascots.
- **Promises:** stays public; switches to an OSI licence if the business ends.

For loom2 this means: **learn from the design, re-implement from concepts, do not transplant files** — loom2 is a personal tool today
but D26 plans distributable `full`/`open` builds. Third-party pieces inside the repo keep their own licences and should be taken from
upstream instead: the HTTP plugin (Tauri, MIT/Apache-2.0), OpenCut and `opencut-wasm` (MIT), Three.js addons (MIT). *Not legal advice.*

## 8. Practice scorecard

| Practice | Verdict for a solo developer + AI agents |
| --- | --- |
| Subsystem `AGENTS.md` files with "how to add X" recipes and ⚠ footguns | **copy** (as real files, not symlinks, on Windows) |
| Newspaper file layout, one command/endpoint per file | **copy** — small diffs, local agent edits |
| Version bump script + release branch + draft releases + build metadata in About | **copy** |
| Offline SQLx query cache checked in | n/a to loom2 (Python), same idea: keep generated contracts committed and checked |
| Tested dev tooling (launcher tests, preflight checks, safe cleanup scripts) | **copy** |
| Dated performance and incident docs with raw data | loom2 already does this in its journal — keep |
| Playwright smoke + perf harness against mocked IPC | **copy** |
| No PR CI | **avoid** — loom2's CI already runs tests and both builds |
| Permissive CSP / filesystem-wide asset scope / plaintext secrets | **avoid** — loom2's strict CSP check is better |
| Settings in a member crate that Cargo ignores; duplicated per-OS configs copied over each other in CI | **avoid** |
| Stale rules and scripts naming deleted crates; specs contradicting code | **avoid** — date and re-verify agent docs |
