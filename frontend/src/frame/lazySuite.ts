// D69 (ArtCraft P5): a suite whose code loads on first use. Its rail and flags are static (the frame shows them at once); Panel, Strip,
// Stage, Inspector and PrimaryAction come from `load()` on first render, each behind its own Suspense skeleton, so the frame stays generic.
// Once the code has loaded (the idle preload, a pointer over the tab), the parts render the suite's components directly: `React.lazy`
// suspends on its first render even for a resolved module, and React holds a revealed boundary back (≈ 300 ms throttle) — the first Edit
// open measured 420–500 ms that way against 210–225 ms eager. Plain `createElement` in a .ts module: the components are built per suite.
import { createElement, lazy, Suspense, useMemo, useState, type ComponentType, type ReactNode } from 'react'
import { create } from 'zustand'
import { ErrorBoundary } from './ErrorBoundary'
import type { SuiteDef } from './suiteRegistry'

type Part = 'Panel' | 'Strip' | 'Stage' | 'Inspector' | 'PrimaryAction'
type Loose = ComponentType<{ tab?: string }>
const Nothing = () => null
const loaders: Record<string, () => Promise<SuiteDef>> = {}

const busy = (className: string, text?: string): ReactNode => createElement('div', { className, 'aria-busy': true }, text)
const SKELETON: Record<Part, () => ReactNode> = {
  Panel: () => busy('suite-loading'), Inspector: () => busy('suite-loading'), Stage: () => busy('suite-loading stage-loading', 'Loading…'),
  Strip: () => null, PrimaryAction: () => null,
}

export function lazySuite(meta: Omit<SuiteDef, Part>, load: () => Promise<SuiteDef>, parts: Part[]): SuiteDef {
  let mod: Promise<SuiteDef> | undefined
  let ready: SuiteDef | undefined
  // a failed load is not kept: the next ask (Try again, a pointer over the tab) imports the chunk again
  const get = (loaders[meta.id] = () => (mod ??= load().then((d) => (ready = d), (e: unknown) => { mod = undefined; throw e })))
  const out = { ...meta } as SuiteDef
  const retries = create<{ n: number }>()(() => ({ n: 0 }))            // one Try again remounts every part of the suite
  for (const k of parts) {
    const make = () => lazy(() => get().then((d) => ({ default: (d[k] ?? Nothing) as Loose })))
    const label = `${meta.id[0].toUpperCase()}${meta.id.slice(1)}`
    const C: Loose = (props) => {
      const [direct] = useState(() => !!ready)                         // fixed per mount: switching the element type would remount the part
      const n = retries((r) => r.n)
      const L = useMemo(() => make(), [n]) // eslint-disable-line react-hooks/exhaustive-deps -- n is the retry count: a new lazy per retry (React.lazy keeps a rejection)
      const part = direct ? createElement((ready![k] ?? Nothing) as Loose, props) : createElement(Suspense, { fallback: SKELETON[k]() }, createElement(L, props))
      // the Stage explains a failure; the panel says one line, the strip / inspector / foot stay empty
      return createElement(ErrorBoundary, { key: n, label, quiet: k === 'Stage' ? undefined : k === 'Panel' ? 'line' : 'hide', onReset: () => retries.setState({ n: n + 1 }) }, part)
    }
    C.displayName = `${meta.id}.${k}`
    ;(out as unknown as Record<Part, Loose>)[k] = C
  }
  return out
}

/** Start loading a lazy suite's code before it is shown (pointer over its tab), so the click finds it loaded. */
export function preloadSuite(id: string): void { void loaders[id]?.().catch(() => undefined) }
