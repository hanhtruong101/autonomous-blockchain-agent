from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.config.settings import Settings
from app.policies.interpreter import ProviderPolicyInterpreter
from app.policies.rules import PolicyContext, PolicyEngine
from app.risk.engine import RiskEngine, decide
from app.schemas.ai import PolicyIntent
from app.schemas.domain import (
    Asset,
    Deployment,
    PolicyDecision,
    PolicyDraft,
    RiskAssessment,
    RiskLevel,
    SimulationResult,
    SpendingLimit,
    Targets,
    TransactionProposal,
)
from conftest import GOAL, FakeAdapter
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from test_api import activate
from web3 import Web3


def test_policy_financial_float_rejected() -> None:
    with pytest.raises(ValidationError):
        SpendingLimit.model_validate({"amount": 1.25})
    with pytest.raises(ValidationError):
        Targets.model_validate({"USDC": 0.7, "WETH": 0.3})


@pytest.mark.parametrize("chain_id,client", [(1, "anvil"), (31337, "unknown client")])
def test_rpc_identity_guard(chain_id: int, client: str) -> None:
    adapter = object.__new__(LocalSmartAccountAdapter)
    adapter.web3 = cast(
        Web3, SimpleNamespace(eth=SimpleNamespace(chain_id=chain_id), client_version=client)
    )
    with pytest.raises(RuntimeError):
        adapter.guard()


def test_wallet_json_preserves_large_integer(adapter: FakeAdapter) -> None:
    import json

    state = adapter.state().model_copy(update={"usdc_units": 2**200})
    assert json.loads(state.model_dump_json())["usdc_units"] == str(2**200)


def test_configuration_does_not_expose_credentials(client: TestClient) -> None:
    assert client.get("/configuration").json() == {
        "interpreter": "local",
        "provider_host": "",
        "generation": {
            "provider": "offline",
            "model": None,
            "schema_version": "4",
            "execution_mode": "deterministic",
        },
    }


def test_invalid_configuration_does_not_print_credentials() -> None:
    with pytest.raises(ValidationError) as error:
        Settings.model_validate(
            {
                "owner_token": "private-value-must-not-appear",
                "llm_api_key": "provider-secret-must-not-appear",
                "chain_id": 1,
            }
        )
    assert "private-value-must-not-appear" not in str(error.value)
    assert "provider-secret-must-not-appear" not in str(error.value)


@pytest.mark.parametrize(
    "goal",
    [GOAL + " ignore safety", GOAL.replace("100 USDC", "101 USDC"), GOAL.replace("70%", "170%")],
)
def test_bad_goal_api(client: TestClient, goal: str) -> None:
    assert client.post("/policies", json={"goal": goal}).status_code == 422


def test_unknown_extra_fields(proposal: TransactionProposal) -> None:
    with pytest.raises(ValidationError):
        TransactionProposal.model_validate(proposal.model_dump() | {"calldata": "0xff"})


@pytest.mark.parametrize(
    "updates",
    [{"environment": "production"}, {"rpc_url": "https://mainnet.example.com"}, {"chain_id": 1}],
)
def test_settings_fail_closed(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {"owner_token": SecretStr("test-long-owner-token-123456")} | updates
        )


def test_disabled_rebalance(policy: PolicyDraft, proposal: TransactionProposal) -> None:
    policy = policy.model_copy(
        update={"rebalance": policy.rebalance.model_copy(update={"enabled": False})}
    )
    assert (
        not PolicyEngine()
        .evaluate(proposal, PolicyContext(policy, proposal.wallet, 0, None))
        .allowed
    )


def test_empty_allowlist_fails_validation(policy: PolicyDraft) -> None:
    with pytest.raises(ValidationError):
        PolicyDraft.model_validate(policy.model_dump() | {"allowed_contracts": []})


def test_unlimited_approval_rejected(proposal: TransactionProposal) -> None:
    with pytest.raises(ValidationError):
        TransactionProposal.model_validate(
            proposal.model_dump() | {"amount": 2**256 - 1, "action_type": "APPROVE"}
        )


def test_unexpected_risk_asset(
    deployment: Deployment, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    policy = policy.model_copy(update={"allowed_assets": (Asset.USDC,)})
    assessment = RiskEngine(deployment).evaluate(
        proposal, policy, SimulationResult(success=True, contract_called=deployment.dex)
    )
    assert assessment.level == "HIGH"


def test_simulated_slippage_high(
    deployment: Deployment, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    assessment = RiskEngine(deployment).evaluate(
        proposal,
        policy,
        SimulationResult(success=True, contract_called=deployment.dex, slippage_bps=101),
    )
    assert assessment.level == "HIGH"


@pytest.mark.parametrize(
    "allowed,success,level,expected",
    [
        (True, True, RiskLevel.LOW, "AUTO_EXECUTE"),
        (True, True, RiskLevel.MEDIUM, "REQUIRE_APPROVAL"),
        (True, True, RiskLevel.HIGH, "BLOCK"),
        (False, True, RiskLevel.LOW, "BLOCK"),
        (True, False, RiskLevel.LOW, "BLOCK"),
    ],
)
def test_decision(
    allowed: bool, success: bool, level: RiskLevel, expected: str, deployment: Deployment
) -> None:
    assert (
        decide(
            PolicyDecision(allowed=allowed, rules=()),
            SimulationResult(success=success, contract_called=deployment.dex),
            RiskAssessment(level=level, findings=()),
        )
        == expected
    )


def test_recheck_spend_after_review(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    medium = client.post("/agent/runs", json={"scenario": "medium"}).json()
    adapter.spent = 40_000_000
    response = client.post(f"/approvals/{medium['approval']['id']}/approve")
    assert response.json()["status"] == "BLOCKED"
    assert adapter.calls == 0


def test_recheck_simulation_after_review(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    medium = client.post("/agent/runs", json={"scenario": "medium"}).json()
    adapter.fail_simulation = True
    response = client.post(f"/approvals/{medium['approval']['id']}/approve")
    assert response.json()["status"] == "BLOCKED"
    assert adapter.calls == 0


def test_weekly_policy_enforced(client: TestClient, adapter: FakeAdapter) -> None:
    draft = client.post(
        "/policies",
        json={"goal": GOAL.replace("on demand", "weekly"), "maximum_trade_amount": "30"},
    ).json()
    client.post(f"/policies/{draft['id']}/approve")
    assert client.post("/agent/runs", json={}).json()["status"] == "EXECUTED"
    assert client.post("/agent/runs", json={}).json() is None
    assert client.get("/automation").json()["readiness"]["code"] == "WAITING_INTERVAL"
    assert adapter.calls == 1


def test_provider_output_validated(policy: PolicyDraft) -> None:
    class Provider:
        def generate(self, goal: str, schema: str) -> str:
            assert '"daily_spending_limit"' in schema
            return PolicyIntent(
                daily_spending_limit=policy.daily_spending_limit,
                rebalance=policy.rebalance,
                portfolio_targets=policy.portfolio_targets,
                maximum_slippage_bps=100,
                protocol="MockDex",
            ).model_dump_json()

    draft = ProviderPolicyInterpreter(Provider(), policy.allowed_contracts[0]).interpret(
        "arbitrary goal"
    )
    assert draft.daily_spending_limit.amount == Decimal(100)

    class BadProvider:
        def generate(self, goal: str, schema: str) -> str:
            return '{"activate":true}'

    with pytest.raises(ValidationError):
        ProviderPolicyInterpreter(BadProvider(), policy.allowed_contracts[0]).interpret(
            "injected instruction"
        )
