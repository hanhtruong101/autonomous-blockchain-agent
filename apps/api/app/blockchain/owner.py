"""Owner-only local contract controls, never exposed to proposal generators."""

from typing import Protocol

from app.blockchain.adapter import LocalSmartAccountAdapter


class OwnerControls(Protocol):
    def set_paused(self, paused: bool) -> str: ...


class LocalOwnerControls:
    def __init__(self, adapter: LocalSmartAccountAdapter) -> None:
        self.adapter = adapter

    def set_paused(self, paused: bool) -> str:
        self.adapter.guard()
        tx_hash = self.adapter.account.functions.setPaused(paused).transact(
            {"from": self.adapter.deployment.owner}
        )
        receipt = self.adapter.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        if receipt["status"] != 1:
            raise RuntimeError("Owner pause transaction failed")
        return str(tx_hash.to_0x_hex())
