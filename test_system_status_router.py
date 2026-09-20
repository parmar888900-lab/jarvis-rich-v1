from backend.services.voice.command_router import VoiceCommandRouter

router = VoiceCommandRouter()

tests = [
    "jarvis status",
    "what is the progress",
    "how many videos have we made",
    "how are the analytics",
    "how is the channel doing",
    "what happened in the last production cycle",
    "give me an update",
    "goal status",
]

for text in tests:
    result = router.parse(text)

    print(
        text,
        "=>",
        result.status,
        result.agent,
        result.task,
        result.reason,
    )
