# Controlled autonomy project

Educational, local-only policy-controlled blockchain automation. Preserve clarity, deterministic behavior and independent security boundaries.

## Invariants

- AI cannot activate policies, authorize execution, access the signer or directly execute transactions.
- Live AI proposes HOLD or a typed SWAP with assets, integer amount, slippage and reason. Preserve its proposed amount; independent policy/simulation/risk gates decide permission. Only trusted code supplies chain, addresses and operation. No executable fallback on model failure.
- Distinguish system skips from AI HOLD in audit/UI history. Repeated HOLD is an advisory, never an automatic execution fallback.
- Policy and risk engines are deterministic and do not depend on the LLM.
- Policy changes create new immutable versions and require explicit owner approval.
- Simulation happens before execution and again after an owner approval.
- High risk, policy failure, invalid approvals and simulation failure never execute.
- Mainnet execution is prohibited. Only local Anvil chain 31337 is supported.
- Financial values never use float arithmetic. Policies use Decimal strings; tokens use integer units.
- Never commit or log private keys, seed phrases, owner tokens or provider secrets. `.env` is ignored.
- Only the owner changes smart-account restrictions. Agent calls cannot loosen policy.
- No arbitrary transaction/calldata endpoint. Execute validated stored TransactionProposal objects only.
- Approval binds the complete proposal digest and active version. Recheck budget and state before signing.
- Do not automatically retry unknown RPC submission outcomes. Preserve wallet reservation until reconciled.

## Boundaries

`schemas` is infrastructure-free. `policies/rules` is independent of interpreter, risk and blockchain. `agent` only proposes. `simulation` uses a replaceable adapter. `risk` produces findings; `execution` coordinates policy, simulation, risk and approvals. `blockchain` maps narrow typed operations to contracts. `db` and `models` own persistence, `audit` records all material decisions. API and UI are presentation boundaries.

## Commands

```sh
uv sync --frozen
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
uv run mypy apps/api/app scripts/deploy.py
uv run pytest -q
npm ci --ignore-scripts
npm run web:check
npm run web:build
forge test --root contracts --chain-id 31337
```

For a full local stack, set `AUTONOMY_OWNER_TOKEN` (24+ characters), then `docker compose up --build`. See README for individual-service development. Integration tests require explicitly enabled fresh local chain fixtures; PostgreSQL locking tests need `TEST_POSTGRES_URL` pointing to an isolated test database. Never label skipped integrations as passed.

## Conventions

Python 3.12, Pydantic v2 immutable boundary models, SQLAlchemy 2 explicit transaction scope, strict mypy, Ruff. Keep rules and application use cases small. Freeze Alembic migration schemas; do not import live ORM metadata in historical revisions. React strict TypeScript, no `any`, typed API results, integer-safe financial display. Solidity custom errors, events, checks-effects-interactions and explicit permissions.

Test denials more extensively than happy paths. Add cases for changed permissions, stale approvals, concurrent submissions and RPC ambiguity when modifying execution. Run lint, types and relevant tests after each slice. Document unverified environments candidly. These contracts are educational and unaudited; never present them as a production wallet.

Scheduling invariants: owner enables schedules separately for an approved version; version changes stop them. Keep model calls outside wallet locks using a durable generation reservation. Check the unique schedule claim again under the coordinator wallet lock before committing a submission intent. Never replay interrupted claims automatically. Freeze invalidates claims and pending proposals, persists local denial even if owner RPC fails, and requests the independent on-chain pause. Resume is owner-only and leaves scheduling off. Allocation checks must use simulated deltas and integer ratios; the mock valuation is valid only for the fixed-price six-decimal test assets.
