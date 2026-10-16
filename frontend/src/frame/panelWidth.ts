// D90 (02 §3.1): Panel and Inspector widths per suite — Generate's default is 30 % of the window, the rest 320 / 340 px; a dragged
// width is kept per suite and clamped to 45 % of the window.
export const PANEL_MIN = 220, INSPECTOR_MIN = 240
const MAX_SHARE = 0.45

/** The default Panel width of a suite at a window width. */
export const defaultPanelWidth = (suite: string, vw: number): number => (suite === 'generate' ? Math.max(300, Math.round(vw * 0.3)) : 320)
export const clampWidth = (w: number, vw: number, min: number): number => Math.round(Math.max(min, Math.min(w, Math.max(min, vw * MAX_SHARE))))

/** The Panel and Inspector widths the frame uses for `suite`. */
export function frameWidths(ui: { panelWidths?: Record<string, number>; inspectorWidths?: Record<string, number>; inspectorWidth: number }, suite: string, vw: number) {
  return {
    panel: clampWidth(ui.panelWidths?.[suite] ?? defaultPanelWidth(suite, vw), vw, PANEL_MIN),
    inspector: clampWidth(ui.inspectorWidths?.[suite] ?? ui.inspectorWidth ?? 340, vw, INSPECTOR_MIN),
  }
}
