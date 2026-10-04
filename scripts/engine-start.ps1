<#
.SYNOPSIS
  Start the loom2 inference engine: the pinned headless ComfyUI (engine/comfyui) in the engine venv.
.DESCRIPTION
  Flags follow 06 §3b / 04 §2 (D13): loopback only, no browser, PyTorch SDPA attention, no pinned memory,
  loom2 model mounts via engine/extra_model_paths.yaml, outputs under engine/comfyui_out (gitignored).
  ComfyUI is used for model and inference management only (D15); its UI is never opened.
.PARAMETER Port       TCP port on 127.0.0.1 (default 8188).
.PARAMETER LowVram    Add --lowvram (ComfyUI's aggressive offload) if dev FLUX.2 refuses to fit.
.PARAMETER Extra      Additional raw ComfyUI arguments.
#>
param(
  [int]$Port = 8188,
  [switch]$LowVram,
  [string[]]$Extra = @()
)
$ErrorActionPreference = 'Stop'
$repo   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo 'engine\.venv\Scripts\python.exe'
$main   = Join-Path $repo 'engine\comfyui\main.py'
if (-not (Test-Path $python)) { throw "engine venv missing: $python (see 12 §1a)" }
if (-not (Test-Path $main))   { throw "ComfyUI checkout missing: $main (git submodule update --init)" }

foreach ($d in 'engine\comfyui_out','engine\comfyui_tmp','engine\comfyui_user') {
  New-Item -ItemType Directory -Force (Join-Path $repo $d) | Out-Null
}

$args = @(
  $main,
  '--listen', '127.0.0.1',
  '--port', "$Port",
  '--disable-auto-launch',
  '--use-pytorch-cross-attention',
  '--disable-pinned-memory',
  '--preview-method', 'none',
  '--log-stdout',
  '--extra-model-paths-config', (Join-Path $repo 'engine\extra_model_paths.yaml'),
  '--output-directory', (Join-Path $repo 'engine\comfyui_out'),
  '--temp-directory',   (Join-Path $repo 'engine\comfyui_tmp'),
  '--user-directory',   (Join-Path $repo 'engine\comfyui_user')
)
if ($LowVram) { $args += '--lowvram' }
$args += $Extra

# Keep the engine process confined to this repo's ComfyUI checkout.
Set-Location (Join-Path $repo 'engine\comfyui')
Write-Host "[loom2] engine: $python $($args -join ' ')"
& $python @args
