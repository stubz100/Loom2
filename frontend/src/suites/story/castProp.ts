// proto01_UIcast CF8 (CW0): a loose 3D model becomes a Cast prop's — "Make it a Cast prop ▸" on a mesh (the Catalogue's and Image's tiles,
// the Bin, a loose mesh on a stage): a new prop, its model this mesh and its hero the picture the mesh was made from, or an open prop
// version whose model it becomes (D110's PUT …/model; the server records the source picture). The caller binds what it placed (Clay).
import { Package, PackagePlus } from 'lucide-react'
import type { Asset, Profile } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { askText, useSession } from '../../store/session'
import { useStory } from './storyStore'

type Mesh = Pick<Asset, 'id' | 'parents'>
type Done = (pid: string) => void

const open = (pid: string, vid: string) => () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: pid, version: vid }))

/** A new prop whose model is the mesh; the picture it was made from (its first parent) becomes the hero, as *Add to Cast as the hero*. */
export async function newPropFrom(mesh: Mesh, name: string, done?: Done): Promise<Profile | null> {
  const st = useStory.getState()
  const p = await st.createProfile(name, 'prop', null)
  if (!p) return null
  const next = await st.setPropModel(p.id, p.current, mesh.id)
  if (!next) return null
  const source = mesh.parents?.[0]
  if (source) await st.addToProfile(p.id, [source], 'hero')
  useSession.getState().toast(`${p.name} is a Cast prop — this is its 3D model`, 'success', { label: `Open ${p.name} in World`, run: open(p.id, p.current) })
  done?.(p.id)
  return next
}

/** The mesh as an existing prop's model (its current version, which must be open). */
export async function intoProp(mesh: Mesh, p: Profile, done?: Done): Promise<Profile | null> {
  const next = await useStory.getState().setPropModel(p.id, p.current, mesh.id)
  if (!next) return null
  useSession.getState().toast(`This is ${p.name}'s 3D model now (${p.current})`, 'success', { label: `Open ${p.name} in World`, run: open(p.id, p.current) })
  done?.(p.id)
  return next
}

/** "Make it a Cast prop ▸": *New prop…* (named by the author), then each prop whose current version is open, the model it would replace said. */
export function castPropMenu(mesh: Mesh, done?: Done): Extract<MenuItem, { items: MenuItem[] }> {
  const props = useStory.getState().profiles.filter((p) => p.cls === 'prop')
  const items: MenuItem[] = [
    { label: 'New prop…', icon: PackagePlus, run: () => void askText({ title: 'A new Cast prop from this 3D model', text: 'The model becomes the prop\'s; the picture it was made from, its hero.', placeholder: 'prop name' })
      .then((n) => { if (n?.trim()) void newPropFrom(mesh, n.trim(), done) }) },
    ...(props.length ? [{ heading: 'As the model of' } as MenuItem] : []),
    ...props.map((p): MenuItem => {
      const v = p.versions.find((x) => x.id === p.current)
      const has = !!v?.model_asset_id && v.model_asset_id !== mesh.id
      return { label: `${p.name} · ${p.current}${has ? ' (replaces its model)' : ''}`, disabled: v?.state !== 'open' || v?.model_asset_id === mesh.id, run: () => void intoProp(mesh, p, done) }
    }),
  ]
  return { label: 'Make it a Cast prop', icon: Package, items }
}
