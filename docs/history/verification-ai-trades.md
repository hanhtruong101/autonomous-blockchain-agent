# AI trade proposals: final UI verification

Verified on 2026-10-12 (Europe/Amsterdam). This report completes the UI checks
interrupted during the previous implementation turn. All funds were fake.

## Environment and boundaries

Used isolated Anvil chain 31337 at port 18547, FastAPI at 8013, Vite at 5192,
an isolated SQLite database, and actual local Ollama `llama3:latest`. The normal
application database and default RPC at 8545 were not reset. PostgreSQL remains
the normal deployment database; this browser run does not validate its locking.

The model chooses HOLD or proposes assets, integer amount, slippage and reason.
The application preserves its amount and supplies trusted addresses/operation.
Policy, simulation, risk, approvals and the smart account independently govern
execution. No fallback trade or expanded signing permission was introduced.

## Browser and chain results

| Check | Observed result |
|---|---|
| Policy generation and review | Actual Ollama returned 70/30 targets, 100 daily, on-demand cadence. Explicit form settings were shown before activation. |
| Manual AI run | Model proposed 50 TestUSDC. History, proposal card, detail and backend all retained 50 and the same accepted reason. Policy/simulation passed, risk LOW, receipt status 1. |
| Scheduled AI run | Owner enabled 30-second checks. A subsequent model-proposed 50-unit trade executed without another Run click. |
| Exhausted budget | After 100 total spent, UI showed BUDGET EXHAUSTED and SYSTEM SKIPPED. History stated AI was not called. |
| High-risk fixture | Explicit slippage scenario D showed HIGH/BLOCKED, failed checks and no transaction hash. Agent nonce remained 2. |
| Medium-risk rejection | A 70-unit fixture reached Approval queue. Reject updated detail and history to REJECTED, with no hash or extra agent transaction. |
| Medium-risk approval | A new 70-unit fixture remained pending until Approve. Afterwards detail/history showed EXECUTED and a confirmed transaction; agent nonce became 3. |
| Emergency freeze | UI showed FROZEN, Run was disabled, direct API run returned 409, and contract `paused()` was true. |
| Owner resume | Contract unpaused and scheduling remained OFF. UI displayed the corrected resume message. |
| Audit log | UI showed proposal checks, approvals/rejection, confirmations, SMART_ACCOUNT_PAUSED and EXECUTION_RESUMED. |
| Evaluation | UI read the saved AI trade-proposal report and displayed model, timestamp, reference differences and safety outcomes. No new inference or signing was triggered by viewing it. |

For the medium-risk checks only, after stopping the schedule, the isolated test
chain was advanced by 86,400 seconds and mined to obtain a new daily allowance.
This was a test-fixture operation, not an application budget-reset feature.
The approval and high-risk browser scenarios were clearly labelled fixed fixtures,
not model-generated trades. The manual and scheduled 50-unit trades used real
local Ollama inference.

## Transaction evidence

Manual AI proposal `c442a600-fac1-43d1-aa95-485625fe6724`:

```text
0x1e556c474670dbc85673e6a2c8980d72da96e986553f12090c1e6c79e9f07f0b
```

Scheduled AI proposal `2e2d71ec-9b5a-4904-a32c-636ae53d9e17`:

```text
0xb4cca8402d62a9e488b8e1fc3f3ab79c48f3f1db465f1997cf36740144a207e9
```

Owner-approved fixture `4441a5a4-4e25-4348-bfea-a9222643758c`:

```text
0x92699fc6085dc4944ed2abf70ce15582562db76c92c18c2ed56102d4be0f76be
```

These hashes refer only to the disposable local chain, not a public explorer.
Saved artifacts are under ignored `local/final-ui-verification/`: `evidence.json`,
`ui.db`, `deployment.json`, `ai-detail.jpg`, `scheduled-budget-skip.jpg`,
`frozen.jpg` and `resumed.jpg`. Preserve them separately when sharing a report.
The full-page blocked screenshot failed to capture; its UI state and backend
denial were inspected directly. No screenshot is claimed for that failed capture.

## Necessary fixes found during verification

- Resume previously left an obsolete freeze message in Latest result. The backend
  now records "Execution resumed by owner; automatic checks remain off". Added
  regression assertions for the message and absent next-check timestamp; verified
  the corrected UI after restarting the isolated API.
- Evaluation now labels its action metric as trade/no-trade agreement and explains
  that direction and amount are assessed separately. A SWAP in the wrong direction
  must not be mistaken for a correct trade just because its action agrees.

No database migration, smart-contract change or new infrastructure was needed.

## Automated verification

After the resume fix: 239 Python tests passed, 6 opt-in integrations skipped;
Ruff lint/format and strict mypy passed (51 source files). TypeScript/ESLint and
the Vite production build passed after the evaluation text change.

The previous slice separately passed the updated mocked-model/real-Anvil integration
and 14 Solidity tests, including 256 fuzz iterations. They are historical results,
not additional integrations rerun in this browser-verification turn. PostgreSQL
concurrency integrations, Docker Compose and paid OpenAI calls were not run here.

The saved 2026-10-11 Ollama benchmark remains 10/16 trade/no-trade agreements,
1/16 exact proposal matches, 11 blocked outcomes and no schema-invalid responses.
It was displayed, not rerun. These observations do not demonstrate reliable model
reasoning, profitability or measured time savings. The system remains local-only,
fixed-price, educational and unaudited.
