import { ErrorBoundary } from './frame/ErrorBoundary'
import { Frame } from './frame/Frame'

export default function App() {
  return <ErrorBoundary label="loom2"><Frame /></ErrorBoundary>
}
