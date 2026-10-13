from datetime import timedelta

from sqlalchemy.orm import Session

from app.audit.recorder import record
from app.blockchain.adapter import SmartAccountAdapter
from app.db.repository import Conflict, Repository
from app.models.entities import ApprovalRequest, Proposal, RiskRecord, SimulationRecord, Wallet
from app.policies.rebalance import goal_improvement, minimum_allocation
from app.policies.rules import PolicyContext, PolicyEngine
from app.risk.engine import RiskEngine, decide
from app.schemas.domain import (
    Evaluation,
    Outcome,
    PolicyDecision,
    PolicyDraft,
    TransactionProposal,
    now,
)
from app.simulation.engine import SimulationEngine


class Pipeline:
    def __init__(self, adapter: SmartAccountAdapter, simulation: SimulationEngine) -> None:
        self.adapter = adapter
        self.simulation = simulation
        self.policy = PolicyEngine()
        self.risk = RiskEngine(adapter.deployment)

    def evaluate(self, session: Session, wallet: Wallet, row: Proposal) -> Evaluation:
        proposal = TransactionProposal.model_validate_json(row.proposal_json)
        version = Repository(session).active(wallet)
        if proposal.digest() != row.digest or proposal.policy_version_id != version.id:
            raise Conflict("Proposal or active policy changed; propose again")
        policy = PolicyDraft.model_validate_json(version.draft_json)
        state = self.adapter.state()
        elapsed = (
            None
            if wallet.last_rebalance_timestamp is None
            else (state.block_timestamp - wallet.last_rebalance_timestamp)
        )
        policy_result = self.policy.evaluate(
            proposal, PolicyContext(policy, wallet.id, state.spent_units, elapsed)
        )
        simulation = self.simulation.simulate(proposal)
        session.add(
            SimulationRecord(proposal_id=proposal.id, result_json=simulation.model_dump_json())
        )
        record(session, "SIMULATION_COMPLETED", proposal.id, simulation)
        goal = goal_improvement(state, policy, proposal, simulation)
        floor = minimum_allocation(state, policy, simulation)
        policy_result = PolicyDecision(
            allowed=policy_result.allowed and goal.passed and floor.passed,
            rules=(*policy_result.rules, goal, floor),
        )
        record(session, "POLICY_CHECK_COMPLETED", proposal.id, policy_result)
        risk = self.risk.evaluate(proposal, policy, simulation)
        session.add(RiskRecord(proposal_id=proposal.id, result_json=risk.model_dump_json()))
        record(session, "RISK_ASSESSED", proposal.id, risk)
        evaluation = Evaluation(
            policy=policy_result,
            simulation=simulation,
            risk=risk,
            outcome=decide(policy_result, simulation, risk),
        )
        row.evaluation_json = evaluation.model_dump_json()
        return evaluation

    def route(self, session: Session, wallet: Wallet, row: Proposal) -> bool:
        evaluation = self.evaluate(session, wallet, row)
        if evaluation.outcome == Outcome.BLOCK:
            row.status = "BLOCKED"
            record(session, "TRANSACTION_BLOCKED", row.id, evaluation)
            return False
        if evaluation.outcome == Outcome.REQUIRE_APPROVAL:
            row.status = "AWAITING_APPROVAL"
            approval = ApprovalRequest(
                proposal_id=row.id,
                proposal_digest=row.digest,
                expires_at=now() + timedelta(minutes=10),
            )
            session.add(approval)
            record(
                session,
                "APPROVAL_REQUESTED",
                row.id,
                "Owner review required; expires in 10 minutes",
            )
            return False
        return True
