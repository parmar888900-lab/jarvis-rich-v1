from pathlib import Path

path = Path("backend/remote_app.py")
text = path.read_text(encoding="utf-8")

old_buttons = '''        <button id="send">
            Send to Jarvis
        </button>
'''

new_buttons = '''        <div class="row">
            <button id="mic" class="secondary">
                🎤 Speak
            </button>

            <button id="send">
                Send to Jarvis
            </button>
        </div>

        <button id="speakToggle" class="secondary">
            Spoken replies: ON
        </button>

        <div class="note" id="voiceNote">
            Tap Speak, say one command, and Jarvis will send it automatically.
        </div>
'''

if old_buttons not in text:
    raise RuntimeError(
        "Command-button section was not found. No changes made."
    )

text = text.replace(
    old_buttons,
    new_buttons,
    1,
)

old_js_start = '''    const sendButton = document.getElementById("send");
    const dot = document.getElementById("dot");
    const connection = document.getElementById("connection");

    const TOKEN_KEY = "jarvis_remote_token";
'''

new_js_start = '''    const sendButton = document.getElementById("send");
    const micButton = document.getElementById("mic");
    const speakToggle = document.getElementById("speakToggle");
    const voiceNote = document.getElementById("voiceNote");
    const dot = document.getElementById("dot");
    const connection = document.getElementById("connection");

    const TOKEN_KEY = "jarvis_remote_token";
    const SPEAK_KEY = "jarvis_spoken_replies";

    let spokenReplies =
        localStorage.getItem(SPEAK_KEY) !== "false";

    let recognition = null;
    let listening = false;
'''

if old_js_start not in text:
    raise RuntimeError(
        "JavaScript variable section was not found."
    )

text = text.replace(
    old_js_start,
    new_js_start,
    1,
)

old_token_line = '''    tokenInput.value = localStorage.getItem(TOKEN_KEY) || "";
'''

new_token_line = '''    tokenInput.value = localStorage.getItem(TOKEN_KEY) || "";

    function updateSpeakButton() {
        speakToggle.textContent =
            "Spoken replies: " +
            (spokenReplies ? "ON" : "OFF");
    }

    updateSpeakButton();

    function getSpokenReply(data) {
        if (
            data &&
            data.result &&
            typeof data.result.message === "string" &&
            data.result.message.trim()
        ) {
            return data.result.message.trim();
        }

        if (
            data &&
            typeof data.message === "string" &&
            data.message.trim()
        ) {
            return data.message.trim();
        }

        if (
            data &&
            data.status === "completed"
        ) {
            return "Command completed successfully.";
        }

        if (
            data &&
            data.status === "confirmation_required"
        ) {
            return "This command requires confirmation.";
        }

        if (
            data &&
            typeof data.reason === "string" &&
            data.reason
        ) {
            return "Command not completed. " +
                data.reason.replaceAll("_", " ");
        }

        return "Jarvis returned a response.";
    }

    function speakReply(text) {
        if (
            !spokenReplies ||
            !text ||
            !("speechSynthesis" in window)
        ) {
            return;
        }

        window.speechSynthesis.cancel();

        const utterance =
            new SpeechSynthesisUtterance(text);

        utterance.lang =
            navigator.language || "en-US";

        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        window.speechSynthesis.speak(
            utterance
        );
    }
'''

if old_token_line not in text:
    raise RuntimeError(
        "Token initialization section was not found."
    )

text = text.replace(
    old_token_line,
    new_token_line,
    1,
)

old_send_listener = '''    sendButton.addEventListener("click", async () => {
'''

new_send_listener = '''    speakToggle.addEventListener(
        "click",
        () => {
            spokenReplies = !spokenReplies;

            localStorage.setItem(
                SPEAK_KEY,
                spokenReplies
                    ? "true"
                    : "false"
            );

            updateSpeakButton();

            if (spokenReplies) {
                speakReply(
                    "Spoken replies enabled."
                );
            }
        }
    );

    sendButton.addEventListener("click", async () => {
'''

if old_send_listener not in text:
    raise RuntimeError(
        "Send-button handler was not found."
    )

text = text.replace(
    old_send_listener,
    new_send_listener,
    1,
)

old_response_section = '''            output.textContent =
                JSON.stringify(data, null, 2);

            if (response.status === 401) {
'''

new_response_section = '''            output.textContent =
                JSON.stringify(data, null, 2);

            speakReply(
                getSpokenReply(data)
            );

            if (response.status === 401) {
'''

if old_response_section not in text:
    raise RuntimeError(
        "Response-rendering section was not found."
    )

text = text.replace(
    old_response_section,
    new_response_section,
    1,
)

old_health_end = '''    checkHealth();
</script>
'''

new_health_end = '''    function setupSpeechRecognition() {
        const Recognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        if (!Recognition) {
            micButton.disabled = true;
            micButton.textContent =
                "Voice input unavailable";

            voiceNote.textContent =
                "This browser does not expose speech recognition. " +
                "Typing still works.";

            return;
        }

        recognition = new Recognition();

        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        recognition.lang =
            navigator.language || "en-US";

        recognition.onstart = () => {
            listening = true;

            micButton.disabled = true;
            micButton.textContent =
                "Listening...";

            voiceNote.textContent =
                "Listening for one command.";
        };

        recognition.onresult = (event) => {
            const transcript =
                event.results[0][0].transcript.trim();

            commandInput.value = transcript;

            voiceNote.textContent =
                'Heard: "' +
                transcript +
                '"';

            if (transcript) {
                setTimeout(
                    () => sendButton.click(),
                    150
                );
            }
        };

        recognition.onerror = (event) => {
            voiceNote.textContent =
                "Voice input error: " +
                event.error;

            if (
                event.error === "not-allowed" ||
                event.error === "service-not-allowed"
            ) {
                voiceNote.textContent +=
                    ". Check Safari microphone permissions.";
            }
        };

        recognition.onend = () => {
            listening = false;

            micButton.disabled = false;
            micButton.textContent =
                "🎤 Speak";
        };

        micButton.addEventListener(
            "click",
            () => {
                if (
                    recognition &&
                    !listening
                ) {
                    try {
                        recognition.start();
                    } catch (error) {
                        voiceNote.textContent =
                            "Could not start microphone: " +
                            error.message;
                    }
                }
            }
        );
    }

    setupSpeechRecognition();
    checkHealth();
</script>
'''

if old_health_end not in text:
    raise RuntimeError(
        "Dashboard script ending was not found."
    )

text = text.replace(
    old_health_end,
    new_health_end,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("IPAD VOICE PATCH COMPLETE")
