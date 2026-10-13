import pytest
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.schemas.domain import Deployment, TransactionProposal
from app.simulation.engine import RpcSimulationEngine
from web3 import Web3
from web3.exceptions import ContractCustomError


@pytest.mark.parametrize(
    "signature,expected",
    [
        ("LimitExceeded()", "On-chain daily spending limit exceeded"),
        ("Paused()", "Smart account is paused"),
        ("Unauthorized()", "Agent is unauthorized or revoked"),
        ("Replay()", "This proposal has already executed on-chain"),
    ],
)
def test_known_revert_reason(
    signature: str,
    expected: str,
    deployment: Deployment,
    proposal: TransactionProposal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RevertingOperation:
        def call(self, transaction: dict[str, str]) -> None:
            raise ContractCustomError(
                "Do not log arbitrary provider text", Web3.keccak(text=signature)[:4].to_0x_hex()
            )

    adapter = object.__new__(LocalSmartAccountAdapter)
    adapter.deployment = deployment
    monkeypatch.setattr(adapter, "operation", lambda proposal: RevertingOperation())
    result = RpcSimulationEngine(adapter).simulate(proposal)
    assert not result.success
    assert result.revert_reason == expected
