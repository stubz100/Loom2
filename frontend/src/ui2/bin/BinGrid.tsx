// B0 (D159, proto01_UI2 11 R2): the Bin's grid, windowed — only the rows in view (and a few around them) are drawn, however many things a
// home holds; as the last rows come into view it asks for the next page (`onEnd`). Square tiles fill the width at no less than `min` px.
import { useVirtualizer } from '@tanstack/react-virtual'
import { Fragment, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

const PAD = 12

export function BinGrid<T>({ items, keyOf, render, onEnd, min = 150, gap = 8, className = '' }: {
  items: T[]; keyOf: (t: T) => string; render: (t: T) => ReactNode; onEnd?: () => void; min?: number; gap?: number; className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [])
  const inner = Math.max(0, width - PAD * 2)
  const cols = Math.max(1, Math.floor((inner + gap) / (min + gap)))
  const cell = Math.max(40, (inner - gap * (cols - 1)) / cols)
  const rows = Math.ceil(items.length / cols)
  const virt = useVirtualizer({ count: rows, getScrollElement: () => ref.current, estimateSize: () => cell + gap, overscan: 4,
    getItemKey: (i) => keyOf(items[i * cols]) ?? i, paddingStart: PAD, paddingEnd: PAD })
  useEffect(() => { virt.measure() }, [cell, cols, virt])
  const vitems = virt.getVirtualItems()
  const last = vitems.length ? vitems[vitems.length - 1].index : -1
  useEffect(() => { if (onEnd && rows && last >= rows - 3) onEnd() }, [last, rows, onEnd])
  return (
    <div ref={ref} className={`b-grid ${className}`}>
      <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
        {vitems.map((v) => (
          <div key={v.key} className="b-row" style={{ position: 'absolute', top: 0, left: PAD, right: PAD, height: cell, transform: `translateY(${v.start}px)`,
            display: 'grid', gridTemplateColumns: `repeat(${cols}, ${cell}px)`, gap }}>
            {items.slice(v.index * cols, v.index * cols + cols).map((t) => <Fragment key={keyOf(t)}>{render(t)}</Fragment>)}
          </div>
        ))}
      </div>
    </div>
  )
}
