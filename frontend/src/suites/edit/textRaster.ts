// D154: a text layer's layout and rasterisation. `layoutText` is pure (a measure function in, lines out — tested without a canvas);
// `rasterizeText` draws the layout on a 2D canvas at 1:1 — the pixels the layer stores and the compositor sees.
import { fontString } from './textFonts'

export interface TextOutline { width: number; colour: string }
export interface TextBlock {
  content: string; font: string; size: number; colour: string; align: 'left' | 'center' | 'right'; leading: number; tracking: number
  weight: 'normal' | 'bold'; italic: boolean; outline: TextOutline | null; box: [number, number] | null
}
export const TEXT_DEFAULTS: TextBlock = { content: '', font: 'Inter', size: 48, colour: '#ffffff', align: 'left', leading: 1.2, tracking: 0, weight: 'normal', italic: false, outline: null, box: null }

export interface TextLine { text: string; x: number; y: number; width: number }
export interface TextLayout { lines: TextLine[]; w: number; h: number; pad: number; lineHeight: number }

/** The margin around the glyphs: half the outline (it is centred on the edge) plus a little for antialiasing and overshoot. */
export const padOf = (t: TextBlock): number => Math.ceil((t.outline ? t.outline.width / 2 : 0) + Math.max(2, t.size * 0.08))

/** Lines placed in the layer's pixel space: paragraph text wraps words to the box width (a word wider than the box breaks by characters)
 * and takes the box's size; point text takes the widest line. `measure` gives a string's advance without tracking; tracking adds per gap. */
export function layoutText(t: TextBlock, measure: (s: string) => number): TextLayout {
  const width = (s: string) => (s ? measure(s) + t.tracking * Math.max(0, s.length - 1) : 0)
  const pad = padOf(t)
  const lineHeight = Math.max(1, Math.round(t.size * t.leading))
  const paragraphs = t.content.replace(/\r\n?/g, '\n').split('\n')
  const maxW = t.box ? Math.max(1, t.box[0] - 2 * pad) : Infinity
  const texts: string[] = []
  for (const p of paragraphs) {
    if (!t.box || width(p) <= maxW) { texts.push(p); continue }
    let line = ''
    for (const word of p.split(' ')) {
      const trial = line ? `${line} ${word}` : word
      if (width(trial) <= maxW) { line = trial; continue }
      if (line) texts.push(line)
      line = ''
      if (width(word) <= maxW) { line = word; continue }
      for (const ch of word) {                                   // a word wider than the box: break it by characters
        if (width(line + ch) <= maxW || !line) line += ch
        else { texts.push(line); line = ch }
      }
    }
    texts.push(line)
  }
  const widths = texts.map(width)
  const w = t.box ? Math.max(1, t.box[0]) : Math.max(1, Math.ceil(Math.max(0, ...widths) + 2 * pad))
  const h = t.box ? Math.max(1, t.box[1]) : Math.max(1, Math.ceil(texts.length * lineHeight + 2 * pad))
  const ascent = t.size * 0.8                                   // the baseline below the line's top; the fonts' ascenders sit near 0.8 em
  const lines: TextLine[] = texts.map((text, i) => {
    const lw = widths[i]
    const x = t.align === 'left' ? pad : t.align === 'center' ? (w - lw) / 2 : w - pad - lw
    return { text, x, y: pad + i * lineHeight + ascent, width: lw }
  })
  return { lines, w, h, pad, lineHeight }
}

/** The block drawn at 1:1 on a fresh canvas: the outline first (a round-joined stroke centred on the edge), then the fill. */
export function rasterizeText(t: TextBlock): { canvas: HTMLCanvasElement; w: number; h: number; layout: TextLayout } {
  const probe = document.createElement('canvas').getContext('2d')!
  probe.font = fontString(t.font, t.size, t.weight, t.italic)
  const layout = layoutText(t, (s) => probe.measureText(s).width)
  const canvas = document.createElement('canvas')
  canvas.width = layout.w; canvas.height = layout.h
  const ctx = canvas.getContext('2d')!
  ctx.font = probe.font
  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = 'left'
  ;(ctx as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = `${t.tracking}px`
  if (t.outline && t.outline.width > 0) {
    ctx.strokeStyle = t.outline.colour; ctx.lineWidth = t.outline.width; ctx.lineJoin = 'round'; ctx.miterLimit = 2
    for (const l of layout.lines) if (l.text) ctx.strokeText(l.text, l.x, l.y)
  }
  ctx.fillStyle = t.colour
  for (const l of layout.lines) if (l.text) ctx.fillText(l.text, l.x, l.y)
  return { canvas, w: layout.w, h: layout.h, layout }
}

/** The layer's name from its content: the first words, trimmed to a short label. */
export function textLayerName(content: string): string {
  const s = content.replace(/\s+/g, ' ').trim()
  return s ? (s.length > 24 ? `${s.slice(0, 23)}…` : s) : 'Text'
}
