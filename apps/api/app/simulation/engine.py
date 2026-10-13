from typing import Protocol

from app.blockchain.adapter import SimulationRejected, SmartAccountAdapter
from app.schemas.domain import SimulationResult, TokenChange, TransactionProposal


class SimulationEngine(Protocol):
    def simulate(self, proposal: TransactionProposal) -> SimulationResult: ...


class RpcSimulationEngine:
    def __init__(self, adapter: SmartAccountAdapter) -> None:
        self.adapter = adapter

    def simulate(self, proposal: TransactionProposal) -> SimulationResult:
        try:
            gas = self.adapter.simulate(proposal)
            return SimulationResult(
                success=True,
                estimated_gas=gas,
                contract_called=proposal.contract_address,
                expected_output=proposal.amount,
                expected_token_changes=(
                    TokenChange(asset=proposal.asset_in, units=-proposal.amount),
                    TokenChange(asset=proposal.asset_out, units=proposal.amount),
                ),
            )
        except SimulationRejected as error:
            return SimulationResult(
                success=False, contract_called=proposal.contract_address, revert_reason=str(error)
            )
        except Exception:
            # Do not persist provider exception text: it may include RPC credentials.
            return SimulationResult(
                success=False,
                contract_called=proposal.contract_address,
                revert_reason="Local RPC simulation failed or reverted",
            )
