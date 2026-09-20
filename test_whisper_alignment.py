import whisper

audio_path = (
    "generated/packages/"
    "Piper_Production_Test/"
    "Piper_Production_Test.wav"
)

print("LOADING MODEL...")

model = whisper.load_model(
    "tiny.en"
)

print("TRANSCRIBING...")

result = model.transcribe(
    audio_path,
    word_timestamps=True,
    fp16=False,
)

print()
print("TEXT:")
print(result["text"])

print()
print("WORD TIMESTAMPS:")

for segment in result["segments"]:

    for word in segment.get(
        "words",
        [],
    ):

        print(
            f"{word['start']:.3f} -> "
            f"{word['end']:.3f} | "
            f"{word['word']!r}"
        )
