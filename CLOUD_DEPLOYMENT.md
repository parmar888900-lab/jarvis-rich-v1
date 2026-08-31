# Jarvis Cloud Runtime

Jarvis runs as a Linux FastAPI service.

Persistent runtime data lives outside the application image.

Expected persistent paths:

/data/generated
/data/database
/data/models
/data/secrets
/data/comfyui/output

External runtime services:

- Ollama / Qwen
- ComfyUI / FLUX

Local runtime binaries:

- Piper
- Whisper
- FFmpeg

The production API starts with:

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

Production should remain private-upload-only during initial cloud testing.
