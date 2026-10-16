// D90 (02 §5): the For chip at the top of a maker's Panel — "For: Shot 12 · v3 ✕" and "← Back to Shot 12". It shows only while the maker
// was opened for a Story object (Make frame ▸ / Make clip ▸); its submissions then carry the `for_shot` origin. ✕ ends that: the maker
// works exactly as when it was opened from its tab. Both verbs are registry commands (storyCommands.ts: gen.for.* / anim.for.*).
import { Clapperboard } from 'lucide-react'
import { CommandButton } from '../../frame/CommandButton'
import { forLabel, useMakeFor, type Maker } from '../../store/origin'
import './forChip.css'

export function ForChip({ maker }: { maker: Maker }) {
  const f = useMakeFor((s) => s[maker])
  if (!f) return null
  const p = maker === 'generate' ? 'gen' : 'anim'
  return (
    <div className="for-chip" data-testid="for-chip" title={`Every ${maker === 'generate' ? 'image' : 'clip'} made here also becomes a take of ${forLabel(f)} (and stays in the Catalogue)`}>
      <span className="for-what"><Clapperboard size={14} /> For: <b>{forLabel(f)}</b></span>
      <CommandButton id={`${p}.for.clear`} className="quiet" size={14} />
      <CommandButton id={`${p}.for.back`} text size={14} label={`Back to ${f.name}`} />
    </div>
  )
}
