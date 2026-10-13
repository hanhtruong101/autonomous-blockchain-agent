import secrets

from fastapi import Header, HTTPException

from app.config.settings import Settings


class OwnerAuth:
    def __init__(self, settings: Settings) -> None:
        self.token = settings.owner_token

    def __call__(self, authorization: str = Header(default="")) -> None:
        expected = "Bearer " + self.token.get_secret_value()
        if not secrets.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Owner authentication required")
