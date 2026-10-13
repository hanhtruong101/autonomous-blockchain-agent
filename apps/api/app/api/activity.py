"""Read a bounded activity projection from immutable audit snapshots."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import AuditEvent, Proposal, Wallet
from app.schemas.activity import ActivityItem, ActivityView, AgentActivity
from app.schemas.domain import as_utc


def activity_view(session: Session, wallet_address: str) -> ActivityView:
    latest = (
        select(func.max(AuditEvent.id))
        .where(AuditEvent.event == "AGENT_ACTIVITY")
        .group_by(AuditEvent.entity_id)
    )
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.id.in_(latest)).order_by(AuditEvent.id.desc()).limit(50)
    ).all()
    snapshots = [(event, AgentActivity.model_validate_json(event.details)) for event in events]
    ids = [snapshot.proposal_id for _, snapshot in snapshots if snapshot.proposal_id]
    proposals = {
        row.id: row.status for row in session.scalars(select(Proposal).where(Proposal.id.in_(ids)))
    }
    items = tuple(
        ActivityItem(
            **snapshot.model_dump(),
            id=event.entity_id,
            updated_at=as_utc(event.created_at),
            proposal_status=proposals.get(snapshot.proposal_id or ""),
        )
        for event, snapshot in snapshots
    )
    holds = 0
    wallet = session.get(Wallet, wallet_address)
    version = wallet.active_version_id if wallet else None
    for item in items:
        if item.policy_version_id != version:
            break
        if item.source == "fixture" or item.state == "SYSTEM_SKIPPED":
            continue
        if item.state != "AI_HOLD":
            break
        holds += 1
    return ActivityView(items=items, consecutive_ai_holds=holds)
