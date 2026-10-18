// 17 (D85): the Story suite's verbs — every one has a mouse home (the panel's buttons, the editor rows' tools, the Inspector, right-click
// menus) per D32; Delete and the arrows are accelerators. SY1 adds the Cast tab's verbs (new profile, expand, curate, lock, copy, open).
import { ArrowDown, ArrowLeft, ArrowUp, BookOpen, BookPlus, ChevronLeft, ChevronRight, Pencil, UserRoundPlus, Users, Check, CircleHelp, Clapperboard, Copy, CornerDownRight, Film, FolderOpen, GitBranch, GitFork, GraduationCap, ImageOff, ImagePlus, ImageUp, Link, ListChecks, ListPlus, Lock, MapPinPlus, Maximize, MessageSquare, Mic, PackagePlus, Palette, PersonStanding, Play, Plus, RotateCcw, ScanFace, Shapes, Sparkles, Square, Star, StickyNote, ToggleLeft, Trash2, Unlink, UserPlus, Volume2, Wand2, X, Zap } from 'lucide-react'
import { registerCommands, runCommand, sep, type Command, type MenuItem } from '../../frame/commands'
import { goBack, useMakeFor } from '../../store/origin'
import { askConfirm, askText, useSession } from '../../store/session'
import { useAlbum } from '../catalogue/albumStore'
import { CLASS_LABEL, latestTrainJob, sy, ttsJobFor, useStory, type ProfileClass } from './storyStore'
import { makeClipFor, makeFrameFor, makeTarget, speakersOf } from './makeFor'
import { runStale, staleOf } from './runStale'
import type { Profile, Shot } from '../../api/types'
import { findNode, pickSampleModel, sampleJob, sampleRecipe, styleGroupName } from './styleSamples'
import { useLibrary } from './libraryStore'
import { FIELD_LABEL, type FieldKey } from '../generate/fieldPresets'
import { needsPicture, swatchJob, useSwatches } from '../generate/swatches'

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
  void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'world'); sy().setSection(section); useSession.getState().setSuite('story') })
}
const style = () => { const s = selected(); return s?.kind === 'style' ? sy().world?.styles.find((x) => x.id === s.id) : undefined }
const sampleModel = () => { const ss = useSession.getState(); return pickSampleModel(ss.capabilities, ss.settings?.samples?.model_id) }   // D91: Settings › Samples' model, else the default
const profile = () => sy().profile()
const version = () => sy().version()
const openVersion = () => version()?.state === 'open'
const animRefable = () => { const c = profile()?.cls; return c === 'character' || c === 'prop' }   // CA0: a place has none
const picked = () => sy().picked
const trainJob = () => { const p = profile(); const v = version(); return p && v ? latestTrainJob(useSession.getState().jobs, p.id, v.id) : undefined }
const trainCaps = () => useSession.getState().capabilities?.train
const refsCount = () => Object.keys(sy().refPage?.assets ?? {}).length
const shot = () => sy().shot()
const shotVersion = () => sy().shotVersion()
const node = () => sy().node()
const visual = () => { const n = node(); return !!n && (n.type === 'dialogue' || n.type === 'shot') }
const projectOpen = () => !!useSession.getState().project?.open
/** D90 (02 §5): the open version Make ▸ works for — the shown one (Shots), or the one a node pins (Flow); null when final (a retake first). */
const shotTarget = () => makeTarget(shot(), shotVersion()?.id)
const nodeShot = () => { const n = node(); return n?.shot_id ? sy().shots.find((x) => x.id === n.shot_id) : undefined }
const nodeTarget = () => makeTarget(nodeShot(), node()?.shot_version)
const board = () => { const g = node()?.board_group_id; return g ? findNode(useAlbum.getState().tree, g) : null }
/** Open a stage at a camera (Shots' "Open in Stage" and the Stage routes of Make ▸). D93 (C8): `speakers` — Make frame ▸ in Stage binds the
 *  shot's speakers to the stage's figures in screen order when the counts match, else says how to bind them. */
function openStageAt(stageId: string, cam: string | null, speakers?: (Profile & { version?: string | null })[], where: 'image' | 'animate' = 'animate'): void {
  // D95 (AN1): a still from the stage is made in Image (From a stage); the stage itself and its clips in Animate (Clay, the stage card)
  if (where === 'image') { void import('../generate/generateStore').then((g) => g.useGenerate.setState({ source: 'stage' })); useSession.getState().setSuite('generate') }
  else { void import('../animate/routeStore').then((r) => r.useAnimRoute.getState().set('stage')); useSession.getState().setSuite('stage') }
  void import('../stage/stageStore').then((m) => { const st = m.useStage.getState(); const go = st.current?.id === stageId ? Promise.resolve() : st.open(stageId); void go.then(() => {
    if (cam) m.useStage.getState().setActiveCamera(cam)
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
const NODE_ICON = { start: Play, hub: GitFork, dialogue: MessageSquare, choice: ListChecks, condition: CircleHelp, action: Zap, shot: Clapperboard, jump: CornerDownRight, comment: StickyNote } as const
const NODE_LABEL = { start: 'Start', hub: 'Hub', dialogue: 'Dialogue', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' } as const
/** The viewport registers its fit, its centre and the screen → flow mapping (D90 B11) in flow coordinates (the canvas is not a store). */
/** D90 (01 §11.2): the item a per-item command acts on — the take or the line whose button or menu ran it (commands take no
 *  arguments; the button sets this first). A run clears it, so the palette never acts on a stale one. */
export const storyItem: { take?: { kind: 'image' | 'clip'; id: string }; line?: { node: string; index: number }; field?: string } = {}   // D92: a library field's Add
/** Run `id` on an item (a take card's ✓ use, a line's 🎙). */
export function runOnItem(item: Partial<typeof storyItem>, id: string): boolean {
  Object.assign(storyItem, item)
  try { return runCommand(id) } finally { for (const k of Object.keys(item) as (keyof typeof storyItem)[]) delete storyItem[k] }
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
    await ss.submitJob(sampleRecipe(id, model.id, first, ss.settings?.samples?.style_prompt, model.style_px), {   // D90: the scene of Settings › Samples; D91: its model
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

/** A group page in the active Catalogue pane (Story's Catalogue workspace). */
function openGroupPage(gid: string): void {
  useSession.getState().setSuite('catalogue')
  void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: gid }) })
}

export async function newProfile(cls: ProfileClass = 'character', hero: string | null = null): Promise<void> {
  const name = await askText({ title: `New ${CLASS_LABEL[cls]}`, text: hero ? 'The image becomes the hero and the cover of a new reference set; @name mentions it in prompts.' : 'An empty profile: give it a hero from the Catalogue ("Make a character…" on a tile) before expanding.', placeholder: `${CLASS_LABEL[cls]} name` })
  if (name?.trim()) await sy().createProfile(name.trim(), cls, hero)
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
    run: () => { void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'world'); sy().setSection('styles'); useSession.getState().setSuite('story') }) } },
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
    run: () => void panelPreset().then((x) => { if (!x?.p) return; x.g.applyPreset(x.p.name); useSession.getState().setSuite('generate') }) },
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
  { id: 'story.cast.expand', scope: 'story', label: 'Expand…', icon: Sparkles, keys: 'Ctrl+Enter', placement: ['panel', 'inspector', 'context'],
    when: () => openVersion() && !!version()?.hero_asset_id && !!useSession.getState().capabilities?.story?.model_id && !sy().expanding,
    run: () => void askExpand(sy().world ? 'full' : 'full', 1, 'draft') },
  { id: 'story.cast.keep', scope: 'story', label: 'Add to the reference set', icon: Check, keys: 'K', placement: ['context', 'inspector', 'toolbar'], when: () => openVersion() && picked().length > 0,
    run: () => void sy().curate(picked(), 'keep') },
  { id: 'story.cast.reject', scope: 'story', label: 'Reject', icon: X, keys: 'X', placement: ['context', 'inspector', 'toolbar'], when: () => openVersion() && picked().length > 0,
    run: () => void sy().curate(picked(), 'reject') },
  { id: 'story.cast.setHero', scope: 'story', label: 'Make it the hero', icon: ImageUp, placement: ['context', 'inspector'], when: () => openVersion() && picked().length === 1,
    run: () => void sy().setHero(picked()[0]) },
  // CA0 (01 step 2, §10): the animation reference — characters (front, back) and props (front, a three-quarter view); a final version takes one too
  { id: 'story.cast.makeAnimRef', scope: 'story', label: 'Make an animation reference', icon: PersonStanding, hint: 'full body, A-pose, 16:9, plain ground — two candidates from the sheet and references',
    placement: ['panel', 'inspector', 'context'], when: () => animRefable() && !!useSession.getState().capabilities?.story?.model_id, run: () => void sy().makeAnimRef('front') },
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
    run: () => { const v = shotVersion(); if (v?.stage_id) openStageAt(v.stage_id, v.camera_id) } },
  // D90 (02 §5): Make frame ▸ / Make clip ▸ — the maker opens with the For chip and its results come back as this version's takes; the
  // Stage routes open the version's camera (its results already become takes of the shots pointing at it)
  { id: 'story.shot.makeFrame', scope: 'story', label: 'Make frame in Image', icon: ImagePlus, placement: ['strip', 'inspector', 'context'], when: () => projectOpen() && !!shotTarget(),
    run: () => { const s = shot(); const v = shotTarget(); if (s && v) void makeFrameFor(s, v) } },
  { id: 'story.shot.makeFrameStage', scope: 'story', label: 'Make frame from the stage (Image)', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotTarget()?.stage_id,
    run: () => { const v = shotTarget(); if (v?.stage_id) openStageAt(v.stage_id, v.camera_id, shotSpeakers(shot()), 'image') } },
  { id: 'story.shot.makeClip', scope: 'story', label: 'Make clip in Animate', icon: Film, placement: ['strip', 'inspector', 'context'], when: () => projectOpen() && !!shotTarget(),
    run: () => { const s = shot(); const v = shotTarget(); if (s && v) void makeClipFor(s, v) } },
  { id: 'story.shot.makeClipStage', scope: 'story', label: 'Make clip on the stage (Animate)', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotTarget()?.stage_id,
    run: () => { const v = shotTarget(); if (v?.stage_id) openStageAt(v.stage_id, v.camera_id, shotSpeakers(shot())) } },   // D95 (AN1, UX0 #21): the speakers bound for the clip too
  // the For chip's verbs in the makers' Panels (D32: a command each)
  { id: 'gen.for.back', scope: 'generate', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], when: () => !!useMakeFor.getState().generate, run: () => goBack('generate') },
  { id: 'gen.for.clear', scope: 'generate', label: 'Stop making for the shot (results stay in the Catalogue only)', icon: X, placement: ['panel'], when: () => !!useMakeFor.getState().generate,
    run: () => useMakeFor.getState().set('generate', null) },
  // RC0 (D96): Run stale — the shown version in Story, the For chip's version in Animate (the recipe list under it shows the button)
  { id: 'story.shot.runStale', scope: 'story', label: 'Run stale steps…', icon: RotateCcw, hint: 'the plan and its cost first; the results become the frame and clip', placement: ['inspector', 'context'],
    when: () => { const s = shot(); const v = shotVersion(); return !!s && v?.state === 'open' && staleOf(s.id, v.id) > 0 }, run: () => { const s = shot(); const v = shotVersion(); if (s && v) void runStale(s.id, v.id) } },
  { id: 'anim.for.runStale', scope: 'animate', label: 'Run stale steps…', icon: RotateCcw, hint: 'the plan and its cost first; the results become the frame and clip', placement: ['panel'],
    when: () => { const f = useMakeFor.getState().animate; return !!f && staleOf(f.shot_id, f.version) > 0 }, run: () => { const f = useMakeFor.getState().animate; if (f) void runStale(f.shot_id, f.version) } },
  { id: 'anim.for.back', scope: 'animate', label: 'Back to the shot', icon: ArrowLeft, placement: ['panel'], when: () => !!useMakeFor.getState().animate, run: () => goBack('animate') },
  { id: 'anim.for.clear', scope: 'animate', label: 'Stop making for the shot (clips stay in the Catalogue only)', icon: X, placement: ['panel'], when: () => !!useMakeFor.getState().animate,
    run: () => useMakeFor.getState().set('animate', null) },
  { id: 'story.shot.openAnimate', scope: 'story', label: 'Open in Animate', icon: Film, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion()?.clip_id,
    run: () => { const v = shotVersion(); if (!v?.clip_id) return; const cid = v.clip_id
      useSession.getState().setSuite('animate')
      void import('../animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(cid)) }) } },
  { id: 'story.shot.release', scope: 'story', label: 'Unbind from its node', icon: Unlink, placement: ['inspector', 'context'], when: () => !!shot()?.owner_node,
    run: () => void sy().patchShot({ owner_node: null }) },
  { id: 'story.shot.delete', scope: 'story', label: 'Delete shot', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!shot(),
    run: () => { const s = shot(); if (!s) return
      void askConfirm({ title: `Delete ${s.name}?`, okLabel: 'Delete', danger: true, text: 'The shot record goes; its frames and clips stay in the Catalogue. A Flow node bound to it loses its shot.' }).then((ok) => { if (ok) void sy().deleteShot() }) } },
  // SY3 · Flow
  ...(Object.keys(NODE_ICON) as (keyof typeof NODE_ICON)[]).map((t): Command => ({
    id: `story.flow.add.${t}`, scope: 'story', label: `Add ${NODE_LABEL[t]}`, icon: NODE_ICON[t], placement: ['strip', 'context'], when: () => !!useSession.getState().project?.open && !sy().play,
    run: () => { void sy().addNode(t) },
  })),
  { id: 'story.flow.delete', scope: 'story', label: 'Delete node', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!node() && !sy().play,
    run: () => { const n = node(); if (!n) return
      void askConfirm({ title: `Delete ${n.title || NODE_LABEL[n.type]}?`, okLabel: 'Delete', danger: true, text: n.shot_id ? 'Its edges go with it; its shot is released (not deleted).' : 'Its edges go with it.' }).then((ok) => { if (ok) void sy().deleteNode(n.id) }) } },
  // D90 (B3): an edge goes by its right-click menu or Delete / Backspace on the canvas while it is selected (nodes keep their confirm)
  { id: 'story.flow.deleteEdge', scope: 'story', label: 'Delete the connection', icon: Unlink, keys: 'Delete', alt: ['Backspace'], placement: ['context'], when: () => !!sy().edge && !sy().play,
    run: () => { const e = sy().edge; if (!e) return; const to = sy().flowGraph?.edges.find((x) => x.from === e.from && x.port === e.port)?.to
      void sy().disconnect(e.from, e.port)
      if (to) useSession.getState().toast('Connection deleted', 'info', () => void sy().connect(e.from, e.port, to)) } },
  { id: 'story.flow.duplicate', scope: 'story', label: 'Duplicate node', icon: Copy, placement: ['inspector', 'context'], when: () => !!node() && !sy().play, run: () => { const n = node(); if (n) void sy().duplicateNode(n.id) } },
  { id: 'story.flow.newShot', scope: 'story', label: 'New shot for this node…', icon: Plus, placement: ['inspector', 'context'], when: () => visual() && !sy().play,
    run: () => { const n = node(); if (!n) return
      void askText({ title: 'New shot for this node', text: 'An empty shot owned by this node (one node, one shot); fill it in Shots, Stage or Animate.', initial: n.title || NODE_LABEL[n.type], placeholder: 'shot name' }).then((name) => { if (name?.trim()) void sy().spawnShot(n.id, name.trim()) }) } },
  { id: 'story.flow.unbind', scope: 'story', label: 'Unbind from its node', icon: Unlink, placement: ['inspector', 'context'], when: () => !!node()?.shot_id && !sy().play, run: () => { const n = node(); if (n) void sy().unbindShot(n.id) } },
  { id: 'story.flow.openShot', scope: 'story', label: 'Open the shot', icon: Link, placement: ['inspector', 'context'], when: () => !!node()?.shot_id,
    run: () => { const n = node(); if (!n?.shot_id) return; const sid = n.shot_id, v = n.shot_version; void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'shots'); sy().selectShot(sid, v) }) } },
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
    when: () => node()?.type === 'dialogue' && (node()?.lines.some((l) => l.text.trim()) ?? false) && !!useSession.getState().capabilities?.voice?.available && !sy().play,
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
  { id: 'story.world.beatToNode', scope: 'story', label: 'Make a Flow node from this beat', icon: GitBranch, placement: ['inspector', 'context'], when: selBeat,
    run: () => { const s = selected(); if (s?.kind === 'beat') void sy().nodeFromBeat(s.id) } },
  // D92: subjects are Cast characters — Generate's Tree prompt with a subject card linked to the profile (its reference set and LoRA follow)
  { id: 'story.cast.useAsSubject', scope: 'story', label: 'Use as a subject in Image', icon: UserRoundPlus, placement: ['inspector', 'context'], when: () => !!profile() && profile()!.cls !== 'place',
    run: () => { const p = profile(); if (!p) return
      void Promise.all([import('../generate/generateStore'), import('../../frame/suiteRegistry')]).then(([g, r]) => {
        g.useGenerate.getState().useAsSubject(p); r.setRailTab('generate', 'prompt'); useSession.getState().setSuite('generate')
        useSession.getState().toast(`${p.name} is a subject in Image's Tree prompt — its reference set${version()?.lora ? ' and LoRA' : ''} follow`, 'info') }) } },
  { id: 'story.cast.openInStory', scope: 'story', label: 'Open in Story · Cast', icon: Users, placement: ['context'], when: () => !!profile(),
    run: () => { void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'cast'); useSession.getState().setSuite('story') }) } },
  { id: 'story.cast.delete', scope: 'story', label: 'Delete profile', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!profile(),
    run: () => { const p = profile(); if (!p) return
      void askConfirm({ title: `Delete ${p.name}?`, okLabel: 'Delete', danger: true, text: 'The profile record goes; its reference sets and images stay in the album (no longer final). @mentions of it stop resolving.' }).then((ok) => { if (ok) void sy().deleteProfile() }) } },
]
registerCommands(cmds)

/** The right-click menu of a row in the World editor: the row is selected first, so the Inspector shows it too. */
/** The right-click menu of a Cast profile row (the profile is selected first). D90 (01 §11.3): the training and new-profile verbs too. */
export const profileMenu = (): MenuItem[] => [{ cmd: 'story.cast.useAsSubject' }, sep, { cmd: 'story.cast.expand' }, { cmd: 'story.cast.newVersion' }, { cmd: 'story.cast.lock' }, sep, { cmd: 'story.cast.openGroup' }, { cmd: 'story.cast.openCandidates' }, sep,
  { cmd: 'story.cast.train' }, { cmd: 'story.cast.useLora' }, { cmd: 'story.cast.checkLora' }, { cmd: 'story.cast.deleteLora' }, sep, { cmd: 'story.cast.new' }, { cmd: 'story.cast.newPlace' }, { cmd: 'story.cast.newProp' }, sep, { cmd: 'story.cast.delete' }]
export function rowMenu(kind: NonNullable<ReturnType<typeof selected>>['kind'], id: string) {
  useStory.getState().select({ kind, id })
  const items: ({ cmd: string; label?: string } | 'sep')[] = []
  if (kind === 'style') items.push({ cmd: 'story.world.styleSample' }, { cmd: 'story.world.openStyleGroup' }, 'sep', { cmd: 'story.world.defaultStyle' })
  if (kind === 'beat') items.push({ cmd: 'story.world.beatUp' }, { cmd: 'story.world.beatDown' }, { cmd: 'story.world.beatToNode' })
  if (kind === 'entry') items.push({ cmd: 'story.world.entryPicture' }, { cmd: 'story.world.entryEarlier' }, { cmd: 'story.world.entryLater' }, 'sep')   // D92
  if (kind === 'panel') { items.push({ cmd: 'story.world.applyPanel' }, { cmd: 'story.world.renamePanel' }, 'sep', { cmd: 'story.world.remove', label: 'Delete…' }); return items }
  items.push(kind === 'entry' ? { cmd: 'story.world.remove', label: 'Remove from the library' } : { cmd: 'story.world.remove' }, 'sep',
    kind === 'style' ? { cmd: 'story.world.addStyle' } : kind === 'beat' ? { cmd: 'story.world.addBeat' } : kind === 'entry' ? { cmd: 'story.world.addEntry' } : { cmd: 'story.world.addVariable' })   // D90 (01 §11.3): Add … where its row is
  return items
}

/** The right-click menu of a Flow edge (the edge is selected first). */
export function edgeMenu(): { cmd: string }[] { return [{ cmd: 'story.flow.deleteEdge' }] }

/** The right-click menu of a Flow node (the node is selected first). */
export function nodeMenu(): ({ cmd: string } | typeof sepItem)[] {
  return [{ cmd: 'story.flow.makeFrame' }, { cmd: 'story.flow.makeClip' }, sepItem, { cmd: 'story.flow.newShot' }, { cmd: 'story.flow.openShot' }, { cmd: 'story.flow.unbind' }, sepItem,
    { cmd: 'story.flow.openBoard' }, { cmd: 'story.flow.clearBoard' }, sepItem, { cmd: 'story.flow.voiceAll' }, sepItem, { cmd: 'story.flow.duplicate' }, { cmd: 'story.flow.delete' }]
}

/** D90 (02 §5): the entries of "Make frame ▸" and "Make clip ▸" (the shot board, the Strip, the Inspector, the shot row's menu). */
export const makeFrameItems = (): MenuItem[] => [{ cmd: 'story.shot.makeFrame', label: 'in Image' }, { cmd: 'story.shot.makeFrameStage', label: 'from the stage (the camera, Image)' }]
export const makeClipItems = (): MenuItem[] => [{ cmd: 'story.shot.makeClip', label: 'in Animate' }, { cmd: 'story.shot.makeClipStage', label: 'on the stage (the camera, Animate)' }, sep, { cmd: 'story.shot.lipsync' }]
/** The right-click menu of a shot row (the shot is selected first). */
export function shotMenu(): MenuItem[] {
  return [{ label: 'Make frame', icon: ImagePlus, items: makeFrameItems() }, { label: 'Make clip', icon: Film, items: makeClipItems() }, sep,
    { cmd: 'story.shot.runStale' }, { cmd: 'story.shot.finalize' }, { cmd: 'story.shot.newVersion' }, sep, { cmd: 'story.shot.openStage' }, { cmd: 'story.shot.openAnimate' }, sep, { cmd: 'story.shot.release' }, { cmd: 'story.shot.delete' }, sep, { cmd: 'story.shot.new' }]
}
const sepItem = { sep: true } as const
