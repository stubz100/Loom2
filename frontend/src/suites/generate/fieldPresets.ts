// Per-field presets for the prompt tree (09 §3a, 2026-10-06): every input has a ✦ icon that opens one menu with the
// built-in vocabulary for that field, the user's own presets (saved from the same menu), and "save current text".
// Nothing is rendered inline any more — the tree shows fields, not chips.
import type { MenuItem } from '../../frame/commands'
import type { Snippet } from './generateStore'

export type FieldKey =
  | 'scene' | 'subject.description' | 'subject.position' | 'subject.action' | 'subject.pose'
  | 'style' | 'lighting' | 'mood' | 'background' | 'composition'
  | 'camera.angle' | 'camera.lens' | 'camera.depth_of_field' | 'camera.f-number' | 'camera.distance'
  | 'text' | 'negative'

export const FIELD_LABEL: Record<FieldKey, string> = {
  scene: 'scene', 'subject.description': 'subject description', 'subject.position': 'position', 'subject.action': 'action', 'subject.pose': 'pose',
  style: 'style', lighting: 'lighting', mood: 'mood', background: 'background', composition: 'composition',
  'camera.angle': 'camera angle', 'camera.lens': 'lens', 'camera.depth_of_field': 'depth of field', 'camera.f-number': 'f-number', 'camera.distance': 'distance',
  text: 'lead text', negative: 'negative',
}

/** Single-valued fields: a preset replaces the text. Everything else appends with a comma. */
export const REPLACE: ReadonlySet<FieldKey> = new Set<FieldKey>(['camera.lens', 'camera.f-number', 'camera.distance', 'camera.depth_of_field'])

// loom's directive vocabulary (04 §3c) plus BFL's prompting-guide examples
export const BUILTIN: Record<FieldKey, string[]> = {
  scene: ['a narrow rain-soaked alley at night in a weathered harbour town', "a captain's cabin lit by a single oil lamp", 'a windswept clifftop at dawn',
    'a crowded fish market under canvas awnings', 'a lighthouse room with a map table', 'an empty rooftop above a sleeping city', 'a storm-lashed ship deck', 'a quiet library at closing time'],
  'subject.description': ['a young woman with red braids, pale freckles and a dark green hooded cloak', 'a weathered sea captain in a navy coat with brass buttons',
    'a brass compass with a cracked glass', 'a stray dog with a torn ear', 'a hand-painted wooden sign reading "…"', 'a child in an oversized yellow raincoat'],
  'subject.position': ['left third', 'centre', 'right third', 'foreground', 'midground', 'background', 'waist-up', 'full figure', 'lower left', 'upper right'],
  'subject.action': ['looking back over the shoulder', 'reading a map', 'running towards the camera', 'holding up a lantern', 'pointing into the distance',
    'leaning on a railing', 'kneeling to pick something up', 'shielding eyes from the light'],
  'subject.pose': ['standing', 'sitting', 'crouching', 'walking', 'running', 'leaning', 'turning back over the shoulder', 'arms crossed', 'reaching out', 'kneeling'],
  style: ['painterly storyboard', 'cinematic film still', 'graphic-novel ink and wash', 'oil painting', 'watercolour sketch', 'photoreal', 'charcoal concept sketch', 'anime key visual'],
  lighting: ['golden hour rim light', 'soft overcast', 'hard noon sun', 'neon rim light', 'single candle', 'moonlight', 'window light', 'firelight', 'studio key + fill', 'backlit silhouette'],
  mood: ['tense', 'melancholic', 'hopeful', 'eerie', 'serene', 'triumphant', 'lonely', 'playful'],
  background: ['harbour cranes in fog', 'rain-streaked brick wall with a neon sign', 'open sea under a bruised sky', 'bookshelves and a ticking clock', 'a blurred crowd', 'distant mountains'],
  composition: ['rule of thirds, subject left', 'centred and symmetrical', 'leading lines towards the subject', 'framed by a doorway', 'low horizon, big sky', 'tight over-the-shoulder', 'dynamic diagonal'],
  'camera.angle': ['eye level', 'low angle', 'high angle', "bird's eye", "worm's eye", 'dutch tilt', 'over the shoulder', 'three-quarter left', 'three-quarter right', 'profile', 'from behind'],
  'camera.lens': ['24mm', '35mm', '50mm', '85mm', '135mm', 'anamorphic'],
  'camera.depth_of_field': ['shallow', 'medium', 'deep', 'rack focus on the subject', 'soft bokeh background'],
  'camera.f-number': ['f/1.4', 'f/2', 'f/2.8', 'f/4', 'f/5.6', 'f/8', 'f/11'],
  'camera.distance': ['extreme close-up', 'close-up', 'medium close-up', 'medium shot', 'medium long shot', 'full shot', 'wide shot', 'establishing shot'],
  text: ['Storyboard frame.', 'Concept art, production painting.', 'Key visual for a film pitch.'],
  negative: ['blurry, low detail', 'text, watermark, logo', 'deformed hands, extra fingers', 'oversaturated'],
}

export const appendValue = (cur: string | undefined, v: string, field: FieldKey): string => (REPLACE.has(field) || !cur?.trim() ? v : `${cur}, ${v}`)

const short = (s: string, n = 48) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

/** The ✦ menu for one field: built-ins, the user's presets for that field, and save / remove. */
export function presetMenu(field: FieldKey, current: string, snippets: Snippet[], onApply: (v: string) => void, onSave: () => void, onDelete: (name: string) => void): MenuItem[] {
  const mine = snippets.filter((s) => s.field === field)
  const items: MenuItem[] = [{ heading: `presets · ${FIELD_LABEL[field]}` }]
  items.push(...BUILTIN[field].map((v) => ({ label: v, run: () => onApply(v) })))
  if (mine.length) {
    items.push({ sep: true }, { heading: 'yours' })
    items.push(...mine.map((s) => ({ label: `${s.name} — ${short(s.text)}`, run: () => onApply(s.text) })))
    items.push({ label: 'Remove a preset', items: mine.map((s) => ({ label: s.name, danger: true, run: () => onDelete(s.name) })) })
  }
  items.push({ sep: true }, { label: 'Save current text as preset…', disabled: !current.trim(), run: onSave })
  return items
}
