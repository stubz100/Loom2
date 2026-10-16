// D90 (02 §6.3, R3): presets are icons, not words. These are the schematic glyphs — the presets whose meaning is geometry (aspect, size,
// shot size, camera angle, lens, depth of field, aperture, composition, subject position, the angle moves). Looks (lighting, mood, style,
// background) get generated sample swatches instead (02 §6.3); anything without a glyph or a swatch falls back to a monogram tile.
// Every glyph is a 32×32 line drawing in currentColor, so it follows the theme and the selected state.
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
  if (v === 'anamorphic') return svg(<><ellipse cx="16" cy="16" rx="13" ry="6" {...S} /><path d="M9 16 L23 16" {...S} strokeWidth={1} /><text x="16" y="27.5" fontSize="6.5" textAnchor="middle" fill="currentColor">ana</text></>)
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

/** The glyph for a preset value of a prompt field, or null when that preset has no geometry to draw (it shows a swatch or a monogram). */
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
    default: return null
  }
}

/** Two letters for a preset that has neither a glyph nor a swatch yet. */
export const monogram = (label: string): string => label.split(/[\s-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('')
