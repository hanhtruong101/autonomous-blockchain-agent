import json

import httpx
import pytest
from app.config.settings import Settings
from app.policies.ollama import OllamaProvider
from app.policies.providers import ProviderFailure
from conftest import TOKEN
from pydantic import SecretStr, ValidationError


def test_ollama_needs_no_key() -> None:
    settings = Settings(
        ai_provider="ollama", ai_model="llama3:latest", owner_token=SecretStr(TOKEN)
    )
    assert settings.openai_api_key is None


@pytest.mark.parametrize("model", [None, "", "llama-cloud", "user/remote"])
def test_ollama_requires_explicit_local_model(model: str | None) -> None:
    values = {} if model is None else {"ai_model": model}
    with pytest.raises(ValidationError):
        Settings(ai_provider="ollama", owner_token=SecretStr(TOKEN), **values)


@pytest.mark.parametrize(
    "mode",
    [
        "ok",
        "timeout",
        "connection",
        "missing",
        "redirect",
        "tool",
        "incomplete",
        "invalid",
        "oversized",
    ],
)
def test_local_transport(mode: str) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        assert "tools" not in payload
        assert payload["stream"] is False
        assert payload["format"]["additionalProperties"] is False
        if mode == "timeout":
            raise httpx.ReadTimeout("private error")
        if mode == "connection":
            raise httpx.ConnectError("private error")
        if mode == "missing":
            return httpx.Response(404, text="private error")
        if mode == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com"})
        if mode == "invalid":
            return httpx.Response(200, text="invalid")
        data = {
            "done": mode != "incomplete",
            "done_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "x" * 100001 if mode == "oversized" else "{}",
            },
        }
        if mode == "tool":
            data["message"]["tool_calls"] = [{"function": "execute"}]
        return httpx.Response(200, json=data)

    provider = OllamaProvider("llama3:latest", httpx.MockTransport(respond))
    schema = '{"type":"object","properties":{}}'
    if mode == "ok":
        assert provider.generate("goal", schema) == "{}"
    else:
        with pytest.raises(ProviderFailure) as error:
            provider.generate("goal", schema)
        assert "private error" not in str(error.value)
    assert calls == 1
