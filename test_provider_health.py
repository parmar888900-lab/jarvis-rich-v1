"""Live provider health regression tests."""

import json
from unittest.mock import patch

from backend.services.runtime.provider_health import (
    ProviderHealthService,
)


class FakeResponse:

    def __init__(
        self,
        payload,
        *,
        status=200,
    ):
        self.payload = payload
        self.status = status

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def read(
        self,
    ):
        return json.dumps(
            self.payload
        ).encode(
            "utf-8"
        )


def test_ollama_requires_configured_model():

    service = ProviderHealthService(
        timeout_seconds=1,
    )

    payload = {
        "models": [
            {
                "name": "qwen2.5:7b"
            }
        ]
    }

    with patch(
        "backend.services.runtime.provider_health.urlopen",
        return_value=FakeResponse(
            payload
        ),
    ):
        result = service.probe_ollama(
            base_url="http://ollama:11434",
            model="qwen2.5:7b",
        )

    assert result.available is True


def test_missing_ollama_model_fails_closed():

    service = ProviderHealthService(
        timeout_seconds=1,
    )

    payload = {
        "models": [
            {
                "name": "other-model"
            }
        ]
    }

    with patch(
        "backend.services.runtime.provider_health.urlopen",
        return_value=FakeResponse(
            payload
        ),
    ):
        result = service.probe_ollama(
            base_url="http://ollama:11434",
            model="qwen2.5:7b",
        )

    assert result.available is False

    assert (
        "configured model unavailable"
        in result.detail
    )


def test_comfyui_valid_response_is_healthy():

    service = ProviderHealthService(
        timeout_seconds=1,
    )

    payload = {
        "system": {
            "os": "linux"
        },
        "devices": [
            {
                "name": "cuda:0"
            }
        ],
    }

    with patch(
        "backend.services.runtime.provider_health.urlopen",
        return_value=FakeResponse(
            payload
        ),
    ):
        result = service.probe_comfyui(
            base_url="http://image:8188",
        )

    assert result.available is True


def test_invalid_comfyui_response_fails_closed():

    service = ProviderHealthService(
        timeout_seconds=1,
    )

    with patch(
        "backend.services.runtime.provider_health.urlopen",
        return_value=FakeResponse(
            {
                "unexpected": True
            }
        ),
    ):
        result = service.probe_comfyui(
            base_url="http://image:8188",
        )

    assert result.available is False


def test_network_failure_is_contained():

    service = ProviderHealthService(
        timeout_seconds=1,
    )

    with patch(
        "backend.services.runtime.provider_health.urlopen",
        side_effect=ConnectionError(
            "provider offline"
        ),
    ):
        result = service.probe_comfyui(
            base_url="http://image:8188",
        )

    assert result.available is False

    assert (
        "ConnectionError"
        in result.detail
    )


def main():

    test_ollama_requires_configured_model()

    print(
        "PASS: Ollama health requires configured model."
    )

    test_missing_ollama_model_fails_closed()

    print(
        "PASS: missing Ollama model fails closed."
    )

    test_comfyui_valid_response_is_healthy()

    print(
        "PASS: valid ComfyUI service reports healthy."
    )

    test_invalid_comfyui_response_fails_closed()

    print(
        "PASS: invalid ComfyUI response fails closed."
    )

    test_network_failure_is_contained()

    print(
        "PASS: provider network failure is contained."
    )

    print()

    print(
        "PASS: provider health regression suite complete."
    )


if __name__ == "__main__":
    main()
