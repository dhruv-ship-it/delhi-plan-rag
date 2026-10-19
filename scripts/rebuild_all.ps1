<#
.SYNOPSIS
    Rebuild everything ZoneWise needs, in order, from the source PDFs.

.DESCRIPTION
    Runs the numbered pipeline scripts in the one order that works, because each reads
    what the one before it wrote:

        01_check_sources    is sources.csv sound and is every PDF on disk
        02_extract          PDFs      -> data/processed/pages.jsonl
        build_chapter_map   pages     -> data/chapter_map.json
        03_chunk            pages+map -> data/processed/chunks.jsonl
        04_tag_zones        chunks    -> the same chunks, with zone tags
        05_build_index      chunks    -> data/index/chroma + bm25.pkl

    Two steps are conditional, because both hit the network and neither should run on a
    routine rebuild:

        06_fetch_layers     only when data/layers/dda is missing, or -RefreshLayers.
                            These come from DDA's GIS portal and do not change.
        build_gazetteer     only when data/gazetteer/metro_stations.json is missing, and
                            a failure is a WARNING rather than an error: an absent
                            gazetteer is a supported state and app/geocode.py falls back
                            to Nominatim (D-074).

    Any other failure stops the run at that step, because everything after it would be
    working from stale or missing input.

    Expect roughly 5-10 minutes on a laptop. 05_build_index is most of it: embedding 700
    chunks takes about 160 seconds, plus a one-off 80 MB model download on a clean
    machine.

.PARAMETER DryRun
    Print the steps that would run, and why each conditional one would or would not,
    then exit. Runs nothing and writes nothing.

.PARAMETER RefreshLayers
    Re-download the DDA map layers even though they are already on disk.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\rebuild_all.ps1 -DryRun

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\rebuild_all.ps1
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$RefreshLayers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Run from the repo root whatever directory this was invoked from, so the relative
# paths below and the scripts' own relative paths agree.
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

$layersDir    = Join-Path $repoRoot 'data\layers\dda'
$gazetteerDir = Join-Path $repoRoot 'data\gazetteer'
$gazetteer    = Join-Path $gazetteerDir 'metro_stations.json'

# Each step: the script to run, and why it is or is not in this run.
$steps = @(
    @{ Script = 'scripts/01_check_sources.py';  Label = 'check sources' }
    @{ Script = 'scripts/02_extract.py';        Label = 'extract page text' }
    @{ Script = 'scripts/build_chapter_map.py'; Label = 'build the chapter map' }
    @{ Script = 'scripts/03_chunk.py';          Label = 'clean and chunk' }
    @{ Script = 'scripts/04_tag_zones.py';      Label = 'tag zones' }
    @{ Script = 'scripts/05_build_index.py';    Label = 'build the search indexes' }
)

# --- the two conditional steps --------------------------------------------------
$haveLayers = (Test-Path $layersDir) -and
              ((Get-ChildItem -Path $layersDir -Filter *.geojson -ErrorAction SilentlyContinue).Count -gt 0)

if ($RefreshLayers) {
    $layerReason = 'forced by -RefreshLayers'
    $runLayers = $true
} elseif (-not $haveLayers) {
    $layerReason = 'data/layers/dda has no .geojson files'
    $runLayers = $true
} else {
    $layerReason = 'data/layers/dda is already populated; pass -RefreshLayers to re-download'
    $runLayers = $false
}

$haveGazetteer = Test-Path $gazetteer
if ($haveGazetteer) {
    $gazetteerReason = 'data/gazetteer/metro_stations.json already exists'
    $runGazetteer = $false
} else {
    $gazetteerReason = 'data/gazetteer/metro_stations.json is missing'
    $runGazetteer = $true
}

# --- dry run --------------------------------------------------------------------
if ($DryRun) {
    Write-Host ''
    Write-Host 'ZoneWise rebuild, dry run. Nothing below is executed.' -ForegroundColor Cyan
    Write-Host "Repo: $repoRoot"
    Write-Host ''
    Write-Host 'Always:' -ForegroundColor Cyan
    $n = 0
    foreach ($step in $steps) {
        $n++
        Write-Host ("  {0}. uv run python {1}" -f $n, $step.Script)
        Write-Host ("     {0}" -f $step.Label) -ForegroundColor DarkGray
    }
    Write-Host ''
    Write-Host 'Conditional:' -ForegroundColor Cyan
    $mark = if ($runLayers) { 'WOULD RUN ' } else { 'would skip' }
    $colour = if ($runLayers) { 'Green' } else { 'DarkGray' }
    Write-Host ("  [{0}] uv run python scripts/06_fetch_layers.py" -f $mark) -ForegroundColor $colour
    Write-Host ("               {0}" -f $layerReason) -ForegroundColor DarkGray
    $mark = if ($runGazetteer) { 'WOULD RUN ' } else { 'would skip' }
    $colour = if ($runGazetteer) { 'Green' } else { 'DarkGray' }
    Write-Host ("  [{0}] uv run python scripts/build_gazetteer.py" -f $mark) -ForegroundColor $colour
    Write-Host ("               {0}" -f $gazetteerReason) -ForegroundColor DarkGray
    Write-Host '               a failure here is tolerated with a warning' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host 'Order matters: 06_fetch_layers runs first when it runs at all (the test' -ForegroundColor DarkGray
    Write-Host 'points it writes are read by nothing in the chunk pipeline, but the layers' -ForegroundColor DarkGray
    Write-Host 'are what the server needs), and build_gazetteer runs last because nothing' -ForegroundColor DarkGray
    Write-Host 'else depends on it.' -ForegroundColor DarkGray
    Write-Host ''
    Pop-Location
    exit 0
}

# --- the real run ---------------------------------------------------------------
function Invoke-Step {
    <#
      Run one pipeline script with uv. Returns the exit code; never throws, so the
      caller decides whether a non-zero code is fatal.
    #>
    param(
        [Parameter(Mandatory)][string]$Script,
        [Parameter(Mandatory)][string]$Label
    )
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkGray
    Write-Host ("  {0}" -f $Label) -ForegroundColor Cyan
    Write-Host ("  uv run python {0}" -f $Script) -ForegroundColor DarkGray
    Write-Host ('=' * 72) -ForegroundColor DarkGray

    $stepStart = Get-Date
    & uv run python $Script
    $code = $LASTEXITCODE
    $elapsed = (Get-Date) - $stepStart
    Write-Host ("  -> exit {0} in {1:n1}s" -f $code, $elapsed.TotalSeconds) -ForegroundColor DarkGray
    return $code
}

$started = Get-Date
$completed = @()

Write-Host ''
Write-Host 'ZoneWise full rebuild.' -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"
Write-Host "Layers:    $layerReason"
Write-Host "Gazetteer: $gazetteerReason"

# The layers first when they are wanted: they need no pipeline output, and finding out
# the download is broken is better before ten minutes of embedding than after.
if ($runLayers) {
    $code = Invoke-Step -Script 'scripts/06_fetch_layers.py' -Label 'download the DDA map layers'
    if ($code -ne 0) {
        Write-Host ''
        Write-Host "STOPPED: scripts/06_fetch_layers.py exited $code." -ForegroundColor Red
        Write-Host 'The layers come from gis.dda.org.in. Check that you can reach it, then' -ForegroundColor Red
        Write-Host 're-run. Nothing after this point was touched.' -ForegroundColor Red
        Pop-Location
        exit 1
    }
    $completed += '06_fetch_layers'
}

foreach ($step in $steps) {
    $code = Invoke-Step -Script $step.Script -Label $step.Label
    if ($code -ne 0) {
        $elapsed = (Get-Date) - $started
        Write-Host ''
        Write-Host ("STOPPED at {0}, exit {1}." -f $step.Script, $code) -ForegroundColor Red
        Write-Host 'Everything after this step reads what it writes, so the run ends here' -ForegroundColor Red
        Write-Host 'rather than building on stale input.' -ForegroundColor Red
        if ($completed.Count -gt 0) {
            Write-Host ("Completed before the failure: {0}" -f ($completed -join ', ')) -ForegroundColor DarkGray
        }
        Write-Host ("Elapsed: {0:n1}s" -f $elapsed.TotalSeconds) -ForegroundColor DarkGray
        Pop-Location
        exit 1
    }
    $completed += (Split-Path -Leaf $step.Script).Replace('.py', '')
}

# The gazetteer last, and a failure here is survivable. Overpass is a free service on
# donated hardware and has been unreachable from more than one environment this project
# has run in; app/geocode.py treats an absent gazetteer as a supported state (D-074).
$gazetteerWarning = $null
if ($runGazetteer) {
    $code = Invoke-Step -Script 'scripts/build_gazetteer.py' -Label 'build the metro gazetteer (optional)'
    if ($code -ne 0) {
        $gazetteerWarning = "scripts/build_gazetteer.py exited $code"
        Write-Host ''
        Write-Host "WARNING: $gazetteerWarning" -ForegroundColor Yellow
        Write-Host 'Tolerated. The gazetteer is an optimisation over Nominatim, not a' -ForegroundColor Yellow
        Write-Host 'requirement: app/geocode.py falls back to Nominatim when the file is' -ForegroundColor Yellow
        Write-Host 'absent (D-074). Run it again from a terminal with Overpass access:' -ForegroundColor Yellow
        Write-Host '    uv run python scripts\build_gazetteer.py' -ForegroundColor Yellow
    } else {
        $completed += 'build_gazetteer'
    }
}

# --- summary --------------------------------------------------------------------
$elapsed = (Get-Date) - $started
Write-Host ''
Write-Host ('=' * 72) -ForegroundColor Green
Write-Host '  rebuild complete' -ForegroundColor Green
Write-Host ('=' * 72) -ForegroundColor Green
Write-Host ("  steps run:  {0}" -f ($completed -join ', '))
if (-not $runLayers)    { Write-Host "  skipped:    06_fetch_layers ($layerReason)" -ForegroundColor DarkGray }
if (-not $runGazetteer) { Write-Host "  skipped:    build_gazetteer ($gazetteerReason)" -ForegroundColor DarkGray }
if ($gazetteerWarning)  { Write-Host "  warning:    $gazetteerWarning" -ForegroundColor Yellow }
Write-Host ("  total time: {0:n1}s ({1:n1} min)" -f $elapsed.TotalSeconds, $elapsed.TotalMinutes)
Write-Host ''
Write-Host '  Next:  uv run pytest' -ForegroundColor Cyan
Write-Host '         powershell -ExecutionPolicy Bypass -File scripts\dev.ps1' -ForegroundColor Cyan
Write-Host ''

Pop-Location
exit 0
