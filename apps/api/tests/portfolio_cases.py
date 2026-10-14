"""Synthetic portfolio fixtures for sizing regression tests."""

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.domain import (
    Deployment,
    PolicyDraft,
    Rebalance,
    SpendingLimit,
    Targets,
    WalletState,
)


@dataclass(frozen=True)
class Scenario:
    name: str
    usdc: int
    weth: int
    target: str
    expected_action: str
    expected_amount: int
    spent: int = 0
    tolerance: int = 0
    cap: str = "30"
    floor: str | None = None
    simulation_success: bool = True


SCENARIOS = (
    Scenario("Far above target", 1000, 0, "0.70", "USDC->WETH", 30),
    Scenario("Far below target", 500, 500, "0.70", "WETH->USDC", 30),
    Scenario("Small excess", 960, 40, "0.95", "USDC->WETH", 10),
    Scenario("Small deficit", 940, 60, "0.95", "WETH->USDC", 10),
    Scenario("At target", 950, 50, "0.95", "HOLD", 0),
    Scenario("Inside tolerance", 945, 55, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Upper band boundary", 960, 40, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Lower band boundary", 940, 60, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Only two units of budget", 1000, 0, "0.70", "USDC->WETH", 2, spent=98),
    Scenario("Budget exhausted", 1000, 0, "0.70", "HOLD", 0, spent=100),
    Scenario("Five-unit trade ceiling", 1000, 0, "0.70", "USDC->WETH", 5, cap="5"),
    Scenario("Hard minimum permits target", 960, 40, "0.95", "USDC->WETH", 10, floor="0.95"),
    Scenario("Minimum cannot be restored in one trade", 900, 100, "0.95", "HOLD", 0, floor="0.95"),
    Scenario(
        "Minimum overrides tolerance",
        940,
        60,
        "0.95",
        "WETH->USDC",
        10,
        floor="0.95",
        tolerance=500,
    ),
    Scenario("Large trade needs approval", 1000, 0, "0.92", "USDC->WETH", 80, cap="100"),
    Scenario(
        "Simulation failure blocks", 1000, 0, "0.70", "USDC->WETH", 30, simulation_success=False
    ),
)


def fixtures(case: Scenario) -> tuple[Deployment, PolicyDraft, WalletState]:
    deployment = Deployment(
        chain_id=31337,
        **{
            name: "0x" + f"{index:02x}" * 20
            for index, name in enumerate(
                ("owner", "agent", "recipient", "usdc", "weth", "dex", "account"), 1
            )
        },
    )
    policy = PolicyDraft(
        daily_spending_limit=SpendingLimit(amount=Decimal("100")),
        maximum_trade_amount=Decimal(case.cap),
        minimum_usdc_ratio=Decimal(case.floor) if case.floor else None,
        allowed_contracts=(deployment.dex,),
        rebalance=Rebalance(minimum_interval_hours=0, tolerance_bps=case.tolerance),
        portfolio_targets=Targets(USDC=Decimal(case.target), WETH=1 - Decimal(case.target)),
        maximum_slippage_bps=100,
    )
    state = WalletState(
        address=deployment.account,
        chain_id=31337,
        usdc_units=case.usdc * 1_000_000,
        weth_units=case.weth * 1_000_000,
        spent_units=case.spent * 1_000_000,
        block_timestamp=1800000000,
    )
    return deployment, policy, state
