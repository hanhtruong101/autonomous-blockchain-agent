"""Integer-only target checks for the two equal-price, six-decimal mock assets."""

from app.schemas.domain import (
    Asset,
    PolicyDraft,
    RuleResult,
    SimulationResult,
    TransactionProposal,
    WalletState,
)


def within_tolerance(state: WalletState, policy: PolicyDraft) -> bool:
    total = state.usdc_units + state.weth_units
    if total == 0:
        return True
    if policy.minimum_usdc_ratio is not None:
        fn, fd = policy.minimum_usdc_ratio.as_integer_ratio()
        if state.usdc_units * fd < total * fn:
            return False
    numerator, denominator = policy.portfolio_targets.USDC.as_integer_ratio()
    distance = abs(state.usdc_units * denominator - total * numerator)
    return distance * 10000 <= policy.rebalance.tolerance_bps * total * denominator


def goal_improvement(
    state: WalletState,
    policy: PolicyDraft,
    proposal: TransactionProposal,
    simulation: SimulationResult,
) -> RuleResult:
    before_total = state.usdc_units + state.weth_units
    after_usdc, after_weth = state.usdc_units, state.weth_units
    valid = (
        simulation.success
        and len(simulation.expected_token_changes) == 2
        and simulation.contract_called.lower() == proposal.contract_address.lower()
        and proposal.asset_in != proposal.asset_out
    )
    changes = {item.asset: item.units for item in simulation.expected_token_changes}
    valid = valid and (
        changes.get(proposal.asset_in) == -proposal.amount
        and changes.get(proposal.asset_out, 0) > 0
    )
    after_usdc += changes.get(Asset.USDC, 0)
    after_weth += changes.get(Asset.WETH, 0)
    after_total = after_usdc + after_weth
    n, d = policy.portfolio_targets.USDC.as_integer_ratio()
    before_distance = abs(state.usdc_units * d - before_total * n)
    after_distance = abs(after_usdc * d - after_total * n)
    passed = (
        valid
        and not within_tolerance(state, policy)
        and after_usdc >= 0
        and after_weth >= 0
        and after_total > 0
        and after_distance * before_total < before_distance * after_total
    )
    return RuleResult(
        rule_name="goal_improvement",
        passed=passed,
        reason="Swap moves allocation closer to the approved target"
        if passed
        else "Swap must start outside tolerance and strictly improve the approved allocation",
        observed_value=(
            f"USDC/WETH units {state.usdc_units}/{state.weth_units} -> {after_usdc}/{after_weth}"
        ),
        required_value=(
            f"Closer to USDC target {policy.portfolio_targets.USDC}; "
            f"tolerance {policy.rebalance.tolerance_bps} bps"
        ),
    )


def minimum_allocation(
    state: WalletState,
    policy: PolicyDraft,
    simulation: SimulationResult,
) -> RuleResult:
    floor = policy.minimum_usdc_ratio
    changes = {item.asset: item.units for item in simulation.expected_token_changes}
    usdc = state.usdc_units + changes.get(Asset.USDC, 0)
    weth = state.weth_units + changes.get(Asset.WETH, 0)
    total = usdc + weth
    n, d = (0, 1) if floor is None else floor.as_integer_ratio()
    passed = floor is None or (
        simulation.success and usdc >= 0 and weth >= 0 and total > 0 and usdc * d >= total * n
    )
    return RuleResult(
        rule_name="minimum_usdc_allocation",
        passed=passed,
        reason="Minimum USDC allocation satisfied"
        if passed
        else "Simulated allocation violates the approved minimum USDC share",
        observed_value=f"Simulated USDC units {usdc} of total {total}",
        required_value="No hard minimum configured" if floor is None else f"USDC share >= {floor}",
    )
