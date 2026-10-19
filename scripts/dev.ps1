<#
.SYNOPSIS
    Start both ZoneWise servers, each in its own PowerShell window.

.DESCRIPTION
    Development needs two processes running at once:

        backend   uv run python scripts/serve.py       http://localhost:8000
        frontend  npm run dev        (in web/)         http://localhost:5173

    Open http://localhost:5173. The Vite dev server proxies /api to the backend, so you
    get hot reload on the React side and the real API underneath.

    Each gets its own window on purpose, rather than being backgrounded: both print
    things you need to read. serve.py says whether answers are enabled or whether it is
    in search-only mode with no API key, and Vite prints compile errors. A backgrounded
    job would hide both.

    The windows stay open when a server exits, so you can read the error that killed it.
    Close them, or Ctrl+C in each, to stop.

.PARAMETER Verify
    Set ZONEWISE_DEV=1 for the backend, which turns on the four /api/dev/eval/
    endpoints and the Verify tab in the web app (D-075). Without this they 404.
    Use this for the question-verification session.

.PARAMETER Port
    Backend port. Default 8000. The Vite proxy is configured for 8000, so changing this
    means the frontend will not find the API.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Verify
#>

[CmdletBinding()]
param(
    [switch]$Verify,
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$webDir   = Join-Path $repoRoot 'web'

# --- check what is needed is there, before opening windows that would just fail ---
$problems = @()

if (-not (Test-Path (Join-Path $repoRoot 'data\index\bm25.pkl'))) {
    $problems += 'No search index (data/index/bm25.pkl). Run: uv run python scripts\05_build_index.py'
}
$layers = Join-Path $repoRoot 'data\layers\dda'
if (-not (Test-Path $layers) -or
    (Get-ChildItem -Path $layers -Filter *.geojson -ErrorAction SilentlyContinue).Count -eq 0) {
    $problems += 'No map layers (data/layers/dda/*.geojson). Run: uv run python scripts\06_fetch_layers.py'
}
if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    $problems += 'Frontend dependencies not installed. Run: cd web; npm install'
}

if ($problems.Count -gt 0) {
    Write-Host ''
    Write-Host 'Cannot start:' -ForegroundColor Red
    foreach ($p in $problems) { Write-Host "  - $p" -ForegroundColor Red }
    Write-Host ''
    Write-Host 'Or rebuild everything:' -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy Bypass -File scripts\rebuild_all.ps1' -ForegroundColor Yellow
    Write-Host ''
    exit 1
}

# --- the backend ----------------------------------------------------------------
# -NoExit so the window survives the process, and the title names the window so two
# of these are tellable apart on the taskbar.
$devEnv = if ($Verify) { '$env:ZONEWISE_DEV = "1"; ' } else { '' }
$backendCommand = @"
`$host.UI.RawUI.WindowTitle = 'ZoneWise backend'
Set-Location '$repoRoot'
$devEnv
uv run python scripts/serve.py --port $Port
"@

Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $backendCommand

# --- the frontend ---------------------------------------------------------------
$frontendCommand = @"
`$host.UI.RawUI.WindowTitle = 'ZoneWise web'
Set-Location '$webDir'
npm run dev
"@

Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $frontendCommand

# --- what just happened ---------------------------------------------------------
Write-Host ''
Write-Host 'Two windows opened:' -ForegroundColor Cyan
Write-Host ("  ZoneWise backend   http://localhost:{0}" -f $Port)
Write-Host ("                     http://localhost:{0}/api/health  what loaded" -f $Port)
Write-Host ("                     http://localhost:{0}/docs         generated API docs" -f $Port)
Write-Host '  ZoneWise web       http://localhost:5173'
Write-Host ''
if ($Verify) {
    Write-Host 'ZONEWISE_DEV=1 is set for the backend.' -ForegroundColor Green
    Write-Host 'The Verify tab is live, and /api/dev/eval/ answers instead of 404ing.'
    Write-Host 'See eval/README.md for how to judge a question.'
} else {
    Write-Host 'ZONEWISE_DEV is not set, so the Verify tab and /api/dev/eval/ will 404.' -ForegroundColor DarkGray
    Write-Host 'Re-run with -Verify to turn them on.' -ForegroundColor DarkGray
}
Write-Host ''
Write-Host 'Open  ->  http://localhost:5173' -ForegroundColor Cyan
Write-Host 'The backend takes a few seconds: the indexes and the embedding model load'
Write-Host 'before the first request. Watch its window for "Application startup complete".'
Write-Host ''
Write-Host 'Stop with Ctrl+C in each window, or just close them.' -ForegroundColor DarkGray
Write-Host ''
