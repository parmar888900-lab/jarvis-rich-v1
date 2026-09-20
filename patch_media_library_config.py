from pathlib import Path

path = Path(
    r"backend/services/runtime/runtime_config.py"
)

text = path.read_text(
    encoding="utf-8"
)

############################################################
# Add dataclass field
############################################################

old = '''    generated_dir: Path
    database_url: str
'''

new = '''    generated_dir: Path
    media_library_dir: Path
    database_url: str
'''

if old not in text:
    raise RuntimeError(
        "RuntimeConfig field insertion point not found."
    )

text = text.replace(
    old,
    new,
    1,
)

############################################################
# Add environment configuration
############################################################

old = '''            generated_dir=_read_path(
                "JARVIS_GENERATED_DIR",
                default="generated",
            ),
            database_url=_read_text(
'''

new = '''            generated_dir=_read_path(
                "JARVIS_GENERATED_DIR",
                default="generated",
            ),
            media_library_dir=_read_path(
                "JARVIS_MEDIA_LIBRARY_DIR",
                default="media_library",
            ),
            database_url=_read_text(
'''

if old not in text:
    raise RuntimeError(
        "RuntimeConfig environment insertion point not found."
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8"
)

print(
    "SUCCESS: media library runtime setting installed."
)
