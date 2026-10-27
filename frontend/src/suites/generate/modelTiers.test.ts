// The review of 2026-10-27, V16: picking a model takes the tier's size from the model's own entry in /capabilities.tiers, and only
// where it has none from its family's (krea2-raw's Full is 1344×768, the family's first spec — the turbo — says 1920×1088).
import { describe, expect, it } from 'vitest'
import { useSession } from '../../store/session'
import { modelPatch } from './generateStore'

describe('modelPatch tiers (V16)', () => {
  it('the model’s own tier size, else its family’s', () => {
    useSession.setState({
      capabilities: {
        models: { 'krea2-raw': { family: 'krea2', turbo: false }, 'krea2-turbo': { family: 'krea2', turbo: true } },
        tiers: { full: { krea2: [1920, 1088], 'krea2-raw': [1344, 768] }, draft: { krea2: [960, 544] } },
      } as never,
    })
    const panel = { tier: 'full', turbo: false, width: 1, height: 1, model_id: 'x' } as never
    expect(modelPatch(panel, 'krea2-raw')).toMatchObject({ model_id: 'krea2-raw', width: 1344, height: 768 })
    expect(modelPatch(panel, 'krea2-turbo')).toMatchObject({ model_id: 'krea2-turbo', width: 1920, height: 1088 })
    expect(modelPatch({ ...(panel as object), tier: 'draft' } as never, 'krea2-raw')).toMatchObject({ width: 960, height: 544 })
    expect(modelPatch({ ...(panel as object), tier: 'custom' } as never, 'krea2-raw')).not.toHaveProperty('width')
  })
})
