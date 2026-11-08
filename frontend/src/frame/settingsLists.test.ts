// Review K72: Settings' list fields keep the text as typed and split it on blur or Save — a trailing separator or a space inside a path
// survives typing.
import { describe, expect, it } from 'vitest'
import type { Settings } from '../api/types'
import { LISTS, listsInto } from './settingsLists'

const S = { mounted_model_trees: ['D:/comfy'], engine: { flags: ['--a'] }, thumbnail_sizes: [256, 512], vsthost: { folders: [] } } as unknown as Settings

describe('the settings list fields (K72)', () => {
  it('shows each list as one line', () => {
    expect([LISTS.trees.join(S), LISTS.flags.join(S), LISTS.thumbs.join(S), LISTS.vst.join(S)]).toEqual(['D:/comfy', '--a', '256,512', ''])
  })
  it('splits what was typed — a second tree, a flag, a Program Files path — and leaves an untyped field alone', () => {
    const typed = listsInto(S, { trees: 'D:/comfy; E:/more models;', flags: '--a --lowvram ', vst: 'C:/Program Files/VST3 extra' })
    expect(typed.mounted_model_trees).toEqual(['D:/comfy', 'E:/more models'])
    expect(typed.engine.flags).toEqual(['--a', '--lowvram'])
    expect(typed.vsthost.folders).toEqual(['C:/Program Files/VST3 extra'])
    expect(typed.thumbnail_sizes).toEqual([256, 512])
    expect(listsInto(S, { thumbs: '256, 384,, x' }).thumbnail_sizes).toEqual([256, 384])
  })
})
