// P17 (D83): the Sequence tab's verbs — every one has a mouse home (the lane's context menu, the Inspector, the transport) per D32;
// undo / redo take Ctrl+Z / Ctrl+Shift+Z in the Animate scope (the clip player has no undo of its own).
import { ArrowLeft, ArrowRight, ChevronFirst, ChevronLast, Clapperboard, FileDown, Pause, Play, Plus, Redo2, Scissors, SkipBack, SkipForward, Trash2, Undo2, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { askConfirm, askText, useSession } from '../../store/session'
import { useAnimate } from './animateStore'
import { duration, ticks } from './lane'
import { useSequence } from './sequenceStore'

const sq = () => useSequence.getState()
const hasSeq = () => !!sq().current
const hasSel = () => hasSeq() && sq().selected !== null && !!sq().lane?.clips[sq().selected!]
const an = () => useAnimate.getState()

registerCommands([
  { id: 'anim.seq.new', scope: 'animate', label: 'New sequence…', icon: Plus, placement: ['panel', 'context'],
    run: () => void askText({ title: 'New sequence', text: 'A single lane at the project frame rate; clips come from the Clips bin.', placeholder: 'sequence name', initial: 'Sequence' }).then((n) => { if (n?.trim()) void sq().create(n.trim()) }) },
  { id: 'anim.seq.rename', scope: 'animate', label: 'Rename sequence…', icon: Clapperboard, placement: ['inspector', 'context'], when: hasSeq,
    run: () => void askText({ title: 'Rename sequence', initial: sq().current?.name ?? '', placeholder: 'sequence name' }).then((n) => { if (n?.trim()) void sq().rename(n.trim()) }) },
  { id: 'anim.seq.delete', scope: 'animate', label: 'Delete sequence', icon: Trash2, placement: ['inspector', 'context'], when: hasSeq,
    run: () => void askConfirm({ title: 'Delete this sequence?', text: 'The document and its exports go; the clips stay in the Catalogue.', okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void sq().destroy() }) },
  { id: 'anim.seq.addCurrent', scope: 'animate', label: 'Add the current clip', icon: Plus, placement: ['panel', 'context'], when: () => hasSeq() && !!an().clip(),
    run: () => { const c = an().clip(); if (c) sq().addClip(c) } },
  { id: 'anim.seq.removeClip', scope: 'animate', label: 'Remove from the sequence', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], when: hasSel, run: () => sq().removeClip(sq().selected!) },
  { id: 'anim.seq.moveLeft', scope: 'animate', label: 'Move clip earlier', icon: ArrowLeft, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! > 0, run: () => sq().moveClip(sq().selected!, sq().selected! - 1) },
  { id: 'anim.seq.moveRight', scope: 'animate', label: 'Move clip later', icon: ArrowRight, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! < (sq().lane?.clips.length ?? 0) - 1, run: () => sq().moveClip(sq().selected!, sq().selected! + 1) },
  { id: 'anim.seq.dissolve', scope: 'animate', label: 'Dissolve from the previous clip (12 frames)', icon: Scissors, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! > 0,
    run: () => { const i = sq().selected!; const l = sq().lane!; sq().setDissolve(i, l.overlaps[i] ? 0 : Math.min(12, ticks(l, l.clips[i]) - 1, ticks(l, l.clips[i - 1]) - 1)) } },
  { id: 'anim.seq.undo', scope: 'animate', label: 'Undo (sequence)', icon: Undo2, keys: 'Ctrl+Z', placement: ['toolbar', 'context'], when: () => hasSeq() && sq().undo.length > 0, run: () => sq().undoEdit() },
  { id: 'anim.seq.redo', scope: 'animate', label: 'Redo (sequence)', icon: Redo2, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'], when: () => hasSeq() && sq().redo.length > 0, run: () => sq().redoEdit() },
  { id: 'anim.seq.play', scope: 'animate', label: 'Play / pause the sequence', icon: Play, placement: ['toolbar', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => sq().togglePlay() },
  { id: 'anim.seq.stepBack', scope: 'animate', label: 'Previous tick', icon: SkipBack, placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead - 1) },
  { id: 'anim.seq.stepForward', scope: 'animate', label: 'Next tick', icon: SkipForward, placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead + 1) },
  { id: 'anim.seq.home', scope: 'animate', label: 'Sequence start', icon: ChevronFirst, placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(0) },
  { id: 'anim.seq.end', scope: 'animate', label: 'Sequence end', icon: ChevronLast, placement: ['toolbar'], when: hasSeq, run: () => { const l = sq().lane; if (l) sq().setPlayhead(duration(l) - 1) } },
  { id: 'anim.seq.zoomIn', scope: 'animate', label: 'Zoom the lane in', icon: ZoomIn, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1.5) },
  { id: 'anim.seq.zoomOut', scope: 'animate', label: 'Zoom the lane out', icon: ZoomOut, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1 / 1.5) },
  { id: 'anim.seq.exportEdl', scope: 'animate', label: 'Export EDL (CMX 3600)', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void sq().exportAs('edl') },
  { id: 'anim.seq.exportFcpxml', scope: 'animate', label: 'Export FCPXML 1.10', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void sq().exportAs('fcpxml') },
  { id: 'anim.seq.render', scope: 'animate', label: 'Render a draft clip (CPU)', icon: Clapperboard, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void sq().render() },
  { id: 'anim.seq.openClip', scope: 'animate', label: 'Open the clip in the player', icon: Pause, placement: ['inspector', 'context'], when: hasSel,
    run: () => { const l = sq().lane!; const c = l.clips[sq().selected!]; an().select(c.source); useSession.getState().toast('Opened in the clip player (Clips tab)', 'info') } },
])

/** Right-click on a lane clip (selected by the caller) or on the lane's empty space. */
export function laneMenu(onClip: boolean): MenuItem[] {
  return onClip
    ? [{ cmd: 'anim.seq.dissolve' }, { cmd: 'anim.seq.moveLeft' }, { cmd: 'anim.seq.moveRight' }, { cmd: 'anim.seq.openClip' }, sep, { cmd: 'anim.seq.removeClip' }, sep, { cmd: 'anim.seq.undo' }, { cmd: 'anim.seq.redo' }]
    : [{ cmd: 'anim.seq.addCurrent' }, { cmd: 'anim.seq.play' }, sep, { cmd: 'anim.seq.exportEdl' }, { cmd: 'anim.seq.exportFcpxml' }, { cmd: 'anim.seq.render' }, sep, { cmd: 'anim.seq.rename' }, { cmd: 'anim.seq.delete' }, sep, { cmd: 'anim.seq.undo' }, { cmd: 'anim.seq.redo' }]
}
