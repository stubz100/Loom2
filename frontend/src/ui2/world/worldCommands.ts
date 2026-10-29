// U3 (D157, proto01_UI2 03 §8): World's commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// entity and version the header shows (the Story store's selection) and on the creation selected in the bin.
import { CopyPlus, ImagePlus, Lock, Pencil, Plus, Sparkles, Star, Trash2, UserRoundPlus } from 'lucide-react'
import { http, unwrap } from '../../api/client'
import { registerCommands } from '../../frame/commands'
import { navigate } from '../../frame/router'
import { askConfirm, askText, useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { ONE, useWorld } from './worldStore'

const sy = () => useStory.getState()
const w = () => useWorld.getState()
const selected = () => w().bin?.items.find((x) => x.asset.id === w().selected) ?? null
const open = () => sy().version()?.state === 'open'
const cls = () => { const r = w().rail; return r === 'look' || r === 'sketches' ? null : r }

registerCommands([
  // U3c (03 §4): Make or Edit in the left column — Edit opens the selected creation in Image's editor (the World layer stays)
  { id: 'world.mode.make', scope: 'world', label: 'Make', icon: Sparkles, placement: ['panel'], when: () => w().mode !== 'make',
    run: () => { w().setMode('make'); navigate({ suite: 'generate' }) } },
  { id: 'world.mode.edit', scope: 'world', label: 'Edit', icon: Pencil, placement: ['panel', 'inspector', 'context'], when: () => !!selected(),
    hint: 'the selected creation in the editor; Save puts the result into this bin',
    run: () => { const s = selected(); if (!s) return; w().setMode('edit')
      void import('../../suites/edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(s.asset.id)) } },
  { id: 'world.edit.saveReference', scope: 'world', label: 'Save as a reference', icon: ImagePlus, placement: ['panel'], when: () => w().mode === 'edit' && open(),
    run: () => void import('./editSave').then((m) => m.saveIntoBin('reference')) },
  { id: 'world.edit.saveHero', scope: 'world', label: 'Save as the hero', icon: Star, placement: ['panel'], when: () => w().mode === 'edit' && open(),
    run: () => void import('./editSave').then((m) => m.saveIntoBin('hero')) },
  { id: 'world.entity.new', scope: 'world', label: 'New entity…', icon: UserRoundPlus, placement: ['panel', 'rail'], when: () => !!cls() && !!useSession.getState().project?.open,
    hint: 'a new character, prop or place of the rail\'s class',
    run: () => { const c = cls(); if (!c) return
      void askText({ title: `New ${ONE[c]}`, placeholder: `${ONE[c]} name`, text: 'A draft until its pictures, body and set are made — the header says what it still needs.' }).then(async (name) => {
        if (!name?.trim()) return
        const p = await sy().createProfile(name.trim(), c)
        if (p) w().pick(p.id)
      }) } },
  { id: 'world.version.new', scope: 'world', label: 'New version (copy)', icon: CopyPlus, placement: ['panel'], when: () => !!sy().version(),
    run: () => void sy().newVersion().then(() => { const p = sy().profile(); if (p) w().pick(p.id, p.current) }) },
  { id: 'world.version.final', scope: 'world', label: 'Mark final', icon: Lock, placement: ['panel'], when: () => open(), danger: true,
    run: () => { const v = sy().version(); const p = sy().profile(); if (!v || !p) return
      void askConfirm({ title: `Mark ${p.name} ${v.id} final?`, okLabel: 'Mark final', text: 'Its reference set and sheet are fixed; a new version is made to change them.' }).then((ok) => { if (ok) void sy().lockVersion() }) } },
  { id: 'world.creation.hero', scope: 'world', label: 'Make it the hero', icon: Star, placement: ['inspector', 'context'], when: () => open() && !!selected() && !selected()!.roles.includes('hero'),
    run: () => { const s = selected(); if (s) void sy().setHero(s.asset.id) } },
  { id: 'world.creation.reference', scope: 'world', label: 'Use as a reference', icon: ImagePlus, placement: ['inspector', 'context'],
    when: () => open() && !!selected() && !selected()!.roles.some((r) => r === 'reference' || r === 'hero'),
    run: () => { const s = selected(); const p = sy().profile(); if (s && p) void sy().addToProfile(p.id, [s.asset.id], 'reference', sy().versionId ?? undefined) } },
  { id: 'world.creation.candidate', scope: 'world', label: 'Back to the candidates', icon: Plus, placement: ['inspector', 'context'],
    when: () => open() && !!selected() && selected()!.roles.includes('reference'),
    run: () => { const s = selected(); const p = sy().profile(); if (s && p) void sy().addToProfile(p.id, [s.asset.id], 'candidate', sy().versionId ?? undefined) } },
  { id: 'world.creation.trash', scope: 'world', label: 'Trash', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!selected() && !selected()!.roles.includes('hero'),
    run: () => { const s = selected(); if (!s) return
      void unwrap(http.POST('/assets/trash', { body: { ids: [s.asset.id] } })).then(() => { w().select(null); void w().loadBin() },
        (e) => useSession.getState().toast(`Trash: ${(e as { detail?: string }).detail ?? e}`, 'error')) } },
])
