<#
.SYNOPSIS
  E0 A/B reference: render bench prompts with loom's proven torch worker (Engine B) in loom's untouched 7.2.1 venv,
  so the ComfyUI engine numbers have a measured baseline on this rig (12 §1a sanity matrix, last row).
.NOTES
  Uses the worker's --jobs-file batch mode (prompt read from a file: no shell quoting of JSON — Windows PowerShell
  5.1 mangles quoted native arguments, which broke the first attempt). loom's vendored multistack is module-invoked
  from its src/ root; Comfy-Org quantised dev split files load via loom's scaled_fp8 loader; HF cache offline.
  Nothing in loom is modified.
#>
param(
  [string]$PromptFile = 'F:\source\repos\stubz003_loom2\bench\t2i\01-alley-rain.json',
  [int]$Width = 960, [int]$Height = 544, [int]$Steps = 20, [double]$Guidance = 4.0, [int[]]$Seeds = @(20261004, 20261005),
  [switch]$Turbo
)
$ErrorActionPreference = 'Stop'
$loomPy = 'F:\source\repos\stubz-002-tripo-sf\.venv\Scripts\python.exe'
$src    = 'F:\source\repos\stubz-002-tripo-sf\loom\loom-loreweave-studio\pipelines\multistack\src'
$outDir = 'F:\source\repos\stubz003_loom2\engine\spikes\out\loom-ab'
New-Item -ItemType Directory -Force $outDir | Out-Null
$prompt = (Get-Content $PromptFile -Raw | ConvertFrom-Json | ConvertTo-Json -Compress -Depth 10)
$spec = @{
  shared = @{ mode = 't2i'; model_name = 'flux.2-dev'; num_steps = $Steps; guidance = $Guidance; width = $Width; height = $Height;
              device = 'cuda'; fp8_matmul = 'auto'; turbo = [bool]$Turbo }
  items  = @($Seeds | ForEach-Object { @{ prompt = $prompt; seed = $_ } })
}
$jobs = Join-Path $outDir 'jobs.json'
$spec | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $jobs
$env:HF_HOME = 'F:\HF_HOME'; $env:HF_HUB_OFFLINE = '1'; $env:MIOPEN_FIND_MODE = '2'; $env:PYTHONUNBUFFERED = '1'
Set-Location $src
Write-Host "[loom A/B] start $(Get-Date -Format 'HH:mm:ss')  steps=$Steps size=${Width}x${Height} turbo=$Turbo seeds=$($Seeds -join ',')"
$sw = [Diagnostics.Stopwatch]::StartNew()
& $loomPy -m pipeline.flux2.run_pipeline --jobs-file $jobs --output-dir $outDir --device cuda
$sw.Stop()
Write-Host "[loom A/B] end $(Get-Date -Format 'HH:mm:ss')  wall $([math]::Round($sw.Elapsed.TotalSeconds,1)) s  exit $LASTEXITCODE"
Get-ChildItem $outDir -Filter *.png | Sort-Object LastWriteTime | ForEach-Object { "[loom A/B] output $($_.FullName)" }
