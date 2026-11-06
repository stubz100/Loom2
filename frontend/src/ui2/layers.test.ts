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
    expect(useLayer.getState().layer).toBe('clay')                                          // C0 (D181): the stage suite is Clay's
    expect(location.hash).toBe('#clay')
    navigate({ suite: 'animate' })
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
  it('K9: a layer tab moves the suite off another layer’s (its keys go quiet), back to where that layer was left', () => {
    const off = followNavigation()
    navigate({ suite: 'animate' })                                                          // Performance on Shots
    useLayer.getState().setLayer('bin')                                                     // the Bin tab
    expect(useSession.getState().ui.suite).toBe('catalogue')                                // not Performance's: V no longer queues variations
    navigate({ suite: 'edit' })                                                             // World's Edit
    useLayer.getState().setLayer('clay')
    expect(useSession.getState().ui.suite).toBe('stage')
    useLayer.getState().setLayer('world')
    expect(useSession.getState().ui.suite).toBe('edit')                                     // where World was left
    useLayer.getState().setLayer('shots')
    expect(useSession.getState().ui.suite).toBe('animate')
    navigate({ suite: 'stage' })
    useLayer.getState().setLayer('clay')                                                    // already the layer's suite: kept
    expect(useSession.getState().ui.suite).toBe('stage')
    off()
  })
  it('follows a hash the author follows', () => {
    const off = followNavigation()
    location.hash = '#bin'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    expect(useLayer.getState().layer).toBe('bin')
    off()
  })
})
