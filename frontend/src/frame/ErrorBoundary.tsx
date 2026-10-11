// A render error must not blank the window: without a boundary React unmounts the whole tree (2026-10-11 — a CI run found the app with
// no `.frame` at all and nothing to say why). Around the app and around each lazily loaded suite part (D69): the part says it failed,
// with the error, and offers Try again (`onReset`: a lazy suite remounts its parts) or a reload. Code that failed to load (a chunk
// fetch) cannot be retried in place — the browser keeps the failed module for the page — so Reload is the first offer then.
// The error also reaches the console (and, uncaught, the crash overlay).
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  label: string
  children?: ReactNode
  onReset?: () => void
  /** 'line': one muted line (a panel beside the part that explains); 'hide': nothing (strip, inspector, foot) */
  quiet?: 'line' | 'hide'
}

const CHUNK = /dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk/i
const isChunkError = (e: Error | null): boolean => !!e && CHUNK.test(e.message)

export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`loom2: ${this.props.label} could not be shown`, error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    if (this.props.quiet === 'hide') return null
    const chunk = isChunkError(error)
    if (this.props.quiet === 'line') return <p className="render-error-line">{this.props.label} is not available — see the middle of the window.</p>
    const retry = <button className={chunk ? 'quiet' : 'primary'} onClick={() => { this.props.onReset?.(); this.setState({ error: null }) }}>Try again</button>
    const reload = <button className={chunk ? 'primary' : 'quiet'} onClick={() => location.reload()}>Reload the app</button>
    return (
      <div className="render-error" role="alert">
        <b>{chunk ? `${this.props.label}'s code could not be loaded` : `${this.props.label} could not be shown`}</b>
        {chunk && <span>Reloading the app fetches it again; your work is saved.</span>}
        <pre>{error.message}</pre>
        <div className="row-btns">{chunk ? <>{reload}{retry}</> : <>{retry}{reload}</>}</div>
      </div>
    )
  }
}
