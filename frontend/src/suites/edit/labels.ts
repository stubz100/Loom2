// One spelling per name across the menus, the layer rows, the Properties title and the blend list (review U6, 2026-10-10):
// adjustment / filter types in sentence case with the British "colour" the rest of the UI uses, blend modes as Photoshop names them.

const TYPE_LABEL: Record<string, string> = {
  levels: 'Levels', curves: 'Curves', hue_saturation: 'Hue/Saturation', color_balance: 'Colour balance', brightness_contrast: 'Brightness/Contrast',
  exposure: 'Exposure', black_white: 'Black & white', invert: 'Invert', gaussian_blur: 'Gaussian blur', sharpen: 'Sharpen', color_to_alpha: 'Colour to alpha',
}

/** The display name of an adjustment or filter type (`hue_saturation` → "Hue/Saturation"). */
export function typeLabel(type: string | undefined): string {
  if (!type) return ''
  const known = TYPE_LABEL[type]
  if (known) return known
  const s = type.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** The display name of a blend mode (`color-burn` → "Color Burn", `pass-through` → "Pass Through"), as in Photoshop's list. */
export function blendLabel(mode: string): string {
  return mode.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}
