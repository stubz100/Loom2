//! S2 spike: PhotoCraft's Quick Selection (segment::quick, a banded min cut fitted to Photoshop) and Magnetic Lasso
//! (magnetic::Tracer) behind a C ABI for a Web Worker. The document is set once as straight RGBA8; a stroke returns a
//! coverage region; a trace returns a polyline. Single-threaded (wasm32 builds of photocraft-algo have no rayon).
use std::cell::RefCell;

use photocraft_algo::magnetic::{Settings, Tracer};
use photocraft_algo::segment::quick::quick_select;
use photocraft_algo::segment::Sampler;
use photocraft_geom::Rect;

struct Doc {
    w: i32,
    h: i32,
    rgba: Vec<u8>,
}

thread_local! {
    static DOC: RefCell<Option<Doc>> = const { RefCell::new(None) };
    static TRACER: RefCell<Option<Tracer>> = const { RefCell::new(None) };
    static REGION: RefCell<(i32, i32, i32, i32, Vec<u8>)> = const { RefCell::new((0, 0, 0, 0, Vec::new())) };
    static PATH: RefCell<Vec<f64>> = const { RefCell::new(Vec::new()) };
}

struct DocSampler<'a>(&'a Doc);
impl Sampler for DocSampler<'_> {
    fn rgba(&self, r: Rect) -> Vec<[f32; 4]> {
        let d = self.0;
        let mut out = Vec::with_capacity((r.width().max(0) * r.height().max(0)) as usize);
        for y in r.y0..r.y1 {
            for x in r.x0..r.x1 {
                if x < 0 || y < 0 || x >= d.w || y >= d.h {
                    out.push([0.0; 4]);
                } else {
                    let i = ((y * d.w + x) * 4) as usize;
                    out.push([d.rgba[i] as f32 / 255.0, d.rgba[i + 1] as f32 / 255.0, d.rgba[i + 2] as f32 / 255.0, d.rgba[i + 3] as f32 / 255.0]);
                }
            }
        }
        out
    }
}

fn fetch_rgba8(d: &Doc, r: Rect) -> Vec<[u8; 4]> {
    let mut out = Vec::with_capacity((r.width().max(0) * r.height().max(0)) as usize);
    for y in r.y0..r.y1 {
        for x in r.x0..r.x1 {
            if x < 0 || y < 0 || x >= d.w || y >= d.h {
                out.push([0; 4]);
            } else {
                let i = ((y * d.w + x) * 4) as usize;
                out.push([d.rgba[i], d.rgba[i + 1], d.rgba[i + 2], d.rgba[i + 3]]);
            }
        }
    }
    out
}

/// Bytes for the caller to fill (the image, the stroke points).
#[unsafe(no_mangle)]
pub extern "C" fn alloc(n: usize) -> *mut u8 {
    let mut v = Vec::<u8>::with_capacity(n);
    let p = v.as_mut_ptr();
    std::mem::forget(v);
    p
}

/// # Safety
/// `p` must come from `alloc(n)` with the same `n`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn dealloc(p: *mut u8, n: usize) {
    unsafe { drop(Vec::from_raw_parts(p, 0, n)) }
}

/// # Safety
/// `p` points at `w * h * 4` bytes of straight RGBA8 (row-major).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn set_image(p: *const u8, w: i32, h: i32) {
    let n = (w.max(0) * h.max(0) * 4) as usize;
    let rgba = unsafe { std::slice::from_raw_parts(p, n) }.to_vec();
    DOC.with(|d| *d.borrow_mut() = Some(Doc { w, h, rgba }));
    TRACER.with(|t| *t.borrow_mut() = Some(Tracer::new(Rect::new(0, 0, w, h))));
}

/// A Quick Selection stroke: `n` points (x, y pairs of f32, document px), brush diameter `size`. Returns 1 when a region was
/// grown (read it with region_*), 0 otherwise.
///
/// # Safety
/// `pts` points at `2 * n` f32.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn quick(pts: *const f32, n: usize, size: f32) -> i32 {
    let raw = unsafe { std::slice::from_raw_parts(pts, 2 * n) };
    let points: Vec<(f32, f32)> = raw.chunks_exact(2).map(|c| (c[0], c[1])).collect();
    DOC.with(|d| {
        let d = d.borrow();
        let Some(doc) = d.as_ref() else { return 0 };
        match quick_select(&DocSampler(doc), Rect::new(0, 0, doc.w, doc.h), &points, size) {
            Some(r) => {
                REGION.with(|g| *g.borrow_mut() = (r.bbox.x0, r.bbox.y0, r.bbox.x1, r.bbox.y1, r.mask));
                1
            }
            None => 0,
        }
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn region_box(i: i32) -> i32 {
    REGION.with(|g| { let g = g.borrow(); [g.0, g.1, g.2, g.3][i.clamp(0, 3) as usize] })
}

#[unsafe(no_mangle)]
pub extern "C" fn region_mask() -> *const u8 {
    REGION.with(|g| g.borrow().4.as_ptr())
}

/// A Magnetic Lasso segment from (x0, y0) to (x1, y1) with the detection width and contrast; returns the number of points
/// (read them with path_ptr as x, y f64 pairs).
#[unsafe(no_mangle)]
pub extern "C" fn trace(x0: f64, y0: f64, x1: f64, y1: f64, width: f64, contrast: f32) -> usize {
    DOC.with(|d| {
        let d = d.borrow();
        let Some(doc) = d.as_ref() else { return 0 };
        TRACER.with(|t| {
            let mut t = t.borrow_mut();
            let Some(tr) = t.as_mut() else { return 0 };
            let mut fetch = |r: Rect| fetch_rgba8(doc, r);
            let path = tr.trace(&mut fetch, [x0, y0], [x1, y1], &[], Settings::new(width, contrast));
            let n = path.len();
            PATH.with(|p| *p.borrow_mut() = path.into_iter().flatten().collect());
            n
        })
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn path_ptr() -> *const f64 {
    PATH.with(|p| p.borrow().as_ptr())
}
