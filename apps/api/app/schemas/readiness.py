from datetime import datetime
from typing import Literal

from app.schemas.domain import Model


class Readiness(Model):
    code: Literal[
        "READY",
        "WAITING_INTERVAL",
        "BUDGET_EXHAUSTED",
        "NO_TRADE",
        "FROZEN",
        "PENDING_REVIEW",
        "RECONCILIATION",
        "GENERATING",
        "NO_POLICY",
        "UNAVAILABLE",
    ]
    reason: str
    next_step: str
    eligible_after: datetime | None = None
    proposal_id: str | None = None
    generation_started_at: datetime | None = None
