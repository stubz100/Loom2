// D95 (IM1, proto01_animate 03 §3): Image's two modes in the panel head — Make (the generate suite) and Edit (the edit suite), opened in
// place; in Edit, "← Results" goes back to Make. Both are the registry's suite commands (D32), so the palette and remapped keys reach them.
import { ArrowLeft } from 'lucide-react'
import { useSession } from '../store/session'
import { markUsed, runCommand } from './commands'

export function ImageModeSwitch() {
  const suite = useSession((s) => s.ui.suite)
  markUsed('global.suite.generate'); markUsed('global.suite.edit')
  return (
    <span className="image-mode">
      {suite === 'edit' && <button type="button" className="quiet image-back" onClick={() => runCommand('global.suite.generate')} title="Back to the results (Image · Make)"><ArrowLeft size={14} /> Results</button>}
      <span className="segmented" role="group" aria-label="Image mode">
        <button type="button" className={suite === 'generate' ? 'active' : ''} aria-pressed={suite === 'generate'} onClick={() => runCommand('global.suite.generate')} title="Make: generate images; the results grid">Make</button>
        <button type="button" className={suite === 'edit' ? 'active' : ''} aria-pressed={suite === 'edit'} onClick={() => runCommand('global.suite.edit')} title="Edit: the open document (layers, brushes, selection, AI)">Edit</button>
      </span>
    </span>
  )
}
