import json
from pathlib import Path
from typing import Any, Protocol

from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import ContractCustomError

from app.schemas.domain import Deployment, TransactionProposal, WalletState


class SimulationRejected(ValueError):
    """A sanitized, locally decoded contract error suitable for an audit event."""


class SmartAccountAdapter(Protocol):
    deployment: Deployment

    def state(self) -> WalletState: ...
    def simulate(self, proposal: TransactionProposal) -> int: ...
    def submit(self, proposal: TransactionProposal) -> str: ...
    def confirmed(self, transaction_hash: str) -> bool: ...


class LocalSmartAccountAdapter:
    def __init__(self, rpc_url: str, deployment_path: str) -> None:
        self.web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        path = Path(deployment_path)
        if not path.is_file():
            raise RuntimeError(
                "Missing local deployment file. From the project root, start Anvil and run "
                "`uv run python scripts/deploy.py` before starting the API. "
                "Check AUTONOMY_DEPLOYMENT_PATH (default: local/deployment.json)."
            )
        self.deployment = Deployment.model_validate_json(path.read_text())
        self.guard()
        self.account = self.contract("PolicySmartAccount", self.deployment.account)
        self.usdc = self.contract("MockUSDC", self.deployment.usdc)
        self.weth = self.contract("MockUSDC", self.deployment.weth)
        for address in (
            self.deployment.account,
            self.deployment.dex,
            self.deployment.usdc,
            self.deployment.weth,
        ):
            if not self.web3.eth.get_code(Web3.to_checksum_address(address)):
                raise RuntimeError(
                    "Missing contracts on the current Anvil chain; execution disabled. "
                    "Start a fresh local Anvil and run `uv run python scripts/deploy.py` "
                    "before starting the API. A saved deployment.json does not restore "
                    "contracts after Anvil restarts."
                )
        if self.account.functions.agent().call().lower() != self.deployment.agent.lower():
            raise RuntimeError("Agent is revoked or deployment is inconsistent")

    def guard(self) -> None:
        if self.web3.eth.chain_id != 31337:
            raise RuntimeError("Only local chain 31337 is permitted; mainnet is prohibited")
        if "anvil" not in self.web3.client_version.lower():
            raise RuntimeError("Execution requires Anvil")

    def contract(self, name: str, address: str) -> Any:
        artifact = json.loads(Path(f"contracts/out/{name}.sol/{name}.json").read_text())
        return self.web3.eth.contract(
            address=Web3.to_checksum_address(address), abi=artifact["abi"]
        )

    def state(self) -> WalletState:
        self.guard()
        timestamp = self.web3.eth.get_block("latest")["timestamp"]
        return WalletState(
            address=self.deployment.account,
            chain_id=31337,
            usdc_units=self.usdc.functions.balanceOf(self.deployment.account).call(),
            weth_units=self.weth.functions.balanceOf(self.deployment.account).call(),
            spent_units=self.account.functions.spent(timestamp // 86400).call(),
            block_timestamp=timestamp,
        )

    def operation(self, proposal: TransactionProposal) -> Any:
        self.guard()
        if (
            proposal.chain_id != 31337
            or proposal.wallet.lower() != self.deployment.account.lower()
            or proposal.action_type != "SWAP"
            or proposal.operation != "swap"
            or proposal.protocol != "MockDex"
            or proposal.contract_address.lower() != self.deployment.dex.lower()
            or proposal.destination.lower() != self.deployment.account.lower()
            or proposal.asset_in == proposal.asset_out
            or proposal.maximum_slippage_bps > 100
        ):
            raise ValueError("Proposal does not describe a supported local operation")
        asset = self.deployment.usdc if proposal.asset_in == "USDC" else self.deployment.weth
        minimum = (proposal.amount * (10000 - proposal.maximum_slippage_bps) + 9999) // 10000
        return self.account.functions.swap(
            bytes.fromhex(proposal.digest()), self.deployment.dex, asset, proposal.amount, minimum
        )

    def simulate(self, proposal: TransactionProposal) -> int:
        operation = self.operation(proposal)
        try:
            operation.call({"from": self.deployment.agent})
            return int(operation.estimate_gas({"from": self.deployment.agent}))
        except ContractCustomError as error:
            reasons = {
                "Unauthorized()": "Agent is unauthorized or revoked",
                "Paused()": "Smart account is paused",
                "LimitExceeded()": "On-chain daily spending limit exceeded",
                "Forbidden()": "On-chain target, asset or slippage restriction failed",
                "Replay()": "This proposal has already executed on-chain",
            }
            selector = error.data[:10] if isinstance(error.data, str) else ""
            reason = next(
                (
                    message
                    for signature, message in reasons.items()
                    if Web3.keccak(text=signature)[:4].to_0x_hex() == selector
                ),
                "Smart account rejected the simulated operation",
            )
            raise SimulationRejected(reason) from None

    def submit(self, proposal: TransactionProposal) -> str:
        return str(self.operation(proposal).transact({"from": self.deployment.agent}).to_0x_hex())

    def confirmed(self, transaction_hash: str) -> bool:
        receipt = self.web3.eth.wait_for_transaction_receipt(HexBytes(transaction_hash), timeout=30)
        return receipt["status"] == 1
