from datetime import datetime
from typing import Literal

from app.schemas.ai import AgentDecision, GenerationMetadata
from app.schemas.domain import Model, WalletState


class WalletObservation(Model):
    """Audit/UI quantities are strings, preserving arbitrary-size chain integers."""

    usdc_units: str
    weth_units: str
    spent_units: str
    block_timestamp: int

    @classmethod
    def from_state(cls, state: WalletState) -> "WalletObservation":
        return cls(
            usdc_units=str(state.usdc_units),
            weth_units=str(state.weth_units),
            spent_units=str(state.spent_units),
            block_timestamp=state.block_timestamp,
        )


class AgentActivity(Model):
    policy_version_id: str | None
    source: Literal["manual", "scheduled", "fixture"]
    state: Literal[
        "OBSERVING",
        "DECIDING",
        "SYSTEM_SKIPPED",
        "AI_HOLD",
        "HOLD",
        "PROPOSAL_CREATED",
        "FAILED",
        "CANCELLED",
    ]
    reason: str
    generation: GenerationMetadata | None = None
    observation: WalletObservation | None = None
    decision: AgentDecision | None = None
    calculation: str | None = None
    proposal_id: str | None = None


class ActivityItem(AgentActivity):
    id: str
    updated_at: datetime
    proposal_status: str | None = None


class ActivityView(Model):
    items: tuple[ActivityItem, ...]
    consecutive_ai_holds: int
