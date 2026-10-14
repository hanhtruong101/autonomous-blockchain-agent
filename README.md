# Controlled Autonomy

An educational AI treasury agent running entirely on local Anvil (chain 31337).
Ollama interprets goals and proposes HOLD or a typed swap. Independent policy,
simulation, risk, approval and smart-account checks govern execution. No real
wallet or cryptocurrency is needed. These contracts are educational and unaudited.

## Architecture

- `apps/api`: FastAPI modular monolith; agent, deterministic controls and persistence.
- `apps/web`: React, TypeScript, Vite and TanStack Query.
- `contracts`: MockUSDC, MockDex and PolicySmartAccount.
- `packages/shared-types`: typed frontend API contracts.
- `scripts`, `infra`, `docs`: local deployment, containers and documentation.

Only local chain 31337 is supported. Both mock tokens have six decimals and fixed
1:1 value. Fresh deployment seeds **500 TestUSDC + 500 TestWETH** in the smart
account, fake ETH, and 10,000 of each token in MockDex. The independent on-chain
spending ceiling is 100 test units per UTC chain day, shared by both swap directions.

## Native Windows startup with Ollama

Install Python 3.12+, uv, Node.js 22+, PostgreSQL and Ollama. Create a PostgreSQL
database named `autonomy`. Run each terminal from the project root (for example
`D:\autonomous-blockchain-agent`). One-time setup:

```powershell
uv sync --frozen
npm ci --ignore-scripts
npm run contracts:build
ollama pull llama3:latest
```

Start the Ollama desktop app. Alternatively run `ollama serve` in a separate
terminal if it is not already serving. `ollama list` shows installed model names.
Ollama must be reachable at localhost:11434. Local inference needs no API key.

**Terminal 1 — Anvil:**

```powershell
.\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe --chain-id 31337 --host 127.0.0.1
```

**Terminal 2 — deploy, migrate and start FastAPI with Ollama:**

```powershell
$env:AUTONOMY_OWNER_TOKEN = [guid]::NewGuid().ToString('N')
$env:AUTONOMY_OWNER_TOKEN | Set-Clipboard
$env:AUTONOMY_DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/autonomy"
$env:AUTONOMY_AI_PROVIDER = "ollama"
$env:AUTONOMY_AI_MODEL = "llama3:latest"
uv run python scripts/deploy.py
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Replace the database credentials and model name as appropriate. Paste the copied
owner token into the app; it authenticates this local owner session.

**Terminal 3 — React:**

```powershell
npm run web:dev
```

Open http://localhost:5173. Keep all services running. On other platforms, use
`anvil` and `forge build --root contracts` from Foundry. The npm Windows wrappers
have a postinstall incompatibility; `--ignore-scripts` avoids it.

Deployment requires a fresh chain and writes public addresses to
`local/deployment.json`. Restarting only FastAPI does not require redeployment.
If Anvil is reset, use a fresh matching demo database and deploy again; an old
JSON file cannot restore contracts. Never expose unlocked Anvil RPC publicly.
Its development identities are public and unsafe outside this sandbox.

## First AI workflow

1. Create a policy: “Keep approximately 55% of my portfolio in USDC, never spend
   more than 100 USDC per day, rebalance on demand, and only interact with approved protocols.”
2. Expand **Advanced settings**: choose Exact target, leave minimum USDC blank,
   and use a maximum trade of 30. Review the draft, then approve explicitly.
3. Open **Agent activity**, choose **Run portfolio check**. From 500/500, the
   direction toward 55% USDC is WETH → USDC. AI may propose a smaller amount or HOLD;
   invalid output never receives an executable fallback.
4. Inspect **Proposals & outcomes**, transaction detail and **Audit log**.
   Low risk may execute; medium risk waits in **Approval queue**; violations,
   high risk and failed simulation block.
5. To automate, select 30 seconds under **Automatic portfolio checks** and enable
   it for the approved policy. Stop or Emergency freeze remains available.

For an exact offline baseline and the A–E safety demonstration, see [demo](docs/demo.md).
The 30-second schedule checks eligibility; it does not override policy cadence.
The model is skipped inside tolerance, at exhausted budget, before the interval,
or when pending work or a hard minimum prevents trading. Scheduling uses backend
UTC time; budgets use chain time. Anvil time advances with blocks.

Policy replacements require approval and stop the old schedule. Freeze cancels
unsubmitted work, persists local denial and requests the independent on-chain pause.
Resume leaves scheduling off. Unknown submission outcomes and interrupted schedule
claims are not replayed automatically; inspect audit/chain evidence before recovery.

## Switch to offline mode

Stop FastAPI with Ctrl+C in Terminal 2, then run:

```powershell
$env:AUTONOMY_AI_PROVIDER = "offline"
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Keep the database, owner token and Anvil settings. Offline mode uses the documented
sentence template and deterministic integer sizing; it does not call a model.
To return to Ollama, set `AUTONOMY_AI_PROVIDER` to `ollama` and restart FastAPI.

## Optional OpenAI provider

In Terminal 2, stop FastAPI, set `AUTONOMY_AI_PROVIDER` to `openai`, set
`OPENAI_API_KEY` and `AUTONOMY_AI_MODEL` to a model available to your account,
then restart FastAPI. Hosted requests may incur API charges for policy drafts
and eligible manual or scheduled checks. Missing required credentials fail startup.
Never commit secrets. `.env.example` lists settings; `.env` is ignored.

## Docker Compose

Set `AUTONOMY_OWNER_TOKEN` to a random value of at least 24 characters, then run
`docker compose up --build`. Compose starts PostgreSQL, Anvil, deployment,
migrations, API and web. Its default is offline and its database/chain are ephemeral.
Use native startup for desktop Ollama: container loopback does not reach the host's
Ollama service. Never change the blockchain RPC to reach Ollama.

## Verification

```powershell
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
uv run mypy apps/api/app scripts/deploy.py
uv run pytest -q
npm run web:check
npm run web:build
forge test --root contracts --chain-id 31337
```

Windows Forge alternative: `.\node_modules\@foundry-rs\forge-win32-amd64\bin\forge.exe`.
Run `uv run python scripts/check_local.py` for non-secret startup diagnostics.
Normal tests use mocked providers and chain adapters. Opt-in real-chain suites
require separate fresh deployments: `RUN_ANVIL_TESTS=1`, `RUN_ANVIL_E2E=1`,
`RUN_AI_ANVIL=1`, or `RUN_AUTOMATION_ANVIL=1`. Set `TEST_ANVIL_RPC` and
`TEST_DEPLOYMENT_PATH` to isolated fixtures. PostgreSQL locking tests require
`TEST_POSTGRES_URL` pointing to an isolated test database. Skipped tests are not passes.

## Documentation and limitations

- [Architecture](docs/architecture.md) and [policy model](docs/policy-model.md)
- [Threat model](docs/threat-model.md) and [implementation plan](docs/implementation-plan.md)
- [Workflow](docs/treasury-agent.md) and [demo](docs/demo.md)
- [Historical verification](docs/history/README.md)

Single owner/wallet, fixed mock prices, no market oracle, real funds or public-chain
execution. AI reasoning and time savings are not proven. Audit records are append-only
through the application but not tamper-proof against database administrators.
Allocation constraints are off-chain checks; the smart account independently enforces
its narrower permissions. A target is not a guaranteed floor. Hard minimums can prevent
partial progress when one permitted trade cannot restore the minimum.
