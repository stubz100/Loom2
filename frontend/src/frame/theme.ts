// Colour themes (07 §7, proto01_design/01 · D34): the palettes live in frame.css as custom properties under
// :root (dark) and :root[data-theme="light"]; this module switches the attribute and carries the few colours a
// PixiJS canvas needs as numbers (keep them equal to --canvas-bg / --checker-a / --checker-b in frame.css).
export type Theme = 'dark' | 'light'

export const THEMES: [Theme, string][] = [['dark', 'Dark'], ['light', 'Light pastel']]

export const CANVAS_COLOURS: Record<Theme, { background: number; checkerA: string; checkerB: string }> = {
  dark: { background: 0x141414, checkerA: '#2a2a2a', checkerB: '#3a3a3a' },
  light: { background: 0xe9e5de, checkerA: '#fbfaf7', checkerB: '#dedad2' },
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}
