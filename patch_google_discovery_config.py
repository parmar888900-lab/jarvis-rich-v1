from pathlib import Path

path = Path(
    r"backend/config.py"
)

text = path.read_text(
    encoding="utf-8"
)

anchor = '''    # YouTube API
    youtube_api_key: str = ""
'''

replacement = '''    # YouTube API
    youtube_api_key: str = ""

    # Google web discovery
    google_search_api_key: str = ""
    google_search_cx: str = ""
'''

if anchor not in text:
    raise RuntimeError(
        "Google config insertion point not found."
    )

text = text.replace(
    anchor,
    replacement,
    1,
)

path.write_text(
    text,
    encoding="utf-8"
)

print(
    "SUCCESS: Google discovery config installed."
)
