// C3 (D181, propo02 04 §4.3; 05 Q4): a scene has a length — 5 s by default (the project's, PUT /project/defaults), 20 s the cap — and its
// timeline is 0 … length − 1: the stage's range and a shot's range lie inside; the length never grows by itself (F37). A scene from
// before C3 (length 0) reads as what it already spans (stages.scene_length, the same rule).
export const SCENE_SECONDS_DEFAULT = 5
export const SCENE_SECONDS_MAX = 20

export interface SceneSpan { length?: number; range: { start: number; end: number }; size: { fps?: number } }

export const fpsOf = (d: Pick<SceneSpan, 'size'>): number => Math.max(1, d.size?.fps ?? 24)

/** The scene's length in frames. */
export function sceneLength(d: SceneSpan): number {
  return d.length || Math.max((d.range?.end ?? 0) + 1, SCENE_SECONDS_DEFAULT * fpsOf(d))
}

/** The scene's length in seconds, one decimal. */
export const sceneSeconds = (d: SceneSpan): string => (sceneLength(d) / fpsOf(d)).toFixed(1)

/** A length asked in seconds as frames: never below what the range already covers, never past the cap. */
export function clampLength(d: SceneSpan, seconds: number): number {
  const fps = fpsOf(d)
  return Math.min(SCENE_SECONDS_MAX * fps, Math.max((d.range?.end ?? 0) + 1, Math.round(seconds * fps)))
}
