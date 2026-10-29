# loom2 dev: one command for the whole stack. `npx tauri dev` runs the Vite dev server (beforeDevCommand),
# builds and opens the shell, and the shell spawns the orchestrator (which spawns the engine on the first job).
#   scripts/dev.ps1            # app
#   scripts/dev.ps1 -Browser   # orchestrator on 8766 with a fixed token + Vite only; open the printed URL in a browser
param([switch]$Browser, [string]$Suite)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if ($Suite) { $env:LOOM2_START_SUITE = $Suite }   # open the app on a suite's layer (catalogue: the Bin; generate, edit: World; animate, stage: Shots; models: the sheet)
if ($Browser) {
    $env:LOOM2_TOKEN = "devtoken"
    $env:PYTHONIOENCODING = "utf-8"
    $state = Join-Path $repo ".loom2_state"
    if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) {
        throw "[loom2] port 8766 is already listening: an earlier orchestrator is still up (stop it first, or the URL below would talk to it — V50)"
    }
    # V51: Start-Process joins the list with spaces and quotes nothing, so the state path is quoted here
    $orch = Start-Process -FilePath (Join-Path $repo "orchestrator\.venv\Scripts\python.exe") -ArgumentList @("-m", "loom2.main", "--port", "8766", "--state", ('"{0}"' -f $state)) `
        -WorkingDirectory (Join-Path $repo "orchestrator") -NoNewWindow -PassThru
    Write-Host "[loom2] orchestrator on http://127.0.0.1:8766 (token devtoken), pid $($orch.Id)"
    Write-Host "[loom2] open http://127.0.0.1:1420/?token=devtoken&port=8766  (add &suite=models to deep-link)"
    Set-Location (Join-Path $repo "frontend")
    try { npm run dev }
    finally {                                         # V50: the orchestrator does not outlive the Vite server it was started for
        if ($orch -and -not $orch.HasExited) { Stop-Process -Id $orch.Id -Force -ErrorAction SilentlyContinue; Write-Host "[loom2] orchestrator stopped" }
    }
} else {
    Set-Location (Join-Path $repo "frontend")
    npx tauri dev
}
