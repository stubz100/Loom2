// U3c (D157, proto01_UI2 03 §4): Edit's Save in World — a new creation written into the entity version's bin with its role.
import { useEditor } from '../../suites/edit/editorStore'
import { useStory } from '../../suites/story/storyStore'
import { useWorld } from './worldStore'

/** Save the open document and put the new creation into the version's bin with a role (the hero, a reference, or a candidate). */
export async function saveIntoBin(role: 'hero' | 'reference' | 'candidate'): Promise<string | null> {
  const st = useStory.getState(), p = st.profile(), vid = st.versionId
  if (!p || !vid) return null
  const id = await useEditor.getState().saveVersion()
  if (!id) return null
  await st.addToProfile(p.id, [id], role, vid)
  useWorld.getState().select(id)
  return id
}
