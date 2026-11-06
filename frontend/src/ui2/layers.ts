// U1 (D157, proto01_UI2 02 §1, §4): the new shell's layer — World · Shots · Episode · Bin; C0 (D181): Clay between World and Shots. It follows every `navigate` (a store or a
// command going to an old place lands on that place's layer) and the URL's hash (`#world`, `#shots`, `#episode`, `#bin`), so a reload stays
// where the author was; the deeper parts of a place (`#world/character/<id>/v1`) come with their layers.
import { create } from 'zustand'
import { currentPlace, layerOf, onNavigate, settleSuite, type Layer, type Place } from '../frame/router'

export const LAYERS: { id: Layer; label: string; key: string }[] = [
  { id: 'world', label: 'World', key: '1' }, { id: 'clay', label: 'Clay', key: '2' }, { id: 'shots', label: 'Shots', key: '3' }, { id: 'episode', label: 'Episode', key: '4' }, { id: 'bin', label: 'Bin', key: '5' },
]

/** The layer a hash names (`#shots/…` → shots), else null. */
export function layerFromHash(hash: string): Layer | null {
  const head = hash.replace(/^#/, '').split('/')[0]
  return LAYERS.some((l) => l.id === head) ? (head as Layer) : null
}

/** K9: the place a layer was last left at, and where it starts — the key hosts and the reused parts read the suite (`ui.suite`), so a layer
 *  shown while the suite is another layer's left that layer's keys live (V in the Bin queued Variations of the hidden clip). */
const DEFAULT_PLACE: Record<Layer, Place> = { world: { suite: 'generate' }, clay: { suite: 'stage' }, shots: { suite: 'story', tab: 'flow' },
  episode: { suite: 'story', tab: 'episode' }, bin: { suite: 'catalogue' } }
const lastPlace: Partial<Record<Layer, Place>> = {}

/** K9: the suite put under the layer shown when it is another layer's. */
function settleOn(layer: Layer): void {
  if (layerOf(currentPlace()) !== layer) settleSuite(lastPlace[layer] ?? DEFAULT_PLACE[layer])
}

interface LayerState { layer: Layer; setLayer: (l: Layer) => void }
export const useLayer = create<LayerState>()((set, get) => ({
  layer: layerFromHash(location.hash) ?? 'world',
  setLayer: (layer) => {
    const switched = get().layer !== layer
    if (switched) set({ layer })
    if (layerFromHash(location.hash) !== layer) history.replaceState(null, '', `${location.pathname}${location.search}#${layer}`)
    if (switched) settleOn(layer)                                           // K9: only a switch to another layer — a navigation inside one leaves the suite to it
  },
}))

/** Mounted by the new shell: navigations land on their layer, a hash typed or followed moves the layer. Returns the cleanup. */
export function followNavigation(): () => void {
  const off = onNavigate((p) => { lastPlace[layerOf(p)] = p; useLayer.getState().setLayer(layerOf(p)) })
  settleOn(useLayer.getState().layer)                                      // K9: a reload at #bin with a persisted Performance suite is put right
  const onHash = () => { const l = layerFromHash(location.hash); if (l) useLayer.getState().setLayer(l) }
  window.addEventListener('hashchange', onHash)
  return () => { off(); window.removeEventListener('hashchange', onHash) }
}
