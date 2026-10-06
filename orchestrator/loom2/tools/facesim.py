"""FaceSim identity advisory (11 §6, 11 §11 item 6): ArcFace cosine similarity between the face in a clip's start frame and
the faces found in its frames, on the CPU through ONNX Runtime with InsightFace's `buffalo_l` pair — SCRFD `det_10g`
(detector with 5 landmarks) and `w600k_r50` (512-d ArcFace). Advisory only: a number in the Clip inspector, never a gate.
Weights: scripts/fetch_facesim.py → <models_root>/insightface/buffalo_l/. E4 measured 0.578 across a Wan clip of the
bench character; same-person frames typically land at 0.45–0.7, different people below 0.3.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

DET_NAME, REC_NAME = "det_10g.onnx", "w600k_r50.onnx"
DET_SIZE = 640
# ArcFace's 112×112 landmark template (left eye, right eye, nose, mouth left, mouth right)
ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


def weights_dir(models_root: Path | str) -> Path:
    return Path(models_root) / "insightface" / "buffalo_l"


def available(models_root: Path | str) -> bool:
    d = weights_dir(models_root)
    return (d / DET_NAME).is_file() and (d / REC_NAME).is_file()


@dataclass
class Face:
    bbox: np.ndarray            # x1, y1, x2, y2 in image pixels
    kps: np.ndarray             # (5, 2)
    score: float

    @property
    def area(self) -> float:
        return float(max(0.0, self.bbox[2] - self.bbox[0]) * max(0.0, self.bbox[3] - self.bbox[1]))


# ---- geometry (pure numpy, unit-tested without weights) -------------------------------------------------------------
def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    return np.stack([points[:, 0] - distance[:, 0], points[:, 1] - distance[:, 1], points[:, 0] + distance[:, 2], points[:, 1] + distance[:, 3]], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    out = []
    for i in range(0, distance.shape[1], 2):
        out.append(points[:, 0] + distance[:, i])
        out.append(points[:, 1] + distance[:, i + 1])
    return np.stack(out, axis=-1)


def nms(dets: np.ndarray, thresh: float = 0.4) -> list[int]:
    """dets: (N, 5) x1 y1 x2 y2 score, sorted by score desc; returns kept indices."""
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]]); yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]]); yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= thresh]
    return keep


def umeyama(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Similarity transform (rotation, uniform scale, translation) mapping src points onto dst — Umeyama 1991. Returns 2×3."""
    n = src.shape[0]
    mu_s, mu_d = src.mean(0), dst.mean(0)
    sc, dc = src - mu_s, dst - mu_d
    cov = dc.T @ sc / n
    u, s, vt = np.linalg.svd(cov)
    d = np.ones(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[1] = -1
    r = u @ np.diag(d) @ vt
    var_s = (sc ** 2).sum() / n
    scale = (s * d).sum() / max(var_s, 1e-12)
    t = mu_d - scale * r @ mu_s
    m = np.zeros((2, 3), dtype=np.float64)
    m[:, :2] = scale * r
    m[:, 2] = t
    return m


def warp_face(img: np.ndarray, kps: np.ndarray, size: int = 112) -> np.ndarray:
    """Align the face to ArcFace's template: PIL's affine takes the inverse map (output → input)."""
    m = umeyama(kps.astype(np.float64), ARCFACE_DST.astype(np.float64))
    full = np.vstack([m, [0, 0, 1]])
    inv = np.linalg.inv(full)
    out = Image.fromarray(img).transform((size, size), Image.Transform.AFFINE, data=tuple(inv[:2].flatten()), resample=Image.Resampling.BICUBIC)
    return np.asarray(out)


# ---- the models ------------------------------------------------------------------------------------------------------
class FaceSim:
    def __init__(self, models_root: Path | str) -> None:
        import onnxruntime as ort

        d = weights_dir(models_root)
        if not available(models_root):
            raise FileNotFoundError(f"FaceSim weights missing in {d} (scripts/fetch_facesim.py)")
        so = ort.SessionOptions()
        so.intra_op_num_threads = 4
        self.det = ort.InferenceSession(str(d / DET_NAME), so, providers=["CPUExecutionProvider"])
        self.rec = ort.InferenceSession(str(d / REC_NAME), so, providers=["CPUExecutionProvider"])
        self.det_in = self.det.get_inputs()[0].name
        self.rec_in = self.rec.get_inputs()[0].name

    def detect(self, img: np.ndarray, thresh: float = 0.5) -> list[Face]:
        """SCRFD on a 640×640 letterbox (longest side scaled, padding bottom/right); faces sorted by area, largest first."""
        h, w = img.shape[:2]
        scale = DET_SIZE / max(h, w)
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        resized = np.asarray(Image.fromarray(img).resize((nw, nh), Image.Resampling.BILINEAR))
        canvas = np.zeros((DET_SIZE, DET_SIZE, 3), dtype=np.uint8)
        canvas[:nh, :nw] = resized
        blob = ((canvas.astype(np.float32) - 127.5) / 128.0).transpose(2, 0, 1)[None]
        outs = [np.asarray(o) for o in self.det.run(None, {self.det_in: blob})]
        outs = [o[0] if o.ndim == 3 else o for o in outs]
        strides, fmc, na = (8, 16, 32), 3, 2
        scores_l, boxes_l, kps_l = [], [], []
        for idx, stride in enumerate(strides):
            scores = outs[idx].reshape(-1)
            bbox_pred = outs[idx + fmc] * stride
            kps_pred = outs[idx + fmc * 2] * stride
            hh, ww = DET_SIZE // stride, DET_SIZE // stride
            centers = np.stack(np.mgrid[:hh, :ww][::-1], axis=-1).astype(np.float32).reshape(-1, 2) * stride
            centers = np.stack([centers] * na, axis=1).reshape(-1, 2)
            pos = np.where(scores >= thresh)[0]
            if not pos.size:
                continue
            scores_l.append(scores[pos])
            boxes_l.append(distance2bbox(centers, bbox_pred)[pos] / scale)
            kps_l.append(distance2kps(centers, kps_pred)[pos] / scale)
        if not scores_l:
            return []
        scores = np.concatenate(scores_l); boxes = np.concatenate(boxes_l); kps = np.concatenate(kps_l)
        order = scores.argsort()[::-1]
        dets = np.hstack([boxes[order], scores[order, None]]).astype(np.float32)
        keep = nms(dets, 0.4)
        faces = [Face(bbox=dets[k, :4], kps=kps[order][k].reshape(5, 2), score=float(dets[k, 4])) for k in keep]
        faces.sort(key=lambda f: -f.area)
        return faces

    def embed(self, img: np.ndarray, kps: np.ndarray) -> np.ndarray:
        face = warp_face(img, kps)
        blob = ((face.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
        emb = np.asarray(self.rec.run(None, {self.rec_in: blob})[0])[0].astype(np.float64)
        return emb / max(1e-12, float(np.linalg.norm(emb)))

    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))


def clip_identity(fs: FaceSim, reference: np.ndarray, frames: list[Path], samples: int = 12) -> dict[str, Any]:
    """Cosine similarity of the largest face in `reference` to the best-matching face in ≤ `samples` evenly spaced frames."""
    ref_faces = fs.detect(reference)
    if not ref_faces:
        return {"status": "no face in the reference frame", "sampled": 0, "with_face": 0}
    ref = fs.embed(reference, ref_faces[0].kps)
    n = len(frames)
    idx = sorted({int(round(i * (n - 1) / max(1, samples - 1))) for i in range(min(samples, n))}) if n else []
    per: list[dict[str, Any]] = []
    for i in idx:
        img = np.asarray(Image.open(frames[i]).convert("RGB"))
        faces = fs.detect(img)
        if not faces:
            per.append({"frame": i, "sim": None, "faces": 0})
            continue
        best = max(fs.similarity(ref, fs.embed(img, f.kps)) for f in faces[:3])
        per.append({"frame": i, "sim": round(best, 3), "faces": len(faces)})
    sims = [(p["sim"], p["frame"]) for p in per if p["sim"] is not None]
    if not sims:
        return {"status": "no face found in the sampled frames", "sampled": len(idx), "with_face": 0, "per_frame": per}
    vals = [s for s, _ in sims]
    lo = min(sims, key=lambda x: x[0])
    return {"status": "ok", "reference_faces": len(ref_faces), "sampled": len(idx), "with_face": len(sims), "mean": round(float(np.mean(vals)), 3),
            "min": round(lo[0], 3), "min_frame": lo[1], "per_frame": per, "model": "buffalo_l · w600k_r50 (ArcFace) · det_10g (SCRFD)",
            "scale": "cosine; same person across a clip ≈ 0.45–0.7 (E4: 0.578), different people < 0.3"}
