import { lazy, Suspense } from 'react'
import { ErrorBoundary } from './frame/ErrorBoundary'
import { Frame } from './frame/Frame'

// D155: `?view=loupe` is the detached loupe / player window — the same bundle, no Frame (lazy: the main window never loads it)
const DetachedLoupe = lazy(() => import('./frame/DetachedLoupe'))
const view = new URLSearchParams(location.search).get('view')

export default function App() {
  return <ErrorBoundary label="loom2">{view === 'loupe' ? <Suspense fallback={null}><DetachedLoupe /></Suspense> : <Frame />}</ErrorBoundary>
}
