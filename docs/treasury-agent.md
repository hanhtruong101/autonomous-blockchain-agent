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
   per-trade cap. A fresh 500/500 wallet and 55% USDC target allow up to 50 WETH total
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

Existing policies are not rewritten. Historical bounded-decision records remain
readable with their original generation metadata. See the
[historical verification index](history/README.md) for dated evidence; those
reports are not current startup instructions.

## Fit and limitations

This demonstrates goal-based controlled autonomy: AI proposes a typed trade
and amount, and independent controls decide execution.
It is not a wallet chatbot or price-prediction bot. The model cannot access keys
or expand permissions. The sandbox holds only fake assets and never connects to
an owner's real wallet.

The model can still misunderstand a goal or choose unnecessary HOLDs. A successful
demo does not establish real-world time savings, market safety or challenge bonus
points. Prices remain fixed 1:1, contracts are educational and unaudited, and
portfolio minimums remain off-chain rules. See the threat model before extending the scope.
