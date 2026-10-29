// B2a (D159, proto01_UI2 11 §7): World's Sheet — the entity version's whole card, as Story's Cast page had it, in the left column beside its
// bin: the sheet's fields (the look, the outfit, bound colours, marks, the label), a character's body (height, build, attachments, the
// figure's sliders, ♀ / ♂, hands at rest) and its skeleton bench, the animation reference (front, back) with its test animation, a prop's
// 3D model turning with its height, a place's set builder, and the Line-up of the class at their sizes in Clay.
import { lazy, Suspense } from 'react'
import { CommandButton } from '../../frame/CommandButton'
import { AnimRef, PropModel } from '../../suites/story/CastParts'
import { CastSheet } from '../../suites/story/CastSheet'
import { useStory } from '../../suites/story/storyStore'
import '../../suites/story/story.css'

const PlaceSetSection = lazy(() => import('../../suites/story/CastSet').then((m) => ({ default: m.PlaceSetSection })))   // CW6: three.js only for a place

export function WorldSheet() {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  if (!p) return <div className="w-empty">Pick or make one in the header.</div>
  const v = p.versions.find((x) => x.id === (vid ?? p.current)) ?? p.versions[0]
  return (
    <div className="w-sheet cast-page" data-testid="world-sheet">
      <CastSheet p={p} v={v} />
      {p.cls === 'character' && <div className="w-verbs"><CommandButton id="cast.shell.make" text /></div>}{/* the sheet holds the body (Fit, Skeleton…, Bench in its foot) */}
      {(p.cls === 'character' || p.cls === 'prop') && <AnimRef p={p} v={v} />}
      {p.cls === 'prop' && <PropModel p={p} v={v} />}
      {p.cls === 'place' && <Suspense fallback={<section className="place-set" />}><PlaceSetSection p={p} v={v} /></Suspense>}
      {p.cls !== 'place' && <div className="w-verbs"><CommandButton id="world.lineup" text /></div>}
    </div>
  )
}
