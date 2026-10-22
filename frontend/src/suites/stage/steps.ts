// D121 (proto01_animate 26 §5.5, AW3): the Shot stepper's rule, pure — the stage's six steps and their states from plain values (the passes,
// the stills and clips, the newest final, its composition), in the pipeline's order. ShotStepper.tsx reads the stores into a `StepInput`.
export type StepState = 'none' | 'fresh' | 'stale' | 'running' | 'partial'
export interface Step { id: 'passes' | 'frame' | 'clip' | 'final' | 'composition' | 'render'; label: string; state: StepState; count?: string; tip: string; cmd: string }
/** What the stepper reads: the stage's passes, stills and clips, the newest final, its composition — plain values, so the rule is testable. */
export interface StepInput {
  camera: string | null
  passes: { n: number; size: string; stale: boolean } | null
  stills: number; frameRunning: boolean
  clips: number; clipRunning: boolean
  final: { layers: number; done: number; running: boolean; assembled: boolean } | null; making: boolean
  comp: { revision: number; stale: boolean; rendered: number | null; rendering: boolean } | null
}

export const STATE_WORD: Record<StepState, string> = { none: 'not yet', fresh: 'done', stale: 'stale', running: 'running', partial: 'part done' }

/** The six steps and their states, in the pipeline's order (the frame, the clip and the final are made from the passes; the composition from
 *  the assembled final; the render from the composition). */
export function stageSteps(i: StepInput): Step[] {
  const passes: StepState = !i.passes ? 'none' : i.passes.stale ? 'stale' : 'fresh'
  const final: StepState = i.making || i.final?.running ? 'running' : !i.final ? 'none' : i.final.assembled ? 'fresh' : i.final.done ? 'partial' : 'none'
  const comp: StepState = !i.comp ? 'none' : i.comp.stale ? 'stale' : 'fresh'
  const render: StepState = !i.comp ? 'none' : i.comp.rendering ? 'running' : i.comp.rendered === null ? 'none' : i.comp.rendered < i.comp.revision ? 'stale' : 'fresh'
  return [
    { id: 'passes', label: 'passes', state: passes, cmd: 'anim.step.passes',
      tip: `The passes of ${i.camera ?? 'the active camera'}: ${i.passes ? `${i.passes.n} at ${i.passes.size}${i.passes.stale ? ', the scene moved on' : ', current'}` : 'none yet'} — Clay renders them (its foot)` },
    { id: 'frame', label: 'frame', state: i.frameRunning ? 'running' : i.stills ? 'fresh' : 'none', count: i.stills ? String(i.stills) : undefined, cmd: 'stage.frame.make',
      tip: `The stage's frames: ${i.stills || 'none yet'} — made in Image › From a stage; one of them starts the stage clip` },
    { id: 'clip', label: 'clip', state: i.clipRunning ? 'running' : i.clips ? 'fresh' : 'none', count: i.clips ? String(i.clips) : undefined, cmd: 'anim.step.clip',
      tip: `The stage's clips: ${i.clips || 'none yet'} — Performance › Stage clip (the sequence animated from a frame)` },
    { id: 'final', label: 'final', state: final, count: i.final && !i.final.assembled ? `${i.final.done}/${i.final.layers}` : undefined, cmd: 'anim.step.final',
      tip: `The final shot: ${!i.final ? (i.making ? 'splitting the scene into layers' : 'none yet') : i.final.assembled ? 'assembled' : `${i.final.done} of ${i.final.layers} layers made`} — Performance › Final shot` },
    { id: 'composition', label: 'composition', state: comp, count: i.comp ? `r${i.comp.revision}` : undefined, cmd: 'anim.step.final.open',
      tip: `The composition: ${!i.comp ? 'none yet (after the assembly)' : `revision ${i.comp.revision}${i.comp.stale ? ', the final changed since' : ''}`} — finished at the Final level` },
    { id: 'render', label: 'render', state: render, cmd: 'anim.step.final.open',
      tip: `The finished shot: ${!i.comp || i.comp.rendered === null ? (i.comp?.rendering ? 'rendering' : 'not rendered yet') : `rendered at revision ${i.comp.rendered}${i.comp.rendered < i.comp.revision ? `, the composition is at ${i.comp.revision}` : ''}`} — the Final level's foot` },
  ]
}
