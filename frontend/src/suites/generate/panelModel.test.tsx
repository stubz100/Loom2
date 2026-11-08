// The review of 2026-11-06, K65 (T8): a fresh panel's model id is '' (the recipe runs the variant's t2i default) — the column's sections
// read the capabilities of that default, not of '': its card is highlighted, Turbo shows (it is sent), CFG is fixed on a distilled model,
// the references count the model's own limit, the size tiers are its own. (Made-up ids: D65's check keeps the roster's out of code.)
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Capabilities } from '../../api/types'
import { useSession } from '../../store/session'
import { ModelSection, RefsSection, SizeSection } from './GenerateColumn'
import { DEFAULT_PANEL, panelModelOf, partModel, recipeFromPanel, useGenerate } from './generateStore'

const DEF = 'test-default', OTHER = 'test-other'
const CAPS = {
  defaults: { t2i: DEF },
  models: {
    [DEF]: { order: 1, label: 'Default', short: 'D', family: 'fam-a', turbo: true, distilled: true, steps: 4, max_refs: 10, wired: true, inputs: {}, recipes: { t2i: true } },
    [OTHER]: { order: 2, label: 'Other', short: 'O', family: 'fam-b', turbo: false, distilled: false, max_refs: 4, wired: true, inputs: {}, recipes: { t2i: true } },
  },
  tiers: { draft: { [DEF]: [1024, 576], 'fam-b': [960, 544] } },
  samplers: [], schedulers: [], weight_dtypes: [], te_devices: [],
} as unknown as Capabilities
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('not stubbed', { status: 500 })))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useSession.setState({ capabilities: CAPS })
  useGenerate.setState({ panel: { ...DEFAULT_PANEL, model_id: '', turbo: true, tier: 'draft' }, preview: null })
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  host?.remove(); host = null; root = null
  vi.unstubAllGlobals()
  useSession.setState({ capabilities: null })
})

describe("K65 the panel's empty model is the default everywhere the column reads it", () => {
  it('panelModelOf resolves an empty or unknown id against the given capabilities, a known one stays', () => {
    expect(panelModelOf({ model_id: '' }, CAPS)).toBe(DEF)
    expect(panelModelOf({ model_id: OTHER }, CAPS)).toBe(OTHER)
    expect(panelModelOf({ model_id: '' }, null)).toBe('')                                 // nothing known yet
    expect(recipeFromPanel(useGenerate.getState().panel).model_id).toBe(DEF)
    expect(partModel()).toBe(DEF)                                                         // the card the column shows
  })

  it('the Model section highlights the default card, shows Turbo (the recipe sends it) and fixes CFG on the distilled default', () => {
    const el = render(<ModelSection />)
    expect(el.querySelector(`[data-model="${DEF}"]`)?.getAttribute('aria-pressed')).toBe('true')
    expect(el.textContent).toContain('8-step Turbo LoRA')
    expect(recipeFromPanel(useGenerate.getState().panel).turbo).toBe(true)
    const cfg = [...el.querySelectorAll('label')].find((l) => l.textContent === 'CFG')?.nextElementSibling?.querySelector('input')
    expect(cfg?.disabled).toBe(true)
  })

  it("the References heading counts the default model's limit; the size tiers are its own", () => {
    expect(render(<RefsSection />).querySelector('.gen-sec-head')?.textContent).toContain('References · 0 of 10')
    const el = render(<SizeSection />)
    expect(el.querySelector('[aria-label="size tier"]')?.innerHTML).toContain('1024×576')
  })
})
