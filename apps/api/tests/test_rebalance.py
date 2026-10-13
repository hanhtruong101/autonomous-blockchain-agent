import pytest
from app.policies.rebalance import goal_improvement, within_tolerance
from app.schemas.domain import Asset, PolicyDraft, TransactionProposal
from app.simulation.engine import RpcSimulationEngine
from conftest import FakeAdapter


@pytest.mark.parametrize(
    "usdc,expected", [(650, True), (750, True), (649, False), (751, False), (700, True)]
)
def test_tolerance_boundaries(
    adapter: FakeAdapter, policy: PolicyDraft, usdc: int, expected: bool
) -> None:
    state = adapter.state().model_copy(
        update={"usdc_units": usdc * 10**25, "weth_units": (1000 - usdc) * 10**25}
    )
    assert within_tolerance(state, policy) is expected


def test_goal_wrong_direction(
    adapter: FakeAdapter, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    state = adapter.state().model_copy(
        update={"usdc_units": 500_000_000, "weth_units": 500_000_000}
    )
    simulation = RpcSimulationEngine(adapter).simulate(proposal)
    assert not goal_improvement(state, policy, proposal, simulation).passed
    reverse = proposal.model_copy(update={"asset_in": Asset.WETH, "asset_out": Asset.USDC})
    assert goal_improvement(
        state, policy, reverse, RpcSimulationEngine(adapter).simulate(reverse)
    ).passed


def test_overshoot_and_missing_deltas(
    adapter: FakeAdapter, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    excessive = proposal.model_copy(update={"amount": 700_000_000})
    simulation = RpcSimulationEngine(adapter).simulate(excessive)
    assert not goal_improvement(adapter.state(), policy, excessive, simulation).passed
    normal = RpcSimulationEngine(adapter).simulate(proposal)
    assert not goal_improvement(
        adapter.state(), policy, proposal, normal.model_copy(update={"expected_token_changes": ()})
    ).passed


def test_inside_tolerance_no_trade(
    adapter: FakeAdapter, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    state = adapter.state().model_copy(
        update={"usdc_units": 740_000_000, "weth_units": 260_000_000}
    )
    assert not goal_improvement(
        state, policy, proposal, RpcSimulationEngine(adapter).simulate(proposal)
    ).passed
