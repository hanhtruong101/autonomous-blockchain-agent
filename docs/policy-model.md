# Policy model

Financial amounts are decimal strings at policy boundaries and integer six-decimal token units in proposals. Floats are rejected. A proposal amount of `30000000` means 30 test tokens. Fixed mock prices value both tokens at one TestUSDC equivalent.

Example draft (replace the address with the deployed MockDex):

```json
{
  "daily_spending_limit": {"asset":"USDC", "amount":"100"},
  "maximum_trade_amount": "30",
  "minimum_usdc_ratio": null,
  "allowed_assets": ["USDC", "WETH"],
  "allowed_protocols": ["MockDex"],
  "allowed_contracts": ["0x0000000000000000000000000000000000000001"],
  "rebalance": {"enabled":true, "minimum_interval_hours":168, "tolerance_bps":100},
  "portfolio_targets": {"USDC":"0.70", "WETH":"0.30"},
  "maximum_slippage_bps": 100
}
```

## Interpretation and activation

`PolicyInterpreter` returns only `PolicyDraft`. `ProviderPolicyInterpreter` accepts a provider implementing structured generation and revalidates the returned JSON against the schema. Its interface has no activation, signing or chain access. `FakePolicyInterpreter` supplies fixtures without an API key.

The default `LocalPolicyInterpreter` is an offline bounded parser, **not an LLM**. It accepts this exact sentence structure, case-insensitively, with an optional final period:

> Keep approximately 70% of my portfolio in USDC, never spend more than 100 USDC per day, rebalance weekly, and only interact with approved protocols.

Percentage may be 0–100; budget must be positive and no greater than 100 with at most six decimals; cadence is `weekly`, `daily` or `on demand`. Extra instructions are rejected. It fixes the allowlist to the actual local MockDex and the maximum slippage to 100 basis points. Arbitrary natural language requires explicitly enabling an external provider, with the same draft approval gate.

## Optional LLM provider

Set `AUTONOMY_AI_PROVIDER=openai`, `AUTONOMY_AI_MODEL=gpt-6-luna` and `OPENAI_API_KEY` in the API environment. Offline is the default and needs no key. `OpenAIResponsesProvider` uses the OpenAI Python SDK Responses API with strict JSON schema, no tools, no automatic retries, no redirects and an explicit official endpoint.

The model returns address-free `PolicyIntent`, containing budget, targets, optional minimum USDC share, cadence, slippage and a supported logical protocol. Validation creates `PolicyDraft`; the backend supplies the deployed contract allowlist. Explicit form values for tolerance and per-trade ceiling become part of the reviewed draft. A form minimum can strengthen, but cannot weaken, a minimum returned by the interpreter. Review is essential because natural-language interpretation can be wrong.

Ollama is also supported locally; see README for configuration. Live portfolio checks validate model output as `ProposalIntent`: HOLD or SWAP, supported assets, integer amount, slippage and reason. HOLD creates no proposal. SWAP preserves model choices while trusted code supplies local addresses and operation. Deterministic policy and simulated allocation checks can reject incorrect amounts or directions; reference sizing is not substituted for model output. AI never activates a policy or executes a transaction.

Transport tests use `httpx2.MockTransport` with the SDK. Live account/model access has not been verified with a paid request. Refusals, malformed or incomplete output, tool calls, network failures and unsupported identifiers fail closed. Audit events store provider/model/schema metadata, never raw provider errors or keys. See [AI integration](ai-integration.md).

Creating a goal always adds a new immutable draft version. `POST /policies/{version_id}/approve` activates that exact version after review, marks the previous one superseded, and records the owner. Reapproving a used version is prohibited. No endpoint mutates a version's draft. The owner token authenticates all application endpoints.

## Enforcement

Each rule returns its name, pass/fail result, reason, observed value and required value. All rules run even when an earlier rule fails:

- DailySpendingLimitRule: chain spending plus proposal amount must fit the active budget.
- TradeSpendingLimitRule: each proposal must fit the approved per-trade ceiling.
- AllowedAssetRule: input and output must both be allowed.
- AllowedProtocolRule and AllowedContractRule: logical name and exact address must pass independently. Empty allowlists are never permissive.
- RebalanceFrequencyRule: the policy must enable rebalancing, and the minimum interval since the last confirmed action must elapse.
- MaximumSlippageRule: requested tolerance may not exceed policy tolerance.
- IdentityRule: chain, wallet and recipient must match the registered local account.
- OperationRule: only a swap between different supported assets is executable through the app.

The independent risk engine flags unknown contracts, changed recipients, unexpected operations, all direct token approvals, unexpected assets/protocols, simulation reverts and slippage over 1%. Amounts at least 70% of the daily policy limit require owner approval. High risk and policy failures always block, even when an approval exists.

The contract independently caps the daily spend at 100 units, supports only the two mock tokens, limits slippage, restricts targets and prevents replay. A smaller approved application budget does not automatically change the owner's on-chain limit; this difference is explicit in the review screen and threat model.

## Rebalance tolerance and goal improvement

`rebalance.tolerance_bps` defaults to 500 and must be an integer from 0 to 1000. It describes absolute percentage-point distance from the approved USDC allocation. At a 70% target with 500 bps, 65–75% is accepted. The backend skips unnecessary portfolio generation inside that band. The execution pipeline independently checks simulated post-swap allocation and requires a strictly smaller normalized target deviation. This blocks a directionally wrong or excessive overshooting trade even if its asset, contract, amount and slippage pass other rules. The check also runs again before signing an approved proposal. All comparisons use integer cross-products and Decimal ratios, without floating point.

These values assume both mock assets have six decimals and a fixed 1:1 price. They are not an oracle or production valuation model. Scheduling permission is owner-approved separately and tied to a specific active policy version; it cannot bypass daily budget, cadence, simulation, risk or approval checks.

## Target versus hard minimum

New UI drafts default to 100 basis points of tolerance and a 30-unit trade ceiling;
both are visible before approval. Stored versions are never rewritten. Legacy
drafts without these fields retain their former 500-bps tolerance and 100-unit
maximum permitted by the existing daily budget.

“Approximately 95%” expresses a target, not a guaranteed 95% floor. Set **Minimum
USDC share** to 95 to require at least that allocation after every trade. The
bounded offline template also accepts “Keep at least 95% ...”. The optional
`minimum_usdc_ratio` cannot exceed the target. Policy review intersects the target
band with this minimum: target 95%, tolerance 1 point, minimum 95% means an accepted
range of 95–96%.

The live planner chooses the smallest of the target gap, remaining daily budget
and per-trade ceiling, rounding down to integer token units without crossing the
target. The execution pipeline independently checks the simulated post-trade
minimum, including during approval revalidation. If a wallet already below the
minimum cannot restore it in one permitted trade, the strict rule requires no
trade; readiness explains the limitation. The hard minimum is an off-chain rule,
not a new independent smart-contract restriction.
