from collections.abc import Iterator
from decimal import Decimal

import pytest
from app.api.application import create_app
from app.config.settings import Settings
from app.models.entities import Base
from app.schemas.domain import (
    Asset,
    Deployment,
    PolicyDraft,
    Rebalance,
    SpendingLimit,
    Targets,
    TransactionProposal,
    WalletState,
)
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TOKEN = "local-tests-only-owner-token-123456"
GOAL = (
    "Keep approximately 70% of my portfolio in USDC, never spend more than 100 USDC per day, "
    "rebalance on demand, and only interact with approved protocols."
)


@pytest.fixture(autouse=True)
def offline_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer's shell must never cause the normal suite to make paid calls.
    monkeypatch.setenv("AUTONOMY_AI_PROVIDER", "offline")
    monkeypatch.setenv("AUTONOMY_AUTOMATION_WORKER", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def deployment() -> Deployment:
    return Deployment(
        chain_id=31337,
        owner="0x" + "01" * 20,
        agent="0x" + "02" * 20,
        recipient="0x" + "03" * 20,
        usdc="0x" + "04" * 20,
        weth="0x" + "05" * 20,
        dex="0x" + "06" * 20,
        account="0x" + "07" * 20,
    )


@pytest.fixture
def policy(deployment: Deployment) -> PolicyDraft:
    return PolicyDraft(
        daily_spending_limit=SpendingLimit(amount=Decimal(100)),
        allowed_contracts=(deployment.dex,),
        rebalance=Rebalance(minimum_interval_hours=0),
        portfolio_targets=Targets(USDC=Decimal("0.7"), WETH=Decimal("0.3")),
        maximum_slippage_bps=100,
    )


@pytest.fixture
def proposal(deployment: Deployment) -> TransactionProposal:
    return TransactionProposal(
        policy_version_id="version",
        chain_id=31337,
        wallet=deployment.account,
        asset_in=Asset.USDC,
        asset_out=Asset.WETH,
        amount=30_000_000,
        destination=deployment.account,
        protocol="MockDex",
        contract_address=deployment.dex,
        operation="swap",
        maximum_slippage_bps=100,
        reason="Test rebalance",
    )


class FakeAdapter:
    def __init__(self, deployment: Deployment) -> None:
        self.deployment = deployment
        self.spent = 0
        self.calls = 0
        self.fail_simulation = False
        self.fail_submit = False
        self.receipt_success = True

    def state(self) -> WalletState:
        return WalletState(
            address=self.deployment.account,
            chain_id=31337,
            usdc_units=1_000_000_000 - self.spent,
            weth_units=self.spent,
            spent_units=self.spent,
            block_timestamp=1_800_000_000,
        )

    def simulate(self, proposal: TransactionProposal) -> int:
        if self.fail_simulation:
            raise ValueError("reverted")
        return 100000

    def submit(self, proposal: TransactionProposal) -> str:
        self.calls += 1
        if self.fail_submit:
            raise OSError("connection lost")
        if self.receipt_success:
            self.spent += proposal.amount
        return "0x" + "ab" * 32

    def confirmed(self, transaction_hash: str) -> bool:
        return self.receipt_success


@pytest.fixture
def adapter(deployment: Deployment) -> FakeAdapter:
    return FakeAdapter(deployment)


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(adapter: FakeAdapter, sessions: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app(Settings(owner_token=SecretStr(TOKEN)), adapter, sessions)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client
