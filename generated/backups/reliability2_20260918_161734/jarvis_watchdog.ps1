param()

$ErrorActionPreference = "Continue"

$ProjectRoot = "C:\Users\hp\jarvis.ai"
$Python = "$ProjectRoot\venv\Scripts\python.exe"

$LogDir = "$ProjectRoot\generated\logs"

$WatchdogLog = "$LogDir\jarvis_watchdog.log"
$JarvisOut = "$LogDir\jarvis_stdout.log"
$JarvisErr = "$LogDir\jarvis_stderr.log"

# /docs is a verified live endpoint in this Jarvis installation.
$HealthUrl = "http://127.0.0.1:8000/docs"

$CheckSeconds = 60
$FailureLimit = 3

$StartupTimeoutSeconds = 180
$StartupPollSeconds = 5

New-Item `
    -ItemType Directory `
    -Force `
    -Path $LogDir |
    Out-Null


function Write-WatchdogLog {

    param(
        [string]$Message
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    $line = "[$timestamp] $Message"

    Add-Content `
        -Path $WatchdogLog `
        -Value $line

    Write-Host $line
}


function Test-JarvisHealth {

    try {

        $response = Invoke-WebRequest `
            -Uri $HealthUrl `
            -UseBasicParsing `
            -TimeoutSec 10

        return (
            $response.StatusCode -ge 200 -and
            $response.StatusCode -lt 400
        )

    }
    catch {

        return $false
    }
}


function Get-JarvisProcesses {

    return @(
        Get-CimInstance Win32_Process `
            -ErrorAction SilentlyContinue |
        Where-Object {

            $_.Name -match "^python(?:\.exe)?$" -and
            $_.CommandLine -match "uvicorn\s+backend\.app:app"
        }
    )
}


function Stop-Jarvis {

    $processes = Get-JarvisProcesses

    foreach ($process in $processes) {

        Write-WatchdogLog (
            "Stopping unhealthy Jarvis PID " +
            $process.ProcessId
        )

        Stop-Process `
            -Id $process.ProcessId `
            -Force `
            -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 5
}


function Start-Jarvis {

    Write-WatchdogLog "Starting Jarvis."

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

        Write-WatchdogLog (
            "Could not launch Jarvis: " +
            $_.Exception.Message
        )

        return $false
    }


    $elapsed = 0

    while ($elapsed -lt $StartupTimeoutSeconds) {

        Start-Sleep -Seconds $StartupPollSeconds

        $elapsed += $StartupPollSeconds


        if (Test-JarvisHealth) {

            Write-WatchdogLog (
                "Jarvis healthy after " +
                $elapsed +
                " seconds."
            )

            return $true
        }


        $processes = Get-JarvisProcesses

        if ($processes.Count -eq 0) {

            Write-WatchdogLog (
                "Jarvis exited during startup."
            )

            return $false
        }
    }


    Write-WatchdogLog (
        "Jarvis did not become healthy within " +
        $StartupTimeoutSeconds +
        " seconds."
    )

    return $false
}


Write-WatchdogLog "Watchdog started."

$failures = 0


while ($true) {

    try {

        if (Test-JarvisHealth) {

            if ($failures -gt 0) {

                Write-WatchdogLog (
                    "Jarvis recovered without restart."
                )
            }

            $failures = 0
        }

        else {

            $failures++

            Write-WatchdogLog (
                "Jarvis health failure " +
                $failures +
                "/" +
                $FailureLimit +
                "."
            )


            if ($failures -ge $FailureLimit) {

                Write-WatchdogLog (
                    "Jarvis considered unhealthy. Restarting."
                )

                Stop-Jarvis

                $started = Start-Jarvis

                if ($started) {

                    Write-WatchdogLog (
                        "Automatic Jarvis recovery completed."
                    )
                }

                else {

                    Write-WatchdogLog (
                        "Recovery attempt failed. " +
                        "Watchdog remains active and will retry."
                    )
                }

                $failures = 0
            }
        }
    }

    catch {

        Write-WatchdogLog (
            "Watchdog iteration error: " +
            $_.Exception.Message
        )
    }


    Start-Sleep -Seconds $CheckSeconds
}
