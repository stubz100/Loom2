// D90 (02 §6.1) → D95 (IM1): a one-column panel and its rail, in sync both ways. A rail click (or a deep link) scrolls to the section
// `#${prefix}${tab}`; scrolling the Panel's body moves the rail's highlight to the last section whose top has passed the body's top (+24 px).
// Generate's column (Image · Make) and Edit's (Image · Edit) use it; Animate's will (AN1).
import { useEffect, useRef, type RefObject } from 'react'
import { setRailTab } from './router'

export function useColumnSync(host: RefObject<HTMLElement | null>, suite: string, sections: readonly string[], prefix: string, tab: string): void {
  const fromScroll = useRef(false)
  const active = useRef(tab)
  useEffect(() => {                                                       // a rail click (or a deep link) scrolls to its section
    active.current = tab
    if (fromScroll.current) { fromScroll.current = false; return }
    document.getElementById(`${prefix}${tab}`)?.scrollIntoView({ block: 'start' })
  }, [tab, prefix])
  useEffect(() => {                                                       // … and scrolling moves the rail's highlight
    const body = host.current?.closest('.body') as HTMLElement | null
    if (!body) return
    const h = () => {
      const top = body.getBoundingClientRect().top + 24
      let cur: string = sections[0]
      for (const id of sections) { const el = document.getElementById(`${prefix}${id}`); if (el && el.getBoundingClientRect().top <= top) cur = id }
      if (cur !== active.current) { active.current = cur; fromScroll.current = true; setRailTab(suite, cur) }
    }
    body.addEventListener('scroll', h, { passive: true })
    return () => body.removeEventListener('scroll', h)
  }, [host, suite, sections, prefix])
}
