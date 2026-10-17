// D92: the no-monogram rule — a PresetIcons tile shows a drawing (an svg glyph) or a picture, never text; a busy tile keeps its glyph and
// shows the busy mark; the words are the tooltip and the accessible name, and under the tile only when the section asks.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { fieldGlyph, glyphFor } from './presetGlyphs'
import { PresetIcons, type PresetIcon } from './PresetIcons'

const render = (items: PresetIcon[], showText = false) => {
  const host = document.createElement('div')
  host.innerHTML = renderToStaticMarkup(<PresetIcons items={items} onPick={() => undefined} showText={showText} />)
  return host
}
const tiles = (host: HTMLElement) => [...host.querySelectorAll<HTMLElement>('.preset-icon .tile')]
/** The tile's own text — what is left outside its svg / img (a glyph's numbers inside the svg drawing are part of the picture). */
const bareText = (t: HTMLElement) => { const c = t.cloneNode(true) as HTMLElement; c.querySelectorAll('svg, img').forEach((x) => x.remove()); return c.textContent?.trim() ?? '' }

describe('D92 PresetIcons never shows letters', () => {
  const items: PresetIcon[] = [
    { id: 'a', label: 'golden hour rim light', icon: fieldGlyph('lighting') },                       // no picture yet: the field's glyph
    { id: 'b', label: 'violet dusk', icon: fieldGlyph('lighting'), busy: true },                      // its picture is being made
    { id: 'c', label: 'eerie', icon: fieldGlyph('mood'), img: '/preset-icons/abc/file' },              // a picture
    { id: 'd', label: 'close-up', icon: glyphFor('camera.distance', 'close-up') },                    // a drawing of its own
    { id: 'e', label: 'Ink wash', icon: fieldGlyph('palette'), badge: '★' },
  ]
  it('every tile holds an svg or an img and no text of its own', () => {
    const host = render(items)
    const ts = tiles(host)
    expect(ts).toHaveLength(items.length)
    for (const t of ts) {
      expect(t.querySelector('svg, img'), t.outerHTML).not.toBeNull()
      expect(bareText(t).replace('★', ''), t.outerHTML).toBe('')
    }
    expect(host.querySelector('.cap')).toBeNull()                                                     // the words are not under the tiles by default
  })
  it('the words are the tooltip and the accessible name; busy tiles keep the glyph and say so', () => {
    const host = render(items)
    const b = host.querySelector<HTMLButtonElement>('[data-id="b"]')!
    expect(b.getAttribute('aria-label')).toBe('violet dusk')
    expect(b.title).toContain('being made')
    expect(b.querySelector('.busy-mark')).not.toBeNull()
    expect(b.querySelector('svg')).not.toBeNull()
    expect(host.querySelector('[data-id="c"] img')?.getAttribute('src')).toBe('/preset-icons/abc/file')
    expect(host.querySelector('[data-id="c"] svg')).toBeNull()                                        // a picture covers the glyph
  })
  it('shows the words under the tiles only when the section asks', () => {
    expect([...render(items, true).querySelectorAll('.cap')].map((c) => c.textContent)).toEqual(items.map((i) => i.label))
  })
})
