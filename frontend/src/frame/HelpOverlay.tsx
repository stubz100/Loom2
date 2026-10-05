// "?" overlay: generated from the command registry for the current suite plus the global scope (07 §4), so it
// can never list a key that has no command behind it. Gestures (modifier-clicks, drags) are listed separately
// with their menu equivalents.
import { useSession } from '../store/session'
import { commandsFor, keyLabel, type Scope } from './commands'
import './menu.css'

const GESTURES: Record<string, [string, string][]> = {
  catalogue: [['Ctrl-click / Shift-click', 'toggle / range select (also: right-click → Select)'], ['Double-click', 'open in the loupe (also: right-click → Open in loupe)'], ['Drag tiles to Generate', 'use as reference (also: right-click → Use as reference)']],
  edit: [['Alt-click eye', 'solo the layer (also: right-click → Solo)'], ['Shift-click mask thumbnail', 'enable / disable the mask (also: right-click → Mask)'], ['Double-click layer', 'rename (also: right-click → Rename…)'], ['Shift / Alt while selecting', 'add / subtract (also: the mode control in Tool options)'], ['Space + drag, middle button', 'pan (also: the Hand tool)'], ['Ctrl + wheel', 'zoom at the pointer (also: the zoom buttons)'], ['\\ (hold)', 'before: hide the active layer (also: the strip button)']],
  generate: [['Drag tiles onto the reference slots', 'add references (also: right-click a tile → Use as reference)']],
}

export function HelpOverlay() {
  const setHelp = useSession((s) => s.setHelp)
  const suite = useSession((s) => s.ui.suite) as Scope
  const sections: [string, [string, string, string?][]][] = [
    [suite, commandsFor(suite).map((c) => [c.label, c.keys ? keyLabel(c.keys) : '—', c.hint])],
    ['global', commandsFor('global').map((c) => [c.label, c.keys ? keyLabel(c.keys) : '—', c.hint])],
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
          <p className="muted" style={{ marginTop: 10 }}>Every command is also in a right-click menu or a toolbar. Shift+F10 opens the menu of the focused item; Ctrl+K opens the command palette.</p>
        </div>
      </div>
    </div>
  )
}
