// D93 phase A: a subject card linked to a Cast profile — "Give <name> a look" while the version has no hero and no references, "More
// looks for <name>" after, refused for a final version (A1); its slots in the prompt as the preview gave them (A3); the name-only warning
// and the casting run's ask (A9); the index the server reads (the subjects the prompt sends, blank cards skipped).
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { Binding, Profile } from '../../api/types'
import { bindingLines, castOffer, castOrigin, nameOnly, needsLook, sentIndex, slotsOf } from './subjectCast'
import { CastButton, SubjectSlots, SubjectWarn } from './SubjectLink'

const prof = (v: Partial<Profile['versions'][number]> = {}, name = 'char01'): Profile => ({
  id: 'prf_1', name, cls: 'character', current: 'v1', schema_version: 2, revision: 3, voice_id: null, created_at: '', updated_at: '',
  versions: [{ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null, anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, poses: {}, from_idea: null, height_m: null, place_set: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null, appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v }],
})
const html = (el: React.ReactElement) => { const host = document.createElement('div'); host.innerHTML = renderToStaticMarkup(el); return host }

describe('D93 (A1) the casting offer', () => {
  it('no hero and no references: "Give <name> a look"', () => {
    const o = castOffer(prof())!
    expect(o.kind).toBe('give')
    expect(o.label).toBe('Give char01 a look')
    expect(o.disabled).toBeNull()
    const b = html(<CastButton offer={o} onCast={() => undefined} />).querySelector('button')!
    expect(b.textContent).toContain('Give char01 a look')
    expect(b.getAttribute('data-cast')).toBe('give')
    expect(b.className).toContain('primary')
  })
  it('a hero, or references through the mention: "More looks for <name>"', () => {
    expect(castOffer(prof({ hero_asset_id: 'ast_h' }))!.label).toBe('More looks for char01')
    expect(castOffer(prof(), 2)!.kind).toBe('more')
  })
  it('a final version refuses with the reason (the button is disabled and says why)', () => {
    const o = castOffer(prof({ state: 'final', hero_asset_id: 'ast_h' }))!
    expect(o.disabled).toMatch(/final — make a new version/)
    const b = html(<CastButton offer={o} onCast={() => undefined} />).querySelector('button')!
    expect(b.hasAttribute('disabled')).toBe(true)
    expect(b.title).toBe(o.disabled)
  })
  it('no profile, no offer; the origin routes into the candidates page and back to Cast', () => {
    expect(castOffer(undefined)).toBeNull()
    expect(castOrigin('prf_1', 'v1', 'grp_c')).toEqual({ suite: 'generate', surface: 'cast', ref: 'prf_1', payload: { version: 'v1', group_id: 'grp_c', profile_id: 'prf_1' } })
  })
})

describe('D93 (A9) the description', () => {
  it('only the name (any case, a trailing full stop) warns; words for the look do not', () => {
    expect(nameOnly('char01', 'char01')).toBe(true)
    expect(nameOnly(' Char01. ', 'char01')).toBe(true)
    expect(nameOnly('char01, a red-haired diver', 'char01')).toBe(false)
    expect(needsLook('', 'char01')).toBe(true)
    expect(needsLook('a red-haired diver', 'char01')).toBe(false)
  })
  it('the warning line: the ask first, then the name-only warning, else nothing', () => {
    expect(html(<SubjectWarn name="char01" nameOnly ask={false} refs={0} />).textContent).toBe('the model only sees the name — describe the look in World')   // D93 (B4): the sheet is Cast's
    expect(html(<SubjectWarn name="char01" nameOnly ask={false} refs={3} />).textContent).toContain('(and its reference images)')
    expect(html(<SubjectWarn name="char01" nameOnly ask refs={0} />).textContent).toContain("describe char01's look in World first")
    expect(html(<SubjectWarn name="char01" nameOnly={false} ask={false} refs={0} />).textContent).toBe('')
  })
})

describe('D93 (A3) the slots', () => {
  const bs: Binding[] = [{ subject: 0, role: 'subject', name: 'Mara', profile_id: 'prf_m', version: 'v1', refs: [1, 2, 3], span: 'reference images 1–3', skipped: 0 },
    { subject: 1, role: 'subject', name: 'Ines', profile_id: 'prf_i', version: 'v1', refs: [4], span: 'reference image 4', skipped: 2 }]
  it('the card shows its range, and what did not fit', () => {
    expect(slotsOf(bs, 0)).toEqual({ label: 'refs 1–3', left: 0, refs: [1, 2, 3] })
    expect(slotsOf(bs, 1)!.label).toBe('ref 4')
    expect(html(<SubjectSlots slots={slotsOf(bs, 1)} />).textContent).toBe('ref 4 · 2 left out')
    expect(slotsOf([{ ...bs[0], refs: [] }], 0)!.label).toBe('no refs')
    expect(slotsOf(bs, -1)).toBeNull()
  })
  it('the Preview says each binding and the cut', () => {
    expect(bindingLines(bs, 4)).toEqual(['subject 1 · Mara → reference images 1–3', 'subject 2 · Ines → reference image 4 · 2 of its set left out (the model takes 4)'])
  })
  it('the index the server reads skips the cards the prompt drops', () => {
    const subs = [{ description: '' }, { description: 'Mara' }, { description: '  ', action: '' }, { description: 'Ines' }]
    expect(sentIndex(subs, 1)).toBe(0)
    expect(sentIndex(subs, 3)).toBe(1)
    expect(sentIndex(subs, 0)).toBe(-1)
    expect(sentIndex([{ description: '' }, { description: '', profile_id: 'prf_m' }], 1)).toBe(0)   // D93 (B4): a linked card without words is sent (its sheet is the server's)
  })
})
