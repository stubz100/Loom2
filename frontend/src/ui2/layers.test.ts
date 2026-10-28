// U1 (D157, proto01_UI2 02 §4): the new shell's layer follows the old places a navigation names and the URL's hash, and writes the hash back.
import { afterEach, describe, expect, it } from 'vitest'
import { navigate } from '../frame/router'
import { useSession } from '../store/session'
import { followNavigation, layerFromHash, useLayer } from './layers'

describe('U1: the layers', () => {
  afterEach(() => { useSession.getState().setSuite('catalogue'); history.replaceState(null, '', location.pathname) })
  it('reads a layer from a hash, its deeper parts aside', () => {
    expect(layerFromHash('#shots/sht_1/clay')).toBe('shots')
    expect(layerFromHash('#bin')).toBe('bin')
    expect(layerFromHash('#nowhere')).toBeNull()
    expect(layerFromHash('')).toBeNull()
  })
  it('lands a navigation on its layer and keeps the hash in step', () => {
    const off = followNavigation()
    navigate({ suite: 'stage' })
    expect(useLayer.getState().layer).toBe('shots')
    expect(location.hash).toBe('#shots')
    navigate({ suite: 'story', tab: 'episode' })
    expect(useLayer.getState().layer).toBe('episode')
    navigate({ suite: 'generate' })
    expect(useLayer.getState().layer).toBe('world')
    off()
    navigate({ suite: 'catalogue' })                                                        // unmounted: the layer stays
    expect(useLayer.getState().layer).toBe('world')
  })
  it('follows a hash the author follows', () => {
    const off = followNavigation()
    location.hash = '#bin'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    expect(useLayer.getState().layer).toBe('bin')
    off()
  })
})
