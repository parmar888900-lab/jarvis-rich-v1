$ErrorActionPreference = "Stop"

$jarvisRoot = "C:\Users\hp\jarvis.ai"
$jarvisPython = "$jarvisRoot\venv\Scripts\python.exe"

$comfyRoot = "C:\Users\hp\ComfyUI"
$comfyPython = "$comfyRoot\venv\Scripts\python.exe"

$ollamaExe = "C:\Users\hp\AppData\Local\Programs\Ollama\ollama.exe"

function Test-Port {
    param(
        [string]$HostName,
        [int]$Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect(
            $HostName,
            $Port,
            $null,
            $null
        )

        $success = $iar.AsyncWaitHandle.WaitOne(1500)

        if (-not $success) {
            $client.Close()
            return $false
        }

        $client.EndConnect($iar)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

Write-Host "=== JARVIS STARTUP ==="

# -------------------------
# OLLAMA
# -------------------------

if (-not (Test-Port "127.0.0.1" 11434)) {
    Write-Host "Starting Ollama..."

    Start-Process `
        -FilePath $ollamaExe `
        -ArgumentList "serve" `
        -WindowStyle Minimized
}
else {
    Write-Host "Ollama already running."
}

$deadline = (Get-Date).AddMinutes(2)

while (-not (Test-Port "127.0.0.1" 11434)) {
    if ((Get-Date) -gt $deadline) {
        throw "Ollama failed to start."
    }

    Start-Sleep -Seconds 2
}

Write-Host "Ollama ready."

# -------------------------
# COMFYUI
# -------------------------

if (-not (Test-Port "127.0.0.1" 8188)) {
    Write-Host "Starting ComfyUI..."

    Start-Process `
        -FilePath $comfyPython `
        -ArgumentList "`"$comfyRoot\main.py`"" `
        -WorkingDirectory $comfyRoot `
        -WindowStyle Minimized
}
else {
    Write-Host "ComfyUI already running."
}

$deadline = (Get-Date).AddMinutes(5)

while (-not (Test-Port "127.0.0.1" 8188)) {
    if ((Get-Date) -gt $deadline) {
        throw "ComfyUI failed to start."
    }

    Start-Sleep -Seconds 3
}

Write-Host "ComfyUI ready."

# -------------------------
# PRODUCTION ENVIRONMENT
# -------------------------

$env:JARVIS_AUTONOMOUS_PRODUCTION = "true"
$env:JARVIS_PRODUCTION_INTERVAL_SECONDS = "21600"

# -------------------------
# REMOTE AUTHENTICATION
# -------------------------

$remoteTokenPath = "$env:USERPROFILE\.jarvis_remote_token"

if (-not (Test-Path $remoteTokenPath)) {
    throw "Jarvis remote token file is missing."
}

$remoteToken = (
    Get-Content $remoteTokenPath -Raw
).Trim()

if ($remoteToken.Length -lt 32) {
    throw "Jarvis remote token is invalid."
}

$env:JARVIS_REMOTE_TOKEN = $remoteToken

Write-Host "Jarvis remote authentication ready."

# -------------------------
# VOICE RUNTIME
# -------------------------

$voiceRunning = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^python(w)?\.exe$" -and
        $_.CommandLine -match `
            "backend\.services\.voice\.voice_runtime"
    } |
    Select-Object -First 1

if ($voiceRunning) {
    Write-Host "Jarvis voice runtime already running."
}
else {
    Write-Host "Starting Jarvis voice runtime..."

    Start-Process `
        -FilePath $jarvisPython `
        -ArgumentList `
            "-m backend.services.voice.voice_runtime" `
        -WorkingDirectory $jarvisRoot `
        -WindowStyle Hidden
}

# -------------------------
# JARVIS API
# -------------------------


# -------------------------
# REMOTE API
# -------------------------

if (-not (Test-Port "127.0.0.1" 8001)) {
    Write-Host "Starting authenticated Jarvis remote API..."

    Start-Process `
        -FilePath $jarvisPython `
        -ArgumentList "-m uvicorn backend.remote_app:app --host 0.0.0.0 --port 8001" `
        -WorkingDirectory $jarvisRoot `
        -WindowStyle Hidden

    $deadline = (Get-Date).AddMinutes(1)

    while (-not (Test-Port "127.0.0.1" 8001)) {
        if ((Get-Date) -gt $deadline) {
            throw "Jarvis remote API failed to start."
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "Jarvis remote API ready."
}
else {
    Write-Host "Jarvis remote API already running."
}

if (Test-Port "127.0.0.1" 8000) {
    Write-Host "Jarvis is already running."
    Write-Host "=== JARVIS STARTUP COMPLETE ==="
    exit 0
}

Write-Host "Starting Jarvis..."
Write-Host "Production interval: 21600 seconds / 6 hours"

Set-Location $jarvisRoot

& $jarvisPython `
    -m uvicorn `
    backend.app:app `
    --host 127.0.0.1 `
    --port 8000


