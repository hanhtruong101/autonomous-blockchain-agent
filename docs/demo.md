# Reproducible local demonstration

Use the README startup with a fresh 500 TestUSDC / 500 TestWETH account.
All assets have a fixed 1:1 mock value. Use a fresh matching chain/database for
separate sequences; do not reset a running demo to test a different scenario.

## AI portfolio workflow

Create this policy:

> Keep approximately 55% of my portfolio in USDC, never spend more than 100 USDC per day, rebalance on demand, and only interact with approved protocols.

Under Advanced settings choose Exact target, leave minimum USDC blank, and set
maximum per trade to 30. Review and approve. Run portfolio check in Agent activity.
The permitted direction is WETH â†’ USDC. Offline sizing proposes 30 then 20,
ending at 550/450. Actual AI may choose smaller amounts or HOLD; inspect its reason.
A low-risk valid proposal can execute; a blocked proposal must have no submission.
Enable 30-second checks separately to observe scheduling without clicking Run.
At target, the next check skips AI. Check history distinguishes skips from AI HOLD.

## Fixed safety scenarios Aâ€“D and medium

Start a separate fresh 500/500 deployment and matching database. Use offline mode
for a deterministic fixture demonstration. Create this policy:

> Keep approximately 30% of my portfolio in USDC, never spend more than 100 USDC per day, rebalance on demand, and only interact with approved protocols.

The fixture buttons are not part of the application UI. With the fresh offline
stack running, set the same `AUTONOMY_OWNER_TOKEN` in a terminal at the project
root, then run:

```powershell
uv run python scripts/demo.py
```

The script creates the policy above with Exact target, no minimum and a 100-unit
per-trade limit. Review its printed draft and type APPROVE to activate it.
It runs A–D and leaves the medium-risk proposal for review in Approval queue.
Keep automatic scheduling off during this sequence.

| Scenario | Expected result |
|---|---|
| A: 30-unit swap USDC â†’ WETH | EXECUTED; balances 470/530, daily spend 30 |
| B: 80-unit budget test | BLOCKED; total 110 would exceed 100 |
| C: unknown contract | BLOCKED; target not allowed |
| D: excessive slippage | BLOCKED; policy/risk checks reject |
| Medium: 70-unit approval test | AWAITING_APPROVAL; no submission before approval |

Approve medium in Approval queue: expected balances 400/600 and daily spend 100.
Alternatively reject it and confirm no new transaction. The next ordinary portfolio
check must skip AI because the budget is exhausted after the approved sequence.
Fixtures are deliberately fixed proposals, not evidence of model reasoning.
`scripts/demo.py` runs the same Aâ€“D sequence and leaves medium for browser review.

## E: independent on-chain enforcement

```powershell
forge test --root contracts --chain-id 31337 --match-test testBypassDailyLimit -vv
```

This bypasses Python and verifies that the contract rejects agent overspending.
It does not use your interactive wallet or require real funds.

## Freeze and evidence

Emergency freeze must disable execution and request an on-chain pause. Resume
must leave scheduling off. A submitted transaction cannot be cancelled.
For each proposal inspect policy rules, simulation, risk, approval, receipt/hash
and audit events. Blocked/rejected proposals must not produce an execution hash.
These are expected outcomes, not a claim that this revision has been run on every environment.
