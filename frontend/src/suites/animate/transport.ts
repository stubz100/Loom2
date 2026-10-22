// D121 (proto01_animate 26 §5.1 rule 3, AW2): one transport for Animate's three levels. Each level registers what play, step, home / end,
// in / out and its marks mean for it — Clay (the stage store: the scene's frame, its range, its keys), Performance (the clip player: the
// clip's frames, its in / out, its beats and harvested frames), Final (the composition: its frames, the selected layer's keys) — and the one
// command set (`anim.play`, `anim.stepBack` …, animateCommands.ts) runs the transport of the level on screen. A leaf module: the stores
// import it, it imports only the session (to read the level).
import { useSession } from '../../store/session'

export type Level = 'stage' | 'animate' | 'final'
export interface Transport {
  /** Something to play (a stage, a clip, a composition). */
  ready(): boolean
  playing(): boolean
  play(on?: boolean): void
  frame(): number
  seek(frame: number): void
  step(delta: number): void
  home(): void
  end(): void
  /** The work area's ends at the playhead (the stage's range, the clip's in / out); absent where there is none (Final). */
  setIn?(): void
  setOut?(): void
  clearInOut?(): void
  hasInOut?(): boolean
  /** The frames previous / next key jump between (the stage's keys, the clip's beats and harvested frames, the selected layer's keys). */
  marks?(): number[]
}

const impl: Partial<Record<Level, Transport>> = {}
export function registerTransport(level: Level, t: Transport): void { impl[level] = t }
/** The transport of the level on screen, or null outside Animate (or before the level's code has loaded). */
export function transport(): Transport | null {
  const s = useSession.getState().ui.suite
  return s === 'stage' || s === 'animate' || s === 'final' ? impl[s] ?? null : null
}

/** The one transport's command ids — every level's key hook dispatches them (Clay's from the animate scope, beside its own). */
export const TRANSPORT_IDS: ReadonlySet<string> = new Set(['anim.play', 'anim.stepBack', 'anim.stepForward', 'anim.back10', 'anim.fwd10', 'anim.home', 'anim.end',
  'anim.setIn', 'anim.setOut', 'anim.clearInOut', 'anim.prevKey', 'anim.nextKey'])

/** The previous / next mark from `frame` (strictly before / after), or null. */
export function neighbour(marks: number[], frame: number, dir: -1 | 1): number | null {
  const c = [...new Set(marks)].filter((f) => (dir < 0 ? f < frame : f > frame)).sort((a, b) => a - b)
  return c.length ? (dir < 0 ? c[c.length - 1] : c[0]) : null
}
