// AU4 (D127, proto01_animate 30 §16): the installed VST3 effects to add to an audio track's chain — the system's folder and the author's
// (Settings › Audio › VST3 folders), scanned by loom2's own host once and again when a bundle changes. A click adds one after the others.
import { useMemo, useState } from 'react'
import type { VstPlugin } from '../../../api/types'
import { Help } from '../../../frame/Help'
import { useSequence } from './sequenceStore'

export function EffectPicker() {
  const track = useSequence((s) => s.fxPicker)
  const name = useSequence((s) => [...(s.tracks?.audio ?? [])].find((t) => t.id === s.fxPicker)?.name ?? '')
  const list = useSequence((s) => s.fxPlugins)
  const scanning = useSequence((s) => s.fxScanning)
  const [q, setQ] = useState('')
  const shown = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean)
    return (list?.plugins ?? []).filter((p) => words.every((w) => `${p.name} ${p.vendor} ${p.sub}`.toLowerCase().includes(w)))
  }, [list, q])
  if (track === null) return null
  const close = () => useSequence.getState().setFxPicker(null)
  const add = (p: VstPlugin) => { close(); void useSequence.getState().cutFx(track, { op: 'add', plugin: { bundle: p.bundle, uid: p.uid, name: p.name, vendor: p.vendor } }) }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal fx-picker" data-testid="fx-picker" onClick={(e) => e.stopPropagation()}>
        <div className="head">Add an effect · {name}<span className="spacer" />
          <Help text={"VST3 effects from C:\\Program Files\\Common Files\\VST3 and your folders in Settings › Audio, each run by loom2's own host (a crash ends only the host). The track is printed through its effects before the mix, the movie and the exports."} /></div>
        <div className="body">
          <input type="text" autoFocus aria-label="find an effect" placeholder="find by name, maker or kind" value={q} onChange={(e) => setQ(e.target.value)} />
          {scanning && <p className="hint">Scanning the VST3 folders… (the first time takes a minute)</p>}
          {list && !list.available && <p className="hint">{list.error}</p>}
          {list?.error && list.available && <p className="hint">{list.error}</p>}
          <ul className="fx-list">
            {shown.map((p) => (
              <li key={`${p.bundle}|${p.uid}`}><button className="link" title={p.bundle} onClick={() => add(p)}><b>{p.name}</b> <span className="hint">{p.vendor}{p.sub ? ` · ${p.sub.replace(/\|/g, ' · ')}` : ''}</span></button></li>
            ))}
          </ul>
          {list && <p className="hint">{shown.length} of {list.plugins.length} effects{list.failed.length ? <> · {list.failed.length} bundle{list.failed.length === 1 ? '' : 's'} did not load <Help text={list.failed.slice(0, 8).map((f) => `${f.bundle}: ${f.error}`).join('\n')} /></> : null}</p>}
        </div>
        <div className="foot">
          <button disabled={scanning} onClick={() => useSequence.getState().setFxPicker(track, true)} title="Scan every bundle again (a new or updated effect is found without it)">Scan again</button>
          <span className="spacer" />
          <button onClick={close}>Close</button>
        </div>
      </div>
    </div>
  )
}
