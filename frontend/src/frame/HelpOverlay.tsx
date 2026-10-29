// "?" overlay: generated from the command registry for what the current suite's keys reach (D121: an Animate mode's reach) plus the
// global scope (07 §4), so it can never list a key that has no command behind it. Gestures (modifier-clicks, drags) are listed separately
// with their menu equivalents.
import { useSession } from '../store/session'
import { command, commandsAt, commandsFor, keyLabel, type Command } from './commands'
import { useKeymap } from './keymap'
import './menu.css'

const GESTURES: Record<string, [string, string][]> = {
  catalogue: [['Ctrl-click / Shift-click', 'toggle / range select (also: the arrow keys with Shift)'], ['Double-click', 'open in the loupe (also: right-click → Open in loupe); in Image\'s results it opens Edit'], ['Drag tiles to the Image tab', 'references in Make, layers in Edit (also: right-click → Use as reference)']],
  edit: [['Alt-click eye', 'solo the layer (also: right-click → Solo)'], ['Shift-click mask thumbnail', 'enable / disable the mask (also: right-click → Mask)'], ['Double-click layer', 'rename (also: right-click → Rename…)'], ['Shift / Alt while selecting', 'add / subtract (also: the mode control in Tool options)'], ['Space + drag, middle button', 'pan (also: the Hand tool)'], ['Ctrl + wheel', 'zoom at the pointer (also: the zoom buttons)']],
  generate: [['Drag tiles onto the reference slots', 'add references (also: right-click a tile → Use as reference)'], ['Right-click a preset icon', 'add or remove it, remake its sample, remove your own preset'], ['Scroll the Panel', 'the rail follows the section you are in (D90)']],
  // D90 (01 §11.2): the gestures of Animate, Stage and Story, with their menu or button equivalents; D121: one list per Animate mode
  // (stage = Clay, animate = Performance, final = Final), the one timeline's drags in each
  animate: [['Drag on the timeline ruler', 'scrub (also: the transport buttons, ← → and , .)'], ['Drag the in / out ends on the ruler', 'trim the work area (also: I / O and the transport)'],
    ['Click a ▼ pin or a harvested frame', 'jump to that frame (also: Alt+← / → the previous / next)'], ["Click the start / end thumbnail in a clip's details (Clips)", 'reuse it as the next start / end frame'],
    ['Drop tiles on the S / E slots or the Animate tab', 'set the start and end frames (also: right-click a tile → Animate)']],
  stage: [['Left-drag · right-drag · wheel in the free view', 'orbit · pan · zoom'], ['Drag the gizmo', 'move / rotate / scale (also: the numbers under its Scene row)'], ['Drop an image tile on the viewport', 'add an image plane'],
    ['Drop a mesh tile on the viewport', 'add a mesh prop (also: Scene › Meshes)'], ['While posing (the pose pill): click a joint, drag a hand or foot', 'rotate the joint (FK) · reach (IK)'],
    ['Double-click a Scene row', 'frame it; double-click its name to rename'], ["Drag the range's ends on the ruler", 'set the range (also: I / O and the range fields)'],
    ['Drag a key on the timeline', 'move it to another frame (also: its right-click → Move this key to the playhead)']],
  final: [['Drag on the ruler', 'scrub (also: the transport buttons, ← →)'], ["Drag a layer's bar · its ends", "move it in time · trim it (also: Trim in / out to the playhead, a layer's right-click)"],
    ["Alt-drag a layer's bar", 'slip its content between its in and out']],
  story: [['Drag between node handles (Flow)', 'connect two nodes; right-click a connection to delete it'], ['Drag a node (Flow)', 'move it; right-click the canvas → Add a node here'], ['Drag a clip block (Episode)', 'reorder (also: Earlier / Later)'],
    ['Drag the edge of a block (Episode)', 'trim in / out'], ['Drag the shaded overlap (Episode)', 'set the dissolve length (also: Dissolve toggles 12 frames)'], ['Drop a picture from the Bin on a style (World)', 'make it a sample of the style'], ['Drag a library tile (World › Library)', 'reorder it within its field (also: Move earlier / later)']],
}

/** D72: the gesture keys every suite shares — not remappable, listed so they are discoverable (07 §4). */
const FIXED_ROWS: [string, string][] = [['move the selection / step frames / nudge a transform box', '← ↑ → ↓'], ['cancel, close, back out of the loupe', 'Esc'],
  ['hold to pan in Edit · play / pause in Shots', 'Space'], ['focus mode · swap in Compare', 'Tab']]

/** D121: Animate's modes by their names (their suites' ids are stage · animate · final). */
const SECTION: Record<string, string> = { stage: 'Shots · Clay', animate: 'Shots · Performance', final: 'Shots · Final', catalogue: 'Bin', generate: 'World · Make', edit: 'World · Edit' }   // B2 (D159): the layers' names

export function HelpOverlay() {
  const setHelp = useSession((s) => s.setHelp)
  const suite = useSession((s) => s.ui.suite)
  useKeymap((k) => k.version)                                            // D72: rows follow a remap
  const row = (c: Command): [string, string, string?] => [c.label, c.keys ? keyLabel(c.keys) : '—', [c.hint, c.fixed ? 'fixed key' : ''].filter(Boolean).join(' · ') || undefined]
  const sections: [string, [string, string, string?][]][] = [
    [SECTION[suite] ?? suite, commandsAt(suite).map(row)],
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
