import { lazy, Suspense } from 'react'
import { ErrorBoundary } from './frame/ErrorBoundary'
import { Shell } from './ui2/Shell'

// D155: `?view=loupe` is the detached loupe / player window — the same bundle, no shell (lazy: the main window never loads it)
const DetachedLoupe = lazy(() => import('./frame/DetachedLoupe'))
const view = new URLSearchParams(location.search).get('view')

/** B2 (D159): the new shell (D157) is the only one; the old frame and its Catalogue are gone. */
export default function App() {
  return <ErrorBoundary label="loom2">{view === 'loupe' ? <Suspense fallback={null}><DetachedLoupe /></Suspense> : <Shell />}</ErrorBoundary>
}
