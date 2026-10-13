// D85 (17 §3a): the Style picker on Generate's Prompt tab — one Story style per generation, its fragment appended after the prompt by
// the server (story.resolve_style); "default" follows the world's ★ style, "none" overrides it. Its own file so Fast Refresh keeps working.
import { styleFor, useStory } from '../story/storyStore'
import { useGenerate } from './generateStore'

export function StylePicker() {
  const choice = useGenerate((g) => g.panel.style_id)
  const set = useGenerate((g) => g.set)
  const world = useStory((s) => s.world)
  const styles = world?.styles ?? []
  const def = styles.find((s) => s.id === world?.default_style)
  const cur = styles.find((s) => s.id === styleFor(choice))
  return (
    <div className="gen-form style-pick" style={{ marginBottom: 8 }}>
      <label>style</label>
      <div>
        <select aria-label="style" title="A Story style: its fragment is appended after the prompt (Story · World)" value={choice === undefined ? '' : choice === null ? 'none' : choice}
          onChange={(e) => set({ style_id: e.target.value === '' ? undefined : e.target.value === 'none' ? null : e.target.value })}>
          <option value="">default{def ? ` · ${def.name}` : ' · none'}</option>
          <option value="none">none</option>
          {styles.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <span className="hint"> {cur ? (cur.fragment ? `appended: ${cur.fragment}` : 'its fragment is empty') : styles.length ? 'no style appended' : 'styles are made in Story · World'}</span>
      </div>
    </div>
  )
}
