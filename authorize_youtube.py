"""One-time YouTube OAuth authorization."""

from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


def main():
    publisher = YoutubePublisher()

    print("=" * 70)
    print("JARVIS YOUTUBE AUTHORIZATION")
    print()
    print(
        "This opens Google OAuth in your browser."
    )
    print(
        "No video will be uploaded."
    )
    print()

    result = publisher.authorize_interactively()

    print()
    print(
        "Authorization result:",
        result,
    )

    channel = publisher.get_authorized_channel()

    print()
    print("=" * 70)
    print("AUTHORIZED YOUTUBE CHANNEL")
    print()
    print(
        "Channel title:",
        channel["channel_title"],
    )
    print(
        "Channel ID:",
        channel["channel_id"],
    )
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
