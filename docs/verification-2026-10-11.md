# Controlled planning and UI verification — 2026-10-11

This report records the earlier explanation-only slice. The subsequent
[bounded AI treasury update](treasury-agent.md) adds HOLD/REBALANCE decisions and
check history; use that report for current behavior and test counts.

## Delivered behavior

- Explicit reviewed tolerance, per-trade ceiling and optional minimum USDC share.
  Existing approved versions are not rewritten.
- Deterministic integer trade sizing, with optional AI explanation. Raw model
  proposals are isolated to synthetic evaluation and adversarial tests.
- Simulated minimum-allocation enforcement, including after owner approval.
- Shared manual/scheduled readiness, actionable reasons, pending-proposal links
  and generation elapsed time. Policy review remains accessible after approval.
- A 16-case read-only Evaluation page and local comparison command.
- Fixed A–D/medium fixtures remain available in a collapsed educational section;
  the old main scenario selector is replaced by Run portfolio check.

No new infrastructure, public chain support, database migration or smart-contract
permission change was introduced by this slice. Existing scheduling migration
0002 is still required for older installations. All new interface text,
documentation and code comments are English.

## Automated checks

| Check | Result |
|---|---|
| Normal Python suite | 215 passed; 6 opt-in integrations skipped in this invocation |
| PostgreSQL locking and concurrent schedule/freeze integrations | Both passed against an isolated PostgreSQL 18 database |
| Anvil adapter, complete API flow, adversarial mock-AI flow and scheduled trade/pause/resume integrations | All four passed separately on isolated chain 31337, with fresh deployments |
| Solidity tests | 14 passed, including the direct daily-limit bypass and 256 fuzz cases |
| Ruff lint and format | Passed; 75 Python files formatted |
| Strict mypy | Passed; 51 source files including new scripts |
| TypeScript and ESLint | Passed |
| Vite production build | Passed |

The six integrations skipped by the ordinary test invocation were explicitly
enabled and run separately; they are not counted as passing because of a skip.
Python reported existing dependency deprecation warnings for websockets and
Starlette/AnyIO. Foundry required access outside the Windows sandbox to locate its
home/compiler cache; its tests then passed.

## Actual browser and Ollama check

Used a separate API/database, Vite port 5190, Anvil port 18545 and local
`llama3:latest`; the user's normal chain was not reset. Created and approved a
95% target policy with a 95% hard minimum, 1-point tolerance and 30-unit trade
ceiling through the UI. Starting from the isolated fixture's 970 USDC / 30 WETH,
Run portfolio check calculated **20 USDC**, obtained an Ollama explanation,
passed policy/simulation/risk and confirmed a local transaction. Transaction
detail showed the minimum-allocation check passing at **950 USDC / 50 WETH**.
Readiness then became **NO TRADE**, disabling further manual generation.

Also verified the persistent active-policy page and both evaluation reports in
the browser. A development hot refresh while formatting the root component reset
the in-memory sign-in; reloading and signing back into the disposable workspace
restored the UI. Temporary test servers were stopped after verification.

## Evaluation and limitations

The deterministic suite matched 16/16 expected actions and amounts. One actual
Ollama shadow run matched 1/16, with zero schema-invalid outputs, 12 hypothetical
blocked results and approximately 25 seconds of total generation time. This
single-machine observation is not a general model ranking. See
[evaluation methodology](evaluation.md) for definitions and a small manual study
to measure time savings rather than infer them from automation alone.

Docker Compose was not executed during this slice, and no paid OpenAI request
was made. Mock assets have equal fixed prices and six decimals. Portfolio
minimums are off-chain checks; the smart account independently enforces its
existing target allowlist, spending, replay and pause restrictions. This remains
an educational, unaudited local prototype.
