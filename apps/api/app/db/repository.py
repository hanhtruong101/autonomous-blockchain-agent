from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Automation, Base, Policy, PolicyVersion, User, Wallet


class Conflict(ValueError):
    pass


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get[T: Base](self, model: type[T], identifier: str) -> T:
        value = self.session.get(model, identifier)
        if value is None:
            raise Conflict("Resource does not exist")
        return value

    def wallet(self, address: str) -> Wallet:
        wallet = self.session.scalar(select(Wallet).where(Wallet.id == address).with_for_update())
        if wallet is None:
            raise Conflict("Wallet not initialized")
        return wallet

    def available_wallet(self, address: str) -> Wallet:
        wallet = self.wallet(address)
        if wallet.execution_paused:
            raise Conflict("Execution is frozen by the owner; resume explicitly")
        if wallet.generating_run_id:
            raise Conflict("An agent run is already generating a proposal")
        if wallet.busy_proposal_id:
            raise Conflict("Wallet has an in-flight or uncertain submission; reconcile it first")
        return wallet

    def active(self, wallet: Wallet) -> PolicyVersion:
        if not wallet.active_version_id:
            raise Conflict("An explicitly approved policy is required")
        version = self.get(PolicyVersion, wallet.active_version_id)
        if version.status != "ACTIVE":
            raise Conflict("Policy is not active")
        return version

    def initialize(self, address: str) -> None:
        if self.session.get(Wallet, address):
            return
        user = User(name="Local owner")
        self.session.add(user)
        self.session.flush()
        wallet = Wallet(id=address, user_id=user.id)
        self.session.add(wallet)
        self.session.flush()
        self.session.add(Policy(wallet_id=address))
        self.session.add(Automation(wallet_id=address))
