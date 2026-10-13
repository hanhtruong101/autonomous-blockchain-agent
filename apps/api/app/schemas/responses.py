from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.ai import GenerationMetadata
from app.schemas.domain import Evaluation, Model, PolicyDraft, TransactionProposal


class GoalInput(Model):
    goal: str = Field(min_length=10, max_length=2000)
    tolerance_bps: int | None = Field(default=None, strict=True, ge=0, le=1000)
    maximum_trade_amount: Decimal | None = Field(default=None, gt=0, le=100, decimal_places=6)
    minimum_usdc_ratio: Decimal | None = Field(default=None, ge=0, le=1)

    @field_validator("maximum_trade_amount", "minimum_usdc_ratio", mode="before")
    @classmethod
    def exact_controls(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use decimal strings for financial controls")
        return value


class ConfigurationView(Model):
    interpreter: Literal["local", "llm"]
    provider_host: str
    generation: GenerationMetadata


class RunInput(Model):
    scenario: Literal["portfolio", "A", "B", "C", "D", "medium"] = "portfolio"


class PolicyView(Model):
    target_usdc_percent: str
    target_weth_percent: str
    accepted_usdc_range: str
    minimum_usdc_percent: str | None
    id: str
    policy_id: str
    goal: str
    status: str
    draft: PolicyDraft
    created_at: datetime


class ApprovalView(Model):
    id: str
    proposal_id: str
    status: str
    expires_at: datetime
    decided_by: str | None


class ExecutionView(Model):
    id: str
    proposal_id: str
    transaction_hash: str | None
    status: str
    created_at: datetime


class ProposalView(Model):
    generation: GenerationMetadata | None = None
    id: str
    status: str
    proposal: TransactionProposal
    evaluation: Evaluation | None
    approval: ApprovalView | None
    execution: ExecutionView | None


class AuditView(Model):
    id: int
    event: str
    entity_id: str
    actor: str
    details: str
    created_at: datetime
