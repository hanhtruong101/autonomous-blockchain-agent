# Implementation plan

## AI trade proposals (2026-10-11, current direction)

1. Let the configured model propose HOLD or a typed SWAP, including assets,
   integer amount, slippage and reasoning. Trusted mapping supplies the local
   chain, wallet and deployed contract; the model never receives signing authority.
2. Preserve model amounts instead of replacing them with reference calculations.
   Keep readiness checks, deterministic policy and allocation checks, simulation,
   risk tiers, approval binding, concurrency guards and on-chain restrictions.
3. Show AI proposals and outcomes consistently in activity, details and history.
   Preserve historical bounded-decision records and label their benchmark separately.
4. Verify accepted variable amounts, rejected unsafe proposals, HOLD, invalid output,
   approval, scheduling and cancellation. Run backend and frontend quality checks.

The earlier HOLD/REBALANCE-only phase below is historical. The fixed-price local
assets, 100 test-USDC daily ceiling and lack of price prediction remain deliberate
prototype limitations. Model mistakes can cause a block or HOLD; never substitute
an executable fallback when generation fails.

## Bounded AI treasury decisions (2026-10-11)

1. Replace explanation-only live generation with validated HOLD/REBALANCE intent.
   The model observes an address-free snapshot and approved policy, never supplies
   amounts or permissions. Deterministic sizing and all execution gates remain.
2. Record typed activity snapshots in the existing audit store, including system
   skips, AI holds, failures and proposals. Expose a bounded authenticated history
   with current proposal outcomes and a repeated-HOLD advisory; no schema migration.
3. Connect activity history to policy/proposal review in the UI and label observation,
   AI decision, calculated plan, safety checks and result separately.
4. Separate decision agreement, deterministic sizing and safety outcomes in the
   synthetic benchmark. Keep old raw-proposal results explicitly historical.
5. Test invalid output, HOLD without execution, calculated amounts, stale state,
   cancellation and schedule claims; run lint, types, API/UI and local-chain checks.

Limitations: bounded two-action agent, fixed-price fake assets, model HOLD may delay
progress, and benchmark agreement is not proof of profitability or time savings.

## Architecture and boundaries

Build a modular FastAPI monolith, React client, PostgreSQL database and local Anvil chain. The interpreter returns a validated draft only. Owner review activates an immutable policy version. The portfolio agent produces typed proposals; deterministic policy rules, RPC simulation and deterministic risk assessment independently gate execution. A restricted smart account is a second enforcement boundary. No arbitrary calldata execution endpoint exists.

## Components and data

Persist users, wallets, policy versions, agent runs, immutable proposals, simulation results, risk assessments, approvals, execution records and append-only application audit events. Proposal digests bind approvals to exact contents and policy versions. Serialize execution per wallet with database locking; reserve spending before submission and retain uncertain submissions for reconciliation. Store amounts as integer token units or decimal strings, never binary floats.

## Phases and verification

1. Local chain slice: mock tokens/exchange, restricted account, deterministic deployment, Python adapter, balances, permitted execution and denied overspending. Verify contract tests and adapter tests.
2. Typed policy representation, individual rules, version persistence, bounded natural-language interpreter and explicit activation. Verify schema, rule and database tests.
3. Portfolio proposals, RPC simulation, risk findings, decision routing, digest-bound expiring approvals, audit and execution lifecycle. Verify negative cases and API tests.
4. React dashboard, policy review, activity, approvals, transaction details and audit. Verify strict types, lint and build.
5. Compose workflow, integration/demo tests, threat model and operational documentation. Run available checks; explicitly record unavailable tooling rather than claim unrun tests passed.

## Technical decisions

- Only chain 31337 is supported. Startup checks both configuration and RPC identity. Production and public-network operation fail closed.
- Mock WETH uses six decimals and a fixed 1:1 test exchange rate with USDC, deliberately simplifying educational accounting. Neither asset has real value.
- The account exposes narrowly typed swap/transfer operations, never arbitrary target calldata. Owner alone changes agent, pause, target and spending permissions. Exact temporary approvals are cleared after swaps.
- The local interpreter supports a documented bounded grammar and rejects unsupported goals. A provider interface accepts validated structured drafts for future LLM integration.
- Owner authentication uses an environment-provided bearer token. The local unlocked development signer is accessible only through a local RPC network; no browser wallet connection is necessary.
- Use database transactions and wallet locking for concurrency, durable submission intent and a contract operation identifier for replay protection. A crash after submission must never cause blind resubmission.
- Keep the wallet behind an adapter rather than introduce ERC-4337.

## Known limitations

Educational contracts are unaudited. Local RPC accounts are publicly known development identities. A compromised backend can use the agent's remaining on-chain permissions; off-chain audit is not tamper-proof against database administrators. Fixed mock prices do not model real markets, MEV or price oracles. No public testnet, mainnet or multi-user identity provider is included. Owner-enabled local scheduling is implemented in the controlled scheduling slice below. Docker/Foundry availability must be verified in the development environment.


## AI integration continuation (2026-10-04)

Preserve existing modules and contracts. Repair startup diagnostics first; deployment stays explicit. Complete the existing adapter with OpenAI Python SDK Responses, select offline/OpenAI in the application factory, and inject the selected proposer into AgentRuns. Validate address-free intent schemas and map to existing domain models. Store provider/model/schema metadata in existing audit rows without a migration. Add a small mode guide and proposal source to the UI. Verify mocked failure cases, then contract and real Anvil/PostgreSQL flows. No paid calls are part of automated verification.

## Controlled scheduling slice

Add a deterministic goal-improvement check after simulation (and before each execution), with an approved rebalance tolerance defaulting to 500 bps. Skip portfolio generation inside that tolerance. Keep fixed attack fixtures, but subject every stored swap to the goal check. Add a small persisted Automation table bound to an explicitly approved policy version, and wallet flags for emergency freeze and generation reservation. Generate outside database locks so owner freeze stays responsive. One API-lifespan worker polls persisted due times; wallet locks, reservations and pending-proposal checks prevent overlap. Do not replay interrupted runs after restart. Three consecutive generation/blocked/failed outcomes pause scheduling; uncertain submissions freeze immediately. Add owner-only freeze/resume controls using existing smart-account pause and cancelling pending approvals. No scheduler infrastructure, new contract or automatic permission change. Add a focused Agent activity panel and migration; test goal arithmetic, approval rechecks, worker races/restarts and freeze before verifying local chain behavior.

## Usability and measurable autonomy (2026-10-11)

Implement four connected slices:
1. Explicit reviewed tolerance, optional minimum USDC allocation, and per-trade spending ceiling. Preserve immutable approved versions; legacy policies retain their existing interpretation. Enforce minimum allocation from simulated deltas independently of the model. Review pages show percentages and the acceptance range.
2. Calculate live trade direction/amount with integer arithmetic, target distance, remaining daily budget and the approved per-trade ceiling. Never cross the target. Providers interpret goals and explain the calculated plan; raw model proposals are retained only for non-executing comparison. No fallback execution on explanation failure.
3. Share readiness checks between manual and scheduled runs. Expose actionable status, next eligibility, pending proposal links and generation start time. Connect these fields to Activity, Overview and policy review. Move fixed attack scenarios out of the main workflow into an explicitly labelled educational section; retain their negative-test value.
4. Add a small offline scenario suite and optional local Ollama shadow benchmark, reporting correctness, safety blocks, latency, trade count and intervention proxies. Never submit benchmark transactions. Document a manual timing exercise and the limits of these measurements.

Use existing JSON policy storage and audit metadata where possible, avoiding infrastructure or contract changes. The optional allocation floor is an off-chain simulated-state restriction; the educational contract still independently enforces its spending/target/pause boundaries. Test sizing, floor failures, stale approvals, API serialization and UI/backend wiring. Do not reset the user's wallet or activate a policy while developing.
