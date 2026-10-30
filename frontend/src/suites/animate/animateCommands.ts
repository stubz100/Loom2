// Animate commands (11 §9, 07 §3c, D32): one definition each for the transport buttons, the strip, the inspector verbs,
// the right-click menus and the keys. Keys are accelerators for buttons that exist anyway.
import { Workflow, ArrowLeftRight, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, Columns2, Diamond, Download, Eye, Film, Frame, Layers, Pause, PersonStanding, Play, Repeat, RotateCcw, Scissors, Shuffle, SkipBack, SkipForward, Sparkles, SquarePlus, SquareX, StepBack, StepForward, Trash, X } from 'lucide-react'
import { command, isEnabled, registerCommands, runCommand, sep, setReach, type Command, type MenuItem } from '../../frame/commands'
import { http, unwrap, type ApiError } from '../../api/client'
import { askText, useSession } from '../../store/session'
import { useAnimate } from './animateStore'
import { useComposition } from './compositionStore'
import { useAnimRoute } from './routeStore'
import { useMakeFor } from '../../store/origin'
import { useStory } from '../story/storyStore'
import { neighbour, transport, TRANSPORT_IDS } from './transport'
import { keyAt, trackOf, useWindows } from './windowsStore'

const wn = () => useWindows.getState()
/** D165: the Windows view's selected box — its layer's boxes and the kind. */
const winSel = () => { const { sel, data } = wn(); const l = sel ? data?.layers.find((x) => x.id === sel.lid) : null; return sel && l ? { l, kind: sel.kind } : null }
import { ArrowDown as ArrowDownIcon, ArrowUp as ArrowUpIcon, Circle as EllipseIcon, Crosshair as SoloIcon, Diamond as KeyIcon, EyeOff as HideIcon, Lock as LockIcon, Redo2 as RedoIcon,
  Square as RectIcon, Undo2 as UndoIcon, ArrowLeftToLine as TrimInIcon, ArrowRightToLine as TrimOutIcon, Columns2 as BeforeIcon, PenTool as PenIcon,
  Scan as FromLayerIcon, MousePointerClick as ObjectIcon, PaintBucket as FillIcon, Route as TrackIcon, Wand2 as PassIcon } from 'lucide-react'
import { navigate } from '../../frame/router'

const an = () => useAnimate.getState()
const cp = () => useComposition.getState()
const hasClip = () => !!an().clip()
/** D125 (A4): the version Animate's For chip names (read from Story's shots), or undefined. */
const forVersion = () => { const f = useMakeFor.getState().animate; return f ? useStory.getState().shots.find((x) => x.id === f.shot_id)?.versions.find((v) => v.id === f.version) : undefined }
/** D125 (A4): the clip's Story verb for menus — Use it as the For chip's shot's clip, else Make a shot from it. */
export const clipShotItem = (): MenuItem => { const f = useMakeFor.getState().animate; return f ? { cmd: 'anim.useClip', label: `Use as ${f.name}'s clip` } : { cmd: 'anim.toShot' } }
/** D121 (AW2): the transport of the level on screen (transport.ts); the clip player's own verbs only at Performance. */
const tp = () => transport()
const ready = () => !!tp()?.ready()
const perfClip = () => useSession.getState().ui.suite === 'animate' && hasClip()
const hasStart = () => !!an().panel.start
/** D121: the Final level is the `final` suite; Performance's own commands stay off there (they share the animate scope's keys). */
const atFinal = () => useSession.getState().ui.suite === 'final' && !!cp().comp
/** D121: the command behind the Performance card's verb (the stage's commands register with the stage's code, which Performance loads). */
const cardCmd = () => { const r = useAnimRoute.getState().route; return r === 'clip' ? 'stage.clip.animate' : r === 'final' ? 'stage.final.next' : 'anim.animate' }
const cardOn = () => { const c = command(cardCmd()); return !!c && isEnabled(c) }
/** The open final's composition is being rendered (a comp_render job queued or running). */
const compRendering = () => { const id = cp().finalId; return !!id && Object.values(useSession.getState().jobs).some((j) => j.kind === 'comp_render' && j.origin?.ref === id && (j.status === 'queued' || j.status === 'running')) }
const selLayer = () => (atFinal() ? cp().layers.find((l) => l.id === cp().selected) ?? null : null)
const hasSel = () => !!selLayer()

registerCommands([
  // render
  { id: 'anim.animate', scope: 'animate', label: 'Animate', icon: Clapperboard, placement: ['panel'], when: hasStart, run: () => void an().animate(false) },
  // D121: Ctrl+Enter is the Performance card's verb — Animate ▶ (image to video), Render clip ▶ (the stage clip), the final shot's next step
  { id: 'anim.run', scope: 'animate', label: "Run the card's verb", hint: "Animate ▶, Render clip ▶ or the final shot's next step — the Performance card decides", icon: Clapperboard, keys: 'Ctrl+Enter', placement: ['panel'],
    when: () => useSession.getState().ui.suite === 'animate' && cardOn(), run: () => { runCommand(cardCmd()) } },
  { id: 'anim.stage', scope: 'animate', label: 'Queue', hint: 'add to the queue and run it later — Run now in the Dock', icon: Layers, keys: 'Ctrl+Shift+Enter', placement: ['panel'], when: hasStart, run: () => void an().animate(true) },
  { id: 'anim.swap', scope: 'animate', label: 'Swap start and end', icon: ArrowLeftRight, placement: ['panel'], when: () => !!an().panel.end, run: () => an().swap() },
  { id: 'anim.clearStart', scope: 'animate', label: 'Clear start frame', icon: X, placement: ['panel', 'context'], when: hasStart, run: () => an().setStart(null) },
  { id: 'anim.clearEnd', scope: 'animate', label: 'Clear end frame', icon: X, placement: ['panel', 'context'], when: () => !!an().panel.end, run: () => an().setEnd(null) },
  // transport — D90 (02 §8.2): the one key set of Animate, the Stage timeline and the Episode lane; `,` `.` and Shift+, / Shift+. stay as alternates
  // D99 (UX0 #19): the viewer levels by number — 1 goes to Clay (the stage) from here; the strip's switch is their mouse home
  { id: 'anim.level.clay', scope: 'animate', label: 'Shots · Clay', keys: '1', placement: ['strip'], run: () => navigate({ suite: 'stage' }) },
  // AE1 / AP1 (D114): the Final level — the composition's frames; its own transport (the clip player's keys stay the clip's)
  { id: 'anim.level.performance', scope: 'animate', label: 'Shots · Performance', keys: '2', placement: ['strip'], run: () => navigate({ suite: 'animate' }) },
  { id: 'anim.level.final', scope: 'animate', label: 'Shots · Final', keys: '3', placement: ['strip'], run: () => navigate({ suite: 'final' }) },
  // RC1 (D96, proto01_animate 28): the Graph — the For chip's shot's recipe over the viewer, in whichever mode is on
  { id: 'anim.level.graph', scope: 'animate', label: "Animate · Graph (the shot's recipe)", icon: Workflow, keys: '4', placement: ['strip'], run: () => { const s = useSession.getState(); s.setUi({ graph: !s.ui.graph }) } },
  // D121 (AW3): the Shot stepper's steps — each opens the level and card where the step's verb is (the foot); the frame's is stage.frame.make
  { id: 'anim.step.passes', scope: 'animate', label: 'The passes (Shots · Clay)', icon: Layers, placement: ['panel'], run: () => navigate({ suite: 'stage' }) },
  { id: 'anim.step.clip', scope: 'animate', label: "The stage's clip (Performance · Stage clip)", icon: Clapperboard, placement: ['panel'], run: () => { useAnimRoute.getState().set('clip'); navigate({ suite: 'animate' }) } },
  { id: 'anim.step.final', scope: 'animate', label: 'The final shot (Performance · Final shot)', icon: Layers, placement: ['panel'], run: () => { useAnimRoute.getState().set('final'); navigate({ suite: 'animate' }) } },
  { id: 'anim.step.final.open', scope: 'animate', label: "The final's composition (Shots · Final)", icon: Film, placement: ['panel'],
    run: () => void Promise.all([import('../stage/finalShot'), import('../stage/stageStore')]).then(([m, s]) => {     // the stage's newest final with a composition, else the Final level as it is
      const id = s.useStage.getState().current?.id
      const f = m.newestFinal(m.useFinals.getState().finals, id)
      if (f && m.useFinals.getState().compositions[f.id]) m.useFinals.getState().openFinal(f.id); else navigate({ suite: 'final' })
    }) },
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
  { id: 'anim.final.mask.poly', scope: 'animate', label: 'Mask: pen', hint: 'click the points of a shape on the frame; the first point again (or a double-click) closes it, Esc drops it', icon: PenIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => cp().setMaskTool(cp().maskTool === 'poly' ? 'off' : 'poly') },
  // D116: the layer's visible content traced into a mask (a character's silhouette from her matte, a prop's alpha, the shadows), keyed on every frame
  { id: 'anim.final.mask.layer', scope: 'animate', label: 'Mask: from the layer', hint: "the layer's visible content at the playhead, traced into a mask that follows it across the shot", icon: FromLayerIcon, placement: ['toolbar', 'context'], when: () => hasSel() && !cp().busy, run: () => void cp().maskFromLayer(true) },
  { id: 'anim.final.mask.object', scope: 'animate', label: 'Mask: object', hint: "click a thing on the frame: EffectCraft's Object Matte cuts the layer to it and follows it across the shot (an effect on the layer)", icon: ObjectIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => cp().setMaskTool(cp().maskTool === 'object' ? 'off' : 'object') },
  { id: 'anim.final.mask.track', scope: 'animate', label: 'Mask: follow the motion', hint: "EffectCraft tracks what is inside the selected mask from the playhead to the end and keys its shape on every frame", icon: TrackIcon, placement: ['toolbar', 'context'], when: () => hasSel() && cp().selectedMask !== null && !cp().busy, run: () => void cp().trackMask() },
  { id: 'anim.final.mask.view', scope: 'animate', label: 'Mask fill', hint: 'show the masks filled instead of as outlines (like Quick mask in Edit)', icon: FillIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => cp().setMaskView(cp().maskView === 'fill' ? 'lines' : 'fill') },
  // D118 (AE4a): a pass on the selected layer — the preset and strength chosen in the Passes part; its take becomes the layer's source
  { id: 'anim.final.pass.run', scope: 'animate', label: 'Run the pass', hint: "the chosen pass over the layer's frames (or the stack from it down) as a GPU job; its result a take the layer shows, or a processing layer above it", icon: PassIcon, placement: ['toolbar', 'context'], when: () => cp().finalLayerId() !== null || cp().pointLayerId() !== null, run: () => void cp().runPass() },
  // AE4e: a processing layer — the pass over the stack below, run again when stale, dropped
  { id: 'anim.final.proc.again', scope: 'animate', label: 'Process again', hint: 'the same pass over the stack below, replacing this processing layer (it reads stale when a layer below changed)', icon: RotateCcw, placement: ['toolbar', 'context'], when: () => cp().selected !== null && !!cp().processingOf(cp().selected!), run: () => void cp().runProcessingAgain() },
  { id: 'anim.final.proc.remove', scope: 'animate', label: 'Remove the processing layer', hint: 'its frames too; the layers below stay as they are', icon: SquareX, placement: ['toolbar', 'context'], when: () => cp().selected !== null && !!cp().processingOf(cp().selected!), run: () => { const p = cp().selected !== null ? cp().processingOf(cp().selected!) : null; if (p) void cp().removeProcessing(p.id) } },
  { id: 'anim.final.trimIn', scope: 'animate', label: 'Trim in to the playhead', icon: TrimInIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().setTiming(cp().selected!, { in: cp().frame / (cp().final?.rate ?? 16) }) },
  { id: 'anim.final.trimOut', scope: 'animate', label: 'Trim out to the playhead', icon: TrimOutIcon, placement: ['toolbar', 'context'], when: hasSel, run: () => void cp().setTiming(cp().selected!, { out: (cp().frame + 1) / (cp().final?.rate ?? 16) }) },
  // AE3: before / after — the frame with every effect off (nothing saved)
  // D121: the Final level's foot — the composition rendered into the finished shot (effectcraft-cli on the CPU); finalShot loads with the stage's code
  { id: 'anim.final.render', scope: 'animate', label: 'Render the finished shot', hint: "the composition at Best and Full on the CPU; the clip becomes the final's and a take on its shot", icon: Film, keys: 'Ctrl+Enter', placement: ['panel'], when: () => atFinal() && !compRendering(),
    run: () => { const id = cp().finalId; if (id) void import('../stage/finalShot').then((m) => m.useFinals.getState().render(id)) } },
  { id: 'anim.final.before', scope: 'animate', label: 'Before', hint: 'the frame with every effect off; again for after', icon: BeforeIcon, placement: ['toolbar', 'context'], when: atFinal, run: () => void cp().compareBefore(!cp().before) },
  // D121 (AW2): the one transport of Animate's three levels — each runs the transport of the level on screen (transport.ts: the stage at Clay,
  // the clip at Performance, the composition at Final); the key set of D90 / D99, the same at every level and in the Episode lane
  { id: 'anim.play', scope: 'animate', label: 'Play / pause', icon: Play, keys: 'Space', placement: ['toolbar', 'context'], when: ready, run: () => tp()?.play() },
  { id: 'anim.stepBack', scope: 'animate', label: 'Previous frame', icon: StepBack, keys: 'ArrowLeft', alt: [','], placement: ['toolbar', 'context'], when: ready, run: () => tp()?.step(-1) },
  { id: 'anim.stepForward', scope: 'animate', label: 'Next frame', icon: StepForward, keys: 'ArrowRight', alt: ['.'], placement: ['toolbar', 'context'], when: ready, run: () => tp()?.step(1) },
  { id: 'anim.back10', scope: 'animate', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+ArrowLeft', alt: ['Shift+,', '<'], placement: ['toolbar'], when: ready, run: () => tp()?.step(-10) },
  { id: 'anim.fwd10', scope: 'animate', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+ArrowRight', alt: ['Shift+.', '>'], placement: ['toolbar'], when: ready, run: () => tp()?.step(10) },
  { id: 'anim.home', scope: 'animate', label: 'First frame', hint: "at Clay the range's start", icon: ChevronFirst, keys: 'Home', placement: ['toolbar', 'context'], when: ready, run: () => tp()?.home() },
  { id: 'anim.end', scope: 'animate', label: 'Last frame', hint: "at Clay the range's end", icon: ChevronLast, keys: 'End', placement: ['toolbar', 'context'], when: ready, run: () => tp()?.end() },
  { id: 'anim.prevKey', scope: 'animate', label: 'Previous key', hint: "the stage's keys, the clip's beats and harvested frames, the selected layer's keys", icon: SkipBack, keys: 'Alt+ArrowLeft', placement: ['toolbar'],
    when: () => !!tp()?.marks && neighbour(tp()!.marks!(), tp()!.frame(), -1) !== null, run: () => { const t = tp(); const f = t?.marks ? neighbour(t.marks(), t.frame(), -1) : null; if (t && f !== null) t.seek(f) } },
  { id: 'anim.nextKey', scope: 'animate', label: 'Next key', hint: "the stage's keys, the clip's beats and harvested frames, the selected layer's keys", icon: SkipForward, keys: 'Alt+ArrowRight', placement: ['toolbar'],
    when: () => !!tp()?.marks && neighbour(tp()!.marks!(), tp()!.frame(), 1) !== null, run: () => { const t = tp(); const f = t?.marks ? neighbour(t.marks(), t.frame(), 1) : null; if (t && f !== null) t.seek(f) } },
  { id: 'anim.shuttleBack', scope: 'animate', label: 'Shuttle backward (J)', icon: SkipBack, keys: 'J', placement: ['context'], when: perfClip, run: () => { const s = an(); useAnimate.setState({ speed: s.speed > 0 ? -1 : Math.max(-4, s.speed * 2) }); s.togglePlay(true) } },
  { id: 'anim.shuttleStop', scope: 'animate', label: 'Stop (K)', icon: Pause, keys: 'K', placement: ['context'], when: perfClip, run: () => { useAnimate.setState({ speed: 1 }); an().togglePlay(false) } },
  { id: 'anim.shuttleFwd', scope: 'animate', label: 'Shuttle forward (L)', icon: SkipForward, keys: 'L', placement: ['context'], when: perfClip, run: () => { const s = an(); useAnimate.setState({ speed: s.speed < 0 ? 1 : Math.min(4, s.speed * 2) }); s.togglePlay(true) } },
  { id: 'anim.setIn', scope: 'animate', label: 'Set in point', hint: "the work area's start here — at Clay the stage's range", icon: Scissors, keys: 'I', placement: ['toolbar', 'context'], when: () => ready() && !!tp()?.setIn, run: () => tp()?.setIn?.() },
  { id: 'anim.setOut', scope: 'animate', label: 'Set out point', hint: "the work area's end here — at Clay the stage's range", icon: Scissors, keys: 'O', placement: ['toolbar', 'context'], when: () => ready() && !!tp()?.setOut, run: () => tp()?.setOut?.() },
  { id: 'anim.clearInOut', scope: 'animate', label: 'Clear in / out', icon: SquareX, placement: ['toolbar', 'context'], when: () => !!tp()?.hasInOut?.(), run: () => tp()?.clearInOut?.() },
  { id: 'anim.loop', scope: 'animate', label: 'Loop', icon: Repeat, placement: ['strip', 'context'], run: () => useAnimate.setState({ loop: !an().loop }) },
  { id: 'anim.onion', scope: 'animate', label: 'Onion skin (start / end stills at 30 %)', icon: Eye, keys: 'N', placement: ['strip', 'context'], when: hasClip, run: () => useAnimate.setState({ onion: !an().onion }) },
  { id: 'anim.view.player', scope: 'animate', label: 'Player view', icon: Film, placement: ['strip'], run: () => an().setView('player') },
  { id: 'anim.view.filmstrip', scope: 'animate', label: 'Frames track (thumbnails on the timeline)', icon: Layers, placement: ['strip'], run: () => useAnimate.setState({ filmTrack: !an().filmTrack }) },   // D99 (UX0 #14)
  { id: 'anim.view.compare', scope: 'animate', label: 'Compare view', icon: Columns2, keys: 'C', placement: ['strip', 'context'], when: hasClip, run: () => an().setView(an().view === 'compare' ? 'player' : 'compare') },
  // D165: the Windows view — each character's window and head box, keyframed by hand before the GPU time is spent
  { id: 'anim.view.windows', scope: 'animate', label: "Windows view (each character's window and head box, by hand)", icon: Frame, placement: ['strip'], when: () => useAnimRoute.getState().route === 'final',
    run: () => an().setView(an().view === 'windows' ? 'player' : 'windows') },
  { id: 'anim.windows.key', scope: 'animate', label: 'Key the box here', icon: Diamond, placement: ['panel', 'context'], when: () => !!winSel(), run: () => void wn().keyHere(),
    hint: 'the box as it is at this frame becomes a key (the automatic keys become yours first)' },
  { id: 'anim.windows.deleteKey', scope: 'animate', label: 'Delete the key here', icon: X, placement: ['panel', 'context'], when: () => { const s = winSel(); return !!s && keyAt(s.l, s.kind, wn().frame) }, run: () => void wn().deleteKey() },
  { id: 'anim.windows.auto', scope: 'animate', label: 'Back to automatic', icon: RotateCcw, placement: ['panel', 'context'], when: () => { const s = winSel(); return !!s && trackOf(s.l, s.kind).mode !== 'auto' },
    run: () => { const s = winSel(); if (s) void wn().setMode({ lid: s.l.id, kind: s.kind }, 'auto') } },
  { id: 'anim.windows.remove', scope: 'animate', label: 'Remove the box', icon: SquareX, placement: ['panel', 'context'], when: () => { const s = winSel(); return !!s && trackOf(s.l, s.kind).mode !== 'none' },
    run: () => { const s = winSel(); if (s) void wn().setMode({ lid: s.l.id, kind: s.kind }, 'none') } },
  { id: 'anim.windows.add', scope: 'animate', label: 'Add the box', icon: SquarePlus, placement: ['panel', 'context'],
    when: () => { const s = winSel(); return !!s && !trackOf(s.l, s.kind).frames.length && trackOf(s.l, s.kind).offer.length > 0 },
    run: () => { const s = winSel(); if (s) void wn().add({ lid: s.l.id, kind: s.kind }) } },
  { id: 'anim.windows.skeletons', scope: 'animate', label: 'Skeletons over the frame', icon: PersonStanding, placement: ['panel'], run: () => useWindows.setState({ skeletons: !wn().skeletons }) },
  // frames
  { id: 'anim.extractFrame', scope: 'animate', label: 'Extract frame to the Bin', icon: Download, keys: 'Alt+F', placement: ['inspector', 'context', 'toolbar'], when: hasClip, run: () => void an().extract([an().frame]) },
  { id: 'anim.extractRange', scope: 'animate', label: 'Extract range (every k-th frame between in and out)', icon: Download, keys: 'Alt+Shift+F', placement: ['inspector', 'context'], when: hasClip, run: () => void an().extractRange() },
  { id: 'anim.sendToEdit', scope: 'animate', label: 'Send frame to Edit', icon: Sparkles, keys: 'E', placement: ['inspector', 'context'], when: hasClip, run: () => void an().sendFrameToEdit() },
  { id: 'anim.extend', scope: 'animate', label: 'Extend ▶ (experimental)', icon: Clapperboard, placement: ['inspector', 'context'],
    when: () => { const c = an().clip(); return !!c && !!useSession.getState().capabilities?.experimental?.extend.models[c.model_id] },
    run: () => void extendClip() },
  { id: 'anim.useAsStart', scope: 'animate', label: 'Use frame as next start', icon: Clapperboard, placement: ['inspector', 'context'], when: hasClip, run: () => void an().useFrameAsStart() },
  // clip verbs
  { id: 'anim.variations', scope: 'animate', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['inspector', 'context'], when: hasClip, run: () => void an().variations() },
  { id: 'anim.rerun', scope: 'animate', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['inspector', 'context'], when: hasClip, run: () => void an().rerun() },
  { id: 'anim.tryOther', scope: 'animate', label: 'Try the other model', icon: Shuffle, placement: ['inspector', 'context'], when: hasClip, run: () => void an().tryOther() },
  { id: 'anim.identity', scope: 'animate', label: 'Measure identity (FaceSim)', icon: Eye, placement: ['inspector', 'context'], when: () => hasClip() && !!useSession.getState().capabilities?.facesim?.available, run: () => void an().measureIdentity() },
  // D125 (A4): with the For chip the clip becomes that shot version's clip where it is played (no second shot)
  { id: 'anim.useClip', scope: 'animate', label: "Use as the shot's clip", icon: Clapperboard, placement: ['inspector', 'context', 'toolbar'], hint: "Animate is making for a shot (the For chip): this clip becomes that version's clip",
    when: () => { const c = an().clip(); const v = forVersion(); return !!c && !!v && v.state === 'open' && v.clip_id !== c.id },
    run: () => { const f = useMakeFor.getState().animate; const c = an().clip(); if (f && c) void useStory.getState().takeFor(f, 'clip', c.id) } },
  // 17 SY2 (D85): the clip becomes a Story shot's clip (version 1); D125 (A4): only without a For chip
  { id: 'anim.toShot', scope: 'animate', label: 'Make a shot from this clip…', icon: Clapperboard, placement: ['inspector', 'context', 'toolbar'], when: () => hasClip() && !useMakeFor.getState().animate,
    run: () => { const c = an().clip(); if (!c) return
      void askText({ title: 'Make a shot from this clip', text: 'A Story shot with this clip as its clip; mark it final there once it is at the project format.', initial: (c.prompt || 'Shot').split(/[,.]/)[0].slice(0, 40), placeholder: 'shot name' })
        .then((n) => { if (n?.trim()) void import('../story/storyStore').then((m) => m.makeShotAndOpen(n.trim(), { clip_id: c.id })) }) } },
  // D90 (02 §9, A8): a clip goes to the Trash as in the Catalogue (Undo in the toast; Empty trash deletes it)
  { id: 'anim.trash', scope: 'animate', label: 'Move to trash', icon: Trash, danger: true, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().trashClip() },
  { id: 'anim.toCatalogue', scope: 'animate', label: 'Show in the Bin', icon: Film, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id,   // B2 (D159): the clip in its home
    run: () => { const id = an().clip()?.asset_id; if (!id) return; navigate({ suite: 'catalogue' }); void import('../../ui2/bin/binStore').then((m) => void m.useBin.getState().reveal(id)) } },
])

// D121: what each mode's keys reach (commands.ts reachOf), one rule for its key hook, the help overlay and the palette. The three share the
// one transport, the mode switches (1 · 2 · 3) and the Shot head's commands (the stepper, the For chip); Clay adds the stage's own,
// Performance the rest of this scope but Final's, Final its own.
const shared = (c: Command) => TRANSPORT_IDS.has(c.id) || /^anim\.(level|step|for)\./.test(c.id)
setReach('stage', [{ scope: 'stage' }, { scope: 'animate', only: shared }])
setReach('animate', [{ scope: 'animate', only: (c) => !c.id.startsWith('anim.final.') }])
setReach('final', [{ scope: 'animate', only: (c) => c.id.startsWith('anim.final.') || shared(c) }])

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
    { cmd: 'anim.variations' }, { cmd: 'anim.rerun' }, { cmd: 'anim.tryOther' }, { cmd: 'anim.identity' }, sep,
    clipShotItem(), { cmd: 'anim.toCatalogue' },
  ]
}

/** D90 (02 §9, A16): right-click on a row of the Clips tab (the clip is selected first). */
export function clipMenu(id: string): MenuItem[] {
  if (an().current !== id) an().select(id)
  return [{ cmd: 'anim.toCatalogue' }, sep, clipShotItem(), sep, { cmd: 'anim.trash' }]
}
