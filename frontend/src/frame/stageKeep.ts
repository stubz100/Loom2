// D69 (ArtCraft P5): heavy stages stay alive while hidden. A suite with `keepAlive` (Edit, Animate) keeps its Stage mounted once
// visited — the editor's GPU canvas and document view, the player's decoder — so switching back costs a frame, not a re-init.
// The release policy unmounts a hidden one (today's destroy path) when it has been hidden longer than `ui.editKeepAliveMin`, or
// when the orchestrator admits a GPU job under VRAM pressure (`engine.vram_pressure`): the 6×4K editor holds ≈ 240 MiB of VRAM.
import { createContext, useContext } from 'react'
import { create } from 'zustand'

/** Whether the Stage this component lives in is the one on screen (true outside keep-alive stages). */
export const StageActive = createContext(true)
export const useStageActive = () => useContext(StageActive)

interface KeepState {
  mounted: string[]                         // keep-alive suites whose Stage is mounted (visible or hidden)
  hiddenAt: Record<string, number>          // when each was last hidden (performance.now)
  visit: (id: string) => void
  hide: (id: string) => void
  /** Unmount every hidden keep-alive stage (the active one stays); returns the ids released. */
  releaseHidden: (active: string, why: string) => string[]
  /** Unmount the stages hidden longer than `minutes`. */
  expire: (active: string, minutes: number) => string[]
}

export const useStageKeep = create<KeepState>()((set, get) => ({
  mounted: [], hiddenAt: {},
  visit: (id) => { if (!get().mounted.includes(id)) set({ mounted: [...get().mounted, id] }) },
  hide: (id) => set({ hiddenAt: { ...get().hiddenAt, [id]: performance.now() } }),
  releaseHidden: (active, why) => {
    const gone = get().mounted.filter((id) => id !== active)
    if (gone.length) {
      console.info(`loom2: released the hidden ${gone.join(', ')} stage${gone.length > 1 ? 's' : ''} (${why})`)
      set({ mounted: get().mounted.filter((id) => id === active) })
    }
    return gone
  },
  expire: (active, minutes) => {
    const now = performance.now()
    const gone = get().mounted.filter((id) => id !== active && now - (get().hiddenAt[id] ?? now) > minutes * 60_000)
    if (gone.length) {
      console.info(`loom2: released the hidden ${gone.join(', ')} stage${gone.length > 1 ? 's' : ''} (hidden for over ${minutes} min)`)
      set({ mounted: get().mounted.filter((id) => !gone.includes(id)) })
    }
    return gone
  },
}))
