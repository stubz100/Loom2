// B2a (D159, 11 §7): a lazily loaded part of a layer — its Suspense and its error boundary, as the old registry gave each suite part (D69):
// a part whose code fails to load says so in the middle (the column says one line, the Inspector nothing) and the rest of the shell stays.
import { Suspense, type ReactNode } from 'react'
import { ErrorBoundary } from '../frame/ErrorBoundary'

export function Part({ label, quiet, fallback = null, children }: { label: string; quiet?: 'line' | 'hide'; fallback?: ReactNode; children: ReactNode }) {
  return <ErrorBoundary label={label} quiet={quiet}><Suspense fallback={fallback}>{children}</Suspense></ErrorBoundary>
}
