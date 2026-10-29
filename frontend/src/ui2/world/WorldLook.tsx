// U3d (D157, proto01_UI2 03 §6): World's Look — the project's styles, made the way an entity's pictures are: a name and its words, a sample
// rendered on the project's own sample scene (G2, U2c), ★ the default every Make uses unless a run picks another. The Story World page's style
// grid and editor, mounted here (they act on the Story store's world record).
import { useEffect } from 'react'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { StyleEditor, StyleGrid } from '../../suites/story/StyleWorld'
import { useLibrary } from '../../suites/story/libraryStore'
import { useStory } from '../../suites/story/storyStore'
import { LOOK_FIELDS, withWords } from './look'
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

function LookWords({ styleId, fragment }: { styleId: string; fragment: string }) {
  const lib = useLibrary((s) => s.library)
  useEffect(() => { if (!useLibrary.getState().library) void useLibrary.getState().load() }, [])
  const entries = (lib?.entries ?? []).filter((e) => (LOOK_FIELDS as readonly string[]).includes(e.field))
  if (!entries.length) return null
  return (
    <div className="w-look-words" data-testid="world-look-words">
      <h4 className="w-h">Look words <Help text="The Library's art styles and moods: a click adds the words to this style's prompt fragment. Light, camera and pose words belong to Clay." /></h4>
      {LOOK_FIELDS.map((f) => {
        const mine = entries.filter((e) => e.field === f)
        return mine.length ? <div key={f} className="w-field"><span>{f === 'style' ? 'art style' : f}</span><div className="w-chips left">
          {mine.map((e) => <button key={e.id} title={e.text} onClick={() => useStory.getState().setStyle(styleId, { fragment: withWords(fragment, e.text) })}>{e.name}</button>)}
        </div></div> : null
      })}
    </div>
  )
}

export function LookInspector() {
  const world = useStory((s) => s.world)
  const selected = useStory((s) => s.selected)
  const style = selected?.kind === 'style' ? world?.styles.find((x) => x.id === selected.id) : undefined
  return (
    <aside className="w-insp" data-testid="world-look-inspector">
      {style && world ? <><StyleEditor key={style.id} s={style} isDefault={world.default_style === style.id} /><LookWords styleId={style.id} fragment={style.fragment} /></> : <span className="w-empty">Pick a style</span>}
    </aside>
  )
}
