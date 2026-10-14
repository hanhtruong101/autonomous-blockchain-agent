import os

import pytest
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.schemas.domain import Asset, TransactionProposal
from web3.exceptions import ContractCustomError


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_ANVIL_TESTS") != "1", reason="requires fresh local Anvil")
def test_local_execution_and_independent_limit() -> None:
    adapter = LocalSmartAccountAdapter(
        os.environ.get("TEST_ANVIL_RPC", "http://127.0.0.1:8545"),
        os.environ.get("TEST_DEPLOYMENT_PATH", "local/deployment.json"),
    )
    deployment = adapter.deployment
    assert adapter.state().usdc_units == 500_000_000
    assert adapter.state().weth_units == 500_000_000
    proposal = TransactionProposal(
        policy_version_id="test",
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
        reason="Test local execution",
    )
    assert adapter.simulate(proposal) > 0
    assert adapter.confirmed(adapter.submit(proposal))
    assert adapter.state().weth_units == 530_000_000
    prohibited = proposal.model_copy(update={"amount": 80_000_000})
    with pytest.raises(ContractCustomError):
        adapter.submit(prohibited)  # Deliberately bypass Python policy rules.
    assert adapter.state().spent_units == 30_000_000
