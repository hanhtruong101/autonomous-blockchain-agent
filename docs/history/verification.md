# Verification record

Verified locally on 20 September 2026 using Windows, Python 3.12, Node.js, Anvil/Forge 1.7.1, Solidity 0.8.28 and PostgreSQL 18.6. Compose and CI target PostgreSQL 17; the schema uses ordinary portable SQL features.

## Executed checks

- Python policy, risk, schema, API, persistence, provider, simulation and architecture tests: 91 passed. Negative cases outnumber happy paths. The default run explicitly skips three opt-in integration tests, which were also run separately.
- Strict mypy over application, tests and Python scripts: passed.
- Ruff lint and format checks: passed.
- React strict TypeScript and ESLint: passed.
- Frontend production build: passed.
- Foundry: 14 tests passed, including 256 fuzz cases for spending above the account budget.
- Fresh Anvil adapter slice: permitted 30-unit swap executed; direct 80-unit follow-up reverted on-chain.
- Complete API-to-Anvil scenarios: A executed; B/C/D blocked; medium proposal waited for approval then executed. Tested against both SQLite and real PostgreSQL with a freshly deployed chain.
- PostgreSQL transaction rollback and concurrent wallet row-lock tests: passed.
- Alembic initial migration against PostgreSQL and subsequent schema-drift check: passed.
- Browser walkthrough: owner sign-in; natural-language draft creation; review/activation; reference agent execution; transaction detail with simulation, risk and hash; medium approval queue and execution; high-risk block; chronological audit. Narrow viewport layout visually inspected.
- npm audit after the `tmp` transitive dependency override: zero reported vulnerabilities at verification time.

## Explicit limits

Docker is not installed in this environment. The full `docker compose up --build` workflow and Linux CI job are supplied but were **not executed here**. The equivalent database, chain, deployment, API and UI were run natively. The one-shot compiler's output permissions account for the [Foundry image's non-root runtime user](https://raw.githubusercontent.com/foundry-rs/foundry/v1.7.1/Dockerfile).

Dependency deprecation warnings originate from web3.py's legacy websocket import and Starlette's test-client/httpx integration; the tested HTTP RPC and API paths passed. No warnings are suppressed.

The default interpreter is offline and bounded. The optional HTTPS structured-output provider is implemented and tested with mocked transport, including refusals, incomplete responses, redirects and attempted tool calls. No live LLM provider, external wallet, public network or real asset was used. The contracts remain unaudited.

For repeatable commands and fresh-state requirements see README and docs/demo.md. Do not run both chain test suites against one already-spent deployment or point database integration tests at non-disposable data.
