"""Voice services, loaded on demand so headless production needs no audio device."""
from importlib import import_module

_EXPORTS = {
    'VoiceAssistant': 'assistant',
    'VoiceAssistantResult': 'assistant',
    'VoiceAssistantResponse': 'assistant',
    'VoiceConfirmationDecision': 'confirmation',
    'VoiceConfirmationManager': 'confirmation',
    'AudioCapture': 'audio_capture',
    'VoiceCommandExecutor': 'command_executor',
    'VoiceExecutionResult': 'command_executor',
    'VoiceCommand': 'command_router',
    'VoiceCommandRouter': 'command_router',
    'WhisperTranscriber': 'transcriber',
    'WakePhraseMatch': 'wake_phrase',
    'WakePhraseParser': 'wake_phrase',
    'AudioPlayer': 'audio_player',
    'VoiceResponseFormatter': 'response_formatter',
    'VoiceResponseSpeaker': 'response_speaker',
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module(f'{__name__}.{module}'), name)
    globals()[name] = value
    return value
