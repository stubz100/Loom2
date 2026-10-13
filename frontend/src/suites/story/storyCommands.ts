// 17 (D85): the Story suite's verbs — every one has a mouse home (the panel's buttons, the editor rows' tools, the Inspector, right-click
// menus) per D32; Delete and the arrows are accelerators. SY1 adds the Cast tab's verbs (new profile, expand, curate, lock, copy, open).
import { ArrowDown, ArrowUp, Check, Copy, FolderOpen, ImageUp, ListPlus, Lock, Palette, Sparkles, Star, ToggleLeft, Trash2, UserPlus, X } from 'lucide-react'
import { registerCommands, type Command } from '../../frame/commands'
import { askConfirm, askText, useSession } from '../../store/session'
import { CLASS_LABEL, sy, useStory, type ProfileClass } from './storyStore'

const hasWorld = () => !!sy().world
const selected = () => sy().selected
const selStyle = () => selected()?.kind === 'style'
const selBeat = () => selected()?.kind === 'beat'
const profile = () => sy().profile()
const version = () => sy().version()
const openVersion = () => version()?.state === 'open'
const picked = () => sy().picked

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
  { id: 'story.cast.openGroup', scope: 'story', label: 'Open the reference set in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version(),
    run: () => { const v = version(); if (!v) return; useSession.getState().setSuite('catalogue'); void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: v.group_id }) }) } },
  { id: 'story.cast.openCandidates', scope: 'story', label: 'Open the candidates in the Catalogue', icon: FolderOpen, placement: ['inspector', 'context'], when: () => !!version()?.candidates_group_id,
    run: () => { const g = version()?.candidates_group_id; if (!g) return; useSession.getState().setSuite('catalogue'); void import('../catalogue/split').then((m) => { const sp = m.useSplit.getState(); m.openPlace(m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState(), { group: g }) }) } },
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
  if (kind === 'beat') items.push({ cmd: 'story.world.beatUp' }, { cmd: 'story.world.beatDown' })
  items.push({ cmd: 'story.world.remove' })
  return items
}
