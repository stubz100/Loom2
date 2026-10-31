// W6 (≈ F23), W13: a picture's prompt in an Inspector — readable (promptText.ts), long prompts clamped with *more* / *less*, the whole on hover.
import { useState } from 'react'
import { readablePrompt } from './promptText'

export function PromptBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const shown = readablePrompt(text)
  const long = shown.length > 360 || shown.split('\n').length > 8
  return (
    <div className="w-prompt-block"><span>prompt</span>
      <p className={`w-prompt${open ? ' open' : ''}`} title={shown}>{shown}</p>
      {long && <button type="button" className="link" onClick={() => setOpen(!open)}>{open ? 'less' : 'more'}</button>}
    </div>
  )
}
