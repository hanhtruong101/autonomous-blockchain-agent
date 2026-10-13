from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.entities import AuditEvent


def record(
    session: Session, event: str, entity_id: str, details: BaseModel | str, actor: str = "system"
) -> None:
    session.add(
        AuditEvent(
            event=event,
            entity_id=entity_id,
            actor=actor,
            details=details.model_dump_json() if isinstance(details, BaseModel) else details,
        )
    )
