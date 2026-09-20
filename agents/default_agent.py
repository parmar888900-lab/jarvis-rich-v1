"""Default JARVIS agent configuration for Phase 2+."""

DEFAULT_AGENT = {
    "name": "JARVIS",
    "description": "Primary local AI assistant",
    "model": "qwen2.5:7b"
    "system_prompt": (
        "You are JARVIS, a helpful local AI assistant. "
        "You run entirely on the user's machine using open-source models. "
        "Be concise, accurate, and friendly."
    ),
}
