from backend.models.generated_content import GeneratedContent
from backend.services.content_validator import ContentValidator


validator = ContentValidator()


safe_content = GeneratedContent(
    title="Safe Test",
    hashtags=["#ai", "#video", "#test"],
    script_lines=[
        "AI video systems are improving rapidly.",
        "Image quality continues to improve.",
        "Creators use AI for several production tasks.",
        "The technology continues to develop.",
    ],
    metadata={},
)


unsafe_content = GeneratedContent(
    title="Unsafe Test",
    hashtags=["#ai", "#video", "#test"],
    script_lines=[
        (
            "AI-generated videos are "
            "indistinguishable from human-made videos."
        ),
        "The technology is improving.",
        "Creators are experimenting with new tools.",
        "The future is guaranteed to change everything.",
    ],
    metadata={},
)


print("SAFE TEST")
print(
    validator.validate(
        safe_content
    )
)

print()

print("UNSAFE TEST")
print(
    validator.validate(
        unsafe_content
    )
)
