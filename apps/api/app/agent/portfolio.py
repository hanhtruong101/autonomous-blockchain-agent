import json
from typing import Protocol

from app.agent.sizing import calculate_plan
from app.schemas.ai import (
    AgentAssessment,
    AgentDecision,
    PolicyIntent,
    ProposalIntent,
    StructuredProvider,
)
from app.schemas.domain import Deployment, PolicyDraft, TransactionProposal, WalletState


class PortfolioProposer(Protocol):
    def propose(
        self, state: WalletState, policy: PolicyDraft, version_id: str, deployment: Deployment
    ) -> TransactionProposal | AgentAssessment | None: ...


class AITradingAgent:
    """Provider-independent proposal mapper; no signing or execution dependencies."""

    def __init__(self, provider: StructuredProvider) -> None:
        self.provider = provider

    def propose(
        self, state: WalletState, policy: PolicyDraft, version_id: str, deployment: Deployment
    ) -> AgentAssessment:
        context = PolicyIntent(
            minimum_usdc_ratio=policy.minimum_usdc_ratio,
            daily_spending_limit=policy.daily_spending_limit,
            rebalance=policy.rebalance,
            portfolio_targets=policy.portfolio_targets,
            maximum_slippage_bps=policy.maximum_slippage_bps,
            protocol="MockDex",
        )
        response = self.provider.generate(
            json.dumps(
                {
                    "task": "portfolio_proposal",
                    "usdc_units": str(state.usdc_units),
                    "weth_units": str(state.weth_units),
                    "spent_units": str(state.spent_units),
                    "remaining_daily_allowance_units": str(
                        max(
                            0,
                            int(policy.daily_spending_limit.amount * 1_000_000) - state.spent_units,
                        )
                    ),
                    "maximum_proposal_units": str(int(policy.maximum_trade_amount * 1_000_000)),
                    "valuation": "Both mock tokens have six decimals and fixed 1:1 value.",
                    "allowed_assets": list(policy.allowed_assets),
                    "allowed_protocols": list(policy.allowed_protocols),
                    "available_actions": ["SWAP", "HOLD"],
                    "approved_policy": context.model_dump(mode="json"),
                }
            ),
            json.dumps(ProposalIntent.model_json_schema(mode="serialization")),
        )
        intent = ProposalIntent.model_validate_json(response)
        decision = AgentDecision(action=intent.action, reason=intent.reason)
        if intent.action == "HOLD":
            return AgentAssessment(decision=decision)
        # Preserve the model's trade fields. Independent gates decide permission;
        # addresses, chain and operation come only from trusted application state.
        proposal = TransactionProposal(
            policy_version_id=version_id,
            chain_id=state.chain_id,
            wallet=deployment.account,
            destination=deployment.account,
            asset_in=intent.asset_in,
            asset_out=intent.asset_out,
            amount=int(intent.amount_units),
            protocol=intent.protocol,
            contract_address=deployment.dex,
            operation="swap",
            maximum_slippage_bps=intent.maximum_slippage_bps,
            reason=intent.reason,
        )
        return AgentAssessment(decision=decision, proposal=proposal)


class PortfolioAgent:
    """Deterministic reference agent. It has no signer or execution dependency."""

    def propose(
        self, state: WalletState, policy: PolicyDraft, version_id: str, deployment: Deployment
    ) -> TransactionProposal | None:
        plan = calculate_plan(state, policy)
        if plan.amount == 0:
            return None
        return TransactionProposal(
            policy_version_id=version_id,
            chain_id=state.chain_id,
            wallet=state.address,
            asset_in=plan.asset_in,
            asset_out=plan.asset_out,
            amount=plan.amount,
            destination=state.address,
            protocol="MockDex",
            contract_address=deployment.dex,
            operation="swap",
            maximum_slippage_bps=policy.maximum_slippage_bps,
            reason=plan.reason,
        )
