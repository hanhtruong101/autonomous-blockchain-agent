import os

from pydantic import SecretStr

from app.api.application import create_app
from app.config.settings import Settings

app = create_app(Settings(owner_token=SecretStr(os.environ.get("AUTONOMY_OWNER_TOKEN", ""))))
