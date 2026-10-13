import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.portfolio import AITradingAgent, PortfolioAgent, PortfolioProposer
from app.api.activity import activity_view
from app.api.queries import approval_view, execution_view, policy_view, proposal_view
from app.approvals.validation import validate_approval
from app.audit.recorder import record
from app.blockchain.adapter import LocalSmartAccountAdapter, SmartAccountAdapter
from app.blockchain.owner import LocalOwnerControls, OwnerControls
from app.config.settings import Settings
from app.db.repository import Conflict, Repository
from app.evaluation import evaluate_scenarios
from app.execution.agent_runs import AgentRuns
from app.execution.automation import AutomationService
from app.execution.coordinator import ExecutionCoordinator
from app.execution.pipeline import Pipeline
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ExecutionRecord,
    PolicyVersion,
    Proposal,
)
from app.policies.interpreter import (
    LocalPolicyInterpreter,
    PolicyInterpreter,
    ProviderPolicyInterpreter,
)
from app.policies.lifecycle import PolicyLifecycle
from app.policies.ollama import OllamaProvider
from app.policies.providers import OpenAIResponsesProvider, ProviderFailure
from app.schemas.activity import ActivityView
from app.schemas.ai import GenerationMetadata, StructuredProvider
from app.schemas.automation import AutomationView, EnableAutomation
from app.schemas.domain import TransactionProposal, WalletState, as_utc
from app.schemas.evaluation import EvaluationReport, EvaluationView
from app.schemas.responses import (
    ApprovalView,
    AuditView,
    ConfigurationView,
    ExecutionView,
    GoalInput,
    PolicyView,
    ProposalView,
    RunInput,
)
from app.security.auth import OwnerAuth
from app.simulation.engine import RpcSimulationEngine


def create_app(
    settings: Settings,
    adapter: SmartAccountAdapter | None = None,
    sessions: sessionmaker[Session] | None = None,
    provider: StructuredProvider | None = None,
    owner_controls: OwnerControls | None = None,
    proposer: PortfolioProposer | None = None,
) -> FastAPI:
    chain = adapter or LocalSmartAccountAdapter(settings.rpc_url, settings.deployment_path)
    factory = sessions or sessionmaker(create_engine(settings.database_url), expire_on_commit=False)
    pipeline = Pipeline(chain, RpcSimulationEngine(chain))
    coordinator = ExecutionCoordinator(factory, pipeline)
    interpreter: PolicyInterpreter = LocalPolicyInterpreter(chain.deployment.dex)
    agent: PortfolioProposer = PortfolioAgent()
    generation = GenerationMetadata(
        execution_mode="deterministic"
        if settings.ai_provider == "offline"
        else "ai_trade_proposal",
        provider=settings.ai_provider,
        model=settings.ai_model if settings.ai_provider != "offline" else None,
    )
    if settings.ai_provider == "openai":
        assert settings.openai_api_key is not None
        provider = provider or OpenAIResponsesProvider(settings.ai_model, settings.openai_api_key)
    elif settings.ai_provider == "ollama":
        provider = provider or OllamaProvider(settings.ai_model)
    if settings.ai_provider != "offline":
        assert provider is not None
        interpreter = ProviderPolicyInterpreter(provider, chain.deployment.dex)
        agent = AITradingAgent(provider)
    if proposer is not None:
        agent = proposer  # Dependency injection for adversarial tests; not selectable via REST.
    lifecycle = PolicyLifecycle(chain.deployment)

    controls = owner_controls
    if controls is None and isinstance(chain, LocalSmartAccountAdapter):
        controls = LocalOwnerControls(chain)
    automation = AutomationService(
        factory,
        AgentRuns(chain, pipeline, agent, generation),
        coordinator,
        controls,
        settings.automation_worker,
    )

    async def worker(stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.to_thread(automation.tick)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Automation check unavailable; no automatic retry of transaction submission"
                )
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with factory.begin() as session:
            Repository(session).initialize(chain.deployment.account)
        stop = asyncio.Event()
        task = asyncio.create_task(worker(stop)) if settings.automation_worker else None
        try:
            yield
        finally:
            stop.set()
            if task:
                await task

    app = FastAPI(
        title="Controlled Autonomy · Local test assets",
        lifespan=lifespan,
        dependencies=[Depends(OwnerAuth(settings))],
    )

    @app.exception_handler(Conflict)
    async def conflict(request: Request, error: Conflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"detail": "Invalid input or unsupported goal"}
        )

    @app.get("/evaluation")
    def evaluation_report() -> EvaluationView:
        path = Path("local/evaluation/ollama_trades.json")
        shadow = None
        status = "No Ollama comparison yet. Run the documented local benchmark command."
        if path.is_file():
            try:
                if path.stat().st_size > 1_000_000:
                    raise ValueError("Report too large")
                shadow = EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))
                if shadow.benchmark_kind != "ai_trade_proposals":
                    raise ValueError("Expected an AI trade-proposal report")
                status = "Saved AI trade-proposal comparison; inspect its timestamp and model."
            except (ValueError, OSError):
                shadow = None
                status = "Saved comparison is invalid. Run the benchmark again."
        return EvaluationView(
            deterministic=evaluate_scenarios(), ollama_shadow=shadow, shadow_status=status
        )

    @app.get("/agent/activity")
    def agent_activity() -> ActivityView:
        with factory() as session:
            return activity_view(session, chain.deployment.account)

    @app.get("/automation")
    def automation_status() -> AutomationView:
        return automation.view()

    @app.post("/automation/enable")
    def enable_automation(request: EnableAutomation) -> AutomationView:
        return automation.enable(request)

    @app.post("/automation/stop")
    def stop_automation() -> AutomationView:
        return automation.stop()

    @app.post("/automation/freeze")
    def freeze_execution() -> AutomationView:
        return automation.freeze()

    @app.post("/automation/resume")
    def resume_execution() -> AutomationView:
        return automation.resume()

    @app.get("/wallet/state")
    def wallet_state() -> WalletState:
        return chain.state()

    @app.get("/configuration")
    def configuration() -> ConfigurationView:
        return ConfigurationView(
            interpreter="llm" if settings.ai_provider != "offline" else "local",
            provider_host=(
                "api.openai.com"
                if settings.ai_provider == "openai"
                else "127.0.0.1:11434"
                if settings.ai_provider == "ollama"
                else ""
            ),
            generation=generation,
        )

    @app.post("/policies", status_code=201)
    def create_policy(request: GoalInput) -> PolicyView:
        try:
            with factory.begin() as session:
                Repository(session).available_wallet(chain.deployment.account)
            # Policy generation also stays outside locks used by emergency freeze.
            draft = interpreter.interpret(request.goal)
            controls = draft.model_dump()
            if request.tolerance_bps is not None:
                controls["rebalance"] = draft.rebalance.model_copy(
                    update={"tolerance_bps": request.tolerance_bps}
                )
            if request.maximum_trade_amount is not None:
                controls["maximum_trade_amount"] = request.maximum_trade_amount
            if request.minimum_usdc_ratio is not None:
                controls["minimum_usdc_ratio"] = max(
                    draft.minimum_usdc_ratio or 0, request.minimum_usdc_ratio
                )
            from app.schemas.domain import PolicyDraft

            draft = PolicyDraft.model_validate(controls)
            with factory.begin() as session:
                row = lifecycle.draft(session, request.goal, draft)
                record(session, "POLICY_GENERATION", row.id, generation)
                return policy_view(row)
        except Conflict:
            raise
        except ValueError as error:
            with factory.begin() as session:
                record(session, "POLICY_GENERATION_FAILED", chain.deployment.account, generation)
                record(
                    session,
                    "POLICY_GENERATION_ERROR",
                    chain.deployment.account,
                    error.code if isinstance(error, ProviderFailure) else "invalid_policy",
                )
            detail = (
                str(error)
                if isinstance(error, ProviderFailure)
                else (
                    "Model output failed policy validation. Rephrase the goal using supported "
                    "assets, budget, targets and cadence."
                    if settings.ai_provider != "offline"
                    else "Offline mode requires the exact displayed goal template."
                )
            )
            raise HTTPException(422, detail + " No policy was activated.") from None

    @app.get("/policies")
    def policies() -> list[PolicyView]:
        with factory() as session:
            return [
                policy_view(row)
                for row in session.scalars(
                    select(PolicyVersion).order_by(PolicyVersion.created_at.desc()).limit(200)
                )
            ]

    @app.get("/policies/{identifier}")
    def policy(identifier: str) -> PolicyView:
        with factory() as session:
            return policy_view(Repository(session).get(PolicyVersion, identifier))

    @app.post("/policies/{identifier}/approve")
    def approve_policy(identifier: str) -> PolicyView:
        with factory.begin() as session:
            return policy_view(lifecycle.approve(session, identifier))

    @app.post("/agent/runs", status_code=201)
    def agent_run(request: RunInput) -> ProposalView | None:
        try:
            identifier, execute = AgentRuns(chain, pipeline, agent, generation).run(
                factory, request
            )
        except Conflict:
            raise
        except ValueError as error:
            with factory.begin() as session:
                record(session, "AGENT_GENERATION_FAILED", chain.deployment.account, generation)
                record(
                    session,
                    "AGENT_GENERATION_ERROR",
                    chain.deployment.account,
                    error.code if isinstance(error, ProviderFailure) else "invalid_proposal",
                )
            detail = (
                str(error)
                if isinstance(error, ProviderFailure)
                else ("Agent output failed proposal validation.")
            )
            raise HTTPException(422, detail + " No fallback or transaction occurred.") from None
        if identifier is None:
            return None
        if execute:
            coordinator.execute(identifier)
        return proposal(identifier)

    @app.get("/proposals")
    def proposals() -> list[ProposalView]:
        with factory() as session:
            return [
                proposal_view(session, row)
                for row in session.scalars(
                    select(Proposal).order_by(Proposal.created_at.desc()).limit(200)
                )
            ]

    @app.get("/proposals/{identifier}")
    def proposal(identifier: str) -> ProposalView:
        with factory() as session:
            return proposal_view(session, Repository(session).get(Proposal, identifier))

    @app.get("/approvals")
    def approvals() -> list[ApprovalView]:
        with factory() as session:
            return [
                approval_view(row)
                for row in session.scalars(
                    select(ApprovalRequest).order_by(ApprovalRequest.expires_at.desc()).limit(200)
                )
            ]

    def decide_approval(identifier: str, approve: bool) -> ProposalView:
        with factory.begin() as session:
            repo = Repository(session)
            wallet = repo.available_wallet(chain.deployment.account)
            approval = repo.get(ApprovalRequest, identifier)
            row = repo.get(Proposal, approval.proposal_id)
            payload = TransactionProposal.model_validate_json(row.proposal_json)
            validate_approval(approval, payload)
            if row.status != "AWAITING_APPROVAL" or row.digest != payload.digest():
                raise Conflict("Proposal cannot be approved in its current state")
            if approve and repo.active(wallet).id != row.policy_version_id:
                raise Conflict("Policy changed since review")
            approval.status = "APPROVED" if approve else "REJECTED"
            approval.decided_by = wallet.user_id
            row.status = "APPROVED" if approve else "REJECTED"
            record(
                session,
                "APPROVAL_GRANTED" if approve else "APPROVAL_REJECTED",
                row.id,
                approval.proposal_digest,
                wallet.user_id,
            )
            proposal_id = row.id
        if approve:
            coordinator.execute(proposal_id)
        return proposal(proposal_id)

    @app.post("/approvals/{identifier}/approve")
    def approve(identifier: str) -> ProposalView:
        return decide_approval(identifier, True)

    @app.post("/approvals/{identifier}/reject")
    def reject(identifier: str) -> ProposalView:
        return decide_approval(identifier, False)

    @app.get("/transactions")
    def transactions() -> list[ExecutionView]:
        with factory() as session:
            return [
                execution_view(row)
                for row in session.scalars(
                    select(ExecutionRecord).order_by(ExecutionRecord.created_at.desc()).limit(200)
                )
            ]

    @app.get("/transactions/{identifier}")
    def transaction(identifier: str) -> ExecutionView:
        with factory() as session:
            return execution_view(Repository(session).get(ExecutionRecord, identifier))

    @app.post("/proposals/{identifier}/reconcile")
    def reconcile(identifier: str) -> ProposalView:
        coordinator.reconcile(identifier)
        return proposal(identifier)

    @app.get("/audit-events")
    def events(after: int = 0) -> list[AuditView]:
        with factory() as session:
            return [
                AuditView(
                    id=row.id,
                    event=row.event,
                    entity_id=row.entity_id,
                    actor=row.actor,
                    details=row.details,
                    created_at=as_utc(row.created_at),
                )
                for row in session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.id > after)
                    .order_by(AuditEvent.id)
                    .limit(500)
                )
            ]

    return app
