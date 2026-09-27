from types import SimpleNamespace

from backend.services.voice.wake_phrase import WakePhraseParser
from backend.services.voice.response_formatter import VoiceResponseFormatter


def test_exact_special_phrase_and_primary_wake_are_distinct():
    parser = WakePhraseParser()
    assert parser.parse("Jarvis").detected
    assert parser.parse("Jarvis, how many videos are rendering?").command == (
        "how many videos are rendering?")
    for text in ("Jarvis, wake up — Daddy’s home", "Jarvis wake up, Daddy's home"):
        result = parser.parse(text)
        assert result.detected and result.variant == "special_home"
        assert result.command == ""
    assert parser.parse("Jarvis, wake — Daddy's home").variant == "standard"
    assert not parser.parse("Someone said Jarvis, wake up — Daddy's home").detected
    assert parser.parse("Hey Jarvis, status").command == "status"


def test_special_greeting_rotation_is_controlled_and_addresses_owner():
    formatter = VoiceResponseFormatter()
    special = SimpleNamespace(status="wake_only", wake_variant="special_home")
    assert [formatter.format(special) for _ in range(5)] == [
        "Welcome, sir.", "Welcome, Mr. Parmar.",
        "Good to have you back, sir.", "Welcome back, Mr. Parmar.",
        "Welcome, sir."]
    assert formatter.format(SimpleNamespace(status="wake_only")) == "Yes?"
