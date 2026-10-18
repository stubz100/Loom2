// D90 (02 §3.1, R4): the Panel and the Inspector are resized by dragging their inner edge; the width is kept per suite, a double-click
// returns to the suite's default (Generate 30 % of the window, the rest 320 / 340 px). While dragging only the CSS variable moves; the
// store takes the width on release.
import { useSession } from '../store/session'
import { clampWidth, INSPECTOR_MIN, PANEL_MIN } from './panelWidth'
import { sharedKeyOf } from './railTabs'

export function Resizer({ side }: { side: 'panel' | 'inspector' }) {
  const key = side === 'panel' ? 'panelWidths' : 'inspectorWidths'
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    e.preventDefault()
    const el = e.currentTarget, host = el.parentElement, frame = el.closest('.frame') as HTMLElement | null
    if (!host || !frame) return
    const x0 = e.clientX, w0 = host.getBoundingClientRect().width, vw = window.innerWidth, min = side === 'panel' ? PANEL_MIN : INSPECTOR_MIN
    let w = w0
    el.setPointerCapture(e.pointerId)
    const move = (ev: PointerEvent) => { w = clampWidth(w0 + (side === 'panel' ? ev.clientX - x0 : x0 - ev.clientX), vw, min); frame.style.setProperty(side === 'panel' ? '--panel-w' : '--inspector-w', `${w}px`) }
    const up = () => {
      el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up)
      const s = useSession.getState()
      s.setUi({ [key]: { ...(s.ui[key] ?? {}), [sharedKeyOf(s.ui.suite)]: w } })
    }
    el.addEventListener('pointermove', move); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up)
  }
  const reset = () => {
    const s = useSession.getState()
    const rest = { ...(s.ui[key] ?? {}) }
    delete rest[sharedKeyOf(s.ui.suite)]
    s.setUi({ [key]: rest })
  }
  return <div className={`resizer ${side}`} role="separator" aria-orientation="vertical" aria-label={`Resize the ${side} (double-click: default width)`}
    title="Drag to resize · double-click for the default width" onPointerDown={onPointerDown} onDoubleClick={reset} />
}
