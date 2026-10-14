# AI integration and verification — 2026-10-04

> Historical integration report. The current live workflow uses typed AI trade
> proposals with independently validated amounts. The old portfolio mode selector
> is absent. Use **Agent activity / Run portfolio check** and the current
> [workflow guide](../treasury-agent.md). Fixed scenarios remain educational fixtures.

## Startup repair

`AUTONOMY_DEPLOYMENT_PATH` defaults to `local/deployment.json`, relative to the project root. `scripts/deploy.py` explicitly writes it after successful deployment/seeding. The reported `Missing local deployment; execution disabled` message came from finding no bytecode at an address in that file. This commonly occurs after restarting ephemeral Anvil while retaining the old file. A missing file is a separate case; both now explain how to recover. Neither case enables execution or deploys automatically.

Use the three-terminal commands in [README](../../README.md): start Anvil, deploy contracts, migrate PostgreSQL, start API, then React. Compile first with `npm run contracts:build`. Verify `Test-Path local/deployment.json`. Deployment requires a fresh local Anvil chain and rejects nonlocal RPC endpoints before connecting. A new chain should use a matching fresh demo database. Never clear a working demo silently.

## Important changes

- `apps/api/app/blockchain/adapter.py`: actionable missing-file and missing-bytecode errors; guard stays enforced.
- `scripts/deploy.py`: retains explicit seeding/output and adds a local RPC URL guard.
- `apps/api/app/config/settings.py`: offline/OpenAI provider selection, configurable `gpt-6-luna`, `OPENAI_API_KEY` as the only key source, missing-key startup rejection.
- `apps/api/app/policies/providers.py`: repairs the existing adapter using OpenAI Python SDK Responses, strict JSON schema, no tools, no automatic retries/redirects, sanitized failures.
- `apps/api/app/schemas/ai.py`: address-free policy/proposal intent types and safe generation metadata.
- `apps/api/app/policies/interpreter.py`: validates policy intent and resolves the deployed allowlist into the existing PolicyDraft.
- `apps/api/app/agent/portfolio.py`: controlled snapshot, validated AI intent, trusted mapping to TransactionProposal; deterministic proposer retained.
- `apps/api/app/execution/agent_runs.py`: injected proposer; explicit scenarios remain fixtures; source recorded in audit.
- `apps/api/app/api/application.py`: selects both generators, records safe generation failures, exposes mode, preserves execution gates.
- `apps/api/app/api/queries.py`, `schemas/responses.py`: expose stored generation metadata with proposal details. No database migration.
- `apps/web/src/main.tsx`, `features/detail.tsx`, `packages/shared-types/index.ts`: small mode/usage/safety guide and provider/model/final decision display.
- `.env.example`, `compose.yaml`, `pyproject.toml`, `uv.lock`: new configuration and locked SDK dependencies (OpenAI 3.24.0 uses httpx2).
- `apps/api/tests/test_provider.py`, `test_startup.py`, `test_ai_anvil.py`, `test_boundaries.py`, `conftest.py`: integration/negative tests, isolated test environment; existing chain tests accept an isolated local RPC/path.
- README, architecture, policy model and implementation plan: updated operation and boundaries.

Contracts, deterministic policy/risk rules, signing coordinator, approval validation and persistence schema are unchanged.

## Architecture and configuration

Natural-language goal → Responses structured intent → Pydantic validation → existing PolicyDraft → owner review/approval → active immutable PolicyVersion.

Controlled portfolio snapshot → OpenAI proposal intent → existing TransactionProposal → deterministic policy → RPC simulation → deterministic risk → decision/approval → execution coordinator rechecks → trusted adapter → PolicySmartAccount → MockDex on Anvil.

Only the backend supplies chain, addresses, operation and calldata. Unknown protocols/actions, malformed values and extra operational fields are rejected. Provider output never grants permissions. Financial quantities remain Decimal strings/integer token units. Error responses do not trigger automatic fallback. The suggested 30-token proposal size is prompt guidance; authoritative budget/slippage/identity limits remain deterministic policy and contract checks.

Offline:

```powershell
$env:AUTONOMY_AI_PROVIDER = "offline"
uv run uvicorn app.main:app --app-dir apps/api --reload
```

OpenAI (user supplies their own key, in the same backend terminal):

```powershell
$env:OPENAI_API_KEY = "YOUR_KEY"
$env:AUTONOMY_AI_PROVIDER = "openai"
$env:AUTONOMY_AI_MODEL = "gpt-6-luna"
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Restart after changing environment variables. There is no key entry in the frontend or database. `.env.example` contains placeholders only. Offline requires no key and sends nothing to OpenAI. Account/model availability is checked by the actual request and errors fail closed. References: [model](https://developers.openai.com/api/docs/models/gpt-6-luna), [structured output](https://developers.openai.com/api/docs/guides/structured-outputs).

## UI walkthrough

1. Follow README to start a fresh local stack. Open http://localhost:5173 and enter the local owner token.
2. Confirm the mode indicator. In OpenAI mode it shows the configured model; requests may incur API charges.
3. Open **Create policy**. Enter “Keep about 70% in USDC, cap daily spending at 100 USDC, rebalance on demand, and use only MockDex with USDC/WETH and at most 1% slippage.” Offline mode requires the displayed exact template instead.
4. Create the draft. Inspect target, daily amount, cadence, contract and slippage. Confirm it remains DRAFT until you explicitly approve.
5. Approve the policy. Open **Agent activity** and select the portfolio run. This uses the selected provider; scenario buttons are deterministic fixtures.
6. Open the proposal detail. Inspect source/model, amount/assets/reason, every policy check, simulation, risk findings, final decision and hash.
7. A low-risk permitted action executes. A medium-risk action appears in **Approval queue** and executes only after approval of that exact proposal and fresh checks. A refusal/error creates no fallback proposal/transaction.
8. Open **Audit log** for generation metadata, checks, approval and execution history.

For a predictable medium-risk demo, use the fixed medium scenario after scenario A under the 100-unit on-demand policy: 30 spent plus 70 proposed, awaiting approval. For an AI-driven medium case on a fresh deployment/day, review a policy with a 30-unit daily budget; a model proposal of 21–30 units triggers medium risk. Model decisions are variable; mocks make safety tests reproducible.

## Verify a real local transaction

Copy the transaction hash from Transaction detail or TRANSACTION_SUBMITTED audit event. Match it to Anvil's transaction output (run without `--silent`). If Cast is installed:

```powershell
cast receipt TRANSACTION_HASH --rpc-url http://127.0.0.1:8545
```

Confirm receipt status 1 and the account/token event logs. Refresh Overview: a 30 TestUSDC swap on a fresh account changes balances from 1000/0 to 970/30 TestUSDC/TestWETH. Approving the later 70 changes them to 900/100. PostgreSQL records can be checked without exposing secrets:

```sql
SELECT proposal_id, status, transaction_hash FROM execution_records ORDER BY created_at;
SELECT event, entity_id, created_at FROM audit_events ORDER BY id;
```

Blocked or invalid proposals must create no execution record/hash. The integration test additionally checks that the agent's chain nonce does not change, proving no submission occurred.

## Safety tests

`test_provider.py` mocks the SDK transport: valid policy/proposal, invalid schema, unknown protocol/action, injected address/chain fields, malformed amount, excessive spending, high slippage, failed simulation, medium approval, missing key, network/timeout/auth/model errors, refusal/tool/incomplete/multiple responses, no automatic retry/fallback and fixture independence.

`test_startup.py` covers missing files and stale deployment bytecode. Existing tests still cover policy approval, expiry/digest changes, concurrent submission, wrong chain, uncertain outcomes and replay. `testBypassDailyLimit` bypasses off-chain policy and expects a Solidity revert. The Anvil adapter integration also directly submits an over-budget operation and verifies a revert.

## Checks executed

This machine has uv inside `.venv`; the exact Python runner was `.venv\Scripts\python.exe -m` (equivalent project environment to `uv run`).

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | 114 passed, 4 opt-in integrations skipped |
| `.venv\Scripts\python.exe -m ruff check apps/api scripts` | Passed |
| `.venv\Scripts\python.exe -m ruff format --check apps/api scripts` | Passed, 57 files |
| `.venv\Scripts\python.exe -m mypy apps/api/app scripts/deploy.py` | Passed, 39 source files |
| `npm run web:check` | Passed TypeScript and ESLint |
| `npm run web:build` | Passed |
| `node_modules\@foundry-rs\forge-win32-amd64\bin\forge.exe test --root contracts --chain-id 31337` | 14 passed, including 256 fuzz runs |
| `.venv\Scripts\python.exe -m alembic upgrade head` | Passed on isolated PostgreSQL database |
| `.venv\Scripts\python.exe -m pytest apps/api/tests/test_database.py -q` | 2 passed with TEST_POSTGRES_URL, including concurrent locking |
| `.venv\Scripts\python.exe -m pytest apps/api/tests/test_ai_anvil.py -q -s` | Passed separately with SQLite and PostgreSQL, RUN_AI_ANVIL=1 |
| `.venv\Scripts\python.exe -m pytest apps/api/tests/test_chain.py -q` | Passed, RUN_ANVIL_TESTS=1 |
| `.venv\Scripts\python.exe -m pytest apps/api/tests/test_e2e_anvil.py -q` | Passed, RUN_ANVIL_E2E=1 |

Chain runs each used a fresh explicit deployment on an isolated Anvil at `http://127.0.0.1:18545`, path `local/ai-verification/deployment.json`. PostgreSQL ran on localhost:55432 in the project test cluster, database `autonomy_ai_verification`. The user's default port 8545/deployment file was not reset or replaced. Forge required execution outside the sandbox due to a Windows compiler-cache/home discovery error.

PostgreSQL-backed mocked-AI evidence (ephemeral chain snapshots, not reusable hashes):

- Low-risk execution: `0xbfb93811872ee483604591728aa91c38e30fd8e5bf2e93b367da7d3a4aa32861`, successful receipt with 5 logs.
- Then 80 more units, unknown protocol and 2000 bps slippage: blocked/rejected; agent nonce stayed 1; no execution record for these requests.
- Medium 70 units waited for approval, then executed: `0xac8afe16b2a2f66b7768f60698b072e07bb05cc963000a68896438e4d350f95c`.
- Final balances: 900,000,000 USDC units / 100,000,000 WETH units; exactly 2 execution records.

## Remaining limitations

No live paid OpenAI call was attempted, and no key was searched for or retrieved. SDK transport mocks verify integration shape and failure behavior, not account access or model quality. Docker was unavailable and Compose was not run. Frontend type/lint/build checks passed; no new browser interaction test was performed. Dependency deprecation warnings remain (websockets/Starlette). This is a single-owner, fixed-price, educational local prototype, not an audited production trading wallet. On-chain controls limit a compromised backend but cannot enforce every off-chain policy. Audit rows are not tamper-proof against a database administrator.

## Ollama addition (2026-10-07)

Native API mode now supports `AUTONOMY_AI_PROVIDER=ollama` with an explicitly configured installed model in `AUTONOMY_AI_MODEL`. No API key is needed. The native adapter calls only loopback port 11434, sends JSON schema with no tools or authorization header, refuses redirects, bounds response size and rejects incomplete/tool outputs. Local inference gets a 180-second timeout; errors never fall back to execution. Docker-host Ollama routing is not included; use the native backend documented in README.

The existing installed `llama3:latest` was tested live with fake portfolio input, without blockchain execution. Initial attempts misinterpreted cadence or units and one was rejected by Pydantic. Task-specific instructions/examples resolved the tested request: a validated 70/30 policy, 100-token budget, zero-hour cadence, 100 bps slippage, followed by a validated 30-token USDC-to-WETH proposal. This is one successful example, not a guarantee of model interpretation. Always review policies.

Verification: 157 Python tests passed, 4 optional integrations skipped; Ruff, mypy, frontend TypeScript/ESLint and production build passed. Mocked Ollama transport covers missing model, connection/timeout, malformed/oversized response, redirects, incomplete results and tool output. The shared API pipeline tests run for both OpenAI and Ollama mode, including blocked and medium-risk cases. No paid API requests or new model downloads were used. Contracts and execution safeguards were unchanged; chain integrations were not rerun for this transport addition.
