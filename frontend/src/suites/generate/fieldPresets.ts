// The prompt tree's fields (09 §3a) and how a preset joins one. D92: the presets themselves are the project's Story · World library
// (story/libraryStore.ts) — Generate's tiles read it, its field's + adds to it.

export type FieldKey =
  | 'scene' | 'subject.description' | 'subject.position' | 'subject.action' | 'subject.pose'
  | 'style' | 'lighting' | 'mood' | 'background' | 'composition'
  | 'camera.angle' | 'camera.lens' | 'camera.depth_of_field' | 'camera.f-number' | 'camera.distance'
  | 'text' | 'negative'

export const FIELD_LABEL: Record<FieldKey, string> = {
  scene: 'scene', 'subject.description': 'description', 'subject.position': 'position', 'subject.action': 'action', 'subject.pose': 'pose',
  style: 'art style', lighting: 'lighting', mood: 'mood', background: 'background', composition: 'composition',
  'camera.angle': 'camera angle', 'camera.lens': 'lens', 'camera.depth_of_field': 'depth of field', 'camera.f-number': 'aperture', 'camera.distance': 'shot size',
  text: 'lead text', negative: 'negative',
}

/** Single-valued fields: a preset replaces the text. Everything else appends with a comma. */
export const REPLACE: ReadonlySet<FieldKey> = new Set<FieldKey>(['camera.lens', 'camera.f-number', 'camera.distance', 'camera.depth_of_field'])

/** D92: how Story · World groups its library (02 §4): what a picture looks like, the camera, the prompt's own lines, a subject's words. A
 *  subject's description is a Cast character now — its group shows only the author's own description presets. The built-in vocabulary
 *  itself lives with the server (orchestrator/loom2/library_seed.json) and seeds every project's library. */
export const LIBRARY_GROUPS: { id: string; label: string; fields: FieldKey[] }[] = [
  { id: 'look', label: 'Look', fields: ['lighting', 'mood', 'style', 'background', 'composition'] },
  { id: 'camera', label: 'Camera', fields: ['camera.distance', 'camera.angle', 'camera.lens', 'camera.depth_of_field', 'camera.f-number'] },
  { id: 'prompt', label: 'Prompt', fields: ['scene', 'text', 'negative'] },
  { id: 'subject', label: 'Subject', fields: ['subject.position', 'subject.action', 'subject.pose', 'subject.description'] },
]

export const appendValue = (cur: string | undefined, v: string, field: FieldKey): string => (REPLACE.has(field) || !cur?.trim() ? v : `${cur}, ${v}`)
