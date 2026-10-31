// W6 (≈ F23): a picture's prompt as words to read — a Tree prompt (FLUX.2's JSON) labelled line by line, not raw JSON.

const str = (v: unknown): string => (typeof v === 'string' ? v.trim() : '')
const SUBJECT_KEYS = ['position', 'action', 'pose'] as const
const TREE_KEYS = ['background', 'lighting', 'mood', 'composition', 'style'] as const

/** A prompt as lines to read: a Tree's scene, its subjects (with where they stand and what they do), its look and camera; other text as is. */
export function readablePrompt(text: string): string {
  const t = text.trim()
  if (!t.startsWith('{')) return text
  let j: Record<string, unknown>
  try { j = JSON.parse(t) as Record<string, unknown> } catch { return text }
  if (!j || typeof j !== 'object' || Array.isArray(j)) return text
  const out: string[] = []
  if (str(j.scene)) out.push(`scene: ${str(j.scene)}`)
  const subs = Array.isArray(j.subjects) ? (j.subjects as Record<string, unknown>[]) : []
  subs.forEach((s, k) => {
    const d = [str(s?.description), ...SUBJECT_KEYS.map((x) => str(s?.[x]))].filter(Boolean).join('; ')
    if (d) out.push(`${subs.length > 1 ? `subject ${k + 1}` : 'subject'}: ${d}`)
  })
  for (const k of TREE_KEYS) if (str(j[k])) out.push(`${k}: ${str(j[k])}`)
  if (Array.isArray(j.color_palette) && j.color_palette.length) out.push(`colours: ${(j.color_palette as unknown[]).map(str).filter(Boolean).join(', ')}`)
  const cam = j.camera && typeof j.camera === 'object' ? Object.values(j.camera as Record<string, unknown>).map(str).filter(Boolean) : []
  if (cam.length) out.push(`camera: ${cam.join(', ')}`)
  return out.length ? out.join('\n') : text
}
