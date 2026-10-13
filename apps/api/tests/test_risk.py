import pytest
from app.risk.engine import RiskEngine
from app.schemas.domain import Deployment, PolicyDraft, SimulationResult, TransactionProposal


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("amount", 30_000_000, "LOW"),
        ("amount", 70_000_000, "MEDIUM"),
        ("maximum_slippage_bps", 1000, "HIGH"),
        ("action_type", "APPROVE", "HIGH"),
        ("destination", "0x" + "99" * 20, "HIGH"),
        ("operation", "arbitrary", "HIGH"),
        ("contract_address", "0x" + "99" * 20, "HIGH"),
        ("protocol", "unknown", "HIGH"),
    ],
)
def test_risk(
    deployment: Deployment,
    policy: PolicyDraft,
    proposal: TransactionProposal,
    field: str,
    value: object,
    expected: str,
) -> None:
    proposal = proposal.model_copy(update={field: value})
    result = RiskEngine(deployment).evaluate(
        proposal, policy, SimulationResult(success=True, contract_called=proposal.contract_address)
    )
    assert result.level == expected


def test_simulation_failure(
    deployment: Deployment, policy: PolicyDraft, proposal: TransactionProposal
) -> None:
    result = RiskEngine(deployment).evaluate(
        proposal, policy, SimulationResult(success=False, contract_called=proposal.contract_address)
    )
    assert result.level == "HIGH"
