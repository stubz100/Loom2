import { lazy, Suspense } from 'react'
import { ErrorBoundary } from './frame/ErrorBoundary'
import { Frame } from './frame/Frame'
import { UI2 } from './frame/router'

// D155: `?view=loupe` is the detached loupe / player window — the same bundle, no Frame (lazy: the main window never loads it)
const DetachedLoupe = lazy(() => import('./frame/DetachedLoupe'))
// U1 (D157, proto01_UI2 07 §1): `?ui=2` is the new shell, built beside the old one on the same records (lazy: the old shell never loads it)
const Shell = lazy(() => import('./ui2/Shell').then((m) => ({ default: m.Shell })))
const view = new URLSearchParams(location.search).get('view')

export default function App() {
  return <ErrorBoundary label="loom2">{view === 'loupe' ? <Suspense fallback={null}><DetachedLoupe /></Suspense> : UI2 ? <Suspense fallback={null}><Shell /></Suspense> : <Frame />}</ErrorBoundary>
}
