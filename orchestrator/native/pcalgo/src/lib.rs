//! S1 spike: PhotoCraft's content-aware fill and PatchMatch completion for the loom2 orchestrator, over numpy arrays.
//! Kernels: photocraft-algo (MIT OR Apache-2.0, Copyright (c) 2026 ArtCraft Team and the PhotoCraft contributors).

use numpy::{IntoPyArray, PyArray3, PyReadonlyArray2, PyReadonlyArray3, PyUntypedArrayMethods};
use photocraft_algo::content_aware::{fill, FillOptions};
use photocraft_algo::inpaint::{complete, CompleteParams};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

fn shape3(img: &PyReadonlyArray3<f32>) -> (usize, usize, usize) {
    let s = img.shape();
    (s[0], s[1], s[2])
}

/// Content-Aware Fill: `img` H×W×C float32 (0–1), `hole` H×W bool; `source` (H×W bool, optional) limits where patches come from.
/// Returns the filled image (unchanged outside the hole).
#[pyfunction]
#[pyo3(signature = (img, hole, source=None, color_adaptation=0.35, seed=1))]
fn content_aware_fill<'py>(py: Python<'py>, img: PyReadonlyArray3<'py, f32>, hole: PyReadonlyArray2<'py, bool>, source: Option<PyReadonlyArray2<'py, bool>>,
                           color_adaptation: f32, seed: u64) -> PyResult<Bound<'py, PyArray3<f32>>> {
    let (h, w, ch) = shape3(&img);
    let hole_v: Vec<bool> = hole.as_array().iter().copied().collect();
    if hole_v.len() != w * h {
        return Err(PyValueError::new_err("hole must be H×W"));
    }
    let src_v: Vec<bool> = match &source {
        Some(s) => s.as_array().iter().copied().collect(),
        None => hole_v.iter().map(|x| !x).collect(),
    };
    let data: Vec<f32> = img.as_array().iter().copied().collect();
    let opts = FillOptions { color_adaptation, seed, ..FillOptions::default() };
    let out = py.detach(|| fill(w, h, ch, &data, &hole_v, &src_v, &opts));
    Ok(numpy::ndarray::Array3::from_shape_vec((h, w, ch), out).map_err(|e| PyValueError::new_err(e.to_string()))?.into_pyarray(py))
}

/// PatchMatch / Wexler EM completion of `hole` from the rest of the image (the Spot Healing core).
#[pyfunction]
#[pyo3(signature = (img, hole, seed=1))]
fn complete_hole<'py>(py: Python<'py>, img: PyReadonlyArray3<'py, f32>, hole: PyReadonlyArray2<'py, bool>, seed: u64) -> PyResult<Bound<'py, PyArray3<f32>>> {
    let (h, w, ch) = shape3(&img);
    let hole_v: Vec<bool> = hole.as_array().iter().copied().collect();
    let data: Vec<f32> = img.as_array().iter().copied().collect();
    let p = CompleteParams { seed, ..CompleteParams::default() };
    let out = py.detach(|| complete(w, h, ch, &data, &hole_v, &p)).ok_or_else(|| PyValueError::new_err("nothing to sample from"))?;
    Ok(numpy::ndarray::Array3::from_shape_vec((h, w, ch), out).map_err(|e| PyValueError::new_err(e.to_string()))?.into_pyarray(py))
}

#[pymodule]
fn loom2_pcalgo(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(content_aware_fill, m)?)?;
    m.add_function(wrap_pyfunction!(complete_hole, m)?)?;
    Ok(())
}
