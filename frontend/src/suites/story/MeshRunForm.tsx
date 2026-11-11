// RS2 (D197 G2; Q13, Q16): the image → 3D run form — a character's shell, a prop's model. The model tile (Pixal3D is the one model today),
// the resolution, the face count and the seed, as the version keeps them (`ProfileVersion.mesh`); a change is the version's draft
// (`meshDraft`) until the run sends and keeps it, so the commands that make a shell from anywhere (the skeleton screen, a ghost figure)
// run what this form shows. The defaults are E14's measured ones, said behind each ?.
import type { ReactNode } from 'react'
import type { Profile } from '../../api/types'
import { RunForm, type RunField } from '../../frame/RunForm'
import { useSession } from '../../store/session'
import { MESH_DEFAULTS, meshKey, useStory, type MeshSettings } from './storyStore'

type Version = Profile['versions'][number]

const FIELDS = (resolutions: number[], min: number, max: number): RunField[] => [
  { key: 'resolution', label: 'resolution', kind: 'choice', options: resolutions.map((r) => ({ value: r, label: String(r), hint: r === 1024 ? 'the measured default' : "the template's own: finer, slower" })),
    help: 'The size the shape is refined at. 1024 is the measured default (E14: 243 s warm, 361 s cold, no out-of-memory on 16 GB); 1536 is the template\'s own, finer and slower.' },
  { key: 'faces', label: 'faces', kind: 'number', min, max, step: 1000,
    help: 'How many triangles the mesh is reduced to. 50 000 is the measured default (E14: 46–50 k, silhouettes 0.90–0.99 of the picture\'s); more keeps finer edges and weighs more in a scene.' },
  { key: 'seed', label: 'seed', kind: 'number', min: 0, max: 2147483647, step: 1,
    help: 'The seed of the shape and texture stages. 0 is what every shell so far was made with; another seed gives another reading of the back the picture does not show.' },
]

/** The settings the next run of this version takes: its draft, else what it keeps, else the defaults. */
function useMeshSettings(p: Pick<Profile, 'id'>, v: Version): MeshSettings {
  const draft = useStory((s) => s.meshDraft[meshKey(p.id, v.id)])
  return draft ?? { ...MESH_DEFAULTS, ...(v.mesh ?? {}) }
}

export function MeshRunForm({ p, v, children, testId }: { p: Profile; v: Version; children?: ReactNode; testId?: string }) {
  const caps = useSession((s) => s.capabilities?.mesh)
  const m = useMeshSettings(p, v)
  if (!caps?.model_id) return <div className="run-form" data-testid={testId}><span className="hint">{caps?.why ?? 'No image → 3D model in this build.'}</span><div className="run-foot">{children}</div></div>
  const models = ((caps.models ?? []) as { id: string; label: string; short?: string; hint?: string | null; seconds?: number | null }[])
    .map((x) => ({ id: x.id, label: x.short ?? x.label, hint: x.hint, health: caps.health, seconds: x.seconds, measured: true }))
  const set = (key: string, value: number | string) => useStory.getState().setMeshDraft(p.id, v.id, { ...m, [key]: value } as MeshSettings)
  const mins = caps.seconds ? Math.round(caps.seconds / 60) : null            // E14's, measured at 1024
  const cost = !mins ? undefined : m.resolution === 1024 ? `≈ ${mins} min warm${caps.cold_seconds ? ` · ${Math.round(caps.cold_seconds / 60)} min cold` : ''}` : `longer than ≈ ${mins} min — ${m.resolution} is not measured yet`
  return (
    <RunForm testId={testId} models={models} model={m.model_id ?? caps.model_id} onModel={(id) => set('model_id', id)}
      fields={FIELDS(caps.resolutions?.length ? caps.resolutions : [1024, 1536], caps.faces_min ?? 2000, caps.faces_max ?? 700000)}
      values={{ resolution: m.resolution, faces: m.faces, seed: m.seed }} onChange={set} cost={cost}>{children}</RunForm>
  )
}
