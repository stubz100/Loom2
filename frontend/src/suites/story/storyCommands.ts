// 17 (D85): the Story suite's verbs — every one has a mouse home (the panel's buttons, the editor rows' tools, the Inspector, right-click
// menus) per D32; Delete and the arrows are accelerators. SY1 adds the Cast tab's verbs (new profile, expand, curate, lock, copy, open).
import { ArrowDown, ArrowUp, Check, CircleHelp, Clapperboard, Copy, CornerDownRight, Film, FolderOpen, GitBranch, GitFork, ImageUp, Link, ListChecks, ListPlus, Lock, Maximize, MessageSquare, Palette, Play, Plus, Shapes, Sparkles, Square, Star, StickyNote, ToggleLeft, Trash2, Unlink, UserPlus, X, Zap, GraduationCap, RotateCcw, Wand2 } from 'lucide-react'
import { registerCommands, type Command } from '../../frame/commands'
import { askConfirm, askText, useSession } from '../../store/session'
import { CLASS_LABEL, latestTrainJob, sy, useStory, type ProfileClass } from './storyStore'

const hasWorld = () => !!sy().world
const selected = () => sy().selected
const selStyle = () => selected()?.kind === 'style'
const selBeat = () => selected()?.kind === 'beat'
const profile = () => sy().profile()
const version = () => sy().version()
const openVersion = () => version()?.state === 'open'
const picked = () => sy().picked
const trainJob = () => { const p = profile(); const v = version(); return p && v ? latestTrainJob(useSession.getState().jobs, p.id, v.id) : undefined }
const trainCaps = () => useSession.getState().capabilities?.train
const refsCount = () => Object.keys(sy().refPage?.assets ?? {}).length
const shot = () => sy().shot()
const shotVersion = () => sy().shotVersion()
const node = () => sy().node()
const visual = () => { const n = node(); return !!n && (n.type === 'dialogue' || n.type === 'shot') }
const NODE_ICON = { start: Play, hub: GitFork, dialogue: MessageSquare, choice: ListChecks, condition: CircleHelp, action: Zap, shot: Clapperboard, jump: CornerDownRight, comment: StickyNote } as const
const NODE_LABEL = { start: 'Start', hub: 'Hub', dialogue: 'Dialogue', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' } as const
/** The viewport registers its fit and its centre in flow coordinates (the canvas is not a store). */
export const flowView: { fit?: () => void; centre?: () => { x: number; y: number } | null } = {}

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
  const ok = await askConfirm({ title: `Train ${p.name} ${v.id}?`, okLabel: o.stage ? 'Stage the job' : 'Train now',
    text: `${base?.label ?? 'the base'}${base?.offload ? ' (offloaded)' : ''} · ${o.steps} steps at ${o.resolution}² · rank ${o.rank} · ${refsCount()} references — ${mins} on this card; the engine stops while it runs${o.stage ? '. Staged: release it when the rig is free.' : '.'}` })
  if (ok) await sy().train()
}

export async function newProfile(cls: ProfileClass = 'character', hero: string | null = null): Promise<void> {
  const name = await askText({ title: `New ${CLASS_LABEL[cls]}`, text: hero ? 'The image becomes the hero and the cover of a new reference set; @name mentions it in prompts.' : 'An empty profile: give it a hero from the Catalogue ("Make a character…" on a tile) before expanding.', placeholder: `${CLASS_LABEL[cls]} name` })
  if (name?.trim()) await sy().createProfile(name.trim(), cls, hero)
}

const cmds: Command[] = [
  { id: 'story.world.addStyle', scope: 'story', label: 'Add style', icon: Palette, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addStyle() } },
  { id: 'story.world.addBeat', scope: 'story', label: 'Add beat', icon: ListPlus, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addBeat() } },
  { id: 'story.world.addVariable', scope: 'story', label: 'Add variable', icon: ToggleLeft, placement: ['panel', 'context'], when: hasWorld, run: () => { sy().addVariable() } },
  { id: 'story.world.defaultStyle', scope: 'story', label: 'Make it the default style', icon: Star, placement: ['inspector', 'context'], when: () => selStyle() && sy().world?.default_style !== selected()?.id,
    run: () => { const s = selected(); if (s?.kind === 'style') sy().setDefaultStyle(s.id) } },
  { id: 'story.world.beatUp', scope: 'story', label: 'Move the beat earlier', icon: ArrowUp, keys: 'Ctrl+ArrowUp', placement: ['inspector', 'context'], when: selBeat, run: () => { const s = selected(); if (s) sy().moveBeat(s.id, -1) } },
  { id: 'story.world.beatDown', scope: 'story', label: 'Move the beat later', icon: ArrowDown, keys: 'Ctrl+ArrowDown', placement: ['inspector', 'context'], when: selBeat, run: () => { const s = selected(); if (s) sy().moveBeat(s.id, 1) } },
  { id: 'story.world.remove', scope: 'story', label: 'Remove', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], when: () => !!selected(), danger: true, run: () => sy().removeSelected() },
  // SY1 · Cast
  { id: 'story.cast.new', scope: 'story', label: 'New profile…', icon: UserPlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('character') },
  { id: 'story.cast.newPlace', scope: 'story', label: 'New place…', icon: UserPlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('place') },
  { id: 'story.cast.newProp', scope: 'story', label: 'New prop…', icon: UserPlus, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open, run: () => void newProfile('prop') },
  { id: 'story.cast.expand', scope: 'story', label: 'Expand…', icon: Sparkles, keys: 'Ctrl+Enter', placement: ['panel', 'inspector', 'context'],
    when: () => openVersion() && !!version()?.hero_asset_id && !!useSession.getState().capabilities?.story?.model_id && !sy().expanding,
    run: () => void askExpand(sy().world ? 'full' : 'full', 1, 'draft') },
  { id: 'story.cast.keep', scope: 'story', label: 'Keep (into the reference set)', icon: Check, keys: 'K', placement: ['context', 'inspector', 'toolbar'], when: () => openVersion() && picked().length > 0,
    run: () => void sy().curate(picked(), 'keep') },
  { id: 'story.cast.reject', scope: 'story', label: 'Reject', icon: X, keys: 'X', placement: ['context', 'inspector', 'toolbar'], when: () => openVersion() && picked().length > 0,
    run: () => void sy().curate(picked(), 'reject') },
  { id: 'story.cast.setHero', scope: 'story', label: 'Make it the hero', icon: ImageUp, placement: ['context', 'inspector'], when: () => openVersion() && picked().length === 1,
    run: () => void sy().setHero(picked()[0]) },
  { id: 'story.cast.lock', scope: 'story', label: 'Lock the version', icon: Lock, placement: ['strip', 'inspector', 'context'], when: () => openVersion() && !!version()?.hero_asset_id && !sy().busy,
    run: () => { const p = profile(); const v = version(); if (!p || !v) return
      void askConfirm({ title: `Lock ${p.name} ${v.id}?`, okLabel: 'Lock', text: 'The reference set becomes read-only (the album refuses changes on its page) and the stub is fixed; @mentions keep resolving to it. A retake is a new version.' }).then((ok) => { if (ok) void sy().lockVersion() }) } },
  { id: 'story.cast.newVersion', scope: 'story', label: 'New version (copy)', icon: Copy, placement: ['strip', 'inspector', 'context'], when: () => !!version() && !sy().busy,
    run: () => { const p = profile(); const v = version(); if (!p || !v) return
      void askConfirm({ title: `Copy ${p.name} ${v.id} into a new version?`, okLabel: 'Copy', text: 'The reference set is duplicated (its images copied — an image lives on one page), the stub and hero copied; the copy becomes the current version, open.' }).then((ok) => { if (ok) void sy().newVersion() }) } },
  { id: 'story.cast.train', scope: 'story', label: 'Train a LoRA…', icon: GraduationCap, placement: ['panel', 'inspector', 'context'],
    when: () => !!version()?.hero_asset_id && !!trainCaps()?.available && refsCount() >= (trainCaps()?.min_refs ?? 4) && !['staged', 'queued', 'running'].includes(trainJob()?.status ?? '') && !sy().busy,
    run: () => void askTrain() },
  { id: 'story.cast.useLora', scope: 'story', label: 'Use in Generate', icon: Wand2, placement: ['inspector', 'context'], when: () => !!version()?.lora,
    run: () => void sy().useLora(version()!.lora!) },
  { id: 'story.cast.deleteLora', scope: 'story', label: 'Delete the LoRA', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!version()?.lora,
    run: async () => { const v = version(); if (!v?.lora) return; if (await askConfirm({ title: 'Delete the LoRA?', okLabel: 'Delete', text: 'The file, its record and the engine\'s cached copy go; the version keeps its trigger for a retrain.' })) await sy().deleteLora(v.lora) } },
  { id: 'story.cast.releaseTrain', scope: 'story', label: 'Release the training job', icon: Play, placement: ['inspector'], when: () => trainJob()?.status === 'staged',
    run: () => { const j = trainJob(); if (j) void useSession.getState().releaseJob(j.id) } },
  { id: 'story.cast.resumeTrain', scope: 'story', label: 'Resume the training job', icon: RotateCcw, placement: ['inspector'], when: () => trainJob()?.status === 'failed' && !!trainJob()?.resumable,
    run: () => { const j = trainJob(); if (j) void sy().requeueTrain(j.id) } },
  { id: 'story.cast.cancelTrain', scope: 'story', label: 'Cancel the training job', icon: X, placement: ['inspector'], when: () => ['staged', 'queued', 'running'].includes(trainJob()?.status ?? ''),
    run: () => { const j = trainJob(); if (j) void useSession.getState().cancelJob(j.id) } },
  { id: 'story.cast.openGroup', scope: 'story', label: 'Open the reference set in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version(),
    run: () => { const v = version(); if (!v) return; useSession.getState().setSuite('catalogue'); void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: v.group_id }) }) } },
  { id: 'story.cast.openCandidates', scope: 'story', label: 'Open the candidates in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version()?.candidates_group_id,
    run: () => { const g = version()?.candidates_group_id; if (!g) return; useSession.getState().setSuite('catalogue'); void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: g }) }) } },
  // SY2 · Shots
  { id: 'story.shot.new', scope: 'story', label: 'New shot…', icon: Clapperboard, placement: ['panel', 'context'], when: () => !!useSession.getState().project?.open,
    run: () => void askText({ title: 'New shot', text: 'An empty shot: its frame and clip come from a Stage camera ("New shot from this camera") or from Animate ("Make a shot from this clip"), or pick takes here.', placeholder: 'shot name' })
      .then((n) => { if (n?.trim()) void sy().createShot(n.trim()) }) },
  { id: 'story.shot.newVersion', scope: 'story', label: 'New version (copy)', icon: Copy, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion(),
    run: () => { const s = shot(); const v = shotVersion(); if (!s || !v) return
      void askConfirm({ title: `Copy ${s.name} ${v.id} into a new version?`, okLabel: 'Copy', text: 'The source, frame and clip pointers are copied (no files); the copy becomes the current version, open — a retake.' }).then((ok) => { if (ok) void sy().newShotVersion() }) } },
  { id: 'story.shot.finalize', scope: 'story', label: 'Finalize the version', icon: Lock, placement: ['strip', 'inspector', 'context'], when: () => { const v = shotVersion(); return !!v && v.state === 'open' && !sy().finalizeWhy(v) },
    run: () => { const s = shot(); const v = shotVersion(); if (!s || !v) return
      void askConfirm({ title: `Finalize ${s.name} ${v.id}?`, okLabel: 'Finalize', text: 'The clip becomes the one the Flow and the Episode bind; the frame and clip are fixed. A retake is a new version.' }).then((ok) => { if (ok) void sy().finalizeShot() }) } },
  { id: 'story.shot.openStage', scope: 'story', label: 'Open in Stage', icon: Shapes, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion()?.stage_id,
    run: () => { const v = shotVersion(); if (!v?.stage_id) return; const sid = v.stage_id, cam = v.camera_id
      useSession.getState().setSuite('stage')
      void import('../stage/stageStore').then((m) => { const st = m.useStage.getState(); const go = st.current?.id === sid ? Promise.resolve() : st.open(sid); void go.then(() => { if (cam) m.useStage.getState().setActiveCamera(cam) }) }) } },
  { id: 'story.shot.openAnimate', scope: 'story', label: 'Open in Animate', icon: Film, placement: ['strip', 'inspector', 'context'], when: () => !!shotVersion()?.clip_id,
    run: () => { const v = shotVersion(); if (!v?.clip_id) return; const cid = v.clip_id
      useSession.getState().setSuite('animate')
      void import('../animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(cid)) }) } },
  { id: 'story.shot.release', scope: 'story', label: 'Release from its node', icon: Unlink, placement: ['inspector', 'context'], when: () => !!shot()?.owner_node,
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
  { id: 'story.flow.duplicate', scope: 'story', label: 'Duplicate node', icon: Copy, placement: ['inspector', 'context'], when: () => !!node() && !sy().play, run: () => { const n = node(); if (n) void sy().duplicateNode(n.id) } },
  { id: 'story.flow.newShot', scope: 'story', label: 'New shot for this node…', icon: Plus, placement: ['inspector', 'context'], when: () => visual() && !sy().play,
    run: () => { const n = node(); if (!n) return
      void askText({ title: 'New shot for this node', text: 'An empty shot owned by this node (loom R146: one node, one shot); fill it in Shots, Stage or Animate.', initial: n.title || NODE_LABEL[n.type], placeholder: 'shot name' }).then((name) => { if (name?.trim()) void sy().spawnShot(n.id, name.trim()) }) } },
  { id: 'story.flow.unbind', scope: 'story', label: 'Release the shot', icon: Unlink, placement: ['inspector', 'context'], when: () => !!node()?.shot_id && !sy().play, run: () => { const n = node(); if (n) void sy().unbindShot(n.id) } },
  { id: 'story.flow.openShot', scope: 'story', label: 'Open the shot', icon: Link, placement: ['inspector', 'context'], when: () => !!node()?.shot_id,
    run: () => { const n = node(); if (!n?.shot_id) return; const sid = n.shot_id, v = n.shot_version; void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'shots'); sy().selectShot(sid, v) }) } },
  { id: 'story.flow.validate', scope: 'story', label: 'Validate', icon: ListChecks, placement: ['strip', 'context'], when: () => !!useSession.getState().project?.open, run: () => void sy().validate() },
  { id: 'story.flow.play', scope: 'story', label: 'Play', icon: Play, keys: 'P', placement: ['strip', 'context'], when: () => !!sy().flowGraph && !sy().play, run: () => sy().playStart() },
  { id: 'story.flow.stop', scope: 'story', label: 'Stop playing', icon: Square, placement: ['strip'], when: () => !!sy().play, run: () => sy().playStop() },
  { id: 'story.flow.fit', scope: 'story', label: 'Fit the graph', icon: Maximize, keys: 'F', placement: ['strip', 'context'], when: () => !!sy().flowGraph && !sy().play, run: () => flowView.fit?.() },
  { id: 'story.world.beatToNode', scope: 'story', label: 'Make a Flow node from this beat', icon: GitBranch, placement: ['inspector', 'context'], when: selBeat,
    run: () => { const s = selected(); if (s?.kind === 'beat') void sy().nodeFromBeat(s.id) } },
  { id: 'story.cast.delete', scope: 'story', label: 'Delete profile', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!profile(),
    run: () => { const p = profile(); if (!p) return
      void askConfirm({ title: `Delete ${p.name}?`, okLabel: 'Delete', danger: true, text: 'The profile record goes; its reference sets and images stay in the album (unlocked). @mentions of it stop resolving.' }).then((ok) => { if (ok) void sy().deleteProfile() }) } },
]
registerCommands(cmds)

/** The right-click menu of a row in the World editor: the row is selected first, so the Inspector shows it too. */
export function rowMenu(kind: NonNullable<ReturnType<typeof selected>>['kind'], id: string) {
  useStory.getState().select({ kind, id })
  const items: ({ cmd: string } | 'sep')[] = []
  if (kind === 'style') items.push({ cmd: 'story.world.defaultStyle' })
  if (kind === 'beat') items.push({ cmd: 'story.world.beatUp' }, { cmd: 'story.world.beatDown' }, { cmd: 'story.world.beatToNode' })
  items.push({ cmd: 'story.world.remove' })
  return items
}

/** The right-click menu of a Flow node (the node is selected first). */
export function nodeMenu(): ({ cmd: string } | typeof sepItem)[] {
  return [{ cmd: 'story.flow.newShot' }, { cmd: 'story.flow.openShot' }, { cmd: 'story.flow.unbind' }, sepItem, { cmd: 'story.flow.duplicate' }, { cmd: 'story.flow.delete' }]
}
const sepItem = { sep: true } as const
