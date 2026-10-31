// W38: the extent a prop's height (`height_m`, World's prop height) sets on its 3D model — its height, or for a flat thing (a letter, a rug, a
// map: its height under FLAT of its longest side) its longest side; the letter's 0.2 m went to its thickness and it stood as a 1 m block.

export const FLAT = 0.15

/** The model's extent its size in metres applies to, from its bounding box's sides (x, y up, z). */
export function sizedExtent(x: number, y: number, z: number): number {
  const long = Math.max(x, z)
  return y < FLAT * long ? long : y
}
