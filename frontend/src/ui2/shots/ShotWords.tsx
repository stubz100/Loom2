// U4d (D157, G13; proto01_UI2 04 §6): the words of the shot's pictures in its header — the scene's words and this shot's own (each kept
// with its record), and *Show the words*: what a still, the plate or a performance is told, part by part, each with where it came from
// (the server's shot_prompt — the Look, the place, the cast in frame, the lights, the scene, the action, this shot).
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import type { ShotPrompt } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { useShots, type WordsFor } from './shotsStore'

const FOR: { id: WordsFor; label: string }[] = [{ id: 'still', label: 'a still' }, { id: 'plate', label: 'the plate' }, { id: 'performance', label: 'a performance' }]

/** A text kept with a record, saved when it is left (a blur), not at every key. */
function KeptText({ value, label, placeholder, rows, disabled, save }: { value: string; label: string; placeholder: string; rows: number; disabled?: boolean; save: (v: string) => Promise<void> }) {
  const [draft, setDraft] = useState<string | null>(null)
  return <textarea rows={rows} aria-label={label} placeholder={placeholder} value={draft ?? value} disabled={disabled}
    onChange={(e) => setDraft(e.target.value)} onBlur={() => { if (draft !== null && draft !== value) void save(draft).finally(() => setDraft(null)); else setDraft(null) }} />
}

const fail = (what: string) => (e: unknown) => { useSession.getState().toast(`${what}: ${(e as { detail?: string }).detail ?? e}`, 'error') }

async function saveSceneWords(sceneId: string, words: string): Promise<void> {
  await unwrap(http.PATCH('/story/scenes/{sid}', { params: { path: { sid: sceneId } }, body: { words } as never })).then((r) => useStory.setState({ scenes: r.items })).catch(fail('Scene words'))
}

async function saveShotWords(words: string): Promise<void> {
  const st = useStory.getState(), s = st.shot(), v = st.shotVersion()
  if (!s || !v) return
  await unwrap(http.PATCH('/story/shots/{sid}', { params: { path: { sid: s.id } }, body: { revision: s.revision, versions: [{ id: v.id, words }] } as never }))
    .then((next) => useStory.setState({ shots: useStory.getState().shots.map((x) => (x.id === next.id ? next : x)) })).catch(fail('Shot words'))
}

/** `stageRev`: the shot's stage's revision — the words follow Clay's edits (a light moved, a figure stepped out of frame). */
export function ShotWords({ stageRev }: { stageRev?: number }) {
  const open = useShots((s) => s.wordsOpen)
  const purpose = useShots((s) => s.wordsFor)
  const s = useStory((st) => st.shot())
  const v = useStory((st) => st.shotVersion())
  const node = useStory((st) => { const sh = st.shot(); return sh?.owner_node ? st.flowNodes[sh.owner_node] : undefined })
  const scene = useStory((st) => (node?.scene_id ? st.scenes.find((x) => x.id === node.scene_id) : undefined))
  const flowNodes = useStory((st) => st.flowNodes)
  const [words, setWords] = useState<{ key: string; p: ShotPrompt } | null>(null)
  const key = s && v ? `${s.id}/${v.id}/${purpose}/${s.revision}/${stageRev ?? ''}/${scene?.words ?? ''}/${node?.text ?? ''}` : null
  useEffect(() => {
    if (!open || !s || !v || !key) return
    let live = true
    void unwrap(http.GET('/story/shots/{sid}/versions/{vid}/prompt', { params: { path: { sid: s.id, vid: v.id }, query: { purpose } } }))
      .then((p) => { if (live) setWords({ key, p }) }).catch(() => undefined)
    return () => { live = false }
  }, [open, key, s, v, purpose, flowNodes])
  if (!s || !v) return null
  const locked = v.state !== 'open'
  const shown = words && words.key === key ? words.p : null
  return (
    <div className="w-field stack s-words" data-testid="shots-words">
      <span>words <Help text="What the shot's pictures are told comes from its records: the Look, the place, the cast the camera sees, Clay's lights, the scene's words, the description and this shot's own words. Nothing is carried over from the last picture made." />
        <CommandButton id="shots.words.toggle" text label={open ? 'Hide the words' : 'Show the words ▸'} /></span>
      {open && <div className="s-words-body">
        {scene && <label className="w-field"><span>the scene's</span><KeptText rows={1} label="the scene's words" placeholder="night, drifting fog" value={scene.words ?? ''} save={(w) => saveSceneWords(scene.id, w)} /></label>}
        <label className="w-field"><span>this shot only</span><KeptText rows={1} label="this shot's words" placeholder="rain on the planks" value={v.words ?? ''} disabled={locked} save={saveShotWords} /></label>
        <div className="w-chips left" role="group" aria-label="the words for">{FOR.map((f) => (
          <button key={f.id} className={purpose === f.id ? 'active' : ''} onClick={() => useShots.getState().setWordsFor(f.id)}>{f.label}</button>))}</div>
        {shown ? shown.parts.length ? <ol className="s-parts">{shown.parts.map((p) => (
          <li key={p.id} data-part={p.id}><span className="s-part-head"><b>{p.label}</b><span className="s-part-src">{p.source}</span></span><span className="s-part-text">{p.text}</span></li>
        ))}</ol> : <span className="w-val">no words yet</span> : <span className="w-val">reading…</span>}
      </div>}
    </div>
  )
}
