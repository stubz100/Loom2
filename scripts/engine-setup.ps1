<#
.SYNOPSIS
  Recreate the loom2 inference engine environment from the pinned sources (06 §3b, 12 §1a, D15/D16).
.DESCRIPTION
  1. engine/comfyui submodule at its pinned commit (Comfy-Org/ComfyUI v0.38.2)
  2. custom nodes at the commits recorded in engine/nodes.lock, plus the local patches in engine/patches/
  3. engine/.venv via uv on Python 3.13 with torch 2.13.0+rocm10.0.0 (AMD stable index, [device-all] extras)
     and ComfyUI's requirements under engine/constraints.txt (torch can never be swapped for a CPU build)
  Nothing here touches PATH, the system Python, or any other venv. Re-runnable; skips what already exists.
.PARAMETER SkipTorch   Do not (re)install torch — only refresh ComfyUI/node requirements.
#>
param([switch]$SkipTorch)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:UV_HTTP_TIMEOUT = '900'
$amdIndex = 'https://stable.repo.amd.com/rocm/whl-next/'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required: irm https://astral.sh/uv/install.ps1 | iex" }

Write-Host "[setup] 1/4 ComfyUI submodule"
git submodule update --init --depth 1 engine/comfyui
Push-Location engine/comfyui; Write-Host "       ComfyUI $(git log -1 --format='%h %ad' --date=short)"; Pop-Location

Write-Host "[setup] 2/4 custom nodes from engine/nodes.lock"
$nodes = Get-Content engine/nodes.lock | Where-Object { $_ -match '^\S+\s+https?://\S+\s+[0-9a-f]{7,}\s' }
foreach ($line in $nodes) {
  $name, $url, $commit = ($line -split '\s+')[0..2]
  $dest = "engine/comfyui/custom_nodes/$name"
  if (-not (Test-Path "$dest/.git")) {
    git clone --quiet $url $dest
  }
  Push-Location $dest
  git fetch --quiet --depth 1 origin $commit 2>$null; git checkout --quiet $commit
  Pop-Location
  Write-Host "       $name @ $commit"
}
$patches = Get-Content engine/nodes.lock | Where-Object { $_ -match '^\S+\s+patch\s+\S+' }
foreach ($line in $patches) {
  $name, $_, $file = ($line -split '\s+')[0..2]
  $dest = "engine/comfyui/custom_nodes/$name"
  $patch = Join-Path $repo "engine/patches/$file"
  Push-Location $dest
  git apply --check $patch 2>$null
  if ($LASTEXITCODE -eq 0) { git apply $patch; Write-Host "       patched $name with $file" }
  else { git apply --reverse --check $patch 2>$null; if ($LASTEXITCODE -eq 0) { Write-Host "       $file already applied to $name" } else { throw "patch $file does not apply to $name" } }
  Pop-Location
}

Write-Host "[setup] 3/4 engine venv (uv, Python 3.13)"
if (-not (Test-Path engine/.venv)) { uv venv engine/.venv --python 3.13 }
if (-not $SkipTorch) {
  uv pip install --python engine/.venv --index $amdIndex `
    'torch[device-all]==2.13.0+rocm10.0.0' 'torchvision[device-all]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
}

Write-Host "[setup] 4/4 ComfyUI + node requirements under constraints"
$reqs = @('-r', 'engine/comfyui/requirements.txt')
Get-ChildItem engine/comfyui/custom_nodes -Directory | ForEach-Object {
  $r = Join-Path $_.FullName 'requirements.txt'; if (Test-Path $r) { $reqs += @('-r', $r) }
}
uv pip install --python engine/.venv -c engine/constraints.txt --index $amdIndex @reqs
uv pip install --python engine/.venv websocket-client

& engine/.venv/Scripts/python.exe -c "import torch; print('[setup] torch', torch.__version__, '| hip', torch.version.hip, '| device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"
Write-Host "[setup] done. Start the engine with scripts/engine-start.ps1"
