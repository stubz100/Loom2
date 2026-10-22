"""loom2's lip-sync runner (D118 AE4d, from spike E29b's L3a): LatentSync 1.5 in `tools/lipsync/.venv` (scripts/lipsync-setup.ps1) on the
face pass's rendered head clip — never the engine venv, and the engine stopped while it runs (one job on the card, D97).

    python tools/lipsync/sync.py <request.json>

The request: checkout (the LatentSync checkout the weights live in), video (the head clip, an mp4 at 25 fps), audio (the lines over
the shot, a WAV), out (the mp4 to write), steps, guidance, seed, result (the JSON to write). Prints one line per stage for the job
card; the result records the seconds. LatentSync's own `scripts/inference.py` does the work (its `main(config, args)`); the venv's
Scripts folder goes first on PATH for the ffmpeg the code calls by name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def say(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str]) -> int:
    req = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    checkout = Path(req["checkout"]).resolve()
    if not (checkout / "scripts" / "inference.py").is_file():
        say(f"no LatentSync checkout at {checkout} — run scripts/lipsync-setup.ps1")
        return 2
    os.chdir(checkout)                                                  # the code reads configs/ and checkpoints/ relative to its root
    sys.path.insert(0, str(checkout))
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    t0 = time.time()
    say("loading LatentSync 1.5 (the U-Net, whisper tiny, the VAE, insightface on the CPU)")
    from omegaconf import OmegaConf
    from scripts.inference import main as infer
    reused = patch_face_fallback()
    config = OmegaConf.load("configs/unet/stage2.yaml")
    args = argparse.Namespace(unet_config_path="configs/unet/stage2.yaml", inference_ckpt_path="checkpoints/latentsync_unet.pt", video_path=str(req["video"]),
                              audio_path=str(req["audio"]), video_out_path=str(req["out"]), inference_steps=int(req.get("steps") or 20),
                              guidance_scale=float(req.get("guidance") or 1.5), temp_dir=str(req.get("temp_dir") or "temp"), seed=int(req.get("seed") or 1247),
                              enable_deepcache=False)
    say(f"syncing {Path(args.video_path).name} to {Path(args.audio_path).name}: {args.inference_steps} steps, guidance {args.guidance_scale}")
    infer(config, args)
    seconds = round(time.time() - t0, 1)
    out = Path(args.video_out_path)
    if not out.is_file():
        say("the model wrote no video")
        return 1
    if reused["frames"]:
        say(f"{reused['frames']} frame(s) without a detectable face took the last face's geometry (a head turned away)")
    if req.get("result"):
        Path(req["result"]).write_text(json.dumps({"seconds": seconds, "out": str(out), "bytes": out.stat().st_size, "reused_face_frames": reused["frames"]}), encoding="utf-8")
    say(f"done in {seconds} s")
    return 0


def patch_face_fallback() -> dict:
    """LatentSync stops at the first frame its detector finds no face in (a head turned away: rig 2026-10-22, 11 of 127 frames). The tool
    carries on instead: such a frame takes the last detected face's three landmarks (the eyebrows and the nose) for its warp, so the
    mouth is redrawn at the last geometry and the clip keeps its length; the count goes to the job's log. The first frame must have a
    face. Returns the counter the patched method fills."""
    import cv2
    import numpy as np
    import torch
    from einops import rearrange
    from latentsync.utils import image_processor as ip
    counter = {"frames": 0}

    def affine_transform(self, image):
        if self.face_detector is None:
            raise NotImplementedError("Using the CPU for face detection is not supported")
        bbox, landmark_2d_106 = self.face_detector(image)
        if bbox is None:
            last = getattr(self, "_loom2_last_landmarks", None)
            if last is None:
                raise RuntimeError("Face not detected in the first frame")
            landmarks3 = last
            counter["frames"] += 1
        else:
            pt_left_eye = np.mean(landmark_2d_106[[43, 48, 49, 51, 50]], axis=0)
            pt_right_eye = np.mean(landmark_2d_106[101:106], axis=0)
            pt_nose = np.mean(landmark_2d_106[[74, 77, 83, 86]], axis=0)
            landmarks3 = np.round([pt_left_eye, pt_right_eye, pt_nose])
            self._loom2_last_landmarks = landmarks3
        face, affine_matrix = self.restorer.align_warp_face(image.copy(), landmarks3=landmarks3, smooth=True)
        box = [0, 0, face.shape[1], face.shape[0]]
        face = cv2.resize(face, (self.resolution, self.resolution), interpolation=cv2.INTER_LANCZOS4)
        face = rearrange(torch.from_numpy(face), "h w c -> c h w")
        return face, box, affine_matrix
    ip.ImageProcessor.affine_transform = affine_transform
    return counter


if __name__ == "__main__":
    sys.exit(main(sys.argv))
