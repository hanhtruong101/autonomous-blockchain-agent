# Evaluating controlled autonomy

Run from the repository root:

```powershell
uv run python scripts/evaluate_agent.py
uv run python scripts/evaluate_agent.py --ollama-model llama3:latest
```

Use an installed local model, optionally --limit 4 for a short subset. Refresh
Evaluation in the UI after completion. GET /evaluation reads the saved
local/evaluation/ollama_trades.json report; it never starts inference.
Historical bounded-decision reports are preserved separately and not loaded.

The 16 synthetic cases test both directions, small gaps, tolerance boundaries,
budget exhaustion, trade caps, hard minimums, medium risk and simulation failure.
The live AITradingAgent proposes HOLD or SWAP with its own amount. The benchmark
uses synthetic simulation deltas and deterministic policy/risk checks; no RPC,
signing, activation or execution is possible. Live readiness would skip some
snapshots that this benchmark deliberately presents to the model.

- Action agreement: HOLD versus a proposed trade compared with the scenario.
- Trade match: exact assets and amount versus the independently specified
  deterministic reference, counted only when a trade is proposed.
- Safety outcome: hypothetical block, approval or automatic-execution decision.

A smaller permitted amount can differ from the reference without being unsafe.
A correct amount can still be blocked when simulation fails. HOLD can be safe
but delay progress; zero sizing cases is not proof of success. Invalid output
is counted as a blocked generation failure, with no fallback.

Latency depends on hardware and loading. These are limited single-step correctness
and intervention proxies, not measured human time savings, profitability or a
model ranking. Compare identical rows across runs. Earlier observations below
belong to historical implementations and are not current live-agent scores.

## Verification observations, 2026-10-11

The deterministic baseline matches 16/16 expected plans. One local `llama3:latest`
bounded-decision run matched 8/16 expected intentions; all 10 REBALANCE requests
produced the expected calculated plan (including no-trade refusals). There were no
schema-invalid responses. These numbers describe one run and do not establish
general model reliability, profitability or time savings.

The earlier raw-amount benchmark matched 1/16 complete plans. That was a different
experiment where the model supplied amounts. Its `ollama.json` file is retained
locally as historical evidence but is not loaded into the current Evaluation page.
Do not compare those percentages as if the task and metric were unchanged.

## Small human-time study

1. Choose three tasks: reach a target with a small gap, wait for a weekly cadence,
   and review a medium-risk transaction. Use identical disposable fixtures for
   each comparison, including balances, policy, budget and cadence.
2. Compare a manual workflow, deterministic automation without AI, and the same
   automation with AI interpretation and bounded decisions. Keep execution safeguards equal.
3. Record setup/review time, active interaction time, clicks, approvals, correction
   time and successful goal completion. Record model waiting time separately.
4. Repeat each task at least three times and alternate the order to reduce
   familiarity effects. Count failures and recovery work rather than discarding
   unsuccessful runs. Use a simple spreadsheet; no telemetry service is needed.
5. Report medians and ranges with the number of trials. Separate one-time setup
   cost from repeated operating cost. Only claim time savings supported by these
   observations, and distinguish automation's benefit from the LLM's contribution.

Never use real funds. Reset only explicitly disposable test fixtures, not a
working demonstration with evidence you want to preserve.
