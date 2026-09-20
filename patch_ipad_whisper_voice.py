from pathlib import Path

path = Path(
    "backend/remote_app.py"
)

text = path.read_text(
    encoding="utf-8"
)

# Add hidden iOS capture input directly after the textarea.
old = '''        ></textarea>

        <div class="row">
'''

new = '''        ></textarea>

        <input
            id="voiceCapture"
            type="file"
            accept="audio/*"
            capture
            hidden
        >

        <div class="row">
'''

if old not in text:
    raise RuntimeError(
        "Could not find command textarea."
    )

text = text.replace(
    old,
    new,
    1,
)

# Add JS reference.
old = '''    const micButton = document.getElementById("mic");
    const speakToggle = document.getElementById("speakToggle");
'''

new = '''    const micButton = document.getElementById("mic");
    const voiceCapture = document.getElementById("voiceCapture");
    const speakToggle = document.getElementById("speakToggle");
'''

if old not in text:
    raise RuntimeError(
        "Could not find mic JavaScript variables."
    )

text = text.replace(
    old,
    new,
    1,
)

# Remove old Web Speech recognition state.
text = text.replace(
    '''    let recognition = null;
    let listening = false;

''',
    "",
    1,
)

start_marker = '''    function setupSpeechRecognition() {'''
end_marker = '''    setupSpeechRecognition();
    checkHealth();
'''

start = text.find(
    start_marker
)

if start == -1:
    raise RuntimeError(
        "Old speech recognition function not found."
    )

end = text.find(
    end_marker,
    start,
)

if end == -1:
    raise RuntimeError(
        "Old speech recognition ending not found."
    )

replacement = r'''    function setVoiceBusy(busy) {
        micButton.disabled = busy;

        micButton.textContent =
            busy
                ? "Processing voice..."
                : "🎤 Speak";
    }

    async function sendVoiceRecording(file) {
        const token = tokenInput.value.trim();

        if (!token) {
            output.textContent =
                "Remote token is required.";

            return;
        }

        if (!file) {
            return;
        }

        setVoiceBusy(true);

        voiceNote.textContent =
            "Sending recording to Whisper...";

        output.textContent =
            "Transcribing voice command...";

        try {
            const response = await fetch(
                "/remote/voice",
                {
                    method: "POST",
                    headers: {
                        "Authorization":
                            "Bearer " + token,
                        "Content-Type":
                            file.type ||
                            "application/octet-stream"
                    },
                    body: file
                }
            );

            let data;

            try {
                data = await response.json();
            } catch {
                data = {
                    status: "error",
                    reason:
                        "Jarvis returned a non-JSON response."
                };
            }

            if (
                typeof data.transcript === "string" &&
                data.transcript.trim()
            ) {
                commandInput.value =
                    data.transcript.trim();

                voiceNote.textContent =
                    'Heard: "' +
                    data.transcript.trim() +
                    '"';
            } else {
                voiceNote.textContent =
                    "No spoken command detected.";
            }

            output.textContent =
                JSON.stringify(
                    data,
                    null,
                    2
                );

            speakReply(
                getSpokenReply(data)
            );

            if (response.status === 401) {
                setConnection(
                    "error",
                    "Authentication rejected"
                );
            } else if (response.ok) {
                setConnection(
                    "online",
                    "Jarvis connected"
                );
            }

        } catch (error) {
            output.textContent =
                "Voice command failed: " +
                error.message;

            voiceNote.textContent =
                "Voice command failed.";

            setConnection(
                "error",
                "Jarvis unavailable"
            );

        } finally {
            setVoiceBusy(false);

            /*
             * Reset the input so recording the same
             * kind of file twice still triggers change.
             */
            voiceCapture.value = "";
        }
    }

    micButton.addEventListener(
        "click",
        () => {
            const token =
                tokenInput.value.trim();

            if (!token) {
                output.textContent =
                    "Remote token is required.";
                return;
            }

            voiceNote.textContent =
                "Record one command, then finish the recording.";

            voiceCapture.click();
        }
    );

    voiceCapture.addEventListener(
        "change",
        () => {
            const file =
                voiceCapture.files &&
                voiceCapture.files[0];

            if (file) {
                sendVoiceRecording(file);
            }
        }
    );

    checkHealth();
'''

text = (
    text[:start]
    + replacement
    + text[
        end + len(end_marker):
    ]
)

path.write_text(
    text,
    encoding="utf-8"
)

print(
    "IPAD WHISPER VOICE PATCH COMPLETE"
)
