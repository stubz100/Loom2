// LT2 (18 §3g): the Models suite's Trained table — the project's own LoRAs (files under story/loras/, cached for the engine under
// loras/projects/<project>/) with Show in Cast and Delete.
import { useEffect } from 'react'
import { askConfirm, useSession } from '../../store/session'
import { openGroupPage } from '../story/storyCommands'
import { sy, useStory } from '../story/storyStore'
import { setRailTab } from '../../frame/suiteRegistry'

const gb = (n: number) => `${(n / 2 ** 30).toFixed(n < 2 ** 30 ? 2 : 1)} GB`

export function TrainedTable() {
  // LT2 (18 §3g): the project's trained LoRAs — files under story/loras/, cached for the engine under loras/projects/<project>/
  const loras = useStory((s) => s.loras)
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) void sy().loadLoras() }, [project?.open]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return null
  return (
    <div className="trained" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 6px' }}>Trained (this project)</h3>
      {loras.length === 0 ? <span className="hint">none yet — Story · Cast trains one from a version's reference set, an album from its right-click</span> : (
        <table className="grid">
          <thead><tr><th>LoRA</th><th>Base</th><th>Steps</th><th>Size</th><th>Trigger</th><th></th></tr></thead>
          <tbody>
            {loras.map((l) => (
              <tr key={l.id}>
                <td><div>{l.name}</div><div className="mono" style={{ color: 'var(--fg3)', fontSize: 11 }}>{l.id}</div></td>
                <td>{l.base}</td><td>{l.steps}</td><td>{gb(l.size)}</td><td className="mono">{l.trigger}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {l.profile_id
                    ? <button onClick={() => { sy().selectProfile(l.profile_id!, l.version); setRailTab('story', 'cast'); useSession.getState().setSuite('story') }} title="Open the version in Story · Cast">Show in Cast</button>
                    : <button disabled={!l.dataset.group_id} onClick={() => openGroupPage(String(l.dataset.group_id))} title="Open the album it was trained on (D122: an album's own LoRA)">Show the album</button>}{' '}
                  <button onClick={() => void (async () => { if (await askConfirm({ title: 'Delete the LoRA?', okLabel: 'Delete', text: `${l.name}: the file, its record and the engine's cached copy go${l.profile_id ? "; the version keeps its trigger" : ""}.` })) await sy().deleteLora(l.id) })()} title="Delete the file, its record and the engine's copy">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
