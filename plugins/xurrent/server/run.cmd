@echo off
rem Resolve uv: standard install path -> PATH -> error with restart hint.
rem ponytail: this wrapper exists only because .mcp.json can't express a fallback chain.
setlocal
set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if exist "%UV%" goto run
set "UV=uv"
where uv >nul 2>nul
if %errorlevel%==0 goto run
echo Xurrent MCP: 'uv' not found. Run setup.ps1, then fully restart Claude Code ^(logoff/logon or reboot^) so the updated PATH applies. 1>&2
exit /b 1
:run
"%UV%" run --directory "%DIR%" server.py
