"""Shared manual/scheduled readiness decisions based on the current chain snapshot."""

from datetime import UTC, datetime

from app.agent.sizing import calculate_plan
from app.schemas.domain import PolicyDraft, WalletState
from app.schemas.readiness import Readiness


def portfolio_readiness(
    state: WalletState, policy: PolicyDraft, last_trade: int | None
) -> Readiness:
    # Exhausted spending takes precedence over cadence for both run entry points.
    if state.spent_units >= int(policy.daily_spending_limit.amount * 1_000_000):
        return Readiness(
            code="BUDGET_EXHAUSTED",
            reason="Daily budget exhausted; waiting for a new chain day",
            next_step=(
                "Wait for the next UTC day on the local chain. A policy change "
                "does not reset spending."
            ),
            eligible_after=datetime.fromtimestamp(
                (state.block_timestamp // 86400 + 1) * 86400, UTC
            ),
        )
    if last_trade is not None:
        eligible = last_trade + policy.rebalance.minimum_interval_hours * 3600
        if state.block_timestamp < eligible:
            return Readiness(
                code="WAITING_INTERVAL",
                reason="Waiting for the policy rebalance interval",
                next_step=(
                    "Wait until the chain reaches the eligible time, or review and "
                    "approve a new cadence."
                ),
                eligible_after=datetime.fromtimestamp(eligible, UTC),
            )
    plan = calculate_plan(state, policy)
    if plan.amount == 0:
        return Readiness(
            code="NO_TRADE",
            reason=plan.reason,
            next_step="No transaction will be submitted. Review your policy if this is unexpected.",
        )
    return Readiness(
        code="READY",
        reason="Portfolio is eligible for a rebalance proposal",
        next_step=(
            "Run once or enable automatic checks. Every proposal still passes "
            "simulation, policy and risk checks."
        ),
    )
