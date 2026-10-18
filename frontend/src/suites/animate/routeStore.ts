// D95 (AN1, proto01_animate 03 §4.2): which card of Animate's Performance section is open — Image to video (a clip from a start image,
// today's Animate form) or From the stage (stills and clips from the stage's passes, Stage's Render) — and with it the foot's verb.
// UI state of this window only.
import { create } from 'zustand'

export type AnimRoute = 'i2v' | 'stage'
export const useAnimRoute = create<{ route: AnimRoute; chosen: boolean; set: (route: AnimRoute) => void }>()((set) => ({
  route: 'i2v', chosen: false,
  set: (route) => set({ route, chosen: true }),
}))
