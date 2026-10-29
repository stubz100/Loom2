// U3 (D157, proto01_UI2 03 §8): World's commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// entity and version the header shows (the Story store's selection) and on the creation selected in the bin.
import { Box, CopyPlus, Hammer, ImagePlus, Lock, Pencil, PersonStanding, Plus, Sparkles, Star, Trash2, UserRoundPlus, Users } from 'lucide-react'
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
/** B2a: the Line-up — the rail's class (a prop with its 3D model), the one open first, twelve at most. */
const lineup = () => {
  const cls = w().rail, here = sy().profileId
  const all = sy().profiles.filter((p) => p.cls === cls && cls !== 'place' && (p.cls === 'character' || !!p.versions.find((v) => v.id === p.current)?.model_asset_id))
  return [...all.filter((p) => p.id === here), ...all.filter((p) => p.id !== here)].slice(0, 12)                  // the one open first
}
const cls = () => { const r = w().rail; return r === 'look' || r === 'sketches' ? null : r }

registerCommands([
  // U3c (03 §4): Make or Edit in the left column — Edit opens the selected creation in Image's editor (the World layer stays)
  // U3f (03 §8, D142): See in clay — the entity version's bench (Clay opened for it: a character's figure, a prop's model beside a 1.75 m
  // figure, a place's set from its picture's camera) inside World, with Clay's tools
  { id: 'world.mode.clay', scope: 'world', label: 'See in clay ▶', icon: Box, placement: ['panel'],
    hint: "Clay opened for this version on a scene of its own — the figure, the model at its height or the set — with all of Clay's tools",
    when: () => { const p = sy().profile(); const v = sy().version(); return !!p && !!v && (p.cls === 'character' || (p.cls === 'prop' && !!v.model_asset_id) || (p.cls === 'place' && !!v.place_set)) },
    run: () => { const p = sy().profile(); const v = sy().version(); if (!p || !v) return
      void import('../../suites/stage/stageStore').then(async (m) => { if (await m.st().openBench(p.id, v.id, 'world')) w().setMode('clay') }) } },
  // B2a (D159, 11 §7): the Sheet — the version's whole card (the sheet, the body and its skeleton, the animation reference and its test, a
  // prop's model, a place's set builder, the Line-up)
  { id: 'world.mode.build', scope: 'world', label: 'Build', icon: Hammer, placement: ['panel'], hint: "what Clay needs: the animation reference, the body, the skeleton, the test animation, a prop's 3D model, a place's set, the line-up",
    when: () => !!sy().profile(), run: () => { w().setMode('build'); navigate({ suite: 'generate' }) } },   // D161: the Sheet's words went to Make
  { id: 'world.lineup', scope: 'world', label: 'Line-up ▶', icon: Users, placement: ['panel'], hint: "this class's characters or props side by side at their sizes in Clay (twelve at most)",
    when: () => lineup().length > 0,
    run: () => { const items = lineup().map((p) => ({ profile_id: p.id }))
      void import('../../suites/stage/stageStore').then(async (m) => { if (await m.st().openLineup(items, () => w().setMode('make'), 'world')) w().setMode('clay') }) } },
  { id: 'world.creation.aposeFront', scope: 'world', label: 'Use as the A-pose front', icon: PersonStanding, placement: ['inspector', 'context'],
    hint: 'the animation reference: full body, A-pose, 16:9, plain ground', when: () => !!selected() && open() && (sy().profile()?.cls === 'character' || sy().profile()?.cls === 'prop'),
    run: () => { const s = selected(); if (s) void sy().setAnimRef('front', s.asset.id) } },
  { id: 'world.creation.setPicture', scope: 'world', label: 'Use as the set picture', icon: ImagePlus, placement: ['inspector', 'context'],   // D161: picked, not the first result
    hint: "the place's set picture: what Build the set ▶ fits a room, a corridor or a street to", when: () => !!selected() && open() && sy().profile()?.cls === 'place',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('front', s.asset.id) } },
  { id: 'world.creation.aposeBack', scope: 'world', label: 'Use as the A-pose back', icon: PersonStanding, placement: ['inspector', 'context'],
    hint: 'its optional back view (a shot that starts turned away)', when: () => !!selected() && sy().profile()?.cls === 'character',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('back', s.asset.id) } },
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
