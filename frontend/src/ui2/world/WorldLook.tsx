// U3d (D157, proto01_UI2 03 §6): World's Look — the project's styles, made the way an entity's pictures are: a name and its words, a sample
// rendered on the project's own sample scene (G2, U2c), ★ the default every Make uses unless a run picks another. The Story World page's style
// grid and editor, mounted here (they act on the Story store's world record).
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { StyleEditor, StyleGrid } from '../../suites/story/StyleWorld'
import { useStory } from '../../suites/story/storyStore'
import '../../suites/story/story.css'

export function LookColumn() {
  const world = useStory((s) => s.world)
  if (!world) return <div className="w-empty">Reading the Look…</div>
  return (
    <div className="w-make" data-testid="world-look">
      <h4 className="w-h">Look <Help text="The project's styles. Every picture made in World and in Shots uses the default ★ unless a run picks another; a style's sample is rendered on this project's own scene, so the looks compare on what the story is." /></h4>
      <label className="w-field"><span>sample scene</span>
        <textarea rows={3} value={world.sample_scene} aria-label="sample scene" placeholder="e.g. a fishing harbour at dusk, a ferry at the pier" onChange={(e) => useStory.getState().edit({ sample_scene: e.target.value })} /></label>
      <div className="w-foot"><CommandButton id="story.world.addStyle" text /></div>
    </div>
  )
}

export function LookCentre() {
  return <div className="w-look"><StyleGrid /></div>
}

export function LookInspector() {
  const world = useStory((s) => s.world)
  const selected = useStory((s) => s.selected)
  const style = selected?.kind === 'style' ? world?.styles.find((x) => x.id === selected.id) : undefined
  return (
    <aside className="w-insp" data-testid="world-look-inspector">
      {style && world ? <StyleEditor key={style.id} s={style} isDefault={world.default_style === style.id} /> : <span className="w-empty">Pick a style</span>}
    </aside>
  )
}
