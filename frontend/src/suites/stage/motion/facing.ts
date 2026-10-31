// M15 (the market walk): a clip's own facing, shown before it is applied — the way the figure will face once the clip plays on it (its yaw
// at the playhead turned by the clip's own root), in words as the shot's camera sees it, and the preview's view from that camera.
import type { MotionFrame } from './retarget'

const DEG = Math.PI / 180

/** The clip's own turn: its root's mean yaw over the frames, degrees (0 = the figure's way). */
export function clipYaw(frames: MotionFrame[]): number {
  let s = 0, c = 0
  for (const f of frames) { const y = (f.joints.root?.[1] ?? 0) * DEG; s += Math.sin(y); c += Math.cos(y) }
  return frames.length ? Math.atan2(s, c) / DEG : 0
}

/** The camera's side of the figure: the angle of (camera − figure) on the floor, degrees in the figure's yaw convention (+Z = 0). */
export const azimuth = (fig: number[], cam: number[]) => Math.atan2(cam[0] - fig[0], cam[2] - fig[2]) / DEG

/** Which way a figure facing `yaw` (degrees, +Z = 0) reads through a camera standing at `az` from it. */
export function facingWords(yaw: number, az: number): 'faces the camera' | 'faces away from the camera' | 'faces left in the shot' | 'faces right in the shot' {
  let d = (yaw - az) % 360
  if (d > 180) d -= 360
  if (d < -180) d += 360
  if (Math.abs(d) <= 45) return 'faces the camera'
  if (Math.abs(d) >= 135) return 'faces away from the camera'
  return d > 0 ? 'faces right in the shot' : 'faces left in the shot'           // the camera's right is (cos az, −sin az): sin(yaw − az) > 0
}
