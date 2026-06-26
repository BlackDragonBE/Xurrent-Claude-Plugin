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

# Python is provisioned by uv (below) — no system Python needed.
# ponytail: dropped the system-Python detect/install dance. uv reads
# requires-python from pyproject.toml and downloads a matching interpreter
# itself, sidestepping the Microsoft Store alias and all PATH-refresh pain.

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

# Python (managed by uv — no system install, no PATH games)
Write-Step "Ensuring a Python 3.10+ interpreter via uv..."
& uv python install 3.12 2>&1 | Out-Null   # ponytail: ignore the cosmetic
# "minor version link" exit code uv sometimes emits; verify by what's installed.
$pyInstalled = (& uv python list --only-installed 2>&1) -match 'cpython-3\.1[0-9]'
if ($pyInstalled) { Write-OK "Python ready (uv-managed)." }
else { Write-Fail "uv could not provide Python 3.10+. Run 'uv python install 3.12' manually, then re-run." }

# Environment variables
Write-Host ""
Write-Step "Configuring Xurrent environment variables..."

function Read-EnvVar {
    param($Name, $Prompt, $Required = $true, $Default = '')
    $current = [System.Environment]::GetEnvironmentVariable($Name, 'User')
    $display  = if ($current) { " (current: $current)" } else { '' }
    $hint     = if (-not $Required) { " [Enter to keep '$Default']" } else { '' }
    $value    = Read-Host "  $Prompt$display$hint"
    if (-not $value) {
        if ($current) { return $current }
        if (-not $Required) { return $Default }
        Write-Fail "$Name is required."
    }
    [System.Environment]::SetEnvironmentVariable($Name, $value, 'User')
    ${env:$Name} = $value
    return $value
}

Read-EnvVar 'XURRENT_ACCOUNT'   'Xurrent account name (e.g. provincieantwerpen)'  | Out-Null
Read-EnvVar 'XURRENT_QA_TOKEN'  'Xurrent QA API token'                             | Out-Null
Read-EnvVar 'XURRENT_PRD_TOKEN' 'Xurrent Production API token'                     | Out-Null
Read-EnvVar 'XURRENT_ME_EMAIL'  'Your Xurrent email (optional but recommended, enables "assigned to me")' $false | Out-Null

Write-OK "Environment variables saved to user profile."

# Pre-warm the server venv (only when script is run from the cloned repo)
$serverDir = if ($PSScriptRoot) { Join-Path $PSScriptRoot "plugins\xurrent\server" } else { $null }
if ($serverDir -and (Test-Path $serverDir)) {
    Write-Step "Syncing server dependencies..."
    & uv sync --directory $serverDir
    Write-OK "Dependencies ready."
}

Write-Host ""
Write-Host "Setup complete. Now run these commands to install the plugin:" -ForegroundColor Green
Write-Host ""
Write-Host "claude plugin marketplace add BlackDragonBE/Xurrent-Claude-Plugin" -ForegroundColor White
Write-Host "claude plugin install xurrent@xurrent-tools" -ForegroundColor White
Write-Host ""
