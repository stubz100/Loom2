// U1 (D157, proto01_UI2 06 §5.3, seam 2): the suites' key hooks — and Edit's paste, deep links and autosave with them — are mounted by the
// shell, not inside a Strip, so a shell without those Strips (the new one) keeps them. A suite registers its host when its code loads; each
// host checks the place itself (`ui.suite`), as it did inside its Strip, so a host mounted early does nothing until its suite is on screen.
import type { ComponentType } from 'react'
import { create } from 'zustand'

const useHosts = create<{ hosts: Record<string, ComponentType> }>()(() => ({ hosts: {} }))

/** A suite's key host: a component that mounts its key hook and renders nothing. Registered again under the same id, it replaces the first. */
export function registerKeyHost(id: string, Host: ComponentType): void {
  useHosts.setState((s) => ({ hosts: { ...s.hosts, [id]: Host } }))
}

/** The ids registered so far (tests). */
export const keyHostIds = (): string[] => Object.keys(useHosts.getState().hosts)

/** Mounted once by each shell (frame/Frame.tsx, ui2/Shell.tsx). */
export function KeyHosts() {
  const hosts = useHosts((s) => s.hosts)
  return <>{Object.entries(hosts).map(([id, Host]) => <Host key={id} />)}</>
}
