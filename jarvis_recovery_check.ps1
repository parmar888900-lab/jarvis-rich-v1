$ErrorActionPreference = "Continue"

$ProjectRoot = "C:\Users\hp\jarvis.ai"
$Python      = "$ProjectRoot\venv\Scripts\python.exe"

$LogDir    = "$ProjectRoot\generated\logs"
$LogFile   = "$LogDir\jarvis_recovery.log"
$JarvisOut = "$LogDir\jarvis_stdout.log"
$JarvisErr = "$LogDir\jarvis_stderr.log"

$HealthUrl = "http://127.0.0.1:8000/docs"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $LogDir |
    Out-Null


function Write-Log {

    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Add-Content `
        -Path $LogFile `
        -Value "[$timestamp] $Message"
}


function Test-Jarvis {

    try {

        $response = Invoke-WebRequest `
            -Uri $HealthUrl `
            -UseBasicParsing `
            -TimeoutSec 10

        return ($response.StatusCode -eq 200)
    }

    catch {

        return $false
    }
}


# ------------------------------------------------------------
# HEALTHY = NOTHING TO DO
# ------------------------------------------------------------

if (Test-Jarvis) {

    Write-Log "Jarvis healthy."

    exit 0
}


Write-Log "Jarvis unhealthy. Beginning recovery."


# ------------------------------------------------------------
# REMOVE STALE UVICORN
# ------------------------------------------------------------

$processes = @(
    Get-CimInstance Win32_Process `
        -ErrorAction SilentlyContinue |
    Where-Object {

        $_.Name -match "^python(?:\.exe)?$" -and
        $_.CommandLine -match "uvicorn\s+backend\.app:app"
    }
)


foreach ($process in $processes) {

    Write-Log (
        "Stopping stale Jarvis PID " +
        $process.ProcessId
    )

    Stop-Process `
        -Id $process.ProcessId `
        -Force `
        -ErrorAction SilentlyContinue
}


Start-Sleep -Seconds 5


# ------------------------------------------------------------
# START FRESH JARVIS
# ------------------------------------------------------------

Write-Log "Starting Jarvis."

try {

    Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "backend.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $JarvisOut `
        -RedirectStandardError $JarvisErr

}

catch {

    Write-Log (
        "Jarvis launch failed: " +
        $_.Exception.Message
    )

    exit 1
}


# ------------------------------------------------------------
# WAIT UP TO 3 MINUTES FOR STARTUP
# ------------------------------------------------------------

for ($i = 1; $i -le 36; $i++) {

    Start-Sleep -Seconds 5

    if (Test-Jarvis) {

        Write-Log (
            "Jarvis recovery successful after " +
            ($i * 5) +
            " seconds."
        )

        exit 0
    }
}


Write-Log (
    "Jarvis did not become healthy within 180 seconds."
)

exit 1
