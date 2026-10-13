"""Scheduling denials, owner cancellation and durable failure behavior."""

from datetime import timedelta

import pytest
from app.db.repository import Conflict
from app.execution.agent_runs import AgentRuns
from app.execution.automation import AutomationService
from app.execution.coordinator import ExecutionCoordinator
from app.execution.pipeline import Pipeline
from app.models.entities import Automation, Wallet
from app.schemas.automation import EnableAutomation
from app.schemas.domain import now
from app.simulation.engine import RpcSimulationEngine
from conftest import FakeAdapter
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_api import activate


class Owner:
    def __init__(self) -> None:
        self.calls: list[bool] = []
        self.fail = False

    def set_paused(self, paused: bool) -> str:
        self.calls.append(paused)
        if self.fail:
            raise OSError("RPC unavailable")
        return "0x" + "aa" * 32


@pytest.fixture
def automation(
    client: TestClient, adapter: FakeAdapter, sessions: sessionmaker[Session]
) -> AutomationService:
    activate(client)
    pipeline = Pipeline(adapter, RpcSimulationEngine(adapter))
    return AutomationService(
        sessions,
        AgentRuns(adapter, pipeline),
        ExecutionCoordinator(sessions, pipeline),
        Owner(),
        True,
    )


def enable(service: AutomationService) -> None:
    with service.sessions() as session:
        version = session.get(Wallet, service.address).active_version_id
    service.enable(EnableAutomation(policy_version_id=version, interval_seconds=30))


def due(service: AutomationService) -> None:
    with service.sessions.begin() as session:
        session.get(Automation, service.address).next_check_at = now() - timedelta(seconds=1)


def test_opt_in_and_due_only(
    automation: AutomationService, adapter: FakeAdapter, client: TestClient
) -> None:
    activate(client, "30")
    automation.tick()
    assert adapter.calls == 0
    enable(automation)
    automation.tick()
    assert adapter.calls == 0
    due(automation)
    automation.tick()
    assert adapter.calls == 1
    assert "EXECUTED" in automation.view().last_result
    automation.tick()
    assert adapter.calls == 1


def test_stop_and_policy_change(
    automation: AutomationService, client: TestClient, adapter: FakeAdapter
) -> None:
    enable(automation)
    automation.stop()
    automation.tick()
    assert adapter.calls == 0
    enable(automation)
    activate(client)
    assert not automation.view().enabled
    assert adapter.calls == 0


def test_freeze_cancels_approval(
    automation: AutomationService, client: TestClient, adapter: FakeAdapter
) -> None:
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    assert response["status"] == "AWAITING_APPROVAL"
    automation.freeze()
    assert client.post(f"/approvals/{response['approval']['id']}/approve").status_code == 409
    assert client.post("/agent/runs", json={}).status_code == 409
    assert adapter.calls == 0
    automation.resume()
    assert not automation.view().enabled
    assert not automation.view().execution_paused
    assert automation.view().next_check_at is None
    assert automation.view().last_result == (
        "Execution resumed by owner; automatic checks remain off"
    )


def test_freeze_rpc_failure_stays_frozen(automation: AutomationService) -> None:
    assert isinstance(automation.controls, Owner)
    automation.controls.fail = True
    with pytest.raises(Conflict):
        automation.freeze()
    assert automation.view().execution_paused
    with pytest.raises(Conflict):
        automation.resume()
    assert automation.view().execution_paused


def test_uncertain_submission_never_retried(
    automation: AutomationService, adapter: FakeAdapter, client: TestClient
) -> None:
    activate(client, "30")
    adapter.fail_submit = True
    enable(automation)
    due(automation)
    automation.tick()
    assert adapter.calls == 1
    assert automation.view().execution_paused
    assert not automation.view().enabled
    automation.tick()
    assert adapter.calls == 1
    with pytest.raises(Conflict):
        automation.resume()


def test_repeated_simulation_failure_freezes(
    automation: AutomationService, adapter: FakeAdapter
) -> None:
    adapter.fail_simulation = True
    enable(automation)
    for _ in range(3):
        due(automation)
        automation.tick()
    assert automation.view().consecutive_failures == 3
    assert automation.view().execution_paused
    assert isinstance(automation.controls, Owner)
    assert automation.controls.calls == [True]
    assert adapter.calls == 0


def test_waits_for_pending_approval(
    automation: AutomationService, client: TestClient, adapter: FakeAdapter
) -> None:
    client.post("/agent/runs", json={"scenario": "medium"})
    enable(automation)
    due(automation)
    automation.tick()
    assert "approval" in automation.view().last_result
    assert adapter.calls == 0


def test_exhausted_budget_skips_model(automation: AutomationService, adapter: FakeAdapter) -> None:
    adapter.spent = 100_000_000
    enable(automation)
    due(automation)
    automation.tick()
    assert "budget" in automation.view().last_result
    assert adapter.calls == 0


def test_restart_does_not_replay_claim(automation: AutomationService, adapter: FakeAdapter) -> None:
    enable(automation)
    due(automation)
    with automation.sessions.begin() as session:
        session.get(Automation, automation.address).running = True
    automation.tick()
    assert adapter.calls == 0
    assert automation.view().running


def test_stop_during_generation(
    automation: AutomationService, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = automation.runs.agent.propose

    def stop_then_propose(*args: object):
        automation.stop()
        return original(*args)

    monkeypatch.setattr(automation.runs.agent, "propose", stop_then_propose)
    enable(automation)
    due(automation)
    automation.tick()
    assert adapter.calls == 0
    assert not automation.view().enabled
    assert not automation.view().generation_in_progress


def test_freeze_resume_during_generation_invalidates_old_claim(
    automation: AutomationService, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = automation.runs.agent.propose

    def freeze_then_propose(*args: object):
        automation.freeze()
        automation.resume()
        enable(automation)
        return original(*args)

    monkeypatch.setattr(automation.runs.agent, "propose", freeze_then_propose)
    enable(automation)
    due(automation)
    automation.tick()
    assert adapter.calls == 0
    assert automation.view().enabled
    assert automation.view().last_result == "Enabled by owner; waiting for next check"


def test_execution_rechecks_schedule_authorization(
    automation: AutomationService, client: TestClient, adapter: FakeAdapter
) -> None:
    enable(automation)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    automation.stop()
    with pytest.raises(Conflict, match="Scheduled execution cancelled"):
        automation.coordinator.execute(response["id"], "stale-claim")
    assert adapter.calls == 0


def test_wrong_version_and_interval_rejected(automation: AutomationService) -> None:
    with pytest.raises(Conflict):
        automation.enable(EnableAutomation(policy_version_id="wrong", interval_seconds=30))
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EnableAutomation(policy_version_id="wrong", interval_seconds=1)


def test_in_tolerance_does_not_call_model(
    automation: AutomationService, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = adapter.state
    monkeypatch.setattr(
        adapter,
        "state",
        lambda: original().model_copy(
            update={"usdc_units": 700_000_000, "weth_units": 300_000_000}
        ),
    )

    def forbidden(*args: object):
        raise AssertionError("Model must not be called")

    monkeypatch.setattr(automation.runs.agent, "propose", forbidden)
    enable(automation)
    due(automation)
    automation.tick()
    assert automation.view().readiness.code == "NO_TRADE"
    assert adapter.calls == 0


def test_rebalance_interval_skips_check(
    automation: AutomationService, adapter: FakeAdapter
) -> None:
    from app.models.entities import PolicyVersion
    from app.schemas.domain import PolicyDraft

    with automation.sessions.begin() as session:
        wallet = session.get(Wallet, automation.address)
        row = session.get(PolicyVersion, wallet.active_version_id)
        policy = PolicyDraft.model_validate_json(row.draft_json)
        row.draft_json = policy.model_copy(
            update={
                "rebalance": policy.rebalance.model_copy(update={"minimum_interval_hours": 168})
            }
        ).model_dump_json()
        wallet.last_rebalance_timestamp = adapter.state().block_timestamp
    enable(automation)
    due(automation)
    automation.tick()
    assert "interval" in automation.view().last_result
    assert adapter.calls == 0


def test_state_read_failures_freeze_both_layers(
    automation: AutomationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable():
        raise OSError("RPC offline")

    monkeypatch.setattr(automation.runs.adapter, "state", unavailable)
    enable(automation)
    for _ in range(3):
        due(automation)
        automation.tick()
    assert automation.view().execution_paused
    assert isinstance(automation.controls, Owner)
    assert automation.controls.calls == [True]


def test_wrong_direction_blocked_by_pipeline(
    automation: AutomationService, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = automation.runs.agent.propose

    def wrong_direction(*args: object):
        from app.schemas.domain import Asset

        return original(*args).model_copy(update={"asset_in": Asset.WETH, "asset_out": Asset.USDC})

    monkeypatch.setattr(automation.runs.agent, "propose", wrong_direction)
    enable(automation)
    due(automation)
    automation.tick()
    assert "BLOCKED" in automation.view().last_result
    assert adapter.calls == 0


def test_generation_failures_never_fallback(
    automation: AutomationService, adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: object):
        raise ValueError("Invalid model output")

    monkeypatch.setattr(automation.runs.agent, "propose", unavailable)
    enable(automation)
    for _ in range(3):
        due(automation)
        automation.tick()
    assert automation.view().execution_paused
    assert not automation.view().generation_in_progress
    assert adapter.calls == 0
