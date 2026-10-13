# Controlled Autonomy

A local-only educational blockchain agent: AI interprets goals and proposes HOLD or a SWAP with assets, amount and reasoning, while deterministic policy, simulation, risk, approval and smart-account controls decide whether they execute. All assets are fake. No real wallet, real ETH or real USDC is required. These contracts are unaudited and are not a production trading wallet.

## Architecture

A modular monolith keeps the agent, policy rules, simulation, risk, approvals and execution separate. Natural language creates a typed draft; only owner approval activates a version. A portfolio agent proposes a typed swap. Policy violations, failed simulation and high risk block execution; medium risk requires approval of the exact proposal; low risk may execute automatically. Execution rechecks current policy and simulation. The smart account independently enforces allowed targets, daily spending, pause/revoke and replay protection.

- `apps/api`: FastAPI, Pydantic, SQLAlchemy, deterministic safety pipeline.
- `apps/web`: React, TypeScript, Vite and TanStack Query.
- `contracts`: MockUSDC, MockDex and PolicySmartAccount.
- `packages/shared-types`: frontend API contracts.
- `scripts`, `infra`, `docs`: deployment, containers and documentation.

## Docker Compose

With Docker available, set `AUTONOMY_OWNER_TOKEN` to a random value of at least 24 characters, then run `docker compose up --build`. Open http://localhost:5173 and use that token. Compose starts PostgreSQL and Anvil, compiles/deploys contracts, applies migrations and starts API/web. The demo chain and database are ephemeral. Never expose the unlocked Anvil RPC publicly. See `.env.example` for configuration; no `.env` file is supplied or required.

## Native Windows startup

Run every terminal from `D:\autonomous-blockchain-agent`. Install Python 3.12+, uv, Node.js 22+ and PostgreSQL. Create the `autonomy` database first. One-time setup:

```powershell
uv sync --frozen
npm ci --ignore-scripts
npm run contracts:build
```

Terminal 1 — keep a fresh local chain running:

```powershell
.\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe --chain-id 31337 --host 127.0.0.1
```

Terminal 2 — deploy, migrate, then start the API:

```powershell
$env:AUTONOMY_OWNER_TOKEN = [guid]::NewGuid().ToString('N')
$env:AUTONOMY_OWNER_TOKEN | Set-Clipboard
$env:AUTONOMY_DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/autonomy"
$env:AUTONOMY_AI_PROVIDER = "offline"
uv run python scripts/deploy.py
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Terminal 3:

```powershell
npm run web:dev
```

Open http://localhost:5173 and paste the owner token. On other platforms use `anvil` and `forge build --root contracts` from your Foundry installation. The npm Foundry wrappers have a Windows postinstall incompatibility; `--ignore-scripts` avoids it. The optional platform executables are under `node_modules/@foundry-rs/`. `npm run contracts:build` uses pinned solc-js.

The sequence is **Anvil → deploy.py → Alembic → FastAPI → React**. Deployment writes public addresses to `local/deployment.json` (or `AUTONOMY_DEPLOYMENT_PATH`). It seeds 1,000 TestUSDC and fake ETH in the account and 10,000 of each token in MockDex. Both tokens have six decimals and a fixed 1:1 price. Account A is owner, B is agent, C is recipient. Anvil's unlocked accounts are public development identities, unsafe anywhere outside this demo.

**Missing local deployment; execution disabled:** start Anvil, run `uv run python scripts/deploy.py`, verify `Test-Path local/deployment.json`, then restart FastAPI. A JSON file left over from a previous Anvil process does not restore contracts: redeploy after restarting the chain. Deployment requires a fresh chain. Use a fresh matching demo database when starting a fresh chain. The API never deploys contracts automatically and rejects every chain except local Anvil 31337, including mainnet and Sepolia.

## Local Ollama (no API key or hosted API charges)

The Ollama desktop app must be running on localhost:11434. Check installed models with `ollama list`. This machine has `llama3:latest`. In the existing backend PowerShell terminal, stop the API with Ctrl+C, then:

```powershell
$env:AUTONOMY_AI_PROVIDER = "ollama"
$env:AUTONOMY_AI_MODEL = "llama3:latest"
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Keep your existing owner token, database settings and Anvil process. No redeployment is needed. No OPENAI_API_KEY is needed or sent. Refresh the UI and confirm **Ollama (local)**. Create/review/approve a policy, then use the portfolio run. Both generation steps call local Ollama; fixture scenarios stay deterministic.

This integration uses the native `/api/chat` JSON-schema format, no tools, no redirects and no automatic retries. All output passes the same Pydantic and execution pipeline checks. Requests allow up to 180 seconds for local loading/inference. Model quality varies: review cadence and amounts carefully; a valid HOLD response can produce no proposal. Missing models, malformed responses and timeouts fail closed. The local endpoint is deliberately fixed to loopback. Run the backend natively for this mode: a Docker API container's loopback cannot reach Windows Ollama. Do not change the blockchain RPC to reach Ollama.

## OpenAI or offline mode

Offline is the default, requires no API key and uses the displayed sentence template. Both policy drafting and portfolio proposals switch together. To select OpenAI explicitly, create a key in your own OpenAI API account and set these in Terminal 2 **before starting/restarting the backend**:

```powershell
$env:OPENAI_API_KEY = "YOUR_KEY"
$env:AUTONOMY_AI_PROVIDER = "openai"
$env:AUTONOMY_AI_MODEL = "gpt-6-luna"
uv run uvicorn app.main:app --app-dir apps/api --reload
```

OpenAI mode makes paid requests only when you create a draft or request a portfolio run. The project never retrieves or generates your key. Only `OPENAI_API_KEY` supplies it; old `AUTONOMY_LLM_*` / `AUTONOMY_INTERPRETER` settings are no longer used. Missing keys fail startup in OpenAI mode. Provider failures never trigger an executing fallback. To deliberately return offline:

```powershell
$env:AUTONOMY_AI_PROVIDER = "offline"
```

Restart the backend and check the mode indicator. The configured default is `gpt-6-luna`; availability depends on your account. See [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs). The SDK uses Responses with no transaction tools. See [AI integration and verification](docs/ai-integration.md) for UI steps and blockchain checks.

## Verification

```powershell
uv run pytest -q
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
uv run mypy apps/api/app scripts/deploy.py
npm run web:check
npm run web:build
forge test --root contracts --chain-id 31337
```

Windows Forge alternative: `.\node_modules\@foundry-rs\forge-win32-amd64\bin\forge.exe test --root contracts --chain-id 31337`.

Normal tests mock OpenAI and use SQLite/fake blockchain adapters. Set `TEST_POSTGRES_URL` to an isolated PostgreSQL database for locking tests. `RUN_ANVIL_TESTS=1`, `RUN_ANVIL_E2E=1` and `RUN_AI_ANVIL=1` enable the adapter, offline API, and mocked-AI/real-chain suites respectively. **Each suite needs a fresh deployment; run them separately.** `TEST_ANVIL_RPC` and `TEST_DEPLOYMENT_PATH` let tests use an isolated local node. The AI suite also uses PostgreSQL when configured. Skipped integrations are not passed tests.

## Demo and limitations

For fixed educational scenarios, review/approve a 100-unit daily and 100-unit per-trade on-demand policy. Run scenario A (30 executes), B (80 more blocks), C (unknown target blocks), D (abnormal slippage blocks), then medium (70 requires approval). `testBypassDailyLimit` bypasses Python and proves the contract still rejects overspending. These buttons are fixed fixtures, independent of AI mode. Use the portfolio check for actual AI trade proposals and independent safety checks. Fixed scenarios live under the collapsed Educational safety scenarios section. See [demo](docs/demo.md) and [AI integration](docs/ai-integration.md).

Single local owner/wallet, fixed mock prices, no market oracle, public chain or production mode. Policy changes do not automatically rewrite the independent on-chain 100-unit ceiling. Uncertain RPC submissions freeze the wallet until reconciliation and are never blindly retried. Audit data is append-only through the app, not tamper-proof against database administrators. Live OpenAI and Docker verification limitations are recorded in the [AI integration report](docs/ai-integration.md).

Read [architecture](docs/architecture.md), [policy model](docs/policy-model.md), [threat model](docs/threat-model.md), [implementation plan](docs/implementation-plan.md) and [earlier verification](docs/verification.md).

## Automatic portfolio checks

Existing installations: stop FastAPI, run `uv run alembic upgrade head` from the repository root using your existing `AUTONOMY_DATABASE_URL`, then restart FastAPI and the frontend. Migration 0002 adds scheduling and execution-freeze state; no contract redeployment is needed. Do not reset your chain or database just for this update.

1. Create and approve an **on demand** policy for a quick demonstration (weekly policies still enforce a week between completed trades).
2. Open **Agent activity → Automatic portfolio checks**. Select 30 seconds for the local demonstration and click **Enable for approved policy**. This is separate from approving the policy; schedules default to off.
3. Leave FastAPI running. The worker checks due schedules roughly every five seconds. It asks the configured provider, including Ollama, to propose HOLD or a typed SWAP for eligible snapshots. The model chooses direction, amount and slippage; independent checks may block its proposal. You no longer need to click demo scenarios A–D to perform ordinary portfolio checks.
4. Watch last/next check and latest result, then open **Proposals & outcomes** for policy, simulation, risk, approvals and transaction hashes. Those results refresh every five seconds. Medium risk waits in the approval queue; it never receives automatic owner approval.
5. Use **Stop automatic checks** to stop scheduling, or **Emergency freeze** to block execution, cancel unsubmitted proposals and request an owner-authorized on-chain pause. **Owner: resume execution** unpauses but leaves scheduling off.

The new-policy form defaults to 100 basis points (one percentage point): a 70% USDC target accepts 69–71%. Existing policies retain their approved tolerance; legacy stored drafts without the field retain the original 500-bps interpretation. The policy review shows the tolerance before activation. A deterministic integer-only check blocks swaps that do not strictly improve the target allocation, using simulated token changes. These calculations apply only to the equal-price, six-decimal mock assets.

The check interval is **not** permission to ignore policy cadence or spending limits. New UI drafts suggest a 30-unit per-trade ceiling, which the owner reviews; the agent may need multiple permitted checks/days to reach a target. A scheduled check skips the model when within tolerance, out of budget, before the rebalance interval, or waiting for approval. No eligible calculated trade means no model call. Invalid AI decision output never triggers fallback execution. Three consecutive failed/blocked checks freeze execution. An unresolved submission stops scheduling immediately and retains the wallet reservation; inspect/reconcile before resuming.

Schedules bind the approved policy version. Approving a replacement stops scheduling and cancels stale pending proposals; enable the new version explicitly. Scheduling uses backend UTC time; budgets/cadence use chain timestamps. Anvil time progresses with blocks, so testing a new day/week requires advancing **only your disposable test chain**. The worker runs inside FastAPI, without an external queue, and does not run while the backend is stopped. Durable in-progress claims are not automatically replayed after a crash: freeze, inspect the audit/chain, and resume explicitly. A submitted transaction cannot be cancelled by stop/freeze. Owner pause RPC failure leaves local execution frozen and is audited.

`AUTONOMY_AUTOMATION_WORKER=false` disables background polling (normal tests use this). It does not silently revoke an already enabled schedule; use Stop first. Restarting with the worker available resumes enabled, unclaimed schedules. All owner control endpoints require the same owner bearer token. Local Anvil owner accounts are unlocked development identities; this control mechanism is not suitable for a real wallet.


## Clear boundaries and AI trade proposals

This update needs no new migration beyond `alembic upgrade head` for the existing schema. Restart the API and frontend. Existing approved versions are not rewritten, and automation is never enabled by the update.

- **Create policy:** enter the goal, select an explicit tolerance, optional hard minimum USDC share, and maximum trade amount. These settings are included in the draft and require owner approval. Daily spending remains capped at 100 test units. A minimum expressed in the goal cannot be weakened by a smaller form minimum.
- **Policy review:** see percentages, the accepted target range, hard minimum, daily/per-trade ceilings and time between completed trades. The check frequency is separate. A hard minimum is enforced from simulated post-trade balances. If the wallet starts below that minimum and cannot reach it in a single permitted trade, the system takes no action and explains why. This off-chain allocation rule is not an additional on-chain contract guarantee.
- **Live portfolio checks:** Ollama/OpenAI proposes assets, integer amount, slippage and a reason, or HOLD. The backend preserves the proposed amount and supplies only trusted local addresses/operations. Deterministic policy, simulated allocation checks, risk, approvals and the smart account control execution. Invalid output fails closed with no fallback. Offline mode uses exact integer sizing as a reference.
- **Overview / Agent activity:** readiness explains cadence, exhausted budget, pending approvals, generation time and recovery steps. Pending items link directly to their proposal. Manual and automatic checks share the same readiness logic.
- **Evaluation:** inspect 16 read-only synthetic cases, including small swaps, reverse swaps, hard minimums, budget exhaustion and simulation failure. The optional model report is observation only; no benchmark can submit a transaction.

Run startup diagnostics from the project root: `uv run python scripts/check_local.py`. It checks reachable local services without printing credentials. Socket reachability does not prove database authentication or migrations are correct.

Run the exact baseline: `uv run python scripts/evaluate_agent.py`. To compare an installed local model, run `uv run python scripts/evaluate_agent.py --ollama-model llama3:latest` (optionally `--limit 4` for a short subset), then refresh **Evaluation**. JSON reports are stored under `local/evaluation/`. The model report is `local/evaluation/ollama_trades.json`. Evaluation separates action agreement, proposal matches against a reference and hypothetical safety outcomes. A different permitted amount is not automatically unsafe. These measurements do not prove real-world time savings; see [evaluation method](docs/evaluation.md).

See the [current verification report](docs/verification-ai-trades.md) for test results, actual Ollama/browser evidence and unverified environments.

## AI treasury workflow

See the [current workflow and verification guide](docs/treasury-agent.md) for the
AI trade-proposal update and exact testing steps.

AI mode is a goal-based treasury agent, not a price prediction bot. After deterministic
preflight allows observation, the model may choose HOLD or propose a SWAP. HOLD never
creates a transaction. For SWAP, the model supplies direction and amount;
policy, simulation, risk, approval and the smart account independently govern
execution. Offline mode remains explicitly deterministic.

In **Agent activity → Check history**, follow observation → AI decision → proposed
trade → safety checks → result. System skips (cadence/budget/tolerance), AI HOLD,
generation failures and transactions are distinct. Three consecutive AI HOLDs in
the visible history produce an advisory to inspect the reasons, not a permission
bypass or automatic switch to another strategy. Every history item links to its
policy and, when present, its proposal with the current execution/approval status.

The authenticated `GET /agent/activity` reads the latest 50 check snapshots from the
existing audit store. Detailed history begins with this update; earlier events remain
in Audit log. No new migration or contract deployment is needed. Restart the API
and frontend; existing policies and separately authorized schedules retain their
settings. Stop an enabled schedule before restarting if you want to review behavior
first. Model HOLD can delay progress even when a trade is permitted.
