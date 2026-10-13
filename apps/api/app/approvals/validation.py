from app.db.repository import Conflict
from app.models.entities import ApprovalRequest
from app.schemas.domain import TransactionProposal, as_utc, now


def validate_approval(approval: ApprovalRequest, proposal: TransactionProposal) -> None:
    if approval.status != "PENDING":
        raise Conflict("Approval has already been decided")
    if as_utc(approval.expires_at) <= now():
        raise Conflict("Approval expired; create a new proposal")
    if approval.proposal_id != proposal.id or approval.proposal_digest != proposal.digest():
        raise Conflict("Proposal differs from the reviewed transaction")
