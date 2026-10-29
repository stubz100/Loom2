// U3e (D157, G3; proto01_UI2 03 §6): the Look's word presets — the Library's art-style and mood entries — and how they join a style's words.

/** U3e (G3): the Library's look words — its art-style and mood entries — as the Look's word presets: a click adds them to the style's words. */
export const LOOK_FIELDS = ['style', 'mood'] as const

/** A style's words with a preset added (once; after a comma). */
export const withWords = (fragment: string, text: string): string => {
  const f = fragment.trim(), t = text.trim()
  if (!t || f.toLowerCase().split(/\s*,\s*/).includes(t.toLowerCase())) return f
  return f ? `${f}, ${t}` : t
}
