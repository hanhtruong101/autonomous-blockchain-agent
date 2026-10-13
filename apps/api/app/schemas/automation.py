"""Typed owner controls and automation status; no model authority."""

from datetime import datetime

from pydantic import Field

from app.schemas.domain import Model
from app.schemas.readiness import Readiness


class EnableAutomation(Model):
    policy_version_id: str
    interval_seconds: int = Field(default=300, strict=True, ge=30, le=604800)


class AutomationView(Model):
    readiness: Readiness
    enabled: bool
    running: bool
    execution_paused: bool
    generation_in_progress: bool
    policy_version_id: str | None
    interval_seconds: int
    next_check_at: datetime | None
    last_check_at: datetime | None
    last_result: str
    consecutive_failures: int
    worker_available: bool
