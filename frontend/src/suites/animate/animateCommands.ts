// Animate commands (11 §9, 07 §3c, D32): one definition each for the transport buttons, the strip, the inspector verbs,
// the right-click menus and the keys. Keys are accelerators for buttons that exist anyway.
import { ArrowLeftRight, Check, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, Columns2, Download, Eye, Film, Layers, Pause, Play, Repeat, RotateCcw, Scissors, Shuffle, SkipBack, SkipForward, Sparkles, SquareX, StepBack, StepForward, Trash, X } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { http, unwrap, type ApiError } from '../../api/client'
import { askText, useSession } from '../../store/session'
import { useAnimate } from './animateStore'
import { useComposition } from './compositionStore'
import { ArrowDown as ArrowDownIcon, ArrowUp as ArrowUpIcon, Circle as EllipseIcon, Crosshair as SoloIcon, Diamond as KeyIcon, EyeOff as HideIcon, Lock as LockIcon, Redo2 as RedoIcon,
  Square as RectIcon, Undo2 as UndoIcon, ArrowLeftToLine as TrimInIcon, ArrowRightToLine as TrimOutIcon, Columns2 as BeforeIcon } from 'lucide-react'

const an = () => useAnimate.getState()
const cp = () => useComposition.getState()
const hasClip = () => !!an().clip()
const hasStart = () => !!an().panel.start
const atFinal = () => cp().level === 'final' && !!cp().comp
const selLayer = () => (atFinal() ? cp().layers.find((l) => l.id === cp().selected) ?? null : null)
const hasSel = () => !!selLayer()

registerCommands([
  // render
  { id: 'anim.animate', scope: 'animate', label: 'Animate', icon: Clapperboard, keys: 'Ctrl+Enter', placement: ['panel'], when: hasStart, run: () => void an().animate(false) },
  { id: 'anim.stage', scope: 'animate', label: 'Queue', hint: 'add to the queue and run it later — Run now in the Dock', icon: Layers, keys: 'Ctrl+Shift+Enter', placement: ['panel'], when: hasStart, run: () => void an().animate(true) },
  { id: 'anim.swap', scope: 'animate', label: 'Swap start and end', icon: ArrowLeftRight, placement: ['panel'], when: () => !!an().panel.end, run: () => an().swap() },
  { id: 'anim.clearStart', scope: 'animate', label: 'Clear start frame', icon: X, placement: ['panel', 'context'], when: hasStart, run: () => an().setStart(null) },
  { id: 'anim.clearEnd', scope: 'animate', label: 'Clear end frame', icon: X, placement: ['panel', 'context'], when: () => !!an().panel.end, run: () => an().setEnd(null) },
  // transport — D90 (02 §8.2): the one key set of Animate, the Stage timeline and the Episode lane; `,` `.` and Shift+, / Shift+. stay as alternates
  // D99 (UX0 #19): the viewer levels by number — 1 goes to Clay (the stage) from here; the strip's switch is their mouse home
  { id: 'anim.level.clay', scope: 'animate', label: 'Animate · Clay', keys: '1', placement: ['strip'], run: () => useSession.getState().setSuite('stage') },
  // AE1 / AP1 (D114): the Final level — the composition's frames; its own transport (the clip player's keys stay the clip's)
  { id: 'anim.level.performance', scope: 'animate', label: 'Animate · Performance', keys: '2', placement: ['strip'], run: () => cp().setLevel('performance') },
  { id: 'anim.level.final', scope: 'animate', label: 'Animate · Final', keys: '3', placement: ['strip'], run: () => cp().setLevel('final') },
  { id: 'anim.final.play', scope: 'animate', label: 'Play / pause the composition', icon: Play, placement: ['toolbar'], when: atFinal, run: () => cp().togglePlay() },
  { id: 'anim.final.stepBack', scope: 'animate', label: 'Previous frame', icon: StepBack, placement: ['toolbar'], when: atFinal, run: () => cp().step(-1) },
  { id: 'anim.final.stepForward', scope: 'animate', label: 'Next frame', icon: StepForward, placement: ['toolbar'], when: atFinal, run: () => cp().step(1) },
  { id: 'anim.final.home', scope: 'animate', label: 'First frame', icon: ChevronFirst, placement: ['toolbar'], when: atFinal, run: () => cp().home() },
  { id: 'anim.final.end', scope: 'animate', label: 'Last frame', icon: ChevronLast, placement: ['toolbar'], when: atFinal, run: () => cp().end() },
  // AE2: the editor — each one engine command on the composition (Layers' toolbar, the row's menu; the keys as accelerators)
  { id: 'anim.final.undo', scope: 'animate', label: 'Undo', icon: UndoIcon, keys: 'Ctrl+Z', placement: ['toolbar', 'context'], when: atFinal, run: () => void cp().undo() },
  { id: 'anim.final.redo', scope: 'animate', label: 'Redo', icon: RedoIcon, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'], when: atFinal, run: () => void cp().redo() },
  { id: 'anim.final.layer.up', scope: 'animate', label: 'Layer up', hint: 'above the next layer', icon: ArrowUpIcon, placement: ['toolbar', 'context'], when: () => (selLayer()?.index ?? 1) > 1, run: () => void cp().arrange(cp().selected!, 'forward') },
  { id: 'anim.final.layer.down', scope: 'animate', label: 'Layer down', hint: 'below the next layer', icon: ArrowDownIcon, placement: ['toolbar', 'context'], when: () => !!selLayer() && selLayer()!.index < cp().layers.length, run: () => void cp().arrange(cp().selected!, 'backward') },
  { id: 'anim.final.layer.hide', scope: 'animate', label: 'Hide / show the layer', icon: HideIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().layerSwitch(cp().selected!, 'video', !selLayer()!.switches.video) },
  { id: 'anim.final.layer.solo', scope: 'animate', label: 'Solo the layer', icon: SoloIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().layerSwitch(cp().selected!, 'solo', !selLayer()!.switches.solo) },
  { id: 'anim.final.layer.lock', scope: 'animate', label: 'Lock / unlock the layer', icon: LockIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().layerSwitch(cp().selected!, 'lock', !selLayer()!.switches.locked) },
  { id: 'anim.final.key.position', scope: 'animate', label: 'Keyframe: position at the playhead', icon: KeyIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().keyToggle('transform/position') },
  { id: 'anim.final.key.opacity', scope: 'animate', label: 'Keyframe: opacity at the playhead', icon: KeyIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().keyToggle('transform/opacity') },
  // AE2c: masks drawn on the frame; AE2d: the layer's in / out at the playhead (the lanes under the transport drag too)
  { id: 'anim.final.mask.rect', scope: 'animate', label: 'Mask: rectangle', hint: 'drag on the frame', icon: RectIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => cp().setMaskTool(cp().maskTool === 'rect' ? 'off' : 'rect') },
  { id: 'anim.final.mask.ellipse', scope: 'animate', label: 'Mask: ellipse', hint: 'drag on the frame', icon: EllipseIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => cp().setMaskTool(cp().maskTool === 'ellipse' ? 'off' : 'ellipse') },
  { id: 'anim.final.trimIn', scope: 'animate', label: 'Trim in to the playhead', icon: TrimInIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().setTiming(cp().selected!, { in: cp().frame / (cp().final?.rate ?? 16) }) },
  { id: 'anim.final.trimOut', scope: 'animate', label: 'Trim out to the playhead', icon: TrimOutIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().setTiming(cp().selected!, { out: (cp().frame + 1) / (cp().final?.rate ?? 16) }) },
  // AE3: before / after — the frame with every effect off (nothing saved)
  { id: 'anim.final.before', scope: 'animate', label: 'Before', hint: 'the frame with every effect off; again for after', icon: BeforeIcon, placement: ['toolbar', 'context'], when: atFinal, run: () => void cp().compareBefore(!cp().before) },
  { id: 'anim.play', scope: 'animate', label: 'Play / pause', icon: Play, keys: 'Space', placement: ['toolbar', 'context'], when: hasClip, run: () => an().togglePlay() },
  { id: 'anim.stepBack', scope: 'animate', label: 'Previous frame', icon: StepBack, keys: 'ArrowLeft', alt: [','], placement: ['toolbar', 'context'], when: hasClip, run: () => an().step(-1) },
  { id: 'anim.stepForward', scope: 'animate', label: 'Next frame', icon: StepForward, keys: 'ArrowRight', alt: ['.'], placement: ['toolbar', 'context'], when: hasClip, run: () => an().step(1) },
  { id: 'anim.back10', scope: 'animate', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+ArrowLeft', alt: ['Shift+,', '<'], placement: ['toolbar'], when: hasClip, run: () => an().step(-10) },
  { id: 'anim.fwd10', scope: 'animate', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+ArrowRight', alt: ['Shift+.', '>'], placement: ['toolbar'], when: hasClip, run: () => an().step(10) },
  { id: 'anim.home', scope: 'animate', label: 'First frame', icon: ChevronFirst, keys: 'Home', placement: ['toolbar', 'context'], when: hasClip, run: () => { an().togglePlay(false); an().setFrame(0) } },
  { id: 'anim.end', scope: 'animate', label: 'Last frame', icon: ChevronLast, keys: 'End', placement: ['toolbar', 'context'], when: hasClip, run: () => { an().togglePlay(false); an().setFrame((an().clip()?.frames ?? 1) - 1) } },
  { id: 'anim.shuttleBack', scope: 'animate', label: 'Shuttle backward (J)', icon: SkipBack, keys: 'J', placement: ['context'], when: hasClip, run: () => { const s = an(); useAnimate.setState({ speed: s.speed > 0 ? -1 : Math.max(-4, s.speed * 2) }); s.togglePlay(true) } },
  { id: 'anim.shuttleStop', scope: 'animate', label: 'Stop (K)', icon: Pause, keys: 'K', placement: ['context'], when: hasClip, run: () => { useAnimate.setState({ speed: 1 }); an().togglePlay(false) } },
  { id: 'anim.shuttleFwd', scope: 'animate', label: 'Shuttle forward (L)', icon: SkipForward, keys: 'L', placement: ['context'], when: hasClip, run: () => { const s = an(); useAnimate.setState({ speed: s.speed < 0 ? 1 : Math.min(4, s.speed * 2) }); s.togglePlay(true) } },
  { id: 'anim.setIn', scope: 'animate', label: 'Set in point', icon: Scissors, keys: 'I', placement: ['toolbar', 'context'], when: hasClip, run: () => an().setInOut('in') },
  { id: 'anim.setOut', scope: 'animate', label: 'Set out point', icon: Scissors, keys: 'O', placement: ['toolbar', 'context'], when: hasClip, run: () => an().setInOut('out') },
  { id: 'anim.clearInOut', scope: 'animate', label: 'Clear in / out', icon: SquareX, placement: ['toolbar', 'context'], when: () => an().inPoint !== null || an().outPoint !== null, run: () => an().setInOut('clear') },
  { id: 'anim.loop', scope: 'animate', label: 'Loop', icon: Repeat, placement: ['strip', 'context'], run: () => useAnimate.setState({ loop: !an().loop }) },
  { id: 'anim.onion', scope: 'animate', label: 'Onion skin (start / end stills at 30 %)', icon: Eye, keys: 'N', placement: ['strip', 'context'], when: hasClip, run: () => useAnimate.setState({ onion: !an().onion }) },
  { id: 'anim.view.player', scope: 'animate', label: 'Player view', icon: Film, placement: ['strip'], run: () => an().setView('player') },
  { id: 'anim.view.filmstrip', scope: 'animate', label: 'Frames track (thumbnails on the timeline)', icon: Layers, placement: ['strip'], run: () => useAnimate.setState({ filmTrack: !an().filmTrack }) },   // D99 (UX0 #14)
  { id: 'anim.view.compare', scope: 'animate', label: 'Compare view', icon: Columns2, keys: 'C', placement: ['strip', 'context'], when: hasClip, run: () => an().setView(an().view === 'compare' ? 'player' : 'compare') },
  // frames
  { id: 'anim.extractFrame', scope: 'animate', label: 'Extract frame to the Catalogue', icon: Download, keys: 'Alt+F', placement: ['inspector', 'context', 'toolbar'], when: hasClip, run: () => void an().extract([an().frame]) },
  { id: 'anim.extractRange', scope: 'animate', label: 'Extract range (every k-th frame between in and out)', icon: Download, keys: 'Alt+Shift+F', placement: ['inspector', 'context'], when: hasClip, run: () => void an().extractRange() },
  { id: 'anim.sendToEdit', scope: 'animate', label: 'Send frame to Edit', icon: Sparkles, keys: 'E', placement: ['inspector', 'context'], when: hasClip, run: () => void an().sendFrameToEdit() },
  { id: 'anim.extend', scope: 'animate', label: 'Extend ▶ (experimental)', icon: Clapperboard, placement: ['inspector', 'context'],
    when: () => { const c = an().clip(); return !!c && !!useSession.getState().capabilities?.experimental?.extend.models[c.model_id] },
    run: () => void extendClip() },
  { id: 'anim.useAsStart', scope: 'animate', label: 'Use frame as next start', icon: Clapperboard, placement: ['inspector', 'context'], when: hasClip, run: () => void an().useFrameAsStart() },
  // clip verbs
  { id: 'anim.keep', scope: 'animate', label: 'Keep', icon: Check, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().setState('keep') },
  { id: 'anim.reject', scope: 'animate', label: 'Reject', icon: X, keys: 'X', placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().setState('reject') },
  { id: 'anim.variations', scope: 'animate', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['inspector', 'context'], when: hasClip, run: () => void an().variations() },
  { id: 'anim.rerun', scope: 'animate', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['inspector', 'context'], when: hasClip, run: () => void an().rerun() },
  { id: 'anim.tryOther', scope: 'animate', label: 'Try the other model', icon: Shuffle, placement: ['inspector', 'context'], when: hasClip, run: () => void an().tryOther() },
  { id: 'anim.identity', scope: 'animate', label: 'Measure identity (FaceSim)', icon: Eye, placement: ['inspector', 'context'], when: () => hasClip() && !!useSession.getState().capabilities?.facesim?.available, run: () => void an().measureIdentity() },
  // 17 SY2 (D85): the clip becomes a Story shot's clip (version 1)
  { id: 'anim.toShot', scope: 'animate', label: 'Make a shot from this clip…', icon: Clapperboard, placement: ['inspector', 'context', 'toolbar'], when: hasClip,
    run: () => { const c = an().clip(); if (!c) return
      void askText({ title: 'Make a shot from this clip', text: 'A Story shot with this clip as its clip; mark it final there once it is at the project format.', initial: (c.prompt || 'Shot').split(/[,.]/)[0].slice(0, 40), placeholder: 'shot name' })
        .then((n) => { if (n?.trim()) void import('../story/storyStore').then((m) => m.makeShotAndOpen(n.trim(), { clip_id: c.id })) }) } },
  // D90 (02 §9, A8): a clip goes to the Trash as in the Catalogue (Undo in the toast; Empty trash deletes it)
  { id: 'anim.trash', scope: 'animate', label: 'Move to trash', icon: Trash, danger: true, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().trashClip() },
  { id: 'anim.toCatalogue', scope: 'animate', label: 'Show in Catalogue', icon: Film, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => { useSession.getState().setSuite('catalogue'); void import('../catalogue/catalogueStore').then((m) => { const c = m.useCatalogue.getState(); void c.setQuery({ folder: 'clips' }).then(() => { const id = an().clip()?.asset_id; if (id) c.select(id, 'single') }) }) } },
])

/** D88 XE (experimental): continue the clip on its own model — the prompt is the clip's, editable; the caveat said before the job. */
async function extendClip(): Promise<void> {
  const c = an().clip(); const s = useSession.getState(); const ex = s.capabilities?.experimental?.extend
  if (!c || !ex) return
  const lead = ex.models[c.model_id]
  const prompt = await askText({ title: 'Extend this clip (experimental)', initial: c.prompt, placeholder: 'what happens next',
    text: `A continuation on ${s.capabilities?.i2v?.models[c.model_id]?.label ?? c.model_id}: ${c.frames} frames from this clip's ${lead === 1 ? 'last frame' : `last ${lead} frames`}. ${ex.caveat}.` })
  if (prompt === null || prompt === undefined) return
  try {
    const r = await unwrap(http.POST('/clips/{clip_id}/extend', { params: { path: { clip_id: c.id } }, body: { prompt_text: prompt, stage: false } }))
    await s.refreshAll()
    s.toast(`Extension queued (experimental) — it continues ${c.id} from its last ${r.lead === 1 ? 'frame' : `${r.lead} frames`}`, 'success')
  } catch (e) { s.toast(`Extend: ${(e as ApiError).detail ?? e}`, 'error') }
}

/** Right-click on the player / timeline. D90 (A1, A3): J / K / L under Shuttle; Onion and Loop are their commands (the toggles' state
 *  checked); Make a shot and Measure identity are here as their placements say. */
export function playerMenu(): MenuItem[] {
  const s = an()
  return [
    { cmd: 'anim.play', label: s.playing ? 'Pause' : 'Play' }, { cmd: 'anim.stepBack' }, { cmd: 'anim.stepForward' }, { cmd: 'anim.home' }, { cmd: 'anim.end' },
    { label: 'Shuttle', icon: SkipForward, items: [{ cmd: 'anim.shuttleBack' }, { cmd: 'anim.shuttleStop' }, { cmd: 'anim.shuttleFwd' }] }, sep,
    { cmd: 'anim.setIn' }, { cmd: 'anim.setOut' }, { cmd: 'anim.clearInOut' }, sep,
    { cmd: 'anim.extractFrame' }, { cmd: 'anim.extractRange' }, { cmd: 'anim.sendToEdit' }, { cmd: 'anim.useAsStart' }, { cmd: 'anim.extend' }, sep,
    { cmd: 'anim.onion', checked: s.onion }, { cmd: 'anim.loop', checked: s.loop },
    { cmd: 'anim.view.compare', label: s.view === 'compare' ? 'Leave compare' : 'Compare…' }, sep,
    { cmd: 'anim.keep' }, { cmd: 'anim.reject' }, { cmd: 'anim.variations' }, { cmd: 'anim.rerun' }, { cmd: 'anim.tryOther' }, { cmd: 'anim.identity' }, sep,
    { cmd: 'anim.toShot' }, { cmd: 'anim.toCatalogue' },
  ]
}

/** D90 (02 §9, A16): right-click on a row of the Clips tab (the clip is selected first). */
export function clipMenu(id: string): MenuItem[] {
  if (an().current !== id) an().select(id)
  return [{ cmd: 'anim.toCatalogue' }, sep, { cmd: 'anim.keep' }, { cmd: 'anim.reject' }, sep, { cmd: 'anim.toShot' }, sep, { cmd: 'anim.trash' }]
}
