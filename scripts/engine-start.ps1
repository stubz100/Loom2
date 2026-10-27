<#
.SYNOPSIS
  Start the loom2 inference engine by hand, exactly as loom2 starts it (the pinned headless ComfyUI in engine/.venv).
.DESCRIPTION
  V44: the launch comes from the orchestrator (python -m loom2.engine.supervisor --argv) — the same flags (06 §3b / 04 §2, D13),
  --reserve-vram and --vram-headroom from Settings, the model mounts written from Settings (V45) and the outputs under
  <state>/engine_out — so the app, which adopts an engine already listening on its port, finds every job's files where its
  finishers read them. ComfyUI is used for model and inference management only (D15); its UI is never opened.
  scripts/engine-stop.ps1 stops it; an adopted engine cannot be restarted from the app.
.PARAMETER State    The app state dir (default: $LOOM2_STATE or <repo>/.loom2_state — the orchestrator's own default).
.PARAMETER LowVram  Add --lowvram (ComfyUI's aggressive offload) if dev FLUX.2 refuses to fit.
.PARAMETER Extra    Additional raw ComfyUI arguments.
#>
param(
  [string]$State,
  [switch]$LowVram,
  [string[]]$Extra = @()
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$orch = Join-Path $repo 'orchestrator\.venv\Scripts\python.exe'
if (-not (Test-Path $orch)) { throw "orchestrator venv missing: $orch (scripts/setup.ps1)" }

$ask = @('-m', 'loom2.engine.supervisor', '--argv')
if ($State) { $ask += @('--state', $State) }
$launch = (& $orch @ask) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $launch) { throw "the orchestrator did not give the engine's launch (python -m loom2.engine.supervisor --argv)" }

$python = [string]$launch.argv[0]
$engineArgs = @($launch.argv | Select-Object -Skip 1)
if (-not (Test-Path $python)) { throw "engine venv missing: $python (see 12 §1a)" }
if (-not (Test-Path $engineArgs[0])) { throw "ComfyUI checkout missing: $($engineArgs[0]) (git submodule update --init)" }
if ($LowVram) { $engineArgs += '--lowvram' }
$engineArgs += $Extra
foreach ($v in $launch.env.PSObject.Properties) { Set-Item -Path "env:$($v.Name)" -Value $v.Value }

# Keep the engine process confined to this repo's ComfyUI checkout, as the supervisor does.
Set-Location $launch.cwd
Write-Host "[loom2] engine on 127.0.0.1:$($launch.port), state $($launch.state): $python $($engineArgs -join ' ')"
& $python @engineArgs
