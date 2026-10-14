"""Untrusted AI output has no address, chain, calldata or permission fields."""

from decimal import Decimal
from typing import Annotated, Literal, Protocol

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.domain import Asset, Model, Rebalance, SpendingLimit, Targets, TransactionProposal


class StructuredProvider(Protocol):
    def generate(self, goal: str, schema: str) -> str: ...


class GenerationMetadata(Model):
    provider: Literal["offline", "openai", "ollama", "fixture"] = "offline"
    model: str | None = None
    schema_version: str = "4"
    execution_mode: (
        Literal[
            "deterministic",
            "deterministic_with_ai_explanation",
            "ai_decision_deterministic_sizing",
            "ai_trade_proposal",
            "fixture",
        ]
        | None
    ) = None


class PolicyIntent(Model):
    minimum_usdc_ratio: Decimal | None = Field(default=None, ge=0, le=1)

    @field_validator("minimum_usdc_ratio", mode="before")
    @classmethod
    def exact_floor(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use decimal strings for allocation floors")
        return value

    daily_spending_limit: SpendingLimit
    rebalance: Rebalance
    portfolio_targets: Targets
    maximum_slippage_bps: int = Field(strict=True, ge=0, le=100)
    protocol: Literal["MockDex"]


class ProposalIntent(Model):
    action: Literal["SWAP", "HOLD"]
    protocol: Literal["MockDex"]
    asset_in: Asset
    asset_out: Asset
    amount_units: Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,14})$")]
    maximum_slippage_bps: int = Field(strict=True, ge=0, le=10000)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def no_operational_details(cls, value: str) -> str:
        import re

        if re.search(r"0x[0-9a-fA-F]+|https?://", value):
            raise ValueError("Model reasoning must not contain addresses, calldata or URLs")
        return value

    @model_validator(mode="after")
    def consistent_action(self) -> "ProposalIntent":
        if self.action == "HOLD" and self.amount_units != "0":
            raise ValueError("HOLD must have zero amount")
        if self.action == "SWAP" and (
            int(self.amount_units) == 0 or self.asset_in == self.asset_out
        ):
            raise ValueError("SWAP requires a positive amount between different assets")
        return self


class AgentDecision(Model):
    """Activity summary. Historical REBALANCE records remain readable."""

    reason: str = Field(min_length=1, max_length=2000)
    action: Literal["HOLD", "REBALANCE", "SWAP"]

    @field_validator("reason")
    @classmethod
    def safe_text(cls, value: str) -> str:
        return ProposalIntent.no_operational_details(value)


class AgentAssessment(Model):
    decision: AgentDecision
    proposal: TransactionProposal | None = None

    @model_validator(mode="after")
    def hold_has_no_proposal(self) -> "AgentAssessment":
        if self.decision.action == "HOLD" and self.proposal is not None:
            raise ValueError("HOLD cannot carry a transaction")
        return self
