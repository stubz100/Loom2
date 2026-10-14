<#
.SYNOPSIS
  Sets up the voice tools (19 §2 E20, D87): Kokoro (draft TTS, Apache-2.0) and Qwen3-TTS (cloning, Apache-2.0) in their own venv
  voices/.venv on Python 3.12 with the engine's ROCm torch wheels. A venv of their own because Qwen3-TTS pins transformers 4.x while
  ai-toolkit (trainers/.venv) pins 5.5.3 — the two cannot share one. The engine venv is never touched.
  1. voices/.venv via uv on Python 3.12 with torch 2.13.0+rocm10.0.0 from the AMD index ([device-all] extras, as engine-setup.ps1)
  2. kokoro + misaki[en] + soundfile + qwen-tts under voices/constraints.txt (torch pinned to the ROCm build)
  Re-runnable; skips what already exists. Models are fetched into HF_HOME on first use (Kokoro 0.3 GB, Qwen3-TTS-0.6B 2.3 GB).
.PARAMETER SkipTorch   Do not (re)install torch — only refresh the packages.
#>
param([switch]$SkipTorch)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$amdIndex = 'https://stable.repo.amd.com/rocm/whl-next/'

Write-Host "[voices] 1/2 voices venv (uv, Python 3.12)"
if (-not (Test-Path voices/.venv)) { uv venv voices/.venv --python 3.12 }
if (-not $SkipTorch) {
  uv pip install --python voices/.venv --index $amdIndex `
    'torch[device-all]==2.13.0+rocm10.0.0' 'torchvision[device-all]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
}

Write-Host "[voices] 2/2 kokoro + qwen-tts under voices/constraints.txt"
uv pip install --python voices/.venv --index-strategy unsafe-best-match -c voices/constraints.txt --index $amdIndex `
  kokoro 'misaki[en]' soundfile qwen-tts
if ($LASTEXITCODE -ne 0) { throw "voice packages install failed" }
# Kokoro's English G2P (misaki) wants spaCy's en_core_web_sm; spaCy fetches it through pip / uv, which need a venv marker and pip itself
uv pip install --python voices/.venv pip
$env:VIRTUAL_ENV = (Join-Path $repo 'voices\.venv')
& voices/.venv/Scripts/python.exe -m spacy download en_core_web_sm
if ($LASTEXITCODE -ne 0) { throw "spaCy en_core_web_sm install failed" }

& voices/.venv/Scripts/python.exe -c "import torch, kokoro, qwen_tts, transformers; print('[voices] torch', torch.__version__, '| kokoro', kokoro.__version__, '| transformers', transformers.__version__, '| device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"
Write-Host "[voices] done. The orchestrator runs the voice jobs with voices/.venv/Scripts/python.exe"
