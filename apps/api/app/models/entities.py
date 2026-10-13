from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas.domain import now


def identifier() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(80))


class Wallet(Base):
    __tablename__ = "wallets"
    id: Mapped[str] = mapped_column(String(42), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    active_version_id: Mapped[str | None] = mapped_column(String(36))
    busy_proposal_id: Mapped[str | None] = mapped_column(String(36))
    execution_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    generating_run_id: Mapped[str | None] = mapped_column(String(36))
    last_rebalance_timestamp: Mapped[int | None] = mapped_column(Integer)


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), unique=True)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"))
    goal: Mapped[str] = mapped_column(Text)
    draft_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"))
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    proposal_json: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    evaluation_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PROPOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SimulationRecord(Base):
    __tablename__ = "simulation_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    result_json: Mapped[str] = mapped_column(Text)


class RiskRecord(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    result_json: Mapped[str] = mapped_column(Text)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    proposal_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(36))


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(66))
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Automation(Base):
    __tablename__ = "automation"
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), primary_key=True)
    policy_version_id: Mapped[str | None] = mapped_column(String(36))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    running: Mapped[bool] = mapped_column(Boolean, default=False)
    check_id: Mapped[str | None] = mapped_column(String(36))
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str] = mapped_column(String(240), default="Not enabled")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
