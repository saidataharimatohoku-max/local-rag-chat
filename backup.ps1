<#
.SYNOPSIS
    Creates local backups of this repository: a full-history git bundle and a
    source zip snapshot of tracked files.

.DESCRIPTION
    Backups are written to a sibling folder so they live outside the repo:
        ..\microsoft-project4-backups

    The git bundle contains the COMPLETE commit history and can be cloned
    directly, even with no internet access:
        git clone <file>.bundle restored-project

    The zip contains only tracked files (no .venv, secrets, or caches).

.EXAMPLE
    .\backup.ps1
#>

$ErrorActionPreference = "Stop"

# Ensure git is reachable even when it's not on PATH.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $env:Path += ";C:\Program Files\Git\cmd"
}

# Resolve paths relative to this script so it works from any working directory.
$repoRoot  = $PSScriptRoot
$backupDir = Join-Path (Split-Path $repoRoot -Parent) "microsoft-project4-backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Push-Location $repoRoot
try {
    $stamp  = Get-Date -Format "yyyy-MM-dd_HHmm"
    $bundle = Join-Path $backupDir "local-rag-chat_$stamp.bundle"
    $zip    = Join-Path $backupDir "local-rag-chat_source_$stamp.zip"

    Write-Host "Creating full-history bundle..." -ForegroundColor Cyan
    git bundle create $bundle --all
    git bundle verify $bundle | Out-Null

    Write-Host "Creating source zip snapshot..." -ForegroundColor Cyan
    git archive --format=zip -o $zip HEAD

    Write-Host "`nBackups written to $backupDir" -ForegroundColor Green
    Get-ChildItem $backupDir |
        Select-Object Name,
            @{N = 'SizeKB'; E = { [math]::Round($_.Length / 1KB, 1) } },
            LastWriteTime |
        Format-Table -AutoSize
}
finally {
    Pop-Location
}
