# Step 2 Validation Script (PowerShell)
# Usage:
#   1) Start backend on http://127.0.0.1:8000
#   2) Edit RootA/RootB + test file names below
#   3) Run this script in PowerShell
#
# Notes:
# - This script checks:
#   health, command, search, root update -> tree/read/search on new root
# - It prints PASS/FAIL per step and exits non-zero on hard failures.

$ErrorActionPreference = "Stop"

# -----------------------------
# CONFIG: EDIT THESE
# -----------------------------
$Base = "http://127.0.0.1:8765"

# Root A and B should both exist and be directories
$RootA = "G:\slpfs_test\root_A"
$RootB = "G:\slpfs_test\root_B"

# Files used for read/search validation
$RootAFile = "A.txt"
$RootBFile = "B.txt"

# Unique phrases to verify semantic/search path
$PhraseA = "alpha semantic token step2"
$PhraseB = "beta unique phrase step2"

# Optional: command input for NL pipeline validation
$CommandTextGood = "create a file named step2-command-check.txt with content hello from command path"
$CommandTextBad  = "blargh xyz nonsense unknown intent"

# -----------------------------
# Helpers
# -----------------------------
$Results = @()

function Add-Result {
    param(
        [string]$Step,
        [string]$Status,
        [string]$Details
    )
    $script:Results += [pscustomobject]@{
        Step    = $Step
        Status  = $Status
        Details = $Details
    }
    $line = "[$Status] $Step - $Details"
    $color = if ($Status -eq "PASS") { "Green" } elseif ($Status -eq "WARN") { "Yellow" } else { "Red" }
    Write-Host $line -ForegroundColor $color
    Write-Output $line
}

function Invoke-Api {
    param(
        [ValidateSet("GET","POST","PUT","DELETE")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )
    $uri = "$Base$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri
    }
    $json = $Body | ConvertTo-Json -Depth 20
    return Invoke-RestMethod -Method $Method -Uri $uri -ContentType "application/json" -Body $json
}

function Ensure-FileContent {
    param(
        [string]$Root,
        [string]$RelativePath,
        [string]$Content
    )
    if (-not (Test-Path $Root)) {
        New-Item -ItemType Directory -Path $Root | Out-Null
    }
    $full = Join-Path $Root $RelativePath
    $dir = Split-Path $full -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    Set-Content -Path $full -Value $Content -Encoding UTF8
    return $full
}

function Has-AnyText {
    param([object]$Value)
    return ($null -ne $Value -and [string]$Value -ne "")
}

# -----------------------------
# Pre-seed test data
# -----------------------------
Write-Output "Starting Step 2 validation against $Base"

try {
    $aFileFull = Ensure-FileContent -Root $RootA -RelativePath $RootAFile -Content "RootA file. $PhraseA"
    $bFileFull = Ensure-FileContent -Root $RootB -RelativePath $RootBFile -Content "RootB file. $PhraseB"
    Add-Result -Step "Seed test data" -Status "PASS" -Details "Created/updated test files in RootA and RootB"
}
catch {
    Add-Result -Step "Seed test data" -Status "FAIL" -Details $_.Exception.Message
    exit 1
}

# -----------------------------
# 0) Reachability
# -----------------------------
try {
    $null = Invoke-Api -Method GET -Path "/"
    Add-Result -Step "Backend reachability" -Status "PASS" -Details "API reachable at $Base"
}
catch {
    Add-Result -Step "Backend reachability" -Status "FAIL" -Details $_.Exception.Message
    $Results | Format-Table -AutoSize
    exit 1
}

# -----------------------------
# 1) Health check
# -----------------------------
try {
    $health = Invoke-Api -Method GET -Path "/api/v1/health"
    $d = $health.data

    $required = @(
        "backend_status","runtime_loaded","ollama_status","model_status",
        "indexed_file_count","current_root"
    )

    $missing = @()
    foreach ($k in $required) {
        if (-not $d.PSObject.Properties.Name.Contains($k)) {
            $missing += $k
        }
    }

    if ($missing.Count -gt 0) {
        Add-Result -Step "Health check fields" -Status "FAIL" -Details ("Missing fields: " + ($missing -join ", "))
    } else {
        Add-Result -Step "Health check fields" -Status "PASS" -Details "All required readiness fields present"
    }

    # Quick static-string guard
    $staticLike = @("checking","pending","unknown")
    $foundStatic = @()
    foreach ($k in @("backend_status","ollama_status","model_status")) {
        $v = [string]$d.$k
        foreach ($s in $staticLike) {
            if ($v.ToLower().Contains($s)) { $foundStatic += "$k=$v" }
        }
    }

    if ($foundStatic.Count -gt 0) {
        Add-Result -Step "Health non-static statuses" -Status "WARN" -Details ("Potential static-like statuses: " + ($foundStatic -join "; "))
    } else {
        Add-Result -Step "Health non-static statuses" -Status "PASS" -Details "Statuses look runtime-derived"
    }
}
catch {
    Add-Result -Step "Health check" -Status "FAIL" -Details $_.Exception.Message
}

# -----------------------------
# 2) Command path
# -----------------------------
try {
    $cmdGood = Invoke-Api -Method POST -Path "/api/v1/command" -Body @{ text = $CommandTextGood }
    $cg = $cmdGood.data

    if ($cg.PSObject.Properties.Name.Contains("command_status") -and $cg.PSObject.Properties.Name.Contains("slpfs_success")) {
        Add-Result -Step "Command path (good input)" -Status "PASS" -Details "SLPFS-mapped command fields present"
    } else {
        Add-Result -Step "Command path (good input)" -Status "FAIL" -Details "Missing command_status/slpfs_success"
    }

    $cmdBad = Invoke-Api -Method POST -Path "/api/v1/command" -Body @{ text = $CommandTextBad }
    $cb = $cmdBad.data
    if ($cb.command_status -eq "failed" -and (Has-AnyText $cb.slpfs_error)) {
        Add-Result -Step "Command pass-through (low confidence/error)" -Status "PASS" -Details "Failure clearly surfaced from SLPFS"
    } else {
        Add-Result -Step "Command pass-through (low confidence/error)" -Status "WARN" -Details "Did not clearly expose failed status/error"
    }
}
catch {
    Add-Result -Step "Command path" -Status "FAIL" -Details $_.Exception.Message
}

# -----------------------------
# 3) Search path (semantic-first)
# -----------------------------
try {
    # First switch to RootA for deterministic search seed
    $cfgA = Invoke-Api -Method PUT -Path "/api/v1/config" -Body @{ root_path = $RootA }

    $searchA = Invoke-Api -Method POST -Path "/api/v1/search" -Body @{
        query = $PhraseA
        k     = 5
        mode  = "normal"
    }

    $sd = $searchA.data
    if ($sd.PSObject.Properties.Name.Contains("source") -and $sd.source -eq "runtime") {
        Add-Result -Step "Search source check" -Status "PASS" -Details "Search source is runtime (semantic-first path)"
    } else {
        Add-Result -Step "Search source check" -Status "WARN" -Details "Search source not explicitly runtime"
    }

    if ($sd.results.Count -ge 1) {
        Add-Result -Step "Search results presence" -Status "PASS" -Details "Received results from vector pipeline mapping"
    } else {
        Add-Result -Step "Search results presence" -Status "WARN" -Details "No results found; verify indexing/model availability"
    }

    # contract mapping fields
    $mappedOk = $true
    foreach ($r in $sd.results) {
        foreach ($f in @("path","score","snippet","is_dir")) {
            if (-not $r.PSObject.Properties.Name.Contains($f)) { $mappedOk = $false }
        }
    }

    if ($mappedOk) {
        Add-Result -Step "Search contract mapping" -Status "PASS" -Details "Results mapped to frontend contract"
    } else {
        Add-Result -Step "Search contract mapping" -Status "WARN" -Details "One or more result fields missing"
    }
}
catch {
    Add-Result -Step "Search path" -Status "FAIL" -Details $_.Exception.Message
}

# -----------------------------
# 4) Root update path end-to-end
# -----------------------------
try {
    # Update root to RootB
    $cfgB = Invoke-Api -Method PUT -Path "/api/v1/config" -Body @{ root_path = $RootB }
    $newRoot = [string]$cfgB.data.root_path

    if ($newRoot -eq $RootB) {
        Add-Result -Step "Config root update" -Status "PASS" -Details "Runtime root updated to RootB"
    } else {
        Add-Result -Step "Config root update" -Status "WARN" -Details "Returned root differs: $newRoot"
    }

    # Verify /config reflects new root
    $cfgNow = Invoke-Api -Method GET -Path "/api/v1/config"
    if ([string]$cfgNow.data.root_path -eq $RootB) {
        Add-Result -Step "Config readback" -Status "PASS" -Details "/config reflects RootB"
    } else {
        Add-Result -Step "Config readback" -Status "FAIL" -Details "/config did not reflect RootB"
    }

    # Verify /tree works on new root
    $tree = Invoke-Api -Method GET -Path "/api/v1/tree"
    if ([string]$tree.data.root -eq $RootB -or [string]$tree.data.path -like "$RootB*") {
        Add-Result -Step "Tree on new root" -Status "PASS" -Details "Tree operates on RootB"
    } else {
        Add-Result -Step "Tree on new root" -Status "WARN" -Details "Tree response root/path not clearly RootB"
    }

    # Verify /file/read reads from new root
    $read = Invoke-Api -Method POST -Path "/api/v1/file/read" -Body @{ path = $RootBFile }
    if ([string]$read.data.path -like "$RootB*" -and [string]$read.data.content -match [regex]::Escape($PhraseB)) {
        Add-Result -Step "Read on new root" -Status "PASS" -Details "File read resolves under RootB"
    } else {
        Add-Result -Step "Read on new root" -Status "FAIL" -Details "Read did not resolve to RootB content"
    }

    # Verify /search sees RootB phrase
    $searchB = Invoke-Api -Method POST -Path "/api/v1/search" -Body @{
        query = $PhraseB
        k     = 5
        mode  = "normal"
    }
    if ($searchB.data.results.Count -ge 1) {
        Add-Result -Step "Search on new root" -Status "PASS" -Details "Search returns RootB results after root update"
    } else {
        Add-Result -Step "Search on new root" -Status "WARN" -Details "No RootB search results; may need reindex/warm-up"
    }
}
catch {
    Add-Result -Step "Root update path" -Status "FAIL" -Details $_.Exception.Message
}

# -----------------------------
# Summary
# -----------------------------
Write-Host ""
Write-Host "=== Validation Summary ===" -ForegroundColor Cyan
$Results | Format-Table -AutoSize

$failCount = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
if ($failCount -gt 0) {
    Write-Host "`nValidation completed with FAILURES: $failCount" -ForegroundColor Red
    exit 1
}

Write-Host "`nValidation completed (no FAIL). Review WARN rows if any." -ForegroundColor Green
exit 0