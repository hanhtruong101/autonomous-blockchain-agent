"""Explicit opt-in real PostgreSQL claim and real Anvil freeze integration."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from app.api.application import create_app
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.blockchain.owner import LocalOwnerControls
from app.config.settings import Settings
from app.execution.agent_runs import AgentRuns
from app.execution.automation import AutomationService
from app.execution.coordinator import ExecutionCoordinator
from app.execution.pipeline import Pipeline
from app.models.entities import Base
from app.schemas.domain import Deployment
from app.simulation.engine import RpcSimulationEngine
from conftest import TOKEN, FakeAdapter
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_api import activate
from test_automation import Owner, due, enable


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requires isolated PostgreSQL")
def test_postgres_single_claim_and_responsive_freeze(
    deployment: Deployment, monkeypatch: pytest.MonkeyPatch
) -> None:
    deployment = deployment.model_copy(update={"account": "0x" + uuid4().hex + "12345678"})
    adapter = FakeAdapter(deployment)
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with TestClient(
        create_app(Settings(owner_token=SecretStr(TOKEN)), adapter, sessions),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        activate(client, "30")
        pipeline = Pipeline(adapter, RpcSimulationEngine(adapter))
        runs = AgentRuns(adapter, pipeline)
        service = AutomationService(
            sessions, runs, ExecutionCoordinator(sessions, pipeline), Owner(), True
        )
        original = runs.agent.propose
        entered, release = Event(), Event()

        def slow_model(*args: object):
            entered.set()
            assert release.wait(10)
            return original(*args)

        monkeypatch.setattr(runs.agent, "propose", slow_model)
        enable(service)
        due(service)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(service.tick)
            try:
                if not entered.wait(3):
                    first.result(timeout=5)
                    pytest.fail("Scheduled generation never started")
                pool.submit(service.tick).result(timeout=5)
                service.freeze()
                assert service.view().execution_paused
            finally:
                release.set()
            first.result(timeout=10)
        assert adapter.calls == 0
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_AUTOMATION_ANVIL") != "1", reason="requires fresh isolated Anvil"
)
def test_scheduled_trade_and_owner_freeze_on_anvil(tmp_path) -> None:
    adapter = LocalSmartAccountAdapter(
        os.environ["TEST_ANVIL_RPC"], os.environ["TEST_DEPLOYMENT_PATH"]
    )
    assert adapter.state().spent_units == 0
    engine = create_engine(f"sqlite:///{tmp_path / 'automation.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with TestClient(
        create_app(Settings(owner_token=SecretStr(TOKEN)), adapter, sessions),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        activate(client, "30")
        pipeline = Pipeline(adapter, RpcSimulationEngine(adapter))
        service = AutomationService(
            sessions,
            AgentRuns(adapter, pipeline),
            ExecutionCoordinator(sessions, pipeline),
            LocalOwnerControls(adapter),
            True,
        )
        enable(service)
        due(service)
        service.tick()
        assert adapter.state().spent_units == 30_000_000
        proposal = client.get("/proposals").json()[0]
        assert proposal["status"] == "EXECUTED"
        assert proposal["execution"]["transaction_hash"]
        assert any(
            rule["rule_name"] == "goal_improvement" and rule["passed"]
            for rule in proposal["evaluation"]["policy"]["rules"]
        )
        service.freeze()
        assert adapter.account.functions.paused().call()
        assert client.post("/agent/runs", json={}).status_code == 409
        service.resume()
        assert not adapter.account.functions.paused().call()
        assert not service.view().enabled
    engine.dispose()
