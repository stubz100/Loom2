// Animate commands (11 §9, 07 §3c, D32): one definition each for the transport buttons, the strip, the inspector verbs,
// the right-click menus and the keys. Keys are accelerators for buttons that exist anyway.
import { ArrowLeftRight, Check, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, Columns2, Download, Eye, Film, Layers, Pause, Play, Repeat, RotateCcw, Scissors, Shuffle, SkipBack, SkipForward, Sparkles, SquareX, StepBack, StepForward, X } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { useSession } from '../../store/session'
import { useAnimate } from './animateStore'

const an = () => useAnimate.getState()
const hasClip = () => !!an().clip()
const hasStart = () => !!an().panel.start

registerCommands([
  // render
  { id: 'anim.animate', scope: 'animate', label: 'Animate', icon: Clapperboard, keys: 'Ctrl+Enter', placement: ['panel'], when: hasStart, run: () => void an().animate(false) },
  { id: 'anim.stage', scope: 'animate', label: 'Stage (add to the queue, run later)', icon: Layers, keys: 'Ctrl+Shift+Enter', placement: ['panel'], when: hasStart, run: () => void an().animate(true) },
  { id: 'anim.swap', scope: 'animate', label: 'Swap start and end', icon: ArrowLeftRight, placement: ['panel'], when: () => !!an().panel.end, run: () => an().swap() },
  { id: 'anim.clearStart', scope: 'animate', label: 'Clear start frame', icon: X, placement: ['panel', 'context'], when: hasStart, run: () => an().setStart(null) },
  { id: 'anim.clearEnd', scope: 'animate', label: 'Clear end frame', icon: X, placement: ['panel', 'context'], when: () => !!an().panel.end, run: () => an().setEnd(null) },
  // transport
  { id: 'anim.play', scope: 'animate', label: 'Play / pause', icon: Play, keys: 'Space', placement: ['toolbar', 'context'], when: hasClip, run: () => an().togglePlay() },
  { id: 'anim.stepBack', scope: 'animate', label: 'Previous frame', icon: StepBack, keys: ',', placement: ['toolbar', 'context'], when: hasClip, run: () => an().step(-1) },
  { id: 'anim.stepForward', scope: 'animate', label: 'Next frame', icon: StepForward, keys: '.', placement: ['toolbar', 'context'], when: hasClip, run: () => an().step(1) },
  { id: 'anim.back10', scope: 'animate', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+,', alt: ['<'], placement: ['toolbar'], when: hasClip, run: () => an().step(-10) },
  { id: 'anim.fwd10', scope: 'animate', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+.', alt: ['>'], placement: ['toolbar'], when: hasClip, run: () => an().step(10) },
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
  { id: 'anim.view.filmstrip', scope: 'animate', label: 'Filmstrip view', icon: Layers, placement: ['strip'], run: () => an().setView('filmstrip') },
  { id: 'anim.view.compare', scope: 'animate', label: 'Compare view', icon: Columns2, keys: 'C', placement: ['strip', 'context'], when: hasClip, run: () => an().setView(an().view === 'compare' ? 'player' : 'compare') },
  // frames
  { id: 'anim.extractFrame', scope: 'animate', label: 'Extract frame to the Catalogue', icon: Download, keys: 'F', placement: ['inspector', 'context', 'toolbar'], when: hasClip, run: () => void an().extract([an().frame]) },
  { id: 'anim.extractRange', scope: 'animate', label: 'Extract range (every k-th frame between in and out)', icon: Download, keys: 'Shift+F', placement: ['inspector', 'context'], when: hasClip, run: () => void an().extractRange() },
  { id: 'anim.sendToEdit', scope: 'animate', label: 'Send frame to Edit', icon: Sparkles, keys: 'E', placement: ['inspector', 'context'], when: hasClip, run: () => void an().sendFrameToEdit() },
  { id: 'anim.useAsStart', scope: 'animate', label: 'Use frame as next start', icon: Clapperboard, placement: ['inspector', 'context'], when: hasClip, run: () => void an().useFrameAsStart() },
  // clip verbs
  { id: 'anim.keep', scope: 'animate', label: 'Keep', icon: Check, keys: 'Shift+K', placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().setState('keep') },
  { id: 'anim.reject', scope: 'animate', label: 'Reject', icon: X, keys: 'X', placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => void an().setState('reject') },
  { id: 'anim.variations', scope: 'animate', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['inspector', 'context'], when: hasClip, run: () => void an().variations() },
  { id: 'anim.rerun', scope: 'animate', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['inspector', 'context'], when: hasClip, run: () => void an().rerun() },
  { id: 'anim.tryOther', scope: 'animate', label: 'Try the other model', icon: Shuffle, placement: ['inspector', 'context'], when: hasClip, run: () => void an().tryOther() },
  { id: 'anim.toCatalogue', scope: 'animate', label: 'Show in Catalogue', icon: Film, placement: ['inspector', 'context'], when: () => !!an().clip()?.asset_id, run: () => { useSession.getState().setSuite('catalogue'); void import('../catalogue/catalogueStore').then((m) => { const c = m.useCatalogue.getState(); void c.setQuery({ folder: 'clips' }).then(() => { const id = an().clip()?.asset_id; if (id) c.select(id, 'single') }) }) } },
])

/** Right-click on the player / timeline. */
export function playerMenu(): MenuItem[] {
  const s = an()
  return [
    { cmd: 'anim.play', label: s.playing ? 'Pause' : 'Play' }, { cmd: 'anim.stepBack' }, { cmd: 'anim.stepForward' }, { cmd: 'anim.home' }, { cmd: 'anim.end' }, sep,
    { cmd: 'anim.setIn' }, { cmd: 'anim.setOut' }, { cmd: 'anim.clearInOut' }, sep,
    { cmd: 'anim.extractFrame' }, { cmd: 'anim.extractRange' }, { cmd: 'anim.sendToEdit' }, { cmd: 'anim.useAsStart' }, sep,
    { label: 'Onion skin', checked: s.onion, run: () => useAnimate.setState({ onion: !s.onion }) }, { label: 'Loop', checked: s.loop, run: () => useAnimate.setState({ loop: !s.loop }) },
    { cmd: 'anim.view.compare', label: s.view === 'compare' ? 'Leave compare' : 'Compare…' }, sep,
    { cmd: 'anim.keep' }, { cmd: 'anim.reject' }, { cmd: 'anim.variations' }, { cmd: 'anim.rerun' }, { cmd: 'anim.tryOther' }, { cmd: 'anim.toCatalogue' },
  ]
}
