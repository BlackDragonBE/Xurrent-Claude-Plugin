#Requires -Version 5.1
<#
.SYNOPSIS
  Check and prepare prerequisites for the Xurrent Claude Plugin.
  Run this before installing the plugin in Claude Code.
#>

$ErrorActionPreference = 'Stop'

function Write-Step { param($msg) Write-Host "  >> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  XX  $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Xurrent Claude Plugin - setup" -ForegroundColor White
Write-Host "------------------------------"

# Python >= 3.10
Write-Step "Checking Python..."
try {
    $pyver = & python --version 2>&1
    if ($pyver -match '(\d+)\.(\d+)') {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Fail "Python 3.10+ required (found $pyver). Install from https://python.org"
        }
        Write-OK $pyver
    }
} catch {
    Write-Fail "Python not found. Install Python 3.10+ from https://python.org"
}

# uv
Write-Step "Checking uv..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warn "uv not found - installing..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'User') + ';' +
                [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Fail "uv install failed. Restart your terminal and re-run this script."
    }
}
Write-OK "uv $((uv --version) -replace 'uv ','')"

# Pre-warm the server venv (only when script is run from the cloned repo)
$serverDir = if ($PSScriptRoot) { Join-Path $PSScriptRoot "plugins\xurrent\server" } else { $null }
if ($serverDir -and (Test-Path $serverDir)) {
    Write-Step "Syncing server dependencies..."
    & uv sync --directory $serverDir
    Write-OK "Dependencies ready."
}

Write-Host ""
Write-Host "Setup complete. Now run these commands inside Claude Code:" -ForegroundColor Green
Write-Host ""
Write-Host "  /plugin marketplace add BlackDragonBE/xurrent-tools" -ForegroundColor White
Write-Host "  /plugin install xurrent@xurrent-tools" -ForegroundColor White
Write-Host ""
