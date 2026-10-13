"""Owner-authorized scheduling; execution still goes through the existing coordinator."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.audit.recorder import record
from app.blockchain.owner import OwnerControls
from app.db.repository import Conflict, Repository
from app.execution.agent_runs import AgentRuns
from app.execution.coordinator import ExecutionCoordinator
from app.execution.readiness import portfolio_readiness
from app.models.entities import AgentRun, ApprovalRequest, Automation, Proposal, Wallet
from app.schemas.activity import AgentActivity, WalletObservation
from app.schemas.automation import AutomationView, EnableAutomation
from app.schemas.domain import PolicyDraft, as_utc, now
from app.schemas.readiness import Readiness
from app.schemas.responses import RunInput

PENDING = ("PROPOSED", "APPROVED", "AWAITING_APPROVAL", "SUBMITTING", "SUBMITTED", "UNCERTAIN")


class AutomationService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        runs: AgentRuns,
        coordinator: ExecutionCoordinator,
        controls: OwnerControls | None,
        worker_available: bool,
    ) -> None:
        self.sessions = sessions
        self.runs = runs
        self.coordinator = coordinator
        self.controls = controls
        self.worker_available = worker_available
        self.address = runs.adapter.deployment.account

    def view(self) -> AutomationView:
        with self.sessions() as session:
            wallet = Repository(session).get(Wallet, self.address)
            schedule = Repository(session).get(Automation, self.address)
            readiness = self.readiness(session, wallet)
            return AutomationView(
                readiness=readiness,
                enabled=schedule.enabled,
                running=schedule.running,
                execution_paused=wallet.execution_paused,
                generation_in_progress=wallet.generating_run_id is not None,
                policy_version_id=schedule.policy_version_id,
                interval_seconds=schedule.interval_seconds,
                next_check_at=as_utc(schedule.next_check_at) if schedule.next_check_at else None,
                last_check_at=as_utc(schedule.last_check_at) if schedule.last_check_at else None,
                last_result=schedule.last_result,
                consecutive_failures=schedule.consecutive_failures,
                worker_available=self.worker_available,
            )

    def readiness(self, session: Session, wallet: Wallet) -> Readiness:
        if wallet.busy_proposal_id:
            return Readiness(
                code="RECONCILIATION",
                reason="A submission is unresolved",
                next_step=(
                    "Open the transaction and reconcile its receipt before any further execution."
                ),
                proposal_id=wallet.busy_proposal_id,
            )
        if wallet.execution_paused:
            return Readiness(
                code="FROZEN",
                reason="Execution is frozen",
                next_step=(
                    "Inspect the audit and chain state, then use owner resume. "
                    "Scheduling stays off."
                ),
            )
        if wallet.generating_run_id:
            run = session.get(AgentRun, wallet.generating_run_id)
            return Readiness(
                code="GENERATING",
                reason="Observing the portfolio and preparing an agent decision",
                next_step=(
                    "Wait for the configured model. An interrupted run requires owner "
                    "inspection, not a blind retry."
                ),
                generation_started_at=as_utc(run.created_at) if run else None,
            )
        if not wallet.active_version_id:
            return Readiness(
                code="NO_POLICY",
                reason="No approved policy",
                next_step="Create a policy, review its boundaries, and approve it first.",
            )
        pending = session.scalar(
            select(Proposal).where(Proposal.status.in_(PENDING)).order_by(Proposal.created_at)
        )
        if pending:
            return Readiness(
                code="PENDING_REVIEW",
                reason="A proposal needs attention",
                next_step="Open the pending proposal to approve, reject, or inspect its status.",
                proposal_id=pending.id,
            )
        try:
            version = Repository(session).active(wallet)
            policy = PolicyDraft.model_validate_json(version.draft_json)
            state = self.runs.adapter.state()
            return portfolio_readiness(state, policy, wallet.last_rebalance_timestamp)
        except Exception:
            return Readiness(
                code="UNAVAILABLE",
                reason="Wallet or policy state is unavailable",
                next_step=(
                    "Check the API, local Anvil and deployment configuration. No "
                    "readiness permission is granted."
                ),
            )

    def enable(self, request: EnableAutomation) -> AutomationView:
        with self.sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.available_wallet(self.address)
            version = repo.active(wallet)
            schedule = repo.get(Automation, self.address)
            if schedule.running or schedule.enabled:
                raise Conflict("Stop the current schedule before enabling another")
            if version.id != request.policy_version_id:
                raise Conflict("Review the active policy before enabling automation")
            schedule.enabled = True
            schedule.policy_version_id = version.id
            schedule.interval_seconds = request.interval_seconds
            schedule.next_check_at = now() + timedelta(seconds=request.interval_seconds)
            schedule.consecutive_failures = 0
            schedule.last_result = "Enabled by owner; waiting for next check"
            record(session, "AUTOMATION_ENABLED", self.address, request, wallet.user_id)
        return self.view()

    def stop(self) -> AutomationView:
        with self.sessions.begin() as session:
            wallet = Repository(session).wallet(self.address)
            schedule = Repository(session).get(Automation, self.address)
            schedule.enabled = False
            schedule.next_check_at = None
            schedule.last_result = "Stopped by owner; submitted transactions cannot be cancelled"
            record(
                session, "AUTOMATION_STOPPED", self.address, schedule.last_result, wallet.user_id
            )
        return self.view()

    def freeze(self) -> AutomationView:
        # Persist the local freeze even if the owner RPC call later fails or times out.
        with self.sessions.begin() as session:
            wallet = Repository(session).wallet(self.address)
            wallet.execution_paused = True
            wallet.generating_run_id = None
            schedule = Repository(session).get(Automation, self.address)
            schedule.enabled = False
            schedule.running = False
            schedule.check_id = None
            schedule.next_check_at = None
            schedule.last_result = "Emergency freeze; owner must resume explicitly"
            for proposal in session.scalars(
                select(Proposal).where(
                    Proposal.status.in_(("PROPOSED", "APPROVED", "AWAITING_APPROVAL"))
                )
            ):
                proposal.status = "CANCELLED"
                approval = session.scalar(
                    select(ApprovalRequest).where(ApprovalRequest.proposal_id == proposal.id)
                )
                if approval:
                    approval.status = "REJECTED"
                    approval.decided_by = wallet.user_id
                record(
                    session,
                    "PROPOSAL_CANCELLED",
                    proposal.id,
                    "Owner emergency freeze",
                    wallet.user_id,
                )
            record(session, "EXECUTION_FROZEN", self.address, schedule.last_result, wallet.user_id)
        if self.controls is None:
            raise Conflict("Local execution frozen; contract owner controls are unavailable")
        try:
            tx_hash = self.controls.set_paused(True)
        except Exception:
            with self.sessions.begin() as session:
                record(
                    session,
                    "OWNER_PAUSE_UNCERTAIN",
                    self.address,
                    "Local freeze persists; inspect contract state before recovery",
                )
            raise Conflict(
                "Local execution frozen; contract pause unconfirmed. Inspect local chain."
            ) from None
        with self.sessions.begin() as session:
            record(session, "SMART_ACCOUNT_PAUSED", self.address, tx_hash, "owner")
        return self.view()

    def resume(self) -> AutomationView:
        if self.controls is None:
            raise Conflict("Contract owner controls are unavailable")
        with self.sessions.begin() as session:
            wallet = Repository(session).wallet(self.address)
            if not wallet.execution_paused:
                raise Conflict("Wallet is not frozen")
            if wallet.busy_proposal_id:
                raise Conflict("Reconcile the uncertain/in-flight submission before resuming")
            try:
                tx_hash = self.controls.set_paused(False)
            except Exception:
                raise Conflict("Resume unconfirmed; local execution remains frozen") from None
            wallet.execution_paused = False
            schedule = Repository(session).get(Automation, self.address)
            schedule.last_result = "Execution resumed by owner; automatic checks remain off"
            record(session, "EXECUTION_RESUMED", self.address, tx_hash, wallet.user_id)
        # Owner must separately re-enable automation; resume never schedules new trades.
        return self.view()

    def tick(self) -> None:
        current = now()
        check_id = str(uuid4())
        with self.sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.wallet(self.address)
            schedule = repo.get(Automation, self.address)
            if not schedule.enabled or schedule.running or schedule.next_check_at is None:
                return
            if as_utc(schedule.next_check_at) > current:
                return
            # Atomic claim also protects portable SQLite tests; PostgreSQL locks the wallet.
            claimed = session.execute(
                update(Automation)
                .execution_options(synchronize_session="fetch")
                .where(
                    Automation.wallet_id == self.address,
                    Automation.running.is_(False),
                    Automation.enabled.is_(True),
                    Automation.next_check_at <= current,
                )
                .values(
                    running=True,
                    check_id=check_id,
                    last_check_at=current,
                    next_check_at=current + timedelta(seconds=schedule.interval_seconds),
                )
            )
            if claimed.rowcount != 1:  # type: ignore[attr-defined]
                return
            bound_version = schedule.policy_version_id
            if wallet.execution_paused or wallet.busy_proposal_id or wallet.generating_run_id:
                schedule.running = False
                schedule.last_result = "Waiting: wallet frozen, generating or submission unresolved"
                if wallet.execution_paused or wallet.busy_proposal_id:
                    schedule.enabled = False
                    schedule.next_check_at = None
                record(session, "AUTOMATION_WAITING", self.address, schedule.last_result)
                record(
                    session,
                    "AGENT_ACTIVITY",
                    check_id,
                    AgentActivity(
                        policy_version_id=bound_version,
                        source="scheduled",
                        state="SYSTEM_SKIPPED",
                        reason=schedule.last_result,
                    ),
                )
                return
            if wallet.active_version_id != bound_version:
                schedule.enabled = False
                schedule.running = False
                schedule.next_check_at = None
                schedule.last_result = "Policy changed; owner must enable the new version"
                record(session, "AUTOMATION_STOPPED", self.address, schedule.last_result)
                return
            if session.scalar(select(Proposal.id).where(Proposal.status.in_(PENDING)).limit(1)):
                schedule.running = False
                schedule.last_result = "Waiting for owner approval or proposal reconciliation"
                record(session, "AUTOMATION_WAITING", self.address, schedule.last_result)
                record(
                    session,
                    "AGENT_ACTIVITY",
                    check_id,
                    AgentActivity(
                        policy_version_id=bound_version,
                        source="scheduled",
                        state="SYSTEM_SKIPPED",
                        reason=schedule.last_result,
                    ),
                )
                return
            version = repo.active(wallet)
            policy = PolicyDraft.model_validate_json(version.draft_json)
            # No LLM call under this lock; RPC reads are bounded by adapter timeout.
            try:
                state = self.runs.adapter.state()
            except Exception:
                schedule.running = False
                schedule.consecutive_failures += 1
                schedule.last_result = "Wallet state unavailable; no action submitted"
                if schedule.consecutive_failures >= 3:
                    schedule.enabled = False
                    schedule.next_check_at = None
                    wallet.execution_paused = True
                    record(
                        session,
                        "AUTOMATION_CIRCUIT_BREAKER",
                        self.address,
                        "Repeated wallet state failures; execution frozen",
                    )
                    if self.controls:
                        try:
                            tx_hash = self.controls.set_paused(True)
                            record(session, "SMART_ACCOUNT_PAUSED", self.address, tx_hash)
                        except Exception:
                            record(
                                session,
                                "OWNER_PAUSE_UNCERTAIN",
                                self.address,
                                "Local freeze persists; verify contract state",
                            )
                record(session, "AUTOMATION_CHECK_FAILED", self.address, schedule.last_result)
                record(
                    session,
                    "AGENT_ACTIVITY",
                    check_id,
                    AgentActivity(
                        policy_version_id=bound_version,
                        source="scheduled",
                        state="FAILED",
                        reason=schedule.last_result,
                    ),
                )
                return
            readiness = portfolio_readiness(state, policy, wallet.last_rebalance_timestamp)
            if readiness.code != "READY":
                schedule.running = False
                schedule.last_result = readiness.reason
                schedule.consecutive_failures = 0
                record(session, "AUTOMATION_SKIPPED", self.address, readiness)
                record(
                    session,
                    "AGENT_ACTIVITY",
                    check_id,
                    AgentActivity(
                        policy_version_id=bound_version,
                        source="scheduled",
                        state="SYSTEM_SKIPPED",
                        reason=readiness.reason,
                        observation=WalletObservation.from_state(state),
                    ),
                )
                return
            record(session, "AUTOMATION_CHECK_STARTED", self.address, bound_version or "")
        failed = False
        identifier = None
        message = "No proposal created; see Check history for the decision or system skip"
        try:
            identifier, execute = self.runs.run(self.sessions, RunInput(), bound_version, check_id)
            if identifier:
                # Stop/policy/freeze can occur after generation; recheck under wallet lock.
                with self.sessions.begin() as session:
                    repo = Repository(session)
                    wallet = repo.wallet(self.address)
                    schedule = repo.get(Automation, self.address)
                    if not schedule.enabled or wallet.execution_paused:
                        row = repo.get(Proposal, identifier)
                        if row.status == "PROPOSED":
                            row.status = "CANCELLED"
                        execute = False
                if execute:
                    self.coordinator.execute(identifier, check_id)
                with self.sessions() as session:
                    status = Repository(session).get(Proposal, identifier).status
                message = f"Proposal {status}; see Proposals & outcomes"
                failed = status in {"BLOCKED", "FAILED", "UNCERTAIN", "SUBMITTING"}
        except Conflict:
            if identifier is not None:
                with self.sessions.begin() as session:
                    repo = Repository(session)
                    repo.wallet(self.address)
                    row = repo.get(Proposal, identifier)
                    if row.status == "PROPOSED":
                        row.status = "CANCELLED"
                        record(
                            session,
                            "PROPOSAL_CANCELLED",
                            identifier,
                            "Scheduled authorization no longer valid",
                        )
            message = "Run stopped by policy, owner controls or a pending proposal"
        except Exception:
            failed = True
            message = "Agent generation or checks failed; no fallback execution"
        breaker = False
        with self.sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.wallet(self.address)
            schedule = repo.get(Automation, self.address)
            if schedule.check_id != check_id:
                return  # A freeze invalidated this run; never mutate a newer claim.
            schedule.running = False
            if schedule.enabled:
                schedule.last_result = message
                schedule.consecutive_failures = schedule.consecutive_failures + 1 if failed else 0
                breaker = schedule.consecutive_failures >= 3 or wallet.busy_proposal_id is not None
                if breaker:
                    schedule.enabled = False
                    schedule.next_check_at = None
                    wallet.execution_paused = True
                    schedule.last_result = (
                        "Circuit breaker: execution frozen; inspect audit and resume explicitly"
                    )
                    record(
                        session, "AUTOMATION_CIRCUIT_BREAKER", self.address, schedule.last_result
                    )
            record(session, "AUTOMATION_CHECK_COMPLETED", self.address, message)
        if breaker and self.controls:
            try:
                tx_hash = self.controls.set_paused(True)
                with self.sessions.begin() as session:
                    record(session, "SMART_ACCOUNT_PAUSED", self.address, tx_hash)
            except Exception:
                with self.sessions.begin() as session:
                    record(
                        session,
                        "OWNER_PAUSE_UNCERTAIN",
                        self.address,
                        "Circuit breaker local freeze persists; verify contract state",
                    )
