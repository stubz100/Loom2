// D92 (wave UI7): World's Library and Saved panels — every Generate template has its entry here. The library is grouped by field (Look ·
// Camera · Prompt · Subject), each entry a picture tile (the same PresetIcons as Generate: its own drawing, its generated picture, or its
// field's glyph while the picture is made) with its name; a click selects it and the World Inspector edits the name and the words (the only
// place they are written), shows the picture large, makes a new one, moves or removes it (Undo). The saved panels show their latest
// result (else the panel glyph): Apply opens Generate with them, Rename…, Delete (confirmed).
import { useEffect } from 'react'
import { libraryDrag } from './libraryDrag'
import { api } from '../../api/client'
import type { LibraryEntry } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { PresetIcons } from '../../frame/PresetIcons'
import { fieldGlyph } from '../../frame/presetGlyphs'
import { useSession } from '../../store/session'
import { FIELD_LABEL, LIBRARY_GROUPS, type FieldKey } from '../generate/fieldPresets'
import { useGenerate } from '../generate/generateStore'
import { needsPicture, swatchJob, useSwatches } from '../generate/swatches'
import { entriesOf, entryTile, useLibrary } from './libraryStore'
import { rowMenu, runOnItem } from './storyCommands'
import { sy, useStory } from './storyStore'

const menu = (kind: 'entry' | 'panel', id: string): MenuItem[] => rowMenu(kind, id).map((m) => (m === 'sep' ? sep : m))
const tileOf = (e: LibraryEntry, url: (f: string, v: string) => string | null, jobs: ReturnType<typeof useSession.getState>['jobs']) => entryTile(e, url, (f, v) => !!swatchJob(jobs, f, v))

/** The library's swatches and the jobs (the busy marks) — loaded once. */
function usePictures() {
  const url = useSwatches((s) => s.url)
  useSwatches((s) => s.items)
  const loaded = useSwatches((s) => s.loaded)
  const jobs = useSession((s) => s.jobs)
  useEffect(() => { if (!loaded) void useSwatches.getState().load() }, [loaded])
  return { url, jobs }
}

/** The click that ends a drag must not select the tile it was released on. */
const swallowAfterDrag = (e: React.MouseEvent) => { if (libraryDrag.justDropped) { e.stopPropagation(); e.preventDefault() } }

export function LibraryGrid() {
  const lib = useLibrary((l) => l.library)
  const selected = useStory((s) => s.selected)
  const { url, jobs } = usePictures()
  markUsed('story.world.addEntry')
  if (!lib) return <div className="empty">Loading the library…</div>
  const sel = selected?.kind === 'entry' ? selected.id : null
  return (
    <div className="lib-groups">
      {LIBRARY_GROUPS.map((g) => (
        <div key={g.id} className="lib-group">
          <h4>{g.label}</h4>
          {g.fields.filter((f) => f !== 'subject.description' || entriesOf(lib, f).length).map((f: FieldKey) => {
            const items = entriesOf(lib, f).map((e) => tileOf(e, url, jobs))
            return (
              <div key={f} className="lib-field" data-field={f} onPointerDown={libraryDrag} onClickCapture={swallowAfterDrag}>
                <span className="lib-label">{FIELD_LABEL[f]}<span className="n"> · {items.length}</span></span>
                <PresetIcons label={`${FIELD_LABEL[f]} entries`} size={56} showText items={items} selected={sel}
                  onPick={(id) => sy().select({ kind: 'entry', id })} onContext={(id, e) => showMenu(e, menu('entry', id))} />
                <button type="button" className="quiet lib-add" title={`Add ${FIELD_LABEL[f]} words to the library`} aria-label={`add a ${FIELD_LABEL[f]} entry`}
                  onClick={() => runOnItem({ field: f }, 'story.world.addEntry')}>＋ Add</button>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

export function PanelGrid() {
  const presets = useGenerate((g) => g.presets)
  const selected = useStory((s) => s.selected)
  const caps = useSession((s) => s.capabilities)
  useEffect(() => { void useGenerate.getState().loadPresets() }, [])
  markUsed('story.world.applyPanel'); markUsed('story.world.renamePanel')
  if (!presets.length) return <div className="empty">None yet — Generate's bookmark (Saved panels) keeps every field of its panel under a name.</div>
  return (
    <PresetIcons label="saved panels" size={72} showText selected={selected?.kind === 'panel' ? selected.id : null}
      items={presets.map((p) => ({ id: p.name, label: p.name, hint: caps?.models[p.panel.model_id]?.label ?? p.panel.model_id, icon: fieldGlyph('panel'), img: p.thumb_asset_id ? api.thumbUrl(p.thumb_asset_id, 256) : null }))}
      onPick={(id) => sy().select({ kind: 'panel', id })} onContext={(id, e) => showMenu(e, menu('panel', id))} />
  )
}

/** The selected entry's editor (the World Inspector): the picture large, the name and the words — the only place they are written. */
export function EntryEditor({ e }: { e: LibraryEntry }) {
  const { url, jobs } = usePictures()
  const t = tileOf(e, url, jobs)
  const pic = needsPicture(e.field, e.text)
  markUsed('story.world.entryPicture'); markUsed('story.world.entryEarlier'); markUsed('story.world.entryLater')
  return (
    <>
      <h4>Library · {FIELD_LABEL[e.field as FieldKey] ?? e.field}</h4>
      <div className="lib-picture" title={pic ? 'its picture, made on the sample model (Settings › Samples)' : 'a drawn glyph — this field is shown by its geometry (or a negative), not a picture'}>
        {t.img ? <img src={t.img} alt={`the picture of ${e.name}`} draggable={false} /> : <span className="glyph">{t.icon}</span>}
        {t.busy && <i className="busy-mark" title="its picture is being made" />}
      </div>
      <div className="kv">
        <span>name</span><input type="text" value={e.name} aria-label="selected entry name" onChange={(ev) => useLibrary.getState().edit(e.id, { name: ev.target.value })} />
        <span>words</span><textarea rows={3} value={e.text} aria-label="selected entry words" placeholder="the words the field takes" onChange={(ev) => useLibrary.getState().edit(e.id, { text: ev.target.value })} />
        <span>from</span><span>{e.source === 'builtin' ? 'the built-in vocabulary' : e.source === 'snippet' ? 'your app-wide presets (before D92)' : 'added in this project'}</span>
      </div>
      <div className="verbs">{pic && <CommandButton id="story.world.entryPicture" text />}<CommandButton id="story.world.entryEarlier" /><CommandButton id="story.world.entryLater" /><CommandButton id="story.world.remove" text /></div>
    </>
  )
}

/** The selected saved panel (the World Inspector): its picture, model, size and the verbs. */
export function PanelEditor({ name }: { name: string }) {
  const p = useGenerate((g) => g.presets.find((x) => x.name === name))
  const caps = useSession((s) => s.capabilities)
  if (!p) return null
  const pn = p.panel as { model_id?: string; width?: number; height?: number; count?: number; prompt_mode?: string }
  return (
    <>
      <h4>Saved panel · {p.name}</h4>
      <div className="lib-picture wide" title="its most recent result">
        {p.thumb_asset_id ? <img src={api.thumbUrl(p.thumb_asset_id, 512)} alt={`the latest result of ${p.name}`} draggable={false} /> : <span className="glyph">{fieldGlyph('panel')}</span>}
      </div>
      <div className="kv">
        <span>model</span><span>{(pn.model_id && caps?.models[pn.model_id]?.label) ?? pn.model_id ?? '—'}</span>
        <span>size</span><span>{pn.width && pn.height ? `${pn.width}×${pn.height} · ${pn.count ?? 1} each` : '—'}</span>
        <span>prompt</span><span>{pn.prompt_mode ?? '—'}</span>
        <span>saved</span><span>{p.saved_at.slice(0, 16).replace('T', ' ')}</span>
      </div>
      <div className="verbs"><CommandButton id="story.world.applyPanel" text /><CommandButton id="story.world.renamePanel" text /><CommandButton id="story.world.remove" text /></div>
    </>
  )
}
