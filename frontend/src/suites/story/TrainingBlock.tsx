// LT2 (18 §3c / §3d / §5): the Cast Inspector's training block — the readiness line (advisory, D10), the trigger and the LoRA the version
// holds (with the measured figures), the options the next job runs with (the base and E16's figures from /capabilities.train, steps,
// resolution, rank, name, the setting word, staged or not), the verbs as commands (D32), and the newest training job's state with its
// Release / Resume / Cancel.
import { CommandButton } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import type { Profile, ProfileVersion } from '../../api/types'
import { readiness } from './coverage'
import { latestTrainJob, sy, useStory } from './storyStore'

export function TrainingBlock({ p, v }: { p: Profile; v: ProfileVersion }) {
  const caps = useSession((s) => s.capabilities?.train)
  const storyCaps = useSession((s) => s.capabilities?.story)
  const jobs = useSession((s) => s.jobs)
  const opts = useStory((s) => s.trainOpts)
  const loras = useStory((s) => s.loras)
  const refPage = useStory((s) => s.refPage)
  const refs = Object.values(refPage?.assets ?? {})
  const ready = readiness(refs, storyCaps?.coverage.shots ?? [], storyCaps?.coverage.angles ?? [], !!v.hero_asset_id)
  const job = latestTrainJob(jobs, p.id, v.id)
  const rec = loras.find((l) => l.id === v.lora)
  const bases = caps?.bases ?? []
  const baseId = opts.model_id && bases.some((b) => b.model_id === opts.model_id) ? opts.model_id : bases.find((b) => b.health !== 'missing')?.model_id ?? bases[0]?.model_id ?? ''
  const base = bases.find((b) => b.model_id === baseId)
  const secs = base?.s_per_it ? Math.round(opts.steps * base.s_per_it) : null
  const set = sy().setTrainOpts
  return (
    <div className="training" aria-label="training">
      <h4>Training</h4>
      <div className="kv">
        <span>readiness</span><span className="readiness" title={ready.lines.join('\n')}>{ready.score} · {ready.summary}</span>
        <span>trigger</span><span className="mono">{v.trigger ?? '— (made at the first training)'}</span>
        <span>LoRA</span>
        <span>{rec ? `${rec.name} · ${rec.steps} steps · ${Math.max(1, Math.round(rec.size / 2 ** 20))} MB` : v.lora ? v.lora : '—'}</span>
        {rec && <><span>measured</span><span>{String(rec.measured.s_per_it ?? '?')} s/it · peak {String(rec.measured.peak_vram_gb ?? '?')} GB · {Math.round(Number(rec.measured.wall_s ?? 0) / 60)} min{rec.measured.resumed_from ? ` · resumed from step ${String(rec.measured.resumed_from)}` : ''}</span></>}
      </div>
      {!caps?.available ? <span className="hint">{caps?.why ?? (bases.length ? 'no trainable base has its weights on disk' : 'the trainer is not available in this build')}</span> : (
        <div className="kv">
          <span>base</span>
          <select aria-label="train base" value={baseId} onChange={(e) => set({ model_id: e.target.value })}>
            {bases.map((b) => <option key={b.model_id} value={b.model_id} disabled={b.health === 'missing'}>{b.label}{b.offload ? ' · offloaded' : ''} · {b.vram_gb} GB{b.s_per_it ? ` · ${b.s_per_it} s/it` : ''}{b.health === 'missing' ? ' · missing' : ''}</option>)}
          </select>
          <span>steps</span><input type="number" aria-label="train steps" min={caps.steps.min} max={caps.steps.max} step={50} value={opts.steps} onChange={(e) => set({ steps: Math.max(caps.steps.min, Math.min(caps.steps.max, Number(e.target.value) || caps.steps.default)) })} />
          <span>resolution</span>
          <select aria-label="train resolution" value={opts.resolution} onChange={(e) => set({ resolution: Number(e.target.value) })}>{caps.resolutions.map((r) => <option key={r} value={r}>{r}²</option>)}</select>
          <span>rank</span>
          <select aria-label="train rank" value={opts.rank} onChange={(e) => set({ rank: Number(e.target.value) })}>{caps.ranks.map((r) => <option key={r} value={r}>{r}</option>)}</select>
          <span>name</span><input type="text" aria-label="lora name" value={opts.name} placeholder={`${p.name} ${v.id}`} onChange={(e) => set({ name: e.target.value })} />
          <span>setting</span><input type="text" aria-label="train setting" value={opts.setting} placeholder="e.g. plain studio background — captioned, so it stays out of the LoRA" onChange={(e) => set({ setting: e.target.value })} />
          <span>stage</span><label><input type="checkbox" aria-label="train staged" checked={opts.stage} onChange={(e) => set({ stage: e.target.checked })} /> stage it — release when the rig is free</label>
          <span>estimate</span><span>{secs ? `≈ ${Math.max(1, Math.round(secs / 60))} min of steps + the loads` : '—'}{refs.length < (caps.min_refs ?? 4) ? ` · ${refs.length} of ${caps.min_refs} references` : ''}</span>
        </div>
      )}
      <div className="verbs"><CommandButton id="story.cast.train" text />{rec && <CommandButton id="story.cast.useLora" text />}{rec && <CommandButton id="story.cast.deleteLora" text />}</div>
      {job && (
        <div className={`train-job ${job.status}`} aria-label="train job">
          <span className={`badge ${job.status}`}>{job.status}</span>
          <span className="mono">{job.status === 'failed' ? job.error : job.progress_text || (job.status === 'staged' ? 'staged — release it when the rig is free' : '')}</span>
          <div className="verbs"><CommandButton id="story.cast.releaseTrain" text /><CommandButton id="story.cast.resumeTrain" text /><CommandButton id="story.cast.cancelTrain" text /></div>
        </div>
      )}
    </div>
  )
}
