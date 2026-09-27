# Operate Jarvis locally on Windows

Use PowerShell in `C:\Users\hp\jarvis.ai`. Public publishing stays off. The
Network V1 worker can make local renders and persist QA jobs; it cannot approve
a video against the six-reference perceptual gate or upload it automatically.

## First setup

```powershell
cd C:\Users\hp\jarvis.ai
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\check_jarvis.py
```

The check prints missing local dependencies, disk space, persisted channels,
job states and the public publishing flag. Install/configure only the missing
models, FFmpeg, Piper, Ollama and media providers your intended format uses.
An empty channel list means the network has no work. To register a real local
editorial identity (this does not create a YouTube account):

```powershell
.\.venv\Scripts\python.exe scripts\configure_network_channel.py --name SpaceDecoded --niche science --editorial "Evidence-first Webb engineering" --allow-topic Webb --timezone America/Edmonton --activate
```

For Windows-only dashboard access, generate a private owner token in a local
PowerShell session and persist it for scheduled tasks. Do not share or commit
the token:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$ownerToken = [Convert]::ToBase64String($bytes)
[Environment]::SetEnvironmentVariable('JARVIS_REMOTE_TOKEN', $ownerToken, 'User')
```

Copy `$ownerToken` privately into the dashboard owner-token field. This token
is stored only in that browser tab's session storage. Sign out and back in
after changing user environment variables so scheduled tasks inherit them.

## Start, check, pause

```powershell
& .\scripts\windows\install_jarvis_network.ps1
Start-ScheduledTask -TaskName JarvisDashboard
Start-ScheduledTask -TaskName JarvisNetwork
Start-ScheduledTask -TaskName JarvisVoice
.\.venv\Scripts\python.exe scripts\check_jarvis.py
```

At each user logon the three tasks start independently and retry on exit.
The installer binds each task to the signed-in owner session and permits
startup while the laptop is on battery. Existing tasks must be reinstalled
with the command above to receive these settings. Task Scheduler startup
still requires a real logon/reboot check on this Windows machine.
Local dashboard: `http://127.0.0.1:8765/dashboard`. A `CONNECTED` badge with
a recent sample time confirms current status. `STALE DATA`, `RECONNECTING` or
`OFFLINE` does not mean the displayed sample is current. The AI core, channels,
jobs, human actions, analytics and system panels read the owner API; empty
sections show no records rather than invented work. `TALK TO JARVIS` uses the
same owner API and needs a working microphone, Whisper, FFmpeg and Piper.

```powershell
.\.venv\Scripts\python.exe scripts\control_network.py pause_production
.\.venv\Scripts\python.exe scripts\control_network.py resume_production
.\.venv\Scripts\python.exe scripts\control_network.py pause_channel --channel-id <ID_FROM_DASHBOARD>
.\.venv\Scripts\python.exe scripts\control_network.py resume_channel --channel-id <ID_FROM_DASHBOARD>
```

The dashboard also has authenticated pause/resume controls. Resumes require
confirmation. No control enables public publishing. To stop service processes
for maintenance, use `Stop-ScheduledTask` for `JarvisNetwork`, `JarvisVoice`
and `JarvisDashboard`. Disable their scheduled tasks if they must stay off
after the next logon. Rerun `Start-ScheduledTask` to recover an individual
service. The supervisor preserves persistent job state across restarts.

Read `generated\logs\network-supervisor.log`, `voice-runtime.log`,
`dashboard.log`, `network-plan.log` and `network-job.log`. The last two rotate
at 20 MiB with three backups. Generated video paths are recorded under each
job's `artifacts.render` and production package lineage; typical media lives
in `generated\videos` and `generated\renders`. Inspect real QA results and
the MP4 before any future release decision. Open `HUMAN ACTION REQUIRED` in
the dashboard for the exact blocker and resume step.

If an earlier same-day planning attempt recorded zero jobs before a topic
adapter repair, keep that allocation as audit history. For one private QA
commissioning job, use the existing active channel ID and a bounded child:

```powershell
.\.venv\Scripts\python.exe scripts\run_bounded.py --stage network-commission --timeout 300 --heartbeat 15 --log generated\logs\network-commission.log -- .venv\Scripts\python.exe scripts\commission_network_job.py 2fef2173-b5da-43bc-8045-f96eaba8d14b
.\.venv\Scripts\python.exe scripts\check_jarvis.py
```

The command selects within the channel's topic rules, researches sources,
checks measured scores and originality, and persists at most one job for its
local day. It never changes the prior allocation or enables publishing. The
running supervisor picks up the queued job; `network-job.log` and the live
dashboard show its progress. A legitimate weak or unavailable topic leaves
no job. Do not repeat expensive production outside the supervisor.

## iPad on the same private LAN

The iPad cannot use Windows `localhost`. An explicit LAN binding requires a
32-character owner token and TLS. In PowerShell on Windows, run:

```powershell
& .\scripts\windows\configure_dashboard_lan.ps1
```

Enter the Windows machine's current private LAN IP from `ipconfig`. The
script creates a self-signed certificate and private key under a host-specific
`generated\state\dashboard-tls-<LAN-IP>` directory, configures the user-level LAN binding, and
prints `https://<LAN-IP>:8765/dashboard`. The owner must transfer the
certificate (never the key) to the iPad and install/full-trust it in iPadOS
settings. This is a device security action Jarvis cannot perform. Permit the
dashboard port only on a trusted private LAN in Windows Firewall; never port
forward it to the public Internet. The iPad and Windows host must be on the
same LAN. Enter the private owner token in the iPad dashboard. Safari's Share
menu can add the page to Home Screen. The app refetches authoritative state
after foregrounding and reconnecting. iPad microphone access needs the
certificate fully trusted; typed commands remain available otherwise. Sign out
and back in on Windows after LAN setup so the scheduled dashboard task sees
the new environment variables.

Do not mistake a Safari certificate warning for completed trust. If the LAN
IP changes, rerun the LAN configuration script and trust the new certificate.
The old private files are preserved. Actual iPad Safari layout, audio capture and trust
must be checked on the user's device.

## Safety and limits

`scripts/check_jarvis.py` must report `public_publishing_enabled: false` and
`network_publishing_enabled: false`. If either is true, pause production and
investigate configuration before continuing. The existing Rich V1 perceptual
gate remains FAIL; automatic QA approval and public uploads are not enabled.
Google login, OAuth consent, verification, quota and financial/legal actions
stay human-only. The dashboard has an unauthenticated shell but gives no live
network data or write access until the owner token is provided. Keep the
Windows machine awake and connected for continuous production; Task Scheduler
starts at user logon, so this setup does not run while no user has logged on.
