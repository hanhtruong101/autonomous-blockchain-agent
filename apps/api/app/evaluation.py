"""Small reproducible comparison of exact sizing and untrusted model proposals."""

from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter_ns

from app.agent.portfolio import PortfolioAgent, PortfolioProposer
from app.policies.rebalance import goal_improvement, minimum_allocation
from app.policies.rules import PolicyContext, PolicyEngine
from app.risk.engine import RiskEngine, decide
from app.schemas.ai import AgentAssessment
from app.schemas.domain import (
    Deployment,
    PolicyDecision,
    PolicyDraft,
    Rebalance,
    SimulationResult,
    SpendingLimit,
    Targets,
    TokenChange,
    WalletState,
    now,
)
from app.schemas.evaluation import EvaluationReport, EvaluationRow


@dataclass(frozen=True)
class Scenario:
    name: str
    usdc: int
    weth: int
    target: str
    expected_action: str
    expected_amount: int
    spent: int = 0
    tolerance: int = 0
    cap: str = "30"
    floor: str | None = None
    simulation_success: bool = True


SCENARIOS = (
    Scenario("Far above target", 1000, 0, "0.70", "USDC->WETH", 30),
    Scenario("Far below target", 500, 500, "0.70", "WETH->USDC", 30),
    Scenario("Small excess", 960, 40, "0.95", "USDC->WETH", 10),
    Scenario("Small deficit", 940, 60, "0.95", "WETH->USDC", 10),
    Scenario("At target", 950, 50, "0.95", "HOLD", 0),
    Scenario("Inside tolerance", 945, 55, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Upper band boundary", 960, 40, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Lower band boundary", 940, 60, "0.95", "HOLD", 0, tolerance=100),
    Scenario("Only two units of budget", 1000, 0, "0.70", "USDC->WETH", 2, spent=98),
    Scenario("Budget exhausted", 1000, 0, "0.70", "HOLD", 0, spent=100),
    Scenario("Five-unit trade ceiling", 1000, 0, "0.70", "USDC->WETH", 5, cap="5"),
    Scenario("Hard minimum permits target", 960, 40, "0.95", "USDC->WETH", 10, floor="0.95"),
    Scenario("Minimum cannot be restored in one trade", 900, 100, "0.95", "HOLD", 0, floor="0.95"),
    Scenario(
        "Minimum overrides tolerance",
        940,
        60,
        "0.95",
        "WETH->USDC",
        10,
        floor="0.95",
        tolerance=500,
    ),
    Scenario("Large trade needs approval", 1000, 0, "0.92", "USDC->WETH", 80, cap="100"),
    Scenario(
        "Simulation failure blocks", 1000, 0, "0.70", "USDC->WETH", 30, simulation_success=False
    ),
)


def fixtures(case: Scenario) -> tuple[Deployment, PolicyDraft, WalletState]:
    deployment = Deployment(
        chain_id=31337,
        **{
            name: "0x" + f"{index:02x}" * 20
            for index, name in enumerate(
                ("owner", "agent", "recipient", "usdc", "weth", "dex", "account"), 1
            )
        },
    )
    policy = PolicyDraft(
        daily_spending_limit=SpendingLimit(amount=Decimal("100")),
        maximum_trade_amount=Decimal(case.cap),
        minimum_usdc_ratio=Decimal(case.floor) if case.floor else None,
        allowed_contracts=(deployment.dex,),
        rebalance=Rebalance(minimum_interval_hours=0, tolerance_bps=case.tolerance),
        portfolio_targets=Targets(USDC=Decimal(case.target), WETH=1 - Decimal(case.target)),
        maximum_slippage_bps=100,
    )
    state = WalletState(
        address=deployment.account,
        chain_id=31337,
        usdc_units=case.usdc * 1_000_000,
        weth_units=case.weth * 1_000_000,
        spent_units=case.spent * 1_000_000,
        block_timestamp=1800000000,
    )
    return deployment, policy, state


def evaluate_scenarios(
    proposer: PortfolioProposer | None = None,
    provider: str = "deterministic",
    model: str | None = None,
    limit: int = 16,
) -> EvaluationReport:
    agent = proposer or PortfolioAgent()
    rows: list[EvaluationRow] = []
    for case in SCENARIOS[:limit]:
        deployment, policy, state = fixtures(case)
        start = perf_counter_ns()
        try:
            result = agent.propose(state, policy, "benchmark-only", deployment)
            assessment = result if isinstance(result, AgentAssessment) else None
            proposal = assessment.proposal if assessment else result
            assert not isinstance(proposal, AgentAssessment)
            intention = (
                assessment.decision.action if assessment else ("REBALANCE" if proposal else "HOLD")
            )
            expected_intention = "HOLD" if case.expected_amount == 0 else "REBALANCE"
            action = "HOLD" if proposal is None else f"{proposal.asset_in}->{proposal.asset_out}"
            amount = 0 if proposal is None else proposal.amount
            violations: tuple[str, ...] = ()
            decision = "HOLD"
            if proposal is not None:
                simulation = SimulationResult(
                    success=case.simulation_success,
                    contract_called=proposal.contract_address,
                    expected_output=proposal.amount,
                    expected_token_changes=(
                        TokenChange(asset=proposal.asset_in, units=-proposal.amount),
                        TokenChange(asset=proposal.asset_out, units=proposal.amount),
                    ),
                )
                policy_decision = PolicyEngine().evaluate(
                    proposal, PolicyContext(policy, state.address, state.spent_units, None)
                )
                rules = (
                    *policy_decision.rules,
                    goal_improvement(state, policy, proposal, simulation),
                    minimum_allocation(state, policy, simulation),
                )
                policy_decision = PolicyDecision(
                    allowed=all(rule.passed for rule in rules), rules=rules
                )
                risk = RiskEngine(deployment).evaluate(proposal, policy, simulation)
                decision = decide(policy_decision, simulation, risk).value
                violations = tuple(rule.rule_name for rule in rules if not rule.passed)
            rows.append(
                EvaluationRow(
                    agent_action=intention,
                    decision_matches_expected=("REBALANCE" if intention == "SWAP" else intention)
                    == expected_intention,
                    sizing_matches_expected=(
                        action == case.expected_action
                        and amount == case.expected_amount * 1_000_000
                    )
                    if intention in {"REBALANCE", "SWAP"}
                    else None,
                    scenario=case.name,
                    expected_action=case.expected_action,
                    expected_amount_units=case.expected_amount * 1_000_000,
                    actual_action=action,
                    actual_amount_units=amount,
                    matches_expected=action == case.expected_action
                    and amount == case.expected_amount * 1_000_000,
                    decision=decision,
                    latency_ms=(perf_counter_ns() - start) // 1_000_000,
                    safety_violations=violations,
                )
            )
        except Exception:
            rows.append(
                EvaluationRow(
                    scenario=case.name,
                    expected_action=case.expected_action,
                    expected_amount_units=case.expected_amount * 1_000_000,
                    actual_action="INVALID",
                    actual_amount_units=0,
                    matches_expected=False,
                    decision="BLOCK",
                    latency_ms=(perf_counter_ns() - start) // 1_000_000,
                    error="Provider output unavailable or invalid; no fallback used",
                )
            )
    return EvaluationReport(
        benchmark_kind="deterministic"
        if proposer is None
        else (
            "bounded_decisions"
            if provider == "ollama_decision"
            else "ai_trade_proposals"
            if provider == "ollama_trades"
            else "legacy_raw_proposals"
        ),
        decision_matches=sum(row.decision_matches_expected is True for row in rows),
        decision_cases=len(rows),
        sizing_matches=sum(row.sizing_matches_expected is True for row in rows),
        sizing_cases=sum(row.sizing_matches_expected is not None for row in rows),
        provider=provider,
        model=model,
        created_at=now().isoformat(),
        rows=tuple(rows),
        correct=sum(row.matches_expected for row in rows),
        total=len(rows),
        proposed_trades=sum(row.actual_amount_units > 0 for row in rows),
        approval_requests=sum(row.decision == "REQUIRE_APPROVAL" for row in rows),
        blocked=sum(row.decision == "BLOCK" for row in rows),
        invalid_outputs=sum(row.error is not None for row in rows),
        total_latency_ms=sum(row.latency_ms for row in rows),
    )
