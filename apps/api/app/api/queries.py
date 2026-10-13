from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ExecutionRecord,
    PolicyVersion,
    Proposal,
)
from app.schemas.ai import GenerationMetadata
from app.schemas.domain import Evaluation, PolicyDraft, TransactionProposal, as_utc
from app.schemas.responses import ApprovalView, ExecutionView, PolicyView, ProposalView


def policy_view(row: PolicyVersion) -> PolicyView:
    draft = PolicyDraft.model_validate_json(row.draft_json)
    target = draft.portfolio_targets.USDC * 100
    tolerance = Decimal(draft.rebalance.tolerance_bps) / 100
    lower = max(Decimal(0), target - tolerance)
    if draft.minimum_usdc_ratio is not None:
        lower = max(lower, draft.minimum_usdc_ratio * 100)
    upper = min(Decimal(100), target + tolerance)
    return PolicyView(
        target_usdc_percent=str(target),
        target_weth_percent=str(draft.portfolio_targets.WETH * 100),
        accepted_usdc_range=f"{lower}% to {upper}%",
        minimum_usdc_percent=str(draft.minimum_usdc_ratio * 100)
        if draft.minimum_usdc_ratio is not None
        else None,
        id=row.id,
        policy_id=row.policy_id,
        goal=row.goal,
        status=row.status,
        draft=draft,
        created_at=as_utc(row.created_at),
    )


def approval_view(row: ApprovalRequest) -> ApprovalView:
    return ApprovalView(
        id=row.id,
        proposal_id=row.proposal_id,
        status=row.status,
        expires_at=as_utc(row.expires_at),
        decided_by=row.decided_by,
    )


def execution_view(row: ExecutionRecord) -> ExecutionView:
    return ExecutionView(
        id=row.id,
        proposal_id=row.proposal_id,
        status=row.status,
        transaction_hash=row.transaction_hash,
        created_at=as_utc(row.created_at),
    )


def proposal_view(session: Session, row: Proposal) -> ProposalView:
    approval = session.scalar(select(ApprovalRequest).where(ApprovalRequest.proposal_id == row.id))
    execution = session.scalar(select(ExecutionRecord).where(ExecutionRecord.proposal_id == row.id))
    metadata = session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == row.id, AuditEvent.event == "PROPOSAL_GENERATION"
        )
    )
    return ProposalView(
        generation=GenerationMetadata.model_validate_json(metadata.details) if metadata else None,
        id=row.id,
        status=row.status,
        proposal=TransactionProposal.model_validate_json(row.proposal_json),
        evaluation=Evaluation.model_validate_json(row.evaluation_json)
        if row.evaluation_json
        else None,
        approval=approval_view(approval) if approval else None,
        execution=execution_view(execution) if execution else None,
    )
