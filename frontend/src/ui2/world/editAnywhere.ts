// B2a (D159, proto01_UI2 11 §7): a picture opened in World's Edit from anywhere (the Bin's Open in Edit, Select subject…, Upscale…, a deep
// link). A picture in an entity's version opens there, as World's own Edit does (Save puts it into that bin with a role). Any other — a
// sketch, a look's sample, a shot's take, an import — opens as a free edit over the Sketches: Save beside it puts the result into the
// picture's own home.
import { http, unwrap } from '../../api/client'
import { navigate } from '../../frame/router'
import type { OpenWith } from '../../frame/openWith'
import { useWorld } from './worldStore'

export async function editAnywhere(assetId: string, o: OpenWith = { suite: 'edit' }): Promise<void> {
  const t = await unwrap(http.GET('/bin/things/{aid}', { params: { path: { aid: assetId } } })).catch(() => null)
  const [top, cls, pid, vid] = (t?.path ?? '').split('/')
  navigate({ suite: 'generate' })
  const w = useWorld.getState()
  if (top === 'world' && pid && vid && cls !== 'look' && cls !== 'sketches') {
    const s = (await import('../../suites/story/storyStore')).useStory
    if (!s.getState().profiles.some((p) => p.id === pid)) await s.getState().loadProfiles()
    w.pick(pid, vid)
    useWorld.getState().select(assetId)
    useWorld.getState().setMode('edit')
  } else {
    w.setRail('sketches')
    useWorld.setState({ mode: 'edit', free: { id: assetId, home: t?.home_id ?? null, name: t?.path ?? 'imports' } })
  }
  const { openWith } = await import('../../frame/openWith')
  await openWith(assetId, { ...o, suite: 'edit' })
}

/** Save the free edit beside the picture it opened: the editor's new version, moved into that picture's home. */
export async function saveBeside(): Promise<string | null> {
  const f = useWorld.getState().free
  const { useEditor } = await import('../../suites/edit/editorStore')
  const id = await useEditor.getState().saveVersion()
  if (!id || !f?.home) return id
  await unwrap(http.POST('/bin/move', { body: { ids: [id], to: f.home } })).catch(() => null)
  return id
}
