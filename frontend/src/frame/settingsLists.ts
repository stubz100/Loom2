// Review K72: Settings' list fields — mounted trees, engine flags, thumbnail sizes, VST3 folders — shown as one line of text, typed as text
// and split only on blur or Save (split and re-joined per keystroke, a trailing separator or space vanished: a second tree, a flag, a path
// with "Program Files" could not be typed).
import type { Settings } from '../api/types'

export type ListField = 'trees' | 'flags' | 'thumbs' | 'vst'

const paths = (t: string): string[] => t.split(';').map((x) => x.trim()).filter(Boolean)

/** Each field: its text from the settings, and the settings with the text split back in. */
export const LISTS: Record<ListField, { join: (s: Settings) => string; into: (s: Settings, text: string) => Settings }> = {
  trees: { join: (s) => s.mounted_model_trees.join(';'), into: (s, t) => ({ ...s, mounted_model_trees: paths(t) }) },
  flags: { join: (s) => s.engine.flags.join(' '), into: (s, t) => ({ ...s, engine: { ...s.engine, flags: t.split(/\s+/).filter(Boolean) } }) },
  thumbs: { join: (s) => s.thumbnail_sizes.join(','), into: (s, t) => ({ ...s, thumbnail_sizes: t.split(',').map((x) => Number(x.trim())).filter((n) => Number.isFinite(n) && n > 0) }) },
  vst: { join: (s) => s.vsthost.folders.join(';'), into: (s, t) => ({ ...s, vsthost: { ...s.vsthost, folders: paths(t) } }) },
}

/** The settings with every typed list text split in (a field not typed keeps its value). */
export function listsInto(s: Settings, texts: Partial<Record<ListField, string>>): Settings {
  return (Object.keys(texts) as ListField[]).reduce((acc, f) => (texts[f] === undefined ? acc : LISTS[f].into(acc, texts[f]!)), s)
}
