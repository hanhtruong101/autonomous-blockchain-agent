import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

Address = Annotated[str, StringConstraints(pattern=r"^0x[0-9a-fA-F]{40}$")]
Units = Annotated[int, Field(strict=True, ge=1, le=10**15)]


def now() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Asset(StrEnum):
    USDC = "USDC"
    WETH = "WETH"


class Action(StrEnum):
    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    APPROVE = "APPROVE"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Outcome(StrEnum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class SpendingLimit(Model):
    asset: Literal["USDC"] = "USDC"
    amount: Decimal = Field(gt=0, le=100, decimal_places=6)

    @field_validator("amount", mode="before")
    @classmethod
    def no_float(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use decimal strings for financial values")
        return value


class Rebalance(Model):
    tolerance_bps: int = Field(default=500, strict=True, ge=0, le=1000)
    enabled: bool = True
    minimum_interval_hours: int = Field(ge=0, le=8760)


class Targets(Model):
    USDC: Decimal = Field(ge=0, le=1)
    WETH: Decimal = Field(ge=0, le=1)

    @field_validator("USDC", "WETH", mode="before")
    @classmethod
    def no_float(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use decimal strings for portfolio targets")
        return value

    @model_validator(mode="after")
    def total(self) -> "Targets":
        if self.USDC + self.WETH != Decimal(1):
            raise ValueError("Targets must sum to one")
        return self


class PolicyDraft(Model):
    # Defaults preserve existing approved policy permissions.
    maximum_trade_amount: Decimal = Field(default=Decimal("100"), gt=0, le=100, decimal_places=6)
    minimum_usdc_ratio: Decimal | None = Field(default=None, ge=0, le=1)

    @field_validator("maximum_trade_amount", "minimum_usdc_ratio", mode="before")
    @classmethod
    def exact_constraints(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use decimal strings for financial constraints")
        return value

    @model_validator(mode="after")
    def compatible_floor(self) -> "PolicyDraft":
        if (
            self.minimum_usdc_ratio is not None
            and self.minimum_usdc_ratio > self.portfolio_targets.USDC
        ):
            raise ValueError("Minimum USDC allocation cannot exceed the USDC target")
        return self

    daily_spending_limit: SpendingLimit
    allowed_assets: tuple[Asset, ...] = (Asset.USDC, Asset.WETH)
    allowed_protocols: tuple[Literal["MockDex"], ...] = ("MockDex",)
    allowed_contracts: tuple[Address, ...] = Field(min_length=1)
    rebalance: Rebalance
    portfolio_targets: Targets
    maximum_slippage_bps: int = Field(strict=True, ge=0, le=100)


class TransactionProposal(Model):
    id: str = Field(default_factory=lambda: str(uuid4()))
    policy_version_id: str
    action_type: Action = Action.SWAP
    chain_id: int = Field(strict=True, gt=0)
    wallet: Address
    asset_in: Asset
    asset_out: Asset
    amount: Units
    destination: Address
    protocol: str = Field(min_length=1, max_length=80)
    contract_address: Address
    operation: str = Field(min_length=1, max_length=80)
    maximum_slippage_bps: int = Field(strict=True, ge=0, le=10000)
    reason: str = Field(min_length=1, max_length=2000)
    created_at: datetime = Field(default_factory=now)

    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class RuleResult(Model):
    rule_name: str
    passed: bool
    reason: str
    observed_value: str
    required_value: str


class PolicyDecision(Model):
    allowed: bool
    rules: tuple[RuleResult, ...]


class TokenChange(Model):
    asset: Asset
    units: int


class SimulationResult(Model):
    success: bool
    estimated_gas: int = 0
    expected_token_changes: tuple[TokenChange, ...] = ()
    contract_called: Address
    revert_reason: str | None = None
    expected_output: int = 0
    slippage_bps: int = 0


class Finding(Model):
    check: str
    level: RiskLevel
    explanation: str


class RiskAssessment(Model):
    level: RiskLevel
    findings: tuple[Finding, ...]


class Evaluation(Model):
    policy: PolicyDecision
    simulation: SimulationResult
    risk: RiskAssessment
    outcome: Outcome


class WalletState(Model):
    address: Address
    chain_id: int
    usdc_units: int = Field(strict=True, ge=0)
    weth_units: int = Field(strict=True, ge=0)
    spent_units: int = Field(strict=True, ge=0)
    block_timestamp: int

    @field_serializer("usdc_units", "weth_units", "spent_units", when_used="json")
    def serialize_balance(self, value: int) -> str:
        # uint256 chain balances can exceed JavaScript's safe integer range.
        return str(value)


class Deployment(Model):
    chain_id: Literal[31337]
    owner: Address
    agent: Address
    recipient: Address
    usdc: Address
    weth: Address
    dex: Address
    account: Address


def as_utc(value: datetime) -> datetime:
    """SQLite stores naive UTC; PostgreSQL may return an offset-aware timestamp."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
