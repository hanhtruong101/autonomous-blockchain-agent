import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.db.repository import Repository
from app.models.entities import Base, User, Wallet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def test_transaction_rollback(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with pytest.raises(RuntimeError), sessions.begin() as session:
        session.add(User(name="rolled back"))
        session.flush()
        raise RuntimeError("rollback")
    with sessions() as session:
        assert session.scalar(select(User)) is None
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requires isolated PostgreSQL")
def test_postgres_wallet_lock_serializes_updates() -> None:
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    sessions = sessionmaker(engine)
    address = "0x" + "ab" * 20
    Base.metadata.create_all(engine)
    with sessions.begin() as session:
        Repository(session).initialize(address)
        wallet = session.get(Wallet, address)
        assert wallet is not None
        wallet.last_rebalance_timestamp = 0

    def increment() -> None:
        with sessions.begin() as session:
            wallet = Repository(session).wallet(address)
            wallet.last_rebalance_timestamp = (wallet.last_rebalance_timestamp or 0) + 1

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: increment(), range(20)))
    with sessions() as session:
        wallet = session.get(Wallet, address)
        assert wallet is not None
        assert wallet.last_rebalance_timestamp == 20
    engine.dispose()
