$ErrorActionPreference = "Stop"

$baseUrl = "http://10.0.0.57:8000"
$tokenPath = "$env:USERPROFILE\.jarvis_remote_token"

$token = (Get-Content $tokenPath -Raw).Trim()

$headers = @{
    Authorization = "Bearer $token"
}

$body = @{
    command = "show me my goals"
} | ConvertTo-Json

Write-Host "=== LIVE JARVIS REMOTE TEST ==="

$response = Invoke-RestMethod `
    -Uri "$baseUrl/remote/command" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body

Write-Host "Status:" $response.status
Write-Host "Agent:" $response.agent
Write-Host "Task:" $response.task

if (
    $response.status -eq "completed" -and
    $response.agent -eq "goal" -and
    $response.task -eq "list_goals"
) {
    Write-Host ""
    Write-Host "LIVE NATURAL-LANGUAGE REMOTE PATH: PASS"
}
else {
    Write-Host ""
    Write-Host "LIVE NATURAL-LANGUAGE REMOTE PATH: FAIL"
    $response | ConvertTo-Json -Depth 10
}
