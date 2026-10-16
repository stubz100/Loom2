// D85 (17 §3a) / D90 (02 §4.1): the Story style of a generation, picked by its sample image — the world's styles are written only in
// Story · World; here they are tiles (StyleTiles), the fragment in the tooltip. "default" follows the world's ★ style, "none" overrides it;
// the server appends the fragment after the prompt (story.resolve_style). Its own file so Fast Refresh keeps working.
import { StyleTiles } from '../story/StyleTiles'
import { useGenerate } from './generateStore'

export function StylePicker() {
  const choice = useGenerate((g) => g.panel.style_id)
  const set = useGenerate((g) => g.set)
  const showText = useGenerate((g) => !!g.presetText.look)
  return (
    <div className="gen-form style-pick" style={{ marginBottom: 8 }}>
      <label>style</label>
      <StyleTiles value={choice} onChange={(v) => set({ style_id: v })} size={48} showText={showText} />
    </div>
  )
}
