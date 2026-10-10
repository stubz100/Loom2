//! The same strokes natively (one thread — photocraft-algo's quick select is one min cut), to size the wasm overhead.
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (path, w, h): (&str, i32, i32) = (&a[1], a[2].parse().unwrap(), a[3].parse().unwrap());
    let rgba = std::fs::read(path).unwrap();
    unsafe { loom2_pcwasm::set_image(rgba.as_ptr(), w, h) };
    let (wf, hf) = (w as f32, h as f32);
    let mut out = vec![];
    for (fx, fy) in [(0.3, 0.4), (0.5, 0.5), (0.7, 0.3), (0.2, 0.8), (0.8, 0.75)] {
        let p = [fx * wf, fy * hf];
        let t = Instant::now(); unsafe { loom2_pcwasm::quick(p.as_ptr(), 1, 30.0) }; out.push(t.elapsed().as_millis());
    }
    let mut drag = vec![];
    for i in 0..15 { drag.push(wf * (0.35 + i as f32 * 0.01)); drag.push(hf * (0.45 + (i as f32 / 3.0).sin() * 0.02)); }
    let t = Instant::now(); unsafe { loom2_pcwasm::quick(drag.as_ptr(), 15, 40.0) }; let td = t.elapsed().as_millis();
    let big = [0.5 * wf, 0.5 * hf];
    let t = Instant::now(); unsafe { loom2_pcwasm::quick(big.as_ptr(), 1, 200.0) }; let tb = t.elapsed().as_millis();
    println!("{w}x{h} native: clicks {out:?} ms, drag {td} ms, 200 px click {tb} ms");
}
