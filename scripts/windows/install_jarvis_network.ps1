# Run once as the Windows owner. The task starts at user logon and retries
# after worker failure; it never enables public publishing.
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_jarvis_network.cmd'
if (-not (Test-Path $runner)) { throw 'Jarvis runner was not found' }
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/d /c "' + $runner + '"') -WorkingDirectory (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'JarvisNetwork' -Action $action -Trigger $trigger -Settings $settings -Description 'Local Jarvis QA-only production supervisor' -Force
$voiceRunner = Join-Path $PSScriptRoot 'run_jarvis_voice.cmd'
$voiceAction = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/d /c "' + $voiceRunner + '"') -WorkingDirectory (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Register-ScheduledTask -TaskName 'JarvisVoice' -Action $voiceAction -Trigger $trigger -Settings $settings -Description 'Local restartable Jarvis wake and voice service' -Force
$dashboardRunner = Join-Path $PSScriptRoot 'run_jarvis_dashboard.cmd'
$dashboardAction = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/d /c "' + $dashboardRunner + '"') -WorkingDirectory (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Register-ScheduledTask -TaskName 'JarvisDashboard' -Action $dashboardAction -Trigger $trigger -Settings $settings -Description 'Owner-only Jarvis dashboard (LAN requires TLS)' -Force
