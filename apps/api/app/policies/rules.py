from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.schemas.domain import PolicyDecision, PolicyDraft, RuleResult, TransactionProposal


@dataclass(frozen=True)
class PolicyContext:
    policy: PolicyDraft
    wallet: str
    spent_units: int
    seconds_since_rebalance: int | None


def describe(value: object) -> str:
    if isinstance(value, (tuple, list)):
        return ", ".join(describe(item) for item in value)
    return "No previous rebalance" if value is None else str(value)


def result(name: str, passed: bool, observed: object, required: object) -> RuleResult:
    actual, expected = describe(observed), describe(required)
    return RuleResult(
        rule_name=name,
        passed=passed,
        reason=(
            f"{name.replace('_', ' ')} passed"
            if passed
            else f"{name.replace('_', ' ')} failed: observed {actual}; required {expected}"
        ),
        observed_value=actual,
        required_value=expected,
    )


class Rule(Protocol):
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult: ...


class DailySpendingLimitRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        maximum = int(context.policy.daily_spending_limit.amount * 1_000_000)
        total = context.spent_units + proposal.amount
        return result(
            "daily_spending_limit",
            total <= maximum,
            f"{Decimal(total) / 1_000_000} TestUSDC total today",
            f"At most {Decimal(maximum) / 1_000_000} TestUSDC per day",
        )


class TradeSpendingLimitRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        maximum = int(context.policy.maximum_trade_amount * 1_000_000)
        return result(
            "trade_spending_limit",
            proposal.amount <= maximum,
            proposal.amount,
            f"At most {maximum} token units per trade",
        )


class AllowedAssetRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        allowed = context.policy.allowed_assets
        return result(
            "allowed_assets",
            proposal.asset_in in allowed and proposal.asset_out in allowed,
            (proposal.asset_in, proposal.asset_out),
            allowed,
        )


class AllowedProtocolRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        allowed = context.policy.allowed_protocols
        return result("allowed_protocol", proposal.protocol in allowed, proposal.protocol, allowed)


class AllowedContractRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        allowed = [address.lower() for address in context.policy.allowed_contracts]
        return result(
            "allowed_contract",
            proposal.contract_address.lower() in allowed,
            proposal.contract_address,
            allowed,
        )


class RebalanceFrequencyRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        elapsed = context.seconds_since_rebalance
        minimum = context.policy.rebalance.minimum_interval_hours * 3600
        passed = context.policy.rebalance.enabled and (elapsed is None or elapsed >= minimum)
        return result(
            "rebalance_frequency",
            passed,
            None if elapsed is None else f"{elapsed} seconds since last action",
            f"Enabled, at least {minimum} seconds between actions",
        )


class MaximumSlippageRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        maximum = context.policy.maximum_slippage_bps
        return result(
            "maximum_slippage",
            proposal.maximum_slippage_bps <= maximum,
            f"{proposal.maximum_slippage_bps} basis points",
            f"At most {maximum} basis points",
        )


class IdentityRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        passed = (
            proposal.chain_id == 31337
            and proposal.wallet.lower() == context.wallet.lower()
            and proposal.destination.lower() == context.wallet.lower()
        )
        return result(
            "chain_wallet_destination",
            passed,
            (proposal.chain_id, proposal.wallet, proposal.destination),
            (31337, context.wallet),
        )


class OperationRule:
    def check(self, proposal: TransactionProposal, context: PolicyContext) -> RuleResult:
        passed = (
            proposal.action_type == "SWAP"
            and proposal.operation == "swap"
            and proposal.asset_in != proposal.asset_out
        )
        return result("operation", passed, proposal.operation, "swap between different assets")


class PolicyEngine:
    def __init__(self) -> None:
        self.rules: tuple[Rule, ...] = (
            DailySpendingLimitRule(),
            TradeSpendingLimitRule(),
            AllowedAssetRule(),
            AllowedProtocolRule(),
            AllowedContractRule(),
            RebalanceFrequencyRule(),
            MaximumSlippageRule(),
            IdentityRule(),
            OperationRule(),
        )

    def evaluate(self, proposal: TransactionProposal, context: PolicyContext) -> PolicyDecision:
        results = tuple(rule.check(proposal, context) for rule in self.rules)
        return PolicyDecision(allowed=all(item.passed for item in results), rules=results)
