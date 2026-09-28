# Run in the owner's PowerShell session from C:\Users\hp\jarvis.ai.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repo 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = Join-Path $repo '.venv\Scripts\python.exe' }
if (-not (Test-Path $python)) { throw 'Install Python requirements into .venv or venv first.' }
$lanHost = Read-Host 'Enter this Windows machine LAN IP address (from ipconfig)'
if (-not $lanHost) { throw 'A LAN IP address is required.' }
$folder = Join-Path $repo ('generated\state\dashboard-tls-' + ($lanHost -replace '[^A-Za-z0-9.-]', '-'))
if (-not (Test-Path (Join-Path $folder 'dashboard.pem')) -or -not (Test-Path (Join-Path $folder 'dashboard.key'))) {
    & $python (Join-Path $repo 'scripts\configure_dashboard_tls.py') --host $lanHost --directory $folder
    if ($LASTEXITCODE -ne 0) { throw 'Certificate generation failed; existing files were preserved.' }
} else { Write-Host 'Reusing the existing certificate for this exact LAN host.' }
$token = [Environment]::GetEnvironmentVariable('JARVIS_REMOTE_TOKEN', 'User')
if (-not $token -or $token.Length -lt 32) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $token = [Convert]::ToBase64String($bytes)
    [Environment]::SetEnvironmentVariable('JARVIS_REMOTE_TOKEN', $token, 'User')
    Write-Host 'Copy this owner token privately into the iPad dashboard (shown once):'
    Write-Host $token
} else { Write-Host 'Existing owner token retained; no secret printed.' }
[Environment]::SetEnvironmentVariable('JARVIS_DASHBOARD_HOST', $lanHost, 'User')
[Environment]::SetEnvironmentVariable('JARVIS_DASHBOARD_CERT', (Join-Path $folder 'dashboard.pem'), 'User')
[Environment]::SetEnvironmentVariable('JARVIS_DASHBOARD_KEY', (Join-Path $folder 'dashboard.key'), 'User')
Write-Host "Dashboard URL: https://${lanHost}:8765/dashboard"
Write-Host 'Install and fully trust dashboard.pem on the iPad before microphone use. Sign out and back in so the dashboard task inherits these settings.'
