import re
from decimal import Decimal
from typing import Protocol

from app.schemas.ai import PolicyIntent, StructuredProvider
from app.schemas.domain import PolicyDraft, Rebalance, SpendingLimit, Targets


class PolicyInterpreter(Protocol):
    def interpret(self, goal: str) -> PolicyDraft: ...


class LocalPolicyInterpreter:
    """Bounded offline grammar; never pretends to understand arbitrary instructions."""

    def __init__(self, dex: str) -> None:
        self.dex = dex

    def interpret(self, goal: str) -> PolicyDraft:
        match = re.fullmatch(
            r"Keep (approximately|at least) (\d{1,3})% of my portfolio in USDC, "
            r"never spend more than (\d+(?:\.\d{1,6})?) USDC per day, "
            r"rebalance (weekly|daily|on demand), and only interact with approved protocols\.?",
            goal.strip(),
            re.IGNORECASE,
        )
        if not match:
            raise ValueError(
                "Unsupported goal. Use the displayed template; arbitrary text is not interpreted."
            )
        target = Decimal(match[2]) / 100
        interval = {"weekly": 168, "daily": 24, "on demand": 0}[match[4].lower()]
        return PolicyDraft(
            minimum_usdc_ratio=target if match[1].lower() == "at least" else None,
            daily_spending_limit=SpendingLimit(amount=Decimal(match[3])),
            allowed_contracts=(self.dex,),
            rebalance=Rebalance(minimum_interval_hours=interval),
            portfolio_targets=Targets(USDC=target, WETH=1 - target),
            maximum_slippage_bps=100,
        )


class ProviderPolicyInterpreter:
    """Provider integration has no chain, database or activation capabilities."""

    def __init__(self, provider: StructuredProvider, dex: str) -> None:
        self.provider = provider
        self.dex = dex

    def interpret(self, goal: str) -> PolicyDraft:
        import json

        response = self.provider.generate(
            json.dumps({"task": "policy_draft", "goal": goal}),
            json.dumps(PolicyIntent.model_json_schema(mode="serialization")),
        )
        intent = PolicyIntent.model_validate_json(response)
        return PolicyDraft(
            minimum_usdc_ratio=intent.minimum_usdc_ratio,
            daily_spending_limit=intent.daily_spending_limit,
            rebalance=intent.rebalance,
            portfolio_targets=intent.portfolio_targets,
            maximum_slippage_bps=intent.maximum_slippage_bps,
            allowed_contracts=(self.dex,),
        )


class FakePolicyInterpreter:
    def __init__(self, draft: PolicyDraft) -> None:
        self.draft = draft

    def interpret(self, goal: str) -> PolicyDraft:
        return self.draft
