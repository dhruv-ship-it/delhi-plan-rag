<#
.SYNOPSIS
    Run every check this repository has, and print one pass/fail summary.

.DESCRIPTION
    Three checks, in rising order of how long they take:

        1. ruff check .     lint: pyflakes (F), syntax errors (E9), import order (I).
                            Not a formatter - `ruff format` is deliberately not run
                            here or anywhere (D-080).
        2. uv run pytest    all 629 tests. 38 of them need the built indexes and the
                            DDA layers; without that data they will fail rather than
                            skip, so on a clean clone use -NoData.
        3. npm run build    the frontend. Catches an import that no test touches,
                            which is most of web/src.

    All three run even when an earlier one fails, because knowing everything that is
    broken in one go beats finding out one thing at a time. The exit code is 0 only if
    all three passed, so this is usable from a pre-push hook.

    This is what CI runs, in the same order, with one difference: CI always passes
    -m "not needs_data", because a GitHub runner has none of the gitignored data.

.PARAMETER NoData
    Run pytest with -m "not needs_data" - the 591 tests that need no built index or map
    layers. Use this on a clean clone, or to check nothing but the code.

.PARAMETER SkipWeb
    Skip the frontend build. It is the slowest of the three and needs node_modules.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check.ps1 -NoData
#>

[CmdletBinding()]
param(
    [switch]$NoData,
    [switch]$SkipWeb
)

Set-StrictMode -Version Latest
# Not 'Stop': a failing check is an expected outcome here, not an exception. Each
# check's exit code is read explicitly instead.
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$webDir   = Join-Path $repoRoot 'web'
Push-Location $repoRoot

$results = [System.Collections.ArrayList]::new()

function Add-Result {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$State,   # PASS | FAIL | SKIP
        [Parameter(Mandatory)][string]$Detail,
        [double]$Seconds = 0
    )
    $null = $results.Add([pscustomobject]@{
        Name    = $Name
        State   = $State
        Detail  = $Detail
        Seconds = $Seconds
    })
}

function Write-Header {
    param([Parameter(Mandatory)][string]$Text)
    Write-Host ''
    Write-Host ('-' * 72) -ForegroundColor DarkGray
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('-' * 72) -ForegroundColor DarkGray
}

# --- 1. ruff --------------------------------------------------------------------
Write-Header 'ruff check .'
$t = Get-Date
& uv run ruff check .
$code = $LASTEXITCODE
$secs = ((Get-Date) - $t).TotalSeconds
if ($code -eq 0) {
    Add-Result -Name 'ruff' -State 'PASS' -Detail 'no lint errors' -Seconds $secs
} else {
    Add-Result -Name 'ruff' -State 'FAIL' -Detail "exit $code - run: uv run ruff check --fix ." -Seconds $secs
}

# --- 2. pytest ------------------------------------------------------------------
if ($NoData) {
    Write-Header 'uv run pytest -m "not needs_data"'
} else {
    Write-Header 'uv run pytest'
}
$t = Get-Date
if ($NoData) {
    & uv run pytest -m "not needs_data" -q
} else {
    & uv run pytest -q
}
$code = $LASTEXITCODE
$secs = ((Get-Date) - $t).TotalSeconds
$scope = if ($NoData) { '591 expected, no data needed' } else { '629 expected' }
if ($code -eq 0) {
    Add-Result -Name 'pytest' -State 'PASS' -Detail $scope -Seconds $secs
} else {
    Add-Result -Name 'pytest' -State 'FAIL' -Detail "exit $code - scroll up for the failures" -Seconds $secs
}

# --- 3. the frontend build ------------------------------------------------------
if ($SkipWeb) {
    Add-Result -Name 'web build' -State 'SKIP' -Detail '-SkipWeb was passed'
} elseif (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Add-Result -Name 'web build' -State 'SKIP' -Detail 'no web/node_modules - run: cd web; npm install'
} else {
    Write-Header 'npm run build  (in web/)'
    $t = Get-Date
    Push-Location $webDir
    & npm run build
    $code = $LASTEXITCODE
    Pop-Location
    $secs = ((Get-Date) - $t).TotalSeconds
    $bundle = Join-Path $webDir 'dist\index.html'
    if ($code -eq 0 -and (Test-Path $bundle)) {
        Add-Result -Name 'web build' -State 'PASS' -Detail 'web/dist/index.html written' -Seconds $secs
    } elseif ($code -eq 0) {
        Add-Result -Name 'web build' -State 'FAIL' -Detail 'vite exited 0 but web/dist/index.html is missing' -Seconds $secs
    } else {
        Add-Result -Name 'web build' -State 'FAIL' -Detail "exit $code" -Seconds $secs
    }
}

# --- summary --------------------------------------------------------------------
$failed  = @($results | Where-Object { $_.State -eq 'FAIL' })
$skipped = @($results | Where-Object { $_.State -eq 'SKIP' })

Write-Host ''
Write-Host ('=' * 72) -ForegroundColor DarkGray
Write-Host '  SUMMARY' -ForegroundColor Cyan
Write-Host ('=' * 72) -ForegroundColor DarkGray
foreach ($r in $results) {
    $colour = switch ($r.State) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        default { 'Yellow' }
    }
    $time = if ($r.Seconds -gt 0) { ('{0,6:n1}s' -f $r.Seconds) } else { '       ' }
    Write-Host ('  {0,-6} {1,-11} {2}  {3}' -f $r.State, $r.Name, $time, $r.Detail) -ForegroundColor $colour
}
Write-Host ('=' * 72) -ForegroundColor DarkGray

Pop-Location

if ($failed.Count -gt 0) {
    Write-Host ("  {0} of {1} checks FAILED: {2}" -f $failed.Count, $results.Count, (($failed.Name) -join ', ')) -ForegroundColor Red
    Write-Host ''
    exit 1
}

$msg = "  all {0} checks passed" -f ($results.Count - $skipped.Count)
if ($skipped.Count -gt 0) { $msg += (", {0} skipped" -f $skipped.Count) }
Write-Host $msg -ForegroundColor Green
Write-Host ''
exit 0
