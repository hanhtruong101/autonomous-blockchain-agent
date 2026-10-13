from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.recorder import record
from app.db.repository import Conflict, Repository
from app.execution.pipeline import Pipeline
from app.models.entities import ApprovalRequest, Automation, ExecutionRecord, Proposal
from app.schemas.domain import Outcome, TransactionProposal, as_utc, now


class ExecutionCoordinator:
    """Durable intent before RPC. Uncertain submissions freeze the wallet, never retry blindly."""

    def __init__(self, sessions: sessionmaker[Session], pipeline: Pipeline) -> None:
        self.sessions = sessions
        self.pipeline = pipeline

    def execute(self, proposal_id: str, scheduled_check: str | None = None) -> None:
        with self.sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.available_wallet(self.pipeline.adapter.deployment.account)
            if scheduled_check is not None:
                schedule = repo.get(Automation, wallet.id)
                if (
                    not schedule.enabled
                    or schedule.check_id != scheduled_check
                    or schedule.policy_version_id != wallet.active_version_id
                ):
                    raise Conflict("Scheduled execution cancelled")
            row = repo.get(Proposal, proposal_id)
            if row.status not in {"PROPOSED", "APPROVED"}:
                raise Conflict("Proposal is not executable")
            evaluation = self.pipeline.evaluate(session, wallet, row)
            if evaluation.outcome == Outcome.BLOCK:
                row.status = "BLOCKED"
                record(session, "TRANSACTION_BLOCKED", row.id, evaluation)
                return
            proposal = TransactionProposal.model_validate_json(row.proposal_json)
            if evaluation.outcome == Outcome.REQUIRE_APPROVAL:
                approval = session.scalar(
                    select(ApprovalRequest).where(ApprovalRequest.proposal_id == proposal_id)
                )
                if (
                    approval is None
                    or approval.status != "APPROVED"
                    or approval.proposal_digest != proposal.digest()
                ):
                    raise Conflict("Exact owner approval required")

                if as_utc(approval.expires_at) <= now():
                    raise Conflict("Approval expired before execution")
            wallet.busy_proposal_id = proposal_id
            row.status = "SUBMITTING"
            session.add(ExecutionRecord(proposal_id=proposal_id))
            record(session, "TRANSACTION_SUBMISSION_STARTED", proposal_id, proposal)

        try:
            tx_hash = self.pipeline.adapter.submit(proposal)
        except Exception:
            # The RPC may have accepted the transaction before disconnecting.
            with self.sessions.begin() as session:
                repo = Repository(session)
                repo.get(Proposal, proposal_id).status = "UNCERTAIN"
                execution = session.scalar(
                    select(ExecutionRecord).where(ExecutionRecord.proposal_id == proposal_id)
                )
                assert execution is not None
                execution.status = "UNCERTAIN"
                record(
                    session,
                    "TRANSACTION_UNCERTAIN",
                    proposal_id,
                    "RPC submission outcome unknown; wallet frozen for manual reconciliation",
                )
            return
        with self.sessions.begin() as session:
            execution = session.scalar(
                select(ExecutionRecord).where(ExecutionRecord.proposal_id == proposal_id)
            )
            assert execution is not None
            execution.transaction_hash = tx_hash
            execution.status = "SUBMITTED"
            Repository(session).get(Proposal, proposal_id).status = "SUBMITTED"
            record(session, "TRANSACTION_SUBMITTED", proposal_id, tx_hash)
        self.reconcile(proposal_id)

    def reconcile(self, proposal_id: str) -> None:
        with self.sessions() as session:
            execution = session.scalar(
                select(ExecutionRecord).where(ExecutionRecord.proposal_id == proposal_id)
            )
            if execution is None or execution.transaction_hash is None:
                raise Conflict("No durable hash; inspect chain events before any operator recovery")
            tx_hash = execution.transaction_hash
        try:
            success = self.pipeline.adapter.confirmed(tx_hash)
            timestamp = self.pipeline.adapter.state().block_timestamp
        except Exception:
            return  # Keep reservation until receipt is available.
        with self.sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.wallet(self.pipeline.adapter.deployment.account)
            row = repo.get(Proposal, proposal_id)
            execution = session.scalar(
                select(ExecutionRecord).where(ExecutionRecord.proposal_id == proposal_id)
            )
            assert execution is not None
            if execution.status in {"CONFIRMED", "FAILED"}:
                return
            execution.status = "CONFIRMED" if success else "FAILED"
            row.status = "EXECUTED" if success else "FAILED"
            if wallet.busy_proposal_id == proposal_id:
                wallet.busy_proposal_id = None
            if success:
                wallet.last_rebalance_timestamp = timestamp
            record(
                session,
                "TRANSACTION_CONFIRMED" if success else "TRANSACTION_FAILED",
                proposal_id,
                tx_hash,
            )
