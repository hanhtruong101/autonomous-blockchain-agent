"""Local Ollama transport: no credentials, tools, remote URLs or automatic retries."""

import json
from typing import Literal

import httpx
from pydantic import BaseModel, Field, JsonValue

from app.policies.providers import ProviderFailure, strict_schema


class OllamaMessage(BaseModel):
    role: Literal["assistant"]
    content: str = Field(min_length=1)
    tool_calls: list[JsonValue] = Field(default_factory=list)


class OllamaResponse(BaseModel):
    done: Literal[True]
    done_reason: Literal["stop"]
    message: OllamaMessage


class OllamaProvider:
    def __init__(self, model: str, transport: httpx.BaseTransport | None = None) -> None:
        self.model = model
        self.transport = transport

    def generate(self, goal: str, schema: str) -> str:
        document = strict_schema(schema)
        policy_task = document.get("title") == "PolicyIntent"
        instructions = (
            "Interpret the user goal as a proposed policy, never activate it. "
            "Use only USDC/WETH and MockDex. Budget is token quantities, NOT base units. "
            "Targets are fractions between 0 and 1, NOT percentages or base units; sum to 1. "
            "On demand is 0 hours, daily 24, weekly 168. Maximum budget 100 and slippage 100 bps. "
            "Example for 70% USDC, 100 daily, on demand, 1% slippage: "
            '{"daily_spending_limit":{"asset":"USDC","amount":"100"},'
            '"portfolio_targets":{"USDC":"0.70","WETH":"0.30"},'
            '"rebalance":{"enabled":true,"minimum_interval_hours":0},'
            '"maximum_slippage_bps":100,"protocol":"MockDex"}. '
            "Use the actual user goal; do not weaken restrictions if ambiguous. "
            if policy_task
            else "Propose one treasury trade for the supplied portfolio. "
            "Never authorize or execute. "
            "Balances and amount_units are integer strings: 1000000 units per token. "
            "Calculate the target gap. Above the USDC target swap USDC to WETH; below, reverse. "
            "Use the smallest of the target gap, maximum_proposal_units "
            "and remaining_daily_allowance_units. "
            "Respect the approved tolerance and minimum_usdc_ratio. Never cross the target. "
            "HOLD with zero amount if within tolerance, out of budget, or a minimum cannot be met. "
        )
        if document.get("title") == "AgentDecision":
            instructions = (
                "Observe the supplied treasury snapshot and choose HOLD or REBALANCE. "
                "REBALANCE means request a move toward the approved target; trusted code "
                "will choose the direction and amount, then run independent safety checks. "
                "HOLD means no transaction. Use HOLD inside tolerance, when budget is exhausted, "
                "or when no permitted trade can satisfy the hard minimum. "
                "Otherwise prefer REBALANCE for this goal-based, fixed-price mock treasury. "
                "Return action and a short English reason only. Never supply an amount, "
                "address, permission, transaction or claim of execution. Do not predict prices. "
            )
        elif policy_task:
            instructions += (
                "Distinguish an approximate target from a hard minimum. For 'at "
                "least' or 'never below', "
                "set minimum_usdc_ratio to that fraction; otherwise null. "
                "Rebalance tolerance_bps is an absolute band around the target, "
                "not a spending limit. "
            )
        instructions += (
            "Return only JSON matching this schema. No tools, addresses or permissions. "
            "All output requires independent validation and policies require owner approval. "
            + json.dumps(document)
        )
        try:
            with httpx.Client(
                timeout=httpx.Timeout(180, connect=5),
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    "POST",
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": goal},
                        ],
                        "format": document,
                        "options": {"temperature": 0, "num_predict": 2048},
                    },
                ) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 100_000:
                            raise ValueError("Response too large")
            result = OllamaResponse.model_validate_json(bytes(body))
            if result.message.tool_calls:
                raise ValueError("Tool output prohibited")
            return result.message.content
        except httpx.TimeoutException:
            raise ProviderFailure("ollama_timeout") from None
        except httpx.HTTPStatusError as error:
            raise ProviderFailure(
                "ollama_model" if error.response.status_code == 404 else "ollama_request"
            ) from None
        except httpx.HTTPError:
            raise ProviderFailure("ollama_connection") from None
        except ValueError:
            raise ProviderFailure("ollama_invalid") from None
