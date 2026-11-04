// U3 (D157, proto01_UI2 03 §8): World's commands (rule 3: every action a command with a mouse home; keys are accelerators). They act on the
// entity and version the header shows (the Story store's selection) and on the creation selected in the bin.
import { ArrowLeft, Box, CopyPlus, Footprints, Hand, ImagePlus, Lock, Pencil, PersonStanding, Plus, Sparkles, Star, Trash2, UserRoundPlus } from 'lucide-react'
import { http, unwrap } from '../../api/client'
import { registerCommands } from '../../frame/commands'
import { navigate } from '../../frame/router'
import { askConfirm, askText, useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { ONE, useWorld } from './worldStore'
import { carriedThings } from './readiness'

const sy = () => useStory.getState()
const w = () => useWorld.getState()
const selected = () => w().bin?.items.find((x) => x.asset.id === w().selected) ?? null
const open = () => sy().version()?.state === 'open'
const cls = () => { const r = w().rail; return r === 'look' || r === 'sketches' ? null : r }
/** W16: what a new entity of each class still needs (a prop has no body, a character no set). */
const NEEDS: Record<string, string> = { character: 'its pictures, A-pose and body are made', prop: 'its pictures and 3D model are made', place: 'its set picture and set are made' }

registerCommands([
  // U3c (03 §4): Make or Edit in the left column — Edit opens the selected creation in Image's editor (the World layer stays). C0 (D181):
  // the bench, the line-up and Build's 3D are Clay's Library (clay.bench.open, clay.lineup, clay.asset.open)
  { id: 'world.creation.aposeFront', scope: 'world', label: 'Use as the A-pose front', icon: PersonStanding, placement: ['inspector', 'context'],
    hint: 'the animation reference: full body, A-pose, 16:9, plain ground', when: () => !!selected() && open() && (sy().profile()?.cls === 'character' || sy().profile()?.cls === 'prop'),
    run: () => { const s = selected(); if (s) void sy().setAnimRef('front', s.asset.id) } },
  { id: 'world.creation.setPicture', scope: 'world', label: 'Use as the set picture', icon: ImagePlus, placement: ['inspector', 'context'],   // D161: picked, not the first result
    hint: "the place's set picture: what Build the set ▶ fits a room, a corridor or a street to", when: () => !!selected() && open() && sy().profile()?.cls === 'place',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('front', s.asset.id) } },
  { id: 'world.creation.aposeBack', scope: 'world', label: 'Use as the A-pose back', icon: PersonStanding, placement: ['inspector', 'context'],
    hint: 'its optional back view (a shot that starts turned away)', when: () => !!selected() && sy().profile()?.cls === 'character',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('back', s.asset.id) } },
  { id: 'world.creation.aposeSide', scope: 'world', label: 'Use as the A-pose side', icon: PersonStanding, placement: ['inspector', 'context'],
    hint: 'its optional side view, facing left (a character performed in profile: the braid, the hood, what hangs behind)', when: () => !!selected() && sy().profile()?.cls === 'character',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('side', s.asset.id) } },
  { id: 'world.creation.handPicture', scope: 'world', label: 'Use as the hand picture', icon: Hand, placement: ['inspector', 'context'],   // RG1 (D187)
    hint: 'its own hand: SDPose reads each finger from it at once (a few seconds)', when: () => !!selected() && sy().profile()?.cls === 'character',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('hand', s.asset.id) } },
  { id: 'world.creation.feetPicture', scope: 'world', label: 'Use as the feet picture', icon: Footprints, placement: ['inspector', 'context'],   // RG1 (D188)
    hint: 'its own feet and shoes from the side: the heel, the toe and the ankle are read from it at once', when: () => !!selected() && sy().profile()?.cls === 'character',
    run: () => { const s = selected(); if (s) void sy().setAnimRef('feet', s.asset.id) } },
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
  { id: 'world.carried.prop', scope: 'world', label: 'Make what it carries a prop…', icon: Box, placement: ['panel'],
    hint: 'the A-pose leaves out what the words have it carry (its hands open, no props); a Cast prop held in Clay (Hold ▸) keeps it',
    when: () => { const v = sy().version(); return sy().profile()?.cls === 'character' && !!v && carriedThings(v).length > 0 },
    run: () => { const v = sy().version(), thing = v ? carriedThings(v)[0] : undefined; if (!thing) return       // M4
      const plain = thing.replace(/^an?\s+/i, '')
      void askText({ title: 'A prop from what it carries', placeholder: 'prop name', initial: plain.charAt(0).toUpperCase() + plain.slice(1) }).then(async (name) => {
        if (!name?.trim()) return
        const p = await sy().createProfile(name.trim(), 'prop', null, thing)
        if (p) { w().pick(p.id); useSession.getState().toast(`${p.name} is a prop now — its pictures and 3D model next; in Clay, Hold ▸ puts it in the hand`, 'info') } }) } },
  { id: 'world.entity.new', scope: 'world', label: 'New entity…', icon: UserRoundPlus, placement: ['panel', 'rail'], when: () => !!cls() && !!useSession.getState().project?.open,
    hint: 'a new character, prop or place of the rail\'s class',
    run: () => { const c = cls(); if (!c) return
      void askText({ title: `New ${ONE[c]}`, placeholder: `${ONE[c]} name`, text: `A draft until ${NEEDS[c]} — the header says what it still needs.` }).then(async (name) => {
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
  { id: 'world.creation.back', scope: 'world', label: 'Back to the entity', icon: ArrowLeft, placement: ['inspector', 'context'], when: () => !!selected(),   // W12: its facts, versions, voice, Delete
    hint: 'the Inspector shows the entity again (also: a click on the selected picture, or on the grid around the pictures)', run: () => w().select(null) },
  { id: 'world.creation.trash', scope: 'world', label: 'Trash', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!selected() && !selected()!.roles.includes('hero'),
    run: () => { const s = selected(); if (!s) return
      void unwrap(http.POST('/assets/trash', { body: { ids: [s.asset.id] } })).then(() => { w().select(null); void w().loadBin() },
        (e) => useSession.getState().toast(`Trash: ${(e as { detail?: string }).detail ?? e}`, 'error')) } },
])
