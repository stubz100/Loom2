// D71 (ArtCraft P15): the `?tool=` / `?ai=` / `?sel=` deep links reach Edit with the tool and the AI operation chosen; unknown values
// are ignored, and a link without a known tool or operation does nothing.
import { describe, expect, it } from 'vitest'
import { deepLinkOf } from './openWith'

const q = (s: string) => new URLSearchParams(s)

describe('deepLinkOf', () => {
  it('reads Edit, the AI tool and AI Select · Subject', () => {
    expect(deepLinkOf(q('suite=edit&tool=ai&ai=select&sel=subject'))).toEqual({ assetId: null, o: { suite: 'edit', tool: 'ai', aiOp: 'select', selMode: 'subject' } })
  })
  it('takes an asset to open', () => {
    expect(deepLinkOf(q('suite=edit&ai=upscale&asset=ast_1'))).toEqual({ assetId: 'ast_1', o: { suite: 'edit', aiOp: 'upscale' } })
  })
  it('ignores unknown values and other suites', () => {
    expect(deepLinkOf(q('suite=edit&tool=lasso&ai=teleport&sel=psychic'))).toEqual({ assetId: null, o: { suite: 'edit', tool: 'lasso' } })
    expect(deepLinkOf(q('suite=edit&tool=nope'))).toBeNull()
    expect(deepLinkOf(q('suite=generate&tool=ai'))).toBeNull()
    expect(deepLinkOf(q('suite=edit'))).toBeNull()
  })
})
