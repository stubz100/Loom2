<#
.SYNOPSIS
  Sets up the LoRA trainer (18 §2 E16a, D86): ai-toolkit as the pinned submodule trainers/ai-toolkit, its own venv trainers/.venv
  on Python 3.12 with the engine's ROCm torch wheels, the requirements filtered for Windows ROCm under trainers/constraints.txt,
  and the loom2 patches from trainers/patches/ applied inside the submodule. The engine venv is never touched.
  1. git submodule update --init trainers/ai-toolkit (at the pin recorded in .gitmodules / the superproject)
  2. trainers/.venv via uv on Python 3.12 (ai-toolkit pins scipy 1.12, which has no 3.13 wheel) with torch 2.13.0+rocm10.0.0
     from the AMD index ([device-all] extras, as engine-setup.ps1)
  3. ai-toolkit's requirements minus bitsandbytes / torchcodec, under trainers/constraints.txt (torchao kept: E16d's layer offloading)
  4. trainers/patches/*.patch applied with git apply (skipped when already applied)
  Re-runnable; skips what already exists. Nothing here touches PATH, the system Python, or any other venv.
.PARAMETER SkipTorch   Do not (re)install torch — only refresh the requirements and the patches.
#>
param([switch]$SkipTorch)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$amdIndex = 'https://stable.repo.amd.com/rocm/whl-next/'

Write-Host "[trainer] 1/4 ai-toolkit submodule"
git submodule update --init trainers/ai-toolkit
if ($LASTEXITCODE -ne 0) { throw "submodule update failed" }

Write-Host "[trainer] 2/4 trainers venv (uv, Python 3.12)"
if (-not (Test-Path trainers/.venv)) { uv venv trainers/.venv --python 3.12 }
if (-not $SkipTorch) {
  uv pip install --python trainers/.venv --index $amdIndex `
    'torch[device-all]==2.13.0+rocm10.0.0' 'torchvision[device-all]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
}

Write-Host "[trainer] 3/4 ai-toolkit requirements under trainers/constraints.txt (no bitsandbytes / torchcodec)"
# torchao stays: its pure-Python wheel imports on the ROCm torch and layer_offloading (the 9B base, E16d) needs its float8 qtype
$drop = '^(bitsandbytes|torchcodec)\b'
$lines = Get-Content trainers/ai-toolkit/requirements_base.txt | Where-Object { $_ -notmatch $drop }
$lines += Get-Content trainers/ai-toolkit/requirements.txt | Where-Object { $_ -notmatch '^-r ' -and $_ -notmatch $drop }
$filtered = Join-Path $env:TEMP 'loom2-trainer-requirements.txt'
Set-Content -Path $filtered -Value $lines -Encoding utf8
# unsafe-best-match: the AMD index carries a numpy of its own; the pinned 1.26.4 (and most of the list) comes from PyPI, torch stays the ROCm build by the constraint
uv pip install --python trainers/.venv --index-strategy unsafe-best-match -c trainers/constraints.txt --index $amdIndex -r $filtered
if ($LASTEXITCODE -ne 0) { throw "requirements install failed" }

Write-Host "[trainer] 4/4 loom2 patches"
Get-ChildItem trainers/patches -Filter *.patch -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
  $patch = $_.FullName
  Push-Location trainers/ai-toolkit
  $ErrorActionPreference = 'SilentlyContinue'
  git apply --check $patch 2>$null
  $ErrorActionPreference = 'Stop'
  if ($LASTEXITCODE -eq 0) { git apply $patch; Write-Host "       patched with $($_.Name)" }
  else {
    $ErrorActionPreference = 'SilentlyContinue'; git apply --reverse --check $patch 2>$null; $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -eq 0) { Write-Host "       $($_.Name) already applied" } else { Pop-Location; throw "patch $($_.Name) does not apply" }
  }
  Pop-Location
}

& trainers/.venv/Scripts/python.exe -c "import torch; print('[trainer] torch', torch.__version__, '| hip', torch.version.hip, '| device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"
Write-Host "[trainer] done. The orchestrator runs trainers/loom2_train.py with trainers/.venv/Scripts/python.exe"
