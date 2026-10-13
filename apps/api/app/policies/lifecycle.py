from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.recorder import record
from app.db.repository import Conflict, Repository
from app.models.entities import ApprovalRequest, Automation, Policy, PolicyVersion, Proposal
from app.schemas.domain import Deployment, PolicyDraft


class PolicyLifecycle:
    def __init__(self, deployment: Deployment) -> None:
        self.deployment = deployment

    def draft(self, session: Session, goal: str, draft: PolicyDraft) -> PolicyVersion:
        wallet = Repository(session).available_wallet(self.deployment.account)
        policy = session.scalar(select(Policy).where(Policy.wallet_id == wallet.id))
        assert policy is not None
        version = PolicyVersion(policy_id=policy.id, goal=goal, draft_json=draft.model_dump_json())
        session.add(version)
        session.flush()
        record(session, "POLICY_DRAFT_CREATED", version.id, draft, wallet.user_id)
        return version

    def approve(self, session: Session, version_id: str) -> PolicyVersion:
        repo = Repository(session)
        wallet = repo.available_wallet(self.deployment.account)
        version = repo.get(PolicyVersion, version_id)
        if version.status != "DRAFT":
            raise Conflict("Only a new draft can be approved")
        draft = PolicyDraft.model_validate_json(version.draft_json)
        if set(address.lower() for address in draft.allowed_contracts) != {
            self.deployment.dex.lower()
        }:
            raise Conflict("Only the deployed MockDex may be approved")
        if wallet.active_version_id:
            repo.get(PolicyVersion, wallet.active_version_id).status = "SUPERSEDED"
        schedule = repo.get(Automation, wallet.id)
        if schedule.enabled:
            schedule.enabled = False
            schedule.next_check_at = None
            schedule.last_result = (
                "Policy changed; enable automation for the new version explicitly"
            )
            record(session, "AUTOMATION_STOPPED", wallet.id, schedule.last_result, wallet.user_id)
        # Pending proposals from superseded policies are never executable.
        for row in session.scalars(
            select(Proposal).where(
                Proposal.status.in_(("PROPOSED", "APPROVED", "AWAITING_APPROVAL"))
            )
        ):
            row.status = "CANCELLED"
            approval = session.scalar(
                select(ApprovalRequest).where(ApprovalRequest.proposal_id == row.id)
            )
            if approval:
                approval.status = "REJECTED"
            record(session, "PROPOSAL_CANCELLED", row.id, "Policy superseded", wallet.user_id)
        wallet.active_version_id = version.id
        version.status = "ACTIVE"
        record(session, "POLICY_APPROVED", version.id, draft, wallet.user_id)
        return version
