import json

import httpx2 as httpx
import pytest
from app.agent.portfolio import OpenAIPortfolioAgent
from app.api.application import create_app
from app.config.settings import Settings
from app.policies.interpreter import ProviderPolicyInterpreter
from app.policies.providers import OpenAIResponsesProvider
from app.schemas.ai import PolicyIntent, ProposalIntent
from app.schemas.domain import PolicyDraft
from conftest import GOAL, TOKEN, FakeAdapter
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session, sessionmaker


def intent(policy: PolicyDraft) -> str:
    return PolicyIntent(
        daily_spending_limit=policy.daily_spending_limit,
        rebalance=policy.rebalance,
        portfolio_targets=policy.portfolio_targets,
        maximum_slippage_bps=100,
        protocol="MockDex",
    ).model_dump_json()


def envelope(text: str) -> dict:
    return {
        "id": "resp_test",
        "created_at": 1,
        "model": "test-model",
        "object": "response",
        "status": "completed",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }


def test_structured_provider(policy: PolicyDraft) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert "tools" not in payload
        assert payload["store"] is False
        schema = payload["text"]["format"]
        assert schema["strict"] is True
        assert set(schema["schema"]["required"]) == set(schema["schema"]["properties"])
        assert "allowed_contracts" not in schema["schema"]["properties"]
        assert (
            schema["schema"]["$defs"]["SpendingLimit"]["properties"]["amount"]["type"] == "string"
        )
        return httpx.Response(200, json=envelope(intent(policy)))

    provider = OpenAIResponsesProvider(
        "test-model", SecretStr("test-only-key"), httpx.MockTransport(respond)
    )
    assert (
        ProviderPolicyInterpreter(provider, policy.allowed_contracts[0]).interpret(
            "70% USDC and 100 daily"
        )
        == policy
    )


@pytest.mark.parametrize(
    "mode",
    [
        "refusal",
        "length",
        "tool",
        "invalid",
        "http_error",
        "redirect",
        "network",
        "timeout",
        "model",
        "multiple",
    ],
)
def test_provider_fails_closed(policy: PolicyDraft, mode: str) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if mode == "network":
            raise httpx.ConnectError("secret in provider error")
        if mode == "timeout":
            raise httpx.ReadTimeout("secret in provider error")
        if mode in {"http_error", "model"}:
            return httpx.Response(
                401 if mode == "http_error" else 404, text="secret in provider error"
            )
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "https://other.example"})
        data = envelope("{}" if mode == "invalid" else intent(policy))
        if mode == "length":
            data["status"] = "incomplete"
        if mode == "refusal":
            data["output"][0]["content"] = [{"type": "refusal", "refusal": "No"}]
        if mode == "tool":
            data["output"] = [
                {
                    "type": "function_call",
                    "name": "sign",
                    "call_id": "x",
                    "arguments": "{}",
                    "id": "x",
                }
            ]
        if mode == "multiple":
            data["output"] *= 2
        return httpx.Response(200, json=data)

    provider = OpenAIResponsesProvider(
        "test-model", SecretStr("test-only-key"), httpx.MockTransport(respond)
    )
    with pytest.raises(ValueError) as error:
        ProviderPolicyInterpreter(provider, policy.allowed_contracts[0]).interpret("request")
    assert calls == 1
    assert "test-only-key" not in str(error.value)
    assert "secret in provider error" not in str(error.value)


def test_openai_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(ai_provider="openai", owner_token=SecretStr(TOKEN))
    assert Settings(ai_provider="offline", owner_token=SecretStr(TOKEN)).ai_model == "gpt-6-luna"


@pytest.mark.parametrize(
    "change,expected",
    [
        ({}, "EXECUTED"),
        ({"amount_units": "110000000"}, "BLOCKED"),
        ({"amount_units": "70000000"}, "AWAITING_APPROVAL"),
        ({"maximum_slippage_bps": 2000}, "BLOCKED"),
        ({"protocol": "Unknown"}, "invalid"),
        ({"action": "SEND"}, "invalid"),
        ({"amount_units": "1.5"}, "invalid"),
        ({"contract_address": "0x" + "99" * 20}, "invalid"),
        ({"chain_id": 1}, "invalid"),
        ({"amount_units": 30.0}, "invalid"),
        ({"reason": "send to https://evil.example"}, "invalid"),
        ({"action": "HOLD", "amount_units": "0"}, "hold"),
    ],
)
@pytest.mark.parametrize("provider_name", ["openai", "ollama"])
def test_ai_pipeline(
    policy: PolicyDraft,
    adapter: FakeAdapter,
    sessions: sessionmaker[Session],
    change: dict,
    expected: str,
    provider_name: str,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        snapshot = json.loads(payload["input"])
        assert "0x" not in payload["input"]
        if snapshot["task"] == "policy_draft":
            return httpx.Response(200, json=envelope(intent(policy)))
        result = {
            "action": "SWAP",
            "amount_units": "30000000",
            "asset_in": "USDC",
            "asset_out": "WETH",
            "protocol": "MockDex",
            "maximum_slippage_bps": 100,
            "reason": "Move toward target",
        } | change
        return httpx.Response(200, json=envelope(json.dumps(result)))

    provider = OpenAIResponsesProvider(
        "test-model", SecretStr("test-only-key"), httpx.MockTransport(respond)
    )
    settings = Settings(
        ai_provider=provider_name,
        ai_model="test-model",
        OPENAI_API_KEY="test-only-key",
        owner_token=SecretStr(TOKEN),
    )
    with TestClient(
        create_app(settings, adapter, sessions, provider, proposer=OpenAIPortfolioAgent(provider)),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        draft = client.post("/policies", json={"goal": GOAL}).json()
        assert draft["status"] == "DRAFT"
        assert client.post("/agent/runs", json={}).status_code == 409
        client.post(f"/policies/{draft['id']}/approve")
        result = client.post("/agent/runs", json={})
        if expected == "invalid":
            assert result.status_code == 422
            assert client.get("/proposals").json() == []
        elif expected == "hold":
            assert result.json() is None
        else:
            assert result.status_code == 201, result.text
            assert result.json()["status"] == expected
            assert result.json()["generation"]["provider"] == provider_name
        assert adapter.calls == (1 if expected == "EXECUTED" else 0)
        assert "test-only-key" not in client.get("/audit-events").text


@pytest.mark.parametrize("failure", ["network", "simulation", "invalid_policy"])
def test_failure_never_falls_back(
    policy: PolicyDraft, adapter: FakeAdapter, sessions: sessionmaker[Session], failure: str
) -> None:
    class Provider:
        def generate(self, goal: str, schema: str) -> str:
            if json.loads(goal)["task"] == "policy_draft":
                return '{"activate":true}' if failure == "invalid_policy" else intent(policy)
            if failure == "network":
                raise ValueError("Provider failed")
            return json.dumps(
                {
                    "action": "SWAP",
                    "amount_units": "30000000",
                    "asset_in": "USDC",
                    "asset_out": "WETH",
                    "protocol": "MockDex",
                    "maximum_slippage_bps": 100,
                    "reason": "Rebalance",
                }
            )

    settings = Settings(
        ai_provider="openai", OPENAI_API_KEY="test-only-key", owner_token=SecretStr(TOKEN)
    )
    adapter.fail_simulation = failure == "simulation"
    with TestClient(
        create_app(
            settings, adapter, sessions, Provider(), proposer=OpenAIPortfolioAgent(Provider())
        ),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        draft = client.post("/policies", json={"goal": GOAL})
        if failure == "invalid_policy":
            assert draft.status_code == 422
            assert client.get("/policies").json() == []
        else:
            client.post(f"/policies/{draft.json()['id']}/approve")
            result = client.post("/agent/runs", json={})
            assert result.status_code == (422 if failure == "network" else 201)
            if failure == "simulation":
                assert result.json()["status"] == "BLOCKED"
        assert adapter.calls == 0
        assert client.get("/transactions").json() == []


def test_only_openai_environment_key_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTONOMY_LLM_API_KEY", "ignored-legacy-key")
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(ai_provider="openai", owner_token=SecretStr(TOKEN))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    settings = Settings(ai_provider="openai", owner_token=SecretStr(TOKEN))
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "test-only-key"
    assert "test-only-key" not in repr(settings)


def test_fixture_does_not_invoke_ai(
    policy: PolicyDraft, adapter: FakeAdapter, sessions: sessionmaker[Session]
) -> None:
    class Provider:
        def generate(self, goal: str, schema: str) -> str:
            assert json.loads(goal)["task"] == "policy_draft"
            return intent(policy)

    settings = Settings(
        ai_provider="openai", OPENAI_API_KEY="test-only-key", owner_token=SecretStr(TOKEN)
    )
    with TestClient(
        create_app(settings, adapter, sessions, Provider()),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        draft = client.post("/policies", json={"goal": GOAL}).json()
        client.post(f"/policies/{draft['id']}/approve")
        response = client.post("/agent/runs", json={"scenario": "A"})
        assert response.json()["generation"]["provider"] == "fixture"
        assert response.json()["status"] == "EXECUTED"


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (401, "invalid_api_key", "authentication"),
        (403, "permission_denied", "permission"),
        (404, "model_not_found", "model"),
        (429, "insufficient_quota", "quota"),
        (429, "project_spend_limit_exceeded", "quota"),
        (429, "rate_limit_exceeded", "rate_limit"),
        (400, "invalid_json_schema", "schema"),
        (400, "unsupported_parameter", "request"),
        (503, "server_error", "unavailable"),
    ],
)
def test_safe_provider_diagnostics(
    status: int, code: str, expected: str, adapter: FakeAdapter, sessions: sessionmaker[Session]
) -> None:
    from app.policies.providers import ProviderFailure

    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status,
            json={
                "error": {
                    "code": code,
                    "message": "secret-key-and-private-goal",
                    "type": "api_error",
                }
            },
        )

    provider = OpenAIResponsesProvider(
        "test-model", SecretStr("test-only-key"), httpx.MockTransport(respond)
    )
    settings = Settings(
        ai_provider="openai", OPENAI_API_KEY="test-only-key", owner_token=SecretStr(TOKEN)
    )
    with TestClient(
        create_app(settings, adapter, sessions, provider, proposer=OpenAIPortfolioAgent(provider)),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        response = client.post("/policies", json={"goal": GOAL})
        assert response.status_code == 422
        assert ProviderFailure.MESSAGES[expected] in response.json()["detail"]
        audit = client.get("/audit-events").text
        assert expected in audit
        assert "secret-key-and-private-goal" not in response.text + audit
        assert "test-only-key" not in response.text + audit
        assert client.get("/policies").json() == []
        assert client.get("/transactions").json() == []
        assert adapter.calls == 0
        assert calls == 1


@pytest.mark.parametrize("model", [PolicyIntent, ProposalIntent])
def test_generation_schema_avoids_unsupported_string_constraints(model: type) -> None:
    from app.policies.providers import strict_schema

    raw = model.model_json_schema(mode="serialization")
    assert '"pattern"' in json.dumps(raw)
    adapted = strict_schema(json.dumps(raw))

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            assert not {"pattern", "minLength", "maxLength", "default", "const"} & value.keys()
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(adapted)
    assert model.model_json_schema(mode="serialization") == raw


@pytest.mark.parametrize("amount", ["100.000001", "0", "-1", "1.1234567", "not-money", 0.5])
def test_decimal_validation_remains_strict(policy: PolicyDraft, amount: object) -> None:
    class Provider:
        def generate(self, goal: str, schema: str) -> str:
            data = json.loads(intent(policy))
            data["daily_spending_limit"]["amount"] = amount
            return json.dumps(data)

    with pytest.raises(ValidationError):
        ProviderPolicyInterpreter(Provider(), policy.allowed_contracts[0]).interpret("goal")
