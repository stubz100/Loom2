// D139: a character's shell is made only from an A-pose picture — the command waits for the fit's verdict on the reference's stance, and a
// shell made from an arms-down picture says so (story.py shell_blocked / shell_from_arms_down). D140: the fit, too, only on an A-pose.
import { describe, expect, it } from 'vitest'
import { fitBlocked, shellBlocked, shellFromArmsDown } from './storyStore'

const v = { anim_ref_asset_id: 'ast_ref', body_points: { pose: [[0, 0, 1]] }, body_fit_from: 'ast_ref', anim_ref_note: null, shell_asset_id: null, shell_from: null } as never

describe('the shell needs the A-pose (D139)', () => {
  it('waits for a reference, its fit, then arms clear of the body', () => {
    expect(shellBlocked(v)).toBeNull()
    expect(shellBlocked({ ...(v as object), anim_ref_asset_id: null } as never)).toMatch(/animation reference first/)
    expect(shellBlocked({ ...(v as object), body_fit_from: 'ast_older' } as never)).toMatch(/fit the body/)          // fitted to another picture
    expect(shellBlocked({ ...(v as object), anim_ref_note: 'arms_close' } as never)).toMatch(/A-pose/)
  })
  it('names a shell made from the arms-down picture the version still has', () => {
    const fused = { ...(v as object), anim_ref_note: 'arms_close', shell_asset_id: 'ast_shell', shell_from: 'ast_ref' } as never
    expect(shellFromArmsDown(fused)).toBe(true)
    expect(shellFromArmsDown({ ...(fused as object), shell_from: 'ast_older' } as never)).toBe(false)
    expect(shellFromArmsDown({ ...(fused as object), anim_ref_note: null } as never)).toBe(false)
  })
})

describe('the fit needs the A-pose (D140)', () => {
  it('waits for a reference, and refuses one a fit found arms-down', () => {
    expect(fitBlocked(v)).toBeNull()
    expect(fitBlocked({ ...(v as object), anim_ref_asset_id: null } as never)).toMatch(/animation reference first/)
    expect(fitBlocked({ ...(v as object), anim_ref_note: 'arms_close' } as never)).toMatch(/only on an A-pose/)
    expect(shellBlocked({ ...(v as object), anim_ref_note: 'arms_close', body_fit_from: 'ast_older' } as never)).toMatch(/A-pose/)   // the stance before the fit
  })
})
