// GPU previews for adjustment and filter layers (10 §3). One Filter per layer instance, registered as a PixiJS
// blend mode ("adj-<layerId>") so the layer's document-sized sprite (white, or its mask) sets the filter bounds
// and carries the layer alpha, while the backdrop arrives as uBackTexture. The filter draws with blend 'none' and
// writes the mixed backdrop with compose.py's rules (D39: the layer's blend mode applies, uP3.w = its index in MODES):
//   adjustment: rgb = cb + (B(mode, cb, f(cb)) − cb)·a where αb > 0, alpha unchanged
//   filter:     the same for rgb, alpha mixed linearly between the backdrop and f(backdrop)
// Per-channel adjustments (levels, curves, exposure, brightness/contrast, invert) are evaluated on the CPU into a
// 256-entry LUT with the exact formulas; hue/saturation, colour balance and black & white run the same math in the
// shader; blur-based filters sample the premultiplied backdrop with compose.py's Gaussian (exact up to a 12-tap
// radius, strided above); noise hashes (seed, x, y) with the same integer hash + Box-Muller as compose.py, so it is exact too.
import { BufferImageSource, ExtensionType, extensions, Filter, GlProgram, GpuProgram, Texture } from 'pixi.js'
import { BLEND_GL, BLEND_WGSL, modeIndex } from './blendModes'
import type { Node } from './editorStore'

const MAX_TAPS = 12

const GL_VERT = /* glsl */ `in vec2 aPosition;
out vec2 vTextureCoord;
uniform vec4 uInputSize;
uniform vec4 uOutputFrame;
uniform vec4 uOutputTexture;
vec4 filterVertexPosition(void) {
  vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;
  position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
  position.y = position.y * (2.0 * uOutputTexture.z / uOutputTexture.y) - uOutputTexture.z;
  return vec4(position, 0.0, 1.0);
}
void main(void) { gl_Position = filterVertexPosition(); vTextureCoord = aPosition * (uOutputFrame.zw * uInputSize.zw); }
`

const GL_FRAG = /* glsl */ `in vec2 vTextureCoord;
out vec4 finalColor;
uniform sampler2D uTexture;
uniform sampler2D uBackTexture;
uniform sampler2D uLutTexture;
uniform vec4 uInputPixel;
uniform vec4 uInputClamp;
uniform vec4 uP0; uniform vec4 uP1; uniform vec4 uP2; uniform vec4 uP3;
{BLEND}
float aj_lum(vec3 c) { return 0.3 * c.r + 0.59 * c.g + 0.11 * c.b; }
vec3 aj_rgb2hsl(vec3 c) {
  float mx = max(c.r, max(c.g, c.b)); float mn = min(c.r, min(c.g, c.b));
  float l = (mx + mn) * 0.5; float d = mx - mn;
  float s = d < 1e-6 ? 0.0 : d / max(1e-6, 1.0 - abs(2.0 * l - 1.0));
  float h = 0.0;
  if (d >= 1e-6) {
    if (mx == c.r) h = mod((c.g - c.b) / max(d, 1e-6), 6.0);
    if (mx == c.g) h = (c.b - c.r) / max(d, 1e-6) + 2.0;
    if (mx == c.b) h = (c.r - c.g) / max(d, 1e-6) + 4.0;
    h = mod(h / 6.0, 1.0);
  }
  return vec3(h, s, l);
}
vec3 aj_hsl2rgb(vec3 hsl) {
  float h = hsl.x; float s = hsl.y; float l = hsl.z;
  float c = (1.0 - abs(2.0 * l - 1.0)) * s;
  float hp = mod(h, 1.0) * 6.0;
  float x = c * (1.0 - abs(mod(hp, 2.0) - 1.0));
  float m = l - c * 0.5;
  vec3 rgb;
  if (hp < 1.0) rgb = vec3(c, x, 0.0); else if (hp < 2.0) rgb = vec3(x, c, 0.0); else if (hp < 3.0) rgb = vec3(0.0, c, x);
  else if (hp < 4.0) rgb = vec3(0.0, x, c); else if (hp < 5.0) rgb = vec3(x, 0.0, c); else rgb = vec3(c, 0.0, x);
  return rgb + m;
}
// noise: lowbias32 integer hash of (seed, x, y) → 23-bit uniforms → Box-Muller; compose.py runs the identical arithmetic
uint aj_h(uint x) { x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u; return x; }
float aj_u(uint v) { return (float(v >> 9u) + 0.5) / 8388608.0; }
vec3 aj_noise3(vec2 px, float seed) {
  uint k = aj_h(aj_h(aj_h(uint(int(seed))) + uint(px.x)) + uint(px.y));
  uint k2 = aj_h(k); uint k3 = aj_h(k2); uint k4 = aj_h(k3);
  float r1 = sqrt(-2.0 * log(aj_u(k))); float a1 = 6.283185307179586 * aj_u(k2);
  float r2 = sqrt(-2.0 * log(aj_u(k3))); float a2 = 6.283185307179586 * aj_u(k4);
  return vec3(r1 * cos(a1), r1 * sin(a1), r2 * cos(a2));
}
float aj_c2a1(float p, float c) { if (p > c) return c < 1.0 ? (p - c) / (1.0 - c) : 1.0; if (p < c) return c > 0.0 ? (c - p) / c : 1.0; return 0.0; }
float aj_c2a(vec3 p, vec3 key, float t, float o) { float a = clamp(max(aj_c2a1(p.r, key.r), max(aj_c2a1(p.g, key.g), aj_c2a1(p.b, key.b))), 0.0, 1.0); return a <= t ? 0.0 : a >= o ? 1.0 : clamp((a - t) / max(o - t, 1e-6), 0.0, 1.0); }
float aj_lut1(float v, int ch) { vec4 t = texture(uLutTexture, vec2((floor(v * 255.0 + 0.5) + 0.5) / 256.0, 0.5)); return ch == 0 ? t.r : ch == 1 ? t.g : t.b; }
vec3 aj_lut(vec3 c) { return vec3(aj_lut1(c.r, 0), aj_lut1(c.g, 1), aj_lut1(c.b, 2)); }
vec4 aj_blur(vec2 uv, float sigma, int r, int stride) {
  vec4 acc = vec4(0.0); float sum = 0.0;
  for (int j = -r; j <= r; j += stride) for (int i = -r; i <= r; i += stride) {
    float w = exp(-0.5 * float(i * i + j * j) / max(1e-6, sigma * sigma));
    acc += w * texture(uBackTexture, clamp(uv + vec2(float(i), float(j)) * uInputPixel.zw, uInputClamp.xy, uInputClamp.zw));
    sum += w;
  }
  return acc / sum;
}
void main() {
  vec4 back = texture(uBackTexture, vTextureCoord);
  vec4 front = texture(uTexture, vTextureCoord);
  float ab = back.a;
  float a = front.r;
  int bm = int(uP3.w + 0.5);
  vec3 cb = ab > 0.0 ? back.rgb / ab : vec3(0.0);
  {MAIN}
}
`

const WGSL = /* wgsl */ `struct GlobalFilterUniforms { uInputSize:vec4<f32>, uInputPixel:vec4<f32>, uInputClamp:vec4<f32>, uOutputFrame:vec4<f32>, uGlobalFrame:vec4<f32>, uOutputTexture:vec4<f32> };
struct AdjUniforms { uP0:vec4<f32>, uP1:vec4<f32>, uP2:vec4<f32>, uP3:vec4<f32> };
@group(0) @binding(0) var<uniform> gfu: GlobalFilterUniforms;
@group(0) @binding(1) var uTexture: texture_2d<f32>;
@group(0) @binding(2) var uSampler : sampler;
@group(0) @binding(3) var uBackTexture: texture_2d<f32>;
@group(1) @binding(0) var<uniform> adjUniforms : AdjUniforms;
@group(1) @binding(1) var uLutTexture: texture_2d<f32>;
@group(1) @binding(2) var uLutSampler: sampler;
struct VSOutput { @builtin(position) position: vec4<f32>, @location(0) uv : vec2<f32> };
fn filterVertexPosition(aPosition:vec2<f32>) -> vec4<f32> {
  var position = aPosition * gfu.uOutputFrame.zw + gfu.uOutputFrame.xy;
  position.x = position.x * (2.0 / gfu.uOutputTexture.x) - 1.0;
  position.y = position.y * (2.0 * gfu.uOutputTexture.z / gfu.uOutputTexture.y) - gfu.uOutputTexture.z;
  return vec4(position, 0.0, 1.0);
}
@vertex fn mainVertex(@location(0) aPosition : vec2<f32>) -> VSOutput { return VSOutput(filterVertexPosition(aPosition), aPosition * (gfu.uOutputFrame.zw * gfu.uInputSize.zw)); }
{BLEND}
fn aj_fmod(x: f32, y: f32) -> f32 { return x - y * floor(x / y); }
fn aj_lum(c: vec3<f32>) -> f32 { return 0.3 * c.r + 0.59 * c.g + 0.11 * c.b; }
fn aj_rgb2hsl(c: vec3<f32>) -> vec3<f32> {
  let mx = max(c.r, max(c.g, c.b)); let mn = min(c.r, min(c.g, c.b));
  let l = (mx + mn) * 0.5; let d = mx - mn;
  var s = 0.0;
  if (d >= 1e-6) { s = d / max(1e-6, 1.0 - abs(2.0 * l - 1.0)); }
  var h = 0.0;
  if (d >= 1e-6) {
    if (mx == c.r) { h = aj_fmod((c.g - c.b) / max(d, 1e-6), 6.0); }
    if (mx == c.g) { h = (c.b - c.r) / max(d, 1e-6) + 2.0; }
    if (mx == c.b) { h = (c.r - c.g) / max(d, 1e-6) + 4.0; }
    h = aj_fmod(h / 6.0, 1.0);
  }
  return vec3<f32>(h, s, l);
}
fn aj_hsl2rgb(hsl: vec3<f32>) -> vec3<f32> {
  let h = hsl.x; let s = hsl.y; let l = hsl.z;
  let c = (1.0 - abs(2.0 * l - 1.0)) * s;
  let hp = aj_fmod(h, 1.0) * 6.0;
  let x = c * (1.0 - abs(aj_fmod(hp, 2.0) - 1.0));
  let m = l - c * 0.5;
  var rgb = vec3<f32>(c, 0.0, x);
  if (hp < 1.0) { rgb = vec3<f32>(c, x, 0.0); } else if (hp < 2.0) { rgb = vec3<f32>(x, c, 0.0); } else if (hp < 3.0) { rgb = vec3<f32>(0.0, c, x); }
  else if (hp < 4.0) { rgb = vec3<f32>(0.0, x, c); } else if (hp < 5.0) { rgb = vec3<f32>(x, 0.0, c); }
  return rgb + vec3<f32>(m);
}
fn aj_h(x0: u32) -> u32 { var x = x0; x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u; return x; }
fn aj_u(v: u32) -> f32 { return (f32(v >> 9u) + 0.5) / 8388608.0; }
fn aj_noise3(px: vec2<f32>, seed: f32) -> vec3<f32> {
  let k = aj_h(aj_h(aj_h(u32(i32(seed))) + u32(px.x)) + u32(px.y));
  let k2 = aj_h(k); let k3 = aj_h(k2); let k4 = aj_h(k3);
  let r1 = sqrt(-2.0 * log(aj_u(k))); let a1 = 6.283185307179586 * aj_u(k2);
  let r2 = sqrt(-2.0 * log(aj_u(k3))); let a2 = 6.283185307179586 * aj_u(k4);
  return vec3<f32>(r1 * cos(a1), r1 * sin(a1), r2 * cos(a2));
}
fn aj_c2a1(p: f32, c: f32) -> f32 { if (p > c) { if (c < 1.0) { return (p - c) / (1.0 - c); } return 1.0; } if (p < c) { if (c > 0.0) { return (c - p) / c; } return 1.0; } return 0.0; }
fn aj_c2a(p: vec3<f32>, key: vec3<f32>, t: f32, o: f32) -> f32 { let a = clamp(max(aj_c2a1(p.r, key.r), max(aj_c2a1(p.g, key.g), aj_c2a1(p.b, key.b))), 0.0, 1.0); if (a <= t) { return 0.0; } if (a >= o) { return 1.0; } return clamp((a - t) / max(o - t, 1e-6), 0.0, 1.0); }
fn aj_lut1(v: f32, ch: i32) -> f32 { let t = textureSampleLevel(uLutTexture, uLutSampler, vec2<f32>((floor(v * 255.0 + 0.5) + 0.5) / 256.0, 0.5), 0.0); if (ch == 0) { return t.r; } if (ch == 1) { return t.g; } return t.b; }
fn aj_lut(c: vec3<f32>) -> vec3<f32> { return vec3<f32>(aj_lut1(c.r, 0), aj_lut1(c.g, 1), aj_lut1(c.b, 2)); }
fn aj_blur(uv: vec2<f32>, sigma: f32, r: i32, stride: i32) -> vec4<f32> {
  var acc = vec4<f32>(0.0); var sum = 0.0;
  for (var j: i32 = -r; j <= r; j += stride) {
    for (var i: i32 = -r; i <= r; i += stride) {
      let w = exp(-0.5 * f32(i * i + j * j) / max(1e-6, sigma * sigma));
      acc += w * textureSampleLevel(uBackTexture, uSampler, clamp(uv + vec2<f32>(f32(i), f32(j)) * gfu.uInputPixel.zw, gfu.uInputClamp.xy, gfu.uInputClamp.zw), 0.0);
      sum += w;
    }
  }
  return acc / sum;
}
@fragment fn mainFragment(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
  let back = textureSampleLevel(uBackTexture, uSampler, uv, 0.0);
  let front = textureSampleLevel(uTexture, uSampler, uv, 0.0);
  let uP0 = adjUniforms.uP0; let uP1 = adjUniforms.uP1; let uP2 = adjUniforms.uP2; let uP3 = adjUniforms.uP3;
  let ab = back.a;
  let a = front.r;
  let bm = i32(uP3.w + 0.5);
  var cb = vec3<f32>(0.0);
  if (ab > 0.0) { cb = back.rgb / ab; }
  var out = vec4<f32>(0.0);
  {MAIN}
  return out;
}
`

/** Per type: [GLSL main, WGSL main]. Adjustments end in `adj`; filters end in `fr` (rgb) and `fa` (alpha). */
function mains(type: string, kind: 'adjustment' | 'filter'): [string, string] {
  const adjGl = (expr: string) => `vec3 adj = clamp(${expr}, 0.0, 1.0); vec3 mixed = ab > 0.0 ? cb + (clamp(w3_blendBy(bm, cb, adj), 0.0, 1.0) - cb) * a : cb; finalColor = vec4(mixed * ab, ab);`
  const adjWg = (expr: string) => `let adj = clamp(${expr}, vec3<f32>(0.0), vec3<f32>(1.0)); var mixed = cb; if (ab > 0.0) { mixed = cb + (clamp(w3_blendBy(bm, cb, adj), vec3<f32>(0.0), vec3<f32>(1.0)) - cb) * a; } out = vec4<f32>(mixed * ab, ab);`
  const fltGl = (body: string) => `${body} vec3 mr = cb + (clamp(w3_blendBy(bm, cb, fr), 0.0, 1.0) - cb) * a; float ma = mix(ab, fa, a); finalColor = vec4(mr * ma, ma);`
  const fltWg = (body: string) => `${body} let mr = cb + (clamp(w3_blendBy(bm, cb, fr), vec3<f32>(0.0), vec3<f32>(1.0)) - cb) * a; let ma = mix(ab, fa, a); out = vec4<f32>(mr * ma, ma);`
  const blurGl = 'vec4 bb = aj_blur(vTextureCoord, uP0.x, int(uP0.y), int(uP0.z)); vec3 bl = bb.a > 1e-6 ? bb.rgb / bb.a : vec3(0.0);'
  const blurWg = 'let bb = aj_blur(uv, uP0.x, i32(uP0.y), i32(uP0.z)); var bl = vec3<f32>(0.0); if (bb.a > 1e-6) { bl = bb.rgb / bb.a; }'
  if (kind === 'adjustment') {
    switch (type) {
      case 'hue_saturation': return [
        adjGl('aj_hsl2rgb(vec3(mod(aj_rgb2hsl(cb).x + uP0.x / 360.0, 1.0), clamp(aj_rgb2hsl(cb).y * (1.0 + uP0.y / 100.0), 0.0, 1.0), clamp(uP0.z > 0.0 ? aj_rgb2hsl(cb).z + uP0.z / 100.0 * (1.0 - aj_rgb2hsl(cb).z) : aj_rgb2hsl(cb).z * (1.0 + uP0.z / 100.0), 0.0, 1.0)))'),
        'let hsl = aj_rgb2hsl(cb); let li = uP0.z / 100.0; var l2 = hsl.z * (1.0 + li); if (li > 0.0) { l2 = hsl.z + li * (1.0 - hsl.z); } ' + adjWg('aj_hsl2rgb(vec3<f32>(aj_fmod(hsl.x + uP0.x / 360.0, 1.0), clamp(hsl.y * (1.0 + uP0.y / 100.0), 0.0, 1.0), clamp(l2, 0.0, 1.0)))'),
      ]
      case 'color_balance': return [
        'float lum = aj_lum(cb); float sh = clamp(1.0 - lum * 2.0, 0.0, 1.0); float hi = clamp(lum * 2.0 - 1.0, 0.0, 1.0); float mid = 1.0 - sh - hi; ' + adjGl('cb + sh * uP0.xyz + mid * uP1.xyz + hi * uP2.xyz'),
        'let lum = aj_lum(cb); let sh = clamp(1.0 - lum * 2.0, 0.0, 1.0); let hi = clamp(lum * 2.0 - 1.0, 0.0, 1.0); let mid = 1.0 - sh - hi; ' + adjWg('cb + sh * uP0.xyz + mid * uP1.xyz + hi * uP2.xyz'),
      ]
      case 'black_white': return [adjGl('vec3(dot(cb, uP0.xyz))'), adjWg('vec3<f32>(dot(cb, uP0.xyz))')]
      default: return [adjGl('aj_lut(cb)'), adjWg('aj_lut(cb)')]            // levels, curves, exposure, brightness_contrast, invert
    }
  }
  switch (type) {
    case 'gaussian_blur': return [fltGl(`${blurGl} vec3 fr = bl; float fa = bb.a;`), fltWg(`${blurWg} let fr = bl; let fa = bb.a;`)]
    case 'sharpen': return [
      fltGl(`${blurGl} vec3 diff = cb - bl; diff *= step(uP1.y, abs(diff)); vec3 fr = clamp(cb + uP1.x * diff, 0.0, 1.0); float fa = ab;`),
      fltWg(`${blurWg} var diff = cb - bl; diff = diff * step(vec3<f32>(uP1.y), abs(diff)); let fr = clamp(cb + uP1.x * diff, vec3<f32>(0.0), vec3<f32>(1.0)); let fa = ab;`),
    ]
    case 'high_pass': return [fltGl(`${blurGl} vec3 fr = clamp(cb - bl + 0.5, 0.0, 1.0); float fa = ab;`), fltWg(`${blurWg} let fr = clamp(cb - bl + vec3<f32>(0.5), vec3<f32>(0.0), vec3<f32>(1.0)); let fa = ab;`)]
    case 'noise': return [
      fltGl('vec2 px = floor(vTextureCoord * uInputPixel.xy); vec3 n = aj_noise3(px, uP0.w) * uP0.x; if (uP0.y > 0.5) n = vec3(n.x); vec3 fr = clamp(cb + n, 0.0, 1.0); float fa = ab;'),
      fltWg('let px = floor(uv * gfu.uInputPixel.xy); var n = aj_noise3(px, uP0.w) * uP0.x; if (uP0.y > 0.5) { n = vec3<f32>(n.x); } let fr = clamp(cb + n, vec3<f32>(0.0), vec3<f32>(1.0)); let fa = ab;'),
    ]
    case 'color_to_alpha': return [                                         // D49: compose.py _color_to_alpha
      fltGl('float ca = aj_c2a(cb, uP0.rgb, uP1.x, uP1.y); vec3 fr = ca >= 1.0 ? cb : ca <= 0.0 ? uP0.rgb : clamp(uP0.rgb + (cb - uP0.rgb) / ca, 0.0, 1.0); float fa = ab * ca;'),
      fltWg('let ca = aj_c2a(cb, uP0.rgb, uP1.x, uP1.y); var fr = clamp(uP0.rgb + (cb - uP0.rgb) / max(ca, 1e-6), vec3<f32>(0.0), vec3<f32>(1.0)); if (ca >= 1.0) { fr = cb; } if (ca <= 0.0) { fr = uP0.rgb; } let fa = ab * ca;'),
    ]
    default: return [fltGl('vec3 fr = cb; float fa = ab;'), fltWg('let fr = cb; let fa = ab;')]
  }
}

// ---- exact per-channel maps for the LUT types (compose.py) ------------------------------------------------
function curve(x: number, points: unknown): number {
  if (!Array.isArray(points) || !points.length) return x
  let pts = (points as [number, number][]).map(([a, b]) => [Number(a) / 255, Number(b) / 255] as [number, number]).sort((p, q) => p[0] - q[0])
  if (pts[0][0] > 0) pts = [[0, pts[0][1]], ...pts]
  if (pts[pts.length - 1][0] < 1) pts = [...pts, [1, pts[pts.length - 1][1]]]
  if (x <= pts[0][0]) return pts[0][1]
  for (let i = 1; i < pts.length; i++) if (x <= pts[i][0]) { const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; return x1 === x0 ? y1 : y0 + (y1 - y0) * (x - x0) / (x1 - x0) }
  return pts[pts.length - 1][1]
}
const hexRgb = (h: string): [number, number, number] => { const m = /^#?([0-9a-f]{6})$/i.exec(h.trim()); const v = m ? m[1] : 'ffffff'; return [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255) as [number, number, number] }
const num = (p: Record<string, unknown>, k: string, d: number) => { const v = Number(p[k]); return Number.isFinite(v) ? v : d }
function channelMap(type: string, p: Record<string, unknown>): (x: number, ch: number) => number {
  switch (type) {
    case 'levels': { const ib = num(p, 'in_black', 0) / 255, iw = num(p, 'in_white', 255) / 255, g = Math.max(0.01, num(p, 'gamma', 1)), ob = num(p, 'out_black', 0) / 255, ow = num(p, 'out_white', 255) / 255
      return (x) => ob + Math.min(1, Math.max(0, (x - ib) / Math.max(1e-6, iw - ib))) ** (1 / g) * (ow - ob) }
    case 'curves': return (x, ch) => curve(curve(x, p.rgb), p[['r', 'g', 'b'][ch]])
    // D40: Photoshop's Exposure works in linear light through a pure 2.2 power (compose.py _exposure)
    case 'exposure': { const ev = num(p, 'exposure', 0), off = num(p, 'offset', 0), g = Math.max(0.01, num(p, 'gamma', 1)); return (x) => Math.min(1, Math.max(0, Math.max(0, x ** 2.2 * 2 ** ev + off) ** (1 / g)) ** (1 / 2.2)) }
    case 'brightness_contrast': { const b = num(p, 'brightness', 0) / 100, c = num(p, 'contrast', 0) / 100; const f = c < 1 ? (1 + c) / Math.max(1e-6, 1 - c) : 1e6; return (x) => Math.min(1, Math.max(0, (x + b - 0.5) * f + 0.5)) }
    case 'invert': return (x) => 1 - x
    default: return (x) => x
  }
}

// ---- registry ---------------------------------------------------------------------------------------------
interface AdjState { name: string; type: string; kind: 'adjustment' | 'filter'; p: Float32Array[]; lut: BufferImageSource; lutData: Uint8Array; filter: AdjFilter | null }
const STATES = new Map<string, AdjState>()

class AdjFilter extends Filter {
  constructor(st: AdjState) {
    const [glMain, wgMain] = mains(st.type, st.kind)
    const wgsl = WGSL.replace('{BLEND}', BLEND_WGSL).replace('{MAIN}', wgMain)
    const gpuProgram = GpuProgram.from({ vertex: { source: wgsl, entryPoint: 'mainVertex' }, fragment: { source: wgsl, entryPoint: 'mainFragment' } })
    const glProgram = GlProgram.from({ vertex: GL_VERT, fragment: GL_FRAG.replace('{BLEND}', BLEND_GL).replace('{MAIN}', glMain) })
    super({
      gpuProgram, glProgram, blendRequired: true,
      resources: {
        adjUniforms: { uP0: { value: st.p[0], type: 'vec4<f32>' }, uP1: { value: st.p[1], type: 'vec4<f32>' }, uP2: { value: st.p[2], type: 'vec4<f32>' }, uP3: { value: st.p[3], type: 'vec4<f32>' } },
        uBackTexture: Texture.EMPTY, uLutTexture: st.lut, uLutSampler: st.lut.style,
      },
    })
    this.blendMode = 'none'
    st.filter = this
  }
  touch(): void { (this.resources.adjUniforms as { update: () => void }).update() }
}

function blurParams(radius: number): [number, number, number] {
  const sigma = Math.max(0, radius)
  const rFull = sigma > 0 ? Math.max(1, Math.ceil(sigma * 3)) : 0
  const stride = Math.max(1, Math.ceil(rFull / MAX_TAPS))
  return [sigma, Math.floor(rFull / stride) * stride, stride]
}

/** Register (once) and update the filter for an adjustment/filter node; returns its blend-mode name. */
export function ensureAdjustment(n: Node): string {
  const name = `adj-${n.id}`
  const kind = n.kind === 'filter' ? 'filter' : 'adjustment'
  const type = n.type ?? (kind === 'filter' ? 'gaussian_blur' : 'levels')
  let st = STATES.get(name)
  if (!st) {
    const lutData = new Uint8Array(256 * 4)
    const lut = new BufferImageSource({ resource: lutData, width: 256, height: 1, format: 'rgba8unorm', alphaMode: 'no-premultiply-alpha', scaleMode: 'nearest' })
    st = { name, type, kind, p: [new Float32Array(4), new Float32Array(4), new Float32Array(4), new Float32Array(4)], lut, lutData, filter: null }
    STATES.set(name, st)
    const state = st
    extensions.add({ name, type: ExtensionType.BlendMode, ref: class extends AdjFilter { constructor() { super(state) } } })
  }
  const p = n.params ?? {}
  const [p0, p1, p2, p3] = st.p
  p0.fill(0); p1.fill(0); p2.fill(0); p3.fill(0)
  p3[3] = modeIndex(n.blend === 'pass-through' ? 'normal' : n.blend)   // D39: the layer's blend mode (clipping is done by EditorCanvas passes)
  if (kind === 'adjustment') {
    if (type === 'hue_saturation') p0.set([num(p, 'hue', 0), num(p, 'saturation', 0), num(p, 'lightness', 0)])
    else if (type === 'color_balance') {
      for (const [i, k] of (['shadows', 'midtones', 'highlights'] as const).entries()) { const v = Array.isArray(p[k]) ? (p[k] as number[]) : [0, 0, 0]; st.p[i].set([Number(v[0] ?? 0) / 100, Number(v[1] ?? 0) / 100, Number(v[2] ?? 0) / 100]) }
    } else if (type === 'black_white') {
      const w = [num(p, 'r', 40), num(p, 'g', 60), num(p, 'b', 20)]; const s = w[0] + w[1] + w[2]
      p0.set(s > 0 ? w.map((x) => x / s) : [0.3, 0.59, 0.11])
    } else {
      const f = channelMap(type, p)
      for (let v = 0; v < 256; v++) for (let ch = 0; ch < 3; ch++) st.lutData[v * 4 + ch] = Math.round(Math.min(1, Math.max(0, f(v / 255, ch))) * 255)
      for (let v = 0; v < 256; v++) st.lutData[v * 4 + 3] = 255
      st.lut.update()
    }
  } else {
    if (type === 'noise') p0.set([num(p, 'amount', 10) / 100, p.monochrome === false ? 0 : 1, 0, num(p, 'seed', 0)])
    else if (type === 'color_to_alpha') { p0.set([...hexRgb(String(p.colour ?? '#ffffff')), 0]); p1.set([num(p, 'transparency_threshold', 0) / 100, num(p, 'opacity_threshold', 100) / 100, 0, 0]) }
    else {
      p0.set(blurParams(num(p, 'radius', type === 'high_pass' ? 3 : type === 'sharpen' ? 1 : 2)))
      if (type === 'sharpen') p1.set([num(p, 'amount', 100) / 100, num(p, 'threshold', 0) / 255])
    }
  }
  st.filter?.touch()
  return name
}
