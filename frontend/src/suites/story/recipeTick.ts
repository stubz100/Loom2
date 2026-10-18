// RC0 (D96): bumped by a story.changed event naming a shot (session.ts), so an open recipe list (RecipeSteps) refetches.
import { create } from 'zustand'

export const useRecipeTick = create<{ tick: Record<string, number>; bump: (id: string) => void }>((set, get) => ({
  tick: {}, bump: (id) => set({ tick: { ...get().tick, [id]: (get().tick[id] ?? 0) + 1 } }),
}))
