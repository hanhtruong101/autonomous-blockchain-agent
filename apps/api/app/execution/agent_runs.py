from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.portfolio import PortfolioAgent, PortfolioProposer
from app.audit.recorder import record
from app.blockchain.adapter import SmartAccountAdapter
from app.db.repository import Conflict, Repository
from app.execution.pipeline import Pipeline
from app.execution.readiness import portfolio_readiness
from app.models.entities import AgentRun, Automation, Proposal
from app.schemas.activity import AgentActivity, WalletObservation
from app.schemas.ai import AgentAssessment, GenerationMetadata
from app.schemas.domain import Asset, PolicyDraft, TransactionProposal
from app.schemas.responses import RunInput


class AgentRuns:
    def __init__(
        self,
        adapter: SmartAccountAdapter,
        pipeline: Pipeline,
        agent: PortfolioProposer | None = None,
        generation: GenerationMetadata | None = None,
    ) -> None:
        self.adapter = adapter
        self.pipeline = pipeline
        self.agent = agent or PortfolioAgent()
        self.generation = generation or GenerationMetadata()

    def run(
        self,
        sessions: sessionmaker[Session],
        request: RunInput,
        scheduled_version: str | None = None,
        scheduled_check: str | None = None,
    ) -> tuple[str | None, bool]:
        with sessions.begin() as session:
            repo = Repository(session)
            wallet = repo.available_wallet(self.adapter.deployment.account)
            version = repo.active(wallet)
            if scheduled_version is not None:
                schedule = repo.get(Automation, wallet.id)
                if (
                    not schedule.enabled
                    or version.id != scheduled_version
                    or schedule.check_id != scheduled_check
                ):
                    raise Conflict("Automation stopped or policy changed")
            if session.scalar(
                select(Proposal.id)
                .where(
                    Proposal.status.in_(
                        (
                            "PROPOSED",
                            "APPROVED",
                            "AWAITING_APPROVAL",
                            "SUBMITTING",
                            "SUBMITTED",
                            "UNCERTAIN",
                        )
                    )
                )
                .limit(1)
            ):
                raise Conflict("Review or reconcile the pending proposal before another run")
            policy = PolicyDraft.model_validate_json(version.draft_json)
            last_trade = wallet.last_rebalance_timestamp
            version_id = version.id
            run = AgentRun(policy_version_id=version_id)
            session.add(run)
            session.flush()
            run_id = run.id
            wallet.generating_run_id = run_id
            generation = (
                self.generation
                if request.scenario == "portfolio"
                else GenerationMetadata(provider="fixture", execution_mode="fixture")
            )
            record(session, "AGENT_RUN_STARTED", run_id, request)
            record(session, "AGENT_GENERATION", run_id, generation)
            activity = AgentActivity(
                policy_version_id=version_id,
                source="scheduled"
                if scheduled_version
                else ("manual" if request.scenario == "portfolio" else "fixture"),
                state="OBSERVING",
                reason="Reading the local wallet snapshot",
                generation=generation,
            )
            record(session, "AGENT_ACTIVITY", run_id, activity)
        try:
            state = self.adapter.state()
            activity = activity.model_copy(
                update={"observation": WalletObservation.from_state(state)}
            )
            readiness = portfolio_readiness(state, policy, last_trade)
            skipped = request.scenario == "portfolio" and readiness.code != "READY"
            if skipped:
                proposal = None
            elif request.scenario == "portfolio":
                activity = activity.model_copy(
                    update={"state": "DECIDING", "reason": "Preparing a treasury trade proposal"}
                )
                with sessions.begin() as session:
                    record(session, "AGENT_ACTIVITY", run_id, activity)
                result = self.agent.propose(state, policy, version_id, self.adapter.deployment)
                if isinstance(result, AgentAssessment):
                    proposal = result.proposal
                    activity = activity.model_copy(update={"decision": result.decision})
                else:
                    proposal = result
            else:
                # Fixed educational attack fixtures, never arbitrary raw transactions.
                amount = {"A": 30, "B": 80, "C": 40, "D": 20, "medium": 70}[request.scenario]
                proposal = TransactionProposal(
                    policy_version_id=version_id,
                    chain_id=31337,
                    wallet=self.adapter.deployment.account,
                    asset_in=Asset.USDC,
                    asset_out=Asset.WETH,
                    amount=amount * 1_000_000,
                    destination=self.adapter.deployment.account,
                    protocol="MockDex",
                    operation="swap",
                    contract_address="0x" + "99" * 20
                    if request.scenario == "C"
                    else self.adapter.deployment.dex,
                    maximum_slippage_bps=2000 if request.scenario == "D" else 100,
                    reason=f"Controlled local demonstration scenario {request.scenario}",
                )
            with sessions.begin() as session:
                repo = Repository(session)
                wallet = repo.wallet(self.adapter.deployment.account)
                if wallet.generating_run_id != run_id or wallet.execution_paused:
                    raise Conflict("Run cancelled by owner controls")
                wallet.generating_run_id = None
                if repo.active(wallet).id != version_id:
                    raise Conflict("Policy changed during generation")
                if scheduled_version is not None:
                    schedule = repo.get(Automation, wallet.id)
                    if not schedule.enabled or schedule.check_id != scheduled_check:
                        raise Conflict("Automation stopped during generation")
                if proposal is None:
                    ai_hold = activity.decision is not None and activity.decision.action == "HOLD"
                    reason = (
                        readiness.reason
                        if skipped
                        else (
                            activity.decision.reason
                            if ai_hold and activity.decision
                            else "No permitted calculated trade; no transaction proposed"
                        )
                    )
                    activity = activity.model_copy(
                        update={
                            "state": "SYSTEM_SKIPPED"
                            if skipped or (activity.decision is not None and not ai_hold)
                            else "AI_HOLD"
                            if ai_hold
                            else "HOLD",
                            "reason": reason,
                        }
                    )
                    record(session, "AGENT_ACTIVITY", run_id, activity)
                    record(
                        session,
                        "AGENT_RUN_COMPLETED",
                        run_id,
                        reason,
                    )
                    return None, False
                row = Proposal(
                    id=proposal.id,
                    policy_version_id=version_id,
                    agent_run_id=run_id,
                    proposal_json=proposal.model_dump_json(),
                    digest=proposal.digest(),
                )
                session.add(row)
                session.flush()
                record(session, "TRANSACTION_PROPOSED", row.id, proposal)
                record(session, "PROPOSAL_GENERATION", row.id, generation)
                execute = self.pipeline.route(session, wallet, row)
                record(
                    session,
                    "AGENT_ACTIVITY",
                    run_id,
                    activity.model_copy(
                        update={
                            "state": "PROPOSAL_CREATED",
                            "proposal_id": row.id,
                            "calculation": (
                                f"Swap {Decimal(proposal.amount).scaleb(-6):f} "
                                f"{proposal.asset_in} "
                                f"to {proposal.asset_out}; maximum slippage "
                                f"{proposal.maximum_slippage_bps} bps. {proposal.reason}"
                            ),
                            "reason": "Proposal evaluated; inspect safety and execution results",
                        }
                    ),
                )
                record(session, "AGENT_RUN_COMPLETED", run_id, row.id)
                return row.id, execute
        except Exception as error:
            with sessions.begin() as session:
                wallet = Repository(session).wallet(self.adapter.deployment.account)
                if wallet.generating_run_id == run_id:
                    wallet.generating_run_id = None
                record(
                    session,
                    "AGENT_RUN_FAILED",
                    run_id,
                    "Generation or validation failed; no fallback transaction",
                )
                record(
                    session,
                    "AGENT_ACTIVITY",
                    run_id,
                    activity.model_copy(
                        update={
                            "state": "CANCELLED" if isinstance(error, Conflict) else "FAILED",
                            "reason": "Run cancelled by changed authorization"
                            if isinstance(error, Conflict)
                            else "Run failed validation or generation; no fallback transaction",
                        }
                    ),
                )
            raise
