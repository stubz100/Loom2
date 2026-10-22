// D121 (proto01_animate 26 §5): the parts every Animate level's column is made of — a section with its sticky head, and the column's host
// in sync with the level's rail (frame/columnSync.ts). Each level (Clay = the stage suite, Performance = animate, Final = final) lists its
// own sections; the ids keep the `anim-sec-` prefix, so a section is `#anim-sec-<id>` at whichever level shows it.
import { useRef, type ReactNode } from 'react'
import { useColumnSync } from '../../frame/columnSync'

export function Sec({ id, title, tools, children }: { id: string; title: string; tools?: ReactNode; children: ReactNode }) {
  return (
    <section id={`anim-sec-${id}`} className="col-sec">
      <h4 className="col-sec-head"><span>{title}</span><span className="spacer" />{tools}</h4>
      {children}
    </section>
  )
}

/** A level's column: the rail jumps to its sections and follows the scroll. `sections` must be a module constant (an effect depends on it). */
export function AnimColumn({ suite, sections, tab, children }: { suite: string; sections: readonly string[]; tab: string; children: ReactNode }) {
  const host = useRef<HTMLDivElement>(null)
  useColumnSync(host, suite, sections, 'anim-sec-', tab)
  return <div ref={host} className="col-column anim-column" data-level={suite}>{children}</div>
}
