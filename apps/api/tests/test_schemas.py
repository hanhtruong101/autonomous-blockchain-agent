import pytest
from app.config.settings import Settings
from app.schemas.domain import TransactionProposal
from pydantic import SecretStr, ValidationError


@pytest.mark.parametrize("value", [0, -1, 1.1, True, "10", 2**256 - 1])
def test_bad_amount(proposal: TransactionProposal, value: object) -> None:
    with pytest.raises(ValidationError):
        TransactionProposal.model_validate(proposal.model_dump() | {"amount": value})


def test_bad_address(proposal: TransactionProposal) -> None:
    with pytest.raises(ValidationError):
        TransactionProposal.model_validate(proposal.model_dump() | {"destination": "wrong"})


@pytest.mark.parametrize("chain", [1, 10, 137, 8453, 42161, 11155111])
def test_chain_guard(chain: int) -> None:
    with pytest.raises(ValidationError):
        Settings(chain_id=chain, owner_token=SecretStr("long-local-test-only-token-value"))


def test_secret_required() -> None:
    with pytest.raises(ValidationError):
        Settings(owner_token=SecretStr(""))


@pytest.mark.parametrize("offset", [-8, 2, 9])
def test_expired_approval_with_timezone_offset(proposal, offset: int) -> None:
    from datetime import timedelta, timezone

    from app.approvals.validation import validate_approval
    from app.db.repository import Conflict
    from app.models.entities import ApprovalRequest
    from app.schemas.domain import now

    approval = ApprovalRequest(
        proposal_id=proposal.id,
        proposal_digest=proposal.digest(),
        status="PENDING",
        expires_at=(now() - timedelta(minutes=1)).astimezone(timezone(timedelta(hours=offset))),
    )
    with pytest.raises(Conflict, match="expired"):
        validate_approval(approval, proposal)
