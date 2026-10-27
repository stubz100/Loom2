// The review of 2026-10-27, V70 (T8): a panel naming a model this build does not offer takes the resolved model — when the panel is
// set and when the capabilities arrive after a remembered panel — so what the column shows is what the job runs. (Made-up ids: D65's
// check keeps the roster's out of code.)
import { beforeEach, describe, expect, it } from 'vitest'
import { useSession } from '../../store/session'
import { useGenerate } from './generateStore'

const BASE = 'test-base', TURBO = 'test-turbo', GONE = 'test-retired'
const caps = { models: { [BASE]: { family: 'test', turbo: false }, [TURBO]: { family: 'test', turbo: true } }, defaults: { t2i: BASE },
  tiers: { draft: { test: [960, 544], [BASE]: [960, 544] } } }

describe('a retired model in the panel (V70)', () => {
  beforeEach(() => { useSession.setState({ capabilities: null, toasts: [] } as never); useGenerate.setState({ panel: { ...useGenerate.getState().panel, model_id: BASE, tier: 'draft' } }) })

  it('set(): a model the build does not offer becomes the resolved one, with a toast', () => {
    useSession.setState({ capabilities: caps } as never)
    useGenerate.getState().set({ model_id: GONE })
    expect(useGenerate.getState().panel.model_id).toBe(BASE)
    expect(useGenerate.getState().panel).toMatchObject({ width: 960, height: 544 })
    expect(useSession.getState().toasts.some((t) => t.text.includes(`${GONE} is not in this build`))).toBe(true)
    useGenerate.getState().set({ model_id: TURBO })                                          // an offered model stays
    expect(useGenerate.getState().panel.model_id).toBe(TURBO)
  })

  it('the capabilities arriving after a remembered panel settle it', () => {
    useGenerate.setState({ panel: { ...useGenerate.getState().panel, model_id: GONE } })
    expect(useGenerate.getState().panel.model_id).toBe(GONE)                                  // nothing to check against yet
    useSession.setState({ capabilities: { ...caps } } as never)
    expect(useGenerate.getState().panel.model_id).toBe(BASE)
  })
})
