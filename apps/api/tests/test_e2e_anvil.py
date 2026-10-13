import os
from pathlib import Path

import pytest
from app.api.application import create_app
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.config.settings import Settings
from app.models.entities import Base
from conftest import GOAL, TOKEN
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_ANVIL_E2E") != "1", reason="requires fresh deployed Anvil")
def test_real_chain_complete_flow(tmp_path: Path) -> None:
    engine = create_engine(os.environ.get("TEST_POSTGRES_URL", f"sqlite:///{tmp_path / 'e2e.db'}"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    adapter = LocalSmartAccountAdapter(
        os.environ.get("TEST_ANVIL_RPC", "http://localhost:8545"),
        os.environ.get("TEST_DEPLOYMENT_PATH", "local/deployment.json"),
    )
    assert adapter.state().spent_units == 0, "Start with fresh deployment"
    app = create_app(Settings(owner_token=SecretStr(TOKEN)), adapter, sessions)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        draft = client.post("/policies", json={"goal": GOAL}).json()
        assert client.post(f"/policies/{draft['id']}/approve").status_code == 200
        for scenario, expected in [
            ("A", "EXECUTED"),
            ("B", "BLOCKED"),
            ("C", "BLOCKED"),
            ("D", "BLOCKED"),
        ]:
            response = client.post("/agent/runs", json={"scenario": scenario})
            assert response.status_code == 201, response.text
            assert response.json()["status"] == expected, response.text
        medium = client.post("/agent/runs", json={"scenario": "medium"}).json()
        assert medium["status"] == "AWAITING_APPROVAL"
        approved = client.post(f"/approvals/{medium['approval']['id']}/approve")
        assert approved.json()["status"] == "EXECUTED", approved.text
        assert adapter.state().spent_units == 100_000_000
        assert adapter.state().weth_units == 100_000_000
        assert len(client.get("/transactions").json()) == 2
    engine.dispose()
