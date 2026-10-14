import json
import os
from pathlib import Path

import pytest
from app.api.application import create_app
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.config.settings import Settings
from app.models.entities import Base, ExecutionRecord
from conftest import GOAL, TOKEN
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_AI_ANVIL") != "1", reason="requires isolated fresh Anvil")
def test_mock_ai_real_chain(tmp_path: Path) -> None:
    """Mock only model generation; policy, simulation and execution use actual Anvil."""
    adapter = LocalSmartAccountAdapter(
        os.environ.get("TEST_ANVIL_RPC", "http://127.0.0.1:8545"),
        os.environ.get("TEST_DEPLOYMENT_PATH", "local/deployment.json"),
    )
    assert adapter.state().spent_units == 0
    engine = create_engine(os.environ.get("TEST_POSTGRES_URL", f"sqlite:///{tmp_path / 'ai.db'}"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    class Provider:
        amount = "30000000"
        protocol = "MockDex"
        slippage = 100

        def generate(self, goal: str, schema: str) -> str:
            if json.loads(goal)["task"] == "policy_draft":
                return json.dumps(
                    {
                        "daily_spending_limit": {"asset": "USDC", "amount": "100"},
                        "rebalance": {"enabled": True, "minimum_interval_hours": 0},
                        "portfolio_targets": {"USDC": "0.7", "WETH": "0.3"},
                        "maximum_slippage_bps": 100,
                        "protocol": "MockDex",
                    }
                )
            return json.dumps(
                {
                    "action": "SWAP",
                    "amount_units": self.amount,
                    "protocol": self.protocol,
                    "asset_in": "WETH",
                    "asset_out": "USDC",
                    "maximum_slippage_bps": self.slippage,
                    "reason": "Mock AI local integration",
                }
            )

    provider = Provider()
    settings = Settings(
        ai_provider="openai", OPENAI_API_KEY="mock-only", owner_token=SecretStr(TOKEN)
    )
    evidence = []
    with TestClient(
        create_app(settings, adapter, sessions, provider),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as client:
        draft = client.post("/policies", json={"goal": GOAL}).json()
        client.post(f"/policies/{draft['id']}/approve")
        first = client.post("/agent/runs", json={}).json()
        assert first["status"] == "EXECUTED"
        assert first["generation"]["execution_mode"] == "ai_trade_proposal"
        first_hash = first["execution"]["transaction_hash"]
        receipt = adapter.web3.eth.get_transaction_receipt(first_hash)
        assert receipt["status"] == 1 and len(receipt["logs"]) > 0
        evidence.append({"status": "EXECUTED", "hash": first_hash, "logs": len(receipt["logs"])})
        nonce = adapter.web3.eth.get_transaction_count(adapter.deployment.agent)
        for amount, protocol, slippage in [
            ("80000000", "MockDex", 100),
            ("40000000", "Unknown", 100),
            ("20000000", "MockDex", 2000),
        ]:
            provider.amount, provider.protocol, provider.slippage = amount, protocol, slippage
            response = client.post("/agent/runs", json={})
            if protocol == "Unknown":
                assert response.status_code == 422
            else:
                assert response.json()["status"] == "BLOCKED"
                assert response.json()["execution"] is None
            assert adapter.web3.eth.get_transaction_count(adapter.deployment.agent) == nonce
            evidence.append(
                {
                    "amount": amount,
                    "protocol": protocol,
                    "status": "BLOCKED",
                    "agent_nonce_unchanged": nonce,
                }
            )
        provider.amount, provider.protocol, provider.slippage = "70000000", "MockDex", 100
        medium = client.post("/agent/runs", json={}).json()
        assert medium["status"] == "AWAITING_APPROVAL"
        assert adapter.web3.eth.get_transaction_count(adapter.deployment.agent) == nonce
        approved = client.post(f"/approvals/{medium['approval']['id']}/approve").json()
        assert approved["status"] == "EXECUTED"
        evidence.append(
            {"status": "OWNER_APPROVED_EXECUTED", "hash": approved["execution"]["transaction_hash"]}
        )
        assert adapter.state().usdc_units == 600_000_000
        assert adapter.state().weth_units == 400_000_000
        with sessions() as session:
            assert len(list(session.scalars(select(ExecutionRecord)))) == 2
        evidence.append(
            {
                "final_usdc_units": adapter.state().usdc_units,
                "final_weth_units": adapter.state().weth_units,
                "execution_records": 2,
            }
        )
        print(json.dumps(evidence, indent=2))
    engine.dispose()
