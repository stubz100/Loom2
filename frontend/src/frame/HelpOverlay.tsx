import { useSession } from '../store/session'

const KEYS: [string, string][] = [
  ['Ctrl+1…5', 'switch suite'], ['Ctrl+K', 'command palette (M2)'], ['`', 'toggle Dock'], ['Tab', 'focus mode (hide Panel + Inspector)'],
  ['Ctrl+B / Ctrl+I', 'toggle Panel / Inspector'], ['Ctrl+,', 'Settings'], ['?', 'this overlay'], ['Esc', 'close overlay'],
  ['Ctrl+Z / Ctrl+Shift+Z', 'undo / redo (suite-scoped, M4)'], ['Space (hold)', 'pan on the Stage (M2+)'], ['Ctrl+wheel / Ctrl+0 / Ctrl+1', 'zoom / fit / 1:1 (M2+)'],
]

export function HelpOverlay() {
  const setHelp = useSession((s) => s.setHelp)
  return (
    <div className="modal-backdrop" onClick={() => setHelp(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="head">Keyboard map<span className="spacer" /><button className="quiet" onClick={() => setHelp(false)}>Close</button></div>
        <div className="body keys">{KEYS.map(([k, v]) => <div key={k}><span>{v}</span><kbd>{k}</kbd></div>)}</div>
      </div>
    </div>
  )
}
