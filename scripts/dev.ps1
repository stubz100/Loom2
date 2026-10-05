# loom2 dev: one command for the whole stack. `npx tauri dev` runs the Vite dev server (beforeDevCommand),
# builds and opens the shell, and the shell spawns the orchestrator (which spawns the engine on the first job).
#   scripts/dev.ps1            # app
#   scripts/dev.ps1 -Browser   # orchestrator on 8766 with a fixed token + Vite only; open the printed URL in a browser
param([switch]$Browser)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if ($Browser) {
    $env:LOOM2_TOKEN = "devtoken"
    $env:PYTHONIOENCODING = "utf-8"
    $state = Join-Path $repo ".loom2_state"
    Start-Process -FilePath (Join-Path $repo "orchestrator\.venv\Scripts\python.exe") -ArgumentList "-m", "loom2.main", "--port", "8766", "--state", $state -WorkingDirectory (Join-Path $repo "orchestrator") -NoNewWindow
    Write-Host "[loom2] orchestrator on http://127.0.0.1:8766 (token devtoken)"
    Write-Host "[loom2] open http://127.0.0.1:1420/?token=devtoken&port=8766  (add &suite=models to deep-link)"
    Set-Location (Join-Path $repo "frontend")
    npm run dev
} else {
    Set-Location (Join-Path $repo "frontend")
    npx tauri dev
}
