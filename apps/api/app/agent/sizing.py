"""Exact sizing for two equal-price mock tokens. No provider or execution dependency."""

from app.policies.rebalance import within_tolerance
from app.schemas.domain import Asset, Model, PolicyDraft, WalletState


class RebalancePlan(Model):
    asset_in: Asset = Asset.USDC
    asset_out: Asset = Asset.WETH
    amount: int = 0
    reason: str


def calculate_plan(state: WalletState, policy: PolicyDraft) -> RebalancePlan:
    if not policy.rebalance.enabled:
        return RebalancePlan(reason="Rebalancing is disabled by the approved policy.")
    if within_tolerance(state, policy):
        return RebalancePlan(
            reason="Portfolio is within the approved target range; no trade is needed."
        )
    remaining = max(0, int(policy.daily_spending_limit.amount * 1_000_000) - state.spent_units)
    if remaining == 0:
        return RebalancePlan(reason="Daily budget exhausted; wait for a new chain day.")
    total = state.usdc_units + state.weth_units
    n, d = policy.portfolio_targets.USDC.as_integer_ratio()
    signed_distance = state.usdc_units * d - total * n
    needed = abs(signed_distance) // d
    amount = min(needed, remaining, int(policy.maximum_trade_amount * 1_000_000))
    if amount == 0:
        return RebalancePlan(
            reason="Target difference is smaller than one token unit; no trade is needed."
        )
    selling_usdc = signed_distance > 0
    after_usdc = state.usdc_units - amount if selling_usdc else state.usdc_units + amount
    if policy.minimum_usdc_ratio is not None:
        fn, fd = policy.minimum_usdc_ratio.as_integer_ratio()
        if after_usdc * fd < total * fn:
            return RebalancePlan(
                reason=(
                    "The minimum USDC allocation cannot be met in one permitted trade. "
                    "Review the policy and remaining budget."
                )
            )
    return RebalancePlan(
        asset_in=Asset.USDC if selling_usdc else Asset.WETH,
        asset_out=Asset.WETH if selling_usdc else Asset.USDC,
        amount=amount,
        reason=(
            f"Calculated {amount} token units from target gap {needed}, remaining daily "
            f"budget {remaining}, and per-trade ceiling "
            f"{int(policy.maximum_trade_amount * 1_000_000)}. "
            "The trade does not cross the target. Values use the fixed 1:1 mock price."
        ),
    )
