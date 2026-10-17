// D90 (02 §6.3, R3): presets are icons, not words. These are the schematic glyphs — the presets whose meaning is geometry (aspect, size,
// shot size, camera angle, lens, depth of field, aperture, composition, subject position, the angle moves). Looks (lighting, mood, style,
// background) get generated sample swatches instead (02 §6.3). D92: no lettered tiles anywhere — a preset without a glyph or a picture
// shows its *field's* glyph (`fieldGlyph`: a sun for lighting, a mask for mood, a palette for a style …); the built-in negatives have
// drawn glyphs of their own. Every glyph is a 32×32 line drawing in currentColor, so it follows the theme and the selected state.
import type { ReactNode } from 'react'

const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
const svg = (body: ReactNode, key?: string) => <svg key={key} viewBox="0 0 32 32" width="100%" height="100%" aria-hidden="true">{body}</svg>
const frame = <rect x="3" y="7" width="26" height="18" rx="1.5" {...S} />

/** A standing figure: head at (x, y) with radius r, body below; `clip` crops it to the 16:9 frame. */
function figure(x: number, y: number, r: number, id: string): ReactNode {
  const b = r * 1.1, h = r * 7
  return (
    <>
      <defs><clipPath id={id}><rect x="3" y="7" width="26" height="18" /></clipPath></defs>
      <g clipPath={`url(#${id})`} {...S}>
        <circle cx={x} cy={y} r={r} />
        <path d={`M${x - b * 1.6} ${y + r + h * 0.55} L${x - b * 1.4} ${y + r + b * 0.9} Q${x} ${y + r + b * 0.2} ${x + b * 1.4} ${y + r + b * 0.9} L${x + b * 1.6} ${y + r + h * 0.55}`} />
        <path d={`M${x - b * 0.7} ${y + r + h * 0.55} L${x - b * 0.8} ${y + r + h} M${x + b * 0.7} ${y + r + h * 0.55} L${x + b * 0.8} ${y + r + h}`} />
      </g>
    </>
  )
}

/** Shot size (camera.distance): the same figure, closer or farther, inside the frame. */
const SHOT: Record<string, [number, number, number]> = {
  'extreme close-up': [16, 18, 10], 'close-up': [16, 15, 5.5], 'medium close-up': [16, 13, 3.6], 'medium shot': [16, 12, 2.6],
  'medium long shot': [16, 11, 1.9], 'full shot': [16, 10, 1.45], 'wide shot': [16, 15, 0.9], 'establishing shot': [20, 18, 0.55],
}
function shotGlyph(v: string): ReactNode | null {
  const p = SHOT[v]
  if (!p) return null
  const extra = v === 'wide shot' || v === 'establishing shot'
    ? <path d={v === 'establishing shot' ? 'M3 21 L8 21 L8 15 L11 15 L11 21 L14 21 L14 12 L17 12 L17 21 L29 21' : 'M3 21.5 L29 21.5'} {...S} strokeWidth={1.1} /> : null
  return svg(<>{frame}{extra}{figure(p[0], p[1], p[2], `shot-${v.replace(/\W/g, '')}`)}</>)
}

/** Camera angle: where a small camera sits relative to the figure, and which way it looks. */
const cam = (x: number, y: number, rot: number) => <path d="M-3 -2 L2 -2 L2 2 L-3 2 Z M2 -1 L4.5 -2.5 L4.5 2.5 L2 1" transform={`translate(${x} ${y}) rotate(${rot})`} {...S} strokeWidth={1.3} />
const person = <g {...S}><circle cx="20" cy="11" r="2.6" /><path d="M16.5 26 L17 16.5 Q20 14.5 23 16.5 L23.5 26" /></g>
const ANGLE: Record<string, ReactNode> = {
  'eye level': <>{person}{cam(6, 11, 0)}</>,
  'low angle': <>{person}{cam(6, 25, -35)}</>,
  'high angle': <>{person}{cam(6, 4, 35)}</>,
  "bird's eye": <>{person}{cam(20, 3, 90)}<path d="M3 29 L29 29" {...S} strokeWidth={1} /></>,
  "worm's eye": <>{person}{cam(20, 29, -90)}</>,
  'dutch tilt': <g transform="rotate(-14 16 16)">{frame}{figure(16, 12, 2.4, 'dutch')}</g>,
  'over the shoulder': <>{frame}{figure(21, 12, 2.4, 'ots')}<path d="M3 25 L3 17 Q6 12 10 13 Q12 15 12 19 L13 25" {...S} /></>,
  'three-quarter left': <><circle cx="16" cy="16" r="9" {...S} /><path d="M16 7 Q11 16 16 25" {...S} /><circle cx="12.5" cy="14" r="1" fill="currentColor" /></>,
  'three-quarter right': <><circle cx="16" cy="16" r="9" {...S} /><path d="M16 7 Q21 16 16 25" {...S} /><circle cx="19.5" cy="14" r="1" fill="currentColor" /></>,
  profile: <><path d="M20 7 Q11 7 11 15 L9 18 L11 19 Q11 25 18 25" {...S} /><circle cx="14" cy="14" r="1" fill="currentColor" /></>,
  'from behind': <><circle cx="16" cy="12" r="5" {...S} /><path d="M8 27 Q8 19 16 18 Q24 19 24 27" {...S} /><path d="M13 9.5 Q16 8 19 9.5" {...S} strokeWidth={1} /></>,
}

/** Lens: the field of view as a wedge from the camera at the bottom. */
const LENS: Record<string, number> = { '24mm': 84, '35mm': 63, '50mm': 47, '85mm': 28, '135mm': 18 }
function lensGlyph(v: string): ReactNode | null {
  if (v === 'anamorphic') return svg(<><ellipse cx="16" cy="15" rx="13" ry="6" {...S} /><path d="M9 15 L23 15" {...S} strokeWidth={1} /><path d="M2 26 L30 26" {...S} strokeWidth={1} /><path d="M8 26 L24 26" {...S} strokeWidth={2.4} opacity={0.5} /></>)   // D92: the oval and a lens flare, no letters
  const a = LENS[v]
  if (!a) return null
  const r = 22, t = (a / 2) * (Math.PI / 180), x = Math.sin(t) * r, y = 28 - Math.cos(t) * r
  return svg(<><path d={`M16 28 L${16 - x} ${y} A${r} ${r} 0 0 1 ${16 + x} ${y} Z`} {...S} /><text x="16" y="25" fontSize="6.5" textAnchor="middle" fill="currentColor">{v.replace('mm', '')}</text></>)
}

/** Depth of field: three subjects in depth, sharp (solid) or soft (dashed). */
const dof = (sharp: [boolean, boolean, boolean], extra?: ReactNode) => svg(<>
  {[[9, 22, 5], [17, 15, 3.6], [24, 10, 2.6]].map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} {...S} strokeDasharray={sharp[i] ? undefined : '1.6 1.6'} />)}{extra}</>)
const DOF: Record<string, () => ReactNode> = {
  shallow: () => dof([true, false, false]), medium: () => dof([true, true, false]), deep: () => dof([true, true, true]),
  'rack focus on the subject': () => dof([false, true, false], <path d="M7 29 L25 29 M22 27 L25 29 L22 31" {...S} strokeWidth={1.1} />),
  'soft bokeh background': () => svg(<><circle cx="10" cy="20" r="5" {...S} />{[[20, 8, 3], [26, 13, 2.5], [22, 18, 2]].map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill="currentColor" opacity={0.35} />)}</>),
}

/** Aperture: the opening as a hexagon, wide at f/1.4, small at f/11. */
const FNUM: Record<string, number> = { 'f/1.4': 10, 'f/2': 8.6, 'f/2.8': 7.2, 'f/4': 6, 'f/5.6': 4.8, 'f/8': 3.6, 'f/11': 2.6 }
function fGlyph(v: string): ReactNode | null {
  const r = FNUM[v]
  if (!r) return null
  const hex = Array.from({ length: 6 }, (_, i) => { const t = (Math.PI / 3) * i + Math.PI / 6; return `${16 + Math.cos(t) * r},${15 + Math.sin(t) * r}` }).join(' ')
  return svg(<><circle cx="16" cy="15" r="12" {...S} strokeWidth={1.1} /><polygon points={hex} {...S} /><text x="16" y="31" fontSize="5.5" textAnchor="middle" fill="currentColor">{v}</text></>)
}

/** Composition and subject position: the frame with guide lines and a dot for the subject. */
const dot = (x: number, y: number, r = 2.2) => <circle cx={x} cy={y} r={r} fill="currentColor" />
const thirds = <path d="M11.7 7 L11.7 25 M20.3 7 L20.3 25 M3 13 L29 13 M3 19 L29 19" {...S} strokeWidth={0.7} opacity={0.6} />
const COMPOSITION: Record<string, ReactNode> = {
  'rule of thirds, subject left': <>{frame}{thirds}{dot(11.7, 13)}</>,
  'centred and symmetrical': <>{frame}<path d="M16 7 L16 25" {...S} strokeWidth={0.7} />{dot(16, 16)}</>,
  'leading lines towards the subject': <>{frame}<path d="M3 25 L16 15 M29 25 L16 15 M3 20 L16 15 M29 20 L16 15" {...S} strokeWidth={0.8} />{dot(16, 14)}</>,
  'framed by a doorway': <>{frame}<rect x="11" y="9.5" width="10" height="15.5" {...S} />{dot(16, 17)}</>,
  'low horizon, big sky': <>{frame}<path d="M3 22 L29 22" {...S} />{dot(10, 20.5, 1.4)}</>,
  'tight over-the-shoulder': <>{frame}<path d="M3 25 L3 15 Q7 10 12 12 Q14 15 14 25" {...S} fill="currentColor" fillOpacity={0.25} />{dot(21, 14)}</>,
  'dynamic diagonal': <>{frame}<path d="M3 25 L29 7" {...S} strokeWidth={0.8} />{dot(19, 13)}</>,
}
const POSITION: Record<string, ReactNode> = {
  'left third': <>{frame}{thirds}{dot(11.7, 16)}</>, centre: <>{frame}{dot(16, 16)}</>, 'right third': <>{frame}{thirds}{dot(20.3, 16)}</>,
  foreground: <>{frame}{dot(16, 21, 3.6)}</>, midground: <>{frame}{dot(16, 16, 2.2)}</>, background: <>{frame}<path d="M3 14 L29 14" {...S} strokeWidth={0.7} />{dot(16, 12.5, 1.2)}</>,
  'waist-up': <>{frame}{figure(16, 12, 2.6, 'pos-waist')}</>, 'full figure': <>{frame}{figure(16, 10, 1.45, 'pos-full')}</>,
  'lower left': <>{frame}{dot(8, 21)}</>, 'upper right': <>{frame}{dot(24, 11)}</>,
}

/** The angle moves of New angle (D82). */
const MOVES: Record<string, ReactNode> = {
  topdown: <>{cam(16, 4, 90)}<ellipse cx="16" cy="24" rx="9" ry="3" {...S} /><path d="M16 9 L16 18 M13.5 15.5 L16 18 L18.5 15.5" {...S} /></>,
  left45: <><circle cx="16" cy="17" r="4" {...S} /><path d="M27 17 A11 11 0 0 0 8.2 9.2 M8.2 9.2 L8.6 13 M8.2 9.2 L12 9.4" {...S} /></>,
  right45: <><circle cx="16" cy="17" r="4" {...S} /><path d="M5 17 A11 11 0 0 1 23.8 9.2 M23.8 9.2 L23.4 13 M23.8 9.2 L20 9.4" {...S} /></>,
  closeup: <>{frame}<rect x="11" y="11" width="10" height="10" {...S} strokeDasharray="1.6 1.4" /><path d="M7 9 L11 11 M25 9 L21 11 M7 23 L11 21 M25 23 L21 21" {...S} strokeWidth={1} /></>,
  wide: <><rect x="10" y="11" width="12" height="10" {...S} /><rect x="3" y="6" width="26" height="20" rx="1.5" {...S} strokeDasharray="1.6 1.4" /><path d="M10 11 L5 8 M22 11 L27 8 M10 21 L5 24 M22 21 L27 24" {...S} strokeWidth={1} /></>,
}

/** Aspect ratio as the shape itself ('16:9', '1:1', '2:3'…). */
export function aspectGlyph(w: number, h: number): ReactNode {
  const k = 26 / Math.max(w, h), rw = w * k, rh = h * k
  return svg(<rect x={16 - rw / 2} y={16 - rh / 2} width={rw} height={rh} rx="1.2" {...S} />)
}
/** Size tiers as three nested sizes, the chosen one solid. */
export function tierGlyph(tier: 'thumb' | 'draft' | 'full' | 'custom'): ReactNode {
  const s = { thumb: 9, draft: 17, full: 26, custom: 0 }[tier]
  if (!s) return svg(<><rect x="5" y="9" width="22" height="14" rx="1.2" {...S} strokeDasharray="2 1.6" /><path d="M11 16 L21 16 M16 11 L16 21" {...S} /></>)
  return svg(<>{[9, 17, 26].map((v) => <rect key={v} x={16 - v / 2} y={16 - (v * 9) / 32} width={v} height={(v * 9) / 16} rx="1" {...S} strokeWidth={v === s ? 1.8 : 0.7} opacity={v === s ? 1 : 0.45} />)}</>)
}

/** The glyph for a preset value of a prompt field, or null when that preset has no drawing of its own (it shows a swatch or its field's glyph, D92). */
export function glyphFor(field: string, value: string): ReactNode | null {
  const v = value.trim().toLowerCase()
  switch (field) {
    case 'camera.distance': return shotGlyph(v)
    case 'camera.angle': return ANGLE[v] ? svg(ANGLE[v]) : null
    case 'camera.lens': return lensGlyph(v)
    case 'camera.depth_of_field': return DOF[v]?.() ?? null
    case 'camera.f-number': return fGlyph(v)
    case 'composition': return COMPOSITION[v] ? svg(COMPOSITION[v]) : null
    case 'subject.position': return POSITION[v] ? svg(POSITION[v]) : null
    case 'move': return MOVES[v] ? svg(MOVES[v]) : null
    case 'negative': return NEGATIVE[v] ? svg(<>{NEGATIVE[v]}{noMark}</>) : null
    default: return null
  }
}

/** D92: the built-in negatives as drawn glyphs (a picture of a negative is meaningless) — the defect, with a small "not" mark. */
const noMark = <g {...S} strokeWidth={1.3}><circle cx="25" cy="7" r="4.5" /><path d="M21.8 10.2 L28.2 3.8" /></g>
const NEGATIVE: Record<string, ReactNode> = {
  'blurry, low detail': <><circle cx="13" cy="18" r="8" {...S} strokeDasharray="2 2" /><circle cx="15" cy="17" r="8" {...S} opacity={0.45} /></>,
  'text, watermark, logo': <><rect x="3" y="10" width="20" height="16" rx="1.5" {...S} /><circle cx="13" cy="18" r="4.5" {...S} /><path d="M15 16.4 A2.4 2.4 0 1 0 15 19.6" {...S} strokeWidth={1.2} /></>,
  'deformed hands, extra fingers': <g {...S}><path d="M8 28 L8 18 M8 18 L6 12 M10.5 17 L10 8 M13 17 L13.5 7.5 M15.5 17.5 L17 9 M17.5 19 L20 12 M19 21 L23 16" /><path d="M8 28 Q14 30 18 24 L19 21" /></g>,
  oversaturated: <>{[[11, 13], [19, 13], [15, 20]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="6.5" fill="currentColor" opacity={0.55} stroke="none" />)}</>,
}

const ray = (i: number) => { const t = (Math.PI / 4) * i, c = Math.cos(t), n = Math.sin(t); return <path key={i} d={`M${16 + c * 8.5} ${16 + n * 8.5} L${16 + c * 12} ${16 + n * 12}`} /> }
const hexAt = (r: number) => Array.from({ length: 6 }, (_, i) => { const t = (Math.PI / 3) * i + Math.PI / 6; return `${16 + Math.cos(t) * r},${16 + Math.sin(t) * r}` }).join(' ')
const bust = (dash?: string) => <g {...S} strokeDasharray={dash}><circle cx="16" cy="11" r="5" /><path d="M6 28 Q6 19 16 18 Q26 19 26 28" /></g>
/** D92: the glyph of a prompt field (and of the other library kinds) — what a tile shows while it has no glyph of its own and no picture. */
const FIELD: Record<string, () => ReactNode> = {
  lighting: () => <g {...S}><circle cx="16" cy="16" r="5.5" />{Array.from({ length: 8 }, (_, i) => ray(i))}</g>,
  mood: () => <g {...S}><path d="M6 8 Q16 4 26 8 Q27 20 16 28 Q5 20 6 8 Z" /><path d="M10 14 Q12 12.5 14 14 M18 14 Q20 12.5 22 14" /><path d="M11.5 20 Q16 23.5 20.5 20" /></g>,
  background: () => <>{frame}<path d="M3 21 L10 14 L15 18 L21 11 L29 19" {...S} /></>,
  scene: () => <>{frame}<path d="M3 20 L29 20" {...S} /><circle cx="22" cy="13" r="2.4" {...S} /><path d="M7 20 L7 15 L10 15 L10 20" {...S} strokeWidth={1.1} /></>,
  style: () => <g {...S}><path d="M26 4 L14.5 15.5" strokeWidth={2.4} /><path d="M14.5 15.5 Q10 16 9 20 Q8 24 4.5 27 Q11 28 14 24.5 Q17 21 16.5 17.5 Z" /></g>,
  text: () => <path d="M5 8 L27 8 M5 13 L27 13 M5 18 L27 18 M5 23 L18 23" {...S} />,
  negative: () => <g {...S}><circle cx="16" cy="16" r="11" /><path d="M8.2 23.8 L23.8 8.2" /></g>,
  'subject.action': () => <g {...S}><circle cx="19.5" cy="6" r="2.6" /><path d="M18.5 9.5 L15 18 M17.5 11.5 L23 14.5 M17.5 11.5 L11.5 12.5 M15 18 L20.5 22 L19 28 M15 18 L11 22.5 L5.5 22" /></g>,
  'subject.pose': () => <g {...S}><circle cx="16" cy="6.5" r="2.8" /><path d="M16 9.5 L16 19 M10 15.5 L16 11.5 L22 15.5 M16 19 L12 28 M16 19 L20 28" /></g>,
  'subject.description': () => bust(),
  'subject.position': () => <>{frame}{thirds}<circle cx="11.7" cy="13" r="2.2" {...S} /></>,
  composition: () => <>{frame}{thirds}</>,
  'camera.angle': () => <g {...S}><rect x="4" y="13" width="15" height="11" rx="1.5" /><path d="M19 16 L27 12 L27 25 L19 21" /><path d="M6 9 A12 12 0 0 1 22 6.5 M22 6.5 L19.5 5 M22 6.5 L20.5 9" strokeWidth={1.2} /></g>,
  'camera.lens': () => <g {...S}><path d="M16 28 L5 9 A20 20 0 0 1 27 9 Z" /><circle cx="16" cy="24" r="1.4" fill="currentColor" /></g>,
  'camera.depth_of_field': () => <>{[[9, 22, 5], [17, 15, 3.6], [24, 10, 2.6]].map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} {...S} strokeDasharray={i ? '1.6 1.6' : undefined} />)}</>,
  'camera.f-number': () => <g {...S}><circle cx="16" cy="16" r="12" strokeWidth={1.1} /><polygon points={hexAt(6)} /></g>,
  'camera.distance': () => <>{frame}{figure(16, 12, 2.6, 'fld-dist')}</>,
  panel: () => <g {...S}><path d="M8 5 L8 27 M16 5 L16 27 M24 5 L24 27" strokeWidth={1.1} /><rect x="5.5" y="9" width="5" height="4" rx="1" fill="currentColor" /><rect x="13.5" y="18" width="5" height="4" rx="1" fill="currentColor" /><rect x="21.5" y="12" width="5" height="4" rx="1" fill="currentColor" /></g>,
  palette: () => <g {...S}><path d="M16 4 C8 4 3 10 3 16 C3 22 8 27 14 27 C16.5 27 17 25 16 23.5 C15 22 16 20.5 18 20.5 L22 20.5 C26 20.5 29 18 29 14 C29 8 23 4 16 4 Z" />{[[10, 15], [13, 9.5], [19.5, 9], [24, 13.5]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1.8" fill="currentColor" />)}</g>,
  character: () => bust(),
  prop: () => <path d="M16 4 L27 10 L27 22 L16 28 L5 22 L5 10 Z M5 10 L16 16 L27 10 M16 16 L16 28" {...S} />,
  place: () => <g {...S}><path d="M16 28 C16 28 7 19 7 12.5 A9 9 0 0 1 25 12.5 C25 19 16 28 16 28 Z" /><circle cx="16" cy="12.5" r="3" /></g>,
  free: () => bust('2 1.8'),
}
/** The fields and kinds `fieldGlyph` draws (a test keeps every library field among them). */
export const FIELD_GLYPHS: readonly string[] = Object.keys(FIELD)
/** D92: a field's (or a kind's — panel, palette, character, prop, place, free) glyph; the generic negative mark for anything unknown. */
export function fieldGlyph(field: string): ReactNode { return svg((FIELD[field] ?? FIELD.negative)()) }
/** D92: a tile's glyph — its own drawing when it has one (geometry, a built-in negative), else its field's. */
export const tileGlyph = (field: string, value: string): ReactNode => glyphFor(field, value) ?? fieldGlyph(field)
