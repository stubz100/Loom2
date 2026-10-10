// Exact W3C / Photoshop blend modes for the PixiJS compositor (10 §3, acceptance 10 §14 item 1).
//
// PixiJS's built-in advanced blend modes use looser formulas (e.g. the Pegtop soft-light), ignore the backdrop
// alpha and batch consecutive layers that share a mode into one pass. These filters mirror
// orchestrator/loom2/compose.py: straight-alpha B(cb, cs) from the W3C compositing spec, then
//   co = cs·αs·(1−αb) + cb·αb·(1−αs) + B·αs·αb ;  αo = αs + αb·(1−αs)
// The filter emits the source-side term (cs·(1−αb) + B·αb)·αs with alpha αs; Pixi's source-over draw of the
// filter output onto the backdrop supplies the cb·αb·(1−αs) term, so the result is exact over any backdrop.
// An alternate "-b" name exists for every mode so two adjacent layers with the same mode never share a batch.
// D39: Soft Light, Vivid Light, Hard Mix and the Burn / Dodge EDGE rule follow Photoshop (ported from PhotoCraft
// crates/color/src/blend.rs and crates/compose/src/psblend.rs @ b37bff98; Copyright (c) 2026 ArtCraft Team and the PhotoCraft
// contributors, MIT OR Apache-2.0). Clipping is no longer a shader variant: EditorCanvas renders a clip run as passes
// (base opaque + clipped layers, then masked by the base's alpha), and "w3c-opaque" draws the base for that.
import { BlendModeFilter, ExtensionType, extensions } from 'pixi.js'

export const MODES = ['normal', 'dissolve', 'darken', 'multiply', 'color-burn', 'linear-burn', 'lighten', 'screen', 'color-dodge', 'linear-dodge', 'overlay', 'soft-light',
  'hard-light', 'vivid-light', 'linear-light', 'pin-light', 'hard-mix', 'difference', 'exclusion', 'subtract', 'divide', 'hue', 'saturation', 'color', 'luminosity'] as const
export type Mode = typeof MODES[number]

const GL_FUNCS = /* glsl */ `
float w3_lum(vec3 c) { return 0.3 * c.r + 0.59 * c.g + 0.11 * c.b; }
vec3 w3_clipColor(vec3 c) {
  float l = w3_lum(c);
  float n = min(c.r, min(c.g, c.b));
  float x = max(c.r, max(c.g, c.b));
  if (n < 0.0) c = l + (c - l) * l / max(l - n, 1e-6);
  if (x > 1.0) c = l + (c - l) * (1.0 - l) / max(x - l, 1e-6);
  return c;
}
vec3 w3_setLum(vec3 c, float l) { return w3_clipColor(c + (l - w3_lum(c))); }
float w3_sat(vec3 c) { return max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b)); }
vec3 w3_setSat(vec3 c, float s) {
  float mx = max(c.r, max(c.g, c.b)); float mn = min(c.r, min(c.g, c.b)); float rng = mx - mn;
  return rng > 1e-6 ? (c - mn) * s / max(rng, 1e-6) : vec3(0.0);
}
float w3_hardLight1(float cb, float cs) { return cs <= 0.5 ? cb * 2.0 * cs : 1.0 - (1.0 - cb) * (1.0 - (2.0 * cs - 1.0)); }
float w3_softLight1(float cb, float cs) { return cs <= 0.5 ? 2.0 * cb * cs + cb * cb * (1.0 - 2.0 * cs) : 2.0 * cb * (1.0 - cs) + sqrt(max(cb, 0.0)) * (2.0 * cs - 1.0); }
float w3_dodge1(float cb, float cs) { if (cb <= 1e-4) return 0.0; return cs >= 1.0 ? 1.0 : min(1.0, cb / max(1e-6, 1.0 - cs)); }
float w3_burn1(float cb, float cs) { if (cb >= 1.0 - 1e-4) return 1.0; return cs <= 0.0 ? 0.0 : 1.0 - min(1.0, (1.0 - cb) / max(1e-6, cs)); }
float w3_vivid1(float cb, float cs) { if (cs <= 0.0) return 0.0; if (cs >= 1.0) return 1.0; return cs <= 0.5 ? 1.0 - min(1.0, (1.0 - cb) / max(1e-6, 2.0 * cs)) : min(1.0, cb / max(1e-6, 2.0 * (1.0 - cs))); }
float w3_pin1(float cb, float cs) { return cs <= 0.5 ? min(cb, 2.0 * cs) : max(cb, 2.0 * cs - 1.0); }
float w3_hardMix1(float cb, float cs) { float g = cs <= 0.5 ? w3_burn1(cb, 2.0 * cs) : w3_dodge1(cb, 2.0 * cs - 1.0); return g >= 0.5 - 1e-6 ? 1.0 : 0.0; }
vec3 w3_hardLight(vec3 b, vec3 s) { return vec3(w3_hardLight1(b.r, s.r), w3_hardLight1(b.g, s.g), w3_hardLight1(b.b, s.b)); }
vec3 w3_softLight(vec3 b, vec3 s) { return vec3(w3_softLight1(b.r, s.r), w3_softLight1(b.g, s.g), w3_softLight1(b.b, s.b)); }
vec3 w3_dodge(vec3 b, vec3 s) { return vec3(w3_dodge1(b.r, s.r), w3_dodge1(b.g, s.g), w3_dodge1(b.b, s.b)); }
vec3 w3_burn(vec3 b, vec3 s) { return vec3(w3_burn1(b.r, s.r), w3_burn1(b.g, s.g), w3_burn1(b.b, s.b)); }
vec3 w3_vivid(vec3 b, vec3 s) { return vec3(w3_vivid1(b.r, s.r), w3_vivid1(b.g, s.g), w3_vivid1(b.b, s.b)); }
vec3 w3_pin(vec3 b, vec3 s) { return vec3(w3_pin1(b.r, s.r), w3_pin1(b.g, s.g), w3_pin1(b.b, s.b)); }
vec3 w3_hardMix(vec3 b, vec3 s) { return vec3(w3_hardMix1(b.r, s.r), w3_hardMix1(b.g, s.g), w3_hardMix1(b.b, s.b)); }
float w3_hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
`

const WGSL_FUNCS = /* wgsl */ `
fn w3_lum(c: vec3<f32>) -> f32 { return 0.3 * c.r + 0.59 * c.g + 0.11 * c.b; }
fn w3_clipColor(cIn: vec3<f32>) -> vec3<f32> {
  var c = cIn;
  let l = w3_lum(c);
  let n = min(c.r, min(c.g, c.b));
  let x = max(c.r, max(c.g, c.b));
  if (n < 0.0) { c = vec3<f32>(l) + (c - vec3<f32>(l)) * (l / max(l - n, 1e-6)); }
  if (x > 1.0) { c = vec3<f32>(l) + (c - vec3<f32>(l)) * ((1.0 - l) / max(x - l, 1e-6)); }
  return c;
}
fn w3_setLum(c: vec3<f32>, l: f32) -> vec3<f32> { return w3_clipColor(c + vec3<f32>(l - w3_lum(c))); }
fn w3_sat(c: vec3<f32>) -> f32 { return max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b)); }
fn w3_setSat(c: vec3<f32>, s: f32) -> vec3<f32> {
  let mx = max(c.r, max(c.g, c.b)); let mn = min(c.r, min(c.g, c.b)); let rng = mx - mn;
  if (rng > 1e-6) { return (c - vec3<f32>(mn)) * (s / max(rng, 1e-6)); }
  return vec3<f32>(0.0);
}
fn w3_hardLight1(cb: f32, cs: f32) -> f32 { return select(1.0 - (1.0 - cb) * (1.0 - (2.0 * cs - 1.0)), cb * 2.0 * cs, cs <= 0.5); }
fn w3_softLight1(cb: f32, cs: f32) -> f32 { return select(2.0 * cb * (1.0 - cs) + sqrt(max(cb, 0.0)) * (2.0 * cs - 1.0), 2.0 * cb * cs + cb * cb * (1.0 - 2.0 * cs), cs <= 0.5); }
fn w3_dodge1(cb: f32, cs: f32) -> f32 { if (cb <= 1e-4) { return 0.0; } if (cs >= 1.0) { return 1.0; } return min(1.0, cb / max(1e-6, 1.0 - cs)); }
fn w3_burn1(cb: f32, cs: f32) -> f32 { if (cb >= 1.0 - 1e-4) { return 1.0; } if (cs <= 0.0) { return 0.0; } return 1.0 - min(1.0, (1.0 - cb) / max(1e-6, cs)); }
fn w3_vivid1(cb: f32, cs: f32) -> f32 { if (cs <= 0.0) { return 0.0; } if (cs >= 1.0) { return 1.0; } if (cs <= 0.5) { return 1.0 - min(1.0, (1.0 - cb) / max(1e-6, 2.0 * cs)); } return min(1.0, cb / max(1e-6, 2.0 * (1.0 - cs))); }
fn w3_pin1(cb: f32, cs: f32) -> f32 { if (cs <= 0.5) { return min(cb, 2.0 * cs); } return max(cb, 2.0 * cs - 1.0); }
fn w3_hardMix1(cb: f32, cs: f32) -> f32 { var g = 0.0; if (cs <= 0.5) { g = w3_burn1(cb, 2.0 * cs); } else { g = w3_dodge1(cb, 2.0 * cs - 1.0); } if (g >= 0.5 - 1e-6) { return 1.0; } return 0.0; }
fn w3_hardLight(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_hardLight1(b.r, s.r), w3_hardLight1(b.g, s.g), w3_hardLight1(b.b, s.b)); }
fn w3_softLight(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_softLight1(b.r, s.r), w3_softLight1(b.g, s.g), w3_softLight1(b.b, s.b)); }
fn w3_dodge(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_dodge1(b.r, s.r), w3_dodge1(b.g, s.g), w3_dodge1(b.b, s.b)); }
fn w3_burn(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_burn1(b.r, s.r), w3_burn1(b.g, s.g), w3_burn1(b.b, s.b)); }
fn w3_vivid(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_vivid1(b.r, s.r), w3_vivid1(b.g, s.g), w3_vivid1(b.b, s.b)); }
fn w3_pin(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_pin1(b.r, s.r), w3_pin1(b.g, s.g), w3_pin1(b.b, s.b)); }
fn w3_hardMix(b: vec3<f32>, s: vec3<f32>) -> vec3<f32> { return vec3<f32>(w3_hardMix1(b.r, s.r), w3_hardMix1(b.g, s.g), w3_hardMix1(b.b, s.b)); }
fn w3_hash(p: vec2<f32>) -> f32 { return fract(sin(dot(p, vec2<f32>(12.9898, 78.233))) * 43758.5453); }
`

/** B(cb, cs) per mode, as a GLSL expression and a WGSL expression. */
const EXPR: Record<Mode, [string, string]> = {
  normal: ['cs', 'cs'],
  dissolve: ['cs', 'cs'],
  darken: ['min(cb, cs)', 'min(cb, cs)'],
  multiply: ['cb * cs', 'cb * cs'],
  'color-burn': ['w3_burn(cb, cs)', 'w3_burn(cb, cs)'],
  'linear-burn': ['cb + cs - 1.0', 'cb + cs - vec3<f32>(1.0)'],
  lighten: ['max(cb, cs)', 'max(cb, cs)'],
  screen: ['cb + cs - cb * cs', 'cb + cs - cb * cs'],
  'color-dodge': ['w3_dodge(cb, cs)', 'w3_dodge(cb, cs)'],
  'linear-dodge': ['cb + cs', 'cb + cs'],
  overlay: ['w3_hardLight(cs, cb)', 'w3_hardLight(cs, cb)'],
  'soft-light': ['w3_softLight(cb, cs)', 'w3_softLight(cb, cs)'],
  'hard-light': ['w3_hardLight(cb, cs)', 'w3_hardLight(cb, cs)'],
  'vivid-light': ['w3_vivid(cb, cs)', 'w3_vivid(cb, cs)'],
  'linear-light': ['cb + 2.0 * cs - 1.0', 'cb + 2.0 * cs - vec3<f32>(1.0)'],
  'pin-light': ['w3_pin(cb, cs)', 'w3_pin(cb, cs)'],
  'hard-mix': ['w3_hardMix(cb, cs)', 'w3_hardMix(cb, cs)'],
  difference: ['abs(cb - cs)', 'abs(cb - cs)'],
  exclusion: ['cb + cs - 2.0 * cb * cs', 'cb + cs - 2.0 * cb * cs'],
  subtract: ['cb - cs', 'cb - cs'],
  divide: ['cb / max(cs, vec3(1e-6))', 'cb / max(cs, vec3<f32>(1e-6))'],
  hue: ['w3_setLum(w3_setSat(cs, w3_sat(cb)), w3_lum(cb))', 'w3_setLum(w3_setSat(cs, w3_sat(cb)), w3_lum(cb))'],
  saturation: ['w3_setLum(w3_setSat(cb, w3_sat(cs)), w3_lum(cb))', 'w3_setLum(w3_setSat(cb, w3_sat(cs)), w3_lum(cb))'],
  color: ['w3_setLum(cs, w3_lum(cb))', 'w3_setLum(cs, w3_lum(cb))'],
  luminosity: ['w3_setLum(cb, w3_lum(cs))', 'w3_setLum(cb, w3_lum(cs))'],
}

function glMain(mode: Mode): string {
  return `
    float ab = back.a;
    float sa = front.a;
    ${mode === 'dissolve' ? 'sa = step(w3_hash(vTextureCoord), sa);' : ''}
    vec3 cb = ab > 0.0 ? back.rgb / ab : vec3(0.0);
    vec3 cs = front.a > 0.0 ? front.rgb / front.a : vec3(0.0);
    vec3 B = clamp(${EXPR[mode][0]}, 0.0, 1.0);
    // Pixi draws the filter output over the backdrop with source-over, so emit only the source-side term
    // (premultiplied): the backdrop's cb·αb·(1−αs) is added by that final blend.
    finalColor = vec4((cs * (1.0 - ab) + B * ab) * sa, sa) * uBlend;
  `
}

function wgslMain(mode: Mode): string {
  return `
    let ab = back.a;
    var sa = front.a;
    ${mode === 'dissolve' ? 'sa = step(w3_hash(uv), sa);' : ''}
    var cb = vec3<f32>(0.0);
    if (ab > 0.0) { cb = back.rgb / ab; }
    var cs = vec3<f32>(0.0);
    if (front.a > 0.0) { cs = front.rgb / front.a; }
    let B = clamp(${EXPR[mode][1]}, vec3<f32>(0.0), vec3<f32>(1.0));
    out = vec4<f32>((cs * (1.0 - ab) + B * ab) * sa, sa) * blendUniforms.uBlend;
  `
}

/** The registered PixiJS blend-mode name for a layer; plain 'normal' stays on the native fast path. */
export function blendName(mode: string, alt: boolean): string {
  const m = (MODES as readonly string[]).includes(mode) ? mode : 'normal'
  if (m === 'normal') return 'normal'
  return `w3c-${m}${alt ? '-b' : ''}`
}

/** The base of a clip run, drawn opaque (straight colour, alpha 1 where it has any alpha): the clipped layers above it then
 * blend "as if the base were opaque" with their ordinary filters, and the run is masked by the base's alpha afterwards. */
export const OPAQUE_BLEND = 'w3c-opaque'

/** Index of a mode in MODES (the uniform the adjustment filters switch on); unknown modes and 'pass-through' → normal. */
export function modeIndex(mode: string): number { return Math.max(0, (MODES as readonly string[]).indexOf(mode)) }

/** `B(cb, cs)` by mode index, for shaders that take the mode as a uniform (adjustment and filter layers, D39). */
export const BLEND_GL = GL_FUNCS + `vec3 w3_blendBy(int m, vec3 cb, vec3 cs) {\n${MODES.map((mode, i) => `  if (m == ${i}) return ${EXPR[mode][0]};`).join('\n')}\n  return cs;\n}\n`
export const BLEND_WGSL = WGSL_FUNCS + `fn w3_blendBy(m: i32, cb: vec3<f32>, cs: vec3<f32>) -> vec3<f32> {\n  switch m {\n${MODES.map((mode, i) => `    case ${i}: { return ${EXPR[mode][1]}; }`).join('\n')}\n    default: { return cs; }\n  }\n}\n`

let registered = false
export function registerBlendModes(): void {
  if (registered) return
  registered = true
  for (const mode of MODES) for (const alt of [false, true]) {
    const name = blendName(mode, alt)
    if (name === 'normal') continue
    const F = class extends BlendModeFilter {
      static extension = { name, type: ExtensionType.BlendMode }
      constructor() { super({ gl: { functions: GL_FUNCS, main: glMain(mode) }, gpu: { functions: WGSL_FUNCS, main: wgslMain(mode) } }) }
    }
    extensions.add(F)
  }
  extensions.add(class extends BlendModeFilter {
    static extension = { name: OPAQUE_BLEND, type: ExtensionType.BlendMode }
    constructor() {
      super({
        gl: { functions: '', main: 'finalColor = front.a > 0.0 ? vec4(front.rgb / front.a, 1.0) : vec4(0.0);' },
        gpu: { functions: '', main: 'out = vec4<f32>(0.0); if (front.a > 0.0) { out = vec4<f32>(front.rgb / front.a, 1.0); }' },
      })
    }
  })
}
registerBlendModes()
