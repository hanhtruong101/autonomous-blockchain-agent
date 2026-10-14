"""Regression cases for exact sizing, explicit minimums, approvals and UI contracts."""

import json
from decimal import Decimal

import pytest
from app.agent.portfolio import AITradingAgent, PortfolioAgent
from app.agent.sizing import calculate_plan
from app.policies.rebalance import minimum_allocation
from app.schemas.domain import Asset, PolicyDraft, TokenChange, TransactionProposal
from app.simulation.engine import RpcSimulationEngine
from conftest import GOAL, TOKEN, FakeAdapter
from fastapi.testclient import TestClient
from portfolio_cases import SCENARIOS, fixtures
from pydantic import ValidationError
from test_api import activate


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case.name)
def test_expected_sizing(case) -> None:
    deployment, policy, state = fixtures(case)
    proposal = PortfolioAgent().propose(state, policy, "test", deployment)
    assert (proposal.amount if proposal else 0) == case.expected_amount * 1_000_000
    assert (
        f"{proposal.asset_in}->{proposal.asset_out}" if proposal else "HOLD"
    ) == case.expected_action


def test_no_fractional_unit_overshoot(policy: PolicyDraft, adapter: FakeAdapter) -> None:
    policy = policy.model_copy(
        update={
            "portfolio_targets": policy.portfolio_targets.model_copy(
                update={"USDC": Decimal("0.333333"), "WETH": Decimal("0.666667")}
            ),
            "rebalance": policy.rebalance.model_copy(update={"tolerance_bps": 0}),
        }
    )
    state = adapter.state().model_copy(update={"usdc_units": 2, "weth_units": 1})
    assert calculate_plan(state, policy).amount == 1
    # The remaining fractional base unit cannot be traded without crossing the target.
    assert (
        calculate_plan(state.model_copy(update={"usdc_units": 1, "weth_units": 2}), policy).amount
        == 0
    )


def test_floor_blocks_even_when_closer_to_target(
    policy: PolicyDraft, adapter: FakeAdapter, proposal: TransactionProposal
) -> None:
    policy = policy.model_copy(
        update={
            "minimum_usdc_ratio": Decimal("0.95"),
            "portfolio_targets": policy.portfolio_targets.model_copy(
                update={"USDC": Decimal("0.95"), "WETH": Decimal("0.05")}
            ),
        }
    )
    state = adapter.state().model_copy(update={"usdc_units": 967_000_000, "weth_units": 33_000_000})
    simulation = RpcSimulationEngine(adapter).simulate(proposal)
    assert not minimum_allocation(state, policy, simulation).passed
    exact = proposal.model_copy(update={"amount": 17_000_000})
    assert minimum_allocation(state, policy, RpcSimulationEngine(adapter).simulate(exact)).passed


def test_floor_uses_output_deltas(
    policy: PolicyDraft, adapter: FakeAdapter, proposal: TransactionProposal
) -> None:
    policy = policy.model_copy(update={"minimum_usdc_ratio": Decimal("0.95")})
    state = adapter.state().model_copy(update={"usdc_units": 940_000_000, "weth_units": 60_000_000})
    reverse = proposal.model_copy(
        update={"asset_in": Asset.WETH, "asset_out": Asset.USDC, "amount": 10_000_000}
    )
    simulation = (
        RpcSimulationEngine(adapter)
        .simulate(reverse)
        .model_copy(
            update={
                "expected_token_changes": (
                    TokenChange(asset=Asset.WETH, units=-10_000_000),
                    TokenChange(asset=Asset.USDC, units=9_000_000),
                )
            }
        )
    )
    assert not minimum_allocation(state, policy, simulation).passed


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_usdc_ratio": 0.5},
        {"maximum_trade_amount": 10.0},
        {"minimum_usdc_ratio": "0.9"},
        {"maximum_trade_amount": "101"},
    ],
)
def test_invalid_controls(policy: PolicyDraft, changes: dict) -> None:
    with pytest.raises(ValidationError):
        PolicyDraft.model_validate(policy.model_dump() | changes)


def test_policy_review_contract_and_immutable_versions(client: TestClient) -> None:
    old = activate(client)
    request = {
        "goal": GOAL.replace("70%", "95%"),
        "tolerance_bps": 100,
        "minimum_usdc_ratio": "0.95",
        "maximum_trade_amount": "12",
    }
    response = client.post("/policies", json=request)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["accepted_usdc_range"] == "95.00% to 96.00%"
    assert Decimal(draft["minimum_usdc_percent"]) == 95
    assert draft["draft"]["maximum_trade_amount"] == "12"
    assert client.get(f"/policies/{old}").json()["status"] == "ACTIVE"
    assert client.post(f"/policies/{draft['id']}/approve").status_code == 200
    assert client.get(f"/policies/{old}").json()["draft"]["minimum_usdc_ratio"] is None
    assert client.get(f"/policies/{old}").json()["status"] == "SUPERSEDED"


def test_at_least_goal_retains_minimum(client: TestClient) -> None:
    response = client.post(
        "/policies",
        json={
            "goal": GOAL.replace("approximately 70%", "at least 95%"),
            "minimum_usdc_ratio": "0.90",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["draft"]["minimum_usdc_ratio"] == "0.95"


def test_live_model_cannot_supply_incomplete_proposal(
    policy: PolicyDraft, adapter: FakeAdapter
) -> None:
    class MaliciousExplanation:
        def generate(self, goal: str, schema: str) -> str:
            assert json.loads(goal)["task"] == "portfolio_proposal"
            return '{"reason":"Use a larger trade", "amount_units":"99000000"}'

    with pytest.raises(ValidationError):
        AITradingAgent(MaliciousExplanation()).propose(
            adapter.state(), policy, "test", adapter.deployment
        )
    assert adapter.calls == 0


def test_live_ai_api_preserves_model_small_amount(adapter: FakeAdapter, sessions) -> None:
    from app.api.application import create_app
    from app.config.settings import Settings
    from pydantic import SecretStr

    class Provider:
        def generate(self, goal: str, schema: str) -> str:
            task = json.loads(goal)
            if task["task"] == "policy_draft":
                return json.dumps(
                    {
                        "daily_spending_limit": {"asset": "USDC", "amount": "100"},
                        "rebalance": {
                            "enabled": True,
                            "minimum_interval_hours": 0,
                            "tolerance_bps": 0,
                        },
                        "portfolio_targets": {"USDC": "0.99", "WETH": "0.01"},
                        "maximum_slippage_bps": 100,
                        "protocol": "MockDex",
                    }
                )
            assert "amount_units" not in task
            assert task["approved_policy"]["portfolio_targets"]["USDC"] == "0.99"
            return json.dumps(
                {
                    "action": "SWAP",
                    "asset_in": "USDC",
                    "asset_out": "WETH",
                    "amount_units": "7000000",
                    "protocol": "MockDex",
                    "maximum_slippage_bps": 100,
                    "reason": "Move toward the approved allocation.",
                }
            )

    settings = Settings(ai_provider="ollama", ai_model="test", owner_token=SecretStr(TOKEN))
    with TestClient(
        create_app(settings, adapter, sessions, Provider()),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        draft = client.post(
            "/policies",
            json={
                "goal": GOAL.replace("70%", "99%"),
                "maximum_trade_amount": "30",
                "tolerance_bps": 0,
            },
        ).json()
        client.post(f"/policies/{draft['id']}/approve")
        result = client.post("/agent/runs", json={}).json()
        assert result["status"] == "EXECUTED"
        assert result["proposal"]["amount"] == 7_000_000
        assert result["generation"]["execution_mode"] == "ai_trade_proposal"
        assert client.get("/automation").json()["readiness"]["code"] == "READY"


def test_approved_trade_rechecks_floor_after_balance_change(
    client: TestClient, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = client.post(
        "/policies",
        json={"goal": GOAL, "minimum_usdc_ratio": "0.70", "maximum_trade_amount": "100"},
    ).json()
    client.post(f"/policies/{draft['id']}/approve")
    proposed = client.post("/agent/runs", json={"scenario": "medium"}).json()
    assert proposed["status"] == "AWAITING_APPROVAL"
    original = adapter.state
    monkeypatch.setattr(
        adapter,
        "state",
        lambda: original().model_copy(
            update={"usdc_units": 750_000_000, "weth_units": 250_000_000}
        ),
    )
    result = client.post(f"/approvals/{proposed['approval']['id']}/approve").json()
    assert result["status"] == "BLOCKED"
    assert any(
        rule["rule_name"] == "minimum_usdc_allocation" and not rule["passed"]
        for rule in result["evaluation"]["policy"]["rules"]
    )
    assert adapter.calls == 0
