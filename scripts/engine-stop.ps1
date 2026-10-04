<#
.SYNOPSIS
  Stop the loom2 inference engine (the headless ComfyUI started by engine-start.ps1) and wait for its port to close.
.PARAMETER Port  TCP port the engine listens on (default 8188).
#>
param([int]$Port = 8188)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$marker = (Join-Path $repo 'engine\comfyui\main.py')
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like "*$marker*" }
if (-not $procs) { Write-Host "[loom2] engine not running"; exit 0 }
foreach ($p in $procs) {
  Write-Host "[loom2] stopping engine pid $($p.ProcessId)"
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
  $open = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $open) { Write-Host "[loom2] engine stopped, port $Port free"; exit 0 }
  Start-Sleep -Milliseconds 500
}
Write-Warning "[loom2] port $Port still listening after 30 s"
exit 1
