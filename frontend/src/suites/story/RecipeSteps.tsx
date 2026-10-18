// RC0 (D96, proto01_animate/05 §4): a shot version's recipe as a list — the template's steps in order, each fresh, stale (with why),
// missing or planned (the wave that brings it), with the last run's cost. The server computes the state (GET /story/shots/{sid}/recipe);
// a story.changed for the shot refetches it (recipeTick), ↻ refetches after edits elsewhere (a stage, a Cast sheet). RC1 draws it as a graph.
import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { http, unwrap, type ApiError } from '../../api/client'
import type { components } from '../../api/schema'
import { useSession } from '../../store/session'
import { useMakeFor, type Maker } from '../../store/origin'
import { useRecipeTick } from './recipeTick'
import { CommandButton } from '../../frame/CommandButton'
import { noteStale, secs } from './runStale'

type Recipe = components['schemas']['RecipeOut']
type Template = components['schemas']['Template']

let templates: Template[] | null = null

export function RecipeSteps({ shotId, version, editable = true, run }: { shotId: string; version: string; editable?: boolean; run?: string }) {
  const open = useSession((s) => !!s.project?.open)
  const path = useSession((s) => s.project?.path)
  const tick = useRecipeTick((s) => s.tick[shotId] ?? 0)
  const [r, setR] = useState<Recipe | null>(null)
  const [tpls, setTpls] = useState<Template[] | null>(templates)
  const [again, setAgain] = useState(0)
  useEffect(() => {
    if (!open) return
    let live = true
    void unwrap(http.GET('/story/shots/{sid}/recipe', { params: { path: { sid: shotId }, query: { version } } })).then((x) => { noteStale(shotId, version, x.stale); if (live) setR(x) }).catch(() => { if (live) setR(null) })
    if (!templates) void unwrap(http.GET('/story/recipe-templates')).then((x) => { templates = x; if (live) setTpls(x) }).catch(() => undefined)
    return () => { live = false }
  }, [open, path, shotId, version, tick, again])
  if (!r) return null
  const setTemplate = (t: string) => void unwrap(http.PUT('/story/shots/{sid}/versions/{vid}/template', { params: { path: { sid: shotId, vid: version } }, body: { template: t } }))
    .then(() => setAgain((n) => n + 1)).catch((e) => useSession.getState().toast(`The template was not changed: ${(e as ApiError).detail ?? e}`, 'error'))
  return (
    <div className="recipe" data-testid="recipe">
      <div className="recipe-head">
        <b>Recipe</b>
        {editable && tpls ? (
          <select aria-label="recipe template" value={r.template} onChange={(e) => setTemplate(e.target.value)} title={tpls.find((t) => t.id === r.template)?.hint}>
            {tpls.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        ) : <span>{r.label}</span>}
        <span className={`meta${r.stale ? ' warn' : ''}`}>{r.stale ? `${r.stale} stale${r.stale_seconds ? ` · ≈ ${secs(r.stale_seconds)} to run again` : ''}` : 'nothing stale'}</span>
        <button type="button" className="quiet" title="Check again (after an edit elsewhere: the stage, a Cast sheet, the world style)" aria-label="check the recipe again" onClick={() => setAgain((n) => n + 1)}><RefreshCw size={13} /></button>
      </div>
      <ol className="recipe-steps">
        {r.steps.map((s) => (
          <li key={s.id} className={`rs ${s.state}`} title={s.reasons.length ? s.reasons.join(' · ') : undefined}>
            <span className="dot" aria-hidden />
            <span className="rs-label">{s.label}{s.experimental ? ' (experimental)' : ''}</span>
            <span className="meta">{s.state === 'planned' ? `planned · ${s.wave}` : s.state}{s.seconds != null ? ` · ${secs(s.seconds)}` : ''}{s.runs > 1 ? ` · ${s.runs} runs` : ''}</span>
            {s.reasons.length > 0 && <small className="rs-why">{s.reasons.join(' · ')}</small>}
          </li>
        ))}
      </ol>
      {run && editable && r.stale > 0 && <div className="verbs"><CommandButton id={run} text /></div>}
    </div>
  )
}

/** The recipe of the shot a maker was opened for (the For chip's shot), under the chip. */
export function ForRecipe({ maker }: { maker: Maker }) {
  const f = useMakeFor((s) => s[maker])
  if (!f || f.kind !== 'shot') return null
  return <RecipeSteps shotId={f.shot_id} version={f.version} run="anim.for.runStale" />
}
