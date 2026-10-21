// D116 (house rule 11): explanatory text never sits as a block on the screen — it hides behind this small question mark and shows on hover
// (the author: "the screen is clogged enough without having blocks of text added to it"). Status lines stay short; this carries the why
// and the how. Mouse-first: a hover, nothing to press; the text is also the icon's accessible label.
import { CircleHelp } from 'lucide-react'

export function Help({ text, size = 12, className = '' }: { text: string; size?: number; className?: string }) {
  return <span className={`help ${className}`} title={text} role="img" aria-label={text} data-help><CircleHelp size={size} /></span>
}
