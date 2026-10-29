// U3c (D157, proto01_UI2 03 §4): Edit, the same editor, on a creation of the entity's bin. Image's editor is mounted as it is (its column,
// strip, canvas and Inspector); it opens the selected creation (`openFromAsset` navigates to Edit, and the router keeps the World layer — so
// the editor's keys, paste and autosave come alive with it). Saving writes a new creation into the same bin, as a candidate, a reference
// or the hero. Loaded lazily: the editor's Pixi code stays out of World until Edit is asked for.
import { CommandButton } from '../../frame/CommandButton'
import { EditSuite } from '../../suites/edit/EditSuite'
import { useEditor } from '../../suites/edit/editorStore'
import { saveIntoBin } from './editSave'

export function WorldEditColumn() {
  return <EditSuite.Panel tab="tools" />
}

export function WorldEditCentre() {
  const doc = useEditor((s) => s.doc)
  const saving = useEditor((s) => s.saving)
  return (
    <div className="w-edit" data-testid="world-edit">
      <div className="strip w-edit-strip"><EditSuite.Strip /></div>{/* the frame's strip row (frame.css), as the old shell hosts it */}
      <div className="w-edit-stage"><EditSuite.Stage /></div>
      {doc && <div className="w-edit-foot">
        <button className="primary" disabled={saving} onClick={() => void saveIntoBin('candidate')}>{saving ? 'Saving…' : 'Save into the bin'}</button>
        <CommandButton id="world.edit.saveReference" text /><CommandButton id="world.edit.saveHero" text /><CommandButton id="world.mode.make" text />
      </div>}
    </div>
  )
}

export function WorldEditInspector() {
  return <aside className="w-insp edit"><EditSuite.Inspector /></aside>
}
