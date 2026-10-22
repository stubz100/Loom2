// D95 (AN1) → D121 (proto01_animate 26 §5.3): which card of Animate's Performance level is open — Image to video (a clip from a start
// image), Stage clip (the stage's sequence animated from one of its frames: IC-LoRA or Wan Animate) or Final shot (the layered route: the
// plate, the characters performed, mattes, the assembly, the composition) — and with it the foot's verb. UI state of this window only.
import { create } from 'zustand'

export type AnimRoute = 'i2v' | 'clip' | 'final'
export const useAnimRoute = create<{ route: AnimRoute; set: (route: AnimRoute) => void }>()((set) => ({
  route: 'i2v',
  set: (route) => set({ route }),
}))
