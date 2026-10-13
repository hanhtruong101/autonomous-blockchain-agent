# Exact local demonstration

Start the stack from README with a fresh database and Anvil. Open `http://localhost:5173` and enter the same local owner token. The account starts with 1,000 TestUSDC and the exchange has both fake assets. The public development signers have fake ETH.

## Create and approve a policy

Open **Create policy**, enter the following and choose **Create policy draft**:

```text
Keep approximately 70% of my portfolio in USDC, never spend more than 100 USDC per day, rebalance on demand, and only interact with approved protocols.
```

For the fixed A–D and medium sequence, set the form's maximum trade amount to 100 before creating the draft. Review the 100-unit daily and per-trade budgets, USDC/WETH assets, deployed MockDex address and 100 basis-point slippage ceiling. Choose **Approve and activate this policy**. Ordinary portfolio checks can keep the smaller default per-trade ceiling of 30.

Use **on demand** for the attack sequence: a weekly policy correctly blocks additional runs for 168 hours after A. Nothing silently disables that restriction.

## Scenarios A–D

Open **Agent activity**, expand **Educational safety scenarios**, and click each named scenario button in order:

| Scenario | Proposal | Expected result |
|---|---|---|
| A | Swap 30 TestUSDC through MockDex | Policy pass, simulation pass, risk LOW, EXECUTED; wallet becomes 970 USDC / 30 WETH |
| B | Swap another 80 | Daily total 110 exceeds 100: BLOCKED; no new transaction |
| C | Swap 40 through unknown address | Contract allowlist fails and risk HIGH: BLOCKED |
| D | Swap 20 with 20% tolerance | Policy fails and risk HIGH: BLOCKED |

Open each detail screen to see every rule, reason, simulation, risk finding and transaction hash. Only A creates an execution record. In **Audit log**, inspect the corresponding proposed, checked, simulated, assessed, submitted/confirmed or blocked events.

## Medium risk

After A–D, choose **Medium · 70-unit review**. Exactly 70 units remain in the daily budget. Policy and simulation pass; the risk engine requires approval because the amount is at least 70% of the daily limit.

Open **Approval queue**, follow **Review transaction**, inspect the full details and choose **Approve this exact transaction**. It executes only after another complete validation. The wallet now has 900 USDC / 100 WETH and daily spending is 100. A second approval attempt fails. To demonstrate rejection instead, reject this request and observe that no transaction is submitted.

## Scenario E: bypass the backend

```sh
forge test --root contracts --chain-id 31337 --match-test testBypassDailyLimit -vv
```

This isolated contract test directly calls the account as the agent: first 30, then 80. It never invokes Python policy validation. The second call reverts with `LimitExceeded`, proving the independent on-chain boundary. The tests also cover revocation, pause, replay, unsafe targets and agent attempts to modify permissions.

## Script alternative

```sh
uv run python scripts/demo.py
```

The script prints the draft and waits for you to type `APPROVE`. It checks A–D and leaves the medium transaction pending for review in the browser. Run only against a fresh stack.

## Verify chain evidence

Use the hash displayed by the UI:

```sh
cast receipt TRANSACTION_HASH --rpc-url http://localhost:8545
```

Run fresh integration tests separately because they intentionally consume the daily allowance:

```sh
RUN_ANVIL_TESTS=1 uv run pytest apps/api/tests/test_chain.py -q
# Reset and redeploy before the next command.
RUN_ANVIL_E2E=1 uv run pytest apps/api/tests/test_e2e_anvil.py -q
```

On PowerShell use `$env:RUN_ANVIL_E2E='1'` before the command, then `Remove-Item Env:RUN_ANVIL_E2E` afterward. To reset the Compose demonstration, run `docker compose down -v`, then `docker compose up --build`. This deliberately destroys only the project's disposable test state; do not reset during a run you want to preserve.

## Automatic workflow without A–D buttons

1. Apply `uv run alembic upgrade head`, restart FastAPI with Ollama configured as described in README, and start React.
2. Create/review/approve: "Keep approximately 70% in USDC, never spend more than 100 USDC per day, rebalance on demand, and only interact with approved protocols."
3. In Agent activity, select a 30-second check interval and click Enable for approved policy.
4. After the next check (plus model decision time), inspect Proposals & outcomes. A valid low-risk proposal executes, medium risk waits for owner approval, invalid/high-risk proposals are blocked. The model chooses HOLD or proposes a SWAP with its own assets, amount and slippage; the backend preserves these for safety validation. Check history also displays AI HOLD decisions without transactions. Readiness shows when no trade is needed or permitted, and skipped checks are recorded without a proposal.
5. Inspect Transaction detail for the `goal_improvement` rule, simulation, risk and local transaction hash. Check Audit Log for AUTOMATION_CHECK_STARTED and AUTOMATION_CHECK_COMPLETED or AUTOMATION_SKIPPED.
6. Click Emergency freeze. Confirm the UI is frozen, schedules off, pending proposals cancelled, and audit includes SMART_ACCOUNT_PAUSED. Run portfolio check must be disabled, and a direct API attempt must fail. Owner resume unpauses execution but does not re-enable the schedule.
7. Approving another policy must stop an enabled schedule; enable the replacement explicitly after reviewing it.

The new-policy form suggests a 30-unit per-trade ceiling. A fresh 1000-USDC wallet cannot reach 70/30 in one 100-unit-budget day. Waiting for cadence/budget is expected controlled behavior. A–E remain negative/security demonstrations, rather than steps needed for ordinary autonomous operation.

## Verify variable sizing and a hard minimum

On a fresh disposable wallet, create an on-demand 95% USDC policy with minimum
USDC share 95, tolerance 100 bps, daily budget 100 and trade ceiling 30. Approve it.
Offline mode calculates 30 then 20, leaving 950 USDC
and 50 WETH. AI mode may propose different amounts or HOLD. Wrong direction,
overspending or a simulated breach of the hard minimum must be blocked. Readiness then shows no trade needed and disables manual generation.
With Ollama configured, each eligible check records an AI trade decision and
generation metadata, including when AI chooses HOLD. Offline mode reproduces the two trades without model variability. Inspect `minimum_usdc_allocation` and `goal_improvement` in
transaction detail. Use **Evaluation** for additional synthetic scenarios without
spending even fake wallet assets.

New integrations are opt-in: `TEST_POSTGRES_URL` enables the concurrency/freeze test in `test_automation_integration.py`. `RUN_AUTOMATION_ANVIL=1`, `TEST_ANVIL_RPC` and `TEST_DEPLOYMENT_PATH` enable the real scheduled-trade/pause/resume test. Use a fresh isolated deployment for every real-chain integration; never run reset operations against your interactive demo chain.
