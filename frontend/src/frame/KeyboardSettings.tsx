// D72 (ArtCraft P16): Settings › Keyboard — every command with its key, by scope; click a key to record a new one (Esc cancels), × leaves
// the command without a key, ↺ restores its own. A remap that collides is refused with the other command's name; Arrows, Esc, Space and
// Tab are fixed. Overrides live on this machine (keyStore.ts) and every tooltip, menu, help row and palette entry follows them.
import { RotateCcw, X } from 'lucide-react'
import { Help } from './Help'
import { useEffect, useMemo, useState } from 'react'
import { askConfirm } from '../store/session'
import { commandsFor, defaultKeysOf, keyLabel, type Scope } from './commands'
import { chordFromEvent, remap, resetAllKeys, resetKey, useKeymap } from './keymap'
import { preloadSuite } from './lazySuite'

const SCOPES: [Scope, string][] = [['global', 'Everywhere'], ['story', 'Story'], ['catalogue', 'Catalogue'], ['generate', 'Image · Make'], ['edit', 'Image · Edit'], ['animate', 'Animate'], ['stage', 'Stage'], ['models', 'Models'], ['bin', 'Bin']]   // D90 (01 §11.7): Stage and Story were missing

export function KeyboardSettings() {
  const overrides = useKeymap((s) => s.overrides)
  const version = useKeymap((s) => s.version)
  const [q, setQ] = useState('')
  const [recording, setRecording] = useState<string | null>(null)
  const [note, setNote] = useState<{ id: string; text: string; error?: boolean } | null>(null)
  const [loaded, setLoaded] = useState(0)
  useEffect(() => {                                                      // every suite's commands, so the conflict check sees them all (D69 lazy)
    for (const id of ['edit', 'animate', 'models', 'stage', 'story']) preloadSuite(id)
    const t = window.setTimeout(() => setLoaded((n) => n + 1), 400)
    return () => window.clearTimeout(t)
  }, [])
  useEffect(() => {
    if (!recording) return
    const h = (e: KeyboardEvent) => {
      e.preventDefault(); e.stopImmediatePropagation()
      if (e.key === 'Escape' && !e.ctrlKey && !e.altKey && !e.shiftKey) { setRecording(null); return }
      const chord = chordFromEvent(e)
      if (!chord) return                                                 // a lone modifier: keep listening
      const r = remap(recording, chord)
      setNote(r.ok ? { id: recording, text: `now ${keyLabel(chord)}` } : { id: recording, text: r.reason, error: true })
      setRecording(null)
    }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [recording])
  const needle = q.trim().toLowerCase()
  const groups = useMemo(() => SCOPES.map(([scope, title]) => [title, commandsFor(scope).filter((c) =>
    !needle || c.label.toLowerCase().includes(needle) || c.id.includes(needle) || (c.keys ?? '').toLowerCase().includes(needle))] as const).filter(([, cs]) => cs.length),
  [needle, version, loaded]) // eslint-disable-line react-hooks/exhaustive-deps
  const changed = Object.keys(overrides).length
  return (
    <div className="keys-settings">
      <span className="hint">Changes apply at once. <Help text={"Key changes stay on this machine — Save and Cancel do not touch them. Every command keeps its button or menu entry."} /></span>
      <div className="keys-top">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search commands or keys" aria-label="Search commands or keys" />
        <button className="quiet" disabled={!changed} onClick={() => void askConfirm({ title: 'Reset all keys', text: `${changed} changed key${changed === 1 ? '' : 's'} go back to the defaults.`, okLabel: 'Reset all' }).then((ok) => { if (ok) { resetAllKeys(); setNote(null) } })}>
          <RotateCcw size={13} /> Reset all{changed ? ` (${changed})` : ''}
        </button>
      </div>
      {groups.map(([title, cs]) => (
        <section key={title}>
          <h5>{title}</h5>
          {cs.map((c) => {
            const own = defaultKeysOf(c.id)?.keys
            const overridden = Object.hasOwn(overrides, c.id)
            return (
              <div key={c.id} className={`keys-row${overridden ? ' changed' : ''}`} data-cmd={c.id}>
                <span className="lbl" title={c.id}>{c.label}</span>
                {note?.id === c.id && <span className={`keys-note${note.error ? ' error' : ''}`}>{note.text}</span>}
                <button className={`keys-chord${recording === c.id ? ' recording' : ''}`} disabled={c.fixed}
                  title={c.fixed ? 'A fixed key (Arrows, Esc, Space, Tab)' : recording === c.id ? 'Press the new key — Esc cancels' : 'Click, then press the new key'}
                  onClick={() => { setNote(null); setRecording(recording === c.id ? null : c.id) }}>
                  {recording === c.id ? 'press a key…' : c.keys ? keyLabel(c.keys) : '—'}
                </button>
                <button className="quiet icon" disabled={c.fixed || !c.keys} title="No key for this command" aria-label={`No key for ${c.label}`} onClick={() => { const r = remap(c.id, null); setNote(r.ok ? { id: c.id, text: 'no key' } : { id: c.id, text: r.reason, error: true }) }}><X size={13} /></button>
                <button className="quiet icon" disabled={!overridden} title={`Back to ${own ? keyLabel(own) : 'no key'}`} aria-label={`Reset the key of ${c.label}`} onClick={() => { resetKey(c.id); setNote(null) }}><RotateCcw size={13} /></button>
              </div>
            )
          })}
        </section>
      ))}
    </div>
  )
}
