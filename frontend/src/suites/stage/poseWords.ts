// D93 (C8): the Stage pose presets (builders.ts POSES, E10's ten) in the words a prompt's subject "pose" field takes — so a figure bound to
// a character can fill that character's Generate subject (Make frame ▸). Pure and three-free: the Story chunk reads it without the engine.
export const POSE_WORDS: Record<string, string> = {
  stand: 'standing', point: 'pointing', arms_crossed: 'standing with arms crossed', walk: 'walking', run: 'running', reach: 'reaching up with both arms',
  sit: 'sitting', crouch: 'crouching', wave: 'waving', look_left: 'looking to the left',
}

/** A figure's pose as words: its preset's (a pose edited joint by joint after the preset still reads as the preset), or '' for none. */
export const poseWords = (pose: { preset?: string | null } | null | undefined): string => (pose?.preset ? POSE_WORDS[pose.preset] ?? pose.preset.replace(/_/g, ' ') : '')
