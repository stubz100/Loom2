// D154: the fonts a text layer can use — five OFL families bundled under public/fonts/ (the @font-face rules in fonts.css) plus any
// family the WebView can name (the system's). A leaf module: no DOM at import time (the Vitest suite imports it).
export interface BundledFont { family: string; weights: [number, number]; italic: boolean; psd: string }

/** The bundled families, their weight range (variable fonts), whether an italic face exists, and the PostScript stem the PSD names. */
export const BUNDLED_FONTS: BundledFont[] = [
  { family: 'Inter', weights: [100, 900], italic: true, psd: 'Inter' },
  { family: 'Lora', weights: [400, 700], italic: true, psd: 'Lora' },
  { family: 'Oswald', weights: [200, 700], italic: false, psd: 'Oswald' },
  { family: 'Courier Prime', weights: [400, 700], italic: true, psd: 'CourierPrime' },
  { family: 'Caveat', weights: [400, 700], italic: false, psd: 'Caveat' },
]

export const fontFamilies = (): string[] => BUNDLED_FONTS.map((f) => f.family)
export const isBundled = (family: string): boolean => BUNDLED_FONTS.some((f) => f.family === family)

/** The PostScript-style name a PSD type layer carries: the bundled stem + the face, or the system family without spaces + the face. */
export function psdFontName(family: string, weight: 'normal' | 'bold', italic: boolean): string {
  const stem = BUNDLED_FONTS.find((f) => f.family === family)?.psd ?? family.replace(/\s+/g, '')
  const face = weight === 'bold' ? (italic ? 'BoldItalic' : 'Bold') : italic ? 'Italic' : 'Regular'
  return `${stem}-${face}`
}

/** The CSS font shorthand the rasteriser and the inline editor share (a generic fallback so an unknown system name still draws). */
export function fontString(family: string, size: number, weight: 'normal' | 'bold', italic: boolean): string {
  return `${italic ? 'italic ' : ''}${weight === 'bold' ? 700 : 400} ${size}px "${family}", sans-serif`
}

/** Wait for the face to be loadable (the bundled TTFs load on first use; a system family resolves at once). Never throws. */
export async function ensureFont(family: string, weight: 'normal' | 'bold', italic: boolean): Promise<void> {
  const fonts = (globalThis as { document?: { fonts?: FontFaceSet } }).document?.fonts
  if (!fonts) return
  try { await fonts.load(fontString(family, 32, weight, italic)) } catch { /* an unknown family: the fallback draws */ }
}
