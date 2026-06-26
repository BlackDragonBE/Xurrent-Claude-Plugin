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
$pythonOk = $false
try {
    $pyver = & python --version 2>&1
    if ($pyver -match '(\d+)\.(\d+)') {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Warn "Python 3.10+ required (found $pyver) — will install via Chocolatey."
        } else {
            Write-OK $pyver; $pythonOk = $true
        }
    }
} catch { <# not found #> }

if (-not $pythonOk) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Installing Python 3 via winget..."
        & winget install --id Python.Python.3 --silent --accept-source-agreements --accept-package-agreements
    } else {
        Write-Warn "winget not found - falling back to Chocolatey..."
        if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
            Write-Warn "Chocolatey not found - installing..."
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
                        [System.Environment]::GetEnvironmentVariable('PATH', 'User')
            if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
                Write-Fail "Chocolatey install failed. Install manually from https://chocolatey.org then re-run."
            }
            Write-OK "Chocolatey installed."
        }
        Write-Step "Installing Python 3 via Chocolatey..."
        & choco install python --yes --no-progress
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    $pyver = & python --version 2>&1
    if ($pyver -match '(\d+)\.(\d+)') { Write-OK $pyver } else { Write-Fail "Python install failed." }
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
