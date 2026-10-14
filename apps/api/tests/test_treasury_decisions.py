"""Live proposals, complete activity history and independent authorization."""

import json
from decimal import Decimal

import pytest
from app.agent.portfolio import AITradingAgent
from app.api.application import create_app
from app.config.settings import Settings
from app.execution.agent_runs import AgentRuns
from app.execution.automation import AutomationService
from app.execution.coordinator import ExecutionCoordinator
from app.execution.pipeline import Pipeline
from app.schemas.ai import AgentAssessment, AgentDecision
from app.simulation.engine import RpcSimulationEngine
from conftest import TOKEN
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from test_api import activate
from test_automation import Owner, due, enable
from test_automation import automation as automation


class DecisionProvider:
    def __init__(self, response: str, target: str = "0.95") -> None:
        self.response = response
        self.target = target
        self.calls = 0

    def generate(self, goal: str, schema: str) -> str:
        context = json.loads(goal)
        if context["task"] == "policy_draft":
            return json.dumps(
                {
                    "daily_spending_limit": {"asset": "USDC", "amount": "100"},
                    "rebalance": {"enabled": True, "minimum_interval_hours": 0, "tolerance_bps": 0},
                    "portfolio_targets": {
                        "USDC": self.target,
                        "WETH": str(Decimal(1) - Decimal(self.target)),
                    },
                    "maximum_slippage_bps": 100,
                    "protocol": "MockDex",
                }
            )
        self.calls += 1
        assert context["task"] == "portfolio_proposal"
        assert "0x" not in goal
        assert "amount_units" in json.loads(schema)["properties"]
        return self.response


def trade_output(**changes: object) -> str:
    return json.dumps(
        {
            "action": "SWAP",
            "asset_in": "USDC",
            "asset_out": "WETH",
            "amount_units": "17000000",
            "protocol": "MockDex",
            "maximum_slippage_bps": 100,
            "reason": "Move toward the approved target.",
        }
        | changes
    )


def ai_client(adapter, sessions, provider):
    return TestClient(
        create_app(
            Settings(owner_token=SecretStr(TOKEN), ai_provider="ollama", ai_model="test"),
            adapter,
            sessions,
            provider,
            owner_controls=Owner(),
        ),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


def test_hold_history_and_repeated_hold_advisory(adapter, sessions) -> None:
    provider = DecisionProvider(
        trade_output(action="HOLD", amount_units="0", reason="Wait for owner review of the goal.")
    )
    with ai_client(adapter, sessions, provider) as client:
        version = activate(client, "30")
        for _ in range(3):
            response = client.post("/agent/runs", json={})
            assert response.status_code == 201 and response.json() is None
        history = client.get("/agent/activity").json()
        assert history["consecutive_ai_holds"] == 3
        assert len(history["items"]) == 3
        item = history["items"][0]
        assert item["state"] == "AI_HOLD"
        assert item["policy_version_id"] == version
        assert item["observation"]["usdc_units"] == "1000000000"
        assert item["decision"]["reason"] == "Wait for owner review of the goal."
        assert item["proposal_id"] is None
        assert client.get("/proposals").json() == []
        assert (
            client.get("/agent/activity", headers={"Authorization": "invalid"}).status_code == 401
        )
        activate(client, "30")
        assert client.get("/agent/activity").json()["consecutive_ai_holds"] == 0
    assert provider.calls == 3 and adapter.calls == 0


def test_ai_amount_is_preserved_and_history_tracks_final_status(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output(amount_units="17000000"))
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "30")
        first = client.post("/agent/runs", json={}).json()
        second = client.post("/agent/runs", json={}).json()
        assert [first["proposal"]["amount"], second["proposal"]["amount"]] == [
            17_000_000,
            17_000_000,
        ]
        provider.response = trade_output(amount_units="16000000")
        assert client.post("/agent/runs", json={}).json()["status"] == "EXECUTED"
        assert client.post("/agent/runs", json={}).json() is None
        history = client.get("/agent/activity").json()["items"]
        assert len(history) == 4
        assert history[0]["state"] == "SYSTEM_SKIPPED"
        assert history[0]["decision"] is None
        assert history[1]["proposal_status"] == "EXECUTED"
        assert history[2]["proposal_id"] == second["id"]
        assert history[1]["decision"]["action"] == "SWAP"
    assert provider.calls == 3 and adapter.calls == 3


@pytest.mark.parametrize(
    "response",
    [
        '{"action":"TRANSFER","reason":"Send elsewhere"}',
        '{"action":"REBALANCE","reason":"Trade","amount_units":"99999999"}',
        '{"action":"REBALANCE","reason":"Visit https://example.com"}',
        '{"reason":"No action field"}',
        "not json",
    ],
)
def test_invalid_decision_fails_closed_and_records_failure(adapter, sessions, response) -> None:
    with ai_client(adapter, sessions, DecisionProvider(response)) as client:
        activate(client, "30")
        assert client.post("/agent/runs", json={}).status_code == 422
        item = client.get("/agent/activity").json()["items"][0]
        assert item["state"] == "FAILED"
        assert item["decision"] is None
        assert client.get("/proposals").json() == []
    assert adapter.calls == 0


def test_exhausted_budget_never_calls_live_model(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output())
    adapter.spent = 100_000_000
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "30")
        response = client.post("/agent/runs", json={})
        assert response.status_code == 201 and response.json() is None
        assert client.get("/agent/activity").json()["items"][0]["state"] == "SYSTEM_SKIPPED"
    assert provider.calls == 0 and adapter.calls == 0


def test_historical_rebalance_activity_remains_readable() -> None:
    assert AgentDecision(action="REBALANCE", reason="Historical decision").action == "REBALANCE"


def test_hold_cannot_carry_proposal(proposal) -> None:
    with pytest.raises(ValidationError):
        AgentAssessment(decision=AgentDecision(action="HOLD", reason="Wait"), proposal=proposal)


def test_history_resolves_current_approval_outcome(client, adapter) -> None:
    activate(client, "100")
    proposal = client.post("/agent/runs", json={"scenario": "medium"}).json()
    history = client.get("/agent/activity").json()["items"][0]
    assert history["source"] == "fixture" and history["decision"] is None
    assert history["proposal_status"] == "AWAITING_APPROVAL"
    approved = client.post(f"/approvals/{proposal['approval']['id']}/approve")
    assert approved.json()["status"] == "EXECUTED"
    history = client.get("/agent/activity").json()["items"]
    assert len(history) == 1 and history[0]["proposal_status"] == "EXECUTED"
    assert adapter.calls == 1


def test_ui_timestamps_include_timezone(client) -> None:
    version = activate(client, "100")
    policy = client.get(f"/policies/{version}").json()
    assert policy["created_at"].endswith(("Z", "+00:00"))
    schedule = client.post(
        "/automation/enable", json={"policy_version_id": version, "interval_seconds": 30}
    ).json()
    assert schedule["next_check_at"].endswith(("Z", "+00:00"))
    proposal = client.post("/agent/runs", json={"scenario": "medium"}).json()
    assert proposal["approval"]["expires_at"].endswith(("Z", "+00:00"))
    assert client.get("/audit-events").json()[0]["created_at"].endswith(("Z", "+00:00"))


def test_scheduled_skip_appears_in_history(client, automation, adapter, monkeypatch) -> None:
    enable(automation)
    original = adapter.state
    monkeypatch.setattr(
        adapter, "state", lambda: original().model_copy(update={"spent_units": 100_000_000})
    )
    due(automation)
    automation.tick()
    item = client.get("/agent/activity").json()["items"][0]
    assert item["state"] == "SYSTEM_SKIPPED"
    assert item["source"] == "scheduled"
    assert item["decision"] is None
    assert "budget" in item["reason"].lower()
    assert adapter.calls == 0


def test_owner_freeze_during_decision_cancels_plan(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output())
    original = provider.generate
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "30")

        def freeze(goal: str, schema: str) -> str:
            assert client.post("/automation/freeze").status_code == 200
            return original(goal, schema)

        provider.generate = freeze
        assert client.post("/agent/runs", json={}).status_code == 409
        assert client.get("/agent/activity").json()["items"][0]["state"] == "CANCELLED"
        assert client.get("/proposals").json() == []
    assert adapter.calls == 0


@pytest.mark.parametrize(
    "change,spent,simulation_failure",
    [
        ({"amount_units": "31000000"}, 0, False),
        ({"amount_units": "110000000"}, 0, False),
        ({"maximum_slippage_bps": 2000}, 0, False),
        ({"asset_in": "WETH", "asset_out": "USDC"}, 0, False),
        ({}, 90_000_000, False),
        ({}, 0, True),
    ],
)
def test_live_ai_unsafe_trade_is_stored_and_blocked(
    adapter, sessions, change, spent, simulation_failure
) -> None:
    adapter.spent = spent
    adapter.fail_simulation = simulation_failure
    provider = DecisionProvider(trade_output(**change), target="0.70")
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "30")
        response = client.post("/agent/runs", json={})
        assert response.status_code == 201
        result = response.json()
        assert result["status"] == "BLOCKED"
        assert result["generation"]["execution_mode"] == "ai_trade_proposal"
        assert result["proposal"]["amount"] == int(change.get("amount_units", "17000000"))
        assert result["execution"] is None
        history = client.get("/agent/activity").json()["items"][0]
        assert history["decision"]["action"] == "SWAP"
        assert history["proposal_status"] == "BLOCKED"
        assert history["proposal_id"] == result["id"]
    assert provider.calls == 1 and adapter.calls == 0


def test_live_ai_medium_trade_requires_exact_owner_approval(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output(amount_units="70000000"), target="0.70")
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "100")
        result = client.post("/agent/runs", json={}).json()
        assert result["status"] == "AWAITING_APPROVAL"
        assert result["proposal"]["amount"] == 70_000_000
        assert adapter.calls == 0
        approved = client.post(f"/approvals/{result['approval']['id']}/approve").json()
        assert approved["status"] == "EXECUTED"
        assert approved["proposal"] == result["proposal"]
    assert adapter.calls == 1


def test_scheduled_ai_trade_uses_model_amount_and_records_source(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output())
    with ai_client(adapter, sessions, provider) as client:
        activate(client, "30")
        pipeline = Pipeline(adapter, RpcSimulationEngine(adapter))
        service = AutomationService(
            sessions,
            AgentRuns(adapter, pipeline, AITradingAgent(provider)),
            ExecutionCoordinator(sessions, pipeline),
            Owner(),
            True,
        )
        enable(service)
        due(service)
        service.tick()
        result = client.get("/proposals").json()[0]
        assert result["status"] == "EXECUTED"
        assert result["proposal"]["amount"] == 17_000_000
        history = client.get("/agent/activity").json()["items"][0]
        assert history["source"] == "scheduled"
        assert history["decision"]["action"] == "SWAP"
    assert provider.calls == 1 and adapter.calls == 1


def test_live_ai_trade_cannot_cross_hard_usdc_minimum(adapter, sessions) -> None:
    provider = DecisionProvider(trade_output(amount_units="51000000"))
    with ai_client(adapter, sessions, provider) as client:
        draft = client.post(
            "/policies",
            json={
                "goal": "Keep approximately 95% USDC with a 95% hard minimum.",
                "maximum_trade_amount": "100",
                "minimum_usdc_ratio": "0.95",
                "tolerance_bps": 0,
            },
        ).json()
        assert client.post(f"/policies/{draft['id']}/approve").status_code == 200
        result = client.post("/agent/runs", json={}).json()
        assert result["status"] == "BLOCKED"
        assert any(
            rule["rule_name"] == "minimum_usdc_allocation" and not rule["passed"]
            for rule in result["evaluation"]["policy"]["rules"]
        )
    assert adapter.calls == 0
