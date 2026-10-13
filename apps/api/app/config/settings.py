from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTONOMY_", extra="ignore", hide_input_in_errors=True
    )
    environment: str = "local"
    chain_id: int = 31337
    rpc_url: str = "http://127.0.0.1:8545"
    database_url: str = "postgresql+psycopg://autonomy:local-only@localhost:5432/autonomy"
    owner_token: SecretStr
    deployment_path: str = "local/deployment.json"
    automation_worker: bool = True
    ai_provider: Literal["offline", "openai", "ollama"] = "offline"
    ai_model: str = "gpt-6-luna"
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @model_validator(mode="after")
    def local_only(self) -> "Settings":
        if self.chain_id != 31337 or self.environment != "local":
            raise ValueError("Execution is supported only on local Anvil chain 31337")
        if len(self.owner_token.get_secret_value()) < 24:
            raise ValueError("An explicit owner token of at least 24 characters is required")
        from urllib.parse import urlparse

        rpc = urlparse(self.rpc_url)
        if (
            rpc.hostname not in {"localhost", "127.0.0.1", "anvil"}
            or rpc.scheme != "http"
            or rpc.username
            or rpc.password
            or rpc.query
            or rpc.fragment
        ):
            raise ValueError("RPC must be a local Anvil endpoint")
        if self.ai_provider == "openai":
            if (
                not self.ai_model
                or not self.openai_api_key
                or not self.openai_api_key.get_secret_value()
            ):
                raise ValueError("OpenAI mode requires AUTONOMY_AI_MODEL and OPENAI_API_KEY")
        if self.ai_provider == "ollama" and (
            "ai_model" not in self.model_fields_set
            or not self.ai_model.strip()
            or "cloud" in self.ai_model.lower()
            or "/" in self.ai_model
        ):
            raise ValueError("Ollama requires AUTONOMY_AI_MODEL naming an installed local model")
        return self
