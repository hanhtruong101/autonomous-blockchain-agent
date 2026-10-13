from app.schemas.domain import (
    Deployment,
    Finding,
    Outcome,
    PolicyDecision,
    PolicyDraft,
    RiskAssessment,
    RiskLevel,
    SimulationResult,
    TransactionProposal,
)


class RiskEngine:
    def __init__(self, deployment: Deployment) -> None:
        self.deployment = deployment

    def evaluate(
        self, proposal: TransactionProposal, policy: PolicyDraft, simulation: SimulationResult
    ) -> RiskAssessment:
        checks = (
            ("unknown_contract", proposal.contract_address.lower() != self.deployment.dex.lower()),
            (
                "unexpected_destination",
                proposal.destination.lower() != self.deployment.account.lower(),
            ),
            (
                "unexpected_operation",
                proposal.operation != "swap" or proposal.action_type != "SWAP",
            ),
            ("simulation_revert", not simulation.success),
            (
                "excessive_slippage",
                max(proposal.maximum_slippage_bps, simulation.slippage_bps) > 100,
            ),
            ("token_approval", proposal.action_type == "APPROVE"),
            (
                "unexpected_asset",
                proposal.asset_in not in policy.allowed_assets
                or proposal.asset_out not in policy.allowed_assets,
            ),
            ("unexpected_protocol", proposal.protocol != "MockDex"),
        )
        findings = [
            Finding(check=name, level=RiskLevel.HIGH, explanation=name.replace("_", " "))
            for name, failed in checks
            if failed
        ]
        maximum = int(policy.daily_spending_limit.amount * 1_000_000)
        if proposal.amount * 100 >= maximum * 70:
            findings.append(
                Finding(
                    check="near_daily_maximum",
                    level=RiskLevel.MEDIUM,
                    explanation="Action consumes at least 70% of the daily limit",
                )
            )
        level = (
            RiskLevel.HIGH
            if any(f.level == RiskLevel.HIGH for f in findings)
            else (RiskLevel.MEDIUM if findings else RiskLevel.LOW)
        )
        return RiskAssessment(level=level, findings=tuple(findings))


def decide(policy: PolicyDecision, simulation: SimulationResult, risk: RiskAssessment) -> Outcome:
    if not policy.allowed or not simulation.success or risk.level == RiskLevel.HIGH:
        return Outcome.BLOCK
    return Outcome.REQUIRE_APPROVAL if risk.level == RiskLevel.MEDIUM else Outcome.AUTO_EXECUTE
