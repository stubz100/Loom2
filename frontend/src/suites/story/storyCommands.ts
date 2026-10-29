// 17 (D85): the Story suite's verbs — every one has a mouse home (the panel's buttons, the editor rows' tools, the Inspector, right-click
// menus) per D32; Delete and the arrows are accelerators. SY1 adds the Cast tab's verbs (new profile, expand, add to the reference set, lock, copy, open).
import { Paintbrush, RefreshCw, CopyPlus, Hammer, Lightbulb, Group, Ungroup, Workflow, ArrowDown, ArrowLeft, Box, Ruler, ArrowUp, BookOpen, BookPlus, ChevronLeft, ChevronRight, Pencil, UserRoundPlus, Users, Check, CircleHelp, Clapperboard, Copy, CornerDownRight, Film, FolderOpen, GitBranch, GitFork, GraduationCap, ImageOff, ImagePlus, ImageUp, Link, ListChecks, ListPlus, Lock, MapPinPlus, Maximize, Mic, PackagePlus, Palette, PersonStanding, Play, Plus, RotateCcw, ScanFace, Shapes, Sparkles, Square, Star, StickyNote, ToggleLeft, Trash2, Unlink, UserPlus, Volume2, Wand2, X, Zap } from 'lucide-react'
import { command, isEnabled, registerCommands, runCommand, sep, type Command, type MenuItem, type OnItem } from '../../frame/commands'
import { nextOwed, readinessOf, type ReadyCell, type ReadyItem } from './castReady'
import { linesToVoice, spineTodo } from './episodeVerbs'
import { goBack, goBackToIdea, useMakeFor } from '../../store/origin'
import { bareNode, cellsOf, hasWork, nextStep, routeOf, staleFrom, type Cell, type Step } from './board'
import { askConfirm, askConfirmCheck, askText, useSession } from '../../store/session'
import { useAlbum } from '../catalogue/albumStore'
import { CLASS_LABEL, latestModelJob, latestTrainJob, modelSource, nodesAfterWithoutPlace, revealClass, sy, ttsJobFor, useStory, type ProfileClass, shellBlocked, fitBlocked } from './storyStore'
import { forShot, makeClipFor, makeFrameFor, makeTarget, speakersOf } from './makeFor'
import { runStale, staleOf } from './runStale'
import type { FlowNode, Profile, SceneOut, Shot, ShotVersion } from '../../api/types'
import { findNode, pickSampleModel, sampleJob, sampleRecipe, sampleScene, styleGroupName } from './styleSamples'
import { useLibrary } from './libraryStore'
import { FIELD_LABEL, type FieldKey } from '../generate/fieldPresets'
import { needsPicture, swatchJob, useSwatches } from '../generate/swatches'
import { navigate, setRailTab } from '../../frame/router'
import { hasLines } from './flow/types'

const hasWorld = () => !!sy().world
const selected = () => sy().selected
const selStyle = () => selected()?.kind === 'style'
const selBeat = () => selected()?.kind === 'beat'
/** D92: the selected library entry (World's tiles; Generate's tile right-click selects it first) and the selected saved panel. */
const entry = () => { const s = selected(); return s?.kind === 'entry' ? useLibrary.getState().library?.entries.find((e) => e.id === s.id) : undefined }
const panelName = () => { const s = selected(); return s?.kind === 'panel' ? s.id : null }
const panelPreset = async () => { const n = panelName(); if (!n) return null; const { useGenerate } = await import('../generate/generateStore'); return { g: useGenerate.getState(), p: useGenerate.getState().presets.find((x) => x.name === n) } }
const entryAt = (delta: -1 | 1) => { const e = entry(); if (!e) return false; const same = (useLibrary.getState().library?.entries ?? []).filter((x) => x.field === e.field); const i = same.findIndex((x) => x.id === e.id) + delta; return i >= 0 && i < same.length }
/** Story · World on a section (the library, the saved panels …). */
function openWorld(section: 'library' | 'panels' | 'styles'): void {
  sy().setSection(section); navigate({ suite: 'story', tab: 'world' })
}
const style = () => { const s = selected(); return s?.kind === 'style' ? sy().world?.styles.find((x) => x.id === s.id) : undefined }
const sampleModel = () => { const ss = useSession.getState(); return pickSampleModel(ss.capabilities, ss.settings?.samples?.model_id) }   // D91: Settings › Samples' model, else the default
const profile = () => sy().profile()
const version = () => sy().version()
const openVersion = () => version()?.state === 'open'
const animRefable = () => { const c = profile()?.cls; return c === 'character' || c === 'prop' }   // CA0: a place has its set picture instead (CW6)
const isPlace = () => profile()?.cls === 'place'
/** CW6: the place version's set jobs still running (its fit, a face's Fill). */
const setJobs = (surface: string) => { const p = profile(); const v = version(); return p && v ? Object.values(useSession.getState().jobs).filter((j) => j.origin?.surface === surface && j.origin?.ref === p.id
  && (j.origin?.payload as { version?: string } | null)?.version === v.id && !['done', 'failed', 'cancelled'].includes(j.status)) : [] }
const setBusy = () => setJobs('set_fit').length > 0 || setJobs('set_fill').length > 0 || !!version()?.place_set?.faces.some((f) => f.fill_job_id)
const fillable = () => (version()?.place_set?.faces ?? []).filter((f) => f.baked_asset_id && (f.bad ?? 0) >= 0.002).map((f) => f.id)
const toFill = () => (version()?.place_set?.faces ?? []).filter((f) => f.baked_asset_id && !f.filled && (f.bad ?? 0) >= 0.002).map((f) => f.id)
const picked = () => sy().picked
const modelJob = () => { const p = profile(); const v = version(); return p && v ? latestModelJob(useSession.getState().jobs, p.id, v.id) : undefined }
const modelBusy = () => { const j = modelJob(); return !!j && !['done', 'failed', 'cancelled'].includes(j.status) }
const mins = (s: number | null | undefined) => (s ? `${Math.max(1, Math.round(s / 60))} min` : '?')
const trainJob = () => { const p = profile(); const v = version(); return p && v ? latestTrainJob(useSession.getState().jobs, p.id, v.id) : undefined }
const trainCaps = () => useSession.getState().capabilities?.train
const refsCount = () => Object.keys(sy().refPage?.assets ?? {}).length
const shot = () => sy().shot()
const shotVersion = () => sy().shotVersion()
const node = () => sy().node()
const visual = () => node()?.type === 'shot'
const projectOpen = () => !!useSession.getState().project?.open
/** D90 (02 §5): the open version Make ▸ works for — the shown one (Shots), or the one a node pins (Flow); null when final (a retake first). */
const shotTarget = () => makeTarget(shot(), shotVersion()?.id)
const nodeShot = () => { const n = node(); return n?.shot_id ? sy().shots.find((x) => x.id === n.shot_id) : undefined }
/** RC2c: the node's scene group, the frame picked on the canvas (else the node's), the nodes a scene verb takes (the selection when the node is in it). */
const sceneOf = (n: FlowNode | undefined): SceneOut | undefined => (n?.scene_id ? sy().scenes.find((s) => s.id === n.scene_id) : undefined)
const pickedScene = (): SceneOut | undefined => (sy().sceneId ? sy().scenes.find((s) => s.id === sy().sceneId) : undefined) ?? sceneOf(node())
/** RC2f: the other Shots whose shown version stands on the stage (a stage shared is linked). */
export const stageUsers = (shotId: string, stageId: string): Shot[] => sy().shots.filter((s) => s.id !== shotId && s.versions.find((v) => v.id === s.current)?.stage_id === stageId)
const sceneTargets = (): string[] => { const n = node(); if (!n) return []; const sel = sy().flowSel; return sel.length > 1 && sel.includes(n.id) ? sel : [n.id] }
const nodeTarget = () => makeTarget(nodeShot(), node()?.shot_version)
const board = () => { const g = node()?.board_group_id; return g ? findNode(useAlbum.getState().tree, g) : null }
/** D125 (S7): the visual nodes after the selected one without a place, up to the next node that has one. */
const placeTargets = (): string[] => { const n = node(); const g = sy().flowGraph; return n && g ? nodesAfterWithoutPlace(n.id, g.edges, sy().flowNodes) : [] }
/** Open a stage at a camera (Shots' "Open in Stage" and the Stage routes of Make ▸). D93 (C8): `speakers` — Make frame ▸ in Stage binds the
 *  shot's speakers to the stage's figures in screen order when the counts match, else says how to bind them. */
function openStageAt(stageId: string, cam: string | null, speakers?: (Profile & { version?: string | null })[], where: 'image' | 'animate' = 'animate', card: 'clay' | 'clip' | 'final' = 'clay', start: string | null = null): void {
  // D95 (AN1): a still from the stage is made in Image (From a stage); the stage itself in Animate's Clay, its clips in Performance's Stage clip card (D121).
  // D125 (A2): a card asked for opens on Performance (the stage clip with the shot's frame as its start, or the final shot), not on Clay
  if (where === 'image') { void import('../generate/generateStore').then((g) => g.useGenerate.setState({ source: 'stage' })); navigate({ suite: 'generate' }) }
  else { void import('../animate/routeStore').then((r) => r.useAnimRoute.getState().set(card === 'final' ? 'final' : 'clip')); navigate({ suite: card === 'clay' ? 'stage' : 'animate' }) }
  void import('../stage/stageStore').then((m) => { const st = m.useStage.getState(); const go = st.current?.id === stageId ? Promise.resolve() : st.open(stageId); void go.then(() => {
    if (cam) m.useStage.getState().setActiveCamera(cam)
    if (start && card === 'clip') m.useStage.getState().setShotStart(start)
    if (!speakers?.length) return
    const n = m.useStage.getState().prebindSpeakers(speakers)
    const figs = (m.useStage.getState().current?.objects ?? []).filter((o) => o.kind === 'mannequin' && o.visible).length
    useSession.getState().toast(n ? `${speakers.map((p) => p.name).join(', ')} bound to the figures, left to right — their references and sheets go into the frame`
      : `The stage has ${figs} figure${figs === 1 ? '' : 's'} and the scene ${speakers.length} speaker${speakers.length === 1 ? '' : 's'} — bind them yourself: a figure's Inspector › character, or right-click ▸ Bind to a character`, n ? 'success' : 'info') }) })
}
/** D93 (C7): the speakers of the node that owns a shot (or the node Make came from). */
const shotSpeakers = (s: Shot | undefined): (Profile & { version?: string | null })[] => {   // D93 follow-up: with the node's pin per speaker
  const n = s?.owner_node ? sy().flowNodes[s.owner_node] : undefined
  return speakersOf(n, sy().profiles).map((p) => { const pin = n?.speaker_versions?.[p.id]; return pin && p.versions.some((v) => v.id === pin) ? { ...p, version: pin } : p })
}
/** D125 (A2): a shot's stage route in context — the For chip set for Animate (its clips and finals come back to the shot), the stage at the
 *  shot's camera, the card asked for. */
function openStageRoute(card: 'clay' | 'clip' | 'final'): void {
  const s = shot(); const v = shotTarget()
  if (!s || !v?.stage_id) return
  useMakeFor.getState().set('animate', forShot(s, v))
  openStageAt(v.stage_id, v.camera_id, shotSpeakers(s), 'animate', card, v.frame_asset_id ?? null)
}

// ---- D125 (SP5): Cast's readiness — each item's verb (the readiness row is its mouse home; the foot runs the next owed one) ----
const ITEM_CMDS: Record<ReadyItem, string[]> = {
  hero: ['story.cast.setHero', 'story.cast.useAsSubject'], sheet: ['story.cast.editSheet'], refs: ['story.cast.addRef', 'story.cast.expand', 'story.cast.openCandidates'],
  animref: ['story.cast.useAsAnimRef', 'story.cast.makeAnimRef'], body: ['story.cast.fitBody'], model: ['story.cast.makeModel', 'story.cast.importModel'], voice: ['story.cast.newVoice'],
  lora: ['story.cast.train'], final: ['story.cast.lock'],
}
/** The item's verb that can run now (a picked candidate first: it becomes the hero, a reference, the animation reference), or null. */
export const itemCommand = (item: ReadyItem): string | null => ITEM_CMDS[item].find((id) => { const c = command(id); return !!c && isEnabled(c) }) ?? null
export const ITEM_NEXT: Record<ReadyItem, string> = { hero: 'Pick its hero', sheet: 'Write its sheet', refs: 'Make its references', animref: 'Make an animation reference',
  body: 'Fit the body', model: 'Make the 3D model', voice: 'Give it a voice', lora: 'Train a LoRA', final: 'Mark final' }
/** The selected version's readiness row (null without one). */
export function castCells(): ReadyCell[] | null {
  const p = profile(); const v = version()
  if (!p || !v) return null
  const r = sy().castUses[p.id]
  const page = sy().refPage                                                  // the version's reference page, when loaded, counts live
  return readinessOf(p, v, r?.uses ?? [], page && page.group.id === v.group_id ? Object.keys(page.assets).length : r?.refs[v.id])
}
export const castNext = (): ReadyCell | null => { const c = castCells(); return c ? nextOwed(c) : null }

// ---- D125 (SP3): the Shots board's cells — each step's verb for the selected shot (the cell is its mouse home; Ctrl+Enter the next one) ----
export const STEP_VERB: Record<Step, (v: ShotVersion, c: Cell) => { label: string; always?: boolean }> = {
  lines: () => ({ label: 'Write its lines in Flow' }),
  voice: () => ({ label: 'Voice its lines' }),
  frame: (v) => ({ label: v.stage_id ? 'Make frame from the stage (Image)' : 'Make frame in Image', always: true }),
  stage: (v) => ({ label: v.stage_id ? 'Open the stage (Animate · Clay)' : 'Link a stage camera…', always: true }),
  clip: (v) => ({ label: v.stage_id ? 'Make clip on the stage (Animate)' : 'Make clip in Animate', always: true }),
  final: (v) => ({ label: v.stage_id ? 'The final shot (Animate)' : 'Link a stage camera first', always: !!v.stage_id }),
  lipsync: (v) => ({ label: routeOf(v).startsWith('clay') ? 'The Lip-sync pass (the final shot)' : 'Lip-sync ▶ (experimental)', always: true }),
  approved: (v) => ({ label: v.state === 'final' ? 'Marked final' : 'Mark final' }),
  cut: () => ({ label: 'Open the Episode' }),
}
const openStory = (tab: string, then?: () => void) => { navigate({ suite: 'story', tab }); then?.() }
/** Run a step's verb for the selected shot (its cell's click, the foot's next step). */
export function runStep(step: Step): void {
  const v = shotTarget() ?? shotVersion()
  if (!v) return
  switch (step) {
    case 'lines': { const n = shot()?.owner_node; openStory('flow', () => { if (n) sy().selectNode(n) }); return }
    case 'voice': runCommand('story.flow.voiceAll'); return
    case 'frame': runCommand(v.stage_id ? 'story.shot.makeFrameStage' : 'story.shot.makeFrame'); return
    case 'stage': runCommand(v.stage_id ? 'story.shot.openStage' : 'story.shot.linkStage'); return
    case 'clip': runCommand(v.stage_id ? 'story.shot.makeClipStage' : 'story.shot.makeClip'); return
    case 'final': runCommand(v.stage_id ? 'story.shot.makeFinal' : 'story.shot.linkStage'); return
    case 'lipsync': runCommand(routeOf(v).startsWith('clay') ? 'story.shot.makeFinal' : 'story.shot.lipsync'); return
    case 'approved': runCommand('story.shot.finalize'); return
    case 'cut': openStory('episode'); return
  }
}
/** The selected shot's cells (the jobs aside — the board shows them), for the foot's next step. */
function selectedCells(): Record<Step, Cell> | null {
  const s = shot(); const v = shotVersion()
  if (!s || !v) return null
  const st = sy()
  return cellsOf(s, v, s.owner_node ? st.flowNodes[s.owner_node] ?? null : null, {
    clipAudio: (id) => (st.clipsById[id] ? !!st.clipsById[id].audio_asset_id : undefined), finals: st.boardFinals, cuts: st.boardCuts, busy: () => new Set(), stale: staleFrom(st.cards) })
}
export const NEXT_LABEL: Record<Step, string> = { lines: 'Write its lines', voice: 'Voice its lines', frame: 'Make its frame', stage: 'Link a stage camera', clip: 'Make its clip',
  final: 'Make the final shot', lipsync: 'Lip-sync it', approved: 'Mark it final', cut: 'Put it in the cut' }
export const selectedNext = (): Step | null => { const c = selectedCells(); return c ? nextStep(c) : null }

const NODE_ICON = { start: Play, hub: GitFork, choice: ListChecks, condition: CircleHelp, action: Zap, shot: Clapperboard, jump: CornerDownRight, comment: StickyNote } as const
const NODE_LABEL = { start: 'Start', hub: 'Hub', dialogue: 'Dialogue', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' } as const
/** The viewport registers its fit, its centre and the screen → flow mapping (D90 B11) in flow coordinates (the canvas is not a store). */
/** D90 (01 §11.2): the item a per-item command acts on — the take or the line whose button or menu ran it (commands take no
 *  arguments; the button sets this first). A run clears it, so the palette never acts on a stale one. */
export const storyItem: { take?: { kind: 'image' | 'clip'; id: string }; line?: { node: string; index: number }; field?: string; face?: string } = {}   // D92: a library field's Add; CW6: a set's face
/** Run `id` on an item (a take card's ✓ use, a line's 🎙). */
export function runOnItem(item: Partial<typeof storyItem>, id: string): boolean {
  Object.assign(storyItem, item)
  try { return runCommand(id) } finally { for (const k of Object.keys(item) as (keyof typeof storyItem)[]) delete storyItem[k] }
}
/** V69: a menu entry's item, set around its `when` and `run` only (`{ cmd, on: onStoryItem({ take }) }`) — a right-click used to leave
 *  the item set after the menu closed, and the palette then ran *Use this take* / *Fill this face* on the last right-clicked item. */
export const onStoryItem = (item: Partial<typeof storyItem>): OnItem => (f) => {
  Object.assign(storyItem, item)
  try { return f() } finally { for (const k of Object.keys(item) as (keyof typeof storyItem)[]) delete storyItem[k] }
}
const takeUsable = () => { const t = storyItem.take; const v = shotVersion(); return !!t && !!v && v.state === 'open' && (t.kind === 'clip' ? v.clip_id !== t.id : v.frame_asset_id !== t.id) }
const lineVoicable = () => { const l = storyItem.line; const n = l ? sy().flowNodes[l.node] : undefined; const j = l ? ttsJobFor(useSession.getState().jobs, l.node, l.index) : undefined
  return !!n && !!n.lines[l!.index]?.text.trim() && !!useSession.getState().capabilities?.voice?.available && !['staged', 'queued', 'running'].includes(j?.status ?? '') }
const playing = () => sy().play
export const flowView: { fit?: () => void; centre?: () => { x: number; y: number } | null; toFlow?: (x: number, y: number) => { x: number; y: number } } = {}

/** The Cast tab's Expand: the cost said first (D79's pattern), then one queued job per cell of the preset. */
export async function askExpand(preset: string, seeds: number, tier: 'draft' | 'full'): Promise<void> {
  const p = profile(); const v = version(); const caps = useSession.getState().capabilities?.story
  if (!p || !v || !caps?.model_id) return
  const cells = (caps.presets[preset]?.cells ?? 0) * seeds
  const secs = (caps.seconds ?? 0) * cells
  const mins = secs ? `about ${Math.max(1, Math.round(secs / 60))} min with the model loaded` : 'time unknown'
  const ok = await askConfirm({ title: `Expand ${p.name} ${v.id}?`, okLabel: `Queue ${cells} jobs`,
    text: `${caps.presets[preset]?.label ?? preset}: ${cells} ${tier === 'full' ? 'full-size' : 'draft'} images on ${caps.label} with the hero as the reference — ${mins} on this card${caps.missing.length ? ` (weights missing: ${caps.missing.join(', ')})` : ''}. They land on the version's candidates page; keep the good ones into the reference set.` })
  if (ok) await sy().expand(preset, seeds, tier)
}

/** LT2 (18 §3c): the cost before the job — the base and E16's rate, the steps, the references; staged by default. */
export async function askTrain(): Promise<void> {
  const p = profile(); const v = version(); const caps = trainCaps(); const o = sy().trainOpts
  if (!p || !v || !caps?.available) return
  const base = caps.bases.find((b) => b.model_id === (o.model_id ?? caps.bases.find((x) => x.health !== 'missing')?.model_id))
  const secs = base?.s_per_it ? Math.round(o.steps * base.s_per_it) : 0
  const mins = secs ? `about ${Math.max(1, Math.round(secs / 60))} min of steps plus the model loads` : 'time unknown'
  const ok = await askConfirm({ title: `Train ${p.name} ${v.id}?`, okLabel: o.stage ? 'Queue the job' : 'Train now',
    text: `${base?.label ?? 'the base'}${base?.offload ? ' (offloaded)' : ''} · ${o.steps} steps at ${o.resolution}² · rank ${o.rank} · ${refsCount()} references — ${mins} on this card; the engine stops while it runs${o.stage ? '. Staged: release it when the rig is free.' : '.'}` })
  if (ok) await sy().train()
}

/** D90 (02 §4.1): the style's group (its samples), made as "Style · <name>" in the album when it has none (or it was deleted). */
async function ensureStyleGroup(id: string): Promise<string | null> {
  if (!useAlbum.getState().tree) await useAlbum.getState().load()
  const tree = useAlbum.getState().tree
  const s = sy().world?.styles.find((x) => x.id === id)
  if (!s || !tree) return null
  if (s.group_id && findNode(tree, s.group_id)) return s.group_id
  const gid = await useAlbum.getState().create(styleGroupName(s.name))
  sy().setStyle(id, { group_id: gid }); await sy().flush()
  return gid
}

/** D90 (02 §4.1): one Draft image of the style on the preview scene, queued now; the finisher puts it on the style's group (the cover
 *  follows: a group without a chosen cover shows its top asset). The world is saved first so the server appends the fragment as typed. */
export async function makeStyleSample(id: string): Promise<void> {
  const model = sampleModel(); const ss = useSession.getState()
  if (!model) { ss.toast('No sample model in this build'); return }
  try {
    const gid = await ensureStyleGroup(id); if (!gid) return
    await sy().flush()
    const s = sy().world?.styles.find((x) => x.id === id)
    const first = !(findNode(useAlbum.getState().tree, gid)?.total)
    const scene = sampleScene(sy().world, ss.settings?.samples?.style_prompt)   // U2 (G2): the project's own sample scene, else Settings › Samples'
    await ss.submitJob(sampleRecipe(id, model.id, first, scene, model.style_px), {   // D91: the sample model
      suite: 'story', surface: 'style', ref: id, payload: { group_id: gid } })
    ss.toast(`Sample queued for ${s?.name ?? 'the style'} — it lands in "${findNode(useAlbum.getState().tree, gid)?.name ?? styleGroupName(s?.name ?? '')}"`, 'info')
  } catch (e) { ss.toast(`Sample not queued: ${(e as { detail?: string }).detail ?? String(e)}`) }
}

/** D90 (02 §4.1): images dropped on a style become its samples — copies (the originals stay put) on the style's group, the first the cover. */
export async function addStyleSamples(id: string, assetIds: string[]): Promise<void> {
  if (!assetIds.length) return
  try {
    const gid = await ensureStyleGroup(id); if (!gid) return
    const al = useAlbum.getState()
    const dup = await al.duplicateAssets(assetIds)
    if (!dup.length) return
    await al.move(dup.map((a) => ({ kind: 'asset' as const, id: a })), gid)
    await al.setCover(gid, dup[0])
  } catch { /* the album verbs toast their own failures */ }
}

/** A group page in the active Catalogue pane (the Catalogue tab, D125). */
export function openGroupPage(gid: string): void {
  navigate({ suite: 'catalogue' })
  void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: gid }) })
}

export async function newProfile(cls: ProfileClass = 'character', hero: string | null = null): Promise<void> {
  const name = await askText({ title: `New ${CLASS_LABEL[cls]}`, text: hero ? 'The image becomes the hero and the cover of a new reference set; @name mentions it in prompts.' : 'An empty profile: give it a hero from the Catalogue ("Make a character…" on a tile) before expanding.', placeholder: `${CLASS_LABEL[cls]} name` })
  if (!name?.trim()) return
  const p = await sy().createProfile(name.trim(), cls, hero)
  if (p) { revealClass(cls); setRailTab('story', 'cast') }   // D125: Cast shows its class
}

// proto01_UIcast CW1: the ideas store, loaded with the board (the commands' `when` reads it synchronously once it is there)
let ideasMod: typeof import('./ideasStore') | null = null
void import('./ideasStore').then((m) => { ideasMod = m })
const ideaStore = () => ideasMod?.useIdeas.getState() ?? null
const idea = () => ideaStore()?.idea()
const focused = () => ideasMod?.focusOf(idea())
/** CW5: the Cast board's line-up — the class shown (characters and props), searched, twelve at most. */
function castLineup() {
  const s = sy(), q = s.castSearch.trim().toLowerCase()
  return s.profiles.filter((p) => (s.castFilter === 'all' ? p.cls !== 'place' : p.cls === s.castFilter) && p.cls !== 'place' && (!q || p.name.toLowerCase().includes(q))
    && (p.cls === 'character' || !!p.versions.find((v) => v.id === p.current)?.model_asset_id)).slice(0, 12)
}
/** CW5: the Ideas board's line-up — the ideas picked, else the class shown that have clay. */
function ideaLineup() {
  const st = ideaStore(), s = sy(), q = s.castSearch.trim().toLowerCase()
  if (!st) return []
  if (st.picked.length) return st.ideas.filter((i) => st.picked.includes(i.id)).slice(0, 12)
  return st.ideas.filter((i) => (s.castFilter === 'all' || i.cls === s.castFilter) && (!q || i.name.toLowerCase().includes(q)) && i.variants.some((v) => v.clay?.body)).slice(0, 12)
}
/** Back from the line-up: Cast's board it was opened from. */
const backToBoard = (board: 'cast' | 'ideas') => () => void import('./ideasStore').then((m) => {
  navigate({ suite: 'story', tab: 'cast' }); m.useIdeas.setState({ board }) })
/** CW2: Image for the idea — the chip, its picture in focus as reference 1, its prompt (a text prompt). */
async function exploreIdea(i: NonNullable<ReturnType<typeof idea>>): Promise<void> {
  const v = ideasMod?.focusOf(i)
  useMakeFor.getState().setIdea({ idea_id: i.id, name: i.name })
  const g = (await import('../generate/generateStore')).useGenerate.getState()
  g.set({ ...(v ? { refs: [{ asset_id: v.asset_id }] } : {}), prompt_mode: 'text', text: v?.made_from.prompt || i.name })   // 02 §5: the picture as reference 1, its prompt (the name without one)
  navigate({ suite: 'generate' })
}

const cmds: Command[] = [
  { id: 'story.world.addStyle', scope: 'story', label: 'Add style', icon: Palette, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addStyle() } },
  { id: 'story.world.addBeat', scope: 'story', label: 'Add beat', icon: ListPlus, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addBeat() } },
  { id: 'story.world.addVariable', scope: 'story', label: 'Add variable', icon: ToggleLeft, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addVariable() } },
  // D90 (02 §4.1): a style is shown by its sample; the sample is made here or dropped on the tile, its group opened in the Catalogue
  { id: 'story.world.styleSample', scope: 'story', label: 'Make a sample image', icon: ImagePlus, placement: ['inspector', 'context'],
    when: () => !!style() && !!useSession.getState().project?.open && !!sampleModel() && !sampleJob(useSession.getState().jobs, style()!.id),
    run: () => { const s = style(); if (s) void makeStyleSample(s.id) } },
  { id: 'story.world.openStyleGroup', scope: 'story', label: 'Open the samples in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'],
    when: () => !!style()?.group_id && !!findNode(useAlbum.getState().tree, style()?.group_id),
    run: () => { const g = style()?.group_id; if (g) openGroupPage(g) } },
  { id: 'story.world.open', scope: 'story', label: 'Open Story · World', icon: BookOpen, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open,
    run: () => { sy().setSection('styles'); navigate({ suite: 'story', tab: 'world' }) } },
  { id: 'story.world.defaultStyle', scope: 'story', label: 'Make it the default style', icon: Star, placement: ['inspector', 'context'], when: () => selStyle() && sy().world?.default_style !== selected()?.id,
    run: () => { const s = selected(); if (s?.kind === 'style') sy().setDefaultStyle(s.id) } },
  // D92: the World library — an entry is written here only (the Inspector); Generate's tiles and its field's + read and add to it
  { id: 'story.world.addEntry', scope: 'story', label: 'Add to the library…', icon: BookPlus, placement: ['panel', 'context'], when: () => hasWorld() && projectOpen(),
    run: () => { const field = (storyItem.field ?? entry()?.field ?? 'lighting') as FieldKey; storyItem.field = undefined
      void askText({ title: `Add to the library · ${FIELD_LABEL[field] ?? field}`, text: 'The words the field takes. The name is the words until you give it one in the Inspector; a look gets its picture by itself.', placeholder: 'the words' })
        .then(async (t) => { if (!t?.trim()) return; const e = await useLibrary.getState().add(field, t); if (e) { sy().select({ kind: 'entry', id: e.id }); sy().setSection('library') } }) } },
  { id: 'story.world.entryPicture', scope: 'story', label: 'Make a new picture', icon: ImagePlus, placement: ['inspector', 'context'], hint: 'one small image on the sample model (Settings › Samples), run now',
    when: () => { const e = entry(); return !!e && needsPicture(e.field, e.text) && projectOpen() && !!sampleModel() && !swatchJob(useSession.getState().jobs, e.field, e.text) },
    run: () => { const e = entry(); if (e) void useSwatches.getState().make([{ field: e.field, value: e.text }]).then((n) => { if (n) useSession.getState().toast(`A new picture for “${e.name}” is queued`, 'info') }) } },
  { id: 'story.world.editEntry', scope: 'story', label: 'Edit in Story · World', icon: Pencil, placement: ['context'], when: () => !!entry() || !!panelName(),
    run: () => openWorld(entry() ? 'library' : 'panels') },
  { id: 'story.world.entryEarlier', scope: 'story', label: 'Move earlier', icon: ChevronLeft, placement: ['inspector', 'context'], when: () => entryAt(-1), run: () => { const e = entry(); if (e) void useLibrary.getState().move(e.id, -1) } },
  { id: 'story.world.entryLater', scope: 'story', label: 'Move later', icon: ChevronRight, placement: ['inspector', 'context'], when: () => entryAt(1), run: () => { const e = entry(); if (e) void useLibrary.getState().move(e.id, 1) } },
  { id: 'story.world.applyPanel', scope: 'story', label: 'Apply in Image', icon: Wand2, placement: ['inspector', 'context'], when: () => !!panelName(),
    run: () => void panelPreset().then((x) => { if (!x?.p) return; x.g.applyPreset(x.p.name); navigate({ suite: 'generate' }) }) },
  { id: 'story.world.renamePanel', scope: 'story', label: 'Rename…', icon: Pencil, placement: ['inspector', 'context'], when: () => !!panelName(),
    run: () => void panelPreset().then(async (x) => { if (!x?.p) return; const from = x.p.name
      const to = await askText({ title: 'Rename the saved panel', initial: from, placeholder: 'name' })
      if (to && (await x.g.renamePreset(from, to))) sy().select({ kind: 'panel', id: to.trim() }) }) },
  { id: 'story.world.beatUp', scope: 'story', label: 'Move the beat earlier', icon: ArrowUp, keys: 'Ctrl+ArrowUp', placement: ['inspector', 'context'], when: selBeat, run: () => { const s = selected(); if (s) sy().moveBeat(s.id, -1) } },
  { id: 'story.world.beatDown', scope: 'story', label: 'Move the beat later', icon: ArrowDown, keys: 'Ctrl+ArrowDown', placement: ['inspector', 'context'], when: selBeat, run: () => { const s = selected(); if (s) sy().moveBeat(s.id, 1) } },
  { id: 'story.world.remove', scope: 'story', label: 'Remove', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], when: () => !!selected(), danger: true, run: () => sy().removeSelected() },
  // SY1 · Cast
  { id: 'story.cast.new', scope: 'story', label: 'New character…', icon: UserPlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('character') },
  { id: 'story.cast.newPlace', scope: 'story', label: 'New place…', icon: MapPinPlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('place') },
  { id: 'story.cast.newProp', scope: 'story', label: 'New prop…', icon: PackagePlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('prop') },
  // proto01_UIcast CW1–CW2 (06 §2.1–2.2): the Ideas board's verbs, on the idea open on the bench (its variant in focus)
  // D142: Clay opened for the version (its bench); CW5: the line-up of what the board shows (or the ideas picked)
  { id: 'story.cast.bench', scope: 'story', label: 'Bench ▶', icon: Hammer, placement: ['panel', 'inspector', 'context'],
    hint: "Clay opened for this version: its figure (a prop: its model at its height beside a 1.75 m figure; a place: its set from the picture's camera) on a scene of its own, with all of Clay's tools",
    when: () => { const p = sy().profile(); const v = sy().version(); return !!p && !!v && (p.cls === 'character' || (p.cls === 'prop' && !!v.model_asset_id) || (p.cls === 'place' && !!v.place_set)) },
    run: () => { const p = sy().profile(); const v = sy().version(); if (p && v) void import('../stage/stageStore').then((m) => m.st().openBench(p.id, v.id)) } },
  { id: 'story.cast.lineup', scope: 'story', label: 'Line-up ▶', icon: Users, placement: ['panel', 'context'], hint: 'the characters and props shown, side by side at their sizes in Clay (twelve at most)',
    when: () => castLineup().length > 0, run: () => { const items = castLineup().map((p) => ({ profile_id: p.id })); void import('../stage/stageStore').then((m) => m.st().openLineup(items, backToBoard('cast'))) } },
  { id: 'story.idea.lineup', scope: 'story', label: 'Line-up ▶', icon: Users, placement: ['panel', 'context'], hint: 'the ideas picked (Ctrl-click), else those shown, in their clay side by side in Clay',
    when: () => ideaLineup().length > 0, run: () => { const items = ideaLineup().map((i) => ({ idea_id: i.id })); void import('../stage/stageStore').then((m) => m.st().openLineup(items, backToBoard('ideas'))) } },
  { id: 'story.idea.new', scope: 'story', label: 'New idea…', icon: Lightbulb, placement: ['panel', 'context'], hint: "of the class shown; Prototype ▸ on a picture starts one with it",
    when: () => !!useSession.getState().project?.open,
    run: () => { const f = sy().castFilter; const cls = f === 'all' ? 'character' : f
      void askText({ title: `New ${cls} idea`, text: 'Its pictures come later: Prototype ▸ on any picture, a drop on its row, or Explore in Image.', placeholder: `${cls} idea` })
        .then(async (n) => { if (n === null) return; const m = await import('./ideasStore'); const i = await m.useIdeas.getState().create(cls, null, n.trim() || null); if (i) m.useIdeas.getState().select(i.id) }) } },
  { id: 'story.idea.clay', scope: 'story', label: 'Make the clay ▶', icon: Shapes, placement: ['panel', 'context'], hint: 'the A-pose picture, the body fitted to it, then the shell in the background (a character)',
    when: () => { const i = idea(); const v = focused(); return i?.cls === 'character' && !!v && !(v.clay && v.clay.job_id && ['drawing', 'fitting', 'shell'].includes(v.clay.step)) },
    run: () => { const i = idea(); const v = focused(); if (i && v) void ideaStore()?.makeClay(i.id, v.id) } },
  { id: 'story.idea.keep', scope: 'story', label: 'Keep ▶', icon: Check, placement: ['panel', 'context'], hint: 'a new Cast profile from the variant in focus: the hero, a sheet drafted from its prompt, its clay',
    when: () => !!focused(), run: () => { const i = idea(); const v = focused(); if (i && v) void ideaStore()?.keep(i.id, v.id) } },
  { id: 'story.idea.explore', scope: 'story', label: 'Explore in Image', icon: Wand2, placement: ['panel', 'context'], hint: "Image with the For chip on the idea, its picture as reference 1 and its prompt — what it makes is listed on the idea",
    when: () => !!idea(), run: () => { const i = idea(); if (i) void exploreIdea(i) } },
  { id: 'story.idea.rename', scope: 'story', label: 'Rename the idea…', icon: Pencil, placement: ['inspector', 'context'], when: () => !!idea(),
    run: () => { const i = idea(); if (i) void askText({ title: 'Rename the idea', initial: i.name }).then((n) => { if (n?.trim()) void ideaStore()?.patch(i.id, { name: n.trim() }) }) } },
  { id: 'story.idea.delete', scope: 'story', label: 'Delete the idea…', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!idea(),
    run: () => { const i = idea(); if (i) void import('./ideaVerbs').then((m) => m.confirmDelete(i)).then((ok) => { if (ok) void ideaStore()?.remove(i.id) }) } },
  // D115: Expand lives in Image — the character as the subject, Full coverage pre-picked in the Poses section, Expand ▶ runs it
  { id: 'story.cast.expand', scope: 'story', label: 'Expand in Image…', icon: Sparkles, keys: 'Ctrl+Enter', placement: ['panel', 'inspector', 'context'],
    when: () => openVersion() && !!version()?.hero_asset_id && !!useSession.getState().capabilities?.story?.model_id && !sy().expanding,
    run: () => { const p = profile(); const v = version(); if (!p || !v) return
      void import('../generate/generateStore').then((g) => {
        const gs = g.useGenerate.getState(); gs.useAsSubject(p)
        const story = useSession.getState().capabilities?.story
        if (story?.model_id) gs.set({ model_id: story.model_id })          // the model Expand ran on in Cast: it takes the hero as a reference and renders the same person
        const plan = ((story?.presets as Record<string, { plan?: { shot: string; angle: string; expression: string }[] }> | undefined)?.full?.plan ?? [])
        gs.setPoses({ cells: plan.map((c) => ({ shot: c.shot, angle: c.angle, expression: c.expression })), expressions: Array.from(new Set(plan.map((c) => c.expression))) })
        gs.setRun('expand'); navigate({ suite: 'generate', tab: 'poses' })
        useSession.getState().toast(`${p.name} ${v.id}: pick the poses, then Expand ▶ — the images land as its candidates`, 'info') }) } },
  // D125 (SP5): the readiness row's Sheet item, and the foot's next owed step
  { id: 'story.cast.editSheet', scope: 'story', label: 'Write the sheet', icon: Pencil, hint: "the version's look in words — Make frame and Expand compose it into every image of it", placement: ['strip'],
    when: () => !!version(), run: () => { const el = document.getElementById('cast-appearance') as HTMLTextAreaElement | null; el?.scrollIntoView({ block: 'center' }); el?.focus() } },
  { id: 'story.cast.next', scope: 'story', label: 'Do the next owed step', icon: ChevronRight, hint: "the first item of the readiness row a shot of this profile still needs", placement: ['panel'],
    when: () => { const n = castNext(); return !!n && !!itemCommand(n.item) }, run: () => { const n = castNext(); const id = n ? itemCommand(n.item) : null; if (id) runCommand(id) } },
  { id: 'story.cast.addRef', scope: 'story', label: 'Add to the reference set', icon: Check, keys: 'K', placement: ['context', 'inspector', 'toolbar'], when: () => openVersion() && picked().length > 0,
    run: () => void sy().addRefs(picked()) },
  { id: 'story.cast.setHero', scope: 'story', label: 'Make it the hero', icon: ImageUp, placement: ['context', 'inspector'], when: () => openVersion() && picked().length === 1,
    run: () => void sy().setHero(picked()[0]) },
  // CA0 (01 step 2, §10): the animation reference — characters (front, back) and props (front, a three-quarter view); a final version takes one too
  { id: 'story.cast.makeAnimRef', scope: 'story', label: 'Make an animation reference', icon: PersonStanding, hint: 'full body, A-pose, 16:9, plain ground — two candidates from the sheet and references',
    placement: ['panel', 'inspector', 'context'], when: () => animRefable() && !!useSession.getState().capabilities?.story?.model_id, run: () => void sy().makeAnimRef('front') },
  { id: 'story.cast.fitBody', scope: 'story', label: 'Fit the body to the animation reference', icon: Ruler,
    hint: "the reference's proportions measured (neck, shoulders, torso, limbs, hands) so the stage figure moves with the character's build; the height and build stay",
    placement: ['panel', 'inspector', 'context'], when: () => profile()?.cls === 'character' && !fitBlocked(version()) && version()?.state === 'open', run: () => void sy().fitBody() },   // D140: only on an A-pose
  // CS2 (proto01_UIcast 03 §3.2, D136 U17): the skeleton bench — its view, its foot's verbs (its code loads with the stage's)
  { id: 'cast.skeleton.open', scope: 'story', label: 'Skeleton…', icon: PersonStanding, hint: "the character's skeleton against its reference, its figure and its guide — fit, tune and lock each part",
    placement: ['panel', 'inspector', 'context'], when: () => profile()?.cls === 'character' && !!version(), run: () => sy().setSkeleton(true) },
  { id: 'cast.skeleton.close', scope: 'story', label: 'Back to the sheet', icon: ChevronLeft, placement: ['panel'], when: () => sy().skeleton, run: () => sy().setSkeleton(false) },
  { id: 'cast.skeleton.fit', scope: 'story', label: 'Fit again ▶', icon: Ruler, hint: "the body fitted to the points as they are now — SDPose's, with those you moved; the locked parts stay",
    placement: ['panel', 'context'], when: () => sy().skeleton && openVersion() && !!version()?.body_points && !fitBlocked(version()),
    run: () => void import('../stage/benchState').then((m) => { const pts = m.bench.points(); if (pts) void sy().refitBody(pts as never) }) },
  { id: 'cast.skeleton.sdpose', scope: 'story', label: "Back to SDPose's points", icon: RotateCcw, placement: ['panel', 'context'], when: () => sy().skeleton && !!version()?.body_points,
    run: () => { const v = version(); if (v) void import('../stage/benchState').then((m) => m.bench.resetPoints(v)) } },
  { id: 'cast.skeleton.mirror', scope: 'story', label: 'Mirror left to right', icon: Copy, hint: 'the side you moved last, onto the other', placement: ['panel', 'context'], when: () => sy().skeleton && !!version()?.body_points,
    run: () => void import('../stage/benchState').then((m) => m.bench.mirror()) },
  { id: 'cast.skeleton.test', scope: 'story', label: 'Test in motion ▶', icon: Play, hint: "the turn test on the shots' own guide (a GPU job; its cost is asked first)", placement: ['panel'],
    when: () => sy().skeleton && !!version()?.anim_ref_asset_id, run: () => runCommand('story.cast.testAnimRef') },
  { id: 'cast.shell.make', scope: 'story', label: 'Make the shell ▶', icon: Shapes,
    hint: "the 3D model of the animation reference in the A-pose (Pixal3D, about four minutes in the background): the clay the character's figures are drawn in — the reference fitted first; arms held against the body would be made part of it (D139)",
    placement: ['panel', 'inspector', 'context'], when: () => profile()?.cls === 'character' && !shellBlocked(version()) && !!useSession.getState().capabilities?.mesh?.model_id,
    run: () => void sy().makeShell() },
  { id: 'story.cast.makeAnimRefBack', scope: 'story', label: 'Make a back view', icon: PersonStanding, hint: 'the same A-pose from behind — for a shot that starts with the character turned away',
    placement: ['panel', 'inspector', 'context'], when: () => profile()?.cls === 'character' && !!useSession.getState().capabilities?.story?.model_id, run: () => void sy().makeAnimRef('back') },
  { id: 'story.cast.useAsAnimRef', scope: 'story', label: 'Use as the animation reference', icon: PersonStanding, placement: ['context', 'inspector'], when: () => animRefable() && picked().length === 1,
    run: () => void sy().setAnimRef('front', picked()[0]) },
  { id: 'story.cast.useAsAnimRefBack', scope: 'story', label: 'Use as the back view', icon: PersonStanding, placement: ['context', 'inspector'], when: () => profile()?.cls === 'character' && picked().length === 1,
    run: () => void sy().setAnimRef('back', picked()[0]) },
  { id: 'story.cast.clearAnimRef', scope: 'story', label: 'Clear the animation reference', icon: X, placement: ['inspector', 'context'], when: () => !!version()?.anim_ref_asset_id,
    run: () => void sy().setAnimRef('front', null) },
  { id: 'story.cast.clearAnimRefBack', scope: 'story', label: 'Clear the back view', icon: X, placement: ['inspector', 'context'], when: () => !!version()?.anim_ref_back_asset_id,
    run: () => void sy().setAnimRef('back', null) },
  // D110 (PS2): a prop is made like a character — its images, then its 3D model (image → mesh, stood upright), which Animate places
  { id: 'story.cast.makeModel', scope: 'story', label: 'Make the 3D model…', icon: Box, hint: 'from the animation reference (else the hero): a textured model, stood upright — a background job of some minutes',
    placement: ['panel', 'inspector', 'context'],
    when: () => profile()?.cls === 'prop' && !!version() && !!modelSource(version()!) && !!useSession.getState().capabilities?.mesh?.model_id && !modelBusy(),
    run: () => { const p = profile(); const v = version(); const mc = useSession.getState().capabilities?.mesh; if (!p || !v || !mc?.model_id) return
      void askConfirm({ title: `${v.model_asset_id ? 'Remake' : 'Make'} ${p.name}'s 3D model?`, okLabel: 'Queue it',
        text: `${mc.label} builds a textured model from ${v.anim_ref_asset_id ? 'the animation reference' : 'the hero'} and stands it upright. About ${mins(mc.seconds)} with the model loaded, ${mins(mc.cold_seconds)} from cold, in the background${mc.health === 'missing' ? ' — its weights are missing (Models › Fetch)' : ''}.${v.model_asset_id ? ' The old model stays in the Catalogue.' : ''}` })
        .then((ok) => { if (ok) void sy().makeModel() }) } },
  { id: 'story.cast.importModel', scope: 'story', label: 'Import a 3D model (GLB)…', icon: Box, placement: ['panel', 'inspector', 'context'],
    hint: 'a .glb of your own (or one whose licence you vouch for) becomes this version\'s model, as it is — every prop has a 3D model (D128)',
    when: () => profile()?.cls === 'prop' && !!version() && !modelBusy(),
    run: () => void askText({ title: 'Import a 3D model', text: 'The path of a .glb file (binary glTF 2.0). It joins the Catalogue as a mesh and becomes this version\'s model.', placeholder: 'D:\\models\\cup.glb' })
      .then((v) => { if (v?.trim()) void sy().importModel(v.trim()) }) },
  { id: 'story.cast.clearModel', scope: 'story', label: 'Clear the 3D model', icon: X, placement: ['inspector', 'context'], when: () => !!version()?.model_asset_id,
    run: () => void sy().setModel(null) },
  // CW6 (proto01_UIcast 04 §3–6; D143): a place's set — its picture (the place empty), the fit, the bake, the Fill
  { id: 'cast.place.picture', scope: 'story', label: 'Make the set picture ▶', icon: ImagePlus, hint: 'the place empty, from eye level, its floor and walls in view — two candidates from the sheet and references',
    placement: ['panel', 'inspector', 'context'], when: () => isPlace() && !!useSession.getState().capabilities?.story?.model_id, run: () => void sy().makeAnimRef('front') },
  { id: 'cast.place.usePicture', scope: 'story', label: 'Use as the set picture', icon: ImagePlus, placement: ['context', 'inspector'], when: () => isPlace() && picked().length === 1,
    run: () => void sy().setAnimRef('front', picked()[0]) },
  { id: 'cast.place.build', scope: 'story', label: 'Build the set ▶', icon: Box, hint: "MoGe reads the set picture's depth: a room, a corridor, a street or open ground fitted to it, scaled by the camera's height, then the picture baked onto its faces",
    placement: ['panel', 'inspector', 'context'], when: () => isPlace() && !!version() && !!(version()!.anim_ref_asset_id ?? version()!.hero_asset_id) && !setBusy(),
    run: () => { const v = version(); const h = v?.place_set?.sources[0]?.camera.pos[1]; void import('./setBuilder').then((m) => m.buildSet(h ?? m.EYE_HEIGHT_M)) } },
  { id: 'cast.place.bake', scope: 'story', label: 'Bake again ▶', icon: RefreshCw, hint: 'the picture projected onto the faces again — after the set or its camera changed (the Fills are made again after it)',
    placement: ['panel', 'context'], when: () => isPlace() && !!version()?.place_set?.sources.length && !setBusy(), run: () => void import('./setBuilder').then((m) => m.bakeSet()) },
  { id: 'cast.place.fill', scope: 'story', label: 'Fill what the picture never saw ▶', icon: Paintbrush, hint: 'Klein paints each face the picture did not see well, the most seen first, with its material — about 45 s a face',
    placement: ['panel', 'context'], when: () => isPlace() && toFill().length > 0 && !setBusy(), run: () => void import('./setBuilder').then((m) => m.fillSet()) },
  { id: 'cast.place.fillFace', scope: 'story', label: 'Fill this face ▶', icon: Paintbrush, hint: 'a filled face is filled again from its bake, with another seed — name its material first for a cleaner surface',
    placement: ['context'], when: () => isPlace() && !!storyItem.face && fillable().includes(storyItem.face) && !setBusy(),
    run: () => { const f = storyItem.face; if (f) void import('./setBuilder').then((m) => m.fillSet([f])) } },
  { id: 'cast.place.clear', scope: 'story', label: 'Clear the set…', icon: X, danger: true, placement: ['inspector', 'context'], when: () => isPlace() && !!version()?.place_set && !setBusy(),
    run: () => void askConfirm({ title: 'Clear the set?', okLabel: 'Clear', text: 'Its kind, sizes and faces go; the baked and filled faces stay in the Catalogue. Build the set ▶ fits it again.' })
      .then((ok) => { if (ok) void import('./setBuilder').then((m) => m.saveSet(null)) }) },
  { id: 'story.cast.testAnimRef', scope: 'story', label: 'Test it: a turn on the spot…', icon: Play, hint: 'the reference performs a turn through the pose-driven model (the cost is asked first)',
    placement: ['panel', 'inspector', 'context'], when: () => profile()?.cls === 'character' && !!version()?.anim_ref_asset_id && !!useSession.getState().capabilities?.stage?.animate,
    run: () => void import('./animTest').then((m) => m.testAnimRef()) },
  { id: 'story.cast.playAnimTest', scope: 'story', label: 'Play the test in Animate', icon: Film, placement: ['inspector', 'context'], when: () => !!version()?.anim_test_clip_id,
    run: () => void import('./animTest').then((m) => m.playAnimTest()) },
  { id: 'story.cast.lock', scope: 'story', label: 'Mark final', icon: Lock, hint: 'the version\'s reference set becomes read-only; a retake is a new version', placement: ['strip', 'inspector', 'context'], when: () => openVersion() && !!version()?.hero_asset_id && !sy().busy,
    run: () => { const p = profile(); const v = version(); if (!p || !v) return
      void askConfirm({ title: `Mark ${p.name} ${v.id} final?`, okLabel: 'Mark final', text: 'The reference set becomes read-only (the album refuses changes on its page) and the character sheet is fixed (the label can still change); @mentions keep resolving to it. A retake is a new version.' }).then((ok) => { if (ok) void sy().lockVersion() }) } },
  { id: 'story.cast.newVersion', scope: 'story', label: 'New version (copy)', icon: Copy, placement: ['strip', 'inspector', 'context'], when: () => !!version() && !sy().busy,
    run: () => { const p = profile(); const v = version(); if (!p || !v) return
      void askConfirm({ title: `Copy ${p.name} ${v.id} into a new version?`, okLabel: 'Copy', text: 'The reference set is duplicated (its images copied — an image lives on one page), the sheet and hero copied; the copy becomes the current version, open — a new costume, age or look: give it a label.' }).then((ok) => { if (ok) void sy().newVersion() }) } },
  { id: 'story.cast.train', scope: 'story', label: 'Train a LoRA…', icon: GraduationCap, placement: ['panel', 'inspector', 'context'],
    when: () => !!version()?.hero_asset_id && !!trainCaps()?.available && refsCount() >= (trainCaps()?.min_refs ?? 4) && !['staged', 'queued', 'running'].includes(trainJob()?.status ?? '') && !sy().busy,
    run: () => void askTrain() },
  { id: 'story.cast.useLora', scope: 'story', label: 'Use in Image', icon: Wand2, placement: ['inspector', 'context'], when: () => !!version()?.lora,
    run: () => void sy().useLora(version()!.lora!) },
  { id: 'story.cast.checkLora', scope: 'story', label: 'Check the identity (8 images)', icon: ScanFace, placement: ['inspector', 'context'],
    when: () => !!version()?.lora && !!version()?.hero_asset_id && !!useSession.getState().capabilities?.facesim?.available,
    run: () => void sy().checkLora(version()!.lora!) },
  { id: 'story.cast.deleteLora', scope: 'story', label: 'Delete the LoRA', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!version()?.lora,
    run: async () => { const v = version(); if (!v?.lora) return; if (await askConfirm({ title: 'Delete the LoRA?', okLabel: 'Delete', text: 'The file, its record and the engine\'s cached copy go; the version keeps its trigger for a retrain.' })) await sy().deleteLora(v.lora) } },
  { id: 'story.cast.releaseTrain', scope: 'story', label: 'Run now', icon: Play, hint: 'the training job waiting in the queue', placement: ['inspector'], when: () => trainJob()?.status === 'staged',
    run: () => { const j = trainJob(); if (j) void useSession.getState().releaseJob(j.id) } },
  { id: 'story.cast.resumeTrain', scope: 'story', label: 'Resume the training job', icon: RotateCcw, placement: ['inspector'], when: () => trainJob()?.status === 'failed' && !!trainJob()?.resumable,
    run: () => { const j = trainJob(); if (j) void sy().requeueTrain(j.id) } },
  { id: 'story.cast.cancelTrain', scope: 'story', label: 'Cancel the training job', icon: X, placement: ['inspector'], when: () => ['staged', 'queued', 'running'].includes(trainJob()?.status ?? ''),
    run: () => { const j = trainJob(); if (j) void useSession.getState().cancelJob(j.id) } },
  { id: 'story.cast.openGroup', scope: 'story', label: 'Open the reference set in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version(),
    run: () => { const v = version(); if (v) openGroupPage(v.group_id) } },
  { id: 'story.cast.openCandidates', scope: 'story', label: 'Open the candidates in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version()?.candidates_group_id,
    run: () => { const g = version()?.candidates_group_id; if (g) openGroupPage(g) } },
  // SY2 · Shots
  { id: 'story.shot.new', scope: 'story', label: 'New shot…', icon: Clapperboard, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open,
    run: () => void askText({ title: 'New shot', text: 'An empty shot: Make frame ▸ / Make clip ▸ on its board open Image, Animate or a Stage camera for it, and what they make comes back as takes.', placeholder: 'shot name' })
      .then((n) => { if (n?.trim()) void sy().createShot(n.trim()) }) },
  { id: 'story.shot.newVersion', scope: 'story', label: 'New version (copy)', icon: Copy, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion(),
    run: () => { const s = shot(); const v = shotVersion(); if (!s || !v) return
      void askConfirm({ title: `Copy ${s.name} ${v.id} into a new version?`, okLabel: 'Copy', text: 'The source, frame and clip pointers are copied (no files); the copy becomes the current version, open — a retake.' }).then((ok) => { if (ok) void sy().newShotVersion() }) } },
  { id: 'story.shot.lipsync', scope: 'story', label: 'Lip-sync ▶ (experimental)', icon: Mic, placement: ['inspector', 'context'],
    when: () => { const v = shotVersion(); const c = useSession.getState().capabilities?.experimental?.lipsync
      return !!v && v.state === 'open' && !!v.frame_asset_id && !!c?.available && sy().lipsyncLines().some((l) => !l.too_long) },   // D90 (B6): a line within the window
    run: () => { const c = useSession.getState().capabilities?.experimental?.lipsync; const o = sy().lipsyncOpts; const p = c?.presets?.[o.preset] as { seconds?: number | null } | undefined
      void askConfirm({ title: 'Lip-sync this version (experimental)?', okLabel: 'Queue the job',
        text: `${c?.label ?? 'S2V'} · ${o.preset} — ≈ ${Math.round((p?.seconds ?? 0) / 60)} min with the engine. ${c?.caveat ?? ''}. The talking clip lands as a take on the version.` })
        .then((ok) => { if (ok) void sy().lipsync() }) } },
  { id: 'story.shot.finalize', scope: 'story', label: 'Mark final', icon: Lock, hint: 'the clip becomes the one the Flow and the Episode bind; a retake is a new version', placement: ['strip', 'inspector', 'context'], when: () => { const v = shotVersion(); return !!v && v.state === 'open' && !sy().finalizeWhy(v) },
    run: () => { const s = shot(); const v = shotVersion(); if (!s || !v) return
      void askConfirm({ title: `Mark ${s.name} ${v.id} final?`, okLabel: 'Mark final', text: 'The clip becomes the one the Flow and the Episode bind; the frame and clip are fixed. A retake is a new version.' }).then((ok) => { if (ok) void sy().finalizeShot() }) } },
  // D90 (01 §11.2): a take becomes the version's frame or clip (the take card's ✓ use and its right-click)
  { id: 'story.shot.useTake', scope: 'story', label: 'Use this take', icon: Check, placement: ['toolbar', 'context'], hint: 'a frame take becomes the version\'s frame, a clip take its clip', when: takeUsable,
    run: () => { const t = storyItem.take; storyItem.take = undefined; if (t) void sy().useTake(t.kind, t.id) } },
  { id: 'story.shot.openStage', scope: 'story', label: 'Open the stage (Animate · Clay)', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion()?.stage_id,
    run: () => { if (shotTarget()?.stage_id) { openStageRoute('clay'); return } const v = shotVersion(); if (v?.stage_id) openStageAt(v.stage_id, v.camera_id) } },   // D125: in context while open
  // D125 (S11): an existing shot pointed at a stage camera (no second shot); a new stage made for it; its final shot opened in context
  { id: 'story.shot.linkStage', scope: 'story', label: 'Link a stage camera…', icon: Link, hint: 'this version takes a stage camera as its source — its stills and clips come back by the camera', placement: ['inspector', 'context'],
    when: () => projectOpen() && !!shotTarget(), run: () => { const s = shot(); const v = shotTarget(); if (s && v) sy().setLinkFor({ shotId: s.id, version: v.id }) } },
  { id: 'story.shot.blockOnStage', scope: 'story', label: 'Block it on a stage…', icon: Shapes, hint: 'a new stage named after the shot, its camera linked; Animate · Clay opens on it for this shot', placement: ['inspector', 'context'],
    when: () => projectOpen() && !!shotTarget() && !shotTarget()?.stage_id,
    run: () => { const s = shot(); const v = shotTarget(); if (!s || !v) return
      void askConfirm({ title: `Block ${s.name} on a new stage?`, okLabel: 'Make the stage', text: `A stage named ${s.name} with one camera, linked to ${s.name} ${v.id}; Animate · Clay opens on it, the speakers bound to its figures as you add them.` })
        .then(async (ok) => { if (!ok) return
          try {
            const { http, unwrap } = await import('../../api/client')
            const st = await unwrap(http.POST('/stages', { body: { name: s.name } }))
            if (await sy().linkStage(s.id, v.id, st.id, st.cameras[0]?.id ?? null)) openStageRoute('clay')
          } catch (e) { useSession.getState().toast(`Stage: ${(e as { detail?: string }).detail ?? String(e)}`) } }) } },
  { id: 'story.shot.makeFinal', scope: 'story', label: 'The final shot (Animate)', icon: Film, hint: 'Performance › Final shot on the stage camera of this shot, for it — its finished render comes back as a take', placement: ['inspector', 'context'],
    when: () => !!shotTarget()?.stage_id, run: () => openStageRoute('final') },
  { id: 'story.shot.next', scope: 'story', label: 'Do the next step', icon: Play, keys: 'Ctrl+Enter', hint: 'the first step the shot still owes, from the board', placement: ['panel'],
    when: () => !!shot() && !!selectedNext(), run: () => { const n = selectedNext(); if (n) runStep(n) } },
  // D90 (02 §5): Make frame ▸ / Make clip ▸ — the maker opens with the For chip and its results come back as this version's takes; the
  // Stage routes open the version's camera (its results already become takes of the shots pointing at it)
  { id: 'story.shot.makeFrame', scope: 'story', label: 'Make frame in Image', icon: ImagePlus, placement: ['strip', 'inspector', 'context'], when: () => projectOpen() && !!shotTarget(),
    run: () => { const s = shot(); const v = shotTarget(); if (s && v) void makeFrameFor(s, v) } },
  { id: 'story.shot.makeFrameStage', scope: 'story', label: 'Make frame from the stage (Image)', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotTarget()?.stage_id,
    run: () => { const s = shot(); const v = shotTarget(); if (!s || !v?.stage_id) return
      useMakeFor.getState().set('generate', forShot(s, v))                 // D125 (I1): From a stage, with the chip on the shot (its stills come back by the camera)
      openStageAt(v.stage_id, v.camera_id, shotSpeakers(s), 'image') } },
  { id: 'story.shot.makeClip', scope: 'story', label: 'Make clip in Animate', icon: Film, placement: ['strip', 'inspector', 'context'], when: () => projectOpen() && !!shotTarget(),
    run: () => { const s = shot(); const v = shotTarget(); if (s && v) void makeClipFor(s, v) } },
  { id: 'story.shot.makeClipStage', scope: 'story', label: 'Make clip on the stage (Animate)', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotTarget()?.stage_id,
    run: () => openStageRoute('clip') },   // D95 (AN1, UX0 #21): the speakers bound; D125 (A2): Performance's Stage clip card, the For chip, the shot's frame as the start
  // the For chip's verbs in the makers' Panels (D32: a command each)
  { id: 'gen.for.back', scope: 'generate', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], hint: 'and stop making for it (D125)', when: () => !!useMakeFor.getState().generate, run: () => goBack('generate') },
  { id: 'gen.for.clear', scope: 'generate', label: 'Stop making for the shot (results stay in the Catalogue only)', icon: X, placement: ['panel'], when: () => !!useMakeFor.getState().generate,
    run: () => useMakeFor.getState().set('generate', null) },
  // proto01_UIcast CW2: the idea chip's verbs
  { id: 'gen.idea.back', scope: 'generate', label: 'Back to the idea', icon: ArrowLeft, placement: ['panel'], hint: 'its bench in Cast, and stop making for it', when: () => !!useMakeFor.getState().idea, run: () => goBackToIdea() },
  { id: 'gen.idea.clear', scope: 'generate', label: 'Stop making for the idea', icon: X, placement: ['panel'], when: () => !!useMakeFor.getState().idea, run: () => useMakeFor.getState().setIdea(null) },
  // RC0 (D96): Run stale — the shown version in Story, the For chip's version in Animate (the recipe list under it shows the button)
  { id: 'story.shot.runStale', scope: 'story', label: 'Run stale steps…', icon: RotateCcw, hint: 'the plan and its cost first; the results become the frame and clip', placement: ['inspector', 'context'],
    when: () => { const s = shot(); const v = shotVersion(); return !!s && v?.state === 'open' && staleOf(s.id, v.id) > 0 }, run: () => { const s = shot(); const v = shotVersion(); if (s && v) void runStale(s.id, v.id) } },
  { id: 'anim.for.runStale', scope: 'animate', label: 'Run stale steps…', icon: RotateCcw, hint: 'the plan and its cost first; the results become the frame and clip', placement: ['panel', 'strip'],   // RC1: the Graph's strip too
    when: () => { const f = useMakeFor.getState().animate; return !!f && staleOf(f.shot_id, f.version) > 0 }, run: () => { const f = useMakeFor.getState().animate; if (f) void runStale(f.shot_id, f.version) } },
  { id: 'anim.for.back', scope: 'animate', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], hint: 'and stop making for it (D125)', when: () => !!useMakeFor.getState().animate, run: () => goBack('animate') },
  { id: 'anim.for.clear', scope: 'animate', label: 'Stop making for the shot (clips stay in the Catalogue only)', icon: X, placement: ['panel'], when: () => !!useMakeFor.getState().animate,
    run: () => useMakeFor.getState().set('animate', null) },
  { id: 'story.shot.openAnimate', scope: 'story', label: 'Open in Animate', icon: Film, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion()?.clip_id,
    run: () => { const v = shotVersion(); if (!v?.clip_id) return; const cid = v.clip_id
      navigate({ suite: 'animate' })
      void import('../animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(cid)) }) } },
  // RC2a (proto01_animate 31 §3b): a shot is in its node — releasing it moves it to a Shot node of its own beside it; the node gets a fresh shot
  { id: 'story.shot.release', scope: 'story', label: 'Move to a node of its own', icon: Unlink, placement: ['inspector', 'context'],
    hint: 'the shot leaves its node for a Shot node beside it (outside the routes); the node keeps its lines and gets a fresh shot',
    when: () => { const s = shot(); const n = s?.owner_node ? sy().flowNodes[s.owner_node] : undefined; return !!s && !!n && !bareNode(n, sy().flowGraph) && hasWork(s) },
    run: () => void sy().patchShot({ owner_node: null }) },
  { id: 'story.shot.delete', scope: 'story', label: 'Delete shot', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!shot(),
    run: () => { const s = shot(); if (!s) return
      void askConfirm({ title: `Delete ${s.name}?`, okLabel: 'Delete', danger: true, text: 'Its versions and takes go; the frames and clips stay in the Catalogue. Its node keeps its lines and gets a fresh shot — a Shot node outside the routes goes with it.' }).then((ok) => { if (ok) void sy().deleteShot() }) } },
  // SY3 · Flow
  ...(Object.keys(NODE_ICON) as (keyof typeof NODE_ICON)[]).map((t): Command => ({
    id: `story.flow.add.${t}`, scope: 'story', label: `Add ${NODE_LABEL[t]}`, icon: NODE_ICON[t], placement: ['strip', 'context'], when: () => !!useSession.getState().project?.open && !sy().play,
    run: () => { void sy().addNode(t) },
  })),
  { id: 'story.flow.delete', scope: 'story', label: 'Delete node', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!node() && !sy().play,
    run: () => { const n = node(); if (!n) return
      const sh = nodeShot()
      if (!sh || sh.owner_node !== n.id) { void askConfirm({ title: `Delete ${n.title || NODE_LABEL[n.type]}?`, okLabel: 'Delete', danger: true, text: 'Its edges go with it.' }).then((ok) => { if (ok) void sy().deleteNode(n.id) }); return }
      // D125 (#4) / RC2a: the node is its shot — the shot moves to a Shot node of its own, or goes too (its frames and clips stay in the Catalogue)
      if (!hasWork(sh)) { void askConfirm({ title: `Delete ${n.title || NODE_LABEL[n.type]}?`, okLabel: 'Delete', danger: true, text: 'Its edges and its empty shot go with it.' }).then((ok) => { if (ok) void sy().deleteNode(n.id, true) }); return }
      void askConfirmCheck({ title: `Delete ${n.title || NODE_LABEL[n.type]}?`, okLabel: 'Delete', danger: true, text: 'Its edges go with it; its shot stays, as a Shot node of its own.', check: `Delete its shot ${sh.name} too (its frames and clips stay in the Catalogue)` })
        .then((r) => { if (r) void sy().deleteNode(n.id, r.checked) }) } },
  // D90 (B3): an edge goes by its right-click menu or Delete / Backspace on the canvas while it is selected (nodes keep their confirm)
  { id: 'story.flow.deleteEdge', scope: 'story', label: 'Delete the connection', icon: Unlink, keys: 'Delete', alt: ['Backspace'], placement: ['context'], when: () => !!sy().edge && !sy().play,
    run: () => { const e = sy().edge; if (!e) return; const to = sy().flowGraph?.edges.find((x) => x.from === e.from && x.port === e.port)?.to
      void sy().disconnect(e.from, e.port)
      if (to) useSession.getState().toast('Connection deleted', 'info', () => void sy().connect(e.from, e.port, to)) } },
  { id: 'story.flow.duplicate', scope: 'story', label: 'Duplicate node', icon: Copy, placement: ['inspector', 'context'], when: () => !!node() && !sy().play, run: () => { const n = node(); if (n) void sy().duplicateNode(n.id) } },
  // D125 (#4): a Dialogue or Shot node is made with its shot; one made before, or unbound since, gets its own here (named after it)
  { id: 'story.flow.newShot', scope: 'story', label: 'Make its shot', icon: Plus, hint: 'a shot owned by this node, named after it', placement: ['inspector', 'context'], when: () => visual() && !node()?.shot_id && !sy().play,
    run: () => { const n = node(); if (n) void sy().spawnShot(n.id, n.title || NODE_LABEL[n.type]) } },
  // D125 (#7, S7): the place carried to the nodes after this one that have none (stopping at a node with a place of its own)
  { id: 'story.flow.placeForward', scope: 'story', label: 'Also for the nodes after it', icon: CornerDownRight, placement: ['inspector', 'context'],
    hint: 'the nodes after this one without a place take it, up to the next node that has one', when: () => !!node()?.place_id && placeTargets().length > 0 && !sy().play,
    run: () => { const n = node(); if (!n?.place_id) return; const ids = placeTargets(); ids.forEach((id) => void sy().patchNode(id, { place_id: n.place_id }))
      useSession.getState().toast(`${ids.length} node${ids.length === 1 ? '' : 's'} at the same place`, 'info') } },
  { id: 'story.flow.unbind', scope: 'story', label: 'Move its shot to a node of its own', icon: Unlink, placement: ['inspector', 'context'],
    hint: 'the shot leaves for a Shot node beside this one (outside the routes); this node gets a fresh shot',
    when: () => { const n = node(); const s = nodeShot(); return !!n && !!s && !bareNode(n, sy().flowGraph) && hasWork(s) && !sy().play }, run: () => { const n = node(); if (n) void sy().unbindShot(n.id) } },
  // RC2c (proto01_animate 31 §3a): scene groups — a frame around Shots; O2: New Shot from this Shot, a sibling in the scene
  { id: 'story.scene.make', scope: 'story', label: 'Make a scene of it…', icon: Group, placement: ['inspector', 'context'],
    hint: 'a frame around this node (and the nodes selected with it — Ctrl-click or Shift-drag): a dialogue in shot / reverse-shot is several Shots, one scene; Episode grades it as one',
    when: () => !!node() && !sy().play,
    run: () => { const n = node(); if (!n) return; const ids = sceneTargets()
      const place = n.place_id ? sy().profiles.find((p) => p.id === n.place_id)?.name : undefined
      void askText({ title: ids.length > 1 ? `A scene of ${ids.length} nodes` : 'A scene', text: 'Its name, shown on its frame in the Flow.', initial: place ?? n.title })
        .then((v) => { if (v?.trim()) void sy().makeScene(v.trim(), ids) }) } },
  { id: 'story.scene.leave', scope: 'story', label: 'Take it out of its scene', icon: Ungroup, placement: ['inspector', 'context'],
    when: () => !!sceneOf(node()) && !sy().play, run: () => { const n = node(); const s = sceneOf(n); if (n && s) void sy().sceneMembers(s.id, [], sceneTargets()) } },
  { id: 'story.scene.rename', scope: 'story', label: 'Rename the scene…', icon: Pencil, placement: ['inspector', 'context'], when: () => !!pickedScene() && !sy().play,
    run: () => { const s = pickedScene(); if (s) void askText({ title: 'Rename the scene', initial: s.name }).then((v) => { if (v?.trim() && v.trim() !== s.name) void sy().renameScene(s.id, v.trim()) }) } },
  { id: 'story.scene.dissolve', scope: 'story', label: 'Dissolve the scene (its nodes stay)', icon: Ungroup, placement: ['inspector', 'context'], when: () => !!pickedScene() && !sy().play,
    run: () => { const s = pickedScene(); if (s) void sy().dissolveScene(s.id) } },
  // RC2e (06 O2): Shot templates — saved from a Shot into World › Presets, used beside a node or where the Flow was right-clicked
  { id: 'story.flow.saveTemplate', scope: 'story', label: 'Save as a template…', icon: BookPlus, placement: ['inspector', 'context'],
    hint: "its kind, its lines (the words), its line, its route and its camera with its keys — World › Presets › Shot templates keeps it",
    when: () => visual() && !!node()?.shot_id && !sy().play,
    run: () => { const n = node(); if (n) void askText({ title: 'Save as a Shot template', text: 'Its name in World › Presets.', initial: n.title }).then((v) => { if (v?.trim()) void sy().saveTemplate(n.id, v.trim()) }) } },
  { id: 'story.template.use', scope: 'story', label: 'New Shot from it', icon: CopyPlus, placement: ['inspector', 'context'],
    hint: 'a node of its kind with its lines on its route — beside the node picked in the Flow (its scene, a camera on its stage), else at the Flow\'s centre',
    when: () => sy().selected?.kind === 'template', run: () => { const id = sy().selected?.id; if (id) void sy().useTemplate(id, sy().nodeId, null) } },
  { id: 'story.template.rename', scope: 'story', label: 'Rename the template…', icon: Pencil, placement: ['inspector', 'context'], when: () => sy().selected?.kind === 'template',
    run: () => { const t = sy().shotTemplates.find((x) => x.id === sy().selected?.id); if (t) void askText({ title: 'Rename the template', initial: t.name }).then((v) => { if (v?.trim() && v.trim() !== t.name) void sy().renameTemplate(t.id, v.trim()) }) } },
  { id: 'story.template.delete', scope: 'story', label: 'Delete the template', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => sy().selected?.kind === 'template',
    run: () => { const t = sy().shotTemplates.find((x) => x.id === sy().selected?.id); if (t) void askConfirm({ title: `Delete the template ${t.name}?`, okLabel: 'Delete', danger: true, text: 'The Shots made from it stay.' }).then((ok) => { if (ok) void sy().deleteTemplate(t.id) }) } },
  // RC2f (06 O3): within a scene a Shot's parts are linked — the stage shared, the cast its scene's; Make independent keeps one for itself
  { id: 'story.flow.ownCast', scope: 'story', label: "Make its cast independent", icon: Unlink, placement: ['inspector', 'context'],
    hint: "it keeps the versions its speakers wear now as its own; the scene's other Shots go on sharing theirs",
    when: () => { const n = node(); return !!sceneOf(n) && !n!.own.includes('cast') && !sy().play }, run: () => { const n = node(); if (n) void sy().ownCast(n.id, true) } },
  { id: 'story.flow.linkCast', scope: 'story', label: "Use the scene's cast", icon: Link, placement: ['inspector', 'context'],
    hint: "its own versions go; it wears the ones its scene's Shots share", when: () => { const n = node(); return !!sceneOf(n) && n!.own.includes('cast') && !sy().play },
    run: () => { const n = node(); if (n) void sy().ownCast(n.id, false) } },
  { id: 'story.shot.ownStage', scope: 'story', label: 'Make its stage independent', icon: Unlink, placement: ['inspector', 'context'],
    hint: "a copy of the stage it shares with other Shots — the set, the props, the lights, the figures, the cameras and keys — for this version alone",
    when: () => { const s = shot(); const v = shotVersion(); return !!s && !!v && v.state === 'open' && !!v.stage_id && stageUsers(s.id, v.stage_id).length > 0 },
    run: () => { const s = shot(); const v = shotVersion(); if (s && v) void sy().ownStage(s.id, v.id) } },
  { id: 'story.flow.sibling', scope: 'story', label: 'New Shot from this Shot', icon: CopyPlus, placement: ['inspector', 'context'],
    hint: 'a sibling in its scene (one is made around the two when it has none): the stage, the place, the pinned cast and the board shared; the lines, a camera of its own and the route copied to change',
    when: () => visual() && !!node()?.shot_id && !sy().play, run: () => { const n = node(); if (n) void sy().newShotFrom(n.id) } },
  // RC1 (proto01_animate 28): a node's shot as its recipe graph, in place of the canvas; the same graph in Animate
  { id: 'story.flow.recipe', scope: 'story', label: 'Open its recipe', icon: Workflow, hint: "the shot's recipe as a graph, here in place of the canvas — what it is made of, what is stale",
    placement: ['inspector', 'context'], when: () => !!node()?.shot_id && !sy().play, run: () => { const n = node(); if (n) sy().setFlowRecipe(n.id) } },
  { id: 'story.flow.recipeClose', scope: 'story', label: 'The Flow', icon: ArrowLeft, hint: 'back to the canvas', placement: ['strip'], when: () => !!sy().flowRecipe, run: () => sy().setFlowRecipe(null) },
  { id: 'story.shot.graphInAnimate', scope: 'story', label: 'Open the graph in Animate', icon: Workflow, hint: "Animate's Graph on this shot (its For chip set): a node opens where it is made",
    placement: ['strip', 'inspector', 'context'], when: () => !!shot() && !!shotVersion(),
    run: () => { const s = shot(); const v = shotVersion(); if (!s || !v) return
      useMakeFor.getState().set('animate', forShot(s, v)); useSession.getState().setUi({ graph: true }); navigate({ suite: 'animate' }) } },
  { id: 'story.flow.openShot', scope: 'story', label: 'Open the shot', icon: Link, placement: ['inspector', 'context'], when: () => !!node()?.shot_id,
    run: () => { const n = node(); if (!n?.shot_id) return; const sid = n.shot_id, v = n.shot_version; setRailTab('story', 'shots'); sy().selectShot(sid, v) } },
  // D90 (02 §4.2, §5): a node's board (an album group) and Make ▸ for its shot (the board's images as Generate's references)
  { id: 'story.flow.makeFrame', scope: 'story', label: 'Make frame in Image', icon: ImagePlus, placement: ['inspector', 'context'], when: () => projectOpen() && !!nodeTarget() && !sy().play,
    run: () => { const s = nodeShot(); const v = nodeTarget(); const n = node(); if (s && v && n) void makeFrameFor(s, v, n.id) } },
  { id: 'story.flow.makeClip', scope: 'story', label: 'Make clip in Animate', icon: Film, placement: ['inspector', 'context'], when: () => projectOpen() && !!nodeTarget() && !sy().play,
    run: () => { const s = nodeShot(); const v = nodeTarget(); const n = node(); if (s && v && n) void makeClipFor(s, v, n.id) } },
  { id: 'story.flow.openBoard', scope: 'story', label: 'Open the board in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!board(),
    run: () => { const g = node()?.board_group_id; if (g) openGroupPage(g) } },
  { id: 'story.flow.clearBoard', scope: 'story', label: 'Remove the board (the group stays)', icon: ImageOff, placement: ['inspector', 'context'], when: () => !!node()?.board_group_id && !sy().play,
    run: () => { const n = node(); if (!n?.board_group_id) return; const was = n.board_group_id
      void sy().patchNode(n.id, { board_group_id: null })
      useSession.getState().toast('Board removed from the node', 'info', () => void sy().patchNode(n.id, { board_group_id: was })) } },
  // D90 (01 §11.2): one line's voice, the 🎙 beside it (the line is the item it was pressed on)
  { id: 'story.flow.voiceLine', scope: 'story', label: 'Voice this line', icon: Mic, placement: ['inspector'], hint: 'its speaker\'s voice, else the voice picked under the lines', when: lineVoicable,
    run: () => { const l = storyItem.line; storyItem.line = undefined; if (l) void sy().voiceLine(l.node, l.index) } },
  { id: 'story.flow.voiceAll', scope: 'story', label: 'Voice all lines', icon: Volume2, placement: ['inspector', 'context'],
    when: () => hasLines(node()) && !!useSession.getState().capabilities?.voice?.available && !sy().play,
    run: () => { const n = node(); if (n) void sy().voiceNode(n.id) } },
  { id: 'story.cast.newVoice', scope: 'story', label: 'New voice…', icon: Mic, placement: ['inspector'], when: () => !!profile() && !!useSession.getState().capabilities?.voice?.available,
    run: () => sy().setVoiceForm(!sy().voiceForm) },
  { id: 'story.cast.deleteVoice', scope: 'story', label: 'Delete the voice', icon: Trash2, placement: ['inspector'], danger: true, when: () => !!profile()?.voice_id,
    run: () => { const p = profile(); if (!p?.voice_id) return; const vid = p.voice_id; const v = sy().voices.find((x) => x.id === vid)
      void askConfirm({ title: `Delete the voice ${v?.name ?? vid}?`, okLabel: 'Delete', danger: true, text: 'The record goes; its spoken lines stay in the Catalogue; every character that had it loses it.' }).then((ok) => { if (ok) void sy().deleteVoice(vid) }) } },
  { id: 'story.flow.validate', scope: 'story', label: 'Validate', icon: ListChecks, placement: ['strip', 'context'], when: () => !!useSession.getState().project?.open, run: () => void sy().validate() },
  { id: 'story.flow.play', scope: 'story', label: 'Play', icon: Play, keys: 'P', placement: ['strip', 'context'], when: () => !!sy().flowGraph && !sy().play, run: () => sy().playStart() },
  // D90 (01 §11.2): play mode's own controls
  { id: 'story.flow.next', scope: 'story', label: 'Next ▸', icon: Play, placement: ['toolbar'], hint: 'play mode: on to the next node (a Choice asks with its options)', when: () => { const p = playing(); return !!p && !p.ended && (p.node ? sy().flowNodes[p.node]?.type : null) !== 'choice' }, run: () => sy().playNext() },
  { id: 'story.flow.restart', scope: 'story', label: 'Restart', icon: RotateCcw, placement: ['toolbar'], hint: 'play mode: from the Start node again', when: () => !!playing(), run: () => sy().playStart() },
  { id: 'story.flow.stop', scope: 'story', label: 'Stop playing', icon: Square, placement: ['strip'], when: () => !!sy().play, run: () => sy().playStop() },
  { id: 'story.flow.fit', scope: 'story', label: 'Fit the graph', icon: Maximize, keys: 'F', placement: ['strip', 'context'], when: () => !!sy().flowGraph && !sy().play, run: () => flowView.fit?.() },
  // D125 (S4, S8): the verbs that work on the episode
  { id: 'story.world.flowFromSpine', scope: 'story', label: 'Make the Flow from the spine…', icon: Workflow, hint: "a Start, then one Shot node per beat not yet made — each with its shot — in a row, connected in the spine's order",
    placement: ['panel', 'strip', 'context'], when: () => projectOpen() && !!sy().world?.spine.length && !sy().play && (!sy().flowLoaded || spineTodo(sy().world!.spine, Object.values(sy().flowNodes)).length > 0),
    run: async () => {
      if (!sy().flowLoaded) await sy().loadFlow()
      const n = spineTodo(sy().world?.spine ?? [], Object.values(sy().flowNodes)).length
      if (!n) { useSession.getState().toast('Every beat of the spine has its node', 'info'); return }
      const ok = await askConfirm({ title: `Make ${n} Shot node${n === 1 ? '' : 's'} from the spine?`, okLabel: 'Make them',
        text: `${sy().flowGraph?.start ? '' : 'A Start node first, then '}one Shot node per beat not yet made, each with its shot, in a row and connected in the spine's order.` })
      if (!ok) return
      const made = await sy().flowFromSpine()
      if (made) { useSession.getState().toast(`${made} Shot node${made === 1 ? '' : 's'} made from the spine`, 'success'); openStory('flow') }
    } },
  { id: 'story.flow.voiceEpisode', scope: 'story', label: 'Voice all lines', icon: Volume2, hint: "every Dialogue line of the episode not voiced yet or changed since — each speaker's voice, else the one picked under the lines",
    placement: ['strip', 'panel', 'context'], when: () => linesToVoice(Object.values(sy().flowNodes)) > 0 && !!useSession.getState().capabilities?.voice?.available && !sy().play,
    run: () => void sy().voiceEpisode() },
  { id: 'story.world.beatToNode', scope: 'story', label: 'Make a Flow node from this beat', icon: GitBranch, placement: ['inspector', 'context'], when: selBeat,
    run: () => { const s = selected(); if (s?.kind === 'beat') void sy().nodeFromBeat(s.id) } },
  // D92: subjects are Cast characters — Generate's Tree prompt with a subject card linked to the profile (its reference set and LoRA follow)
  { id: 'story.cast.useAsSubject', scope: 'story', label: 'Use as a subject in Image', icon: UserRoundPlus, placement: ['inspector', 'context'], when: () => !!profile() && profile()!.cls !== 'place',
    run: () => { const p = profile(); if (!p) return
      void import('../generate/generateStore').then((g) => {
        g.useGenerate.getState().useAsSubject(p); navigate({ suite: 'generate', tab: 'prompt' })
        useSession.getState().toast(`${p.name} is a subject in Image's Tree prompt — its reference set${version()?.lora ? ' and LoRA' : ''} follow`, 'info') }) } },
  { id: 'story.cast.openInStory', scope: 'story', label: 'Open in Story · Cast', icon: Users, placement: ['context'], when: () => !!profile(),
    run: () => { const p = profile(); if (p) revealClass(p.cls); navigate({ suite: 'story', tab: 'cast' }) } },
  { id: 'story.cast.delete', scope: 'story', label: 'Delete profile', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!profile(),
    run: () => { const p = profile(); if (!p) return
      void askConfirm({ title: `Delete ${p.name}?`, okLabel: 'Delete', danger: true, text: 'The profile record goes; its reference sets and images stay in the album (no longer final). @mentions of it stop resolving.' }).then((ok) => { if (ok) void sy().deleteProfile() }) } },
]
registerCommands(cmds)

/** The right-click menu of a row in the World editor: the row is selected first, so the Inspector shows it too. */
/** The right-click menu of a Cast profile row (the profile is selected first). D90 (01 §11.3): the training and new-profile verbs too. */
export const profileMenu = (): MenuItem[] => [{ cmd: 'story.cast.useAsSubject' }, sep, { cmd: 'story.cast.bench' }, { cmd: 'cast.skeleton.open' }, { cmd: 'cast.shell.make' }, { cmd: 'story.cast.lineup' }, sep, { cmd: 'story.cast.expand' }, { cmd: 'story.cast.newVersion' }, { cmd: 'story.cast.lock' }, sep, { cmd: 'story.cast.openGroup' }, { cmd: 'story.cast.openCandidates' }, sep,
  { cmd: 'story.cast.train' }, { cmd: 'story.cast.useLora' }, { cmd: 'story.cast.checkLora' }, { cmd: 'story.cast.deleteLora' }, sep, { cmd: 'story.cast.new' }, { cmd: 'story.cast.newPlace' }, { cmd: 'story.cast.newProp' }, sep, { cmd: 'story.cast.delete' }]
export function rowMenu(kind: NonNullable<ReturnType<typeof selected>>['kind'], id: string) {
  useStory.getState().select({ kind, id })
  const items: ({ cmd: string; label?: string } | 'sep')[] = []
  if (kind === 'style') items.push({ cmd: 'story.world.styleSample' }, { cmd: 'story.world.openStyleGroup' }, 'sep', { cmd: 'story.world.defaultStyle' })
  if (kind === 'beat') items.push({ cmd: 'story.world.beatUp' }, { cmd: 'story.world.beatDown' }, { cmd: 'story.world.beatToNode' }, { cmd: 'story.world.flowFromSpine' })
  if (kind === 'entry') items.push({ cmd: 'story.world.entryPicture' }, { cmd: 'story.world.entryEarlier' }, { cmd: 'story.world.entryLater' }, 'sep')   // D92
  if (kind === 'panel') { items.push({ cmd: 'story.world.applyPanel' }, { cmd: 'story.world.renamePanel' }, 'sep', { cmd: 'story.world.remove', label: 'Delete…' }); return items }
  items.push(kind === 'entry' ? { cmd: 'story.world.remove', label: 'Remove from the library' } : { cmd: 'story.world.remove' }, 'sep',
    kind === 'style' ? { cmd: 'story.world.addStyle' } : kind === 'beat' ? { cmd: 'story.world.addBeat' } : kind === 'entry' ? { cmd: 'story.world.addEntry' } : { cmd: 'story.world.addVariable' })   // D90 (01 §11.3): Add … where its row is
  return items
}

/** The right-click menu of a Flow edge (the edge is selected first). */
export function edgeMenu(): { cmd: string }[] { return [{ cmd: 'story.flow.deleteEdge' }] }

/** The right-click menu of a Flow node (the node is selected first). */
export function nodeMenu(): MenuItem[] {
  const n = node()
  const into = sy().scenes.filter((s) => s.id !== n?.scene_id)                                      // RC2c: join a scene by its name
  return [{ cmd: 'story.flow.makeFrame' }, { cmd: 'story.flow.makeClip' }, sepItem, { cmd: 'story.flow.newShot' }, { cmd: 'story.flow.openShot' }, { cmd: 'story.flow.recipe' }, { cmd: 'story.flow.unbind' }, { cmd: 'story.flow.placeForward' }, sepItem,
    { cmd: 'story.flow.sibling' }, { cmd: 'story.scene.make' }, ...(into.length && n ? [{ label: 'Into the scene', icon: Group, items: into.map((s) => ({ label: s.name, run: () => void sy().sceneMembers(s.id, sceneTargets(), []) })) }] : []),
    { cmd: 'story.scene.leave' }, { cmd: 'story.flow.ownCast' }, { cmd: 'story.flow.linkCast' }, { cmd: 'story.flow.saveTemplate' }, ...templateItems(n?.id ?? null, null), sepItem,
    { cmd: 'story.flow.openBoard' }, { cmd: 'story.flow.clearBoard' }, sepItem, { cmd: 'story.flow.voiceAll' }, sepItem, { cmd: 'story.flow.duplicate' }, { cmd: 'story.flow.delete' }]
}
/** RC2e: *New Shot from a template ▸* — beside a node (its scene, its stage) or at a point of the Flow. */
export function templateItems(near: string | null, at: { x: number; y: number } | null): MenuItem[] {
  const ts = sy().shotTemplates
  return ts.length ? [{ label: 'New Shot from a template', icon: CopyPlus, items: ts.map((t) => ({ label: t.name, run: () => void sy().useTemplate(t.id, near, at) })) }] : []
}
/** RC2c: a scene frame's right-click (the frame is picked first). */
export function sceneMenu(): MenuItem[] {
  return [{ cmd: 'story.scene.rename' }, { cmd: 'story.scene.dissolve' }]
}

/** D90 (02 §5): the entries of "Make frame ▸" and "Make clip ▸" (the shot board, the Strip, the Inspector, the shot row's menu). */
export const makeFrameItems = (): MenuItem[] => [{ cmd: 'story.shot.makeFrame', label: 'in Image' }, { cmd: 'story.shot.makeFrameStage', label: 'from the stage (the camera, Image)' }]
export const makeClipItems = (): MenuItem[] => [{ cmd: 'story.shot.makeClip', label: 'in Animate' }, { cmd: 'story.shot.makeClipStage', label: 'on the stage (the camera, Animate)' }, { cmd: 'story.shot.makeFinal', label: 'the final shot (the camera, Animate)' }, sep, { cmd: 'story.shot.lipsync' }, sep, { cmd: 'story.shot.linkStage' }, { cmd: 'story.shot.blockOnStage' }]
/** The right-click menu of a shot row (the shot is selected first). */
export function shotMenu(): MenuItem[] {
  return [{ label: 'Make frame', icon: ImagePlus, items: makeFrameItems() }, { label: 'Make clip', icon: Film, items: makeClipItems() }, sep,
    { cmd: 'story.shot.runStale' }, { cmd: 'story.shot.graphInAnimate' }, { cmd: 'story.shot.finalize' }, { cmd: 'story.shot.newVersion' }, sep, { cmd: 'story.shot.openStage' }, { cmd: 'story.shot.linkStage' }, { cmd: 'story.shot.blockOnStage' }, { cmd: 'story.shot.ownStage' }, { cmd: 'story.shot.openAnimate' }, sep, { cmd: 'story.shot.release' }, { cmd: 'story.shot.delete' }, sep, { cmd: 'story.shot.new' }]
}
const sepItem = { sep: true } as const
