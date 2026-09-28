# Jarvis private commissioning: Windows and human actions

This is the physical-machine handoff for `C:\Users\hp\jarvis.ai` on
`sprint/rich-v1-20260920`. The Work container has no access to that machine's
SQLite, cached media, credentials, microphone, speaker, task scheduler or
iPad. Repository tests do **not** establish a real QA video or a Rich V1
perceptual PASS. Keep public and Network publishing OFF. Never edit SQLite or
delete the sealed same-day zero allocation.

The recovered R14 artifact was technically probed at 33.30 seconds,
1080×1920, 30 fps, H.264/AAC, 17,872,064 bytes, SHA-256
`1d8612d01f5b1b5abdc85a0ea0657a26d4bc1b99636867cd9c29f8380cbf11d3`.
Its inspected contact frames still show repeated opening chamber shots and
source text competing with captions. It is **Rich V1 FAIL** until a later
actual render clears the six-reference perceptual bar. This recovered Work
artifact is not assumed present on the Windows host.

The current matcher now prefers a visibly different opening frame only when
another **strictly eligible** clip scores within .025 of the best semantic
match. That code has a focused regression test, but no later real render has
verified the viewer-facing effect. Do not call R14 improved retroactively.

## 1. Pull, inspect, then run one private validation command

In PowerShell on Windows, from the existing repository:

```powershell
cd C:\Users\hp\jarvis.ai
git status --short --branch
git fetch origin
git pull --ff-only origin sprint/rich-v1-20260920
.\venv\Scripts\python.exe scripts\commission_and_validate.py 2fef2173-b5da-43bc-8045-f96eaba8d14b
```

Expected: branch `sprint/rich-v1-20260920` and a fast-forward. The single
command runs the checker, enforces both publishing flags OFF, allows only
the unrelated missing YouTube analytics token for private QA, bounds topic
research to 360 seconds, observes the persisted job and supervisor for at
most 7500 seconds, and probes any final MP4 with a separate 30-second
`ffprobe` watchdog. It writes shareable `evidence.json` and `summary.txt`
in a timestamped `generated\reports\private-commission-*` folder. Raw
stage logs remain separately under `generated\logs\private-commission\*`
for local diagnosis and should not be shared without reviewing for sensitive
provider output. The report records actual candidate scores, job state, render
metadata and hash without tokens. `QA` is technical admission only, never
perceptual approval. If `git pull`
reports local modifications, stop before overwriting them and retain the
output of `git status --short --branch`; do not reset or apply the old stash.
If the checker reports either publishing flag true, the wrapper stops before
commissioning. Pause production via
`.\venv\Scripts\python.exe scripts\control_network.py pause_production`
and do not commission. If dependencies are missing, retain the report; no
Google OAuth refresh is needed merely for private local QA.
The readiness check now also requires `ffprobe`, because the private QA
boundary probes the completed video with it. A missing `ffprobe` is a real
machine dependency to fix before running a costly render.

## 2. Understand the private result (no second commissioning command)

Use the existing ACTIVE SpaceDecoded ID. This is bounded, source-backed and
tries up to four eligible allowed Webb alternatives; it may correctly produce
no job. It leaves the prior zero allocation untouched.

The one command above records actual `production_score`, `quality`,
`research_confidence`, `evidence`, `visual_supply`, `visual`, `weakest`,
`source_count`, `.55` threshold, and rejection/eligibility reason. Originality
is reported as pending until its transactional reservation. Then either
`private_qa_job=<ID> state=QUEUED`, an idempotent existing job ID, or a safe
“No channel-vetted source-backed original topic cleared the .55 gate”. A
correct no-job result is a quality-gate outcome, not permission to lower the
threshold. A nonzero exit means a boundary is unresolved; share
`evidence.json` and `summary.txt`. Only inspect raw logs locally, sharing
redacted excerpts if needed. Do not repeat a job already queued/running.

The original real Windows candidate, “How James Webb Space Telescope unfolded
its mirror after launch”, had production score 72.25/100 and visual supply
72/100. Its exact research confidence was **not** captured in the prior
Windows log; the new diagnostic records it on the next actual research run.
It was below the unchanged weakest-component .55 cutoff. Do not infer or
invent the absent value.

## 3. Local QA video and lineage

The wrapper observes the scheduled supervisor. If its heartbeat was stale,
it runs one bounded single-instance supervisor tick; the OS lock prevents
overlapping workers. A render has a 7200-second worker limit and the supervisor
records repair/failure rather than uploading. If the evidence ends at
`job_queued` or `job_repair`, examine the recorded retry/state; never start
a duplicate production child.

```powershell
.\venv\Scripts\python.exe scripts\check_jarvis.py
Get-Content generated\logs\network-supervisor.log -Tail 60
Get-Content generated\logs\network-job.log -Tail 80
```

Open the authenticated dashboard at `http://127.0.0.1:8765/dashboard` and
check the actual job's stage, `artifacts.render`, and `lineage` including
`render_sha256`, `script_sha256`, `evidence_ids` where available, and the
package directory. `QA` means a local technical render was admitted for
review. It is **not** benchmark approval. `REPAIR` or `FAILED` requires the
job log and exact failure reason; the supervisor retries only within its
bounded policy. If the task is queued but no heartbeat becomes fresh, run
`Get-ScheduledTaskInfo -TaskName JarvisNetwork` and retain the task result.
Do not restart the production child manually while the supervisor owns it.

The wrapper already records `ffprobe` metadata and SHA-256. For independent
verification on a final MP4, use the recorded path (do not guess a filename):

```powershell
ffprobe -v error -show_entries format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate -of json "<ARTIFACTS.RENDER_PATH>"
Get-FileHash -Algorithm SHA256 "<ARTIFACTS.RENDER_PATH>"
```

Expected: nonzero duration, video and audio streams, portrait 1080×1920 and
30 fps for this Rich V1 path, with a real SHA-256. If `ffprobe` is not on PATH,
use its installed full path; do not infer validity from an `.mp4` extension.
Physically watch and listen on a phone-sized display. Check hook, script,
visual relevance and escalation, repeats, annotation/caption collision,
motion, music/ducking, narration, black frames and ending. Compare against
all six benchmark formats. Record PASS only if it truly reaches that bar;
otherwise record the concrete viewer-facing defect. Public release remains
disabled either way. Share the MP4 or representative clips and the QA notes
for later review if desired, without publishing.

## 4. Voice, scheduled startup and iPad (can be batched after step 1)

Run the existing task installer from the owner session only if its definitions
need refreshing, then physically sign out/in or restart once. The process
scoped policy bypass does not change the machine's policy.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\windows\install_jarvis_network.ps1"
Get-ScheduledTaskInfo -TaskName JarvisNetwork
Get-ScheduledTaskInfo -TaskName JarvisVoice
Get-ScheduledTaskInfo -TaskName JarvisDashboard
```

After actual logon, run `scripts\check_jarvis.py` with the real venv above;
expected supervisor and voice heartbeats are `fresh`. Open the authenticated
dashboard and verify `CONNECTED` with a recent sample timestamp. A queued
Scheduled Task or stale heartbeat is not a successful startup. For failure,
retain `Get-ScheduledTaskInfo` outputs and the tails of
`generated\logs\network-supervisor.log`, `voice-runtime.log`, `dashboard.log`.
Direct runners, only for isolated diagnosis, are
`scripts\windows\run_jarvis_network.cmd`, `run_jarvis_voice.cmd` and
`run_jarvis_dashboard.cmd`; do not launch duplicates over healthy tasks.

Physically test the laptop microphone and speaker: say **“Jarvis”**, then
**“Jarvis, wake up — Daddy's home”**, and use persistent **TALK TO JARVIS**.
Expected special greetings rotate “Welcome, sir.” and “Welcome, Mr. Parmar.”
among four controlled variants. Check Piper playback, STT, router response,
and no TTS self-trigger. On failure, retain only safe `voice-runtime.log`
error/status lines, never raw spoken secrets. Hardware/device switching and
the British voice's perceived quality cannot be proven in this container.

For iPad on the same trusted LAN, if not yet configured, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\windows\configure_dashboard_lan.ps1"
```

Use the real private Windows LAN IP. The script reuses an existing owner token
and host-specific certificate; never print or share the current token in a
bug report. Sign out/in to refresh scheduled-task environment. Transfer **only
the certificate**, never its private key, to the iPad and fully trust it in
iPadOS. Open the printed `https://<LAN-IP>:8765/dashboard` in Safari, enter
the owner token privately, verify `CONNECTED` and a fresh sample, background
and foreground Safari, briefly disconnect/reconnect Wi-Fi, and confirm
`OFFLINE`/`STALE DATA`/`RECONNECTING` never masquerade as live. Test portrait,
landscape, touch controls, TALK TO JARVIS microphone permission and speech.
Safari's Share menu can Add to Home Screen. If Safari warns about the
certificate or microphone is unavailable, resolve iPad trust/permission and
the private-LAN firewall route; never port-forward Jarvis to the Internet.
These are physical device checks, not repository test passes.

## 5. Channels 61–100 and external Google actions

The repository contains **proposals only**, all PLANNED and paused, in
`backend/services/network/channel_blueprints.py`. No accounts, OAuth grants,
branding images or channel rows were created for 61–100. The owner supplied
the real first-60 names and handles; they are stored as **external account-side
planning data**, not registered IDs, in
`config/channel_roster_1_60.user_supplied.json`. The full 100-name/handle
comparison was completed in Work, including a genuine collision at proposed
#64; that proposal alone was renamed to `CellChemistryLab`. Recheck with:

```powershell
.\venv\Scripts\python.exe scripts\validate_channel_blueprints.py --existing-roster config\channel_roster_1_60.user_supplied.json
```

The roster is a JSON array of objects with `name` and optional `handle`.
Expected `all_100_checked: true`, `known_existing: 60`, and no collision.
Check handle
availability and branding with the actual services; proposed handles are not
reserved. Account creation, Google login, OAuth consent, phone/identity
verification, tax/payment and platform restrictions are HUMAN_ACTION_REQUIRED
only if later separately authorized. They are not needed for local QA.

This user-supplied roster does not establish OAuth, repository registration,
account capabilities or current handle availability. Those facts require
authorized account-side verification only if later needed.

## Safety after each step

`scripts\check_jarvis.py` must continue to show both publishing flags false.
There is no authorized public upload, no OAuth refresh required for private
QA, no alteration of the sealed zero allocation, and no automatic Rich V1
perceptual approval. Keep the old runtime-state stash unapplied.
