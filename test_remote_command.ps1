$ErrorActionPreference = "Stop"

$baseUrl = "http://10.0.0.57:8000"
$token = (Get-Content "$env:USERPROFILE\.jarvis_remote_token" -Raw).Trim()

Write-Host "=== JARVIS REMOTE TEST ==="

$body = @{
    agent      = "goal"
    task       = "list_goals"
    priority   = "normal"
    parameters = @{}
} | ConvertTo-Json -Depth 10

Write-Host "1. Submitting command..."

$submit = Invoke-RestMethod `
    -Uri "$baseUrl/command" `
    -Method POST `
    -Headers @{ Authorization = "Bearer $token" } `
    -ContentType "application/json" `
    -Body $body

Write-Host "Accepted:" $submit.status
Write-Host "Command ID:" $submit.command_id

$commandId = $submit.command_id

Write-Host "2. Waiting for completion..."

for ($i = 0; $i -lt 15; $i++) {

    Start-Sleep -Seconds 1

    $result = Invoke-RestMethod `
        -Uri "$baseUrl/command/$commandId" `
        -Method GET `
        -Headers @{ Authorization = "Bearer $token" }

    Write-Host "Status:" $result.status

    if ($result.status -eq "completed") {
        Write-Host ""
        Write-Host "JARVIS REMOTE COMMAND PATH: PASS"
        Write-Host "Result:"
        Write-Host $result.result
        exit 0
    }

    if ($result.status -eq "failed") {
        Write-Host ""
        Write-Host "JARVIS REMOTE COMMAND PATH: FAILED"
        Write-Host $result.result
        exit 1
    }
}

Write-Host ""
Write-Host "TEST TIMED OUT"
Write-Host "Final status:" $result.status
exit 2
