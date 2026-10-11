// "?" overlay: generated from the command registry for the current suite plus the global scope (07 §4), so it
// can never list a key that has no command behind it. Gestures (modifier-clicks, drags) are listed separately
// with their menu equivalents.
import { useSession } from '../store/session'
import { command, commandsFor, keyLabel, type Command, type Scope } from './commands'
import { useKeymap } from './keymap'
import './menu.css'

const GESTURES: Record<string, [string, string][]> = {
  catalogue: [['Ctrl-click / Shift-click', 'toggle / range select (also: right-click → Select)'], ['Double-click', 'open in the loupe (also: right-click → Open in loupe)'], ['Drag tiles to Generate', 'use as reference (also: right-click → Use as reference)']],
  edit: [['Alt-click eye', 'solo the layer (also: right-click → Solo)'], ['Shift-click mask thumbnail', 'enable / disable the mask (also: right-click → Mask)'], ['Double-click layer', 'rename (also: right-click → Rename…)'], ['Shift / Alt while selecting', 'add / subtract (also: the mode control in Tool options)'], ['Space + drag, middle button', 'pan (also: the Hand tool)'], ['Ctrl + wheel', 'zoom at the pointer (also: the zoom buttons)']],
  generate: [['Drag tiles onto the reference slots', 'add references (also: right-click a tile → Use as reference)']],
}

/** D72: the gesture keys every suite shares — not remappable, listed so they are discoverable (07 §4). */
const FIXED_ROWS: [string, string][] = [['move the selection / step frames / nudge a transform box', '← ↑ → ↓'], ['cancel, close, back out of the loupe', 'Esc'],
  ['hold to pan in Edit · play / pause in Animate', 'Space'], ['focus mode · swap in Compare', 'Tab']]

export function HelpOverlay() {
  const setHelp = useSession((s) => s.setHelp)
  const suite = useSession((s) => s.ui.suite) as Scope
  useKeymap((k) => k.version)                                            // D72: rows follow a remap
  const row = (c: Command): [string, string, string?] => [c.label, c.keys ? keyLabel(c.keys) : '—', [c.hint, c.fixed ? 'fixed key' : ''].filter(Boolean).join(' · ') || undefined]
  const sections: [string, [string, string, string?][]][] = [
    [suite, commandsFor(suite).map(row)],
    ['global', commandsFor('global').map(row)],
    ['fixed keys', FIXED_ROWS.map(([what, k]) => [what, k] as [string, string])],
    ...(GESTURES[suite] ? [['gestures', GESTURES[suite].map(([g, what]) => [what, g] as [string, string])] as [string, [string, string, string?][]]] : []),
  ]
  return (
    <div className="modal-backdrop" onClick={() => setHelp(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 'min(900px, 94vw)' }}>
        <div className="head">Commands and keys<span className="spacer" /><button className="quiet" onClick={() => setHelp(false)}>Close</button></div>
        <div className="body" style={{ maxHeight: '72vh', overflow: 'auto' }}>
          <div className="cmd-help">
            {sections.map(([name, rows]) => (
              <section key={name}>
                <h4 className="sect">{name}</h4>
                {rows.map(([label, key, hint], i) => <div className="row" key={i}><span>{label}{hint ? <span className="muted"> · {hint}</span> : null}</span><kbd>{key}</kbd></div>)}
              </section>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 10 }}>Every command is also in a right-click menu or a toolbar. {keyLabel(command('global.contextMenu')?.keys) || 'Right-click'} opens the menu of the focused item; {keyLabel(command('global.palette')?.keys) || 'the ☰ menu'} opens the command palette. Keys can be changed in Settings › Keyboard; the fixed keys cannot.</p>
        </div>
      </div>
    </div>
  )
}
