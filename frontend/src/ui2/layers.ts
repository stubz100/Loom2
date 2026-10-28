// U1 (D157, proto01_UI2 02 §1, §4): the new shell's layer — World · Shots · Episode · Bin. It follows every `navigate` (a store or a
// command going to an old place lands on that place's layer) and the URL's hash (`#world`, `#shots`, `#episode`, `#bin`), so a reload stays
// where the author was; the deeper parts of a place (`#world/character/<id>/v1`) come with their layers.
import { create } from 'zustand'
import { layerOf, onNavigate, type Layer } from '../frame/router'

export const LAYERS: { id: Layer; label: string; key: string }[] = [
  { id: 'world', label: 'World', key: '1' }, { id: 'shots', label: 'Shots', key: '2' }, { id: 'episode', label: 'Episode', key: '3' }, { id: 'bin', label: 'Bin', key: '4' },
]

/** The layer a hash names (`#shots/…` → shots), else null. */
export function layerFromHash(hash: string): Layer | null {
  const head = hash.replace(/^#/, '').split('/')[0]
  return LAYERS.some((l) => l.id === head) ? (head as Layer) : null
}

interface LayerState { layer: Layer; setLayer: (l: Layer) => void }
export const useLayer = create<LayerState>()((set, get) => ({
  layer: layerFromHash(location.hash) ?? 'world',
  setLayer: (layer) => {
    if (get().layer !== layer) set({ layer })
    if (layerFromHash(location.hash) !== layer) history.replaceState(null, '', `${location.pathname}${location.search}#${layer}`)
  },
}))

/** Mounted by the new shell: navigations land on their layer, a hash typed or followed moves the layer. Returns the cleanup. */
export function followNavigation(): () => void {
  const off = onNavigate((p) => useLayer.getState().setLayer(layerOf(p)))
  const onHash = () => { const l = layerFromHash(location.hash); if (l) useLayer.getState().setLayer(l) }
  window.addEventListener('hashchange', onHash)
  return () => { off(); window.removeEventListener('hashchange', onHash) }
}
