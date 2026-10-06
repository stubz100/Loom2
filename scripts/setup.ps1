<#
.SYNOPSIS
  Set up a loom2 checkout on a Windows machine: both Python environments, the frontend, the engine checkout, the small
  tool weights (12 §8 M7 "installer script"; 06 §3b D15/D16).
.DESCRIPTION
  1. orchestrator/.venv via uv (Python 3.13, torch-free): pyproject + uv.lock, with the dev extras
  2. frontend: npm ci (Vite 8, React 19, Tauri CLI)
  3. engine: scripts/engine-setup.ps1 (ComfyUI submodule at its pin, custom nodes from nodes.lock, engine/.venv with
     torch ROCm from the AMD stable index) — skip with -SkipEngine on a machine without the GPU
  4. FaceSim weights (InsightFace buffalo_l, 275 MB) into <models_root>/insightface — skip with -SkipWeights
  Model weights for generation are fetched from the Models suite (or scripts/fetch_weights.py) — never here.
  Re-runnable; every step skips what already exists. Nothing touches PATH or the system Python.
.EXAMPLE
  scripts/setup.ps1                 # everything
  scripts/setup.ps1 -SkipEngine     # a dev machine without the RX 9070 XT (offline tests, frontend, UI work)
#>
param([switch]$SkipEngine, [switch]$SkipWeights, [string]$ModelsRoot)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Need($name, $hint) { if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "$name is required: $hint" } }
Need uv   "irm https://astral.sh/uv/install.ps1 | iex"
Need node "Node 22 — https://nodejs.org"
Need npm  "comes with Node"
if (-not $SkipEngine) { Need git "https://git-scm.com (the engine is a git submodule)" }

Write-Host "[setup] 1/4 orchestrator venv (uv, Python 3.13)"
uv sync --project orchestrator --extra dev
& "$repo\orchestrator\.venv\Scripts\python.exe" -c "import loom2, onnxruntime, av; print('       loom2 ok · onnxruntime', onnxruntime.__version__, '· PyAV', av.__version__)"

Write-Host "[setup] 2/4 frontend (npm ci)"
Push-Location frontend
if (Test-Path node_modules) { Write-Host "       node_modules present — npm ci refreshes it from package-lock" }
npm ci
Pop-Location

if ($SkipEngine) { Write-Host "[setup] 3/4 engine skipped (-SkipEngine)" }
else {
  Write-Host "[setup] 3/4 engine (ComfyUI pin + ROCm torch venv) — scripts/engine-setup.ps1"
  & "$repo\scripts\engine-setup.ps1"
}

if ($SkipWeights) { Write-Host "[setup] 4/4 FaceSim weights skipped (-SkipWeights)" }
else {
  Write-Host "[setup] 4/4 FaceSim weights (InsightFace buffalo_l)"
  $args = @("$repo\scripts\fetch_facesim.py"); if ($ModelsRoot) { $args += @("--models-root", $ModelsRoot) }
  & "$repo\orchestrator\.venv\Scripts\python.exe" @args
}

Write-Host ""
Write-Host "[setup] done. Next:"
Write-Host "  scripts/dev.ps1              # the app (Tauri shell → orchestrator → engine on the first job)"
Write-Host "  scripts/dev.ps1 -Browser     # orchestrator + Vite only, open the printed URL"
Write-Host "  Models suite → Fetch          # generation weights (or scripts/fetch_weights.py); the roster lists licences and sizes"
Write-Host "  orchestrator/.venv/Scripts/python.exe -m pytest orchestrator -q --timeout 120   # offline tests"
