<#
.SYNOPSIS
  Sets up the lip-sync model as a tool (D118 AE4d, from spike E29b): LatentSync 1.5 in its own venv tools/lipsync/.venv on Python 3.11
  with the engine's ROCm torch wheels, the checkout tools/lipsync/LatentSync at the pinned commit, and the 1.5 weights under its
  checkpoints/. The code is Apache-2.0; the 1.5 weights are OpenRAIL++ — the tool is offered under the `full` variant only (D26).
  A venv of its own: the model wants Python 3.11 (decord has no 3.12 wheel) and pins diffusers / transformers the other venvs do not.
  1. tools/lipsync/LatentSync — git clone at the pin (shallow), the face detector's ONNX provider patched to the CPU
  2. tools/lipsync/.venv via uv on Python 3.11 with torch 2.13.0+rocm10.0.0 from the AMD index (as voices-setup.ps1)
  3. the requirements minus torch, the CUDA ONNX runtime (the CPU one instead), gradio, lpips, scenedetect — under tools/lipsync/constraints.txt
  4. ffmpeg from imageio-ffmpeg beside the venv's python (the code calls `ffmpeg` by name)
  5. the weights: copied from engine/spikes/third_party/LatentSync/checkpoints when the spike's checkout is there, else fetched from the hub
     (ByteDance/LatentSync-1.5: the U-Net, config, whisper tiny, insightface buffalo_l, face-alignment's files; no syncnet, no eval models)
  6. the SD VAE (stabilityai/sd-vae-ft-mse, MIT) into HF_HOME
  Re-runnable; skips what already exists.
.PARAMETER SkipTorch   Do not (re)install torch — only refresh the packages.
#>
param([switch]$SkipTorch)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$amdIndex = 'https://stable.repo.amd.com/rocm/whl-next/'
$pin = 'a229c3948406bc2cf6eaf4873e662e70c6a04746'
$dir = Join-Path $repo 'tools\lipsync'
$checkout = Join-Path $dir 'LatentSync'
$venv = Join-Path $dir '.venv'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not $env:HF_HOME) { $env:HF_HOME = 'F:/HF_HOME' }

Write-Host "[lipsync] 1/6 the checkout at $pin"
if (-not (Test-Path (Join-Path $checkout 'scripts\inference.py'))) {
  git clone --filter=blob:none https://github.com/bytedance/LatentSync.git $checkout
  git -C $checkout checkout --quiet $pin
}
$fd = Join-Path $checkout 'latentsync\utils\face_detector.py'
(Get-Content $fd -Raw) -replace 'providers=\["CUDAExecutionProvider"\]', 'providers=["CPUExecutionProvider"]' | Set-Content $fd -NoNewline

Write-Host "[lipsync] 2/6 the venv (uv, Python 3.11)"
if (-not (Test-Path $venv)) { uv venv $venv --python 3.11 }
if (-not $SkipTorch) {
  uv pip install --python $venv --index $amdIndex `
    'torch[device-all]==2.13.0+rocm10.0.0' 'torchvision[device-all]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
}

Write-Host "[lipsync] 3/6 the requirements under tools/lipsync/constraints.txt"
uv pip install --python $venv --index-strategy unsafe-best-match -c (Join-Path $dir 'constraints.txt') --index $amdIndex `
  'diffusers==0.32.2' 'transformers==4.48.0' 'decord==0.6.0' 'accelerate==0.26.1' 'einops==0.7.0' 'omegaconf==2.3.0' 'opencv-python==4.9.0.80' `
  'mediapipe==0.10.11' 'python_speech_features==0.6' 'librosa==0.10.1' 'ffmpeg-python==0.2.0' 'imageio==2.31.1' 'imageio-ffmpeg==0.5.1' `
  'face-alignment==1.4.1' 'huggingface-hub==0.30.2' 'numpy==1.26.4' 'kornia==0.8.0' 'insightface==0.7.3' 'onnxruntime==1.21.0' 'DeepCache==0.1.1'
if ($LASTEXITCODE -ne 0) { throw "lip-sync packages install failed" }

Write-Host "[lipsync] 4/6 ffmpeg beside the venv's python"
$ff = Join-Path $venv 'Scripts\ffmpeg.exe'
if (-not (Test-Path $ff)) {
  $src = & $py -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
  Copy-Item $src $ff
}

Write-Host "[lipsync] 5/6 the weights (OpenRAIL++: full variant only)"
$ck = Join-Path $checkout 'checkpoints'
$spike = Join-Path $repo 'engine\spikes\third_party\LatentSync\checkpoints'
$files = @('latentsync_unet.pt', 'config.json', 'whisper/tiny.pt', 'auxiliary/2DFAN4-cd938726ad.zip', 'auxiliary/s3fd-619a316812.pth', 'auxiliary/sfd_face.pth',
           'auxiliary/models/buffalo_l/1k3d68.onnx', 'auxiliary/models/buffalo_l/2d106det.onnx', 'auxiliary/models/buffalo_l/det_10g.onnx',
           'auxiliary/models/buffalo_l/genderage.onnx', 'auxiliary/models/buffalo_l/w600k_r50.onnx')
foreach ($f in $files) {
  $dst = Join-Path $ck $f
  if (Test-Path $dst) { continue }
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  $from = Join-Path $spike $f
  if (Test-Path $from) { Copy-Item $from $dst; Write-Host "  copied $f from the spike's checkout" }
  else {
    & $py -c "import sys; from huggingface_hub import hf_hub_download; hf_hub_download('ByteDance/LatentSync-1.5', sys.argv[1], local_dir=sys.argv[2])" $f $ck   # V51: paths as argv, never spliced into the source
    if ($LASTEXITCODE -ne 0) { throw "fetch of $f failed" }
  }
}

Write-Host "[lipsync] 6/6 the SD VAE into HF_HOME"
& $py -c "from diffusers import AutoencoderKL; AutoencoderKL.from_pretrained('stabilityai/sd-vae-ft-mse'); print('[lipsync] sd-vae-ft-mse cached')"
if ($LASTEXITCODE -ne 0) { throw "the VAE fetch failed" }

& $py -c "import torch, diffusers, transformers, insightface, DeepCache; print('[lipsync] torch', torch.__version__, '| diffusers', diffusers.__version__, '| transformers', transformers.__version__)"
Write-Host "[lipsync] done. The orchestrator runs the mouth step with $py (Settings.lipsync)"
