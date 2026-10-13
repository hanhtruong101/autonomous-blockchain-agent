# AI treasury agent

## Current workflow

The live model observes balances and the approved policy, then returns HOLD or
SWAP with assets, an integer amount, maximum slippage and reasoning. The backend
preserves those proposed trade fields. It supplies the trusted local wallet,
chain and MockDex address; AI has no signer, tools or permission-changing access.

Deterministic policy rules, simulated goal improvement and hard minimum checks,
risk assessment, approval tiers and smart-account restrictions govern execution.
Low risk may execute, medium risk waits for owner approval, and high risk or a
policy/simulation failure blocks. Approval binds the exact stored proposal;
current state and simulation are rechecked before signing. Invalid model output
fails closed without an executable fallback.

The integer reference planner remains in offline mode and readiness checks.
Readiness prevents calls when cadence, tolerance, budget, hard minimum or pending
work makes a run ineligible. It does not replace an eligible AI proposal's amount.
This remains goal-based treasury automation with fake fixed-price assets, not
price prediction or unrestricted trading.

## Try it

1. Stop an enabled schedule if you want to review the behavior before resuming.
   Restart API and frontend with AUTONOMY_AI_PROVIDER=ollama and your installed
   AUTONOMY_AI_MODEL. No migration, redeployment or wallet reset is needed.
2. Review an approved on-demand policy with a reachable target, daily budget and
   per-trade cap. A fresh 1000-USDC wallet and 95% target allow up to 50 USDC total
   toward that goal; a 30-USDC cap limits each proposed trade.
3. Choose Agent activity / Run portfolio check. Open Proposals & outcomes to see
   the model's exact amount, direction, provider, policy, simulation and risk.
   A model can propose 17 instead of 30; a permitted smaller trade can execute.
4. Read Check history: system skips did not call AI, AI HOLD contains its reason,
   and proposed trades link to their current outcome and full transaction detail.
   Oversized or wrong-direction trades should appear BLOCKED with no transaction
   hash. Three repeated HOLDs produce an advisory, never an automatic fallback.
5. To test scheduling, choose 30 seconds / Enable for approved policy, leave the
   backend and Ollama running, and inspect new history without clicking Run.
   A weekly policy can still skip for 168 hours after a completed trade.
6. Review medium-risk proposals in Approval queue. Test Stop and Emergency freeze;
   freeze invalidates pending work and requests the independent on-chain pause.
7. Run the optional synthetic comparison from Evaluation. It now uses the same
   AI trade proposer as live runs, without RPC, signing or wallet changes.
   Compare action, proposed amount and safety separately. A reference mismatch
   does not automatically mean an unsafe trade.

No existing policy is rewritten. Old bounded-decision records remain readable and
carry their original generation metadata. Historical reports below describe the
previous phase, not verification of this change. Current checks are recorded in
[AI trade verification](verification-ai-trades.md).

## Historical verification: earlier HOLD/REBALANCE-only phase, 2026-10-11

- Python: 229 passed in the ordinary invocation; six opt-in integrations were
  excluded there and exercised separately against isolated PostgreSQL/Anvil.
- Added 14 regression cases covering HOLD history, repeated-HOLD advisories,
  policy replacement, exact sizing, malformed intents, unexpected amount fields,
  exhausted budget, approval-status projection, timezone serialization,
  scheduled skips and owner freeze during model generation.
- Browser with actual local `llama3:latest`: the 95% goal produced repeated HOLD
  decisions despite eligibility. The UI preserved these reasons and displayed the
  advisory. This is a model limitation, not proof that the target was reached.
- A separately reviewed 70% policy produced a scheduled REBALANCE decision and a
  successful **30-USDC** Anvil trade through policy, simulation and low-risk gates.
  No manual Run or A–D button was used for that transaction. Check history exposed
  all five stages and linked to the stored proposal.
- The read-only Ollama benchmark recorded 8/16 intent agreements and 10/10
  calculated-plan matches after REBALANCE, including four no-trade refusals.
  This is different from the earlier raw-amount experiment, not a comparable
  before/after reliability percentage.
- Ruff, strict mypy, TypeScript, ESLint and the production frontend build passed.
- All six opt-in integrations passed separately, including PostgreSQL locking,
  concurrent schedule/freeze behavior and four fresh-chain Anvil flows. Solidity
  regression tests passed 14/14, including the independent spending-limit bypass
  rejection and 256 fuzz runs.

The verification used a separate database and Anvil port 18545. The normal demo
chain was not reset. Temporary verification services were stopped afterwards.
Docker Compose and paid OpenAI requests were not exercised in this update.

## Fit and limitations

This demonstrates goal-based controlled autonomy: an AI proposes an intention,
trusted calculations construct a plan, and independent controls decide execution.
It is not a wallet chatbot or price-prediction bot. The model cannot access keys
or expand permissions. The sandbox holds only fake assets and never connects to
an owner's real wallet.

The model can still misunderstand a goal or choose unnecessary HOLDs. A successful
demo does not establish real-world time savings, market safety or challenge bonus
points. Prices remain fixed 1:1, contracts are educational and unaudited, and
portfolio minimums remain off-chain rules. See the threat model and evaluation
methodology before extending the scope.
