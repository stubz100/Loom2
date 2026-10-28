// U1 (D157, proto01_UI2 06 §5.3, seam 3): the project's clips as a record the layers share. Episode reads them here, not from Animate's
// store; Animate's store still holds them (its player, its filter, the live set) until the Shots layer takes them over through this module.
import type { Clip } from '../api/types'
import { useAnimate } from '../suites/animate/animateStore'

/** The clips, as a hook (re-renders when they change). */
export const useClips = (): Clip[] => useAnimate((s) => s.clips)
/** The clips now. */
export const clipList = (): Clip[] => useAnimate.getState().clips
/** The list fetched again (a take made since it was read). */
export const loadClips = (): Promise<void> => useAnimate.getState().loadClips()
